# Superseded: the first run's results, 2026-07-31

**This document is kept for comparison and its two headline ratios are REFUTED,
not merely out of date.** It is the record of the FIRST run of this benchmark,
which was a single run of each arm. Everything below this header is that
document exactly as it was written, unedited.

The benchmark was re-measured on 2026-09-19 at three replicates of each arm.
Both ratios below sit ABOVE every replicate measured then, on both clocks:

- the server-side `took` p95 ratio, on the three replicates, and
- the client-side wall p95 ratio, on the same three.

The current measured results are in `results/RESULTS.md`, and the per-replicate
rows they rest on are in `RUN-RECORD.md`. The raw records of the run below are
still on disk and still tracked, as `results/results.json` and
`results/run-full.log`; the derivation reads neither, and counts and names both
as excluded.

**Why this file exists rather than an edit.** A superseded record that has been
overwritten can only be described, never compared -- and the comparison is the
finding. Nothing below was changed, including the sentences that are now wrong.

**The two markers that were added, and the only thing they change.** Everything
below the rule is wrapped in a paired `artifact:frozen` region. The markers are
HTML comments: they add no word a reader sees and they change no sentence, so
the paragraph above stays true. What they do is make this document's own header
MACHINE-READABLE. A standing check hunts every withdrawn figure across the whole
tree and classifies each appearance, and its ordinary rule is a radius -- a
withdrawal marker within twelve lines. A whole-document historical record does
not fit inside a radius: the adjudication is up here and the figures are thirty
lines down, so without the region this file reads to that check as three current
assertions of refuted ratios.

The alternative was to exempt the file by NAME, and that is refused on purpose.
A document that gets immunity from its name is the one place a live claim can
hide, and the check counts and names every hit this region froze, so a reader
can see exactly how much the declaration is covering.

---

<!-- artifact:frozen:begin -->

# Measured results

Run 2026-07-31. Elasticsearch **8.15.0** in Docker, single node, 2 GB heap.
**2,500,000 documents** per index, both force-merged to **1 segment**, 1 shard, 0 replicas.
**500 seeded logical lookups** replayed against each index after an uncounted 50-query warmup.
Total runtime 381 s.

## Latency

### Server-side (Elasticsearch's own reported `took`)

| | p50 | **p95** | p99 | mean | max |
|---|---|---|---|---|---|
| **before** (dynamic mapping + `multi_match`) | 19 ms | **35 ms** | 45 ms | 18.97 ms | 52 ms |
| **after** (explicit `keyword` + filter context) | 7 ms | **9 ms** | 10 ms | 6.27 ms | 13 ms |

**p95: 35 ms to 9 ms - a 3.89x reduction.**

### Client-side wall time (includes HTTP transport)

| | p50 | **p95** | p99 | mean | max |
|---|---|---|---|---|---|
| **before** | 63.63 ms | **81.63 ms** | 90.21 ms | 63.06 ms | 98.77 ms |
| **after** | 52.32 ms | **56.15 ms** | 58.46 ms | 52.10 ms | 60.99 ms |

**p95: 81.63 ms to 56.15 ms - a 1.45x reduction.**

The two clocks disagree in MAGNITUDE and agree in DIRECTION, which is the expected and
correct outcome. Wall time carries a roughly 47 ms constant floor of Python-client and
HTTP round-trip overhead that the index design cannot touch, so it dilutes the ratio. The
server-side `took` is the honest measure of what the mapping change bought; the wall clock
is the honest measure of what a caller on this transport actually feels. Both are reported
because quoting only the flattering one would be the whole problem.

## The guard that makes the number mean something

| | value |
|---|---|
| total hits, before | 2,659,272 |
| total hits, after | 2,470,027 |
| before is a superset by volume | **True** |
| zero-hit queries, before | 0 |
| zero-hit queries, after | 0 |

The naive design matched **more** documents (2.66M vs 2.47M) and was still 3.89x slower at
p95. The speedup was therefore not bought by returning less work - which is the one way a
comparison like this usually cheats. Zero-hit counts of 0 on both sides confirm both
formulations actually answer the workload rather than silently matching nothing.

The two designs do **not** return identical hit sets, and they are not supposed to:
analyzed `text` fields tokenize `us-west-2` into `us` / `west` / `2`, so the naive query is
genuinely fuzzier. Imprecision is part of why it is the wrong tool.

## What produced the difference

1. **Scoring vs filtering.** The before query runs in query context, so Lucene scores every
   match across 8 analyzed fields. The after query runs entirely in filter context - no
   scoring, and clauses are eligible for the node query cache.
2. **Analyzed `text` vs `keyword`.** Dimension values like `auth-api` and `us-west-2` are
   tokenized and matched as multiple terms under dynamic mapping; as `keyword` they are one
   exact term with a single postings lookup.
3. **Field fan-out.** `cross_fields` blends statistics across all 8 listed fields; the term
   filters touch exactly the fields named.

## Honest limits on these numbers

- Single node, on a laptop, 1 shard, 1 segment, warm OS page cache, no concurrent load.
  Production numbers on a sharded multi-node cluster under real query concurrency will
  differ, likely substantially.
- 2.5M documents is a small index by Elasticsearch standards.
- `size: 10` on every query. Deep pagination would change the picture.
- The corpus is synthetic. Real log data has different cardinality and term distributions.

What the run does establish, and all it establishes: **on an identical corpus, holding
shards, segments, warmup and query set constant, the mapping-and-query redesign reduced
server-side p95 from 35 ms to 9 ms while matching a superset of the documents.**

## Reproducing

```
docker run -d --name es-bench -p 9200:9200 \
  -e discovery.type=single-node -e xpack.security.enabled=false \
  -e "ES_JAVA_OPTS=-Xms2g -Xmx2g" \
  docker.elastic.co/elasticsearch/elasticsearch:8.15.0
pip install -r requirements.txt
python run_benchmark.py 2500000 500
```

Both the corpus and the query sample are seeded, so the run is reproducible.
Raw output: `results/results.json`, `results/run-full.log`.

<!-- artifact:frozen:end -->
