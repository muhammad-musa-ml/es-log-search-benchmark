"""The derivation: its three refusals, its census, and its byte stability.

WHY THESE ASSERTIONS AND NOT OTHERS
-------------------------------------
`derive.py` is the only place a number this repository publishes is authored, so
the tests that matter are the ones that catch it authoring a number it should
have refused to author, or authoring a different number over the same records.

Three refusals, each with its own test, because each fails differently:
a missing gate means nothing authorised the derivation at all; a zero population
means a figure counted nothing and every count under it would be a 0/0 pass; a
threshold claim on too few replicates means a single run landing the right side
of a line was reported as evidence the line was crossed.

Byte stability is asserted in BOTH directions. A test that only checks that two
derivations agree is satisfied by a `derive.py` that writes a constant, so the
paired case - change one recorded number, the bytes must move - is what makes
the first one mean anything.

The census is asserted as an IDENTITY rather than as a list of expected
filenames: derived-from plus excluded equals listed. A record that is neither
used nor accounted for cannot exist, and the identity says so without having to
be updated every time a replicate is added.
"""
from __future__ import annotations

import json
import os
import shutil

import pytest

import canonkit
import derive

ARTIFACT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ARTIFACT_ROOT, "results")
SPECS_PATH = os.path.join(ARTIFACT_ROOT, "figure-specs.json")
FIGURES_PATH = os.path.join(RESULTS_DIR, "figures.json")


def load_specs():
    with open(SPECS_PATH, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def read_json(path):
    with open(path, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def sandbox(tmp_path, omit=(), mutate=None):
    """A throwaway artifact root holding a COPY of every results record.

    Copied rather than pointed at, because several of these tests mutate a
    record and every one of them writes a figures.json. A test that wrote into
    the tracked tree would leave the repository dirty and would make the order
    the tests run in decide what they measure.
    """
    root = os.path.join(str(tmp_path), "artifact")
    results = os.path.join(root, "results")
    os.makedirs(results)
    for name in sorted(os.listdir(RESULTS_DIR)):
        if not name.endswith(".json") or name in omit:
            continue
        if name == "figures.json":
            continue
        payload = read_json(os.path.join(RESULTS_DIR, name))
        if mutate is not None:
            payload = mutate(name, payload)
            if payload is None:
                continue
        with open(os.path.join(results, name), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
    return root


def derive_into(root, specs=None):
    return derive.derive(root, specs if specs is not None else load_specs(),
                         slug="es-log-search-benchmark")


# ---------------------------------------------------------------------------
# The three refusals
# ---------------------------------------------------------------------------


def test_it_refuses_with_exit_2_when_the_gate_is_absent(tmp_path):
    root = sandbox(tmp_path, omit=("gate.json",))
    with pytest.raises(SystemExit) as exit_info:
        derive_into(root)
    assert exit_info.value.code == canonkit.EXIT_DID_NOT_RUN
    assert not os.path.isfile(os.path.join(root, "results", "figures.json")), (
        "the refusal wrote a figures record anyway, which would leave a file "
        "implying a derivation that did not happen")


def test_it_refuses_a_figure_whose_selector_matches_no_record(tmp_path):
    root = sandbox(tmp_path)
    spec = dict(load_specs()[0])
    spec["select"] = {"record_kind": "a-kind-no-record-carries"}
    with pytest.raises(SystemExit) as exit_info:
        derive_into(root, [spec])
    assert exit_info.value.code == canonkit.EXIT_DID_NOT_RUN


def test_it_refuses_a_threshold_claim_on_too_few_replicates(tmp_path, capsys):
    """And the refusal NAMES BOTH COUNTS: what it had, and what is required."""
    root = sandbox(tmp_path)
    spec = None
    for candidate in load_specs():
        if candidate["kind"] == "speedup_over_replicates":
            spec = dict(candidate)
            break
    assert spec is not None
    spec["threshold_claim"] = True
    spec["select"] = dict(spec.get("select") or {})
    spec["select"]["replicate_in"] = [2]
    with pytest.raises(SystemExit) as exit_info:
        derive_into(root, [spec])
    assert exit_info.value.code == canonkit.EXIT_DID_NOT_RUN
    message = capsys.readouterr().err
    assert "1 recorded run" in message
    assert str(canonkit.THRESHOLD_CLAIM_MIN_RUNS) in message


def test_a_population_of_one_is_legal_and_zero_is_not(tmp_path):
    """a design rule's distinction, asserted rather than assumed.

    A single-sample population fact is a legitimate figure that says so in its
    label; a population of zero is the 0/0 pass wearing a figure's clothes.
    """
    root = sandbox(tmp_path)
    spec = None
    for candidate in load_specs():
        if candidate["kind"] == "corpus_size":
            spec = dict(candidate)
            break
    assert spec is not None
    spec["select"] = dict(spec.get("select") or {})
    spec["select"]["replicate_in"] = [2]
    record = derive_into(root, [spec])
    figure = record["figures"][spec["key"]]
    assert figure["population"] == 1
    assert figure["population_label"].strip()


# ---------------------------------------------------------------------------
# an earlier finding: the raw replicates travel
# ---------------------------------------------------------------------------


def test_both_speedups_carry_their_raw_replicates_and_not_only_a_ratio(tmp_path):
    root = sandbox(tmp_path)
    record = derive_into(root)
    speedups = [key for key, figure in record["figures"].items()
                if figure["kind"] == "speedup_over_replicates"]
    assert len(speedups) == 2, speedups
    for key in speedups:
        runs = record["figures"][key].get("runs")
        assert isinstance(runs, list)
        assert len(runs) >= canonkit.THRESHOLD_CLAIM_MIN_RUNS, (
            "%s carries %d raw replicate(s)" % (key, len(runs or [])))
        for run in runs:
            assert run["before_p95"] > 0
            assert run["after_p95"] > 0
            assert run["speedup_x"] > 0


def test_the_published_speedup_is_the_weakest_replicate_not_an_average(tmp_path):
    """The value is an ORDER STATISTIC over the replicates, never a mean.

    Reported as the smallest ratio any replicate produced, which is a claim the
    data supports in every run rather than a central tendency no run observed.
    """
    root = sandbox(tmp_path)
    record = derive_into(root)
    for key, figure in record["figures"].items():
        if figure["kind"] != "speedup_over_replicates":
            continue
        ratios = [run["speedup_x"] for run in figure["runs"]]
        assert figure["value"] == min(ratios)
        assert figure["observed_range"] == [min(ratios), max(ratios)]


# ---------------------------------------------------------------------------
# Byte stability, both directions
# ---------------------------------------------------------------------------


def test_re_deriving_over_identical_records_is_byte_identical(tmp_path):
    root = sandbox(tmp_path)
    derive_into(root)
    first = open(os.path.join(root, "results", "figures.json"), "rb").read()
    derive_into(root)
    second = open(os.path.join(root, "results", "figures.json"), "rb").read()
    assert first == second


def test_changing_one_recorded_number_changes_the_bytes(tmp_path):
    """The paired case. Without it, a derive.py writing a constant passes above.

    THE RECORD MUTATED MUST BE ONE THE DERIVATION ACTUALLY READS, and this test
    asserts that rather than assuming it. Written the obvious way - take the
    first `*-pair.json` - it mutated the SMOKE replicate, which is correctly
    excluded for failing its own guards, so the bytes did not move and the test
    failed. That failure was the test working: a stability test pointed at a
    record outside the population proves nothing in either direction.
    """
    root = sandbox(tmp_path)
    record = derive_into(root)
    baseline = open(os.path.join(root, "results", "figures.json"), "rb").read()

    derived = set(record["population"]["derived_from_records"])
    target_name = None
    for name in sorted(derived):
        if name.endswith("-pair.json"):
            target_name = name
            break
    assert target_name is not None, (
        "no pair record is in the derived population of %d" % len(derived))
    for figure in record["figures"].values():
        if figure["kind"] == "speedup_over_replicates":
            assert target_name in figure["derived_from"]
    target = os.path.join(root, "results", target_name)
    payload = read_json(target)
    payload["after"]["server_took_ms"]["p95"] = (
        float(payload["after"]["server_took_ms"]["p95"]) + 1.0)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)

    derive_into(root)
    changed = open(os.path.join(root, "results", "figures.json"), "rb").read()
    assert changed != baseline


def test_the_derivation_does_not_stamp_a_wall_clock(tmp_path):
    """`dated_at` is the last measurement's own finish, never `now`.

    A wall clock here would move the bytes on every re-derivation for a reason
    that has nothing to do with any measurement, which is what makes the record
    un-pinnable.
    """
    root = sandbox(tmp_path)
    record = derive_into(root)
    finishes = set()
    for name in sorted(os.listdir(os.path.join(root, "results"))):
        if not name.endswith("-pair.json"):
            continue
        finishes.add(read_json(os.path.join(root, "results", name))
                     .get("finished_at"))
    assert record["dated_at"] in finishes


# ---------------------------------------------------------------------------
# The census: counted exclusions, and an identity that closes
# ---------------------------------------------------------------------------


def test_the_july_record_is_excluded_as_superseded_and_still_on_disk(tmp_path):
    root = sandbox(tmp_path)
    record = derive_into(root)
    by_reason = dict((entry["reason"], entry)
                     for entry in record["population"]["excluded_by_reason"])
    assert "results.json" in by_reason[derive.SUPERSEDED]["names"]
    assert by_reason[derive.SUPERSEDED]["records"] == 1
    assert os.path.isfile(os.path.join(RESULTS_DIR, "results.json")), (
        "the July record is the BEFORE side this programme compares against "
        "and is never deleted")


def test_a_replicate_whose_own_guards_failed_never_feeds_a_figure(tmp_path):
    root = sandbox(tmp_path)
    record = derive_into(root)
    by_reason = dict((entry["reason"], entry)
                     for entry in record["population"]["excluded_by_reason"])
    failed = by_reason[derive.GUARD_FAILED]["names"]
    assert failed, ("no record was excluded for failing its own guards; the "
                    "smoke run at 20,000 documents failed G2 and its three "
                    "records must not back a published figure")
    for figure in record["figures"].values():
        overlap = sorted(set(figure["derived_from"]) & set(failed))
        assert overlap == [], "%s rests on %s" % (figure, overlap)


def test_the_census_identity_closes(tmp_path):
    root = sandbox(tmp_path)
    record = derive_into(root)
    population = record["population"]
    assert population["derived_from"] + population["excluded"] == population["listed"]


def test_every_excluded_record_carries_a_reason_and_a_count(tmp_path):
    root = sandbox(tmp_path)
    record = derive_into(root)
    entries = record["population"]["excluded_by_reason"]
    assert entries
    for entry in entries:
        assert entry["reason"].strip()
        assert entry["records"] == len(entry["names"])


def test_only_records_carrying_this_runs_gate_token_are_derived_from(tmp_path):
    root = sandbox(tmp_path)
    record = derive_into(root)
    gate = read_json(os.path.join(root, "results", "gate.json"))
    for name in record["population"]["derived_from_records"]:
        payload = read_json(os.path.join(root, "results", name))
        assert derive.record_gate_token(payload) == gate["run_token"]


# ---------------------------------------------------------------------------
# The committed record
# ---------------------------------------------------------------------------


def test_the_committed_figures_record_validates(tmp_path):
    assert os.path.isfile(FIGURES_PATH), (
        "results/figures.json is absent; run `python derive.py`")
    record = read_json(FIGURES_PATH)
    assert canonkit.validate_figures(record) == []


def test_every_committed_figure_carries_a_labelled_non_zero_population():
    record = read_json(FIGURES_PATH)
    for key, figure in record["figures"].items():
        assert figure["population"] >= 1, key
        assert figure["population_label"].strip(), key


def test_every_committed_figure_names_its_unbacked_canon_sentinel():
    """This artifact backs no canon bullet, and the field says so IN the record.

    The schema requires a compound-keyed `canon_bullet` on every figure and
    rejects both `None` and an absent key - measured, not assumed. So the
    absence is recorded as a sentinel a reader can resolve rather than as a
    hole they have to interpret.
    """
    record = read_json(FIGURES_PATH)
    for key, figure in record["figures"].items():
        assert figure["canon_bullet"] == derive.UNBACKED_SENTINEL, key
