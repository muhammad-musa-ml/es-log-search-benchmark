"""THE ONLY PLACE A NUMBER THIS BENCHMARK PUBLISHES IS AUTHORED.

Every figure the repository ships is computed here, from the per-replicate JSON
records the measuring script wrote, and written to results/figures.json. Nothing
else may author a number: each figure carries its own population, its population
label and the list of records it came from, so a reader can walk back to the
machine.

    per-replicate records -> classify -> select -> compute -> figure

WHY THIS FILE HAS ITS OWN READER
----------------------------------
The shared contract reads one record per replayed item. This benchmark writes
three records per REPLICATE - one per arm, plus a pair record holding what only
the comparison can say - flat under `results/`. So the three REFUSALS and the
figure record are copied from that contract exactly; the reader is written for
this shape.

THE POPULATION IS THE HARD PART, NOT THE ARITHMETIC
-----------------------------------------------------
`results/` holds four kinds of file and only one of them may feed a figure:

  * `results.json` - the JULY run. It carries no gate token, because it predates
    the gate. EXCLUDED as superseded, COUNTED, and never deleted: it is the
    BEFORE side a measurement-wins programme compares against, and a superseded
    record that has been overwritten can only be described rather than compared.
  * `gate.json` - a gate decides; it does not measure. EXCLUDED as not a run.
  * the SMOKE replicate, run at 20,000 documents from the README's own
    documented command. It carries this run's token and is measurement-shaped,
    so nothing structural separates it - what separates it is that IT FAILED ITS
    OWN GUARDS. At that corpus size 5 of 50 lookups on one arm and 6 of 50 on
    the other matched nothing, which is exactly the condition G2 exists to
    catch. EXCLUDED as guard-failed, COUNTED, and not deleted, because a guard
    that fired is evidence rather than noise.
  * the campaign replicates, which carry the token and passed every guard.

A RECORD IS EXCLUDED BY A PROPERTY IT CARRIES, never by its filename. Excluding
the smoke run by name, or by "the one with the small corpus", would be a
judgement dressed as a rule and would go quietly wrong the first time a
different replicate failed. `all_guards_passed` is written by the run itself.

An arm record does not carry the guard verdict - only the pair record for its
replicate does - so the verdict is looked up BY REPLICATE. That lookup is a
named function with a test pointed at it, because a classifier that silently
found no verdict would let a failed replicate's arms through while its pair was
correctly excluded, and the census identity would still close.

EVERY EXCLUSION IS COUNTED AND GIVEN ITS REASON, printed beside the derivation.
The counts close as an identity - excluded plus derived-from equals listed -
enforced by the shared reporter rather than asserted in prose, so a record that
is neither used nor accounted for cannot exist.

NO STATISTIC IS COMPUTED ACROSS REPLICATES, AND THAT IS THE POINT OF THE RUN
------------------------------------------------------------------------------
A speedup figure's VALUE is the smallest ratio any replicate produced - an order
statistic, and a claim every run supports - not a mean, which is a claim no run
observed. The raw replicates travel in the figure record beside it, and the
observed range is reported as its two actual endpoints rather than as a spread.
A ratio with no replicates behind it is the single-sample shape this whole
re-measurement exists to replace.

BYTE STABILITY. This file stamps no wall clock. `dated_at` is the moment the
last measurement it rests on FINISHED, read from that run's own record, so
re-deriving over unchanged records produces byte-identical output and
results/figures.json can be hash-pinned. Changing one recorded number still
changes the bytes; both directions are asserted in tests/test_derive.py.

THE CANON SENTINEL. The figures schema requires a compound-keyed `canon_bullet`
on every figure and rejects both `None` and an absent key - probed directly
against the validator rather than assumed. This artifact backs no canon bullet,
so every figure carries a sentinel that says exactly that. A recorded "this
backs nothing" and a missing field are different claims, and only the first can
be read back.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import canonkit

SCHEMA = "canonkit/figures/1"

# What this file writes, and therefore the one name in results/ that is never
# part of its own input population. Leaving it in is not a harmless over-count:
# the file does not exist on the first run and does on every later one, so the
# listed population would step from N to N+1 the moment it was first written and
# the record's bytes would move for a reason that has nothing to do with any
# measurement.
OUTPUT_NAME = "figures.json"

# This artifact is cited by no bullet in either canon - its own expected-set row
# records that, with the bullet-scoped probe behind it. The field is PRESENT and
# says so.
UNBACKED_SENTINEL = "unbacked:no-canon-bullet"

# The exclusion reasons, in the order they print. Each is a MECHANICAL property
# of the record, not a judgement about it, and each is exactly true of every
# file it holds.
GUARD_FAILED = "the replicate's own guard array did not pass"
SUPERSEDED = "superseded by the re-run"
NOT_A_RUN = "not a per-run measurement record"
EXCLUSION_ORDER = (GUARD_FAILED, SUPERSEDED, NOT_A_RUN)

# Where a clock's percentiles live inside an arm summary.
CLOCKS = ("wall_ms", "server_took_ms")


# ---------------------------------------------------------------------------
# reading a record
# ---------------------------------------------------------------------------


def record_gate_token(record):
    """THIS record's gate token, read from where the run recorder writes it.

    `run.gate_token` first, because that is the per-run shape. The flat
    `gate_token` fallback is what the measurement files carry at top level, so
    the same function answers for both without a second spelling.
    """
    if not isinstance(record, dict):
        return None
    run = record.get("run")
    if isinstance(run, dict):
        token = run.get("gate_token")
        if isinstance(token, str) and token:
            return token
    token = record.get("gate_token")
    return token if isinstance(token, str) and token else None


def run_block(record):
    run = record.get("run") if isinstance(record, dict) else None
    return run if isinstance(run, dict) else {}


def is_gate(record):
    """The gate's own record. Identified by what it IS, not by its filename."""
    return (isinstance(record, dict)
            and "run_token" in record and "assertions" in record)


def is_measurement(record):
    """A record carrying measured numbers a reader would take as results.

    Two shapes are accepted, and the second is why this is not a one-liner. The
    current shape declares `record_kind`. The JULY shape predates that field
    entirely and would be classified "not a run" by a `record_kind` test alone -
    which would exclude it for the WRONG REASON, saying it is not a measurement
    when in fact it is a measurement this run supersedes.
    """
    if not isinstance(record, dict):
        return False
    if record.get("record_kind") in ("arm", "pair"):
        return True
    return all(isinstance(record.get(key), dict)
               for key in ("before", "after", "equivalence"))


def load_flat_records(results_dir):
    """Every JSON file DIRECTLY under results/, as (name, payload) pairs.

    NOT recursive, and that is a decision rather than an oversight.
    `results/raw/` holds one RUN record per measurement - the provenance index,
    carrying timestamps, the cost triple and the contention censuses. Its
    records restate the same replicate identity the flat records carry, so
    walking it too would count every replicate twice.
    """
    pairs = []
    for path in sorted(glob.glob(os.path.join(str(results_dir), "*.json"))):
        name = os.path.basename(path)
        if name == OUTPUT_NAME:
            continue
        with open(path, "rb") as handle:
            pairs.append((name, json.loads(handle.read().decode("utf-8"))))
    return pairs


def guard_verdicts_by_replicate(pairs, token):
    """{replicate index: all_guards_passed}, read from the PAIR records.

    An arm record does not carry the guard verdict; only its replicate's pair
    record does. Without this lookup a failed replicate's two arm records would
    be derived from while its pair was correctly excluded - and the census
    identity would still close, so nothing would say so.

    Only token-carrying records contribute, because a July record's absence of a
    verdict must not be read as a verdict.
    """
    verdicts = {}
    for _name, record in pairs:
        if not isinstance(record, dict):
            continue
        if record.get("record_kind") != "pair":
            continue
        if record_gate_token(record) != token:
            continue
        replicate = record.get("replicate")
        passed = record.get("all_guards_passed")
        if isinstance(replicate, int) and isinstance(passed, bool):
            verdicts[replicate] = passed
    return verdicts


# ---------------------------------------------------------------------------
# the census
# ---------------------------------------------------------------------------


class Census(object):
    """What was derived from, what was not, and why - with the counts.

    `excluded` is a list of (reason, names) in EXCLUSION_ORDER rather than a
    dict, so the printed line cannot re-order between runs.
    """

    def __init__(self, total, listed, derived, buckets, records):
        self.total = total
        self.listed = listed
        self.derived = derived
        self.records = records
        self.excluded = [(reason, sorted(buckets.get(reason, [])))
                         for reason in EXCLUSION_ORDER]

    @property
    def excluded_count(self):
        return sum(len(names) for _reason, names in self.excluded)

    def exclusion_line(self):
        parts = ["%s, %d records" % (reason, len(names))
                 for reason, names in self.excluded]
        return ("[derive] excluded %d of %d record(s): %s"
                % (self.excluded_count, self.total, "; ".join(parts)))


def classify(results_dir, token):
    """Sort every flat results record into exactly one class.

    Order matters and is argued. The two STRUCTURAL classes come first, because
    they say what a file IS. The TOKEN comes next, because it is the only thing
    separating two campaigns of the same shape. The GUARD VERDICT comes last,
    because it is a property of a record that has already been established to be
    a measurement taken under this gate - asking it of a July record would be
    asking a question that record cannot answer.
    """
    pairs = load_flat_records(results_dir)
    verdicts = guard_verdicts_by_replicate(pairs, token)

    buckets = {}
    derived = []
    listed = []
    records = {}
    for name, record in pairs:
        listed.append(name)
        records[name] = record
        if is_gate(record) or not is_measurement(record):
            buckets.setdefault(NOT_A_RUN, []).append(name)
        elif record_gate_token(record) != token:
            buckets.setdefault(SUPERSEDED, []).append(name)
        elif verdicts.get(record.get("replicate")) is False:
            buckets.setdefault(GUARD_FAILED, []).append(name)
        else:
            derived.append(name)
    return Census(len(listed), sorted(listed), sorted(derived), buckets, records)


# ---------------------------------------------------------------------------
# selecting the records one declared figure rests on
# ---------------------------------------------------------------------------


def select_records(spec, census):
    """The derived records this spec names, as (name, payload), name-sorted."""
    selector = spec.get("select") or {}
    chosen = []
    for name in census.derived:
        record = census.records[name]
        if ("record_kind" in selector
                and record.get("record_kind") != selector["record_kind"]):
            continue
        if "arm" in selector and record.get("arm") != selector["arm"]:
            continue
        if ("replicate_in" in selector
                and record.get("replicate") not in selector["replicate_in"]):
            continue
        chosen.append((name, record))
    return chosen


def _dig(record, path):
    """Follow a declared key path, returning None rather than raising."""
    current = record
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _replicate(record):
    value = record.get("replicate")
    return value if isinstance(value, int) else -1


def refuse_disagreement(spec, label, values, names):
    canonkit.die(
        canonkit.EXIT_DID_NOT_RUN,
        "%s figure %r reads %s, which the seed makes deterministic, and the %d "
        "selected record(s) do NOT agree: %s (records: %s). Replicates that "
        "disagree on a deterministic quantity are not replicates of one thing, "
        "and averaging them would hide exactly that.\n"
        "  REPAIR: this is a finding about the measurement, not about the "
        "spec. Read the disagreeing records before deriving anything from them."
        % (canonkit.REFUSAL_PREFIX, spec["key"], label, len(names),
           sorted(values), sorted(names)))


# ---------------------------------------------------------------------------
# the declared figure kinds
# ---------------------------------------------------------------------------


def compute_speedup_over_replicates(spec, selected, context):
    """an earlier finding: the RAW replicates travel, and the VALUE is an order statistic.

    The published value is the SMALLEST ratio any replicate produced. That is a
    claim every run in the population supports; a mean is a claim no run
    observed, and it would delete the disagreement the replication was taken to
    find.
    """
    clock = spec.get("clock")
    if clock not in CLOCKS:
        canonkit.die(
            canonkit.EXIT_DID_NOT_RUN,
            "%s figure %r declares clock %r; this benchmark records %s.\n"
            "  REPAIR: correct `clock` in figure-specs.json."
            % (canonkit.REFUSAL_PREFIX, spec["key"], clock, list(CLOCKS)))

    runs = []
    for name, record in selected:
        before = _dig(record, ("before", clock, "p95"))
        after = _dig(record, ("after", clock, "p95"))
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            canonkit.die(
                canonkit.EXIT_DID_NOT_RUN,
                "%s figure %r found no %s p95 on both arms of %s.\n"
                "  REPAIR: re-run that replicate."
                % (canonkit.REFUSAL_PREFIX, spec["key"], clock, name))
        if float(after) <= 0:
            canonkit.die(
                canonkit.EXIT_DID_NOT_RUN,
                "%s figure %r would divide by a %s p95 of %r in %s. A ratio "
                "against zero is not a speedup.\n"
                "  REPAIR: re-run that replicate."
                % (canonkit.REFUSAL_PREFIX, spec["key"], clock, after, name))
        runs.append({
            "replicate": _replicate(record),
            "record": name,
            "clock": clock,
            "before_p95": round(float(before), 6),
            "after_p95": round(float(after), 6),
            "delta_p95_ms": round(float(before) - float(after), 6),
            "speedup_x": round(float(before) / float(after), 6),
        })
    runs.sort(key=lambda entry: (entry["replicate"], entry["record"]))
    ratios = [entry["speedup_x"] for entry in runs]
    faster = sum(1 for entry in runs if entry["after_p95"] < entry["before_p95"])
    return {
        "value": min(ratios),
        "numerator": faster,
        "denominator": len(runs),
        "population": len(runs),
        "runs": runs,
        "extra": {
            "clock": clock,
            # The two ENDPOINTS, both of them actual observations. Not a spread:
            # a spread is a derived width, and these are two measured runs.
            "observed_range": [min(ratios), max(ratios)],
            "value_rule": ("the smallest ratio any replicate produced; every "
                           "replicate in the population met or beat it"),
        },
    }


def compute_corpus_size(spec, selected, context):
    """Documents live in EACH index, which the seed makes deterministic."""
    values = set()
    runs = []
    for name, record in selected:
        count = _dig(record, ("corpus", "doc_count"))
        values.add(int(count) if isinstance(count, (int, float)) else None)
        runs.append({"replicate": _replicate(record), "record": name,
                     "doc_count": count})
    if len(values) != 1 or None in values:
        refuse_disagreement(spec, "the loaded document count", values,
                            [name for name, _ in selected])
    runs.sort(key=lambda entry: (entry["replicate"], entry["record"]))
    return {
        "value": sorted(values)[0],
        "numerator": len(selected),
        "denominator": len(selected),
        "population": len(selected),
        "runs": runs,
        "extra": {"agreed_across_records": len(selected)},
    }


def compute_replayed_population(spec, selected, context):
    """Logical lookups replayed against ONE index, per arm record."""
    values = set()
    runs = []
    for name, record in selected:
        count = record.get("n")
        values.add(int(count) if isinstance(count, (int, float)) else None)
        runs.append({"replicate": _replicate(record), "record": name,
                     "arm": record.get("arm"), "n": count})
    if len(values) != 1 or None in values:
        refuse_disagreement(spec, "the replayed lookup count", values,
                            [name for name, _ in selected])
    runs.sort(key=lambda entry: (entry["replicate"], str(entry["arm"])))
    return {
        "value": sorted(values)[0],
        "numerator": len(selected),
        "denominator": len(selected),
        "population": len(selected),
        "runs": runs,
        "extra": {"arm_records_agreeing": len(selected)},
    }


def compute_agreed_count(spec, selected, context):
    """A count the records must agree on, read from a declared key path."""
    path = tuple(spec.get("path") or ())
    if not path:
        canonkit.die(
            canonkit.EXIT_DID_NOT_RUN,
            "%s figure %r declares kind `agreed_count` with no `path`.\n"
            "  REPAIR: name the key path in figure-specs.json."
            % (canonkit.REFUSAL_PREFIX, spec["key"]))
    values = set()
    runs = []
    for name, record in selected:
        value = _dig(record, path)
        values.add(int(value) if isinstance(value, (int, float)) else None)
        runs.append({"replicate": _replicate(record), "record": name,
                     "value": value})
    if len(values) != 1 or None in values:
        refuse_disagreement(spec, ".".join(path), values,
                            [name for name, _ in selected])
    runs.sort(key=lambda entry: (entry["replicate"], entry["record"]))
    return {
        "value": sorted(values)[0],
        "numerator": len(selected),
        "denominator": len(selected),
        "population": len(selected),
        "runs": runs,
        "extra": {"read_from": ".".join(path)},
    }


def compute_zero_hit_total(spec, selected, context):
    """Lookups that matched NOTHING, summed over every arm of every replicate.

    A sum, never a mean: this counts occurrences of a condition over a stated
    population, and the population is printed beside it. The expected value is
    zero, and a zero here is a measured zero rather than an absent count -
    the denominator says how many lookups were examined to find it.
    """
    total = 0
    population = 0
    runs = []
    for name, record in selected:
        before = _dig(record, ("equivalence", "zero_hit_queries_before"))
        after = _dig(record, ("equivalence", "zero_hit_queries_after"))
        queries = _dig(record, ("equivalence", "queries"))
        if not all(isinstance(v, int) for v in (before, after, queries)):
            canonkit.die(
                canonkit.EXIT_DID_NOT_RUN,
                "%s figure %r found no zero-hit counts in %s.\n"
                "  REPAIR: re-run that replicate."
                % (canonkit.REFUSAL_PREFIX, spec["key"], name))
        total += before + after
        population += queries * 2
        runs.append({"replicate": _replicate(record), "record": name,
                     "zero_hit_before": before, "zero_hit_after": after,
                     "lookups_examined": queries * 2})
    runs.sort(key=lambda entry: (entry["replicate"], entry["record"]))
    return {
        "value": total,
        "numerator": total,
        "denominator": population,
        "population": population,
        "runs": runs,
        "extra": {"arm_replays_examined": len(selected) * 2},
    }


KINDS = {
    "speedup_over_replicates": compute_speedup_over_replicates,
    "corpus_size": compute_corpus_size,
    "replayed_population": compute_replayed_population,
    "agreed_count": compute_agreed_count,
    "zero_hit_total": compute_zero_hit_total,
}


# ---------------------------------------------------------------------------
# the three refusals, copied from the shared contract
# ---------------------------------------------------------------------------


def refuse_zero_population(key, population, because):
    """COPIED VERBATIM in its diagnosis; only the REPAIR names this artifact."""
    canonkit.die(
        canonkit.EXIT_DID_NOT_RUN,
        "%s figure %r has a population of %d (%s). A figure over zero inputs "
        "did not measure anything, and every count derived from it would be a "
        "0/0 pass. Population 1 is legal; 0 is not.\n"
        "  REPAIR: run `python gate.py` then `python run_benchmark.py` so "
        "results/ holds per-replicate records this spec can select, then "
        "re-run derive.py."
        % (canonkit.REFUSAL_PREFIX, key, population, because))


def refuse_threshold_claim(key, count):
    canonkit.die(
        canonkit.EXIT_DID_NOT_RUN,
        "%s figure %r carries threshold_claim: true with %d recorded run(s); "
        "at least %d are required. A single run landing the right side of a "
        "line does not establish that the line was crossed.\n"
        "  REPAIR: record %d more run(s), or drop threshold_claim and report "
        "the figure without the crossing claim."
        % (canonkit.REFUSAL_PREFIX, key, count,
           canonkit.THRESHOLD_CLAIM_MIN_RUNS,
           canonkit.THRESHOLD_CLAIM_MIN_RUNS - count))


# ---------------------------------------------------------------------------
# the derivation
# ---------------------------------------------------------------------------


def latest_run(census):
    """The last-STARTED run among the records actually derived from.

    Selected by the recorded started_at INSIDE the record, never by file mtime,
    and drawn from the used population rather than from every record on disk:
    the figures record is dated by the last measurement it rests on.
    """
    runs = [run_block(census.records[name]) for name in census.derived]
    runs = [run for run in runs if run.get("started_at")]
    if not runs:
        return {}
    return sorted(runs, key=lambda run: str(run["started_at"]))[-1]


def build_context(census):
    """The quantities a spec may refer to but must never type."""
    replicates = sorted(set(
        census.records[name].get("replicate") for name in census.derived
        if isinstance(census.records[name].get("replicate"), int)))
    return {"replicates": replicates}


def derive(root, specs, slug=None, stream=None):
    """Author every declared figure and write results/figures.json."""
    stream = stream if stream is not None else sys.stdout
    results_dir = os.path.join(str(root), "results")
    slug = slug or os.path.basename(os.path.abspath(str(root)))

    # Refuses with exit 2 when the gate is absent or failed, BEFORE any record
    # is read. A number authored past a failed gate has nothing behind it.
    token = canonkit.require_gate(results_dir)

    census = classify(results_dir, token)
    context = build_context(census)
    run = latest_run(census)

    figures = {}
    for spec in specs:
        key = spec["key"]
        kind = spec.get("kind")
        if kind not in KINDS:
            canonkit.die(
                canonkit.EXIT_DID_NOT_RUN,
                "%s figure %r declares kind %r, which this artifact cannot "
                "author. Known kinds: %s.\n"
                "  REPAIR: correct the kind in figure-specs.json."
                % (canonkit.REFUSAL_PREFIX, key, kind, sorted(KINDS)))

        selected = select_records(spec, census)
        if not selected:
            refuse_zero_population(
                key, 0,
                "no record in the derived population of %d matches its "
                "selector %r" % (len(census.derived), spec.get("select")))

        computed = KINDS[kind](spec, selected, context)
        population = int(computed["population"])
        if population < 1:
            refuse_zero_population(
                key, population,
                "its %d selected record(s) counted nothing" % len(selected))

        runs = list(computed.get("runs") or [])
        if spec.get("threshold_claim"):
            if len(runs) < canonkit.THRESHOLD_CLAIM_MIN_RUNS:
                refuse_threshold_claim(key, len(runs))

        figure = {
            "value": computed["value"],
            "unit": spec["unit"],
            "population": population,
            "population_label": spec["population_label"],
            "derived_from": sorted(name for name, _ in selected),
            # This artifact backs no canon bullet and the field SAYS SO. A
            # recorded "this backs nothing" and a missing field are different
            # claims; the schema rejects the second, and only the first can be
            # read back.
            "canon_bullet": UNBACKED_SENTINEL,
            "canon_value": spec.get("canon_value"),
            "similar": spec.get("similar"),
            "similar_reason_ref": spec.get("similar_reason_ref"),
            "tier_achieved": spec.get("tier_achieved"),
            "reproduce_criterion": spec.get("reproduce_criterion"),
            "threshold_claim": bool(spec.get("threshold_claim")),
            "not_shown": spec.get("not_shown"),
            # The chain, recorded so it can be re-walked rather than trusted.
            "kind": kind,
            "predicate": spec.get("select"),
            "numerator": computed["numerator"],
            "denominator": computed["denominator"],
        }
        figure.update(computed.get("extra") or {})
        # an earlier finding: the RAW replicates, never only a summary statistic over them.
        if runs:
            figure["runs"] = runs
        figures[key] = figure

    record = {
        "schema": SCHEMA,
        "schema_version": canonkit.SCHEMA_VERSION,
        "artifact": slug,
        "gate_token": token,
        # NOT a wall clock. The instant the last measurement these figures rest
        # on finished, read from that run's own record - so re-deriving over
        # unchanged records is byte-identical and this file can be hash-pinned,
        # while the provenance it carries is still machine-written.
        "dated_at": run.get("finished_at") or run.get("started_at"),
        "started_at": run.get("started_at"),
        "started_at_utc": run.get("started_at_utc"),
        # `source_run_id`, NOT `run_id`. A top-level `run_id` is how the
        # conformance runner recognises a file as being ITSELF a run record, and
        # it then requires the full seven-field run block. A figures record is
        # not a run and would be reported as a PARTIAL one.
        "source_run_id": run.get("run_id"),
        "replicates_derived_from": context["replicates"],
        "population": {
            "listed": census.total,
            "derived_from": len(census.derived),
            "excluded": census.excluded_count,
            "derived_from_records": census.derived,
            "excluded_by_reason": [
                {"reason": reason, "records": len(names), "names": names}
                for reason, names in census.excluded],
        },
        "figures": figures,
    }

    violations = canonkit.validate_figures(record)
    if violations:
        canonkit.die(
            canonkit.EXIT_DID_NOT_RUN,
            "%s derive.py assembled a figures record its own validator rejects "
            "(%d violation(s)):\n%s\n"
            "  REPAIR: this is a defect in the figure SPECS or in derive.py, "
            "not in the measurement."
            % (canonkit.REFUSAL_PREFIX, len(violations), "\n".join(violations)))

    canonkit.atomic_write_json(os.path.join(results_dir, OUTPUT_NAME), record)

    # The population line. `listed` is every JSON file directly under results/,
    # `checked` is what the figures rest on, and the reporter RAISES if the two
    # do not close against the exclusions - so the identity is enforced rather
    # than claimed.
    canonkit.report("DERIVE", True, 0, len(census.derived), 1,
                    not_examined=census.excluded_count, listed=census.total,
                    note="authored %d figure(s) over %d per-replicate record(s) "
                         "from replicate(s) %s"
                         % (len(figures), len(census.derived),
                            context["replicates"]))
    stream.write(census.exclusion_line() + "\n")
    for reason, names in census.excluded:
        if names:
            stream.write("[derive]   %s, %d records: %s\n"
                         % (reason, len(names), ", ".join(names)))
    stream.write("[derive] census identity: derived-from %d + excluded %d == "
                 "%d listed\n"
                 % (len(census.derived), census.excluded_count, census.total))
    for key in sorted(figures):
        figure = figures[key]
        stream.write("[derive] %s = %s %s  (%d of %d %s)\n"
                     % (key, figure["value"], figure["unit"],
                        figure["numerator"], figure["denominator"],
                        figure["population_label"]))
    return record


def main(argv=None, stream=None):
    parser = argparse.ArgumentParser(
        description="Author this benchmark's figures from its own records.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--specs", default="figure-specs.json",
                        help="path to the JSON file holding the declared specs")
    args = parser.parse_args(argv)
    with open(args.specs, "rb") as handle:
        specs = json.loads(handle.read().decode("utf-8"))
    derive(args.root, specs, stream=stream)
    return canonkit.EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
