"""
Run: python simulator.py <trace file> [options]

Trace lines (blank lines and '#' comments skipped):
    R 7fffa4c8       R/W, or 0/1 dinero-style, hex address, optional ",size" suffix
"""

from __future__ import annotations

import argparse
import sys

from typing import Iterator

from config import (
    CacheConfig, SimConfig,
    ReplacementPolicy, WriteHitPolicy, WriteMissPolicy,
)
from hierarchy import Hierarchy
from stats import build_report


_READ_TOKENS = {"r", "read", "l", "load", "0", "2", "i"}  # 2/i = instr fetch, treated as read
_WRITE_TOKENS = {"w", "write", "s", "store", "1"}


def parse_trace(path: str) -> Iterator[tuple[bool, int]]:
    with open(path, "r") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                raise ValueError(f"{path}:{lineno}: cannot parse line: {raw!r}")

            op_token = parts[0].lower()
            addr_token = parts[1]

            if op_token in _WRITE_TOKENS:
                is_write = True
            elif op_token in _READ_TOKENS:
                is_write = False
            else:
                raise ValueError(f"{path}:{lineno}: unknown op {parts[0]!r}")

            address = int(addr_token, 16)
            yield is_write, address


def build_config(args: argparse.Namespace) -> SimConfig:
    repl = ReplacementPolicy(args.repl)
    write_hit = WriteHitPolicy(args.write_hit)
    write_miss = WriteMissPolicy(args.write_miss)

    l1 = CacheConfig(
        name="L1",
        size_bytes=args.l1_size,
        block_bytes=args.block,
        associativity=args.l1_assoc,
        hit_time=args.l1_hit,
        replacement=repl,
        write_hit=write_hit,
        write_miss=write_miss,
        address_bits=args.addr_bits,
    )

    l2 = None
    if not args.no_l2:
        l2 = CacheConfig(
            name="L2",
            size_bytes=args.l2_size,
            block_bytes=args.block,
            associativity=args.l2_assoc,
            hit_time=args.l2_hit,
            replacement=repl,
            write_hit=write_hit,
            write_miss=write_miss,
            address_bits=args.addr_bits,
        )

    return SimConfig(l1=l1, l2=l2, memory_access_time=args.mem_time)


def make_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Trace-driven L1/L2 cache simulator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("trace", help="path to the trace file")

    p.add_argument("--block", type=int, default=64, help="block size (bytes)")
    p.add_argument("--l1-size", type=int, default=32 * 1024, help="L1 size (bytes)")
    p.add_argument("--l1-assoc", type=int, default=8, help="L1 associativity")
    p.add_argument("--l2-size", type=int, default=256 * 1024, help="L2 size (bytes)")
    p.add_argument("--l2-assoc", type=int, default=8, help="L2 associativity")
    p.add_argument("--no-l2", action="store_true", help="single-level cache only")

    p.add_argument("--l1-hit", type=float, default=1.0, help="L1 hit time")
    p.add_argument("--l2-hit", type=float, default=10.0, help="L2 hit time")
    p.add_argument("--mem-time", type=float, default=100.0, help="memory access time")

    p.add_argument("--repl", default="LRU",
                   choices=[e.value for e in ReplacementPolicy])
    p.add_argument("--write-hit", default="WRITE_BACK",
                   choices=[e.value for e in WriteHitPolicy])
    p.add_argument("--write-miss", default="WRITE_ALLOCATE",
                   choices=[e.value for e in WriteMissPolicy])

    p.add_argument("--addr-bits", type=int, default=32, help="address width (bits)")
    p.add_argument("--seed", type=int, default=None, help="RNG seed for RANDOM repl")
    return p


def main(argv: list[str] | None = None) -> int:
    args = make_arg_parser().parse_args(argv)
    config = build_config(args)

    print(config.describe())
    print()

    h = Hierarchy(config, rng_seed=args.seed)

    try:
        for is_write, address in parse_trace(args.trace):
            h.access(address, is_write)
    except FileNotFoundError:
        print(f"error: trace file not found: {args.trace}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(build_report(h).render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
