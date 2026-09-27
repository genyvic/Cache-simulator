from __future__ import annotations

from dataclasses import dataclass

from hierarchy import Hierarchy


@dataclass
class LevelReport:
    name: str
    accesses: int
    hits: int
    misses: int
    reads: int
    writes: int
    writebacks: int
    hit_time: float
    local_miss_rate: float
    global_miss_rate: float


@dataclass
class Report:
    levels: list[LevelReport]
    total_accesses: int
    memory_accesses: float
    memory_access_time: float
    amat: float

    def render(self) -> str:
        w = 62
        out: list[str] = []
        out.append("=" * w)
        out.append("CACHE SIMULATION RESULTS".center(w))
        out.append("=" * w)
        out.append(f"Total CPU accesses: {self.total_accesses}")
        out.append("")

        for lv in self.levels:
            out.append(f"--- {lv.name} " + "-" * (w - 5 - len(lv.name)))
            out.append(f"  accesses         : {lv.accesses}")
            out.append(f"  hits             : {lv.hits}")
            out.append(f"  misses           : {lv.misses}")
            out.append(f"  reads / writes   : {lv.reads} / {lv.writes}")
            out.append(f"  writebacks       : {lv.writebacks}")
            out.append(f"  hit time         : {lv.hit_time:g} cycles")
            out.append(f"  local miss rate  : {lv.local_miss_rate:.4%}")
            out.append(f"  global miss rate : {lv.global_miss_rate:.4%}")
            out.append("")

        out.append("--- Main memory " + "-" * (w - 16))
        out.append(f"  accesses         : {self.memory_accesses}")
        out.append(f"  access time      : {self.memory_access_time:g} cycles")
        out.append("")
        out.append("=" * w)
        out.append(f"  AMAT             : {self.amat:.4f} cycles/access")
        out.append("=" * w)
        return "\n".join(out)


def build_report(h: Hierarchy) -> Report:
    total = h.total_accesses if h.total_accesses else 1  # avoid divide-by-zero

    level_reports: list[LevelReport] = []
    for lvl in h.levels:
        s = lvl.stats_dict()
        level_reports.append(
            LevelReport(
                name=lvl.cfg.name,
                accesses=int(s["accesses"]),
                hits=int(s["hits"]),
                misses=int(s["misses"]),
                reads=int(s["reads"]),
                writes=int(s["writes"]),
                writebacks=int(s["writebacks"]),
                hit_time=lvl.cfg.hit_time,
                local_miss_rate=lvl.miss_rate(),        # misses / accesses at this level
                global_miss_rate=s["misses"] / total,   # misses / total CPU accesses
            )
        )

    amat = _compute_amat(h)

    return Report(
        levels=level_reports,
        total_accesses=h.total_accesses,
        memory_accesses=h.memory_accesses,
        memory_access_time=h.memory_access_time,
        amat=amat,
    )


def _compute_amat(h: Hierarchy) -> float:
    # AMAT = hit_time(L1) + miss_rate(L1) * (hit_time(L2) + miss_rate(L2) * mem_time)
    # walked bottom-up so it generalizes to any number of levels
    penalty = h.memory_access_time
    for lvl in reversed(h.levels):
        penalty = lvl.cfg.hit_time + lvl.miss_rate() * penalty
    return penalty
