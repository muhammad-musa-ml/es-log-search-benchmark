# Run record

What was measured, under what conditions, and what was decided before it was measured.

## The replication decision, made 2026-09-19, BEFORE this run

**Three replicates of both arms. Nothing is averaged across them.**

The first run of this benchmark was a SINGLE run. `results/results.json` records
`n_queries: 500`, one load of each index, `total_runtime_seconds: 381.2`, and no replicate
files of any kind. Both headline figures it publishes - a 1.45x client-side p95 reduction and
a 3.89x server-side one - are ratios between one number and one other number. **Both are
withdrawn**, and the two numbers are quoted in this paragraph only to say which ones; the
withdrawal, its date and its reason are recorded in `results/retractions.json`.

Nothing in the planning documents this run inherits answered whether that was enough. The
replication discussion they carry is scoped to a different artifact's measured bimodality and
says nothing about this one, and the open question naming this gap was left open on purpose,
for the plan that ran the measurement to answer. This is that answer, and it is recorded here
rather than in a planning file because a later reader will be holding this repository.

**Three reasons, in the order they decide it:**

1. **A recorded figure is presumed inaccurate until it is measured again.** That is the
   standing rule this whole programme runs on, and it is not satisfied by confirming a single
   sample - confirming one sample against itself is not a measurement, it is a reading. A
   single run is the thing being re-measured; it cannot also be the baseline that re-measures
   it.

2. **A ratio derived from one run of each arm cannot distinguish the effect from the run.**
   Both arms here happen to run inside one process against one loaded corpus, so they share
   whatever the machine was doing - which removes SOME between-arm variance and removes none of
   the between-RUN variance. If the JVM's compilation state, the page cache, or a neighbouring
   container moved one run, a single-run ratio absorbs that movement into the reported effect
   and nothing in the output says so.

3. **It costs minutes.** The first run took 381.2 s. Three replicates is about twenty minutes
   on a machine that is otherwise idle, against a figure that is meant to survive being read by
   a stranger.

**What is NOT done with the three, and why.** No mean across replicates. No standard deviation
across replicates. No "1.45x plus or minus" of any kind -- and that figure is quoted here as
the SHAPE of a summary statistic rather than as a reading, since it is itself withdrawn. Each replicate is one row, reported
individually. If the three runs of an arm disagree, **the disagreement is the finding** - it is
the single most informative thing a replicated measurement can produce, and a summary statistic
is precisely the operation that destroys it. A reader who wants the spread can read the rows.

This is a rule about aggregating ACROSS RUNS. It is not a rule about distribution statistics
WITHIN a run: the arithmetic mean of 500 query latencies, sitting beside that run's p50, p95,
p99 and max, is a property of one measured population and stays. See the adjudication below.

## What is not touched

`results/results.json`, `results/RESULTS.md` and `results/run-full.log` are the July run's
records and this run does not modify, move or delete any of them. They are the BEFORE side the
re-measurement is compared against, and a superseded record that has been overwritten can no
longer be compared against - it can only be described. They are excluded from the derivation,
counted as excluded, and named with their reason.

## The replicates

Every figure in this section is read out of a record the run wrote. One row per arm per
replicate, and the rows are not combined.

| replicate | arm | corpus | lookups | wall p95 ms | server p95 ms | other containers on the VM, start / finish |
|---|---|---|---|---|---|---|
| 1 | `logs-before` | 20,000 | 50 | 70.97 | 22.0 | 0 of 1 / 0 of 1 |
| 1 | `logs-after` | 20,000 | 50 | 54.19 | 4.0 | 0 of 1 / 0 of 1 |
| 2 | `logs-before` | 2,500,000 | 500 | 80.92 | 35.0 | 0 of 1 / 0 of 1 |
| 2 | `logs-after` | 2,500,000 | 500 | 58.68 | 11.0 | 0 of 1 / 0 of 1 |
| 3 | `logs-before` | 2,500,000 | 500 | 81.18 | 37.0 | 0 of 1 / 0 of 1 |
| 3 | `logs-after` | 2,500,000 | 500 | 57.66 | 11.0 | 0 of 1 / 0 of 1 |
| 4 | `logs-before` | 2,500,000 | 500 | 78.64 | 34.0 | 0 of 1 / 0 of 1 |
| 4 | `logs-after` | 2,500,000 | 500 | 56.84 | 10.0 | 0 of 1 / 0 of 1 |

**The ratio each replicate produced, on each clock.** One row per replicate; no row is a
summary of the others.

| replicate | clock | before p95 ms | after p95 ms | delta ms | ratio |
|---|---|---|---|---|---|
| 1 | server `took` | 22.0 | 4.0 | 18.0 | 5.5x |
| 1 | client wall | 70.97 | 54.19 | 16.78 | 1.31x |
| 2 | server `took` | 35.0 | 11.0 | 24.0 | 3.18x |
| 2 | client wall | 80.92 | 58.68 | 22.24 | 1.38x |
| 3 | server `took` | 37.0 | 11.0 | 26.0 | 3.36x |
| 3 | client wall | 81.18 | 57.66 | 23.52 | 1.41x |
| 4 | server `took` | 34.0 | 10.0 | 24.0 | 3.4x |
| 4 | client wall | 78.64 | 56.84 | 21.8 | 1.38x |

## The run chain

| what | value |
|---|---|
| gate token | `b95e85d10fb295abef37c2034bc1a71f6f9182933dba23513867c7ab955897c2` |
| gate decided at | `2026-09-19T06:05:20.323652-05:00` |
| gate assertions | 8 declared, 0 failed |
| gate declared inputs | 11, 0 absent |
| Elasticsearch node | `docker.elastic.co/elasticsearch/elasticsearch@sha256:84a73ced8390c059e7bc2858595c68dc36e6f8bdb98895dcab0074eda35ac96e` |

| replicate | started | finished | wall s | server | client | gate token on record |
|---|---|---|---|---|---|---|
| 1 | `2026-09-19T06:09:32.140401-05:00` | `2026-09-19T06:09:49.153923-05:00` | 16.8 | 8.15.0 | 8.19.3 | `b95e85d10fb2` |
| 2 | `2026-09-19T06:10:24.506645-05:00` | `2026-09-19T06:17:14.868248-05:00` | 410.1 | 8.15.0 | 8.19.3 | `b95e85d10fb2` |
| 3 | `2026-09-19T06:17:19.227704-05:00` | `2026-09-19T06:24:14.652131-05:00` | 415.2 | 8.15.0 | 8.19.3 | `b95e85d10fb2` |
| 4 | `2026-09-19T06:24:18.595607-05:00` | `2026-09-19T06:30:54.568681-05:00` | 395.7 | 8.15.0 | 8.19.3 | `b95e85d10fb2` |

Every `started_at` above is strictly later than the gate's `dated_at`, which is the
ordering a gate minted after a measurement could not satisfy.

## The guards, per replicate

| replicate | guard | verdict | population | floor |
|---|---|---|---|---|
| 1 | `G1-equivalence-one-sided` | pass | 50 | 30 |
| 1 | `G2-workload-coverage` | **FAIL** | 50 | 30 |
| 1 | `G3-two-clocks-agree-in-direction` | pass | 2 | 2 |
| 1 | `G4-corpora-identical-size` | pass | 20,000 | 1 |
| 2 | `G1-equivalence-one-sided` | pass | 500 | 30 |
| 2 | `G2-workload-coverage` | pass | 500 | 30 |
| 2 | `G3-two-clocks-agree-in-direction` | pass | 2 | 2 |
| 2 | `G4-corpora-identical-size` | pass | 2,500,000 | 1 |
| 3 | `G1-equivalence-one-sided` | pass | 500 | 30 |
| 3 | `G2-workload-coverage` | pass | 500 | 30 |
| 3 | `G3-two-clocks-agree-in-direction` | pass | 2 | 2 |
| 3 | `G4-corpora-identical-size` | pass | 2,500,000 | 1 |
| 4 | `G1-equivalence-one-sided` | pass | 500 | 30 |
| 4 | `G2-workload-coverage` | pass | 500 | 30 |
| 4 | `G3-two-clocks-agree-in-direction` | pass | 2 | 2 |
| 4 | `G4-corpora-identical-size` | pass | 2,500,000 | 1 |

| replicate | all guards passed | total runtime s | exit |
|---|---|---|---|
| 1 | False | 16.7 | 3 |
| 2 | True | 410.0 | 0 |
| 3 | True | 415.1 | 0 |
| 4 | True | 395.6 | 0 |

## What the July run recorded, beside what this one did

Read from `results/results.json`, which this run did not touch.

**Both July ratios in the table below are WITHDRAWN figures, quoted here to say
which ones they are.** They sit above every replicate this run measured, on both
clocks, so they are refuted rather than noisy; `results/retractions.json`
records them with their date and their reason, and nothing in this repository
may cite either as a current figure.

| | July, one run (withdrawn) | this run |
|---|---|---|
| documents per index | 2,500,000 | 20,000, 2,500,000, 2,500,000, 2,500,000 |
| lookups replayed per arm | 500 | 50, 500, 500, 500 |
| total runtime s | 381.2 | 16.7, 410.0, 415.1, 395.6 |
| server p95 ratio | 3.89x | 5.5x, 3.18x, 3.36x, 3.4x |
| client wall p95 ratio | 1.45x | 1.31x, 1.38x, 1.41x, 1.38x |
| Elasticsearch server | 8.15.0 | 8.15.0 |
| Python client library | recorded nowhere | 8.19.3 |
| replicates | 1 | 4 |

## Replicate 1 is the documented smoke run, and its guard failure is kept

The first row above is not a campaign replicate. It is the command this repository's own README
documents as the quick check - the one that loads a small corpus and exercises the whole path -
run exactly as written, before the campaign.

It FAILED its own coverage guard, and that is the most useful thing in this record. At smoke
corpus size, lookups in the replayed sample matched nothing on both arms. A benchmark whose fast
arm is fast partly because some of its lookups match nothing is the failure the whole design is
arranged against, and the guard array - authored before any of this was measured - caught it on
its first real run rather than after publication.

So that replicate's records are kept, and they are EXCLUDED from the derivation by the property
they themselves carry: `all_guards_passed` is false. Not by their filename, and not by "the one
with the small corpus", either of which would be a judgement dressed up as a rule and would go
quietly wrong the first time a different replicate failed. The exclusion is counted and named
beside the derivation.

## No statistic is computed across the replicates, and here is how that is checked

The rule is one rule and it has a scope, so the scope is stated rather than left for a reader to
infer.

**What is forbidden:** aggregating ACROSS RUNS. A mean of the replicates, a standard deviation
over them, a ratio quoted as a value plus a spread. Those operations destroy the disagreement
that replication was taken to find, which is the one thing replication produces that a single run
cannot.

**What is not forbidden, and would be wrong to delete:** a distribution statistic WITHIN a single
run. The arithmetic mean of one run's own measured lookup latencies, sitting beside that run's
p50, p95, p99 and max, is a property of one measured population. It is neither an aggregate over
runs nor a claim about a run other than its own. Deleting it to make a text search come out empty
would destroy a real measurement in order to make a checker green, which is the shape of fix this
programme refuses.

**How the two are told apart, mechanically.** Every occurrence of `mean`, `average`, their
inflections, and any standard-deviation token, across this record, the results document and the
README, is classified into exactly one of five classes: a forbidden cross-run aggregate; a
within-run distribution statistic; the ordinary English verb; a quotation of superseded wording;
or a statement of the prohibition itself. The counts of all five print on every run, alongside the
raw hit count, and the classified counts are asserted to sum to the raw one - so a class that
silently stopped being looked for would show up as an identity that no longer closes. The forbidden
count is zero.

The classifier carries live controls in both directions: lines that ARE statistics, which it must
match, and lines using the same words as ordinary English, which it must not. Adding the
prohibition class is itself an example of why the controls matter - the first run of the
classifier flagged this document's own prohibition sentence as a violation of the rule it states.
A prohibition is told from a real aggregate by a test that cannot launder one: it negates the
operation and carries no numeral, because a reported average has to carry the number it reports.

## The measurement window

The programme holds one measurement window and this campaign held it end to end. It was free
before the first command and free again after the last, and it was held by a live process
throughout rather than by a lock file whose owner had exited - the difference between a window
that is held and a lock that merely exists.

## The Elasticsearch node

Brought up from this repository's committed compose file, which names the image by its
multi-platform INDEX digest rather than by a tag. The README's own instructions name the same
image by TAG; on this machine the two resolve to the same bytes, and that was read from the
running container rather than assumed. On another machine, or on another day, a tag need not.

## Containers

Nothing on the Docker engine was started by this campaign except the Elasticsearch node it
measures, and that node was stopped and removed when the campaign finished. The container census
recorded at the start and at the finish of every replicate is in the table above, and it is per
replicate rather than once, because a neighbour that appeared mid-campaign would otherwise be
invisible.
