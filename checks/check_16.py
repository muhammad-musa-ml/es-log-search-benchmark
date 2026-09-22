"""CHECK-16 -- a retracted figure that is still being asserted.

    python check_16.py <artifact> [--report FILE] [--min-population N]
                                  [--radius N]

the project requirements document reserved this id with its trigger: "Retraction-leak grep --
trigger: the first retraction". The trigger arrived. One of this programme's
artifacts withdrew two figures and one claim, and a one-off sweep counted where
they still appeared. That sweep's closing section says plainly what it could not
do -- "It is a measurement taken once. Nothing re-runs it. If a retracted figure
is typed back into a sentence tomorrow, this file will not notice." This check
is what re-runs it.

WHAT IT REFUSES, AND WHAT IT MUST NOT
---------------------------------------
A retraction is worth something only if the withdrawn figure stops being
asserted. But a retraction RECORD quotes the figure it withdrew -- that is the
record doing its job -- and so does the withdrawn run's own machine record. To a
grep those look identical to a sentence that still claims the number, which is
why a grep alone was never going to settle this and why every hit here is
CLASSIFIED rather than counted.

THE FALSE POSITIVE THAT SHAPED THE NEEDLE RULE, MEASURED RATHER THAN IMAGINED
------------------------------------------------------------------------------
EVERY NUMBER IN THIS DOCSTRING IS INVENTED, and that is not squeamishness. This
module is VENDORED into every artifact, so it is inside the population of its
own scan -- and the first draft quoted the real withdrawn hit rate the case
below is about. It shipped into an artifact that declares that figure, and the
check reported a LIVE finding against its own documentation, at the exact line
that explains the rule. The project records seven earlier instances of a
repo-wide guard matching its own source; this is the eighth, and the repair is
the same one: use a number no artifact ever published.

The one-off sweep's single most useful finding, restated with invented values: a
results file's line `"rps": 6377.7` matches a needle of `77.7`. It is a
requests-per-second reading and has nothing to do with a hit rate, but nothing
about the four characters says so. Its conclusion is this check's rule:

    A numeric needle must carry its unit or its context -- a needle of `77.7%`
    does not match `6377.7`; a bare `77.7` does. Or it must carry a DIGIT
    BOUNDARY.

So a BARE-NUMERIC needle whose match is adjacent to another digit -- or to a
decimal point that makes it part of a longer number -- is FALSE-POSITIVE:
counted, printed, never a finding. The sweep is explicit about why that matters
more than tidiness: "a checker that fires on a throughput number in a results
file would train its reader to ignore it, and a checker that is routinely
ignored is worse than none."

THE FOUR ARMS, IN ORDER, WITH NO EXCLUSION LIST
-------------------------------------------------
    1. FALSE-POSITIVE  the needle matched something that is not the figure at
                       all: a bare-numeric needle inside a longer number, or a
                       word-form needle with none of its declared context terms
                       within the adjudication radius.
    2. FROZEN          a withdrawal marker sits within the radius, so the
                       appearance is a record quoting what was withdrawn.
    3. LIVE            everything else, WHEREVER IT LIVES. A live appearance
                       inside the retraction record itself is still a finding;
                       no document gets immunity from its name.
    4. UNCLASSIFIED    reserved. Never silent, and always a finding.

NO FILE IS EXCLUDED BY NAME. The declaration is scanned like every other file,
and its own hits land in FROZEN on the ordinary rule because each one sits
beside a withdrawal marker -- the correct answer arrived at by the classifier
rather than bought with an exemption. A hit nobody can place is UNCLASSIFIED and
is a finding, repaired by writing an adjudication beside the hit and never by
widening the marker set until the count reads zero.

THE POPULATION IS THE FILES, AND THE NEEDLE COUNT IS A SECOND NUMBER
----------------------------------------------------------------------
`checked` counts files READ. `not-examined` counts files listed and not read,
each with a reason. The declared retraction count and the needle count print in
the note beside them, because they answer a different question and neither can
stand in for the other: a scan of 149 files with 13 needles and a scan of 149
files with 0 needles are different runs, and one number cannot tell them apart.

AN ARTIFACT THAT HAS RETRACTED NOTHING IS A PASS, AND THAT IS DELIBERATE
--------------------------------------------------------------------------
`{"retracted": []}` is a legal, meaningful declaration: a dated, committed
statement that the author reviewed this artifact and it withdrew nothing. The
scan still walks every file and the verdict still rests on a real population.

What is NOT a pass is the declaration being ABSENT. That is a DID-NOT-RUN with a
REPAIR clause, because "no retracted figure is asserted here", said over an
artifact nobody reviewed, is a sentence rather than a measurement -- which is
the exact shape a design rule exists to refuse.

VENDORING. Enumerated into the vendored set by tools/vendor.py's check-module
glob and copied to <artifact>/checks/check_16.py, beside <artifact>/canonkit.py.
Run BY PATH under a bare module name, never as a dotted package module. Stdlib
only, ASCII only.
"""

import argparse
import importlib.util
import json
import os
import re
import sys

CHECK_ID = "CHECK-16"

# a design rule: the POPULATION floor, declared per-check IN CODE, overridable on the
# command line, and the EFFECTIVE value is what prints as `floor=`. One readable
# file is the smallest population over which this check means anything; zero is
# DID-NOT-RUN.
DEFAULT_FLOOR = 1

SCHEMA = "canonkit/check-16/1"

HERE = os.path.dirname(os.path.abspath(__file__))

# `tools/` in this repository, `<artifact>/` in a vendored copy. ONE expression
# for both layouts: the checks package always sits one directory below the core.
CORE_ROOT = os.path.dirname(HERE)

# THE DECLARATION. Machine-readable and committed, so the needle set is
# reviewable and the scan is reproducible from the artifact alone.
DECLARATION_RELATIVE = os.path.join("results", "retractions.json")

DECLARATION_SCHEMA_PREFIX = "canonkit/retractions/"

# THE ADJUDICATION RADIUS, in lines either side of a hit. Twelve is the sweep's
# own figure, adopted rather than re-invented: it is what a withdrawal block and
# the note under it span in the documents this was measured on. It is
# overridable so a future artifact with a different house style can widen it
# WITHOUT the widening being invisible -- the effective value prints in the note.
DEFAULT_RADIUS = 12
RADIUS_KEY = "CHECK-16:radius"

# THE WITHDRAWAL MARKERS. A declared, committed list kept HERE beside the check
# so it is reviewable rather than magic, and FIXED BEFORE any scan is run: a cue
# set adjusted until the count reads zero is measuring the adjuster.
#
# WIDENING THIS LIST WEAKENS THE CHECK. Every term added is one more way for a
# live assertion to be filed as a record of a withdrawal, so a term earns its
# place by NAMING A WITHDRAWAL and never by being a word that often appears
# nearby.
FROZEN_MARKERS = (
    ("retract", "the plainest form: 'retracted', 'retraction'"),
    ("withdraw", "'withdraw', 'withdrawn', 'withdrawal'"),
    ("superseded", "names a figure that a later reading replaced"),
    ("unvalidated", "the sweep's own word for a figure that cannot be relied on"),
    ("no longer", "'no longer claimed', 'no longer holds'"),
)

# `frozen` WAS A SEVENTH MARKER AND IT WAS REMOVED, which is the opposite of
# the usual direction and is the reason it is recorded rather than deleted.
#
# It matched the anchor comment `<!-- artifact:frozen:begin -->` itself, so any
# hit within the RADIUS of a frozen anchor was frozen by the MARKER rule -- and
# that quietly defeated the region's own pairing rule, because a hit five lines
# under a STRAY, unclosed `begin` came out frozen anyway. The region mechanism
# below answers the same question properly: explicitly, paired, and counted. Two
# mechanisms for one question, one of them weaker, is how the weaker one ends up
# deciding. Measured: it also made the region's count read 0 while the region
# was doing the work, which is a count that cannot be reviewed.

# THE DECLARED FROZEN REGION, and it is not a second mechanism -- it is the one
# CHECK-01 already uses, with the same anchor and the same pairing rule
# (the anchor-token rule: the anchor token is `artifact:`, paired begin/end only). Two
# checks disagreeing about what a frozen region IS would be a drift nobody sees
# from a green run, so the predicate below is copied from check_01.py and
# tools/tests/test_check_16.py pins the two implementations to agree.
#
# WHY A REGION IS NEEDED AT ALL, MEASURED RATHER THAN ANTICIPATED. The marker
# rule is a RADIUS, and a whole-document historical record does not fit inside
# one: a file whose title and opening paragraph say it is superseded carries its
# adjudication at the TOP and its figures thirty lines down. Measured on a real
# artifact, that produced three findings against a document doing exactly what
# it was kept to do. The alternatives were both worse -- widening the radius
# until the count reads zero is measuring the adjuster, and excluding the file
# by NAME is the move the sweep this check is built on explicitly refuses, on
# the grounds that a document which gets immunity from its name is the one place
# a live claim can hide.
#
# So the author DECLARES the region, in the document, with a paired marker a
# reader can see, and the count of hits frozen that way PRINTS separately from
# the count frozen by a nearby marker. An adjudication nobody can count is an
# exclusion list wearing a better name.
FROZEN_ANCHOR = "artifact:frozen"
FROZEN_BEGIN_RE = re.compile(r"<!--\s*%s:begin\s*-->" % FROZEN_ANCHOR)
FROZEN_END_RE = re.compile(r"<!--\s*%s:end\s*-->" % FROZEN_ANCHOR)

# File extensions walked. Anything else is listed with a reason and counted as
# not-examined, never dropped.
TEXT_SUFFIXES = (
    ".py", ".md", ".json", ".yml", ".yaml", ".txt", ".toml", ".cfg", ".sh",
    ".js", ".ini", ".sql", ".log", ".csv", ".html",
)
TEXT_STEMS = ("Dockerfile",)

# Directories never walked, each because it holds no authored text. NAMED
# `PRUNED_` rather than with the word canonkit declares BANNED_VERDICT: that
# word was retired from this toolkit's vocabulary the day before this module was
# written, and a new module re-seeding it in a constant name is exactly how a
# retired spelling comes back. The directories are counted and given a reason in
# `not_examined`, so pruning them is visible rather than silent.
PRUNED_DIRS = ("__pycache__", ".pytest_cache", ".venv", "node_modules",
               ".mypy_cache", ".ruff_cache")

# `.git` is named separately because it is not a cache -- it is the object store,
# and walking it would make every historical revision of every retracted figure
# a hit. The count still prints; it is an exclusion with a reason, not a silence.
GIT_DIR = ".git"

MAX_LISTED_FINDINGS = 20

BARE_NUMERIC_RE = re.compile(r"^\d+(?:[.,]\d+)?$")

DIGITS = "0123456789"

# A decimal separator only EXTENDS a number when a digit sits on its far side.
# MEASURED, on this check's own committed fixture, before it shipped: treating a
# bare `,` or `.` as adjacency classified the JSON line `"value": 4.321,` as a
# false positive, because of the comma that separates it from the next key. That
# is the check going BLIND to a withdrawn figure sitting in a machine record --
# the single most likely place for one to survive -- and it reads as a clean
# adjudication rather than as a miss.
DECIMAL_SEPARATORS = ".,"


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

    PREFERS AN ALREADY-LOADED COPY, for the reason every sibling module states:
    loading this file's sibling __init__.py by path a second time would mint a
    SECOND CheckResult class, and a runner comparing against its own would
    reject a result that is structurally identical.
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
# The declaration
# ---------------------------------------------------------------------------


def read_declaration(artifact):
    """Parse results/retractions.json. Raises CheckRefusal -- every one is a 2."""
    path = os.path.join(artifact, DECLARATION_RELATIVE)
    if not os.path.isfile(path):
        raise CheckRefusal(
            "no retraction declaration at %s, so this check has no needles and "
            "cannot look. An artifact that withdrew nothing still declares that "
            "it withdrew nothing -- a clean scan over an artifact nobody "
            "reviewed is a sentence, not a measurement. REPAIR: write %s "
            "carrying a reviewed_on date and `\"retracted\": []`."
            % (path, DECLARATION_RELATIVE.replace(os.sep, "/")))
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            payload = json.loads(handle.read())
    except (OSError, ValueError) as error:
        raise CheckRefusal(
            "%s could not be read as JSON: %s. REPAIR: fix the declaration; a "
            "malformed one is a check that could not look, never a clean one."
            % (path, error))
    if not isinstance(payload, dict):
        raise CheckRefusal(
            "%s is not a JSON object, so it declares nothing." % path)
    if not isinstance(payload.get("retracted"), list):
        raise CheckRefusal(
            "%s carries no `retracted` list. Its ABSENCE is not an empty list: "
            "one says nothing was withdrawn, the other says nobody wrote the "
            "key, and a check cannot tell them apart from a missing field. "
            "REPAIR: add `\"retracted\": []` if nothing was withdrawn." % path)
    return payload


def declaration_findings(payload, path):
    """Well-formedness findings over the declaration itself.

    These are FINDINGS and not refusals: the file was read, so the check looked.
    A declaration with no review date is the free-pass this check would
    otherwise hand out for shipping `{"retracted": []}` and never reading it.
    """
    findings = []
    reviewed = payload.get("reviewed_on")
    if not isinstance(reviewed, str) or not reviewed.strip():
        findings.append(finding(
            "declaration:no-reviewed-on", path,
            "the declaration carries no `reviewed_on` date. Without one, an "
            "empty `retracted` list is indistinguishable from a file nobody "
            "read"))
    schema = payload.get("schema")
    if not isinstance(schema, str) or \
            not schema.startswith(DECLARATION_SCHEMA_PREFIX):
        findings.append(finding(
            "declaration:no-schema", path,
            "the declaration carries no `schema` beginning %r, so a later "
            "reader cannot tell which shape it is"
            % DECLARATION_SCHEMA_PREFIX))
    for index, entry in enumerate(payload.get("retracted") or []):
        where = "%s[%d]" % (path, index)
        if not isinstance(entry, dict):
            findings.append(finding(
                "declaration:not-an-object", where,
                "a retracted entry is %r rather than an object" % type(entry)))
            continue
        if not str(entry.get("id") or "").strip():
            findings.append(finding(
                "declaration:no-id", where, "a retracted entry carries no `id`"))
        if not str(entry.get("withdrawn_on") or "").strip():
            findings.append(finding(
                "declaration:no-withdrawn-on", where,
                "retracted entry %r carries no `withdrawn_on` date"
                % entry.get("id")))
        if not str(entry.get("why") or "").strip():
            findings.append(finding(
                "declaration:no-reason", where,
                "retracted entry %r carries no `why`. A retraction with no "
                "stated reason cannot be reviewed" % entry.get("id")))
        needles = entry.get("needles")
        if not isinstance(needles, list) or not needles:
            findings.append(finding(
                "declaration:no-needles", where,
                "retracted entry %r declares no needles, so nothing hunts it "
                "and its presence in this list is decoration"
                % entry.get("id")))
    return findings


def needle_set(payload):
    """[(retraction id, needle text, context terms, bare-numeric?)] -- one row per needle.

    A figure has more than one spelling, and a needle that knows only one of
    them reports a zero that means nothing. The declaration therefore carries
    every form a figure could have been written in, and this flattens them.
    """
    rows = []
    for entry in payload.get("retracted") or []:
        if not isinstance(entry, dict):
            continue
        rid = str(entry.get("id") or "")
        context = [str(term) for term in (entry.get("context_terms") or [])
                   if str(term).strip()]
        for needle in entry.get("needles") or []:
            if isinstance(needle, dict):
                text = str(needle.get("needle") or "")
                terms = [str(t) for t in (needle.get("context_terms") or context)
                         if str(t).strip()]
            else:
                text = str(needle)
                terms = context
            text = text.strip()
            if not text:
                continue
            rows.append((rid, text, tuple(terms),
                         bool(BARE_NUMERIC_RE.match(text))))
    return rows


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------


def is_text_candidate(name):
    return name.endswith(TEXT_SUFFIXES) or any(
        name.startswith(stem) for stem in TEXT_STEMS)


def walk(artifact):
    """(examined, not_examined). Two lists, both returned, neither implied.

    `examined` is [(relative path, text)]. `not_examined` is
    [(relative path, reason)] -- every input this check did not read, with the
    reason beside it, because an excluded input with no count and no reason is
    an input silently dropped.
    """
    examined, not_examined = [], []
    for base, dirs, names in os.walk(artifact):
        pruned = [d for d in dirs if d == GIT_DIR or d in PRUNED_DIRS]
        dirs[:] = [d for d in dirs if d not in pruned]
        for directory in sorted(pruned):
            relative = os.path.relpath(
                os.path.join(base, directory), artifact).replace(os.sep, "/")
            not_examined.append((
                relative + "/",
                "the object store, not authored text" if directory == GIT_DIR
                else "a generated cache, not authored text"))
        for name in sorted(names):
            path = os.path.join(base, name)
            relative = os.path.relpath(path, artifact).replace(os.sep, "/")
            if not is_text_candidate(name):
                not_examined.append((relative, "not a text file this check reads"))
                continue
            try:
                with open(path, "r", encoding="utf-8", newline="") as handle:
                    examined.append((relative, handle.read()))
            except (OSError, UnicodeDecodeError) as error:
                not_examined.append((relative, "unreadable as UTF-8: %s" % error))
    return examined, not_examined


# ---------------------------------------------------------------------------
# The four arms
# ---------------------------------------------------------------------------


def digit_adjacent(line, start, end):
    """True when a match sits inside a longer number.

    The measured case, with the invented values this file uses throughout for
    the reason its module docstring states: needle `77.7` against
    `"rps": 6377.7`. The character before the match is `3`, so the match is the
    TAIL of a longer number and is not the figure at all.

    A DECIMAL SEPARATOR ONLY COUNTS WHEN A DIGIT SITS ON ITS FAR SIDE, and that
    conjunct was added after measuring what its absence did: `"value": 4.321,`
    in a machine record classified FALSE-POSITIVE on the trailing comma, so the
    check went blind to a withdrawn figure in exactly the file most likely to
    still carry one -- and printed a clean adjudication while doing it.
    """
    def at(index):
        """The character at `index`, or None outside the line.

        NONE RATHER THAN THE EMPTY STRING, and that is not a style choice. This
        function used `""` for "off the end of the line" and tested membership
        with `ch in DIGITS` -- and `"" in "0123456789"` is True in Python, so
        EVERY match touching a line boundary was classified FALSE-POSITIVE. A
        withdrawn figure on its own line, or at the end of one, was invisible to
        this check and the report said it had been adjudicated. Measured on this
        check's own fixture before it shipped, on the line `"value": 4.321,`.
        """
        if 0 <= index < len(line):
            return line[index]
        return None

    def is_digit(ch):
        return ch is not None and ch in DIGITS

    def is_separator(ch):
        return ch is not None and ch in DECIMAL_SEPARATORS

    head = is_digit(at(start - 1)) or (is_separator(at(start - 1))
                                       and is_digit(at(start - 2)))
    tail = is_digit(at(end)) or (is_separator(at(end))
                                 and is_digit(at(end + 1)))
    return head or tail


def window(lines, index, radius):
    low = max(0, index - radius)
    high = min(len(lines), index + radius + 1)
    return "\n".join(lines[low:high]).lower()


def frozen_lines(text):
    """The 1-based line numbers inside a paired `artifact:frozen` region.

    COPIED FROM check_01.py, including its rule about the unpaired case: an
    UNCLOSED begin marker freezes NOTHING. The unpaired region is ignored rather
    than silently swallowing the rest of the document, which is the direction
    that keeps an error loud instead of quiet -- and it is the direction that
    matters here, because the quiet failure would be a stray `begin` marker
    freezing every live claim below it.
    """
    inside = set()
    opened = None
    for index, line in enumerate(text.split("\n")):
        if opened is None:
            if FROZEN_BEGIN_RE.search(line):
                opened = index + 1
            continue
        if FROZEN_END_RE.search(line):
            inside.update(range(opened, index + 2))
            opened = None
    return inside


def classify(line, start, end, lines, index, radius, bare_numeric, terms,
             in_frozen_region=False):
    """(arm, why). The four arms, in order, and never a fifth."""
    if bare_numeric and digit_adjacent(line, start, end):
        return ("FALSE-POSITIVE",
                "a bare-numeric needle inside a longer number, so it is not "
                "the figure")
    near = window(lines, index, radius)
    if terms and not any(term.lower() in near for term in terms):
        return ("FALSE-POSITIVE",
                "a word-form needle with none of its declared context terms "
                "within the radius, so it is ordinary English about something "
                "else")
    for marker, _ in FROZEN_MARKERS:
        if marker in near:
            return ("FROZEN",
                    "a withdrawal marker (%r) sits within the radius, so this "
                    "appearance is a record quoting what was withdrawn" % marker)
    if in_frozen_region:
        # ORDERED AFTER THE MARKER RULE ON PURPOSE. A hit that a nearby marker
        # already explains is reported that way, so the region's count stays
        # the count of hits that NEEDED it -- which is the number a reviewer
        # has to look at. A region absorbing hits the ordinary rule would have
        # caught makes itself look load-bearing and hides how wide it really is.
        return ("FROZEN",
                "inside a declared %s region, so the document adjudicates it "
                "as a historical quotation. The region is written in the file "
                "and paired; it is not inferred from the file's name"
                % FROZEN_ANCHOR)
    return ("LIVE",
            "no withdrawal marker within the radius and not inside a declared "
            "%s region, so this reads as a current assertion of a figure that "
            "was withdrawn" % FROZEN_ANCHOR)


def finding(kind, where, detail):
    return {"id": "%s:%s" % (kind, where), "kind": kind, "where": where,
            "detail": detail}


def scan_file(relative, text, needles, radius):
    """[(arm, retraction id, needle, line number, why)] for one file."""
    lines = text.splitlines()
    frozen = frozen_lines(text)
    hits = []
    for index, line in enumerate(lines):
        haystack = line.lower()
        in_region = (index + 1) in frozen
        for rid, needle, terms, bare in needles:
            lowered = needle.lower()
            start = haystack.find(lowered)
            while start != -1:
                end = start + len(lowered)
                arm, why = classify(line, start, end, lines, index, radius,
                                    bare, terms, in_frozen_region=in_region)
                hits.append((arm, rid, needle, index + 1, why))
                start = haystack.find(lowered, start + 1)
    return hits


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


def run(artifact, ctx=None):
    """Measure. Returns a CheckResult. DOES NOT PRINT -- the caller prints."""
    core = load_core()
    contract = load_contract()
    ctx = ctx if ctx is not None else contract.CheckContext()
    floor = ctx.floor_for(CHECK_ID, DEFAULT_FLOOR)
    overrides = getattr(ctx, "floor_overrides", None) or {}
    radius = overrides.get(RADIUS_KEY, DEFAULT_RADIUS)
    artifact = os.path.abspath(str(artifact))

    def refused(note):
        # THE COUNT TRAVELS ON THIS BRANCH TOO. Every check prints ONE line on
        # EVERY branch, carrying its count WITH its verdict; a DID-NOT-RUN that
        # does not say how much it examined is the shape that rule forbids.
        result = contract.CheckResult(
            check_id=CHECK_ID, code=core.EXIT_DID_NOT_RUN, found=0, checked=0,
            floor=floor, waived=0,
            note="%s files=0 retractions=0 needles=0 radius=%d"
                 % (note, radius))
        result.detail = {
            "artifact": artifact, "declaration": "", "reviewed_on": "",
            "retractions": 0, "needles": 0, "radius": radius,
            "files_checked": 0, "files_not_examined": [],
            "arms": {"LIVE": 0, "FROZEN": 0, "FALSE-POSITIVE": 0,
                     "UNCLASSIFIED": 0},
            "region_frozen": 0, "region_files": [],
            "hits": [], "findings": []}
        return result

    if not os.path.isdir(artifact):
        return refused("%s is not a directory" % artifact)

    declaration_path = os.path.join(artifact, DECLARATION_RELATIVE)
    try:
        payload = read_declaration(artifact)
    except CheckRefusal as refusal:
        return refused(str(refusal))

    relative_declaration = DECLARATION_RELATIVE.replace(os.sep, "/")
    findings = declaration_findings(payload, relative_declaration)
    needles = needle_set(payload)

    examined, not_examined = walk(artifact)
    checked = len(examined)

    arms = {"LIVE": 0, "FROZEN": 0, "FALSE-POSITIVE": 0, "UNCLASSIFIED": 0}
    hits = []
    # COUNTED SEPARATELY, and named by file. A declared region is an
    # adjudication a human wrote, and an adjudication nobody can count is an
    # exclusion list wearing a better name. This is the number a reviewer opens
    # the files for.
    region_frozen = 0
    region_files = {}
    for relative, text in examined:
        for arm, rid, needle, lineno, why in scan_file(relative, text, needles,
                                                       radius):
            arms[arm] = arms.get(arm, 0) + 1
            if arm == "FROZEN" and FROZEN_ANCHOR in why:
                region_frozen += 1
                region_files[relative] = region_files.get(relative, 0) + 1
            hits.append({"arm": arm, "retraction": rid, "needle": needle,
                         "file": relative, "line": lineno, "why": why})
            if arm in ("LIVE", "UNCLASSIFIED"):
                findings.append(finding(
                    "retraction-%s" % arm.lower(),
                    "%s:%d" % (relative, lineno),
                    "%r (withdrawn as %r) -- %s" % (needle, rid, why)))

    suppressed = waiver_ids(getattr(ctx, "waivers", None))
    kept = [item for item in findings if item["id"] not in suppressed]
    waived = len(findings) - len(kept)
    found = len(kept)

    if checked == 0:
        code = core.EXIT_DID_NOT_RUN
    elif checked < floor:
        code = core.EXIT_DID_NOT_RUN
    elif found:
        code = core.EXIT_FINDING
    else:
        code = core.EXIT_PASS

    note = ("retractions=%d needles=%d radius=%d live=%d frozen=%d "
            "(region=%d in %d file(s)) false-positive=%d unclassified=%d"
            % (len(payload.get("retracted") or []), len(needles), radius,
               arms["LIVE"], arms["FROZEN"], region_frozen, len(region_files),
               arms["FALSE-POSITIVE"], arms["UNCLASSIFIED"]))

    result = contract.CheckResult(
        check_id=CHECK_ID, code=code, found=found, checked=checked, floor=floor,
        waived=waived, not_examined=len(not_examined),
        listed=checked + len(not_examined), note=note,
        finding_ids=sorted({item["id"] for item in kept}))
    result.detail = {
        "artifact": artifact,
        "declaration": relative_declaration,
        "declaration_present": os.path.isfile(declaration_path),
        "reviewed_on": str(payload.get("reviewed_on") or ""),
        "retractions": len(payload.get("retracted") or []),
        "needles": len(needles),
        "radius": radius,
        "files_checked": checked,
        "files_not_examined": [{"path": rel, "reason": why}
                               for rel, why in not_examined],
        "arms": arms,
        "region_frozen": region_frozen,
        "region_files": [{"path": path, "hits": count}
                         for path, count in sorted(region_files.items())],
        "hits": hits,
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
        "declaration": detail.get("declaration", ""),
        "declaration_present": detail.get("declaration_present", False),
        "reviewed_on": detail.get("reviewed_on", ""),
        "retractions": detail.get("retractions", 0),
        "needles": detail.get("needles", 0),
        "radius": detail.get("radius", DEFAULT_RADIUS),
        "files_checked": detail.get("files_checked", 0),
        "not_examined_entries": list(detail.get("files_not_examined", [])),
        "arms": dict(detail.get("arms", {})),
        "region_frozen": detail.get("region_frozen", 0),
        "region_files": list(detail.get("region_files", [])),
        "hits": list(detail.get("hits", [])),
        "findings": detail.get("findings", []),
        "artifact": detail.get("artifact", ""),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_16",
        description="CHECK-16: fails when a figure this artifact declared "
                    "retracted is still being asserted somewhere in it.")
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
    parser.add_argument("--radius", type=int, default=None,
                        help="override the adjudication radius, in lines either "
                             "side of a hit. The OVERRIDDEN value prints in the "
                             "note, so a widening cannot be invisible.")
    args = parser.parse_args(argv)

    core = load_core()
    contract = load_contract()

    overrides = {}
    if args.min_population is not None:
        overrides[CHECK_ID] = args.min_population
    if args.radius is not None:
        overrides[RADIUS_KEY] = args.radius
    ctx = contract.CheckContext(floor_overrides=overrides)

    result = run(args.artifact, ctx)

    core.report(CHECK_ID, result.code == core.EXIT_PASS, result.found,
                result.checked, result.floor, waived=result.waived,
                note=result.note, not_examined=result.not_examined,
                listed=result.listed)

    if result.checked and result.checked < result.floor:
        print("  DEMOTED to DID-NOT-RUN: population %d is below the effective "
              "floor %d." % (result.checked, result.floor))

    detail = getattr(result, "detail", {}) or {}
    for item in detail.get("findings", [])[:MAX_LISTED_FINDINGS]:
        print("  %-24s %s: %s" % (item["kind"], item["where"], item["detail"]))
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
