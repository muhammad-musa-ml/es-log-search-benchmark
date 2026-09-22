"""CHECK-03 -- an unedited template copy must not pass.

    python check_03.py <artifact> [--report FILE] [--min-population N]
                                  [--word-floor N]

the project requirements document states the check verbatim: "Fails when the 'what this does not
show' section is absent, is byte-identical to the template placeholder, falls
under its word floor, or contains no scope vocabulary -- an unedited template
copy must not pass."

WHY A HEADING COUNT IS NOT A CHECK, AND THIS IS THE MEASURED REASON
-------------------------------------------------------------------
The inherited acceptance criterion was `grep -c "What this does not show" >= 1`.
An unedited template copy satisfies it perfectly: the heading survives every copy
untouched. A criterion that a completely unedited artifact passes is not a weak
check, it is an unrun one.

Worse, the heading is not even stable. The two artifacts that shipped before this
program existed use two DIFFERENT limitations headings -- `## What this benchmark
is NOT` and `## Honest limits on these numbers` -- so a check keyed on either
literal passes one artifact and fails the other. Both numbers are measured, not
supposed.

So this check keys on the ANCHOR, `artifact:limits`, and never on heading text.
The region is the addressing mechanism; the heading above it is free prose.

WHAT IT LOOKS AT, AND WHAT IT DELIBERATELY DOES NOT
-----------------------------------------------------
README.md AND results/RESULTS.md -- the two documents SCANNED_DOCUMENTS declares.

**This paragraph used to say "README.md, and only README.md", and called that a
scoping decision rather than an oversight.** It was neither: results/RESULTS.md
ships the SAME limits placeholder, so an artifact could fill its README, leave
the RESULTS placeholder exactly as generated, and pass. an earlier plan recorded it as open
item 6 with "the plan that next edits check_03.py" as its owner; an earlier plan is
that plan, and a design rule closed it.

Why it survived as long as it did is worth keeping, because it is the reason a
gap can sit in plain sight: the walking-skeleton round trip FILLS the RESULTS
region the way a real author would, so the defect is unreachable from the
skeleton and fully reachable from a hand-authored artifact. Every test passed,
and the one shape the tests exercised was the one shape that could not fail.

The two are not equal. README.md is REQUIRED -- absent, it is a refusal, because
an artifact must not be able to delete its README and pass on a correct optional
document. results/RESULTS.md is optional: absent, it simply does not join the
population. The count of documents actually examined prints as `documents=N of M`
so the difference is readable rather than inferable from this paragraph.

ON EVERY BRANCH, INCLUDING A REFUSAL. A DID-NOT-RUN carries `documents=0 of M`
too, because a check that says it could not look and then does not say how much
of its declared population that covers is the line the conventions document, section 2,
exists to forbid. Measured 2026-09-17: both of this programme's two existing
artifacts land on exactly that branch -- neither README carries an `artifact:`
region yet -- so it is the line a reader of an earlier round actually sees.

FIVE CONDITIONS, NOT FOUR, AND WHERE THE FIFTH COMES FROM
-----------------------------------------------------------
The requirement names four. an earlier plan, which authored the placeholder, designed
it to fail four conditions of which one -- "names itself" -- is not on the
requirement's list, while "absent" (which is) cannot apply to a placeholder that
is present. Taking the union rather than either list alone:

    absent                 a region-bearing README with no artifact:limits
                           region at all. The document carries other regions, so
                           the limits one was removed rather than never added.
    unedited               the region body is byte-identical to the skeleton's
                           own placeholder, compared by sha256.
    thin                   the body falls under its word floor.
    no-scope-vocabulary    the body contains no term that BOUNDS a claim.
    sentinel               the body still carries the skeleton's own TODO marker.
                           Without this, a body padded past the word floor with
                           two scope terms passes while still saying "replace
                           this paragraph".

"ABSENT" IS TWO DIFFERENT FACTS AND THEY GET DIFFERENT CODES
--------------------------------------------------------------
    no README, or a README carrying no artifact: region at all
        -> code 2, DID-NOT-RUN. There was nothing to look at. This is not a
           rendered artifact and saying "its limits paragraph is bad" would be a
           finding about a document this check never read.
    a region-bearing README with no limits region
        -> code 1. The document IS addressed by this mechanism and the region
           was removed.

"Could not look" and "found a problem" stay distinct, which is the distinction
a design rule calls the most important one in the checker.

THE BYTE COMPARISON, AND WHERE ITS CROSS-CHECK LIVES
------------------------------------------------------
LIMITS_PLACEHOLDER_SHA256 below is a COMMITTED LITERAL, deliberately not a value
derived from templates/README-SKELETON.md at import time. A derived constant
follows an edit to the placeholder and every assertion keeps passing -- exactly
the drift the constant exists to catch.

It must equal the value an earlier plan recorded. tools/tests/test_check_03.py IMPORTS
that plan's constant rather than re-typing it and asserts the two are equal, so
the two plans cannot drift apart silently.

This module also cross-checks the LIVE skeleton when it can reach one, which it
can from this repository and cannot from a vendored copy inside an artifact (an
artifact has no templates/ directory). That arm's availability is REPORTED --
`skeleton=checked` or `skeleton=unavailable` -- rather than left as a silent
difference between two runs of the same tool.

EXIT CODES (canonkit's contract, a design rule)
    0  a filled-in limits paragraph that bounds its claim
    1  at least one of the five conditions. The check DID look.
    2  it could not look: no README, no region-bearing document, or a population
       below the effective floor.

VENDORING. Enumerated into the vendored set by tools/vendor.py's check-module
glob and copied to <artifact>/checks/check_03.py, beside <artifact>/canonkit.py.
Run BY PATH under a bare module name, never as a dotted package module. Stdlib
only, ASCII only.
"""

import argparse
import hashlib
import importlib.util
import os
import re
import sys

CHECK_ID = "CHECK-03"

# a design rule: the POPULATION floor, declared per-check IN CODE, overridable on the
# command line, and the EFFECTIVE value is what prints as `floor=`. One
# region-bearing document is the smallest population over which this check means
# anything; zero is DID-NOT-RUN.
DEFAULT_FLOOR = 1

# The WORD floor is a different number answering a different question, so it is a
# different constant. Collapsing the two would make `floor=` ambiguous and would
# demote every run to DID-NOT-RUN, because a population of one document is always
# below a word floor of forty.
DEFAULT_WORD_FLOOR = 40

# The key a caller uses to override the word floor through CheckContext, so both
# floors travel the same channel without sharing a name.
WORD_FLOOR_KEY = "CHECK-03:words"

SCHEMA = "canonkit/check-03/1"

HERE = os.path.dirname(os.path.abspath(__file__))

# `tools/` in this repository, `<artifact>/` in a vendored copy. ONE expression
# for both layouts: the checks package always sits one directory below the core.
CORE_ROOT = os.path.dirname(HERE)

# a design rule / an earlier plan open item 6. The scalar `DOCUMENT` is GONE rather than shadowed:
# two sources of truth for "which documents do we scan" is the split this change
# exists to close, and a fallback constant beside the tuple would recreate it.
#
# `results/RESULTS.md` ships the SAME limits placeholder as the README and went
# unchecked. The round trip masks that -- it fills the RESULTS region as a real
# author would -- so the gap is unreachable from the walking skeleton and fully
# reachable from a hand-authored artifact, which is what both of this phase's
# artifacts are.
#
# The tuple and the reader below are copied from check_09, which already scans
# exactly these two documents. Two checks disagreeing about which documents an
# artifact HAS is how a confident verdict gets delivered over half a tree.
SCANNED_DOCUMENTS = ("README.md", "results/RESULTS.md")
REQUIRED_DOCUMENT = "README.md"

ANCHOR = "artifact:limits"
REGION_TOKEN = "artifact:"

# The sha256 of the UNEDITED artifact:limits body as both skeletons ship it.
# Recorded by an earlier plan in tools/tests/test_template_generate.py as
# LIMITS_PLACEHOLDER_SHA256 and restated here because a vendored copy cannot
# reach that module. The two are asserted equal by tools/tests/test_check_03.py.
LIMITS_PLACEHOLDER_SHA256 = (
    "9c0056098163d3cfc0a0a9694665bd2cfd79a38aeaa82d720fce82360efcd0a3")

# The skeleton's own TODO marker, assembled from parts so this file's source is
# not itself a hit for a sweep that hunts the marker across the tree.
SENTINEL = "TODO(" + ANCHOR + ")"

SKELETON_RELATIVE = os.path.join("templates", "README-SKELETON.md")

# ---------------------------------------------------------------------------
# THE SCOPE VOCABULARY
# ---------------------------------------------------------------------------
#
# A declared, committed list with each term's reason beside it, kept HERE next to
# the check so it is reviewable rather than magic. These are terms that BOUND a
# claim: they name the population it was measured over, the conditions it does
# not cover, or what a reader must not conclude.
#
# It is deliberately the SAME TEN TERMS an earlier plan asserted the placeholder
# carries none of, and tools/tests/test_check_03.py pins the two sets equal.
# WIDENING THIS LIST WEAKENS THE CHECK: every term added is one more way for an
# unedited-in-spirit paragraph to satisfy the condition, so a term earns its
# place by bounding a claim, never by being a word that often appears nearby.
SCOPE_VOCABULARY = (
    ("not shown", "names something the artifact deliberately does not cover"),
    ("does not", "the plainest form of naming an exclusion"),
    ("excludes", "names what was removed from the measured population"),
    ("limited to", "names the boundary of the population"),
    ("only", "narrows a claim to the conditions actually measured"),
    ("cannot", "names a conclusion a reader must not draw"),
    ("untested", "names a path that was never exercised"),
    ("unmeasured", "names a quantity nobody put a number on"),
    ("out of scope", "names the boundary explicitly"),
    ("never", "names an absolute exclusion"),
)
SCOPE_TERMS = tuple(term for term, _ in SCOPE_VOCABULARY)

# The committed literal, asserted against the derivation at import time. a design rule's
# derive-and-assert shape: a purely derived count silently stops checking when a
# term is dropped, because expected falls to match found.
SCOPE_TERM_COUNT = 10

if len(SCOPE_TERMS) != SCOPE_TERM_COUNT:
    raise RuntimeError(
        "SCOPE_VOCABULARY declares %d term(s) but the committed literal "
        "SCOPE_TERM_COUNT says %d. Update BOTH in the same commit -- and read "
        "the paragraph above first: widening this list WEAKENS the check."
        % (len(SCOPE_TERMS), SCOPE_TERM_COUNT))

if len(set(SCOPE_TERMS)) != len(SCOPE_TERMS):
    raise RuntimeError("SCOPE_VOCABULARY contains a duplicate term")

FINDING_ABSENT = "absent"
FINDING_UNEDITED = "unedited"
FINDING_THIN = "thin"
FINDING_NO_SCOPE = "no-scope-vocabulary"
FINDING_SENTINEL = "sentinel"
FINDING_PLACEHOLDER_DRIFT = "placeholder-drift"

MAX_LISTED_FINDINGS = 20

REGION_RE = re.compile(
    r"<!--\s*%s:begin\s*-->\n(?P<body>.*?)<!--\s*%s:end\s*-->" % (ANCHOR, ANCHOR),
    re.S)
ANY_REGION_RE = re.compile(
    r"<!--\s*%s[a-z][a-z0-9_-]*:(?:begin|end)\s*-->" % REGION_TOKEN)


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

    PREFERS AN ALREADY-LOADED COPY. A runner that loaded the package holds one
    class object; loading this file's sibling __init__.py by path a second time
    would mint a SECOND CheckResult class, and a runner comparing against its own
    would reject a result that is structurally identical.
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


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def region_body(text):
    """The bytes BETWEEN the paired begin/end markers, or None when absent."""
    match = REGION_RE.search(text)
    return match.group("body") if match else None


def is_region_bearing(text):
    """True when the document uses the paired-region addressing mechanism."""
    return bool(ANY_REGION_RE.search(text))


def word_count(body):
    return len(body.split())


def scope_terms_in(body):
    lowered = body.lower()
    return [term for term in SCOPE_TERMS if term in lowered]


def skeleton_placeholder_sha256(source_root=None):
    """The LIVE skeleton's limits body sha, or None when no skeleton is reachable.

    Reachable from this repository, unreachable from a vendored copy inside an
    artifact -- an artifact has no templates/ directory. The availability is
    REPORTED rather than silently changing what the check examined.
    """
    root = (os.path.abspath(str(source_root)) if source_root
            else os.path.dirname(CORE_ROOT))
    path = os.path.join(root, SKELETON_RELATIVE)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    body = region_body(text)
    return sha256_text(body) if body is not None else None


# ---------------------------------------------------------------------------
# THE DETECTION. Isolated in one function so the RED commit stubs exactly this
# and the GREEN commit replaces exactly this.
# ---------------------------------------------------------------------------


def limits_findings(document, body, word_floor):
    """The five conditions, evaluated over ONE region body.

    `body` is None when the region is absent from a document that DOES use the
    region mechanism. A document using no region at all never reaches here --
    that is a refusal, not a finding, and run() makes the distinction.

    Each condition is evaluated INDEPENDENTLY and each produces its own finding
    id. A single combined verdict could be carried by any one of them and would
    not tell an author which one to fix; the placeholder fails four at once and
    each of the four is named separately.
    """
    if body is None:
        return [{
            "kind": FINDING_ABSENT,
            "id": "limits:%s:%s" % (FINDING_ABSENT, document),
            "document": document,
            "detail": "%s uses the paired-region mechanism but carries no "
                      "%s region. The region was removed rather than never "
                      "added. REPAIR: restore the region and write the "
                      "paragraph inside it." % (document, ANCHOR)}]

    findings = []

    if sha256_text(body) == LIMITS_PLACEHOLDER_SHA256:
        findings.append({
            "kind": FINDING_UNEDITED,
            "id": "limits:%s:%s" % (FINDING_UNEDITED, document),
            "document": document,
            "detail": "the body is BYTE-IDENTICAL to the skeleton's own "
                      "placeholder (sha %s). A heading count passes this "
                      "unchanged, which is why the comparison is over bytes. "
                      "REPAIR: write what this artifact does not show."
                      % LIMITS_PLACEHOLDER_SHA256[:12]})

    words = word_count(body)
    if words < word_floor:
        findings.append({
            "kind": FINDING_THIN,
            "id": "limits:%s:%s" % (FINDING_THIN, document),
            "document": document,
            "detail": "the body is %d word(s) against an effective floor of "
                      "%d. REPAIR: name the population, the conditions it does "
                      "not cover, and what a reader must not conclude."
                      % (words, word_floor)})

    terms = scope_terms_in(body)
    if not terms:
        findings.append({
            "kind": FINDING_NO_SCOPE,
            "id": "limits:%s:%s" % (FINDING_NO_SCOPE, document),
            "document": document,
            "detail": "the body carries none of the %d declared terms that "
                      "BOUND a claim. A paragraph that only describes what WAS "
                      "measured is not a limits paragraph. REPAIR: say what "
                      "this does not show, in those words. Declared terms: %s"
                      % (len(SCOPE_TERMS), ", ".join(SCOPE_TERMS))})

    if SENTINEL in body:
        findings.append({
            "kind": FINDING_SENTINEL,
            "id": "limits:%s:%s" % (FINDING_SENTINEL, document),
            "document": document,
            "detail": "the body still carries the skeleton's own marker, so it "
                      "says `replace this paragraph` while claiming to be the "
                      "replacement. Without this condition a body padded past "
                      "the word floor with two bounding terms would pass with "
                      "the marker intact. REPAIR: delete the marker line."})

    return findings


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


def read_documents(artifact):
    """(relative, text) for every scanned document PRESENT. Refusals are code 2.

    Three states, kept apart on purpose:

      absent + optional   not a document, not an error. It simply does not join
                          the population, and the count in the note says so.
      absent + REQUIRED   a refusal. Otherwise an artifact could delete its
                          README and pass on a correct optional document.
      unreadable          a refusal, NEVER a silent drop. A document that cannot
                          be read is not a document with nothing in it, and
                          dropping it shrinks the population with no error --
                          which is the shape this programme refuses everywhere.
    """
    documents = []
    for relative in SCANNED_DOCUMENTS:
        path = os.path.join(str(artifact), relative.replace("/", os.sep))
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as handle:
                documents.append((relative, handle.read().decode("utf-8")))
        except UnicodeDecodeError as error:
            raise CheckRefusal(
                "%s is not valid UTF-8 (%s), so its limits region could not be "
                "read. REPAIR: re-write the document as UTF-8."
                % (relative, error))
    if not any(relative == REQUIRED_DOCUMENT for relative, _ in documents):
        raise CheckRefusal(
            "%s carries no %s, so there is no limits paragraph to examine. "
            "REPAIR: generate the artifact from the skeleton."
            % (artifact, REQUIRED_DOCUMENT))
    return documents


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
    overrides = getattr(ctx, "floor_overrides", None) or {}
    word_floor = overrides.get(WORD_FLOOR_KEY, DEFAULT_WORD_FLOOR)
    artifact = os.path.abspath(str(artifact))

    def refused(note):
        # THE COUNT TRAVELS ON THIS BRANCH TOO, and it is not decoration.
        # The conventions document, section 2: every check prints ONE line on EVERY branch,
        # carrying its count WITH its verdict. A DID-NOT-RUN that does not say
        # how many of its declared documents it examined is the shape that rule
        # exists to forbid -- and it is the branch BOTH of an earlier round's artifacts
        # currently land on, so it is the line a reader of this phase actually
        # sees. `0 of 2` is always correct here: a refusal examined none of
        # them, whatever the reason, and the reason is the sentence beside it.
        result = contract.CheckResult(
            check_id=CHECK_ID, code=core.EXIT_DID_NOT_RUN, found=0, checked=0,
            floor=floor, waived=0,
            note="%s documents=0 of %d" % (note, len(SCANNED_DOCUMENTS)))
        result.detail = {"artifact": artifact, "document": REQUIRED_DOCUMENT,
                         "documents": [],
                         "documents_scanned": 0,
                         "documents_declared": len(SCANNED_DOCUMENTS),
                         "word_floor": word_floor, "words": 0,
                         "scope_terms": [], "region_present": False,
                         "region_bearing": False, "body_sha256": "",
                         "skeleton_cross_checked": False, "findings": []}
        return result

    if not os.path.isdir(artifact):
        return refused("%s is not a directory" % artifact)

    try:
        documents = read_documents(artifact)
    except CheckRefusal as refusal:
        return refused(str(refusal))

    texts = dict(documents)
    required_text = texts[REQUIRED_DOCUMENT]

    # The REQUIRED document decides whether this check addresses the artifact at
    # all -- unchanged from before the tuple. An OPTIONAL document that carries
    # no region is simply not part of the population; it is not a finding, and
    # it is not a refusal either.
    if not is_region_bearing(required_text):
        return refused(
            "%s carries no %s region of any kind, so this is not a document "
            "this check addresses. A finding about a paragraph that was never "
            "read is not a finding. REPAIR: generate the artifact from the "
            "skeleton, which ships the paired regions."
            % (REQUIRED_DOCUMENT, REGION_TOKEN))

    examined = [(relative, text) for relative, text in documents
                if is_region_bearing(text)]
    checked = len(examined)

    findings = []
    for relative, text in examined:
        findings.extend(limits_findings(relative, region_body(text), word_floor))

    # The scalar detail fields describe the REQUIRED document, which is what
    # every existing reader of this report means by "the region". The second
    # document contributes FINDINGS and the document COUNT; collapsing two
    # bodies into one word count would be a number about neither.
    body = region_body(required_text)

    # The cross-check against the LIVE skeleton, when one is reachable. Its
    # availability is recorded either way: an arm that silently does not run in
    # half the layouts is an arm nobody can reason about.
    live_sha = skeleton_placeholder_sha256()
    if live_sha is not None and live_sha != LIMITS_PLACEHOLDER_SHA256:
        findings.append({
            "kind": FINDING_PLACEHOLDER_DRIFT,
            "id": "limits:%s" % FINDING_PLACEHOLDER_DRIFT,
            "document": SKELETON_RELATIVE.replace(os.sep, "/"),
            "detail": "the live skeleton's limits body hashes %s but this "
                      "module's committed constant is %s. The two plans have "
                      "drifted apart. REPAIR: update BOTH in the same commit."
                      % (live_sha, LIMITS_PLACEHOLDER_SHA256)})

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

    words = word_count(body) if body is not None else 0
    terms = scope_terms_in(body) if body is not None else []
    note = ("region=%s words=%d of %d scope-terms=%d documents=%d of %d "
            "skeleton=%s"
            % ("present" if body is not None else "ABSENT", words, word_floor,
               len(terms), len(examined), len(SCANNED_DOCUMENTS),
               "checked" if live_sha is not None else "unavailable"))

    result = contract.CheckResult(
        check_id=CHECK_ID, code=code, found=found, checked=checked, floor=floor,
        waived=waived, note=note,
        finding_ids=sorted({finding["id"] for finding in kept}))
    result.detail = {
        "artifact": artifact,
        "document": REQUIRED_DOCUMENT,
        "documents": [relative for relative, _ in examined],
        "documents_scanned": len(examined),
        "documents_declared": len(SCANNED_DOCUMENTS),
        "word_floor": word_floor,
        "words": words,
        "scope_terms": terms,
        "region_present": body is not None,
        "region_bearing": True,
        "body_sha256": sha256_text(body) if body is not None else "",
        "skeleton_cross_checked": live_sha is not None,
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
        "document": detail.get("document", REQUIRED_DOCUMENT),
        "documents": list(detail.get("documents", [])),
        "documents_scanned": detail.get("documents_scanned", 0),
        "documents_declared": detail.get("documents_declared", len(SCANNED_DOCUMENTS)),
        "word_floor": detail.get("word_floor", DEFAULT_WORD_FLOOR),
        "words": detail.get("words", 0),
        "scope_terms": list(detail.get("scope_terms", [])),
        "region_present": detail.get("region_present", False),
        "region_bearing": detail.get("region_bearing", False),
        "body_sha256": detail.get("body_sha256", ""),
        "skeleton_cross_checked": detail.get("skeleton_cross_checked", False),
        "findings": detail.get("findings", []),
        "artifact": detail.get("artifact", ""),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_03",
        description="CHECK-03: fails when the limits paragraph is absent, is "
                    "byte-identical to the template placeholder, falls under "
                    "its word floor, or contains no scope vocabulary.")
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
    parser.add_argument("--word-floor", type=int, default=None,
                        help="override the effective WORD floor. The OVERRIDDEN "
                             "value is what prints in the note.")
    args = parser.parse_args(argv)

    core = load_core()
    contract = load_contract()

    overrides = {}
    if args.min_population is not None:
        overrides[CHECK_ID] = args.min_population
    if args.word_floor is not None:
        overrides[WORD_FLOOR_KEY] = args.word_floor
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
        print("  %-20s %s: %s" % (finding["kind"], finding["document"],
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
