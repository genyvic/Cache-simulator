from __future__ import annotations

from config import SimConfig
from cache import Cache, AccessResult


class Hierarchy:
    """Wires cache levels together: L1 -> L2 -> memory."""

    def __init__(self, config: SimConfig, rng_seed: int | None = None) -> None:
        self.cfg = config

        self.levels: list[Cache] = [Cache(config.l1, rng_seed=rng_seed)]
        if config.l2 is not None:
            self.levels.append(Cache(config.l2, rng_seed=rng_seed))

        self.memory_access_time = config.memory_access_time
        self.memory_accesses = 0
        self.total_accesses = 0

    def access(self, address: int, is_write: bool) -> AccessResult:
        self.total_accesses += 1
        return self._send(0, address, is_write)

    def _send(self, level_idx: int, address: int, is_write: bool) -> AccessResult | None:
        if level_idx >= len(self.levels):
            self.memory_accesses += 1
            return None

        result = self.levels[level_idx].access(address, is_write)

        # miss that installed a block -> fetch it from the next level
        if not result.hit and result.allocated:
            self._send(level_idx + 1, address, is_write=False)

        # write-through hit or no-write-allocate miss -> forward the write
        if result.propagate_write:
            self._send(level_idx + 1, address, is_write=True)

        # dirty line evicted -> write it down to the next level
        if result.writeback_addr is not None:
            self._send(level_idx + 1, result.writeback_addr, is_write=True)

        return result

    @property
    def l1(self) -> Cache:
        return self.levels[0]

    @property
    def l2(self) -> Cache | None:
        return self.levels[1] if len(self.levels) > 1 else None

    def summary(self) -> str:
        lines = []
        for lvl in self.levels:
            s = lvl.stats_dict()
            lines.append(
                f"{lvl.cfg.name}: {s['accesses']} acc, {s['hits']} hits, "
                f"{s['misses']} misses, miss_rate={s['miss_rate']:.4f}, "
                f"writebacks={s['writebacks']}"
            )
        lines.append(f"Main memory: {self.memory_accesses} accesses")
        return "\n".join(lines)


if __name__ == "__main__":
    from config import CacheConfig, SimConfig

    # L1: 2 sets, L2: 4 sets, both direct-mapped, 8-byte blocks
    l1 = CacheConfig(name="L1", size_bytes=16, block_bytes=8, associativity=1, hit_time=1.0)
    l2 = CacheConfig(name="L2", size_bytes=32, block_bytes=8, associativity=1, hit_time=10.0)
    cfg = SimConfig(l1=l1, l2=l2, memory_access_time=100.0)
    print(cfg.describe())
    print()

    h = Hierarchy(cfg)
    trace = [
        (0x00, False), (0x08, False), (0x00, False), (0x10, False),
        (0x00, False), (0x00, True), (0x10, False),
    ]
    for i, (addr, is_write) in enumerate(trace, 1):
        r = h.access(addr, is_write)
        kind = "W" if is_write else "R"
        note = "HIT " if r.hit else "MISS"
        print(f"  {i}. {kind} 0x{addr:02X} -> L1 {note}")

    print()
    print(h.summary())

    l1, l2 = h.l1, h.l2
    assert (l1.hits, l1.misses, l1.writebacks) == (2, 5, 1), "L1 numbers are off"
    assert l2 is not None and (l2.hits, l2.misses) == (3, 3), "L2 numbers are off"
    assert h.memory_accesses == 3, "memory access count is off"
