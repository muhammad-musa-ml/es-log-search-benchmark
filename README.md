# Elasticsearch mapping-and-query benchmark

<!-- artifact:date:begin -->
Measured <!--artifact:key:dated_at-->2026-09-19T06:30:54.568681-05:00<!--/artifact:key--> on the owner's own machine.
<!-- artifact:date:end -->

<!-- artifact:opening:begin -->
**What this is.** A benchmark built from scratch in 2026-09 on my own machine, so
that what it claims can be checked rather than taken. Two Elasticsearch indices
hold a byte-identical synthetic log corpus and differ in exactly two things -
the mapping, and how the query is written - and what is measured is what that
difference is worth on a log-search path. Every figure below was measured here,
on the date it carries, and this repository's commit dates are that build's own.

**It stands alone, and it backs nothing.** Nothing I publish anywhere else -
no profile, no site, no line on a page about me - cites this repository or
rests on a number in it. It answers one technical question and is not evidence
for anything else. There is no employer named here and no earlier work behind
it, because there is neither: nothing was reproduced, nothing was rebuilt, and
the first time this ran was on the machine it was written on.

| | naive design | explicit design |
|---|---|---|
| mapping | Elasticsearch **dynamic mapping**: every string inferred as analyzed `text` with a `.keyword` sub-field | dimension fields as `keyword`, only the genuine prose field as `text`, real `integer` / `date` types, `dynamic: strict` |
| query | a broad `multi_match` (`cross_fields`, `operator: and`) fanned out across eight fields, in **query context**, so every hit is scored | `bool.filter` with `term` clauses, entirely in **filter context**, so scoring is skipped and clauses are cacheable |
| documents matched | <!--artifact:key:total_hits_naive_design-->2659272<!--/artifact:key--> | <!--artifact:key:total_hits_explicit_design-->2470027<!--/artifact:key--> |
| p95 speedup, server-side `took` | - | <!--artifact:key:server_p95_speedup_x-->3.181818<!--/artifact:key-->x |
| p95 speedup, client-side wall | - | <!--artifact:key:wall_p95_speedup_x-->1.379005<!--/artifact:key-->x |
| documents per index | <!--artifact:key:corpus_doc_count_per_index-->2500000<!--/artifact:key--> | <!--artifact:key:corpus_doc_count_per_index-->2500000<!--/artifact:key--> |
| seeded lookups replayed per arm | <!--artifact:key:queries_replayed_per_arm-->500<!--/artifact:key--> | <!--artifact:key:queries_replayed_per_arm-->500<!--/artifact:key--> |
| runs behind each speedup | <!--artifact:key:server_p95_speedup_x.population-->3<!--/artifact:key--> | <!--artifact:key:server_p95_speedup_x.population-->3<!--/artifact:key--> |

Each speedup is the **weakest** of its runs, never a middle one:
*<!--artifact:key:server_p95_speedup_x.value_rule-->the smallest ratio any replicate produced; every replicate in the population met or beat it<!--/artifact:key-->*. The full per-run rows are in
`RUN-RECORD.md`, the reading of the numbers is in `results/RESULTS.md`, and
nothing anywhere combines one run with another.
<!-- artifact:opening:end -->

Both designs answer the same logical question: *show me events matching this
combination of service / level / region / endpoint.*

## Why the naive side is not a strawman

The naive index is not deliberately crippled. It uses Elasticsearch's own
dynamic mapping, which is exactly what you get when documents are bulk-loaded
without an explicit mapping - the single most common way a log index comes into
existence.

The naive query uses `cross_fields` rather than the `best_fields` default,
deliberately. With `best_fields` plus `operator: and`, every term would have to
appear in one single field, which matches almost nothing - that would have made
the naive side trivially fast **and wrong**, which is a rigged comparison rather
than a benchmark.

## Measurement discipline

- Both corpora are built from the **same seed**, so they are identical, and the
  loader refuses outright if the two live document counts ever differ.
- Both indices are **force-merged to one segment**. Segment count materially
  affects query latency; leaving it to chance would confound the result.
- The **same seeded lookup sample** runs against both, in the same order.
- Each index gets an **uncounted warmup pass**, so neither side pays a
  cold-cache penalty the other avoids. Those lookups are in no distribution.
- **Two independent clocks** are recorded: client-side wall time, which is what
  a caller experiences and includes HTTP transport, and Elasticsearch's own
  reported `took`, which is server-side execution only. Had the two clocks
  disagreed about the direction of the result, the result would not be
  trustworthy.
- Shard and replica counts are pinned identically.
- The node is pinned **by digest**, not by tag, in `docker-compose.yml`. A tag
  resolves to different bytes on different days, and for a benchmark whose whole
  subject is how a search engine behaves, the engine's build is the single
  largest input to the measurement.
- Nothing runs until `gate.py` has recorded the conditions and minted a token,
  and every measurement record carries that token. A gate minted afterwards
  would prove nothing about what preceded what.
- The benchmark was run more than once, each run writing its own records, and no
  figure is computed across them.

### The check that makes the latency number mean something

The two designs do **not** return identical hit sets, and demanding that they do
would be the wrong check. Analyzed `text` fields tokenize dimension values, so
the naive query is genuinely **fuzzier** - imprecision is part of why it is the
wrong tool, not an artifact of this benchmark:

```
dynamic mapping    us-west-2  ->  us / west / 2     (analyzed into three terms)
explicit mapping   us-west-2  ->  us-west-2         (one keyword term)
```

What must hold is one-sided: the fuzzy design should match **at least as many**
documents as the exact one. If the naive side returned *fewer* hits while also
being slower, the speedup would be suspect - a big query being compared against
a small one. The guard asserts that direction and reports both hit totals and
both zero-hit counts, so the divergence is visible rather than hidden.

## Running it

Every command here was executed, in this order, before it was written down.

```
docker compose up -d
pip install -r requirements.txt
python gate.py
python run_benchmark.py --replicate 5
python derive.py
python render.py . --write
docker compose down
```

**`docker compose up -d` rather than a `docker run` line.** The compose file
names the node by digest; a `docker run` line names it by tag, and the two can
resolve to different bytes on a different day or a different machine.

**`python gate.py` first, and it is not optional.** `run_benchmark.py` reads the
gate's token before it opens a socket and refuses if there is none, so a run
nothing authorised cannot spend the machine to discover that.

**`--replicate` must name an index whose records are not already on disk.** The
committed records occupy the first four. Without the flag the run refuses, by
design: writing over a replicate's records would destroy a measurement and leave
a count that still claims it. The corpus size and the lookup count are optional
positional arguments that default to the published configuration, so the line
above runs exactly what was measured here.

A much smaller run exercises the whole path in well under a minute:

```
python run_benchmark.py 20000 50 --replicate 9
```

**It is expected to FAIL a guard, and that is not a broken repository.** At that
corpus size some replayed lookups match nothing on both arms, the coverage guard
fails, and the run says so. That is the guard doing its job; the line is a smoke
test of the path, and it is not a measurement.

The exit codes a reader will actually meet:

```
0  the run completed and every guard passed
2  it REFUSED before measuring anything: no gate yet, or a --replicate index
   whose records are already on disk
3  it ran to completion and a guard FAILED. The records are written and kept,
   and the derivation excludes them by that property and counts them
```

Records land under `results/`, one set per run. `results/RESULTS.md` holds the
measured numbers and the reading of them, `RUN-RECORD.md` holds the per-run rows
and what was decided before anything was measured, and
`RESULTS-2026-07-31-SUPERSEDED.md` holds the first run's document, unedited,
with its two headline ratios marked refuted.

## Layout

```
esbench/docgen.py    seeded synthetic log/event builder
esbench/mappings.py  the two index designs
esbench/queries.py   the seeded query sample + both query formulations
esbench/load.py      bulk load, force-merge, corpus-equality assertion
esbench/bench.py     warmup, replay, percentiles
esbench/guards.py    the guard array every run has to satisfy
gate.py              reads the conditions, records them, mints the run token
run_benchmark.py     driver: one run of both arms, one set of records
derive.py            the only program that authors a published figure
render.py            writes those figures into these documents, and refuses
```

## What this does not show

<!-- artifact:limits:begin -->
This measures one mechanism at one scale on one machine. It does not establish
what any production deployment would do, and no number here may be borrowed for
a differently shaped cluster: a single node with one shard, one segment, a warm
page cache and no competing traffic is the easiest case a search engine ever
sees. Mapping and query formulation move together in this comparison,
deliberately, so the two effects are not separated and this benchmark cannot say
how much each contributes on its own. Index build time, ingest throughput,
memory footprint and relevance quality are all unmeasured - only read latency
and matched-document counts were recorded. The corpus is synthetic and the
lookup sample is seeded and fixed, so an unseen query shape is untested and real
log data has cardinalities and term distributions this does not reproduce.
Absolute latencies here are never comparable with another machine's; the ratio
between the two arms is what travels, and only at this scale, on this workload.
Every run behind these figures was made with nothing else running on the
container engine, and each run's record carries the census that says so - a run
made while the machine is busy with other work is not comparable with them.
<!-- artifact:limits:end -->
