from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ReplacementPolicy(str, Enum):
    LRU = "LRU"
    FIFO = "FIFO"
    RANDOM = "RANDOM"


class WriteHitPolicy(str, Enum):
    WRITE_BACK = "WRITE_BACK"
    WRITE_THROUGH = "WRITE_THROUGH"


class WriteMissPolicy(str, Enum):
    WRITE_ALLOCATE = "WRITE_ALLOCATE"
    NO_WRITE_ALLOCATE = "NO_WRITE_ALLOCATE"


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _log2(n: int) -> int:
    if not _is_power_of_two(n):
        raise ValueError(f"{n} is not a power of two")
    return n.bit_length() - 1


@dataclass
class CacheConfig:
    """Settings for one cache level, plus the derived tag/index/offset math."""

    name: str
    size_bytes: int
    block_bytes: int
    associativity: int
    hit_time: float = 1.0

    replacement: ReplacementPolicy = ReplacementPolicy.LRU
    write_hit: WriteHitPolicy = WriteHitPolicy.WRITE_BACK
    write_miss: WriteMissPolicy = WriteMissPolicy.WRITE_ALLOCATE

    address_bits: int = 32

    # derived in __post_init__
    num_sets: int = field(init=False)
    offset_bits: int = field(init=False)
    index_bits: int = field(init=False)
    tag_bits: int = field(init=False)

    def __post_init__(self) -> None:
        if not _is_power_of_two(self.size_bytes):
            raise ValueError(f"[{self.name}] size_bytes must be a power of two")
        if not _is_power_of_two(self.block_bytes):
            raise ValueError(f"[{self.name}] block_bytes must be a power of two")
        if not _is_power_of_two(self.associativity):
            raise ValueError(f"[{self.name}] associativity must be a power of two")
        if self.block_bytes > self.size_bytes:
            raise ValueError(f"[{self.name}] block_bytes can't exceed size_bytes")

        bytes_per_set = self.block_bytes * self.associativity
        if self.size_bytes % bytes_per_set != 0:
            raise ValueError(
                f"[{self.name}] size_bytes must be divisible by "
                f"block_bytes * associativity ({bytes_per_set})"
            )
        self.num_sets = self.size_bytes // bytes_per_set

        self.offset_bits = _log2(self.block_bytes)
        self.index_bits = _log2(self.num_sets)
        self.tag_bits = self.address_bits - self.offset_bits - self.index_bits
        if self.tag_bits < 0:
            raise ValueError(f"[{self.name}] address_bits too small for this cache")

    def block_address(self, address: int) -> int:
        return address >> self.offset_bits

    def set_index(self, address: int) -> int:
        return self.block_address(address) & (self.num_sets - 1)

    def tag(self, address: int) -> int:
        return self.block_address(address) >> self.index_bits

    def split(self, address: int) -> tuple[int, int, int]:
        offset = address & (self.block_bytes - 1)
        index = self.set_index(address)
        tag = self.tag(address)
        return tag, index, offset

    def describe(self) -> str:
        return (
            f"{self.name}: {self.size_bytes} B, {self.block_bytes} B blocks, "
            f"{self.associativity}-way, {self.num_sets} sets | "
            f"tag/index/offset = {self.tag_bits}/{self.index_bits}/{self.offset_bits} bits | "
            f"repl={self.replacement.value}, "
            f"write={self.write_hit.value}+{self.write_miss.value}"
        )


@dataclass
class SimConfig:
    """L1 + optional L2 + main memory latency."""

    l1: CacheConfig
    l2: CacheConfig | None = None
    memory_access_time: float = 100.0

    def describe(self) -> str:
        lines = [self.l1.describe()]
        if self.l2 is not None:
            lines.append(self.l2.describe())
        lines.append(f"Main memory access time: {self.memory_access_time} cycles")
        return "\n".join(lines)


def default_config() -> SimConfig:
    l1 = CacheConfig(name="L1", size_bytes=32 * 1024, block_bytes=64, associativity=8, hit_time=1.0)
    l2 = CacheConfig(name="L2", size_bytes=256 * 1024, block_bytes=64, associativity=8, hit_time=10.0)
    return SimConfig(l1=l1, l2=l2, memory_access_time=100.0)


if __name__ == "__main__":
    cfg = default_config()
    print(cfg.describe())
    print()
    addr = 0x1A2B3C4D
    tag, index, offset = cfg.l1.split(addr)
    print(f"Address 0x{addr:08X} in L1 -> tag=0x{tag:X}, set={index}, offset={offset}")
    assert (tag, index, offset) == (0x1A2B3, 49, 0xD), "split() math is off"
