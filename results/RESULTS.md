# Measured results

<!-- artifact:run:begin -->
Measured <!--artifact:key:dated_at-->2026-09-19T06:30:54.568681-05:00<!--/artifact:key--> on the owner's own machine, against Elasticsearch
**8.15.0** in Docker - the node is pinned by digest in `docker-compose.yml` -
single node, one shard, no replicas, both indices force-merged to one segment.
Each index holds <!--artifact:key:corpus_doc_count_per_index-->2500000<!--/artifact:key--> documents; each arm
replays <!--artifact:key:queries_replayed_per_arm-->500<!--/artifact:key--> seeded logical lookups after an
uncounted warmup pass that is in no distribution below.

Both arms run in one process against one loaded corpus, and that pairing is what
makes this a comparison. The whole thing was run
<!--artifact:key:server_p95_speedup_x.population-->3<!--/artifact:key--> times over, and the per-run rows are
in `RUN-RECORD.md`. Nothing here is combined across those runs.
<!-- artifact:run:end -->

## What the mapping change bought

Two clocks are recorded on every lookup, and both are reported here, because
quoting only the flattering one would be the whole problem. Server-side `took`
is Elasticsearch's own reported execution time. Client-side wall time includes
HTTP transport and Python-client overhead, which puts a roughly constant floor
under it that no index design can touch, so it is smaller by construction.

<!-- artifact:latency:begin -->
| clock | p95 speedup | population |
|---|---|---|
| server-side `took` | <!--artifact:key:server_p95_speedup_x-->3.181818<!--/artifact:key-->x | <!--artifact:key:server_p95_speedup_x.population-->3<!--/artifact:key--> |
| client-side wall | <!--artifact:key:wall_p95_speedup_x-->1.379005<!--/artifact:key-->x | <!--artifact:key:wall_p95_speedup_x.population-->3<!--/artifact:key--> |

**Each of those is the WEAKEST of its runs, not a middle.** The rule, in the
record's own words: *<!--artifact:key:server_p95_speedup_x.value_rule-->the smallest ratio any replicate produced; every replicate in the population met or beat it<!--/artifact:key-->*. The
population behind both is <!--artifact:key:server_p95_speedup_x.population_label-->replicates in which the same seeded lookup sample was replayed against both index designs<!--/artifact:key-->.

What the server-side figure is NOT:
<!--artifact:key:server_p95_speedup_x.not_shown-->Server-side `took` only: Elasticsearch's own reported execution time, excluding HTTP transport and client overhead. It is the honest measure of what the mapping change bought and must never be read as what a caller experiences -- the wall-clock figure beside it is that. The published value is the WEAKEST of the replicates, not a central tendency; the raw runs travel in `runs`.<!--/artifact:key-->
<!-- artifact:latency:end -->

The two clocks disagree in magnitude and agree in direction, which is the
expected and correct outcome. If they had disagreed about the direction, the
result would not be trustworthy and this document would be saying so instead.

## The check that makes the latency number mean something

The two designs do **not** return identical hit sets, and demanding that they do
would be the wrong check. Analyzed `text` fields tokenize a dimension value into
several terms, so the naive query is genuinely **fuzzier** - imprecision is part
of why it is the wrong tool, not an artifact of this benchmark:

```
dynamic mapping    us-west-2  ->  us / west / 2      (three analyzed terms)
explicit mapping   us-west-2  ->  us-west-2          (one keyword term)
```

What must hold is one-sided: the fuzzy design has to match **at least as many**
documents as the exact one. If the naive side returned fewer hits while also
being slower, the speedup would be suspect - a big query compared against a
small one.

<!-- artifact:guard:begin -->
| | matched documents |
|---|---|
| naive design (dynamic mapping, `multi_match`) | <!--artifact:key:total_hits_naive_design-->2659272<!--/artifact:key--> |
| explicit design (`keyword` + filter context) | <!--artifact:key:total_hits_explicit_design-->2470027<!--/artifact:key--> |

Lookups that matched nothing, on either arm, in any run:
<!--artifact:key:zero_hit_lookups-->0<!--/artifact:key--> out of <!--artifact:key:zero_hit_lookups.denominator-->3000<!--/artifact:key-->
<!--artifact:key:zero_hit_lookups.population_label-->arm replays examined for lookups that matched nothing (both arms of every replicate)<!--/artifact:key-->.

That zero is a MEASURED zero and the denominator beside it is what makes it one.
<!--artifact:key:total_hits_naive_design.not_shown-->Summed over the whole replayed sample, not per lookup. The two designs are NOT expected to return identical hit sets: analyzed text fields tokenize dimension values, so the dynamic-mapping design is genuinely fuzzier and matches a superset. That is what makes it the wrong tool, not an artifact of the benchmark.<!--/artifact:key-->
<!-- artifact:guard:end -->

So the faster arm was not bought by returning less work, which is the one way a
comparison like this usually cheats. Both totals are deterministic functions of
the seed and the lookup order, and the derivation REFUSES, naming the disagreeing
values, if two runs ever disagree about either of them.

## What produced the difference

1. **Scoring versus filtering.** The naive query runs in query context, so Lucene
   scores every match across all eight analyzed fields. The explicit query runs
   entirely in filter context - no scoring, and the clauses are eligible for the
   node query cache.
2. **Analyzed `text` versus `keyword`.** Dimension values are tokenized and
   matched as several terms under dynamic mapping; as `keyword` each is one exact
   term with a single postings lookup.
3. **Field fan-out.** `cross_fields` blends statistics across every listed field;
   the term filters touch exactly the fields they name.

## What changed when it was run again

This benchmark was first run once, in July, and both ratios it published then are
REFUTED by the re-measurement above rather than merely out of date. That
document is kept whole and unedited as `RESULTS-2026-07-31-SUPERSEDED.md`, and
its raw records are still on disk and still tracked as `results/results.json` and
`results/run-full.log`. The derivation reads neither, and counts and names both
as excluded.

**Where the disagreement lives is the useful part, and it is not where a reader
would guess.** On the server clock, the first run's `before` p95 sits inside the
spread the later runs measured - the naive arm reproduces. Its `after` p95 sits
BELOW every one of them. So the ratio fell because the FAST side was measured
optimistically the first time, not because the baseline drifted. The per-run rows
that show this are in `RUN-RECORD.md`; none of them is combined with any other.

One further run was made at a much smaller corpus size. It ran to completion and
its own coverage guard failed, because at that size a fraction of the replayed
lookups matched nothing on both arms - which is exactly the condition that would
have made a fast arm fast for the wrong reason. Its records are kept, excluded by
the property they carry rather than by their name, and counted as excluded.

## What this does not show

<!-- artifact:limits:begin -->
This is a measurement of two index designs on one laptop on one day, and it is
not a measurement of Elasticsearch. It does not establish what a production
cluster would do: one node, one shard, one segment, a warm page cache and no
concurrent query load is the easiest case a search engine ever sees, and nothing
here is measured under sharding, replication, query concurrency, deep pagination
or memory pressure. Every query asks for a small page of hits, so paging deep
into a result set is untested and the numbers say nothing about it. The corpus is
synthetic, so its cardinalities and term distributions are only as realistic as
the code that wrote them, and real log data is not that. The lookup sample is
seeded and fixed, so it cannot tell a reader what an unseen query shape costs.
No absolute latency here is comparable with another machine's; only the ratio
between the two arms is, and only on this workload at this scale. Every run
behind these figures was made with nothing else running on the container engine,
and each run's record carries the census that says so - so a ratio measured
while the machine is busy with other work cannot be put beside these.
<!-- artifact:limits:end -->

## Reproducing

Every command below was run, in this order, before it was written down.

```
docker compose up -d
pip install -r requirements.txt
python gate.py
python run_benchmark.py --replicate 5
python derive.py
python render.py . --write
docker compose down
```

`run_benchmark.py` takes the corpus size and the lookup count as optional
positional arguments and defaults both to the published configuration, so the
line above runs what was measured here. `--replicate` picks which run's records
to write, and it must name an index that is not already on disk: the committed
records occupy the first four, and writing over one would destroy a measurement
while leaving a count that still claims it. Both the corpus and the query sample
are seeded, so a run is reproducible.
