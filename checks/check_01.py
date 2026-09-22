"""CHECK-01 -- a figure that appears without its population.

    python check_01.py <artifact> [--report FILE] [--min-population N]

the project requirements document states the check verbatim: "Fails when a figure appears without
its population, reporting the COUNT OF UNCLASSIFIED NUMERALS rather than a bare
verdict." Both halves are load-bearing and this module does both.

WHAT IT LOOKS AT, AND WHY IT IS TWO LIMBS RATHER THAN ONE
---------------------------------------------------------
1. THE RECORD. Every figure in results/figures.json must carry an integer
   `population` of at least 1. `population: 1` is legal and renders --
   peak VRAM and free VRAM at run start are legitimately single-sample
   population facts. Missing, non-integer, or zero is the 0/0 pass wearing a
   figure's clothes, and the offending KEY is named: a bare "a figure is missing
   its population" makes the operator search.

   render.py already REFUSES to render such a figure. That is prevention, and it
   only covers documents this tooling wrote. This limb is the DETECTION half,
   and it is not redundant: a README can be hand-written, hand-edited, or
   inherited from before the rule existed.

2. THE DOCUMENT. canonkit.classify_numerals() runs BOTH rules over README.md
   (and results/RESULTS.md when it exists) -- the shape allow-list as primary
   plus the value check beside it (a design rule and a design rule share the one implementation).
   Deny-by-value alone misses a hand-typed number that happens not to match a
   figure; shape alone misses a real figure value typed in a PERMITTED shape.
   `fixtures/broken-artifacts/broken-figure-in-prose` is exactly the second
   case, measured: its leaked value classifies as a PORT and a shape-only rule
   reports that document clean.

WHY A RENDERED HOLE IS MASKED BEFORE ANY OF THAT, which is the one thing here a
reader is most likely to want explained. render.py writes a figure into a
document as

    <!--artifact:key:median_latency_ms-->12.5<!--/artifact:key-->

and classify_numerals, which knows only about `{{figures.*}}` references, reads
that `12.5` as an unclassified numeral AND as a value leak. MEASURED, not
supposed: a correctly rendered artifact scores unclassified=1 value_leaks=1 per
figure if the holes are not masked first. Un-masked, this check would fail every
correctly rendered artifact in the program, which is the checker-nobody-reads
failure a design rule exists to prevent. The mask is therefore not a convenience; it is
what makes "a figure lives inside a paired region" the thing being
enforced instead of the thing being punished.

WHY A QUOTED CANON BULLET IS MASKED TOO (an earlier plan FINDING A / open item 13). The
second mask, and the second thing a reader will want explained. CHECK-09
REQUIRES the canon bullet's text in the claim-under-test table VERBATIM, byte
for byte, with no normalization -- a paraphrase is exactly what it exists to
catch. MEASURED over the committed snapshot: ZERO of its 49 bullets have text
classify_numerals reads cleanly, because a canon bullet IS a metric claim and
metric claims carry numerals. So the two checks contradicted each other on
every artifact this programme will ever ship, and the contradiction was held by
an owner-authored committed waiver until an earlier plan removed it.

The repair is a CLASSIFICATION, not an exclusion (the conventions document section 4
forbids the exclusion-list shape outright): the text is accounted for because it
is a VERBATIM QUOTATION OF AN APPROVED CLAIM, resolvable against
canon-bullets.json -- the same corpus, read through the same loader, that
CHECK-09 resolves against. So it is keyed to the CITED BULLET rather than to the
claim region: a paraphrase is masked by nothing, a cell citing a bullet the
corpus does not carry is masked by nothing, and every numeral elsewhere in the
claim block is a claim about THIS measurement and stays a finding. The count of
findings the mask removed prints as `canon-text=`, beside the count of cells it
did and did not mask, so the exclusion is countable rather than invisible.

TWO FALSE POSITIVES CLOSED HERE RATHER THAN IN THE FROZEN CORE (G-1, G-2)
-------------------------------------------------------------------------
Both were raised against canonkit.classify_numerals by an earlier plan and both are
closed in THIS file, because the core's sha256 is asserted cross-repository by
tools/vendor.py and because the correct scope for both is a check that knows
which artifact it is looking at, which the core does not.

  G-1  A markdown ordered-list marker (`1.`, `2.`, `10)`) classifies as an
       unclassified numeral. MEASURED: three markers, three findings. A check
       that raises against the first author who writes a numbered list is a
       check people learn to ignore.

  G-2  A slug carrying a digit (`bp2-platform`) puts an unclassified numeral
       into a generated README title. NOT hypothetical for this program: the
       example-beta canon numbers its example projects BP-1..BP-5.

Both are re-classified STRUCTURALLY, never by text matching -- an earlier plan
measured what a text predicate costs here (`startswith("canonkit.")` matched the
FILENAME and produced 26 confident false findings):

  * an ordered-list marker is a bare integer whose line holds nothing but
    whitespace before it and a `.` or `)` plus a space after it. `12.5` at the
    start of a line is not a bare integer and is NOT re-classified.
  * an artifact-slug token is a token EQUAL to this artifact's own slug, taken
    from the figures record's `artifact` field and from the directory name. A
    figure value can never equal the slug, and the value rule runs over the same
    text regardless, so the overlap that catches a leak is untouched.

FOUR MORE CLASSES, AND THE MEASUREMENT THAT FORCED THEM (G-3 .. G-6)
---------------------------------------------------------------------
The first real artifact this check ever ran over scored `found=319 checked=10 of
10 unclassified=304 leaks=15`. Reading the 171 distinct (document, token) pairs
instead of the total is what produced this section: `p99` appears nineteen
times, `k6` six, the artifact's own `run_k6_sweep.py` three, and a retraction
record quotes the withdrawn numbers it exists to withdraw. NONE of those is a
figure appearing without its population, which is the whole of this check's
requirement -- and the only way to satisfy the rule as it stood was to misspell
a tool's name, rename a directory that four pinned inputs reference, and delete
the retraction records. A repair that damages the artifact to please the lint is
the delete-shaped fix, so the lint is what changed.

  G-3  percentile_label   `p50`, `p99`, `P95`. A percentile label names WHICH
                          order statistic, never its magnitude, so it can be
                          neither a figure typed into prose nor a number
                          back-solved from a canon percentage. Every latency
                          artifact in this programme reports them.
  G-4  tree_path          a token naming a file or directory that EXISTS in
                          this artifact. Derived by walking the tree, never a
                          committed word list, and a candidate must begin with
                          a LETTER -- so a token shaped like a measurement can
                          never be admitted by naming a file after it.
  G-5  fenced_block       a numeral inside a fenced code block. A fenced block
                          reproduces a command exactly; re-typing an argument,
                          an environment assignment or an image tag to please a
                          lint makes the documented command WRONG, which is the
                          dead-instruction defect the README rule exists to
                          prevent. INLINE code spans are deliberately NOT
                          included: a span is prose formatting, and a measured
                          latency inside backticks is exactly the un-rendered
                          figure a design rule forbids.
  G-7  calendar_month     an ISO-8601 year-month. The allow-list ALREADY
                          classifies a date; this is the same category at the
                          precision an engagement has. the project technology-stack document section 8(b)
                          makes an engagement's dates mandatory in every
                          published README, and inventing a day precision
                          nobody measured to satisfy a lint is the shape this
                          project refuses. It stops at month precision
                          deliberately: a bare `2024` is the same token shape
                          as `2000 requests`.
  G-6  frozen_quotation   a numeral inside a paired `artifact:frozen` region. A
                          retraction MUST quote the number it withdraws or it
                          records nothing, and this programme already keeps a
                          LIVE-vs-FROZEN classification for its banned-name
                          lint. The region is DECLARED in the document, using
                          the same paired mechanism as every other anchor, so
                          it is never inferred from wording.

WHY ALL SIX ARE SAFE, STATED ONCE BECAUSE IT IS ONE PROPERTY. Every
re-classification acts on canonkit's UNCLASSIFIED hits and on nothing else. The
VALUE rule runs over the same text independently and is never masked, so a
figures.json value typed inside a fenced block, inside a frozen region, or
beside a file name is STILL a leak. That is what keeps `artifact:frozen` honest
in particular: a frozen region may hold only numbers that are not current figure
values, so it cannot be used to smuggle a live measurement past the rule that it
must be rendered. Each class prints its own count.

A ONE-CHARACTER NEEDLE IS NOT A NEEDLE (handed over by an earlier plan by name)
---------------------------------------------------------------------------
Two of that artifact's fifteen leaks were the bare string `3`, produced from two
replicate-count figures whose value is 3.0 and whose `%g` rendering is one
character long. A single digit occurs constantly in ordinary prose, so such a
needle cannot DISCRIMINATE a leak from a coincidence -- and a check that cannot
discriminate is not a check. It was NOT repaired by changing the figures: three
replicates is the honest value, and tuning a measurement to please a checker is
the wrong direction. Needles below MIN_NEEDLE_LENGTH are dropped AFTER the core
has run, in this module rather than in the frozen core, and the count prints as
`short-needle=` so the exclusion is countable rather than invisible.

EXIT CODES (canonkit's contract, a design rule)
    0  every figure carries its population and no numeral is unaccounted for
    1  at least one finding. The check DID look.
    2  it could not look: no figures record, zero figures, no README, or a
       population BELOW THE EFFECTIVE FLOOR. Never 0 in those cases --
       conformance.py lifts a 2 to an artifact-level 1 without erasing it.

`found` COUNTS EVERY FINDING, not only the numerals. The plan's wording for this
module was "unclassified numerals plus value leaks"; an unpopulated figure is
also a finding and also drives the verdict, so excluding it would print
`found=0` beside a FAIL. A population line whose own number contradicts its
verdict is decoration. The three components are printed separately in the note
and carried separately in the --report JSON, so the requirement's "count of
unclassified numerals" is available on its own.

VENDORING. Enumerated into the vendored set by tools/vendor.py's check-module
glob and copied to <artifact>/checks/check_01.py, beside <artifact>/canonkit.py.
Run BY PATH under a bare module name; never `tools.checks.check_01`.
Stdlib only, ASCII only.

  The canon-bullet mask needs TWO members of that same set beside it:
  checks/check_09.py, whose claim-table reader this module loads rather than
  copies, and canon-bullets.json at the artifact root, which an earlier plan added.
  Both travel with this file by construction -- one glob, one declared tuple --
  and if either is absent the mask degrades to NO masking, with the reason
  printed. That direction is the safe one: an unresolvable quotation is
  UNCLASSIFIED and stays a finding, which is louder than today rather than
  quieter, and is the opposite of the inert-inside-a-vendored-copy defect.
"""

import argparse
import importlib.util
import json
import os
import re
import sys

CHECK_ID = "CHECK-01"

# a design rule: declared per-check IN CODE, overridable on the command line, and the
# EFFECTIVE floor is what prints. One figure is the smallest population over
# which this check means anything; zero is DID-NOT-RUN by a design rule.
DEFAULT_FLOOR = 1

SCHEMA = "canonkit/check-01/1"

HERE = os.path.dirname(os.path.abspath(__file__))

# `tools/` in this repository, `<artifact>/` in a vendored copy. ONE expression
# for both layouts: the checks package always sits one directory below the core.
CORE_ROOT = os.path.dirname(HERE)

FIGURES_RELATIVE = os.path.join("results", "figures.json")

# Both numbers are printed. README.md is REQUIRED -- it is the interviewer-facing
# document. results/RESULTS.md is scanned when present; its absence is not a
# defect and must not read as one.
SCANNED_DOCUMENTS = ("README.md", "results/RESULTS.md")
REQUIRED_DOCUMENT = "README.md"

MAX_LISTED_FINDINGS = 20

# The rendered form render.py writes. Matched WITH its markers so the key itself
# is masked too: a key such as `p95_ms` carries a digit, and the marker text
# `--artifact:key:p95_ms--` tokenizes to an unclassified numeral otherwise.
RENDERED_HOLE_RE = re.compile(
    r"<!--artifact:key:(?P<key>[A-Za-z0-9_.\[\]-]+)-->"
    r"(?P<value>.*?)"
    r"<!--/artifact:key-->", re.S)

# CommonMark: an ordered-list marker is 1-9 digits followed by `.` or `)` and
# then a space, a tab, or the end of the line.
ORDERED_LIST_MARKER_RE = re.compile(r"^\d{1,9}[.)](?:[ \t]|$)")
BARE_INT_RE = re.compile(r"^\d+$")

# The claim block's render anchor (the anchor-token rule: the design rule token is `artifact:`).
# RECORDED, and deliberately NOT keyed on -- see mask_claim_bullet_text. It is
# here so a reader who greps for the anchor lands on the paragraph explaining
# why this module does not use it.
CLAIM_ANCHOR = "artifact:claim"

# CHECK-09's module, loaded as a SIBLING rather than re-implemented. Both
# layouts put every check module in one directory: `tools/checks/` here,
# `<artifact>/checks/` in a vendored copy, because tools/vendor.py ships them
# through one glob.
CLAIM_READER_BASENAME = "check_09.py"

KIND_ORDERED_LIST = "ordered_list_marker"
KIND_ARTIFACT_SLUG = "artifact_slug"
KIND_PERCENTILE_LABEL = "percentile_label"
KIND_TREE_PATH = "tree_path"
KIND_FENCED_BLOCK = "fenced_block"
KIND_FROZEN_QUOTATION = "frozen_quotation"
KIND_CALENDAR_MONTH = "calendar_month"

# The seven re-classification kinds, declared as ONE tuple so the report, the
# counters and the note cannot drift apart by one name.
RECLASSIFIED_KINDS = (KIND_ORDERED_LIST, KIND_ARTIFACT_SLUG,
                      KIND_PERCENTILE_LABEL, KIND_TREE_PATH,
                      KIND_FENCED_BLOCK, KIND_FROZEN_QUOTATION,
                      KIND_CALENDAR_MONTH)

# G-7. An ISO-8601 year-month. The frozen core's own date rule already
# classifies `2024-06-01`, so this is the SAME category at the precision a
# engagement actually has. It stops at month precision deliberately: a bare
# `2024` is the same token shape as `2000 requests`, and admitting one would
# admit the other.
ISO_YEAR_MONTH_RE = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")

# G-3. `p` or `P` followed by one to three digits, and nothing else. Bounded
# deliberately: `p200000` is not a percentile, it is a number with a letter in
# front of it.
PERCENTILE_LABEL_RE = re.compile(r"^[pP]\d{1,3}$")

# G-4. A candidate name must BEGIN WITH A LETTER. That single condition is what
# stops the class from ever admitting a measurement: `1.363x` cannot become
# acceptable by creating a file called `1.363x`.
TREE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.+-]*$")

# Directories never walked for G-4 candidates: machine output and tooling, none
# of which an author cites by name in prose, and all of which are large.
TREE_WALK_PRUNED = (".git", "__pycache__", ".pytest_cache", "node_modules")

# A ceiling on the walk, so a check can never become a directory crawl. The
# number of names actually collected is reported.
TREE_WALK_MAX_ENTRIES = 20000

# G-5. A fence is three or more backticks or tildes at the start of a line,
# optionally indented and optionally carrying an info string.
FENCE_RE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[^`]*$")

# G-6. The paired frozen region, the same mechanism every other anchor uses.
FROZEN_ANCHOR = "artifact:frozen"
FROZEN_BEGIN_RE = re.compile(r"<!--\s*%s:begin\s*-->" % FROZEN_ANCHOR)
FROZEN_END_RE = re.compile(r"<!--\s*%s:end\s*-->" % FROZEN_ANCHOR)

# A value string shorter than this cannot discriminate a leak from a
# coincidence, so it is not used as a needle. Committed as a literal because a
# derived floor would follow the shortest value and stop checking.
MIN_NEEDLE_LENGTH = 2

FINDING_POPULATION = "population"
FINDING_NUMERAL = "numeral"
FINDING_LEAK = "value_leak"


class CheckRefusal(Exception):
    """The check could not look. Carries the note printed beside code 2."""


def load_core():
    """Load the frozen core BY PATH, as a sibling. Never `tools.canonkit`."""
    path = os.path.join(CORE_ROOT, "canonkit.py")
    spec = importlib.util.spec_from_file_location("frozen_core", path)
    if spec is None or spec.loader is None:
        raise ImportError("could not build an import spec for %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_contract():
    """The check-module contract (CheckResult, CheckContext).

    PREFERS AN ALREADY-LOADED COPY, and that is not an optimisation. A runner
    that imported the package holds one class object; loading this file's
    sibling __init__.py by path a second time would mint a SECOND CheckResult
    class, and a runner doing isinstance() against its own would reject a result
    that is structurally identical. The path load is the standalone fallback, so
    `python check_01.py <artifact>` works inside a vendored artifact where there
    is no package to import.
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


def mask_rendered_holes(text):
    """Blank every rendered hole, preserving offsets AND line numbers.

    Returns (masked_text, hole_count). Newlines survive the mask so every hit's
    reported line number is its line in the ORIGINAL document.
    """
    masked = list(text)
    holes = 0
    for match in RENDERED_HOLE_RE.finditer(text):
        holes += 1
        for index in range(match.start(), match.end()):
            if masked[index] != "\n":
                masked[index] = " "
    return "".join(masked), holes


# ---------------------------------------------------------------------------
# The canon bullet's own text (an earlier plan FINDING A / open item 13)
# ---------------------------------------------------------------------------


def load_claim_reader():
    """(module, reason). CHECK-09's claim-table reader, loaded BY PATH.

    NOT a convenience import, and the reason it is a load rather than a copy is
    the whole point. CHECK-09 decides which table is a claim table, which cell
    holds the bullet text, which spellings of a field label it accepts and how a
    bullet reference resolves to a compound key. If this module re-implemented
    any of that the two would drift, and the FIRST spelling CHECK-09 learned and
    this one did not would be a claim table CHECK-09 REQUIRES and CHECK-01
    reports as a leak -- the exact conflict this masking exists to close,
    silently re-created one label at a time.

    Loading by path under a bare module name is a design rule's mandated mechanism.

    A MISSING OR BROKEN reader degrades to NO MASKING, never to a refusal, and
    the sentence saying so travels into the note. That direction is the safe
    one: an unresolvable quotation is UNCLASSIFIED and stays a finding, which is
    louder than today rather than quieter. The broad catch is deliberate -- a
    defect in the vendored set must not be able to turn CHECK-01 itself into a
    traceback whose exit status reads as a finding about the artifact.
    """
    path = os.path.join(HERE, CLAIM_READER_BASENAME)
    if not os.path.isfile(path):
        return None, ("%s is not beside this module, so no claim table could be "
                      "read" % CLAIM_READER_BASENAME)
    spec = importlib.util.spec_from_file_location("claim_reader", path)
    if spec is None or spec.loader is None:
        return None, "could not build an import spec for %s" % path
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        return None, "%s could not be loaded (%s)" % (CLAIM_READER_BASENAME,
                                                      error)
    return module, None


def load_claim_snapshot(reader):
    """(snapshot, reason). The claim corpus CHECK-09 resolves against.

    The SAME source, read through the SAME loader, so a bullet the two modules
    disagree about is impossible by construction rather than by discipline.
    """
    if reader is None:
        return None, None
    try:
        return reader.load_snapshot(), None
    except (reader.CheckRefusal, OSError) as refusal:
        return None, str(refusal)


def claim_cell_span(reader, line, value):
    """(start, end) of a table row's SECOND cell value within `line`, or None.

    Computed from the row's own pipe positions rather than searched for, and
    then VERIFIED: the characters at the computed offsets must BE `value`. A
    span that does not hold what it claims to hold masks the wrong bytes, and a
    mask over the wrong bytes is a hole in the lint nobody would see.
    """
    match = reader.TABLE_ROW_RE.match(line)
    if match is None:
        return None
    cells = match.group("body").split("|")
    if len(cells) < 2:
        return None
    start = match.start("body") + len(cells[0]) + 1
    cell = cells[1]
    start += len(cell) - len(cell.lstrip(" \t"))
    end = start + len(value)
    if line[start:end] != value:
        return None
    return start, end


def claim_bullet_text_spans(reader, snapshot, text):
    """((line, start, end) per masked cell, count of cells left unmasked).

    KEYED TO THE CITED BULLET, never to the region. A cell is masked only when
    its bytes ARE the text of a bullet the SAME table cites, resolved through
    the snapshot. A paraphrase, a cell citing a bullet the corpus does not
    carry, and every numeral elsewhere in the claim block are all left alone and
    stay findings. That is what makes this a CLASSIFICATION -- the text is
    accounted for because it is a verbatim quotation of an approved claim --
    rather than the widened cue set the conventions document section 4 forbids. Nothing
    here is a committed list of strings to ignore: every masked byte is derived
    from the corpus, and a corpus that stops resolving masks NOTHING.

    THE TABLE IS FOUND STRUCTURALLY, through CHECK-09's own finder, and NOT
    through CLAIM_ANCHOR. templates/RESULTS-SKELETON.md puts the headline
    before/after table inside its `artifact:claim` region and leaves the
    claim-under-test table OUTSIDE it, further down the file. A mask keyed on
    the anchor would therefore leave RESULTS.md's bullet text a finding on every
    artifact this programme ships -- the same defect, relocated to the document
    that gets read second.
    """
    spans = []
    unmasked = 0
    lines = text.split("\n")
    for table in reader.find_claim_tables("", text):
        cell = table.fields.get(reader.F_TEXT)
        if cell is None:
            continue
        value, line_no = cell
        identifier = table.fields.get(reader.F_BULLET_ID)
        quoted = []
        for token in reader.split_id_tokens(identifier[0] if identifier else ""):
            resolution = reader.resolve_reference(token, snapshot)
            if resolution.resolved:
                quoted.append(snapshot.text_for(resolution.key))
        if not any(reader.texts_match(value, other) for other in quoted):
            unmasked += 1
            continue
        if not (0 < line_no <= len(lines)):
            unmasked += 1
            continue
        span = claim_cell_span(reader, lines[line_no - 1], value)
        if span is None:
            unmasked += 1
            continue
        spans.append((line_no, span[0], span[1]))
    return spans, unmasked


def mask_claim_bullet_text(text, spans):
    """Blank each span, preserving offsets AND line numbers.

    The same in-place shape as mask_rendered_holes, for the same reason: every
    remaining hit's reported line number stays its line in the ORIGINAL
    document, and the blanked text cannot change how a LATER numeral classifies
    (canonkit's version and port rules read the characters immediately before a
    token).
    """
    if not spans:
        return text
    lines = text.split("\n")
    for line_no, start, end in spans:
        line = lines[line_no - 1]
        lines[line_no - 1] = line[:start] + " " * (end - start) + line[end:]
    return "\n".join(lines)


def numeral_finding_count(core, text, figures, context):
    """How many numeral findings `text` yields -- the BEFORE side of the mask.

    Run only when there is something to mask, so a document with no claim table
    takes exactly the path it always took. The difference between this and the
    count after masking is what prints as `canon-text=`: not "cells I touched"
    but "findings this classification removed", which is the number a reader
    needs to judge whether the lint still covers anything.

    It applies EVERY filter the real pass applies, including the needle floor.
    A BEFORE side computed under different rules from the AFTER side would make
    `canon-text=` a difference between two things nobody measured.
    """
    report = core.classify_numerals(text, figures)
    raw = [hit for hit in report.hits if hit.kind == core.KIND_UNCLASSIFIED]
    remaining, _ = reclassify(raw, text, context)
    leaks, _ = drop_short_needles(report.leaks)
    return len(remaining) + len(leaks)


def artifact_slugs(artifact, record):
    """Every spelling of THIS artifact's own name, for the G-2 re-classification."""
    slugs = set()
    name = os.path.basename(os.path.abspath(str(artifact)))
    if name:
        slugs.add(name)
    declared = record.get("artifact") if isinstance(record, dict) else None
    if isinstance(declared, str) and declared.strip():
        slugs.add(declared.strip())
    return slugs


def is_ordered_list_marker(line_text, col, token):
    """G-1. STRUCTURAL: position on the line, not the token's text.

    True only when `token` is a bare integer, nothing but whitespace precedes it
    on its line, and a `.` or `)` plus a space follows it. `12.5` opening a line
    is not a bare integer and so is never re-classified here; a leaked value
    that happens to open a list item is still caught by the value rule, which
    runs over the same text independently.
    """
    if not BARE_INT_RE.match(token):
        return False
    if col < 0 or col > len(line_text):
        return False
    if line_text[:col].strip():
        return False
    return bool(ORDERED_LIST_MARKER_RE.match(line_text[col:]))


def is_artifact_slug(token, slugs):
    """G-2. The token IS this artifact's own name, not a claim about a measurement."""
    return token in slugs


def is_percentile_label(token):
    """G-3. A label naming WHICH order statistic. It carries no magnitude."""
    return bool(PERCENTILE_LABEL_RE.match(token))


def is_tree_path(token, names):
    """G-4. The token names a file or directory that EXISTS in this artifact."""
    return token in names


def is_calendar_month(token):
    """G-7. An ISO-8601 year-month -- a DATE, which the allow-list already has."""
    return bool(ISO_YEAR_MONTH_RE.match(token))


def tree_names(artifact):
    """Every file and directory NAME in the artifact, for the G-4 class.

    Walked rather than listed, so the class is derived from the artifact and
    cannot rot into a committed vocabulary. Only names BEGINNING WITH A LETTER
    are collected -- that one condition is what makes the class incapable of
    admitting a measurement -- and only names carrying a digit can ever match a
    numeral token anyway, so the set stays small.
    """
    names = set()
    entries = 0
    for root, dirnames, filenames in os.walk(str(artifact)):
        dirnames[:] = [name for name in dirnames
                       if name not in TREE_WALK_PRUNED]
        for name in list(dirnames) + list(filenames):
            entries += 1
            if entries > TREE_WALK_MAX_ENTRIES:
                return names
            if any(char.isdigit() for char in name) and TREE_NAME_RE.match(name):
                names.add(name)
    return names


def fenced_lines(text):
    """The 1-based line numbers inside a fenced code block, fences included.

    G-5. The fence's own line joins the set because an info string can carry a
    version. Nesting is not modelled: markdown does not nest fences of the same
    character, and a longer fence inside a shorter one is still inside it.
    """
    inside = set()
    open_fence = None
    for index, line in enumerate(text.split("\n")):
        match = FENCE_RE.match(line)
        if open_fence is None:
            if match is not None:
                open_fence = match.group("fence")[0]
                inside.add(index + 1)
            continue
        inside.add(index + 1)
        if match is not None and match.group("fence")[0] == open_fence:
            open_fence = None
    return inside


def frozen_lines(text):
    """The 1-based line numbers inside a paired `artifact:frozen` region.

    G-6. An UNCLOSED begin marker freezes NOTHING: the unpaired region is
    ignored rather than silently swallowing the rest of the document, which is
    the direction that keeps an error loud instead of quiet. render.py refuses
    an unpaired region outright, so the two agree on what a region is.
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


class DocumentContext(object):
    """What one document's re-classification needs, computed once per document."""

    def __init__(self, slugs, names, fenced, frozen):
        self.slugs = slugs
        self.names = names
        self.fenced = fenced
        self.frozen = frozen


def reclassify(hits, text, context):
    """Split canonkit's unclassified hits into real findings and the six false
    positives closed here. Returns (findings, counts_by_kind)."""
    lines = text.split("\n")
    remaining = []
    counts = dict((kind, 0) for kind in RECLASSIFIED_KINDS)
    for hit in hits:
        line_text = lines[hit.line - 1] if 0 < hit.line <= len(lines) else ""
        if is_ordered_list_marker(line_text, hit.col, hit.token):
            counts[KIND_ORDERED_LIST] += 1
            continue
        if is_artifact_slug(hit.token, context.slugs):
            counts[KIND_ARTIFACT_SLUG] += 1
            continue
        if is_percentile_label(hit.token):
            counts[KIND_PERCENTILE_LABEL] += 1
            continue
        if is_calendar_month(hit.token):
            counts[KIND_CALENDAR_MONTH] += 1
            continue
        if is_tree_path(hit.token, context.names):
            counts[KIND_TREE_PATH] += 1
            continue
        if hit.line in context.fenced:
            counts[KIND_FENCED_BLOCK] += 1
            continue
        if hit.line in context.frozen:
            counts[KIND_FROZEN_QUOTATION] += 1
            continue
        remaining.append(hit)
    return remaining, counts


def drop_short_needles(leaks):
    """(kept, dropped). A needle below the floor cannot discriminate.

    Applied AFTER the frozen core has run, because the core's sha256 is
    asserted cross-repository and the correct scope for this is a check that
    can print the count it removed.
    """
    kept = []
    dropped = 0
    for leak in leaks:
        if len(str(leak.token)) < MIN_NEEDLE_LENGTH:
            dropped += 1
            continue
        kept.append(leak)
    return kept, dropped


def figure_population_findings(figures):
    """Every figure whose denominator is missing, not an integer, or below one."""
    findings = []
    for key in sorted(figures):
        entry = figures[key]
        if not isinstance(entry, dict):
            findings.append((key, "the figure is %s, not an object"
                             % type(entry).__name__))
            continue
        if "population" not in entry:
            findings.append((key, "no `population` beside its "
                                  "`population_label`"))
            continue
        population = entry["population"]
        if isinstance(population, bool) or not isinstance(population, int):
            findings.append((key, "`population` is %r, which is %s and not an "
                                  "integer" % (population,
                                               type(population).__name__)))
            continue
        if population < 1:
            findings.append((key, "`population` is %d; a figure over zero "
                                  "inputs measured nothing (population 1 is "
                                  "legal, 0 is not)" % population))
    return findings


def normalize_figures(record):
    """The `figures` block as key -> figure dict, accepting both shapes in use."""
    figures = record.get("figures")
    if isinstance(figures, dict):
        return dict(figures)
    if isinstance(figures, list):
        normalized = {}
        for index, entry in enumerate(figures):
            if not isinstance(entry, dict) or not entry.get("id"):
                raise CheckRefusal(
                    "results/figures.json: figures[%d] is not an object "
                    "carrying an `id`. REPAIR: re-run derive.py, which writes "
                    "the keyed form." % index)
            normalized[str(entry["id"])] = entry
        return normalized
    raise CheckRefusal(
        "results/figures.json: `figures` is %s, expected an object or a list. "
        "REPAIR: re-run derive.py." % type(figures).__name__)


def load_record(artifact):
    """The figures record. Raises CheckRefusal -- every refusal is a code 2."""
    path = os.path.join(str(artifact), FIGURES_RELATIVE)
    if not os.path.isfile(path):
        raise CheckRefusal(
            "there is no results/figures.json under %s, so there are zero "
            "figures to examine. REPAIR: run derive.py before the checker."
            % artifact)
    try:
        with open(path, "rb") as handle:
            record = json.loads(handle.read().decode("utf-8"))
    except ValueError as error:
        raise CheckRefusal(
            "results/figures.json does not parse as JSON (%s). REPAIR: re-run "
            "derive.py rather than repairing it by hand." % error)
    except UnicodeDecodeError as error:
        raise CheckRefusal(
            "results/figures.json is not valid UTF-8 (%s). REPAIR: re-run "
            "derive.py." % error)
    if not isinstance(record, dict):
        raise CheckRefusal(
            "results/figures.json is not a JSON object. REPAIR: re-run derive.py.")
    return record


def read_documents(artifact):
    """(relative, text) for every scanned document present. Raises on a missing
    README, which is a DID-NOT-RUN rather than a pass over zero documents."""
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
                "%s is not valid UTF-8 (%s), so its numerals could not be "
                "read. REPAIR: re-write the document as UTF-8." % (relative, error))
    if not any(relative == REQUIRED_DOCUMENT for relative, _ in documents):
        raise CheckRefusal(
            "%s carries no %s, so there is no document to examine. REPAIR: "
            "generate the artifact from the skeleton."
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


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


def run(artifact, ctx=None):
    """Measure. Returns a CheckResult. DOES NOT PRINT -- the caller prints.

    The split is deliberate: conformance.py (an earlier plan) owns the run's one
    population line per check, and a module that printed as well would emit two.
    main() below prints, so a direct module run is not silent.
    """
    core = load_core()
    contract = load_contract()
    ctx = ctx if ctx is not None else contract.CheckContext()
    floor = ctx.floor_for(CHECK_ID, DEFAULT_FLOOR)
    artifact = os.path.abspath(str(artifact))

    def refused(note):
        result = contract.CheckResult(
            check_id=CHECK_ID, code=core.EXIT_DID_NOT_RUN, found=0, checked=0,
            floor=floor, waived=0, note=note)
        result.detail = {"documents_scanned": 0,
                         "documents_declared": len(SCANNED_DOCUMENTS),
                         "unclassified": 0, "value_leaks": 0,
                         "short_needle_leaks": 0, "tree_names": 0,
                         "unpopulated_figures": 0, "rendered_holes": 0,
                         "canon_bullet_text": 0, "claim_cells_masked": 0,
                         "claim_cells_unmasked": 0, "claim_corpus": None,
                         "reclassified": dict((kind, 0)
                                              for kind in RECLASSIFIED_KINDS),
                         "findings": [], "artifact": artifact}
        return result

    if not os.path.isdir(artifact):
        return refused("%s is not a directory" % artifact)

    try:
        record = load_record(artifact)
        figures = normalize_figures(record)
    except CheckRefusal as refusal:
        return refused(str(refusal))

    if not figures:
        return refused(
            "results/figures.json holds 0 figures. A check over zero figures "
            "cannot fail, so it must not be allowed to report success")

    try:
        documents = read_documents(artifact)
    except CheckRefusal as refusal:
        return refused(str(refusal))

    checked = len(figures)
    findings = []

    # Limb 1 -- the record.
    for key, why in figure_population_findings(figures):
        findings.append({"kind": FINDING_POPULATION,
                         "id": "figure:%s" % key,
                         "document": FIGURES_RELATIVE.replace(os.sep, "/"),
                         "line": 0, "token": key, "detail": why})

    # Limb 2 -- the documents.
    slugs = artifact_slugs(artifact, record)
    names = tree_names(artifact)
    unclassified = 0
    leaks = 0
    short_needles = 0
    holes = 0
    canon_text = 0
    cells_masked = 0
    cells_unmasked = 0
    reclassified = dict((kind, 0) for kind in RECLASSIFIED_KINDS)

    reader, reader_note = load_claim_reader()
    snapshot, snapshot_note = load_claim_snapshot(reader)
    corpus_note = reader_note or snapshot_note

    for relative, text in documents:
        masked, hole_count = mask_rendered_holes(text)
        holes += hole_count

        # Computed from the ORIGINAL text, whose line numbers both masks
        # preserve by construction, so a region's extent is never a function of
        # what was masked inside it.
        context = DocumentContext(slugs, names, fenced_lines(text),
                                  frozen_lines(text))

        spans = []
        if snapshot is not None:
            spans, unmasked = claim_bullet_text_spans(reader, snapshot, text)
            cells_unmasked += unmasked
        if spans:
            before = numeral_finding_count(core, masked, figures, context)
            masked = mask_claim_bullet_text(masked, spans)
            cells_masked += len(spans)

        numeral_report = core.classify_numerals(masked, figures)
        raw = [hit for hit in numeral_report.hits
               if hit.kind == core.KIND_UNCLASSIFIED]
        remaining, counts = reclassify(raw, masked, context)
        kept_leaks, dropped_needles = drop_short_needles(numeral_report.leaks)
        short_needles += dropped_needles
        for kind in reclassified:
            reclassified[kind] += counts[kind]
        for hit in remaining:
            unclassified += 1
            findings.append({"kind": FINDING_NUMERAL,
                             "id": "numeral:%s:%s" % (relative, hit.token),
                             "document": relative, "line": hit.line,
                             "token": hit.token,
                             "detail": "an unclassified numeral in %s"
                                       % ("un-rendered prose"
                                          if hit.kind == core.KIND_UNCLASSIFIED
                                          else hit.kind)})
        for leak in kept_leaks:
            leaks += 1
            findings.append({"kind": FINDING_LEAK,
                             "id": "leak:%s:%s" % (relative, leak.token),
                             "document": relative, "line": leak.line,
                             "token": leak.token,
                             "detail": "a figures.json VALUE typed outside "
                                       "every rendered hole"})
        if spans:
            canon_text += before - (len(remaining) + len(kept_leaks))

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

    # `canon-text` is COUNTED and carries its reason, which is the whole of
    # the conventions document section 2 property 3: a masked numeral that silently left
    # the denominator would be the same defect the mask exists to repair,
    # wearing a friendlier hat. `claim-cells` prints both sides -- quoted
    # verbatim and left alone -- so a corpus that stopped resolving shows up as
    # a rising unmasked count rather than as silence.
    note = ("unclassified=%d leaks=%d unpopulated=%d canon-text=%d "
            "claim-cells=%d of %d reclassified=%d short-needle=%d "
            "tree-names=%d documents=%d of %d"
            % (unclassified, leaks,
               sum(1 for f in kept if f["kind"] == FINDING_POPULATION),
               canon_text, cells_masked, cells_masked + cells_unmasked,
               sum(reclassified.values()), short_needles, len(names),
               len(documents), len(SCANNED_DOCUMENTS)))
    if corpus_note:
        note = "%s [canon corpus unread: %s]" % (note, corpus_note)

    result = contract.CheckResult(
        check_id=CHECK_ID, code=code, found=found, checked=checked, floor=floor,
        waived=waived, note=note,
        finding_ids=sorted({finding["id"] for finding in kept}))
    result.detail = {
        "documents_scanned": len(documents),
        "documents_declared": len(SCANNED_DOCUMENTS),
        "unclassified": unclassified,
        "value_leaks": leaks,
        "short_needle_leaks": short_needles,
        "tree_names": len(names),
        "unpopulated_figures": sum(1 for f in kept
                                   if f["kind"] == FINDING_POPULATION),
        "rendered_holes": holes,
        "canon_bullet_text": canon_text,
        "claim_cells_masked": cells_masked,
        "claim_cells_unmasked": cells_unmasked,
        "claim_corpus": corpus_note,
        "reclassified": reclassified,
        "findings": kept,
        "artifact": artifact,
    }
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_report(result, core):
    """The structured record. Its `schema_version` is what makes the
    anti-rot regression stable across wording changes."""
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
        "documents_scanned": detail.get("documents_scanned", 0),
        "documents_declared": detail.get("documents_declared",
                                         len(SCANNED_DOCUMENTS)),
        "unclassified": detail.get("unclassified", 0),
        "value_leaks": detail.get("value_leaks", 0),
        "short_needle_leaks": detail.get("short_needle_leaks", 0),
        "tree_names": detail.get("tree_names", 0),
        "unpopulated_figures": detail.get("unpopulated_figures", 0),
        "rendered_holes": detail.get("rendered_holes", 0),
        "canon_bullet_text": detail.get("canon_bullet_text", 0),
        "claim_cells_masked": detail.get("claim_cells_masked", 0),
        "claim_cells_unmasked": detail.get("claim_cells_unmasked", 0),
        "claim_corpus": detail.get("claim_corpus", None),
        "reclassified": detail.get("reclassified", {}),
        "findings": detail.get("findings", []),
        "artifact": detail.get("artifact", ""),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_01",
        description="CHECK-01: fails when a figure appears without its "
                    "population, reporting the count of unclassified numerals.")
    parser.add_argument("artifact", nargs="?", default=".",
                        help="the artifact directory (default: the current one)")
    parser.add_argument("--report", default=None,
                        help="write the structured report here. A file "
                             "rather than a pipe: a command piped into tail "
                             "returns the PIPE's exit status.")
    parser.add_argument("--min-population", type=int, default=None,
                        help="override the effective floor for this check "
                             ". The OVERRIDDEN value is what prints.")
    args = parser.parse_args(argv)

    core = load_core()
    contract = load_contract()

    overrides = {}
    if args.min_population is not None:
        overrides[CHECK_ID] = args.min_population
    ctx = contract.CheckContext(floor_overrides=overrides)

    result = run(args.artifact, ctx)

    # The population line, printed on EVERY branch.
    core.report(CHECK_ID, result.code == core.EXIT_PASS, result.found,
                result.checked, result.floor, waived=result.waived,
                note=result.note, not_examined=result.not_examined,
                listed=result.listed)

    # a design rule's demotion, said out loud rather than hidden in an exit code. The
    # line above reports what was found; this one reports that the population
    # was too small for that finding to mean anything.
    if result.checked and result.checked < result.floor:
        print("  DEMOTED to DID-NOT-RUN: population %d is below the effective "
              "floor %d." % (result.checked, result.floor))

    detail = getattr(result, "detail", {}) or {}
    for finding in detail.get("findings", [])[:MAX_LISTED_FINDINGS]:
        print("  %-12s %s line %d: %s -- %s"
              % (finding["kind"], finding["document"], finding["line"],
                 finding["token"], finding["detail"]))
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
