"""CHECK-09 -- the claim-under-test block, compound-keyed and compared as bytes.

    python check_09.py <artifact> [--report FILE] [--min-claims N] [--canon FILE]

the project requirements document states the check verbatim: it fails when the claim-under-test
block is missing its canon, its project, its bullet id, the bullet text
verbatim, the measured counterpart, or a verdict in
{SUPPORTS, SUPPORTS-WITH-REVISION, DOES-NOT-SUPPORT}.

WHY THIS CHECK EXISTS AT ALL. the project overview document's Key Decision a design rule -- "a measured
number that differs from the canon figure WINS and the published entry changes" --
is an intention until a machine can read the claim it applies to. A block naming
the canon, the project, the bullet, the bullet's text verbatim, the measured
counterpart and one of three verdicts is that record. Without it, "the
measurement wins" is a sentence in a planning document.

(Citation note: the context note also carries a design rule, about dual timestamps. The
a design rule meant here is the project overview document's Key Decision. Bare `a design rule` is ambiguous in this
repository and is qualified everywhere it appears in this file.)

WHAT THIS CHECK DOES NOT DO, STATED FIRST BECAUSE IT IS THE EASIEST THING TO GET
WRONG. It NEVER judges whether the verdict is RIGHT. Whether a measured figure
would mislead a reader of the bullet is a READING -- a project requirement's "similar" is
bounded by the bullet's own `metric_basis` -- and the validation note lists that
judgment as manual-only with the owner as its named human. A check that claimed
to decide it would be a check that cannot discriminate, dressed as rigour. This
module verifies a verdict EXISTS and is one of the three legal strings. Nothing
more.

THE CLAIM TABLE IS FOUND STRUCTURALLY, NOT BY AN ANCHOR, and that is measured
rather than stylistic. `templates/README-SKELETON.md` puts the claim table
INSIDE the `artifact:claim` region; `templates/RESULTS-SKELETON.md` puts a
DIFFERENT table (the headline before/after table) inside its `artifact:claim`
region and leaves the claim-under-test table OUTSIDE it, further down the file.
A check keyed on the anchor reads the wrong table in one of the two skeletons
this program ships. So a claim table is any contiguous two-column markdown table
whose first column carries the claim field names; the anchor is RECORDED beside
each table for the report and is never the thing being keyed on.

THE COMPARISON IS ON ENCODED BYTES AND NOTHING IS NORMALIZED.
A paraphrase is exactly what this check exists to catch, and normalization is
how a paraphrase passes. Case folding, whitespace collapsing, Unicode
normalization, dash folding and quote folding are all absent by construction:
`texts_match()` encodes both sides as UTF-8 and compares the bytes. Two strings
that render identically on screen -- NFC and NFD spellings of the same accented
word -- are a finding here, and that is correct: the snapshot holds what the
canon says, byte for byte.

EXACTLY ONE REMOVAL IS PERMITTED before the comparison, and it is delimiter
removal rather than normalization: the leading and trailing SPACES and TABS that
markdown table syntax requires around a cell's content. `| x |` and `|x|` are
the same cell. Nothing inside the cell is touched -- a doubled internal space, a
different dash, a different case, a trailing period are all findings.

THE CONSOLE IS NEVER THE JUDGE. The snapshot is read with an explicit
encoding="utf-8" and the comparison runs on `str.encode("utf-8")`. Every
diagnostic goes to the --report file. On this machine the console renders
correct UTF-8 as replacement characters, so an equal pair can look unequal and
an unequal pair can look equal; nothing in this module's control flow reads
stdout.

THE SIX BRANCHES, one finding kind each, so a report can be triaged without
re-reading the document:

  1 absent          a required part of the claim block is not there: no claim
                    table at all beside figures that DO name a canon bullet, or
                    a table carrying no usable Canon, Project or Bullet id row
  2 bare-bullet-id  the bullet reference is AMBIGUOUS -- written without its
                    canon prefix, resolving to nothing, or contradicted by the
                    Canon or Project row beside it. 17 of the 49 bullet ids
                    exist in BOTH canons, so a bare id is ambiguous in 35% of
                    cases and the message names BOTH candidate resolutions.
                    (The id string is narrower than the kind's meaning; the
                    unprefixed case is the common one and the one named.)
  3 unknown-key     a compound key that is not in the snapshot
  4 text-mismatch   the cell's bytes differ from the snapshot's `text`
  5 no-counterpart  a claim with no measured counterpart, or a figure carrying a
                    canon_value with NOTHING MEASURED beside it. The reverse is
                    NOT a finding -- see below.
  6 verdict         no verdict, or one outside the three legal strings

BRANCH 5 OVER THE FIGURES RECORD IS ONE-DIRECTIONAL, AND THAT IS MEASURED
--------------------------------------------------------------------------
It was symmetric once. canonkit.validate_figures REQUIRES a compound-keyed
`canon_bullet` on EVERY figure -- `None` is a schema violation -- so a
derivation that authors supporting evidence beside the headline (a
load-generator ceiling, a replicate count, a cache hit rate) has to name a
bullet on all of it. A symmetric branch 5 then demands that the CANON state a
number for every one of them, and no canon does.

MEASURED on the first real artifact this check ever ran over: ten figures, ten
`no-counterpart` findings, and the message's own repair -- "re-run derive.py" --
is a dead instruction, because no derivation can produce a value the canon does
not carry.

So the two directions get different answers, because they are different facts:

    canon_value present, value absent   FINDING. A comparison was declared and
                                        nothing was measured for it.
    value present, canon_value absent   NOT a finding. A measurement the canon
                                        states no number for is what supporting
                                        evidence IS. It is COUNTED and printed
                                        as `no-canon-value=` instead of being
                                        silently tolerated.

Nothing about which claim is supported moves: that comparison is the claim
TABLE's `Measured counterpart` row, which branch 5 still requires, and the
correction record CHECK-20 requires afterwards.

`BP-n` IS RESOLVED THROUGH THE SNAPSHOT, NEVER THROUGH A PATTERN. ROADMAP and
the project overview document call example-beta's paths BP-1..BP-5 while the canon stores them as
P1..P5, so `BP-2-B1` must reach `example-beta:P2-B1` and must never reach
`example-alpha:P2-B1`. The mapping is canon-specific; a pattern that stripped the
`B` would send an example-beta figure to an alpha bullet in every colliding
case. The index is built from the snapshot's own derived `display_ref` values.

THE THREE LEGAL VERDICTS ARE THIS MODULE'S OWN CONSTANT, and deliberately not
canonkit.SIMILARITY_VERDICTS. Those five (CONFIRMS, SUPPORTS,
SUPPORTS-WITH-REVISION, DOES-NOT-SUPPORT, REFRESH) are the FIGURE-level
`similar` vocabulary; the claim block's verdict set is three. Reusing one
constant for both would silently admit CONFIRMS and REFRESH into a claim block
-- the same shape of mistake as conflating a word floor with a population floor.

POPULATION (a design rule, C1). `checked` counts BULLET REFERENCES examined: every token
in a claim table's `Bullet id` row plus every figure carrying a `canon_bullet`.
`not_examined` counts figures examined that carry no `canon_bullet` -- they were
listed and looked at, and they had nothing for this check. Zero references is
DID-NOT-RUN (code 2), never a pass: an artifact whose figures name no canon
bullet and whose documents carry no claim table has not been checked, it has
been walked past.

  The one reading this module had to fix rather than inherit: "no claim block ->
  DID-NOT-RUN or finding depending on whether the artifact declares any figure
  at all" and "zero-input is a figures.json with no canon_bullet on any figure
  and no claim region -> code 2" only reconcile if "declares a figure" means
  "declares a figure CARRYING A CANON BULLET". That is the reading implemented,
  stated here rather than silently chosen.

EXIT CODES (canonkit's contract, a design rule)
    0  every reference resolves, every text matches, every verdict is legal
    1  at least one finding. The check DID look.
    2  it could not look: no document, or zero bullet references, or a
       population BELOW THE EFFECTIVE FLOOR. Never 0 in those cases --
       conformance.py lifts a 2 to an artifact-level 1 without erasing it.

VENDORING. Enumerated into the vendored set by tools/vendor.py's check-module
glob and copied to <artifact>/checks/check_09.py, beside <artifact>/canonkit.py
and <artifact>/canon-bullets.json. Run BY PATH under a bare module name; never
`tools.checks.check_09`. Stdlib only, ASCII only.
"""

import argparse
import importlib.util
import json
import os
import re
import sys

CHECK_ID = "CHECK-09"

# a design rule: declared per-check IN CODE, overridable on the command line, and the
# EFFECTIVE floor is what prints. One bullet reference is the smallest
# population over which this check means anything; zero is DID-NOT-RUN by a design rule.
DEFAULT_FLOOR = 1

SCHEMA = "canonkit/check-09/1"

HERE = os.path.dirname(os.path.abspath(__file__))

# `tools/` in this repository, `<artifact>/` in a vendored copy. ONE expression
# for both layouts: the checks package always sits one directory below the core.
CORE_ROOT = os.path.dirname(HERE)

SNAPSHOT_BASENAME = "canon-bullets.json"
FIGURES_RELATIVE = os.path.join("results", "figures.json")

SCANNED_DOCUMENTS = ("README.md", "results/RESULTS.md")
REQUIRED_DOCUMENT = "README.md"

MAX_LISTED_FINDINGS = 20

# THIS MODULE'S OWN CONSTANT. Not canonkit.SIMILARITY_VERDICTS -- see the
# docstring. Three, and only three.
LEGAL_VERDICTS = ("SUPPORTS", "SUPPORTS-WITH-REVISION", "DOES-NOT-SUPPORT")

# the anchor-token rule (an earlier plan): the anchor token is `artifact:`, never `backing:`. Recorded
# for the report only; the claim table is found structurally.
CLAIM_ANCHOR = "artifact:claim"
CLAIM_REGION_RE = re.compile(
    r"<!--\s*" + re.escape(CLAIM_ANCHOR) + r":begin\s*-->"
    r"(?P<body>.*?)"
    r"<!--\s*/?" + re.escape(CLAIM_ANCHOR) + r":end\s*-->", re.S)

TABLE_ROW_RE = re.compile(r"^[ \t]*\|(?P<body>.*)\|[ \t]*$")
SEPARATOR_CELL_RE = re.compile(r"^:?-{1,}:?$")

# canonkit's own shape for a compound key, restated here so a vendored copy does
# not depend on a private name in the frozen core.
COMPOUND_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_-]*$")

F_CANON = "canon"
F_PROJECT = "project"
F_BULLET_ID = "bullet_id"
F_TEXT = "bullet_text"
F_MEASURED = "measured_counterpart"
F_VERDICT = "verdict"

# Every spelling of a claim field this module accepts, normalized. Committed as
# a literal map rather than a fuzzy match: a field name a reader cannot find in
# this tuple is a field this check does not read, and that has to be visible.
FIELD_ALIASES = {
    "canon": F_CANON,
    "project": F_PROJECT,
    # The skeleton says EXAMPLE PROJECT from 2026-09-16. `P1` / `BP-2` are the
    # example projects of an engagement, and the owner's framing rule is that this
    # work is never presented as a personal project -- a table row labelled
    # "Project" in a published repository says the opposite of what the entry
    # says. Both spellings normalize to the same field so artifacts generated
    # before the rename keep validating: renaming a label is not a reason to
    # invalidate evidence that was already correct.
    "example project": F_PROJECT,
    "bullet id": F_BULLET_ID,
    "bullet ids": F_BULLET_ID,
    "bullet text, verbatim": F_TEXT,
    "bullet text verbatim": F_TEXT,
    "bullet text": F_TEXT,
    "measured counterpart": F_MEASURED,
    "measured": F_MEASURED,
    "verdict": F_VERDICT,
}

REQUIRED_CLAIM_FIELDS = (F_CANON, F_PROJECT, F_BULLET_ID, F_TEXT, F_MEASURED,
                         F_VERDICT)

KIND_ABSENT = "absent"
KIND_BARE_ID = "bare-bullet-id"
KIND_UNKNOWN_KEY = "unknown-key"
KIND_TEXT_MISMATCH = "text-mismatch"
KIND_NO_COUNTERPART = "no-counterpart"
KIND_VERDICT = "verdict"

FINDING_KINDS = (KIND_ABSENT, KIND_BARE_ID, KIND_UNKNOWN_KEY,
                 KIND_TEXT_MISMATCH, KIND_NO_COUNTERPART, KIND_VERDICT)


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

    PREFERS AN ALREADY-LOADED COPY for the reason check_01.py records: loading
    the sibling __init__.py by path a second time would mint a SECOND
    CheckResult class, and a runner doing isinstance() against its own would
    reject a structurally identical result.
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
# The snapshot
# ---------------------------------------------------------------------------


class Snapshot(object):
    """The committed canon snapshot, plus the three indexes this check needs.

    Every index is DERIVED from the snapshot's own records. None of the three
    is a pattern over an id string: `BP-2` -> example-beta is canon-specific
    knowledge that lives in the data, and a pattern would send an example-beta
    figure to an alpha bullet in all seventeen colliding cases.
    """

    def __init__(self, record):
        self.record = record
        self.bullets = record.get("bullets") or {}
        self.by_display = {}
        self.by_bare_id = {}
        self.display_prefix_canon = {}
        for key in sorted(self.bullets):
            entry = self.bullets[key]
            if not isinstance(entry, dict):
                continue
            bare = entry.get("id")
            if isinstance(bare, str) and bare:
                self.by_bare_id.setdefault(bare, []).append(key)
            display = entry.get("display_ref")
            if isinstance(display, str) and display:
                self.by_display[display] = key
                prefix = display.split("-B")[0]
                canon = entry.get("canon")
                if prefix and isinstance(canon, str):
                    self.display_prefix_canon.setdefault(prefix, set()).add(canon)

    def text_for(self, key):
        entry = self.bullets.get(key)
        return entry.get("text") if isinstance(entry, dict) else None

    @property
    def collision_ids(self):
        return sorted(bare for bare, keys in self.by_bare_id.items()
                      if len(keys) > 1)


def load_snapshot(path=None):
    """Read tools/canon-bullets.json with an EXPLICIT encoding.

    The snapshot is written with ensure_ascii=False, so the encoding is not
    incidental: a default-locale read on this machine is cp1252 and would
    either raise or silently mojibake the very bytes the comparison depends on.
    """
    if path is None:
        path = os.path.join(CORE_ROOT, SNAPSHOT_BASENAME)
    if not os.path.isfile(path):
        raise CheckRefusal(
            "the canon snapshot is not at %s, so no bullet text can be compared "
            "against anything. REPAIR: vendor %s beside the checks package."
            % (path, SNAPSHOT_BASENAME))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    except ValueError as error:
        raise CheckRefusal("%s does not parse as JSON (%s)" % (path, error))
    except UnicodeDecodeError as error:
        raise CheckRefusal("%s is not valid UTF-8 (%s)" % (path, error))
    if not isinstance(record, dict) or not isinstance(record.get("bullets"), dict):
        raise CheckRefusal("%s carries no `bullets` object" % path)
    if not record["bullets"]:
        raise CheckRefusal(
            "%s carries ZERO bullets. A comparison against an empty snapshot "
            "passes everything, which is the 0/0 pass wearing a snapshot's "
            "clothes." % path)
    return Snapshot(record)


# ---------------------------------------------------------------------------
# Pure helpers -- the markdown table
# ---------------------------------------------------------------------------


def split_table_row(line):
    """The cells of a markdown table row, or None when the line is not one.

    Returns cells with their surrounding pipes removed and NOTHING else done to
    them. The caller decides what may be stripped, because the answer differs
    between a FIELD NAME (a label) and the bullet TEXT (the compared bytes).
    """
    match = TABLE_ROW_RE.match(line)
    if match is None:
        return None
    return match.group("body").split("|")


def is_separator_row(cells):
    """`|---|---|`. Table syntax, never a claim field."""
    stripped = [cell.strip() for cell in cells]
    if not stripped or not any(stripped):
        return False
    return all(SEPARATOR_CELL_RE.match(cell) for cell in stripped if cell)


def normalize_field_name(cell):
    """A claim field LABEL, lowercased with its markdown emphasis removed.

    Applied ONLY to the first column. The bullet text in the second column goes
    through cell_value() instead, which removes table padding and nothing else.
    """
    text = cell.strip().strip("*_").strip()
    return " ".join(text.split()).lower()


def cell_value(cell):
    """A cell's content with the table's own padding removed, and NOTHING else.

    The ONE permitted removal before a byte comparison: markdown requires
    spaces around a cell's content, so `| x |` and `|x|` hold the same cell.
    Internal whitespace, case, dashes and quotes are untouched -- normalizing
    any of them is how a paraphrase passes.
    """
    return cell.strip(" \t")


def strip_id_delimiters(token):
    """Backticks and quotes around an IDENTIFIER, never around the bullet text.

    An id written `` `P2-B1` `` in prose is the same identifier; the backticks
    are markdown delimiters. This function is deliberately NOT applied to the
    bullet text cell, where a backtick would be a byte the canon does not have.
    """
    return token.strip().strip("`'\"").strip()


def split_id_tokens(value):
    """The bullet ids in a `Bullet id` cell. The skeleton's field is plural."""
    tokens = []
    for piece in re.split(r"[,\s]+", value or ""):
        token = strip_id_delimiters(piece)
        if token:
            tokens.append(token)
    return tokens


class ClaimTable(object):
    """One claim-under-test table found in one document."""

    def __init__(self, document, line, fields, inside_region):
        self.document = document
        self.line = line
        self.fields = fields          # normalized field -> (value, line)
        self.inside_region = inside_region

    def value(self, field):
        entry = self.fields.get(field)
        return entry[0] if entry else None

    def has(self, field):
        return field in self.fields


def region_spans(text):
    """(start, end) character offsets of every artifact:claim region."""
    return [(m.start(), m.end()) for m in CLAIM_REGION_RE.finditer(text)]


def find_claim_tables(document, text):
    """Every claim-under-test table in one document, found STRUCTURALLY.

    A claim table is a contiguous run of markdown table rows whose first column
    carries at least one of the claim field labels AND which names either the
    bullet id or the bullet text. The `artifact:claim` anchor is recorded but
    never keyed on -- RESULTS-SKELETON.md puts a different table inside its
    region, so an anchor-keyed check reads the wrong table there.
    """
    spans = region_spans(text)
    tables = []
    offset = 0
    block = []
    block_start_line = 0
    block_start_offset = 0
    lines = text.split("\n")

    def close(block, start_line, start_offset):
        if not block:
            return
        fields = {}
        for cells, line_no in block:
            if is_separator_row(cells):
                continue
            if len(cells) < 2:
                continue
            name = normalize_field_name(cells[0])
            field = FIELD_ALIASES.get(name)
            if field is None:
                continue
            if field in fields:
                continue
            fields[field] = (cell_value(cells[1]), line_no)
        if F_BULLET_ID not in fields and F_TEXT not in fields:
            return
        inside = any(start <= start_offset < end for start, end in spans)
        tables.append(ClaimTable(document, start_line, fields, inside))

    for index, line in enumerate(lines):
        line_no = index + 1
        cells = split_table_row(line)
        if cells is None:
            close(block, block_start_line, block_start_offset)
            block = []
        else:
            if not block:
                block_start_line = line_no
                block_start_offset = offset
            block.append((cells, line_no))
        offset += len(line) + 1
    close(block, block_start_line, block_start_offset)
    return tables


# ---------------------------------------------------------------------------
# Pure helpers -- the byte comparison
# ---------------------------------------------------------------------------


def texts_match(left, right):
    """True only when the two strings ENCODE to identical UTF-8 bytes.

    No casefold, no whitespace collapse, no unicodedata.normalize. An NFC and an
    NFD spelling of the same accented word render identically and are NOT equal
    here, which is the point: the snapshot holds what the canon says, byte for
    byte, and a check that normalized would pass the paraphrase it exists to
    catch.
    """
    if left is None or right is None:
        return False
    return left.encode("utf-8") == right.encode("utf-8")


def first_difference(left, right):
    """(byte offset, left byte, right byte) of the first difference, or None.

    Reported into the --report file so an author can find the character without
    trusting a console that renders correct UTF-8 as replacement characters.
    """
    if left is None or right is None:
        return None
    a = left.encode("utf-8")
    b = right.encode("utf-8")
    for index in range(min(len(a), len(b))):
        if a[index] != b[index]:
            return (index, a[index], b[index])
    if len(a) != len(b):
        index = min(len(a), len(b))
        return (index,
                a[index] if index < len(a) else None,
                b[index] if index < len(b) else None)
    return None


# ---------------------------------------------------------------------------
# Pure helpers -- reference resolution
# ---------------------------------------------------------------------------


RESOLVED_COMPOUND = "compound"
RESOLVED_DISPLAY = "display"
UNRESOLVED_BARE = "bare"
UNRESOLVED_UNKNOWN_KEY = "unknown-key"
UNRESOLVED_UNKNOWN = "unknown"


class Resolution(object):
    """What a bullet reference token resolved to, and how."""

    def __init__(self, token, key, how, candidates=None):
        self.token = token
        self.key = key
        self.how = how
        self.candidates = list(candidates or [])

    @property
    def resolved(self):
        return self.key is not None


def resolve_reference(token, snapshot):
    """Resolve ONE bullet reference token against the snapshot.

    Order matters and is stated: a compound key is authoritative; a display ref
    (`BP-2-B1`) is resolved through the snapshot's own derived mapping; anything
    else is unresolved, and a BARE id is reported as ambiguous rather than
    guessed. Guessing is the earlier step spoofing case: 17 of the 49 ids exist in
    both canons, so a coin flip is wrong 35% of the time and reads as a pass.
    """
    token = strip_id_delimiters(token)
    if COMPOUND_KEY_RE.match(token):
        if token in snapshot.bullets:
            return Resolution(token, token, RESOLVED_COMPOUND)
        return Resolution(token, None, UNRESOLVED_UNKNOWN_KEY)
    if token in snapshot.by_display:
        return Resolution(token, snapshot.by_display[token], RESOLVED_DISPLAY)
    candidates = snapshot.by_bare_id.get(token)
    if candidates:
        return Resolution(token, None, UNRESOLVED_BARE, candidates)
    return Resolution(token, None, UNRESOLVED_UNKNOWN)


# ---------------------------------------------------------------------------
# Enumeration -- the POPULATION. Never stubbed; a population a check did not
# really count is the 0/0 pass with a number printed beside it.
# ---------------------------------------------------------------------------


class Reference(object):
    """One bullet reference this check examined, and where it came from."""

    def __init__(self, source, token, text=None, figure_key=None,
                 canon_value=None, value=None, has_canon_value=False,
                 has_value=False):
        self.source = source
        self.token = token
        self.text = text
        self.figure_key = figure_key
        self.canon_value = canon_value
        self.value = value
        self.has_canon_value = has_canon_value
        self.has_value = has_value


def load_figures(artifact):
    """(figures dict, present). A missing figures record is not a refusal here:
    an artifact can carry a claim table and no figures yet."""
    path = os.path.join(str(artifact), FIGURES_RELATIVE)
    if not os.path.isfile(path):
        return {}, False
    try:
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    except (ValueError, UnicodeDecodeError) as error:
        raise CheckRefusal(
            "results/figures.json could not be read as UTF-8 JSON (%s). "
            "REPAIR: re-run derive.py rather than editing it by hand." % error)
    if not isinstance(record, dict):
        raise CheckRefusal("results/figures.json is not a JSON object")
    figures = record.get("figures")
    if isinstance(figures, list):
        keyed = {}
        for index, entry in enumerate(figures):
            if isinstance(entry, dict) and entry.get("id"):
                keyed[str(entry["id"])] = entry
            else:
                raise CheckRefusal(
                    "results/figures.json: figures[%d] carries no `id`" % index)
        return keyed, True
    if isinstance(figures, dict):
        return dict(figures), True
    return {}, True


def read_documents(artifact):
    """(relative, text) for every scanned document present.

    A missing README is a DID-NOT-RUN, not a pass over zero documents.
    """
    documents = []
    for relative in SCANNED_DOCUMENTS:
        path = os.path.join(str(artifact), relative.replace("/", os.sep))
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                documents.append((relative, handle.read()))
        except UnicodeDecodeError as error:
            raise CheckRefusal(
                "%s is not valid UTF-8 (%s), so its claim table could not be "
                "read. REPAIR: re-write the document as UTF-8."
                % (relative, error))
    if not any(relative == REQUIRED_DOCUMENT for relative, _ in documents):
        raise CheckRefusal(
            "%s carries no %s, so there is no claim block to examine. REPAIR: "
            "generate the artifact from the skeleton."
            % (artifact, REQUIRED_DOCUMENT))
    return documents


def enumerate_references(documents, figures):
    """(references, tables, figures_not_examined). The population, really counted.

    The third element was called `skipped_figures` until 2026-09-21, when that
    spelling was retired from this toolkit's vocabulary for the reason
    canonkit's BANNED_VERDICT declaration states. The NAME it returns into was
    re-keyed then; this sentence describing it was not, and a docstring naming a
    thing that no longer exists is the same defect as a test pinning a value
    that moved -- it reads as current and is not.
    """
    references = []
    tables = []
    for relative, text in documents:
        for table in find_claim_tables(relative, text):
            tables.append(table)
            for token in split_id_tokens(table.value(F_BULLET_ID)):
                references.append(Reference(source=relative, token=token,
                                            text=table.value(F_TEXT)))
    not_examined = 0
    for key in sorted(figures):
        entry = figures[key]
        if not isinstance(entry, dict):
            not_examined += 1
            continue
        token = entry.get("canon_bullet")
        if not isinstance(token, str) or not token.strip():
            not_examined += 1
            continue
        references.append(Reference(
            source=FIGURES_RELATIVE.replace(os.sep, "/"),
            token=token.strip(), figure_key=key,
            canon_value=entry.get("canon_value"), value=entry.get("value"),
            has_canon_value="canon_value" in entry,
            has_value="value" in entry))
    return references, tables, not_examined


def finding_id(kind, document, detail):
    return "claim:%s:%s#%s" % (kind, document, detail)


# ---------------------------------------------------------------------------
# Detection -- the six branches
# ---------------------------------------------------------------------------


UNFILLED_HOLE_RE = re.compile(r"^<.*>$", re.S)
UNRENDERED_REFERENCE_RE = re.compile(r"^\{\{.*\}\}$", re.S)


def is_unfilled(value):
    """True when a cell was never filled in by a human or by render.py.

    Three shapes, all of them the skeleton's own: absent, a `<...>` instruction
    to the author, or an unrendered `{{figures.*}}` reference. The third is the
    one that would otherwise pass: `{{figures.headline_ratio}}` is a perfectly
    good STRING, and a check that only tested for emptiness would read an
    artifact nobody ever rendered as one carrying a measured counterpart.
    """
    if value is None:
        return True
    stripped = value.strip()
    if not stripped:
        return True
    if UNFILLED_HOLE_RE.match(stripped):
        return True
    return bool(UNRENDERED_REFERENCE_RE.match(stripped))


def has_real_value(entry, key):
    """True when `key` is present AND is not null.

    `canon_value: null` is "present with nothing in it", which is the case
    branch 5 exists for. Treating key-presence alone as presence would let a
    figure declare a canon value of nothing and pass.
    """
    return key in entry and entry[key] is not None


def claim_findings(references, tables, snapshot, uncompared=None):
    """The six branches. Returns (findings, counts_by_kind).

    `uncompared` is an optional single-element list the caller passes in to
    receive the count of figures the canon states no number for. A COUNT rather
    than a finding, for the reason the module docstring gives.

    Every branch produces its own KIND and its own finding id, so a report can
    be triaged without re-reading the document. The id is
    `claim:<kind>:<document>#<detail>`; the detail is the thing an operator has
    to go and look at.
    """
    counts = dict((kind, 0) for kind in FINDING_KINDS)
    findings = []

    def add(kind, document, detail_key, line, message, **extra):
        counts[kind] += 1
        record = {"kind": kind,
                  "id": finding_id(kind, document, detail_key),
                  "document": document,
                  "line": line,
                  "detail": message}
        record.update(extra)
        findings.append(record)

    figure_refs = [ref for ref in references if ref.figure_key is not None]

    # -- Branch 1 ----------------------------------------------------------
    # A required part of the claim block is not there. The whole table first:
    # the artifact named a canon bullet in its figures and then never said which
    # claim is under test. This is a FINDING and not a refusal, because the
    # artifact DID make a claim -- "could not look" and "found a problem" are
    # the distinction an earlier finding calls the most important in the checker, and filing
    # this under the former would hide it in the one verdict nobody triages.
    if not tables and figure_refs:
        add(KIND_ABSENT, REQUIRED_DOCUMENT, "<no-claim-table>", 0,
            "%d figure(s) name a canon bullet (%s) but no document carries a "
            "claim-under-test table, so nothing records WHICH claim these "
            "measurements are weighed against. the project overview document's Key Decision a design rule "
            "-- the measurement wins and the published entry changes -- has no "
            "subject without it. REPAIR: copy the claim table from "
            "templates/README-SKELETON.md and fill it in."
            % (len(figure_refs),
               ", ".join(sorted({ref.token for ref in figure_refs}))))

    for table in tables:
        # Canon and project are named by the requirement and are checked for
        # PRESENCE here. They are also redundant with a compound key, which is
        # why a row that CONTRADICTS the key is reported below as an ambiguity
        # rather than as an absence.
        for field, label in ((F_CANON, "Canon"),
                             (F_PROJECT, "Example project (or Project)")):
            if is_unfilled(table.value(field)):
                add(KIND_ABSENT, table.document, field, table.line,
                    "the claim table carries no usable `%s` row. REPAIR: name "
                    "it; the skeleton renders it from the manifest." % label)

        tokens = split_id_tokens(table.value(F_BULLET_ID))
        resolutions = [resolve_reference(token, snapshot) for token in tokens]
        resolved = [res for res in resolutions if res.resolved]

        if not tokens:
            add(KIND_ABSENT, table.document, F_BULLET_ID, table.line,
                "the claim table carries no usable `Bullet id` row, so the "
                "claim names no bullet at all. REPAIR: write the COMPOUND key, "
                "`<canon>:<bullet-id>`.")

        # -- Branches 2 and 3 ---------------------------------------------
        for res in resolutions:
            if res.how == UNRESOLVED_BARE:
                add(KIND_BARE_ID, table.document, res.token, table.line,
                    "`%s` is written WITHOUT its canon prefix and that bare id "
                    "exists in %d canons, so it names %s. This is not a near "
                    "miss: those bullets are different sentences about "
                    "different work. REPAIR: write one of the compound keys. "
                    "(A `Canon` row beside it is not a substitute -- two fields "
                    "that can disagree is the ambiguity, not the fix.)"
                    % (res.token, len(res.candidates),
                       " or ".join(sorted(res.candidates))),
                    candidates=sorted(res.candidates))
            elif res.how == UNRESOLVED_UNKNOWN_KEY:
                add(KIND_UNKNOWN_KEY, table.document, res.token, table.line,
                    "`%s` is compound-keyed but is not one of the %d bullets in "
                    "the committed canon snapshot. REPAIR: check the key "
                    "against tools/%s."
                    % (res.token, len(snapshot.bullets), SNAPSHOT_BASENAME))
            elif res.how == UNRESOLVED_UNKNOWN:
                add(KIND_BARE_ID, table.document, res.token, table.line,
                    "`%s` is neither a compound key `<canon>:<bullet-id>`, nor "
                    "a display reference the snapshot knows, nor a bullet id in "
                    "either canon, so it resolves to nothing. REPAIR: write the "
                    "compound key." % res.token)
            else:
                # It RESOLVED. A Canon or Project row naming something else
                # means the block names two different bullets, which is the
                # same ambiguity branch 2 exists for, one level up.
                entry = snapshot.bullets.get(res.key) or {}
                for field, label in ((F_CANON, "canon"),
                                     (F_PROJECT, "project")):
                    stated = table.value(field)
                    actual = entry.get(label)
                    if (stated and actual and not is_unfilled(stated)
                            and stated.strip() != actual):
                        add(KIND_BARE_ID, table.document,
                            "<%s-disagrees>:%s" % (label, res.token),
                            table.line,
                            "the `%s` row says %r but `%s` resolves to %r. The "
                            "block names two different things and a reader "
                            "cannot tell which claim is under test. REPAIR: "
                            "keep the compound key and correct the row."
                            % (label.capitalize(), stated.strip(), res.token,
                               actual))

        # The detail key every per-TABLE finding below is filed under: the
        # resolved key when there is one, so an operator can search for the
        # bullet rather than for the row.
        anchor = (resolved[0].key if resolved
                  else (tokens[0] if tokens else "<no-id>"))

        # -- Branch 4 -- the byte comparison -------------------------------
        if resolved:
            stated_text = table.value(F_TEXT)
            if stated_text is None:
                add(KIND_TEXT_MISMATCH, table.document, anchor, table.line,
                    "the claim table carries no `Bullet text, verbatim` row, so "
                    "there is nothing to compare against the canon. REPAIR: "
                    "paste the bullet; do not paraphrase it.")
            elif not any(texts_match(stated_text, snapshot.text_for(res.key))
                         for res in resolved):
                target = resolved[0]
                difference = first_difference(stated_text,
                                              snapshot.text_for(target.key))
                offset = difference[0] if difference else -1
                add(KIND_TEXT_MISMATCH, table.document, anchor, table.line,
                    "the `Bullet text, verbatim` cell is not byte-identical to "
                    "the snapshot's text for %s. First difference at UTF-8 byte "
                    "%d; stated length %d byte(s), canon length %d byte(s). "
                    "Nothing is normalized here on purpose -- a paraphrase is "
                    "what this branch exists to catch, and normalization is how "
                    "one passes. REPAIR: paste the bullet from tools/%s. (Read "
                    "the --report file, not the console: correct UTF-8 renders "
                    "as replacement characters on this platform.)"
                    % (target.key, offset,
                       len(stated_text.encode("utf-8")),
                       len((snapshot.text_for(target.key) or "").encode("utf-8")),
                       SNAPSHOT_BASENAME),
                    byte_offset=offset, resolved_key=target.key)

        # -- Branch 5 -- the measured counterpart --------------------------
        if is_unfilled(table.value(F_MEASURED)):
            add(KIND_NO_COUNTERPART, table.document, anchor, table.line,
                "the claim table names no measured counterpart, so the canon "
                "figure has nothing beside it to be weighed against. A claim "
                "with no counterpart cannot be SUPPORTED or refuted; it can "
                "only be asserted. REPAIR: name the figure this bullet is "
                "tested by.")

        # -- Branch 6 -- the verdict ---------------------------------------
        verdict = table.value(F_VERDICT)
        if is_unfilled(verdict):
            add(KIND_VERDICT, table.document, "<absent>", table.line,
                "the claim table carries no verdict. The three legal values "
                "are %s. DOES-NOT-SUPPORT is a legitimate outcome of a build, "
                "not a failure of one -- an absent verdict is the only illegal "
                "answer here." % ", ".join(LEGAL_VERDICTS))
        elif verdict.strip() not in LEGAL_VERDICTS:
            add(KIND_VERDICT, table.document, verdict.strip(), table.line,
                "the verdict is %r, which is not one of the three legal "
                "values: %s. (This check verifies a verdict EXISTS and is "
                "legal. It never judges whether it is RIGHT -- that reading is "
                "the owner's under a project requirement and is recorded as manual-only.)"
                % (verdict.strip(), ", ".join(LEGAL_VERDICTS)))

    # -- The figures limb: branches 2, 3 and 5 over the results record -----
    for ref in figure_refs:
        document = ref.source
        res = resolve_reference(ref.token, snapshot)
        if res.how == UNRESOLVED_BARE:
            add(KIND_BARE_ID, document, ref.figure_key, 0,
                "figure %r names canon_bullet %r, which is written without its "
                "canon prefix and exists in %d canons: %s. REPAIR: write the "
                "compound key."
                % (ref.figure_key, ref.token, len(res.candidates),
                   " or ".join(sorted(res.candidates))),
                candidates=sorted(res.candidates))
        elif res.how == UNRESOLVED_UNKNOWN_KEY:
            add(KIND_UNKNOWN_KEY, document, ref.figure_key, 0,
                "figure %r names canon_bullet %r, which is not one of the %d "
                "bullets in the committed canon snapshot."
                % (ref.figure_key, ref.token, len(snapshot.bullets)))
        elif res.how == UNRESOLVED_UNKNOWN:
            add(KIND_BARE_ID, document, ref.figure_key, 0,
                "figure %r names canon_bullet %r, which resolves to nothing at "
                "all." % (ref.figure_key, ref.token))

        canon_side = ref.has_canon_value and ref.canon_value is not None
        measured_side = ref.has_value and ref.value is not None
        if canon_side and not measured_side:
            add(KIND_NO_COUNTERPART, document, ref.figure_key, 0,
                "figure %r carries a usable `canon_value` with nothing "
                "MEASURED beside it. The comparison was declared and then not "
                "made, so the figure records a canon number nobody weighed "
                "anything against. REPAIR: measure it, or drop the "
                "`canon_value` -- a figure the canon states no number for is "
                "supporting evidence and is counted as such."
                % ref.figure_key)
        elif measured_side and not canon_side:
            # NOT a finding. See the docstring: canonkit requires a
            # `canon_bullet` on every figure, so supporting evidence must name
            # one, and no canon states a number for a load-generator ceiling.
            if uncompared is not None:
                uncompared[0] += 1

    return findings, counts


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
    artifact = os.path.abspath(str(artifact))
    snapshot_path = getattr(ctx, "canon_snapshot", None)

    def refused(note):
        result = contract.CheckResult(
            check_id=CHECK_ID, code=core.EXIT_DID_NOT_RUN, found=0, checked=0,
            floor=floor, waived=0, note=note)
        result.detail = {"documents_scanned": 0,
                         "documents_declared": len(SCANNED_DOCUMENTS),
                         "claim_tables": 0, "references": 0,
                         "figures_without_bullet": 0,
                         "figures_without_canon_value": 0,
                         "counts": dict((kind, 0) for kind in FINDING_KINDS),
                         "findings": [], "artifact": artifact,
                         "legal_verdicts": list(LEGAL_VERDICTS)}
        return result

    if not os.path.isdir(artifact):
        return refused("%s is not a directory" % artifact)

    try:
        snapshot = load_snapshot(snapshot_path)
        documents = read_documents(artifact)
        figures, _ = load_figures(artifact)
    except CheckRefusal as refusal:
        return refused(str(refusal))

    references, tables, not_examined = enumerate_references(documents, figures)
    checked = len(references)

    # WHERE APPLICABILITY IS DECIDED, AND IT IS NOT HERE.
    #
    # This refusal is "this artifact should have a claim table and does not".
    # That is a DIFFERENT fact from "this artifact owes no claim at all", and
    # only the second is an inapplicability. The second is decided by the
    # RUNNER, before this module is called: conformance.py's ARTIFACT_SUBSET
    # declares CHECK-09 inapplicable when the slug's manifest row maps a claim
    # through neither `bullets` nor `backs_bullets` AND records a
    # `no_row_reason`. Such a member is named with that reason, contributes no
    # code, and stays in CHECK-11's population.
    #
    # DO NOT ADD A SECOND, IN-MODULE PREDICATE. The runner aggregates every
    # applicable record's code and the conventions document section 1 lifts any 2 to 1,
    # so an in-module "this one does not apply" returning EXIT_DID_NOT_RUN puts
    # EXIT=0 permanently out of reach for an artifact that is CORRECT to back
    # nothing -- which is exactly what a design rule declined to tolerate with a waiver.
    # The refusal below must keep firing: `example-cache-benchmark`'s row
    # DOES name a claim, and a missing claim table there is a real finding.
    if checked == 0:
        return refused(
            "no claim table names a bullet id and no figure carries a "
            "canon_bullet, so there are ZERO bullet references to examine. A "
            "check over zero references cannot fail, so it must not be allowed "
            "to report success. REPAIR: fill in the claim-under-test "
            "block from the skeleton -- or, if this path genuinely backs no "
            "claim, record that in the expected set's own row as empty mapping "
            "fields plus a `no_row_reason`, which the runner's applicability "
            "declaration reads and this module never does.")

    uncompared = [0]
    findings, counts = claim_findings(references, tables, snapshot, uncompared)

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

    note = ("references=%d tables=%d %s no-canon-value=%d documents=%d of %d"
            % (checked, len(tables),
               " ".join("%s=%d" % (kind, counts.get(kind, 0))
                        for kind in FINDING_KINDS),
               uncompared[0], len(documents), len(SCANNED_DOCUMENTS)))

    result = contract.CheckResult(
        check_id=CHECK_ID, code=code, found=found, checked=checked, floor=floor,
        waived=waived, not_examined=not_examined, note=note,
        finding_ids=sorted({finding["id"] for finding in kept}))
    result.detail = {
        "documents_scanned": len(documents),
        "documents_declared": len(SCANNED_DOCUMENTS),
        "claim_tables": len(tables),
        "references": checked,
        "figures_without_bullet": not_examined,
        "figures_without_canon_value": uncompared[0],
        "counts": counts,
        "findings": kept,
        "artifact": artifact,
        "legal_verdicts": list(LEGAL_VERDICTS),
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
        "claim_tables": detail.get("claim_tables", 0),
        "references": detail.get("references", 0),
        "figures_without_bullet": detail.get("figures_without_bullet", 0),
        "figures_without_canon_value": detail.get("figures_without_canon_value", 0),
        "counts": detail.get("counts", {}),
        "findings": detail.get("findings", []),
        "artifact": detail.get("artifact", ""),
        "legal_verdicts": detail.get("legal_verdicts", list(LEGAL_VERDICTS)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_09",
        description="CHECK-09: fails when the claim-under-test block is missing "
                    "its ids, its verbatim bullet text, its measured "
                    "counterpart or a legal verdict.")
    parser.add_argument("artifact", nargs="?", default=".",
                        help="the artifact directory (default: the current one)")
    parser.add_argument("--report", default=None,
                        help="write the structured report here. A file "
                             "rather than a pipe: a command piped into tail "
                             "returns the PIPE's exit status.")
    parser.add_argument("--min-claims", type=int, default=None,
                        help="override the effective floor for this check "
                             ". The OVERRIDDEN value is what prints.")
    parser.add_argument("--canon", default=None,
                        help="an alternate canon snapshot. Exists so a test can "
                             "compare against a hermetic snapshot instead of "
                             "the committed one.")
    args = parser.parse_args(argv)

    core = load_core()
    contract = load_contract()

    overrides = {}
    if args.min_claims is not None:
        overrides[CHECK_ID] = args.min_claims
    ctx = contract.CheckContext(floor_overrides=overrides)
    ctx.canon_snapshot = args.canon

    result = run(args.artifact, ctx)

    # The population line, printed on EVERY branch.
    core.report(CHECK_ID, result.code == core.EXIT_PASS, result.found,
                result.checked, result.floor, waived=result.waived,
                note=result.note, not_examined=result.not_examined,
                listed=result.listed)

    # a design rule's demotion, said out loud rather than hidden in an exit code.
    if result.checked and result.checked < result.floor:
        print("  DEMOTED to DID-NOT-RUN: population %d is below the effective "
              "floor %d." % (result.checked, result.floor))

    detail = getattr(result, "detail", {}) or {}
    for finding in detail.get("findings", [])[:MAX_LISTED_FINDINGS]:
        print("  %-14s %s line %d: %s"
              % (finding["kind"], finding["document"], finding["line"],
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
