"""CHECK-04 -- the gate was RECORDED, ordered FIRST, and its token stamped.

    python check_04.py <artifact> [--report FILE] [--min-population N]

the project requirements document states the check verbatim: "Fails when `results/gate.json` is
absent, when its `dated_at` is not earlier than every measurement's
`started_at`, or when a measurement lacks the gate token. A correctly recorded
FAILED gate is a PASS for this check."

THE BRANCH THAT MUST NOT FIRE, AND WHY IT IS STATED FIRST
-----------------------------------------------------------
A correctly recorded FAILED gate is a PASS. This check asks whether the gate was
RECORDED and ORDERED, not whether it succeeded.

That is not leniency, it is a design rule working. A failed gate writes a full record,
mints its token and exits 3, precisely so that a measurement which ran anyway
carries a key rather than no key at all. Refusing every artifact whose gate
failed would collapse two different facts -- "this path did not measure, and
said so" and "this path measured without authorisation" -- into one verdict, and
the first of those is a correctly closed path, not a defect.

ORDERING IS READ FROM INSIDE THE JSON. NEVER FROM THE FILESYSTEM.
------------------------------------------------------------------
The filesystem's own record of when a file was last written is not evidence
here. The reasons are set out in the comment block above `comparable()`, where
someone reaching for the convenient answer would actually be standing, and a
test asserts the property mechanically rather than by eye.

FOUR BRANCHES. THE REQUIREMENT NAMES THREE; THE FOURTH IS WHERE THE THIRD'S
TWO SHAPES AND AN UNORDERABLE STAMP GO.

    gate-absent          results/gate.json is not there. Nothing authorised
                         anything, and no ordering question can even be asked.
    after-measurement    the gate's dated_at is NOT strictly earlier than some
                         measurement's started_at, naming that measurement. A
                         gate decided at the same instant a run began did not
                         precede it.
    token-absent         a measurement carries no gate_token at all.
    token-mismatch       a measurement carries a token that is not the gate's
                         run_token.
    unorderable          a measurement whose started_at cannot be compared with
                         the gate's dated_at -- unparseable, or one of the two
                         naive while the other is aware. This is a finding and
                         not a refusal: a timestamp that cannot be ordered is a
                         defect in the record, and reporting it as "could not
                         look" would hide it behind a verdict about population.

token-absent and token-mismatch are the requirement's single "lacks the gate
token" branch, split because their repairs differ: one run never stamped what it
was given, the other stamped something else. Both name the file.

WHAT THIS CHECK DELIBERATELY DOES NOT DO, AND WHERE IT IS DONE INSTEAD
-----------------------------------------------------------------------
It does not ask whether a figure is re-derivable from its per-item records --
that is `templates/verify.py`, which walks the whole chain and compares the
CURRENT gate's token against the one the figures record claims. The two
mechanisms answer different questions and `tools/tests/test_check_04.py`
demonstrates the difference rather than asserting it: CHECK-04 passes a
correctly recorded failed gate, and verify.py is what speaks up once that gate
is fixed and re-run, because a content token moves when the content moves.

It also does not examine a results file that records no start. A file carrying a
token but no started_at is outside this check's population and is counted as
not-examined with that reason printed. CHECK-06 is what requires every results
file carrying numbers to have a run record behind it, so the gap is closed by a
different check rather than left open -- and the population line says so.

WHAT IS IN THE POPULATION
---------------------------
Every `*.json` under `results/`, recursively, that carries a `started_at`,
EXCEPT `results/gate.json` (the gate is the thing being ordered AGAINST, not a
measurement) and everything under `results/raw/items/` (per-item records, which
runmeta.py keeps in their own directory so a glob over runs does not count
them). Both exclusions are counted and given a reason.

EXIT CODES (canonkit's contract, a design rule)
    0  a recorded gate, earlier than every measurement, its token on each one
    1  at least one of the four branches
    2  it could not look: no measurement under this artifact records a start, so
       there is nothing to order a gate against; or the population is below the
       effective floor

VENDORING. Enumerated into the vendored set by tools/vendor.py's check-module
glob and copied to <artifact>/checks/check_04.py, beside <artifact>/canonkit.py.
Run BY PATH under a bare module name, never as a dotted package module. Stdlib
only, ASCII only.
"""

import argparse
import datetime
import importlib.util
import json
import os
import sys

CHECK_ID = "CHECK-04"

# a design rule: the POPULATION floor, declared per-check IN CODE, overridable on the
# command line, and the EFFECTIVE value is what prints as `floor=`. One
# measurement is the smallest population over which an ordering claim means
# anything; zero is DID-NOT-RUN.
DEFAULT_FLOOR = 1

SCHEMA = "canonkit/check-04/1"

HERE = os.path.dirname(os.path.abspath(__file__))
CORE_ROOT = os.path.dirname(HERE)

RESULTS_DIRNAME = "results"
GATE_FILENAME = "gate.json"
ITEMS_DIRNAME = "items"

STARTED_AT = "started_at"
DATED_AT = "dated_at"
RUN_TOKEN = "run_token"
GATE_TOKEN = "gate_token"

FINDING_GATE_ABSENT = "gate-absent"
FINDING_AFTER_MEASUREMENT = "after-measurement"
FINDING_TOKEN_ABSENT = "token-absent"
FINDING_TOKEN_MISMATCH = "token-mismatch"
FINDING_UNORDERABLE = "unorderable"

MAX_LISTED_FINDINGS = 20

# How much of a token is printed. A full 64-character hex string twice on one
# line makes the line unreadable and the difference harder to see, not easier.
TOKEN_PREFIX = 12


class CheckRefusal(Exception):
    """The check could not look. Carries the note printed beside code 2."""


def load_core():
    """Load the frozen core BY PATH, as a sibling. Never a dotted import."""
    path = os.path.join(CORE_ROOT, "canonkit.py")
    spec = importlib.util.spec_from_file_location("frozen_core", path)
    if spec is None or spec.loader is None:
        raise ImportError("could not build an import spec for %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_contract():
    """The check-module contract, PREFERRING AN ALREADY-LOADED COPY.

    Loading __init__.py by path a second time would mint a SECOND CheckResult
    class, and a runner comparing against its own would reject a result that is
    structurally identical.
    """
    target = os.path.realpath(os.path.join(HERE, "__init__.py"))
    for module in list(sys.modules.values()):
        origin = getattr(module, "__file__", None)
        if not origin or not hasattr(module, "CheckResult"):
            continue
        try:
            if os.path.realpath(origin) == target:
                return module
        except (OSError, ValueError):
            continue
    spec = importlib.util.spec_from_file_location("check_contract", target)
    if spec is None or spec.loader is None:
        raise ImportError("could not build an import spec for %s" % target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def parse_stamp(value):
    """An ISO-8601 timestamp as a datetime, or None when it is not one."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(text)
    except ValueError:
        return None


# WHY THIS MODULE NEVER READS A FILE'S mtime, AND WHY THAT IS A TEST RATHER
# THAN A PROMISE.
#
# Ordering two records by their mtime is the convenient answer, it is one import
# away, and it is wrong here for two measured reasons rather than one stylistic
# one:
#
#   1. An ordinary copy PRESERVES mtime. A results tree copied forward from an
#      earlier session therefore carries entirely plausible file times, and the
#      copied-results case is precisely one of the two failures a design rule's content
#      token exists to catch. templates/verify.py records the same argument in
#      the same words, for the same reason.
#   2. mtime crosses the NTFS/WSL2 boundary badly on this machine, so the same
#      file can answer the question differently depending on which side asked.
#
#   3. And it is trivially SET. `touch` is not a difficult attack; it is a
#      single command, and nothing about the result looks edited.
#
# So this module orders by the ISO timestamps recorded INSIDE each record and
# nothing else. tools/tests/test_check_04.py asserts that two ways: every line
# in this file naming mtime is a COMMENT line, and -- the stronger form --
# tokenize proves no NAME or attribute token here contains it, which also
# catches st_mtime and getmtime. The test additionally sets a MISLEADING mtime
# on a measurement and asserts the verdict does not move.


def comparable(left, right):
    """True when two datetimes can be ordered against each other.

    Python refuses to compare an aware datetime with a naive one, and raises
    while doing it. Asking the question first turns that into a NAMED finding
    instead of a traceback, which is the difference between a check that reports
    a defect and a check that crashes on one.
    """
    if left is None or right is None:
        return False
    return (left.tzinfo is None) == (right.tzinfo is None)


def relative_path(artifact, path):
    """A stable, forward-slashed id for a file inside the artifact."""
    try:
        rel = os.path.relpath(str(path), str(artifact))
    except ValueError:
        rel = str(path)
    return rel.replace(os.sep, "/")


def read_json(path):
    """The parsed object, or None when the file is not readable JSON."""
    try:
        with open(str(path), "rb") as handle:
            return json.loads(handle.read().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def enumerate_measurements(artifact):
    """Every measurement under results/, with the excluded ones named.

    A measurement is a results record that says WHEN IT BEGAN. That is the
    definition this check can order something against, so it is the definition
    of its population.
    """
    root = os.path.join(str(artifact), RESULTS_DIRNAME)
    measurements = []
    not_examined = []
    if not os.path.isdir(root):
        return measurements, not_examined

    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.basename(dirpath) == ITEMS_DIRNAME:
            for name in sorted(filenames):
                if name.endswith(".json"):
                    not_examined.append({
                        "path": relative_path(artifact,
                                              os.path.join(dirpath, name)),
                        "reason": "a per-item record, not a measurement. "
                                  "runmeta.py keeps these in their own "
                                  "directory so a glob over runs does not "
                                  "count them."})
            dirnames[:] = []
            continue
        dirnames.sort()
        for name in sorted(filenames):
            if not name.endswith(".json"):
                continue
            full = os.path.join(dirpath, name)
            rel = relative_path(artifact, full)
            if os.path.dirname(full) == root and name == GATE_FILENAME:
                not_examined.append({
                    "path": rel,
                    "reason": "the gate is what a measurement is ordered "
                              "AGAINST, so it is not itself in the population."})
                continue
            record = read_json(full)
            if not isinstance(record, dict):
                not_examined.append({
                    "path": rel,
                    "reason": "not a readable JSON object."})
                continue
            if STARTED_AT not in record:
                not_examined.append({
                    "path": rel,
                    "reason": "records no %s, so there is no instant to order "
                              "against the gate. CHECK-06 is what requires a "
                              "results file carrying numbers to have a run "
                              "record behind it." % STARTED_AT})
                continue
            measurements.append({
                "path": rel,
                "started_at_raw": record.get(STARTED_AT),
                "started_at": parse_stamp(record.get(STARTED_AT)),
                "token": record.get(GATE_TOKEN),
            })
    return measurements, not_examined


def read_gate(artifact):
    """(gate_record, dated_at, present). `present` is a fact, not an inference."""
    path = os.path.join(str(artifact), RESULTS_DIRNAME, GATE_FILENAME)
    if not os.path.isfile(path):
        return None, None, False
    record = read_json(path)
    if not isinstance(record, dict):
        return None, None, True
    return record, parse_stamp(record.get(DATED_AT)), True


def short(token):
    """A token prefix for a message, or a word naming its absence."""
    if not isinstance(token, str) or not token:
        return "<none>"
    return token[:TOKEN_PREFIX]


# ---------------------------------------------------------------------------
# THE DETECTION. Isolated in one function so the RED commit stubs exactly this
# and the GREEN commit replaces exactly this.
# ---------------------------------------------------------------------------


def gate_findings(gate, gate_dated_at, gate_present, measurements):
    """The four branches, over ONE gate record and N measurements.

    THE FAILED-GATE CARVE-OUT IS AN ABSENCE, AND ABSENCES ARE EASY TO LOSE.
    Nothing below reads `passed`. That is the requirement working, not an
    oversight: this function asks whether the gate was RECORDED, whether it
    PRECEDED each run, and whether its token is STAMPED -- and a correctly
    recorded failure satisfies all three. `passed` is READ by build_note and
    PRINTED, so a reader can see the carve-out being taken rather than having
    to infer it from a pass.

    Ordering uses only the parsed ISO stamps. See the comment block above
    comparable() for why the filesystem's own record is not evidence here.
    """
    if not gate_present:
        return [{
            "kind": FINDING_GATE_ABSENT,
            "id": "gate:%s" % FINDING_GATE_ABSENT,
            "path": "%s/%s" % (RESULTS_DIRNAME, GATE_FILENAME),
            "detail": "there is no gate record, so nothing authorised the %d "
                      "measurement(s) under this artifact and no ordering "
                      "question can even be asked. REPAIR: run `python gate.py` "
                      "in the artifact root BEFORE measuring; a gate written "
                      "afterwards records a decision that did not govern "
                      "anything." % len(measurements)}]

    findings = []
    run_token = (gate or {}).get(RUN_TOKEN)

    for measurement in measurements:
        path = measurement["path"]
        started_at = measurement["started_at"]

        # --- ordering, from the records ------------------------------------
        if not comparable(gate_dated_at, started_at):
            findings.append({
                "kind": FINDING_UNORDERABLE,
                "id": "gate:%s:%s" % (FINDING_UNORDERABLE, path),
                "path": path,
                "detail": "this record's %s (%r) cannot be ordered against the "
                          "gate's %s (%r). Either one of them is not a "
                          "parseable ISO-8601 timestamp, or one is naive while "
                          "the other carries an offset -- and a naive stamp "
                          "beside an aware one cannot be compared at all. "
                          "REPAIR: write both through canonkit.now_local, "
                          "which always carries a real offset."
                          % (STARTED_AT, measurement["started_at_raw"],
                             DATED_AT, (gate or {}).get(DATED_AT))})
        elif not gate_dated_at < started_at:
            findings.append({
                "kind": FINDING_AFTER_MEASUREMENT,
                "id": "gate:%s:%s" % (FINDING_AFTER_MEASUREMENT, path),
                "path": path,
                "detail": "the gate is dated %s and this run began %s, so the "
                          "gate did NOT precede it. A gate decided at or after "
                          "the moment a run started did not authorise that run; "
                          "at best it was written up afterwards. REPAIR: run "
                          "the gate first and re-measure. Note the comparison "
                          "is over the timestamps recorded INSIDE these "
                          "records, so re-saving either file changes nothing."
                          % (gate_dated_at.isoformat(), started_at.isoformat())})

        # --- the token ------------------------------------------------------
        # Evaluated INDEPENDENTLY of the ordering above rather than in an else
        # branch. A run can be both mis-ordered and unauthorised, and an author
        # who fixed only the one the check happened to mention would re-run and
        # be told about the other -- which reads as the check moving its own
        # goalposts.
        token = measurement["token"]
        if not token:
            findings.append({
                "kind": FINDING_TOKEN_ABSENT,
                "id": "gate:%s:%s" % (FINDING_TOKEN_ABSENT, path),
                "path": path,
                "detail": "this record carries no %s, so nothing ties it to the "
                          "gate that was supposed to authorise it. A run with "
                          "no token cannot be tested against anything, which is "
                          "why runmeta.start_run REFUSES to open one. REPAIR: "
                          "pass what canonkit.require_gate returns into "
                          "start_run." % GATE_TOKEN})
        elif token != run_token:
            findings.append({
                "kind": FINDING_TOKEN_MISMATCH,
                "id": "gate:%s:%s" % (FINDING_TOKEN_MISMATCH, path),
                "path": path,
                "detail": "this record carries token %s but the gate in this "
                          "artifact minted %s. a design rule makes the token a function "
                          "of gate CONTENT, so these two differ exactly when "
                          "the gate has CHANGED since this run -- or when the "
                          "results were copied in from another session. REPAIR: "
                          "re-measure under the current gate; do not restamp "
                          "the record, which would erase the only evidence that "
                          "they disagree."
                          % (short(token), short(run_token))})

    return findings


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


def waiver_ids(waivers):
    """The finding ids an owner-authored waiver suppresses for THIS check."""
    ids = set()
    for waiver in waivers or []:
        if not isinstance(waiver, dict):
            continue
        check = waiver.get("check") or waiver.get("check_id")
        if check != CHECK_ID:
            continue
        for field in ("finding_id", "id"):
            value = waiver.get(field)
            if isinstance(value, str) and value:
                ids.add(value)
    return ids


def build_note(gate, gate_dated_at, gate_present, checked, listed):
    """The summary line's tail. Every number in it is one this check measured.

    `gate-passed` is REPORTED and never acted on. A reader who sees
    `gate-passed=False` beside a PASS is seeing the requirement's carve-out
    working, and a reader who cannot see it has no way to tell that carve-out
    from an oversight.
    """
    if not gate_present:
        return ("gate=ABSENT measurements=%d of %d" % (checked, listed))
    passed = (gate or {}).get("passed", (gate or {}).get("ok"))
    return ("gate=present gate-passed=%s gate-dated=%s token=%s "
            "measurements=%d of %d"
            % (passed,
               gate_dated_at.isoformat() if gate_dated_at else "UNPARSEABLE",
               short((gate or {}).get(RUN_TOKEN)), checked, listed))


def run(artifact, ctx=None):
    """Measure. Returns a CheckResult. DOES NOT PRINT -- the caller prints."""
    core = load_core()
    contract = load_contract()
    ctx = ctx if ctx is not None else contract.CheckContext()
    floor = ctx.floor_for(CHECK_ID, DEFAULT_FLOOR)
    artifact = os.path.abspath(str(artifact))

    def refused(note, listed=0, not_examined=None):
        result = contract.CheckResult(
            check_id=CHECK_ID, code=core.EXIT_DID_NOT_RUN, found=0, checked=0,
            floor=floor, waived=0, not_examined=listed, listed=listed, note=note)
        result.detail = {"artifact": artifact, "gate_present": False,
                         "gate_passed": None, "gate_dated_at": "",
                         "gate_token": "",
                         "not_examined": list(not_examined or []),
                         "findings": []}
        return result

    if not os.path.isdir(artifact):
        return refused("%s is not a directory" % artifact)

    gate, gate_dated_at, gate_present = read_gate(artifact)
    measurements, not_examined = enumerate_measurements(artifact)
    checked = len(measurements)
    listed = checked + len(not_examined)

    if not checked:
        return refused(
            "no results file under %s/%s records a %s, so there is no "
            "measurement for a gate to have preceded. An ordering claim over "
            "nothing is not an ordering claim. REPAIR: run the measurement "
            "through runmeta.start_run, which stamps %s and the gate token."
            % (os.path.basename(artifact), RESULTS_DIRNAME, STARTED_AT,
               STARTED_AT),
            listed=listed, not_examined=not_examined)

    findings = list(gate_findings(gate, gate_dated_at, gate_present,
                                  measurements))

    waived_ids = waiver_ids(getattr(ctx, "waivers", None))
    kept = [finding for finding in findings if finding["id"] not in waived_ids]
    waived = len(findings) - len(kept)

    found = len(kept)
    if checked < floor:
        code = core.EXIT_DID_NOT_RUN
    elif found:
        code = core.EXIT_FINDING
    else:
        code = core.EXIT_PASS

    note = build_note(gate, gate_dated_at, gate_present, checked, listed)

    result = contract.CheckResult(
        check_id=CHECK_ID, code=code, found=found, checked=checked, floor=floor,
        waived=waived, not_examined=len(not_examined), listed=listed, note=note,
        finding_ids=sorted({finding["id"] for finding in kept}))
    result.detail = {
        "artifact": artifact,
        "gate_present": gate_present,
        "gate_passed": (gate or {}).get("passed", (gate or {}).get("ok")),
        "gate_dated_at": gate_dated_at.isoformat() if gate_dated_at else "",
        "gate_token": short((gate or {}).get(RUN_TOKEN)),
        "not_examined": not_examined,
        "findings": kept,
    }
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_report(result, core):
    """The structured record, over stable fields only."""
    detail = getattr(result, "detail", {}) or {}
    return {
        "schema": SCHEMA,
        "schema_version": core.SCHEMA_VERSION,
        "check_id": result.check_id,
        "code": result.code,
        "found": result.found,
        "checked": result.checked,
        "listed": result.listed,
        "not_examined": result.not_examined,
        "floor": result.floor,
        "waived": result.waived,
        "finding_ids": list(result.finding_ids),
        "note": result.note,
        "gate_present": detail.get("gate_present", False),
        "gate_passed": detail.get("gate_passed"),
        "gate_dated_at": detail.get("gate_dated_at", ""),
        "gate_token": detail.get("gate_token", ""),
        # TWO KEYS, DELIBERATELY. `not_examined` above is the COUNT that has to
        # match the printed label; this is the list of entries and the reason
        # beside each. They collided for one commit on 2026-09-21, when the
        # count stopped being spelled the banned way and landed on this name --
        # a duplicate dict key is legal, the later one wins, and the count would
        # have vanished from every report with nothing raised.
        "not_examined_entries": detail.get("not_examined", []),
        "findings": detail.get("findings", []),
        "artifact": detail.get("artifact", ""),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_04",
        description="CHECK-04: fails when results/gate.json is absent, when "
                    "its dated_at is not earlier than every measurement's "
                    "started_at, or when a measurement lacks the gate token. A "
                    "correctly recorded FAILED gate is a PASS.")
    parser.add_argument("artifact", nargs="?", default=".",
                        help="the artifact directory (default: the current one)")
    parser.add_argument("--report", default=None,
                        help="write the structured report here. A file "
                             "rather than a stream a caller has to capture: a "
                             "command joined to another process reports the "
                             "other process's exit status.")
    parser.add_argument("--min-population", type=int, default=None,
                        help="override the effective POPULATION floor. "
                             "The OVERRIDDEN value is what prints as floor=.")
    args = parser.parse_args(argv)

    core = load_core()
    contract = load_contract()

    overrides = {}
    if args.min_population is not None:
        overrides[CHECK_ID] = args.min_population
    ctx = contract.CheckContext(floor_overrides=overrides)

    result = run(args.artifact, ctx)

    core.report(CHECK_ID, result.code == core.EXIT_PASS, result.found,
                result.checked, result.floor, waived=result.waived,
                note=result.note, not_examined=result.not_examined, listed=result.listed)

    if result.checked and result.checked < result.floor:
        print("  DEMOTED to DID-NOT-RUN: population %d is below the effective "
              "floor %d." % (result.checked, result.floor))

    detail = getattr(result, "detail", {}) or {}
    for finding in detail.get("findings", [])[:MAX_LISTED_FINDINGS]:
        print("  %-18s %s: %s" % (finding["kind"], finding["path"],
                                  finding["detail"]))
    extra = len(detail.get("findings", [])) - MAX_LISTED_FINDINGS
    if extra > 0:
        print("  ... and %d more" % extra)

    if result.code == core.EXIT_DID_NOT_RUN and not result.checked:
        sys.stderr.write("%s %s\n" % (core.REFUSAL_PREFIX, result.note))
        sys.stderr.flush()

    if args.report:
        core.atomic_write_json(args.report, build_report(result, core))

    return result.code


if __name__ == "__main__":
    sys.exit(main())
