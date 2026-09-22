"""CHECK-06 -- every results file carries a machine-emitted run record.

    python check_06.py <artifact> [--report FILE] [--min-population N]

the project requirements document states the check verbatim: "Fails when a results file carries no
machine-emitted run record." a project requirement states what such a record is: `started_at`
and `finished_at` in ISO-8601 with offset, the environment fingerprint, and
`{api_spend_usd, gpu_minutes, wall_seconds}` -- "written by the run, never by a
human".

AN OMITTED KEY AND A ZERO ARE DIFFERENT CLAIMS
------------------------------------------------
A run that spent nothing writes `0.0`. It does not omit the key.

This is the whole reason the cost triple is checked for PRESENCE rather than for
plausibility. `record.get("api_spend_usd", 0.0)` cannot tell an absence from a
zero, so an omitted key reads downstream as a run that cost nothing -- and
a project requirement re-derives each path's metered spend and GPU hours from exactly these
records before the owner says go. A missing key that reads as free is a number
the owner would act on.

So `api_spend_usd: 0.0` PASSES here and the same key OMITTED is a finding, and
there is a test for each so the pair cannot quietly collapse into one rule.

A NAIVE TIMESTAMP PRESENTED AS UTC, AND THE MEASURED WAY TO CATCH IT
----------------------------------------------------------------------
The failure the research note names is `datetime.utcnow().isoformat() + "Z"`. The
object was NAIVE -- it carried no timezone at all -- and the appended letter
claims UTC. It type-checks, it looks right, and every consumer that parses it
gets an aware datetime built from an unaware one.

The obvious rule, "reject a stamp that parses without tzinfo", catches only half
of it. MEASURED on this interpreter (CPython 3.12.11):

    datetime.fromisoformat("2026-01-01T00:00:00Z")  ->  tzinfo is None: False

so the hand-assembled string parses as AWARE and sails through. The other half
needs a different observation, and this one is also measured:

    datetime.now(timezone.utc).isoformat()  ->  '2026-09-16T00:57:50+00:00'
    datetime.now().astimezone().isoformat() ->  '2026-09-15T19:57:50-05:00'

`datetime.isoformat()` NEVER emits a literal `Z`. It writes an offset. So a `Z`
suffix in a field this project's emitter wrote is proof the string was assembled
by appending a suffix rather than produced by the clock -- which is the
utcnow()-plus-Z shape by construction. Both arms report the NAIVE case by name,
because "invalid timestamp" would send an author looking for a typo.

WHERE A RESULTS FILE'S RUN RECORD LIVES
-----------------------------------------
Not always inside the file. The record is located in one of three places, tried
in this order, and WHICH ONE was used is reported:

    inline      the file carries `run_id`, so it IS a run record.
                `results/raw/<run_id>.json`, written by runmeta.
    run-block   the file carries a `run` object. `results/provenance.json`,
                which copies the seven fields out of the run record.
    by-token    the file carries a `gate_token` and a record under
                `results/raw/` carries the same one. This is how
                `results/figures.json` -- a DERIVED view with no cost fields of
                its own -- is tied to the run that produced it.

If none of the three finds a record, the file carries numbers that no machine
run stands behind, and that is the finding the requirement names.

WHAT IS IN THE POPULATION
---------------------------
A `*.json` file under `results/` that carries numbers a reader would take as
measured: one with a `figures` block, a `run` block, a `run_id`, or any run key
at top level. EXCEPT:

    results/gate.json          a gate decides; it does not measure. Its
                               ordering and its token are CHECK-04's job.
    results/raw/items/*.json   per-item records are the INPUT to a derivation,
                               not results files in their own right, and
                               runmeta.py keeps them in their own directory for
                               exactly that reason. Their run record is the run
                               that wrote them.

Both exclusions are counted with a reason beside them.

`results/provenance.json`'s `images{}` block is NOT examined here. Pin-shaped
reasoning over that block is CHECK-08's scope (an earlier plan), and the measured
false positive lives there -- a provenance KEY naming the load generator by its
floating tag, whose VALUE is a digest, is not an unpinned image. This check
reads `run` and nothing else out of that document.

THE TAG IS DESCRIBED, NEVER SPELLED. This file is vendored into every artifact,
so a comment that explained the ban by QUOTING the banned string would plant one
carrier of it in every artifact generated from here, forever -- which is the
consequence templates/docker-compose.yml already measured on its own first
draft, and the reason check_08.py assembles its needle from parts rather than
writing it. Do not "clarify" this sentence by naming the tag.

EXIT CODES (canonkit's contract, a design rule)
    0  every results file carrying numbers has a complete machine run record
    1  a record is missing, partial, or carries a timestamp that lies
    2  it could not look: no results file under this artifact carries numbers,
       or the population is below the effective floor

VENDORING. Enumerated into the vendored set by tools/vendor.py's check-module
glob and copied to <artifact>/checks/check_06.py, beside <artifact>/canonkit.py.
Run BY PATH under a bare module name, never as a dotted package module. Stdlib
only, ASCII only.
"""

import argparse
import datetime
import importlib.util
import json
import os
import sys

CHECK_ID = "CHECK-06"

# a design rule: the POPULATION floor, declared per-check IN CODE, overridable on the
# command line, and the EFFECTIVE value is what prints as `floor=`.
DEFAULT_FLOOR = 1

SCHEMA = "canonkit/check-06/1"

HERE = os.path.dirname(os.path.abspath(__file__))
CORE_ROOT = os.path.dirname(HERE)

RESULTS_DIRNAME = "results"
GATE_FILENAME = "gate.json"
RAW_DIRNAME = "raw"
ITEMS_DIRNAME = "items"

RUN_BLOCK = "run"
RUN_ID = "run_id"
GATE_TOKEN = "gate_token"
FIGURES = "figures"

# The seven fields a project requirement requires, as a COMMITTED LITERAL rather than a value
# read from the core at import time. A derived constant follows an edit to the
# core and every assertion here keeps passing -- exactly the drift the literal
# exists to catch -- and a vendored copy inside an artifact must not depend on
# the core's spelling of a list it can restate. tools/tests/test_check_06.py
# asserts this tuple equals canonkit.PROVENANCE_RUN_KEYS, so the two cannot
# drift apart silently.
RUN_RECORD_KEYS = ("started_at", "finished_at", "started_at_utc",
                   "finished_at_utc", "api_spend_usd", "gpu_minutes",
                   "wall_seconds")

RUN_RECORD_KEY_COUNT = 7

if len(RUN_RECORD_KEYS) != RUN_RECORD_KEY_COUNT:
    raise RuntimeError(
        "RUN_RECORD_KEYS holds %d field(s) but the committed literal "
        "RUN_RECORD_KEY_COUNT says %d. Update BOTH in the same commit, or the "
        "derived count silently stops checking."
        % (len(RUN_RECORD_KEYS), RUN_RECORD_KEY_COUNT))

TIMESTAMP_KEYS = ("started_at", "finished_at", "started_at_utc",
                  "finished_at_utc")
COST_KEYS = ("api_spend_usd", "gpu_minutes", "wall_seconds")

SOURCE_INLINE = "inline"
SOURCE_RUN_BLOCK = "run-block"
SOURCE_BY_TOKEN = "by-token"

FINDING_MISSING = "missing-record"
FINDING_PARTIAL = "partial-record"
FINDING_NAIVE = "naive-timestamp"
FINDING_UNPARSEABLE = "unparseable-timestamp"

MAX_LISTED_FINDINGS = 20


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
    """The check-module contract, PREFERRING AN ALREADY-LOADED COPY."""
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


def relative_path(artifact, path):
    try:
        rel = os.path.relpath(str(path), str(artifact))
    except ValueError:
        rel = str(path)
    return rel.replace(os.sep, "/")


def read_json(path):
    try:
        with open(str(path), "rb") as handle:
            return json.loads(handle.read().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def carries_numbers(record):
    """True when a results record holds numbers a reader would take as measured.

    Four shapes rather than "any number anywhere": a waivers file or a manifest
    fragment can hold an integer without claiming a measurement, and demanding a
    run record behind those would report findings about documents that never
    measured anything.
    """
    if not isinstance(record, dict):
        return False
    if isinstance(record.get(FIGURES), dict) and record[FIGURES]:
        return True
    if isinstance(record.get(RUN_BLOCK), dict):
        return True
    if record.get(RUN_ID):
        return True
    return any(key in record for key in RUN_RECORD_KEYS)


def is_naive_shaped(value):
    """(is_naive, why) for an ISO-8601 string. See the module docstring.

    Returns (False, "") for a stamp that is genuinely aware, and (None, why)
    when the string does not parse at all -- a different finding.
    """
    if not isinstance(value, str) or not value.strip():
        return None, "is not a string carrying a timestamp at all"
    text = value.strip()

    # ARM TWO, and it must come FIRST: the hand-assembled form parses as AWARE,
    # so a tzinfo test run before this one would clear it and return.
    if text.endswith("Z"):
        return True, (
            "ends with a literal Z. datetime.isoformat() NEVER emits Z -- it "
            "writes an offset such as +00:00 -- so this string was assembled by "
            "APPENDING a suffix to a stamp rather than produced by the clock. "
            "That is the utcnow().isoformat() + \"Z\" shape: a NAIVE datetime "
            "presented as UTC. It type-checks and it lies")

    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None, "is not a parseable ISO-8601 timestamp"

    if parsed.tzinfo is None:
        return True, (
            "parses with no tzinfo at all, so it is a NAIVE datetime. Nothing "
            "in it says which zone it belongs to, and a design rule needs a real offset "
            "because CHECK-02 compares the LOCAL date component against the "
            "README's date")
    return False, ""


# ---------------------------------------------------------------------------
# Locating the run record
# ---------------------------------------------------------------------------


def raw_records(artifact):
    """Every run record under results/raw/, keyed by its gate token.

    A list per token rather than one record: two runs under the same gate is
    the normal case, and keeping only the last would silently pick a winner.
    """
    root = os.path.join(str(artifact), RESULTS_DIRNAME, RAW_DIRNAME)
    by_token = {}
    if not os.path.isdir(root):
        return by_token
    for name in sorted(os.listdir(root)):
        if not name.endswith(".json"):
            continue
        record = read_json(os.path.join(root, name))
        if not isinstance(record, dict):
            continue
        token = record.get(GATE_TOKEN)
        if isinstance(token, str) and token:
            by_token.setdefault(token, []).append((name, record))
    return by_token


def locate_run_record(path, record, by_token):
    """(run_record, source, record_path, why) for one results record.

    `record_path` NAMES THE RECORD, and that is what the record-level findings
    are keyed on rather than the file that referenced it. Several results files
    legitimately point at ONE run record -- a derived figures record and the raw
    record it came from are the normal case -- and keying a finding on the
    referencing file would report ONE incomplete record once per reference.
    `found` would then count references rather than defects, which makes it a
    property of the artifact's shape instead of its faults. A record that is
    MISSING is the exception and is keyed on the referencing file, because there
    is no record to name.

    `run_record` is None when none of the three locations holds one, and `why`
    then says which locations were tried and how each came up empty.
    """
    if record.get(RUN_ID):
        return record, SOURCE_INLINE, path, ""

    block = record.get(RUN_BLOCK)
    if isinstance(block, dict):
        return block, SOURCE_RUN_BLOCK, "%s#%s" % (path, RUN_BLOCK), ""

    token = record.get(GATE_TOKEN)
    if isinstance(token, str) and token:
        matches = by_token.get(token)
        if matches:
            return (matches[0][1], SOURCE_BY_TOKEN,
                    "%s/%s/%s" % (RESULTS_DIRNAME, RAW_DIRNAME, matches[0][0]),
                    "")
        return None, "", "", (
            "it carries a %s but no record under %s/%s/ carries that token "
            "(%d record(s) there do carry one)"
            % (GATE_TOKEN, RESULTS_DIRNAME, RAW_DIRNAME,
               sum(len(v) for v in by_token.values())))

    return None, "", "", (
        "it carries no %s of its own, no %s block, and no %s to tie it to one"
        % (RUN_ID, RUN_BLOCK, GATE_TOKEN))


# ---------------------------------------------------------------------------
# THE DETECTION. Isolated in one function so the RED commit stubs exactly this
# and the GREEN commit replaces exactly this.
# ---------------------------------------------------------------------------


def record_findings(path, record, by_token):
    """Every finding about ONE results file's run record.

    Three questions, asked in an order that is not arbitrary:

      1. is there a record at all?          -> missing-record, and STOP. The
                                               later questions are about a
                                               record that does not exist.
      2. is every field PRESENT?            -> partial-record
      3. does every timestamp carry a zone? -> naive-timestamp

    2 and 3 are both asked even when 2 finds something, because they have
    different repairs and an author who fixed only the one the check happened to
    mention would re-run and be told about the other.
    """
    run_record, source, record_path, why = locate_run_record(path, record,
                                                             by_token)

    if run_record is None:
        return [{
            "kind": FINDING_MISSING,
            "id": "run-record:%s:%s" % (FINDING_MISSING, path),
            "path": path,
            "detail": "this file carries numbers a reader would take as "
                      "measured, and NO machine-emitted run record stands "
                      "behind them: %s. Nothing says when they were produced, "
                      "how long it took, or what it cost -- and an unbacked "
                      "number cannot be argued with, which is worse than a "
                      "wrong one. REPAIR: produce it through "
                      "runmeta.start_run / finish_run, which write the record "
                      "and stamp the gate token this lookup follows." % why}]

    findings = []

    # --- every field PRESENT, and a null is not a value --------------------
    #
    # `None` is what start_run leaves in finished_at before finish_run fills it,
    # so a null here is an UNFINISHED run rather than a recorded nothing. Both
    # shapes are reported as missing, and the message distinguishes them,
    # because "the key is not there" and "the run never closed" send an author
    # to different places.
    absent = [key for key in RUN_RECORD_KEYS if key not in run_record]
    nulled = [key for key in RUN_RECORD_KEYS
              if key in run_record and run_record[key] is None]
    mistyped = [key for key in COST_KEYS
                if key in run_record and run_record[key] is not None
                and (isinstance(run_record[key], bool)
                     or not isinstance(run_record[key], (int, float)))]

    if absent or nulled or mistyped:
        parts = []
        if absent:
            parts.append(
                "ABSENT: %s. An omitted key and a recorded zero are DIFFERENT "
                "CLAIMS -- a run that spent nothing writes 0.0 -- and the "
                "ordinary defaulting read cannot tell them apart, so an "
                "omission travels downstream as a run that cost nothing. "
                "a project requirement re-derives each path's metered spend from exactly "
                "this record" % ", ".join(absent))
        if nulled:
            parts.append(
                "PRESENT BUT NULL: %s. That is what start_run leaves behind "
                "before finish_run fills it in, so this run never closed"
                % ", ".join(nulled))
        if mistyped:
            parts.append(
                "NOT A NUMBER: %s. A cost field that is not a number cannot be "
                "summed, and a project requirement sums these" % ", ".join(mistyped))
        findings.append({
            "kind": FINDING_PARTIAL,
            "id": "run-record:%s:%s" % (FINDING_PARTIAL, record_path),
            "path": record_path,
            "detail": "this run record (located %s) is incomplete. %s. REPAIR: "
                      "close the run through runmeta.finish_run, which REFUSES "
                      "a call that does not supply the whole cost triple."
                      % (source, "; ".join(parts))})

    # --- every timestamp AWARE --------------------------------------------
    naive = []
    unparseable = []
    for key in TIMESTAMP_KEYS:
        if key not in run_record or run_record[key] is None:
            continue                      # already reported as partial, above
        verdict, why_stamp = is_naive_shaped(run_record[key])
        if verdict is True:
            naive.append("%s (%r) %s" % (key, run_record[key], why_stamp))
        elif verdict is None:
            unparseable.append("%s (%r) %s" % (key, run_record[key], why_stamp))

    if naive:
        findings.append({
            "kind": FINDING_NAIVE,
            "id": "run-record:%s:%s" % (FINDING_NAIVE, record_path),
            "path": record_path,
            "detail": "NAIVE timestamp(s) in this run record -- %s. A naive "
                      "datetime presented as UTC type-checks and lies, and "
                      "every consumer that parses it gets an aware datetime "
                      "built from an unaware one. REPAIR: write both forms "
                      "through canonkit.now_local and canonkit.now_utc, which "
                      "always carry a real offset." % "; ".join(naive)})

    if unparseable:
        findings.append({
            "kind": FINDING_UNPARSEABLE,
            "id": "run-record:%s:%s" % (FINDING_UNPARSEABLE, record_path),
            "path": record_path,
            "detail": "timestamp field(s) that are not ISO-8601 at all -- %s. "
                      "REPAIR: write them through canonkit.now_local / "
                      "now_utc rather than formatting them by hand."
                      % "; ".join(unparseable)})

    return findings


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


def enumerate_results_files(artifact):
    """(in_population, not_examined). Every exclusion carries its reason."""
    root = os.path.join(str(artifact), RESULTS_DIRNAME)
    population = []
    not_examined = []
    if not os.path.isdir(root):
        return population, not_examined

    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.basename(dirpath) == ITEMS_DIRNAME:
            for name in sorted(filenames):
                if name.endswith(".json"):
                    not_examined.append({
                        "path": relative_path(artifact,
                                              os.path.join(dirpath, name)),
                        "reason": "a per-item record: the INPUT to a "
                                  "derivation rather than a results file. Its "
                                  "run record is the run that wrote it."})
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
                    "reason": "a gate decides; it does not measure. Its "
                              "ordering and its token are CHECK-04's job."})
                continue
            record = read_json(full)
            if not isinstance(record, dict):
                not_examined.append({
                    "path": rel, "reason": "not a readable JSON object."})
                continue
            if not carries_numbers(record):
                not_examined.append({
                    "path": rel,
                    "reason": "carries no figures block, no run block, no "
                              "run id and no run field, so it makes no "
                              "measured claim that needs a run behind it."})
                continue
            population.append((rel, record))
    return population, not_examined


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
        result.detail = {"artifact": artifact, "sources": {},
                         "not_examined": list(not_examined or []),
                         "findings": []}
        return result

    if not os.path.isdir(artifact):
        return refused("%s is not a directory" % artifact)

    population, not_examined = enumerate_results_files(artifact)
    checked = len(population)
    listed = checked + len(not_examined)

    if not checked:
        return refused(
            "no results file under %s/%s carries a figure or a measurement, so "
            "there is nothing here that needs a run record behind it. REPAIR: "
            "run the measurement through runmeta.start_run and finish_run, "
            "which write the record this check looks for."
            % (os.path.basename(artifact), RESULTS_DIRNAME),
            listed=listed, not_examined=not_examined)

    by_token = raw_records(artifact)

    # ONE FINDING PER DEFECT, not per reference to it. Several results files
    # legitimately point at one run record, so the same incomplete record is
    # reached more than once; the record-level findings are keyed on the RECORD
    # and collapse here. Without this, `found` would grow with the number of
    # derived views an artifact happens to publish, which would make the count a
    # property of its shape rather than of its faults.
    findings = []
    seen_ids = set()
    sources = {}
    for path, record in population:
        _, source, _, _ = locate_run_record(path, record, by_token)
        sources[path] = source or "none"
        for finding in record_findings(path, record, by_token):
            if finding["id"] in seen_ids:
                continue
            seen_ids.add(finding["id"])
            findings.append(finding)

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

    located = sum(1 for value in sources.values() if value != "none")
    note = ("records-located=%d of %d (%s) results-files=%d of %d"
            % (located, checked,
               " ".join("%s=%d" % (name,
                                   sum(1 for v in sources.values() if v == name))
                        for name in (SOURCE_INLINE, SOURCE_RUN_BLOCK,
                                     SOURCE_BY_TOKEN)),
               checked, listed))

    result = contract.CheckResult(
        check_id=CHECK_ID, code=code, found=found, checked=checked, floor=floor,
        waived=waived, not_examined=len(not_examined), listed=listed, note=note,
        finding_ids=sorted({finding["id"] for finding in kept}))
    result.detail = {
        "artifact": artifact,
        "sources": sources,
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
        "sources": detail.get("sources", {}),
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
        prog="check_06",
        description="CHECK-06: fails when a results file carrying numbers has "
                    "no machine-emitted run record behind it, when that record "
                    "is partial, or when its timestamps are naive.")
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
        print("  %-22s %s: %s" % (finding["kind"], finding["path"],
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
