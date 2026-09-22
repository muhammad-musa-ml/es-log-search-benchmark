"""The equivalence claim, re-checked against this artifact's own records.

THIS IS THE ARTIFACT'S FIRST TEST, and what it exists to catch is narrow and
specific: the shipped `equivalence` block is a pair of booleans with a count
beside them, and a boolean that was written by the same function that decided it
cannot be evidence for itself. So every assertion below RECOMPUTES the property
from the record's own raw numbers and compares the answer against what the
record claims - two paths, rather than one path restated.

The guard array is checked the same way. `canonkit.validate_guards` is the
programme's own validator and knows nothing about this benchmark; running the
authored guards through it is what makes "the guards are well formed" a
measurement rather than a design intention.

RUN AGAINST THE JULY RECORD ON PURPOSE. `results/results.json` is the run this
programme presumes inaccurate until it measures for itself, and it is exactly
the right input for a shape test: if the guard array cannot be built from the
record the artifact already had, the shape is wrong, and finding that out costs
a second rather than a re-measurement.
"""
from __future__ import annotations

import json
import os

import pytest

import canonkit
from esbench import guards

ARTIFACT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ARTIFACT_ROOT, "results")
JULY_RECORD = os.path.join(RESULTS_DIR, "results.json")


def read_json(path):
    with open(path, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


@pytest.fixture(scope="module")
def july():
    """The first run's record. Read, never written."""
    assert os.path.isfile(JULY_RECORD), (
        "%s is absent. It is the BEFORE side this programme measures against "
        "and is never deleted." % JULY_RECORD)
    return read_json(JULY_RECORD)


# ---------------------------------------------------------------------------
# The equivalence claim, recomputed rather than read back
# ---------------------------------------------------------------------------


def test_the_one_sided_claim_recomputes_from_the_records_own_totals(july):
    """The record's boolean must equal the inequality recomputed from its totals."""
    block = july["equivalence"]
    recomputed = int(block["total_hits_before"]) >= int(block["total_hits_after"])
    assert block["before_is_superset_by_volume"] is recomputed
    assert block["speedup_not_bought_by_returning_less"] is recomputed
    assert recomputed is True, (
        "the fuzzy design matched FEWER documents (%s) than the exact one (%s), "
        "so the latency comparison is between a small query and a big one"
        % (block["total_hits_after"], block["total_hits_before"]))


def test_the_two_boolean_fields_are_the_same_claim_twice(july):
    """They are computed from one expression, so they can never legitimately differ.

    Recorded here because a reader meeting two differently NAMED booleans has
    every reason to think they are two independent checks. They are one.
    """
    block = july["equivalence"]
    assert (block["before_is_superset_by_volume"]
            is block["speedup_not_bought_by_returning_less"])


def test_both_arms_replayed_the_population_the_record_declares(july):
    assert july["before"]["n"] == july["after"]["n"] == july["n_queries"]
    assert july["equivalence"]["queries"] == july["n_queries"]


def test_the_recorded_speedups_recompute_from_the_recorded_percentiles(july):
    """Both published ratios are re-divided from the p95 values beside them."""
    for delta_key, clock in (("delta_wall", "wall_ms"),
                             ("delta_server", "server_took_ms")):
        before = float(july["before"][clock]["p95"])
        after = float(july["after"][clock]["p95"])
        assert after > 0
        assert round(before / after, 2) == july[delta_key]["p95_speedup_x"]
        assert round(before - after, 2) == july[delta_key]["p95_ms"]


# ---------------------------------------------------------------------------
# The authored guard array, validated by the programme's own validator
# ---------------------------------------------------------------------------


def test_the_july_record_yields_a_guard_array_with_zero_violations(july, capsys):
    built = guards.build_guards(july)
    violations = canonkit.validate_guards(built)
    with capsys.disabled():
        print("\n[guards] built=%d violations=%d all_guards_passed=%s"
              % (len(built["guards"]), len(violations),
                 built["all_guards_passed"]))
        for guard in built["guards"]:
            print("[guards]   %-34s %-4s population=%d floor=%s"
                  % (guard["id"], "pass" if guard["passed"] else "FAIL",
                     guard["population"], guard["minimum_required"]))
    assert violations == []
    assert len(built["guards"]) == guards.GUARD_COUNT


def test_every_guard_carries_the_five_keys_ruling_c1_requires(july):
    for guard in guards.build_guards(july)["guards"]:
        missing = [key for key in canonkit.GUARD_REQUIRED_KEYS
                   if key not in guard]
        assert missing == [], "%s is missing %s" % (guard.get("id"), missing)


def test_every_guard_keeps_its_domain_specific_count_beside_the_fixed_one(july):
    """C1 fixes ONE name; it does not delete the name a reader already knows."""
    domain_keys = {
        "G1-equivalence-one-sided": "total_hits_before",
        "G2-workload-coverage": "replayed_before",
        "G3-two-clocks-agree-in-direction": "clocks",
        "G4-corpora-identical-size": "doc_count_per_index",
    }
    for guard in guards.build_guards(july)["guards"]:
        assert domain_keys[guard["id"]] in guard


def test_the_july_record_passes_every_authored_guard(july):
    built = guards.build_guards(july)
    failed = [guard["id"] for guard in built["guards"] if not guard["passed"]]
    assert failed == [], "guards that did not pass over the July record: %s" % failed
    assert built["all_guards_passed"] is True


# ---------------------------------------------------------------------------
# The floors: what they are, and what they are not
# ---------------------------------------------------------------------------


def test_a_floor_is_not_the_population_the_run_happened_to_have(july):
    """The discriminating test: a floor derived from the run would MOVE with it.

    The same record is offered at three different populations. A floor computed
    from the payload changes with it; a declared floor does not. Asserting only
    that the floors are below the run's own count would pass for both.
    """
    seen = {}
    for scale in (1, 4, 40):
        payload = json.loads(json.dumps(july))
        payload["n_queries"] = july["n_queries"] * scale
        payload["before"]["n"] = payload["after"]["n"] = july["n_queries"] * scale
        payload["equivalence"]["queries"] = july["n_queries"] * scale
        payload["corpus"]["doc_count"] = july["corpus"]["doc_count"] * scale
        for guard in guards.build_guards(payload)["guards"]:
            seen.setdefault(guard["id"], set()).add(guard["minimum_required"])
    moved = sorted(gid for gid, floors in seen.items() if len(floors) > 1)
    assert moved == [], "floor(s) that moved with the population: %s" % moved


def test_a_guard_below_its_own_floor_does_not_report_passed(july):
    """Under-populated is not passed, and it is not a silent zero either."""
    payload = json.loads(json.dumps(july))
    thin = guards.EQUIVALENCE_MIN_QUERIES - 1
    payload["n_queries"] = thin
    payload["before"]["n"] = payload["after"]["n"] = thin
    payload["equivalence"]["queries"] = thin
    built = guards.build_guards(payload)
    by_id = dict((guard["id"], guard) for guard in built["guards"])
    assert by_id["G1-equivalence-one-sided"]["passed"] is False
    assert by_id["G1-equivalence-one-sided"]["population"] == thin
    assert built["all_guards_passed"] is False
    # And the validator has nothing to say, because the guard did not claim to
    # pass: the two mechanisms are independent and both have to hold.
    assert canonkit.validate_guards(built) == []


def test_the_validator_catches_a_guard_that_passes_under_its_own_floor():
    """The other half: a hand-built guard that DOES claim to pass, below its floor."""
    built = {
        "guards": [{
            "id": "G1-equivalence-one-sided",
            "passed": True,
            "population": 2,
            "population_label": "replayed logical lookups",
            "minimum_required": guards.EQUIVALENCE_MIN_QUERIES,
        }],
        "all_guards_passed": True,
    }
    violations = canonkit.validate_guards(built)
    assert len(violations) == 1
    assert "below its own declared floor" in violations[0]


def test_an_empty_guard_array_is_a_violation_and_not_a_pass():
    """`all([])` is True, which is how an unpopulated array reports everything fine."""
    violations = canonkit.validate_guards({"guards": [], "all_guards_passed": True})
    assert violations
    assert any("EMPTY" in line for line in violations)


def test_every_builder_appends_on_every_branch_even_with_nothing_to_read():
    """A conditional append is how an array ends up empty. There are none."""
    built = guards.build_guards({})
    assert len(built["guards"]) == guards.GUARD_COUNT
    assert built["all_guards_passed"] is False
    assert canonkit.validate_guards(built) == []


# ---------------------------------------------------------------------------
# The independent path: this module recomputes what derive.py authored
# ---------------------------------------------------------------------------
#
# TWO PATHS AGREEING IS A MEASUREMENT; ONE PATH IS AN ASSERTION. The code below
# shares nothing with derive.py except the records on disk: it re-reads the pair
# records, re-divides the percentiles and re-takes the minimum, so a defect in
# the derivation's selection, its arithmetic or its order statistic shows up
# here as a disagreement rather than as two copies of the same mistake.


def campaign_pairs():
    """Every pair record whose own guard array passed. Selected HERE, not read."""
    chosen = []
    for name in sorted(os.listdir(RESULTS_DIR)):
        if not name.endswith("-pair.json"):
            continue
        record = read_json(os.path.join(RESULTS_DIR, name))
        if record.get("all_guards_passed") is True:
            chosen.append((name, record))
    return chosen


def recomputed_speedups():
    """{clock: (weakest ratio, [every ratio])}, computed from the records."""
    out = {}
    for clock in ("wall_ms", "server_took_ms"):
        ratios = []
        for _name, record in campaign_pairs():
            before = float(record["before"][clock]["p95"])
            after = float(record["after"][clock]["p95"])
            ratios.append(round(before / after, 6))
        out[clock] = (min(ratios), sorted(ratios))
    return out


def test_this_module_and_derive_py_agree_on_both_speedups():
    figures_path = os.path.join(RESULTS_DIR, "figures.json")
    assert os.path.isfile(figures_path), "run `python derive.py` first"
    figures = read_json(figures_path)["figures"]
    here = recomputed_speedups()
    for key, clock in (("wall_p95_speedup_x", "wall_ms"),
                       ("server_p95_speedup_x", "server_took_ms")):
        weakest, every = here[clock]
        assert figures[key]["value"] == weakest, (
            "%s: derive.py says %s, this module recomputes %s from the same "
            "records" % (key, figures[key]["value"], weakest))
        assert sorted(run["speedup_x"] for run in figures[key]["runs"]) == every


def test_both_paths_read_the_same_replicates():
    """Agreeing on a number while reading different records would prove nothing."""
    figures = read_json(os.path.join(RESULTS_DIR, "figures.json"))["figures"]
    here = sorted(name for name, _ in campaign_pairs())
    for key in ("wall_p95_speedup_x", "server_p95_speedup_x"):
        assert sorted(figures[key]["derived_from"]) == here


def test_the_replicates_disagree_with_the_july_single_sample(july):
    """The finding this re-measurement exists to be able to produce.

    Not asserted as a target - asserted as a PROPERTY OF THE RECORDS, so that if
    a later run reproduced July's figure this test would fail and say so rather
    than letting the disagreement quietly disappear. Both clocks, both
    directions of the comparison, recomputed here from the raw percentiles.
    """
    here = recomputed_speedups()
    for delta_key, clock in (("delta_wall", "wall_ms"),
                             ("delta_server", "server_took_ms")):
        july_ratio = float(july[delta_key]["p95_speedup_x"])
        _weakest, every = here[clock]
        assert every, "no campaign replicate was found"
        assert max(every) < july_ratio, (
            "%s: every replicate (%s) should sit below July's single sample "
            "(%s); if that is no longer true the disagreement has changed and "
            "the run record must say so" % (clock, every, july_ratio))
