# Cache Simulator

A small trace-driven L1/L2 cache simulator written in Python. Feed it a memory
trace (a list of reads/writes with hex addresses) and it'll walk each access
through the cache hierarchy, tally hits/misses/writebacks per level, and print
a report with miss rates and AMAT (average memory access time).

Mostly built to play around with how associativity, block size, and
replacement policy actually move the numbers, rather than just reading about
it.

## Running it

```
python simulator.py sample.trace
```

That uses the default config (32 KB 8-way L1, 256 KB 8-way L2, 64-byte
blocks, LRU, write-back + write-allocate). Output looks like:

```
L1: 32768 B, 64 B blocks, 8-way, 64 sets | tag/index/offset = 20/6/6 bits | repl=LRU, write=WRITE_BACK+WRITE_ALLOCATE
L2: 262144 B, 64 B blocks, 8-way, 512 sets | tag/index/offset = 17/9/6 bits | repl=LRU, write=WRITE_BACK+WRITE_ALLOCATE
Main memory access time: 100.0 cycles

==============================================================
                   CACHE SIMULATION RESULTS
==============================================================
Total CPU accesses: 46

--- L1 -------------------------------------------------------
  accesses         : 46
  hits             : 30
  misses           : 16
  ...

  AMAT             : 39.2609 cycles/access
==============================================================
```

### Options

```
--block N            block size in bytes            (default 64)
--l1-size N           L1 size in bytes               (default 32768)
--l1-assoc N          L1 associativity                (default 8)
--l2-size N           L2 size in bytes                (default 262144)
--l2-assoc N          L2 associativity                (default 8)
--no-l2               single-level cache only

--l1-hit N            L1 hit time (cycles)            (default 1)
--l2-hit N            L2 hit time (cycles)            (default 10)
--mem-time N          main memory access time         (default 100)

--repl {LRU,FIFO,RANDOM}
--write-hit {WRITE_BACK,WRITE_THROUGH}
--write-miss {WRITE_ALLOCATE,NO_WRITE_ALLOCATE}

--addr-bits N         address width in bits            (default 32)
--seed N              RNG seed, only matters for --repl RANDOM
```

Sizes and block/associativity values need to be powers of two, and
`size_bytes` has to divide evenly by `block_bytes * associativity` — the sim
will complain with a specific error if the numbers don't fit.

## Trace format

One access per line: an op token, then a hex address. Blank lines and `#`
comments are skipped.

```
R 00001000
W 00001000
```

It also accepts dinero-style tokens (`0`/`1` for read/write, `l`/`s` for
load/store, `i` for instruction fetch — treated as a read).

## Layout

- `cache.py` — one cache level: hit/miss logic, LRU/FIFO/random replacement,
  dirty-line tracking, writebacks
- `config.py` — `CacheConfig`/`SimConfig` plus the tag/index/offset bit math
- `hierarchy.py` — wires L1 → L2 → main memory together, forwards misses and
  writebacks down the chain
- `stats.py` — turns raw counters into a report (local/global miss rate,
  AMAT)
- `simulator.py` — CLI entry point and trace file parser
- `sample.trace` — a small trace with some spatial/temporal locality, mostly
  for trying things out

Each module also has a little `if __name__ == "__main__":` block at the
bottom with a hand-worked example and an assertion against the expected
numbers, if you want to check the logic without running a full trace.
