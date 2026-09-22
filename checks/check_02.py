"""CHECK-02 -- the README's date must be a date a MACHINE wrote.

    python check_02.py <artifact> [--report FILE] [--min-population N]

the project requirements document states the check verbatim: "Fails when the README date is
absent, or does not equal the date component of a machine-emitted `started_at`
in a results file."

WHY THIS CHECK EXISTS, AND THE MEASURED REASON IT COULD NOT RUN UNTIL NOW
-------------------------------------------------------------------------
The date is the single easiest field in an artifact to TYPE rather than derive.
Nothing about a hand-typed date looks wrong: it is well formed, it is plausible,
and it is wrong only in the one way that matters -- it is not what the machine
recorded.

The shared pattern note probed both shipped artifacts for started_at / finished_at /
dated_at / "timestamp" / isoformat and found exactly ONE hit, and that hit is a
synthetic log document's field rather than a run stamp. So before an earlier plan
built the emitter this check had NO MACHINE SIDE to compare against and could
only ever have reported that a date looked like a date. That is why a project requirement came
first, and it is why this module refuses rather than passes when it finds no
machine stamp: "there was nothing to compare against" is not "the date agrees".

THE LOCAL DATE COMPONENT, AND WHY THAT CHOICE IS PRINTED RATHER THAN ASSUMED
-----------------------------------------------------------------------------
a design rule stores timestamps BOTH ways: `started_at` as local time carrying a REAL
offset, and `started_at_utc` beside it. This check compares the README's date
against the LOCAL one, because the local stamp is the one a reader's intuition
matches -- "measured on the fifteenth" means the day it was on the machine.

The two can name DIFFERENT DAYS, and on this machine they routinely do. Measured
while this check was written: the local stamp read 2026-09-15T19:57:50-05:00 and
the UTC counterpart read 2026-09-16T00:57:50+00:00 at the same instant. Same
moment, two dates, one day apart. A silent choice between them would be a defect
nobody could see, so this check makes the choice EXPLICIT (local) and COUNTS the
divergences in its own summary line as `utc-date-differs=N`. A legitimate
difference is still worth printing; a reader who sees that number knows which
day the comparison was against and why the other file says something else.

TWO FAILURE BRANCHES, KEPT APART ON PURPOSE
---------------------------------------------
    absent      the README carries no date this check can read: the document is
                missing, the artifact:date region is missing, or the region is
                there and holds no ISO-8601 date at all.
    disagrees   a date is present and does NOT equal the local date component of
                a machine-emitted started_at, naming the results file it
                disagreed with.

Collapsing them into one verdict would tell an author that "the date is a
problem" without saying which problem, and the repairs are different: one is
"render the region", the other is "the rendered date and the run disagree, so
one of them was not produced by the run".

WHAT IS IN THE POPULATION, AND WHAT IS DELIBERATELY NOT
--------------------------------------------------------
Every `*.json` under `results/`, recursively, EXCEPT:

    results/gate.json          the gate is not a measurement. Its `dated_at` is
                               the instant a gate was decided, not the instant a
                               run started, and comparing a README date against
                               it would report agreement with something that
                               measured nothing. Gate ordering is CHECK-04's job.
    results/raw/items/*.json   per-item records. runmeta.py keeps them in their
                               own directory precisely so a glob over run
                               records does not count them, and a per-item
                               record carries no run stamp anyway.

Both exclusions are COUNTED and printed as not-examined rather than silently
dropped, because a population that quietly shrinks is the failure this whole
phase is organised around.

`found` and `checked` answer different questions and are reported separately:
`found` is the number of missing-or-disagreeing dates, `checked` is the number of
results files that actually carried a machine-emitted started_at.

EXIT CODES (canonkit's contract, a design rule)
    0  the README's date equals the local date component of every machine stamp
    1  the date is absent, or it disagrees with at least one machine stamp
    2  it could not look: no results file under this artifact carries a
       machine-emitted started_at, or the population is below the effective
       floor

VENDORING. Enumerated into the vendored set by tools/vendor.py's check-module
glob and copied to <artifact>/checks/check_02.py, beside <artifact>/canonkit.py.
Run BY PATH under a bare module name, never as a dotted package module. Stdlib
only, ASCII only.
"""

import argparse
import datetime
import importlib.util
import json
import os
import re
import sys

CHECK_ID = "CHECK-02"

# a design rule: the POPULATION floor, declared per-check IN CODE, overridable on the
# command line, and the EFFECTIVE value is what prints as `floor=`. One results
# file carrying a machine stamp is the smallest population over which this check
# means anything; zero is DID-NOT-RUN.
DEFAULT_FLOOR = 1

SCHEMA = "canonkit/check-02/1"

HERE = os.path.dirname(os.path.abspath(__file__))

# `tools/` in this repository, `<artifact>/` in a vendored copy. ONE expression
# for both layouts: the checks package always sits one directory below the core.
CORE_ROOT = os.path.dirname(HERE)

DOCUMENT = "README.md"
ANCHOR = "artifact:date"
REGION_TOKEN = "artifact:"

RESULTS_DIRNAME = "results"
GATE_FILENAME = "gate.json"

# runmeta.py's own separation, restated here as the reason for an exclusion
# rather than as a magic string.
ITEMS_DIRNAME = "items"

STARTED_AT = "started_at"
STARTED_AT_UTC = "started_at_utc"

FINDING_ABSENT = "absent"
FINDING_DISAGREES = "disagrees"

MAX_LISTED_FINDINGS = 20

# How many distinct machine dates the summary line names before it stops. The
# COUNT is always printed; the enumeration is a convenience.
MAX_NAMED_DATES = 3

REGION_RE = re.compile(
    r"<!--\s*%s:begin\s*-->\n(?P<body>.*?)<!--\s*%s:end\s*-->" % (ANCHOR, ANCHOR),
    re.S)

# An ISO-8601 calendar date, INCLUDING the date component of a full timestamp.
#
# THE BOUNDARY HERE IS A LOOKAHEAD AND NOT `\b`, AND THAT IS A MEASURED FIX.
# The first version of this constant ended in `\b` with a comment claiming it
# found the date component of a full timestamp. It does not: in
# `2026-09-15T20:08:11-05:00` the character after `15` is `T`, which is a WORD
# character, so there is no word boundary there and the match fails. The
# comment described a property the expression did not have.
#
# That mattered immediately rather than hypothetically. render.py writes a
# region body as a KEY HOLE, so the walking skeleton's rendered date region is
#     <!--artifact:key:dated_at-->2026-09-15T20:08:11.856801-05:00<!--/...-->
# and the `\b` version reported `readme-date=ABSENT` over a document whose date
# was right there. The GENERATED artifact -- the one every path produces -- was
# the case the expression could not read.
#
# `(?!\d)` rejects a longer number (2026-09-155) while accepting any non-digit
# continuation, which is what a timestamp is. `(?<!\d)` does the same at the
# front.
ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")


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
    """The check-module contract (CheckResult, CheckContext).

    PREFERS AN ALREADY-LOADED COPY, for the reason check_03.py records: a runner
    that loaded the package holds one class object, and loading __init__.py by
    path a second time would mint a SECOND CheckResult class that a runner
    comparing against its own would reject.
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


def region_body(text):
    """The bytes BETWEEN the paired begin/end markers, or None when absent."""
    match = REGION_RE.search(text)
    return match.group("body") if match else None


def first_iso_date(text):
    """The first ISO-8601 calendar date in `text` as a date, or None.

    Returns None rather than raising on 2026-13-45: a well-shaped string that
    names no real day is not a date, and treating it as absent gives the author
    the same repair instruction.
    """
    if not text:
        return None
    for match in ISO_DATE_RE.finditer(text):
        try:
            return datetime.date(int(match.group(1)), int(match.group(2)),
                                 int(match.group(3)))
        except ValueError:
            continue
    return None


def parse_stamp(value):
    """An ISO-8601 timestamp as a datetime, or None when it is not one.

    Accepts a naive stamp. Whether a stamp is AWARE is CHECK-06's question and
    it names the naive case specifically; this check's job is the DATE, and a
    naive stamp still has one. Refusing it here would move a CHECK-06 finding
    into CHECK-02's count, which is how two checks come to report the same
    defect twice and neither reports it clearly.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    # fromisoformat accepts a trailing Z from 3.11 onward. Normalising it here
    # keeps this module working on 3.10 as well, and costs nothing on newer.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(text)
    except ValueError:
        return None


def relative_path(artifact, path):
    """A stable, forward-slashed id for a file inside the artifact."""
    try:
        rel = os.path.relpath(str(path), str(artifact))
    except ValueError:
        rel = str(path)
    return rel.replace(os.sep, "/")


def enumerate_results_files(artifact):
    """Every candidate under results/, with the excluded ones named.

    Returns (candidates, exclusions). `exclusions` is a list of
    {path, reason} so the not-examined count carries a reason beside it rather
    than being a bare number.
    """
    root = os.path.join(str(artifact), RESULTS_DIRNAME)
    candidates = []
    exclusions = []
    if not os.path.isdir(root):
        return candidates, exclusions

    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.basename(dirpath) == ITEMS_DIRNAME:
            for name in sorted(filenames):
                if name.endswith(".json"):
                    exclusions.append({
                        "path": relative_path(artifact,
                                              os.path.join(dirpath, name)),
                        "reason": "a per-item record, not a results file. "
                                  "runmeta.py keeps these in their own "
                                  "directory so a glob over run records does "
                                  "not count them as runs."})
            dirnames[:] = []
            continue
        dirnames.sort()
        for name in sorted(filenames):
            if not name.endswith(".json"):
                continue
            full = os.path.join(dirpath, name)
            if os.path.dirname(full) == root and name == GATE_FILENAME:
                exclusions.append({
                    "path": relative_path(artifact, full),
                    "reason": "the gate is not a measurement: its dated_at is "
                              "when a gate was decided, not when a run "
                              "started. Gate ordering is CHECK-04's job."})
                continue
            candidates.append(full)
    return candidates, exclusions


def read_json(path):
    """The parsed object, or None when the file is not readable JSON."""
    try:
        with open(str(path), "rb") as handle:
            return json.loads(handle.read().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def machine_stamps(artifact):
    """Every machine-emitted started_at under results/, with its file.

    Returns (stamps, not_examined). A `stamp` is a dict carrying the file's
    relative path, the parsed LOCAL datetime, its date, and -- when the record
    carries one -- the UTC counterpart's date, so the divergence can be counted
    without parsing twice.
    """
    candidates, not_examined = enumerate_results_files(artifact)
    stamps = []
    for path in candidates:
        rel = relative_path(artifact, path)
        record = read_json(path)
        if not isinstance(record, dict):
            not_examined.append({
                "path": rel,
                "reason": "not a readable JSON object, so it carries no "
                          "machine stamp this check can read."})
            continue
        local = parse_stamp(record.get(STARTED_AT))
        if local is None:
            not_examined.append({
                "path": rel,
                "reason": "carries no parseable %s, so it records no instant a "
                          "run began." % STARTED_AT})
            continue
        utc = parse_stamp(record.get(STARTED_AT_UTC))
        stamps.append({
            "path": rel,
            "local": local,
            "date": local.date(),
            "utc_date": utc.date() if utc is not None else None,
        })
    return stamps, not_examined


# ---------------------------------------------------------------------------
# THE DETECTION. Isolated in one function so the RED commit stubs exactly this
# and the GREEN commit replaces exactly this.
# ---------------------------------------------------------------------------


def date_findings(document, readme_date, readme_note, stamps):
    """The two branches, evaluated over ONE rendered date and N machine stamps.

    `readme_date` is None when the document carries no date this check can read;
    `readme_note` says WHICH of the three ways it was absent, so the repair
    instruction is specific.

    The two branches are kept apart and never collapsed. They have DIFFERENT
    repairs: an absent date means "render the region", a disagreeing date means
    "the rendered date and the run do not describe the same day, so one of them
    was not produced by the run". A single combined verdict would name the
    problem without naming the repair.

    A disagreement is reported PER MACHINE STAMP, naming the file it disagreed
    with. One finding for the whole document would say a date is wrong without
    saying what it is wrong against, and an artifact whose results files
    disagree with EACH OTHER would then be indistinguishable from one whose
    single stamp disagrees with the README.
    """
    if readme_date is None:
        return [{
            "kind": FINDING_ABSENT,
            "id": "date:%s:%s" % (FINDING_ABSENT, document),
            "path": document,
            "detail": "%s. A machine recorded %d start(s) under %s/ and none of "
                      "those dates is published. REPAIR: render the %s region "
                      "from the figures record rather than typing a date into "
                      "prose."
                      % (readme_note, len(stamps), RESULTS_DIRNAME, ANCHOR)}]

    findings = []
    for stamp in stamps:
        if stamp["date"] == readme_date:
            continue

        # The highest-value diagnostic this check can give, and the reason it
        # carries the UTC date at all: when the rendered date equals the UTC
        # counterpart, the author did not invent a date -- they read the other
        # one of two fields that are both present and both machine-written.
        if stamp["utc_date"] is not None and stamp["utc_date"] == readme_date:
            why = ("The rendered date equals this record's %s (%s) while its "
                   "%s names %s. Both fields are machine-written and they fall "
                   "on different days; a design rule stores both so the choice between "
                   "them is deliberate. CHECK-02 compares the LOCAL one. "
                   "REPAIR: render from %s."
                   % (STARTED_AT_UTC, stamp["utc_date"].isoformat(),
                      STARTED_AT, stamp["date"].isoformat(), STARTED_AT))
        else:
            why = ("The rendered date is %s and this record's %s names %s. "
                   "REPAIR: render the %s region from the machine record "
                   "rather than typing a date, or explain why a run on one day "
                   "is published under another."
                   % (readme_date.isoformat(), STARTED_AT,
                      stamp["date"].isoformat(), ANCHOR))

        findings.append({
            "kind": FINDING_DISAGREES,
            "id": "date:%s:%s" % (FINDING_DISAGREES, stamp["path"]),
            "path": stamp["path"],
            "detail": why})
    return findings


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


def read_document(artifact):
    """The README's text, or None when there is none to read.

    An absent README is NOT a refusal here, and that differs from CHECK-03 on
    purpose. CHECK-03 asks about a paragraph inside the document, so with no
    document there is nothing to have an opinion about. CHECK-02 asks whether a
    machine-recorded date was PUBLISHED, and a machine stamp with no document
    carrying its date is that question answered no.
    """
    path = os.path.join(str(artifact), DOCUMENT)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def readme_date_for(artifact):
    """(date, note) for the artifact's rendered date region.

    `note` names which of the three absences applies, so a reader is not left to
    guess between "no document", "no region" and "a region with no date".
    """
    text = read_document(artifact)
    if text is None:
        return None, ("%s carries no %s at all" % (artifact, DOCUMENT))
    body = region_body(text)
    if body is None:
        return None, ("%s carries no %s region, so no date is addressed by this "
                      "mechanism" % (DOCUMENT, ANCHOR))
    found = first_iso_date(body)
    if found is None:
        return None, ("the %s region of %s holds no ISO-8601 date"
                      % (ANCHOR, DOCUMENT))
    return found, ""


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


def build_note(readme_date, stamps, checked, listed, divergent):
    """The summary line's tail. Every number in it is one this check measured."""
    dates = sorted({stamp["date"].isoformat() for stamp in stamps})
    named = ", ".join(dates[:MAX_NAMED_DATES])
    if len(dates) > MAX_NAMED_DATES:
        named = named + ", +%d more" % (len(dates) - MAX_NAMED_DATES)
    return ("readme-date=%s machine-dates=%d (%s) results-files=%d of %d "
            "utc-date-differs=%d"
            % (readme_date.isoformat() if readme_date else "ABSENT",
               len(dates), named or "none", checked, listed, divergent))


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
        result.detail = {"artifact": artifact, "document": DOCUMENT,
                         "readme_date": "", "machine_dates": [],
                         "utc_date_differs": 0,
                         "not_examined": list(not_examined or []),
                         "findings": []}
        return result

    if not os.path.isdir(artifact):
        return refused("%s is not a directory" % artifact)

    stamps, not_examined = machine_stamps(artifact)
    checked = len(stamps)
    listed = checked + len(not_examined)

    if not checked:
        return refused(
            "no results file under %s/%s carries a machine-emitted %s, so there "
            "is no machine side to compare a README date against. A date that "
            "agrees with nothing is not a date that agrees. REPAIR: run the "
            "measurement through runmeta.start_run, which stamps %s and %s."
            % (os.path.basename(artifact), RESULTS_DIRNAME, STARTED_AT,
               STARTED_AT, STARTED_AT_UTC),
            listed=listed, not_examined=not_examined)

    readme_date, readme_note = readme_date_for(artifact)
    divergent = sum(1 for stamp in stamps
                    if stamp["utc_date"] is not None
                    and stamp["utc_date"] != stamp["date"])

    findings = list(date_findings(DOCUMENT, readme_date, readme_note, stamps))

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

    note = build_note(readme_date, stamps, checked, listed, divergent)

    result = contract.CheckResult(
        check_id=CHECK_ID, code=code, found=found, checked=checked, floor=floor,
        waived=waived, not_examined=len(not_examined), listed=listed, note=note,
        finding_ids=sorted({finding["id"] for finding in kept}))
    result.detail = {
        "artifact": artifact,
        "document": DOCUMENT,
        "readme_date": readme_date.isoformat() if readme_date else "",
        "machine_dates": sorted({stamp["date"].isoformat() for stamp in stamps}),
        "utc_date_differs": divergent,
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
        "document": detail.get("document", DOCUMENT),
        "readme_date": detail.get("readme_date", ""),
        "machine_dates": list(detail.get("machine_dates", [])),
        "utc_date_differs": detail.get("utc_date_differs", 0),
        # THE COUNT AND THE ENTRIES ARE TWO KEYS, and they were one for as long
        # as the count was spelled the banned way. When the count was renamed to
        # `not_examined` on 2026-09-21 it landed on the key this list already
        # held: a duplicate key in a dict literal is legal, the LATER one wins
        # silently, and the count would have been deleted from every report with
        # nothing raised and nothing in the diff to see. The list is the reasons;
        # `not_examined` above is the number that has to match the printed label.
        "not_examined_entries": detail.get("not_examined", []),
        "findings": detail.get("findings", []),
        "artifact": detail.get("artifact", ""),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_02",
        description="CHECK-02: fails when the README date is absent, or does "
                    "not equal the LOCAL date component of a machine-emitted "
                    "started_at in a results file.")
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
        print("  %-12s %s: %s" % (finding["kind"], finding["path"],
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
