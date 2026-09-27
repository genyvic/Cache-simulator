from __future__ import annotations

import random
from dataclasses import dataclass

from config import (
    CacheConfig,
    ReplacementPolicy,
    WriteHitPolicy,
    WriteMissPolicy,
)


@dataclass
class CacheLine:
    valid: bool = False
    tag: int = 0
    dirty: bool = False
    last_used: int = 0    # for LRU
    inserted_at: int = 0  # for FIFO


@dataclass
class AccessResult:
    hit: bool
    writeback_addr: int | None = None  # set if a dirty line got evicted
    allocated: bool = False            # true if this access installed a block
    propagate_write: bool = False      # true if the write also needs to go to the next level


class Cache:
    """One cache level. L1 and L2 are just instances of this with different configs."""

    def __init__(self, config: CacheConfig, rng_seed: int | None = None) -> None:
        self.cfg = config
        self.sets: list[list[CacheLine]] = [
            [CacheLine() for _ in range(config.associativity)]
            for _ in range(config.num_sets)
        ]
        self._clock: int = 0
        self._rng = random.Random(rng_seed)

        self.reads = 0
        self.writes = 0
        self.read_hits = 0
        self.write_hits = 0
        self.read_misses = 0
        self.write_misses = 0
        self.writebacks = 0

    @property
    def hits(self) -> int:
        return self.read_hits + self.write_hits

    @property
    def misses(self) -> int:
        return self.read_misses + self.write_misses

    @property
    def accesses(self) -> int:
        return self.hits + self.misses

    def miss_rate(self) -> float:
        return self.misses / self.accesses if self.accesses else 0.0

    def access(self, address: int, is_write: bool) -> AccessResult:
        self._clock += 1
        if is_write:
            self.writes += 1
        else:
            self.reads += 1

        index = self.cfg.set_index(address)
        tag = self.cfg.tag(address)
        ways = self.sets[index]

        for line in ways:
            if line.valid and line.tag == tag:
                return self._on_hit(line, is_write)

        return self._on_miss(address, index, tag, is_write)

    def _on_hit(self, line: CacheLine, is_write: bool) -> AccessResult:
        if is_write:
            self.write_hits += 1
        else:
            self.read_hits += 1

        if self.cfg.replacement == ReplacementPolicy.LRU:
            line.last_used = self._clock

        result = AccessResult(hit=True)

        if is_write:
            if self.cfg.write_hit == WriteHitPolicy.WRITE_BACK:
                line.dirty = True
            else:  # write-through: goes down now, line stays clean
                line.dirty = False
                result.propagate_write = True

        return result

    def _on_miss(
        self, address: int, index: int, tag: int, is_write: bool
    ) -> AccessResult:
        if is_write:
            self.write_misses += 1
        else:
            self.read_misses += 1

        result = AccessResult(hit=False)

        allocate = True
        if is_write and self.cfg.write_miss == WriteMissPolicy.NO_WRITE_ALLOCATE:
            allocate = False
            result.propagate_write = True

        if not allocate:
            return result

        ways = self.sets[index]
        victim = self._choose_victim(ways)

        if victim.valid and victim.dirty:
            self.writebacks += 1
            result.writeback_addr = self._line_address(victim.tag, index)

        victim.valid = True
        victim.tag = tag
        victim.last_used = self._clock
        victim.inserted_at = self._clock

        if is_write:
            if self.cfg.write_hit == WriteHitPolicy.WRITE_BACK:
                victim.dirty = True
            else:
                victim.dirty = False
                result.propagate_write = True
        else:
            victim.dirty = False

        result.allocated = True
        return result

    def _choose_victim(self, ways: list[CacheLine]) -> CacheLine:
        for line in ways:
            if not line.valid:
                return line

        policy = self.cfg.replacement
        if policy == ReplacementPolicy.LRU:
            return min(ways, key=lambda ln: ln.last_used)
        if policy == ReplacementPolicy.FIFO:
            return min(ways, key=lambda ln: ln.inserted_at)
        return self._rng.choice(ways)

    def _line_address(self, tag: int, index: int) -> int:
        block_address = (tag << self.cfg.index_bits) | index
        return block_address << self.cfg.offset_bits

    def stats_dict(self) -> dict[str, float]:
        return {
            "accesses": self.accesses,
            "hits": self.hits,
            "misses": self.misses,
            "reads": self.reads,
            "writes": self.writes,
            "read_misses": self.read_misses,
            "write_misses": self.write_misses,
            "writebacks": self.writebacks,
            "miss_rate": self.miss_rate(),
        }


if __name__ == "__main__":
    cfg = CacheConfig(
        name="TEST",
        size_bytes=32,
        block_bytes=8,
        associativity=1,
        address_bits=32,
    )
    print(cfg.describe())
    c = Cache(cfg)

    # direct-mapped, 4 sets, 8-byte blocks -> 0x00 and 0x20 collide in set 0
    trace = [
        (0x00, False),  # miss, fills set 0
        (0x04, False),  # hit, same block as 0x00
        (0x20, False),  # miss, evicts 0x00 (conflict)
        (0x00, False),  # miss, 0x00 evicted
        (0x00, True),   # hit, now dirty
        (0x20, True),   # miss, evicts dirty 0x00 -> writeback
    ]

    for addr, is_write in trace:
        r = c.access(addr, is_write)
        kind = "W" if is_write else "R"
        note = "HIT " if r.hit else "MISS"
        wb = f"  writeback@0x{r.writeback_addr:X}" if r.writeback_addr is not None else ""
        print(f"  {kind} 0x{addr:02X} -> {note}{wb}")

    print()
    print("Summary:", c.stats_dict())
    assert (c.hits, c.misses, c.writebacks) == (2, 4, 1), "trace above should give 2 hits / 4 misses / 1 writeback"
