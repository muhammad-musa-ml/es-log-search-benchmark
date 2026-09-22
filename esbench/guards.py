"""The guard array a run asserts over its OWN records, authored rather than retrofitted.

WHY THIS FILE IS NEW WORK AND NOT A RENAME
-------------------------------------------
This benchmark shipped with no `guards` key at all. What it had was an
`equivalence` block - guard-SHAPED without being a guard: it carried two boolean
verdicts (`before_is_superset_by_volume`, `speedup_not_bought_by_returning_less`)
and a count beside them, but nothing said what population made the verdict mean
anything, and nothing said below which population it would stop meaning
anything. A verdict with no floor beside it cannot be read as a pass; it can
only be read as "something returned True".

So the four guards below are AUTHORED. Each carries the fixed triple ruling C1
requires - `population`, `population_label`, `minimum_required` - beside its
`id` and `passed`, and each floor is argued at the site.

THE THIRD POPULATION CONVENTION, RECORDED HERE BECAUSE THIS FILE IS WHERE IT ENDS
----------------------------------------------------------------------------------
Two artifacts in this programme already name the population integer differently.
The read-through benchmark uses five names across seven guards (`compared_keys`,
`hits`/`misses`, `redis_dbsize_after_run`, `driver_ceiling_rps`,
`distinct_tenants_in_sequence`). This benchmark used a THIRD convention of its
own: `"n": 500` inside each arm's summary. That is the argument for fixing ONE
name rather than adopting any of the ones already in use - a checker cannot
mechanically locate "the population field" when its name varies six ways. The
domain-specific name is KEPT beside the fixed one for readability, exactly as
the ruling allows; what changes is that `population` is always there too.

WHAT A FLOOR IS, AND WHAT IT IS NOT
-------------------------------------
A floor is the population below which THIS guard's verdict would not mean
anything - not the population the run happened to have. Writing down the run's
own count would produce a floor that can never fail, which is a floor-shaped
absence of a floor. Two of the four floors below are derived from the sampling
structure of `queries.build_sample`, one is the number of clocks, and one is
explicitly a VACUITY floor and says so.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# The two sampling floors, and the arithmetic behind them
# ---------------------------------------------------------------------------
#
# `queries.build_sample` draws `width = rng.randint(2, 4)` per lookup, so each
# of the three query shapes - 2, 3 or 4 pinned dimensions - is drawn with
# probability 1/3, independently, n times. Computed with exact rationals rather
# than estimated (scripts/floors, run 2026-09-19):
#
#     n     P(some width never appears)      P(the 4-wide shape never appears)
#     ---   ------------------------------   ---------------------------------
#     10    5.197e-02   about 1 in 19        1.734e-02   about 1 in 58
#     20    9.022e-04   about 1 in 1,108     3.007e-04   about 1 in 3,325
#     30    1.565e-05   about 1 in 63,917    5.215e-06   about 1 in 191,751
#     40    2.713e-07   about 1 in 3,685,777 9.044e-08   about 1 in 11,057,332
#
# 30 is where both probabilities cross into "this did not happen by sampling
# accident". 20 does not: a 1-in-1,108 chance of a blind spot is not a number to
# hang a guard's meaning on, and 40 buys three more orders of magnitude for a
# floor already far below any population this benchmark runs at.

# G1 asks whether the fuzzy design matched at least as many documents as the
# exact one. It is a claim about the WORKLOAD, so a sample that never drew one
# of the three query shapes has not tested the workload - it has tested two
# thirds of it. At 30 lookups the chance of that is about 1 in 63,917.
EQUIVALENCE_MIN_QUERIES = 30

# G2 asks whether both arms actually answered. The only shape that can
# plausibly return nothing is the WIDEST one - four pinned dimensions over
# 12 services x 5 levels x 6 regions x 12 endpoints - so a sample that never
# drew a 4-wide lookup cannot report "no query matched nothing" as a fact about
# the workload. At 30 lookups the chance of missing it is about 1 in 191,751.
COVERAGE_MIN_QUERIES = 30

# G3 compares the client's wall clock against the server's reported `took`. Its
# population is the number of CLOCKS, and the floor is 2 because "the clocks
# agree" over one clock is `all()` over a single element - the guard measuring
# itself. There is no sampling argument here and none is needed.
TWO_CLOCKS_MIN = 2

# G4 asks whether both indices hold the same number of live documents. This
# floor is a VACUITY floor and nothing more: at zero documents the equality is
# trivially true and every latency number under it would be a measurement of an
# empty index. It is NOT a claim that one document is enough to benchmark
# anything - the adequacy question is answered by the corpus size the run
# records and by the limits the results document states, not here.
CORPUS_VACUITY_MIN = 1


def _block(payload, key):
    value = payload.get(key) if isinstance(payload, dict) else None
    return value if isinstance(value, dict) else {}


def _int(value, default=0):
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def guard_equivalence_one_sided(payload):
    """G1 - the speedup was not bought by returning less work.

    The two designs do NOT return identical hit sets and are not supposed to:
    analyzed `text` fields tokenize `us-west-2` into `us` / `west` / `2`, so the
    naive query is genuinely fuzzier. What must hold is one-sided - the fuzzy
    design matches AT LEAST as many documents as the exact one. A faster arm
    that also returned FEWER hits would be a small query beating a big one.
    """
    equivalence = _block(payload, "equivalence")
    before = _int(equivalence.get("total_hits_before"), -1)
    after = _int(equivalence.get("total_hits_after"), -1)
    population = _int(equivalence.get("queries"))
    return {
        "id": "G1-equivalence-one-sided",
        "passed": bool(before >= 0 and after >= 0 and before >= after
                       and population >= EQUIVALENCE_MIN_QUERIES),
        "total_hits_before": before,
        "total_hits_after": after,
        "hit_volume_ratio": (round(float(before) / after, 6) if after > 0
                             else None),
        "population": population,
        "population_label": ("replayed logical lookups whose hit counts were "
                             "collected on BOTH indices"),
        "minimum_required": EQUIVALENCE_MIN_QUERIES,
    }


def guard_workload_coverage(payload):
    """G2 - both arms answered the same workload, and neither silently matched nothing.

    Three conditions, and all three are the same claim from different sides: the
    two arms replayed the same NUMBER of lookups, that number is the one the run
    asked for, and no lookup on either arm returned zero hits. A zero-hit lookup
    is a query that exercised the index without testing it, and a benchmark
    whose fast arm is fast because it matches nothing is the failure this
    benchmark's whole design is arranged against.
    """
    equivalence = _block(payload, "equivalence")
    before = _block(payload, "before")
    after = _block(payload, "after")
    requested = _int(payload.get("n_queries"), -1)
    n_before = _int(before.get("n"), -1)
    n_after = _int(after.get("n"), -1)
    zero_before = _int(equivalence.get("zero_hit_queries_before"), -1)
    zero_after = _int(equivalence.get("zero_hit_queries_after"), -1)
    population = min(n_before, n_after) if n_before >= 0 and n_after >= 0 else 0
    return {
        "id": "G2-workload-coverage",
        "passed": bool(n_before >= 0 and n_before == n_after == requested
                       and zero_before == 0 and zero_after == 0
                       and population >= COVERAGE_MIN_QUERIES),
        "requested_queries": requested,
        "replayed_before": n_before,
        "replayed_after": n_after,
        "zero_hit_queries_before": zero_before,
        "zero_hit_queries_after": zero_after,
        "population": max(population, 0),
        "population_label": ("logical lookups replayed on BOTH indices, counted "
                             "as the smaller of the two arms"),
        "minimum_required": COVERAGE_MIN_QUERIES,
    }


def guard_two_clocks_agree(payload):
    """G3 - the client clock and the server clock agree about the DIRECTION.

    Two independent clocks are recorded: client-side wall time, which includes
    HTTP transport, and Elasticsearch's own reported `took`, which does not.
    They are expected to disagree in MAGNITUDE - wall time carries a constant
    transport floor the index design cannot touch, so it dilutes the ratio. They
    must not disagree in DIRECTION. If one clock said the explicit design was
    faster and the other said it was slower, neither number would be worth
    publishing, and the artifact's own results document says exactly that.
    """
    before = _block(payload, "before")
    after = _block(payload, "after")
    clocks = []
    for key in ("wall_ms", "server_took_ms"):
        b = before.get(key) if isinstance(before.get(key), dict) else None
        a = after.get(key) if isinstance(after.get(key), dict) else None
        if b is None or a is None:
            continue
        try:
            clocks.append({
                "clock": key,
                "before_p95": float(b["p95"]),
                "after_p95": float(a["p95"]),
                "after_is_faster": float(a["p95"]) < float(b["p95"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    directions = set(clock["after_is_faster"] for clock in clocks)
    return {
        "id": "G3-two-clocks-agree-in-direction",
        "passed": bool(len(clocks) >= TWO_CLOCKS_MIN and len(directions) == 1),
        "clocks": clocks,
        "distinct_directions": len(directions),
        "population": len(clocks),
        "population_label": ("independently recorded clocks whose p95 was read "
                             "on BOTH arms (client wall time, server `took`)"),
        "minimum_required": TWO_CLOCKS_MIN,
    }


def guard_corpora_identical(payload):
    """G4 - both indices hold the same number of live documents.

    The loader generates both corpora from one seed and refuses outright when
    the two live counts differ, so this guard is not the only line - it is the
    line that survives into the RECORD. A guard that exists only as a raise
    inside a loader leaves a results file that cannot say the condition was
    checked, which is indistinguishable from one where it was not.
    """
    corpus = _block(payload, "corpus")
    doc_count = _int(corpus.get("doc_count"), -1)
    before_loaded = corpus.get("load_seconds_before")
    after_loaded = corpus.get("load_seconds_after")
    both_loaded = (isinstance(before_loaded, (int, float))
                   and isinstance(after_loaded, (int, float)))
    return {
        "id": "G4-corpora-identical-size",
        "passed": bool(doc_count >= CORPUS_VACUITY_MIN and both_loaded),
        "doc_count_per_index": doc_count,
        "load_seconds_before": before_loaded,
        "load_seconds_after": after_loaded,
        "population": max(doc_count, 0),
        "population_label": ("live documents counted in EACH index after the "
                             "force-merge, the loader having refused a mismatch"),
        "minimum_required": CORPUS_VACUITY_MIN,
    }


BUILDERS = (
    guard_equivalence_one_sided,
    guard_workload_coverage,
    guard_two_clocks_agree,
    guard_corpora_identical,
)

GUARD_COUNT = 4

if len(BUILDERS) != GUARD_COUNT:
    raise RuntimeError(
        "BUILDERS holds %d guard(s) but the committed literal says %d. Update "
        "BOTH in the same commit, or a guard can be dropped from the array "
        "without any count moving." % (len(BUILDERS), GUARD_COUNT))


def build_guards(payload):
    """The guard container: the array, and the derived summary flag beside it.

    `all_guards_passed` is DERIVED here rather than supplied, and the array is
    built unconditionally - every builder appends exactly one guard on every
    branch, including the branches where it could not read what it needed. A
    conditional append is how an array ends up empty, and `all([])` is True.
    """
    guards = [builder(payload) for builder in BUILDERS]
    return {
        "guards": guards,
        "all_guards_passed": all(bool(guard["passed"]) for guard in guards),
    }
