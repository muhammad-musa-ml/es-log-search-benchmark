"""render.py -- write figures.json into a document's regions, and REFUSE.

    python render.py <artifact>            # the DEFAULT: report, never rewrite
    python render.py <artifact> --write    # rewrite the regions

THE DEFAULT IS INVERTED FROM THE ANALOG, DELIBERATELY. Say it here because a
reviewer who knows the analog will expect the old behaviour:
the-upstream-project/scripts/dev/sync_cache.py:154 has `--check` as OPT-IN and
WRITING as the default action. This tool inverts that. A tool that
rewrites by default destroys the very edit it exists to report, and a design rule also
withholds any override: an override on the tool whose job is refusing is the
escape hatch that empties it. There is none, and a test asserts the literal
appears nowhere in this file.

What IS copied from the analog is its measurement shape, unchanged:

  * `_verify` (sync_cache.py:134-149) returns `(checked, problems)` -- population
    and findings as SEPARATE values -- and byte-compares rather than trusting
    that a write happened. Both properties are kept.
  * its reporting (sync_cache.py:167-189) prints a count that ALWAYS carries its
    denominator, and truncates a long finding list WITH its own count
    (`... and N more`) rather than silently. Both are kept.
  * its argv handling is NOT copied. That is the part a design rule inverts.

JUDGE STALENESS BY CONTENT, NEVER BY MTIME. Copied from the same analog's
warning at sync_cache.py:30-33: `copytree`/`copy2` PRESERVE the source's mtime,
so a freshly copied stale file looks new and a correct file that was touched
looks changed. Nothing in this module reads a timestamp. Drift here means the
BYTES differ, which is a fact about content and survives every copy, checkout
and clone. The same trap is waiting in CHECK-04, which orders a chain of runs:
order it by the recorded ISO timestamps INSIDE the records, never by mtime.

THE REGION MECHANISM (the design rules)
----------------------------------
A figure may appear in a document in exactly one place: inside a PAIRED region.

    <!-- artifact:figures:begin -->  ...  <!-- artifact:figures:end -->

There is no single-marker form, and a begin with no matching end is a REFUSAL
naming its line rather than a silent no-op -- a no-op here would leave a figure
un-rendered and report success, which is the failure this tool exists to catch.

Inside a region, a figure is written as a KEY REFERENCE, never as a number:

    {{figures.median_latency_ms}}

and `--write` turns it into

    <!--artifact:key:median_latency_ms-->12.5<!--/artifact:key-->

WHY THE REFERENCE SURVIVES RENDERING, which is the one design decision here a
reader is most likely to want explained. A substitution that CONSUMED the
reference would leave the rendered document with no record of where its numbers
came from, and re-rendering it would then be impossible -- so the second run
could not be idempotent, and a hand edit could not be detected, because there
would be nothing left to compare against. Keeping the key beside the value is
what makes the byte-compare possible at all. Markdown renders an HTML comment as
nothing, so a reader of the rendered README sees `12.5`.

WHAT IT REFUSES, and each refusal names the thing to repair (the shared pattern shape from
canonkit: `REFUSING:` on stderr, a distinct non-zero exit, a repair instruction):

  * a figure whose `population` is missing or zero, NAMED. This is a success criterion's
    load-bearing refusal and it is PREVENTION, not detection: a figure that
    cannot be rendered without a population cannot reach a README without one.
    `population: 1` is legal and renders -- peak VRAM and free VRAM at
    run start are legitimately single-sample population facts.
  * a key reference naming a key that `figures.json` does not hold, with the
    available keys LISTED, because "unknown key" alone makes the operator search.
  * a key reference OUTSIDE every region. This tool touches region
    interiors only, so such a reference would sit un-rendered forever while
    looking accepted.
  * an unmatched or mis-nested region marker, with its line number.
  * a figures record holding zero figures. Rendering over zero figures cannot
    fail, so it must not be allowed to report success.

EXIT CODES (canonkit's contract; a caller branches on these):
    0  clean: nothing drifted, or --write succeeded
    1  DRIFT: the document does not match its source. The tool DID look.
    2  REFUSED: it could not look, or a precondition failed. Also argparse's
       own code for an unknown flag.

VENDORING. This file is in the declared vendored set (tools/vendor.py) and is
copied by bytes to an artifact's root, beside canonkit.py. It is run BY PATH and
imports the core as a SIBLING; it is never `tools.render` and never imports
`tools.canonkit`. Stdlib only, ASCII only, same contract as the core.
"""

import argparse
import difflib
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

SCHEMA = "canonkit/render/1"

# The documents whose regions this renders. README.md is required -- it is the
# interviewer-facing document and a project requirement names it. results/RESULTS.md is
# rendered when present; an artifact that has not produced one yet is not a
# defect, and BOTH numbers are printed so a reader can tell the two apart.
RENDERED_DOCUMENTS = ("README.md", "results/RESULTS.md")
REQUIRED_DOCUMENT = "README.md"

FIGURES_RELATIVE = os.path.join("results", "figures.json")

# Copied from the analog: a finding list is truncated WITH its own count.
MAX_LISTED_FINDINGS = 20
MAX_DIFF_LINES = 60
MAX_LISTED_KEYS = 40

# The top-level fields of a figures record a document may reference. A CLOSED
# list on purpose. Allowing "any top-level scalar" would let a key invented
# outside the figures block bypass the population refusal below, which is the
# one refusal a success criterion names.
TOP_LEVEL_KEYS = ("artifact", "dated_at", "started_at", "started_at_utc",
                  "gate_token")

# `artifact:<name>:begin` / `:end`. The token is `artifact:`.
MARKER_RE = re.compile(r"<!--\s*artifact:([a-z][a-z0-9_-]*):(begin|end)\s*-->")

# The two forms a hole takes, matched in ONE pass so every hole's line number is
# its position in the ORIGINAL text rather than in a partly-substituted copy.
HOLE_RE = re.compile(
    r"<!--artifact:key:(?P<rkey>[A-Za-z0-9_.\[\]-]+)-->"
    r"(?P<value>.*?)"
    r"<!--/artifact:key-->"
    r"|"
    r"\{\{\s*figures\.(?P<ukey>[A-Za-z0-9_.\[\]-]+?)\s*\}\}",
    re.S)

RENDERED_OPEN = "<!--artifact:key:%s-->"
RENDERED_CLOSE = "<!--/artifact:key-->"

# `begin` and `end` are the only two key paths that would make a rendered hole's
# marker parse as a REGION marker. Refused rather than escaped.
RESERVED_KEY_PATHS = ("begin", "end")


def load_core():
    """Load the frozen core BY PATH, as a sibling. Never `tools.canonkit`.

    The vendored copy of this file sits at an artifact's root beside
    canonkit.py, with no `tools` package anywhere. Loading by path is therefore
    not a style choice: it is the only load that works in both places.
    """
    path = os.path.join(HERE, "canonkit.py")
    spec = importlib.util.spec_from_file_location("frozen_core", path)
    if spec is None or spec.loader is None:
        raise ImportError("could not build an import spec for %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Refusal(Exception):
    """A precondition failed. The tool COULD NOT LOOK; nothing was written."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def line_of(text, offset):
    """1-based line number of `offset` in `text`."""
    return text.count("\n", 0, offset) + 1


def format_value(key, value):
    """Render one figure value as the string that goes into the document.

    `repr` for a float rather than `%g`: `%g` silently rounds to six significant
    digits, so a measured 1234567 would be published as 1.23457e+06 -- a figure
    altered by its own renderer.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return value
    raise Refusal(
        "figure %r holds a %s, which has no single rendered form.\n"
        "  REPAIR: give the figure a scalar `value` in results/figures.json, or "
        "reference one of its scalar fields as {{figures.%s.<field>}}."
        % (key, type(value).__name__, key))


def normalize_figures(record, figures_path):
    """The `figures` block as key -> figure dict.

    Accepts BOTH shapes present in this repository: the object keyed by figure
    key that derive.py writes, and the list of entries carrying an `id` that the
    test conftest builds. Accepting both is deliberate -- refusing the second
    would make this tool unable to render the very fixtures the suite hands it,
    and the two shapes carry the same information.
    """
    figures = record.get("figures")
    if isinstance(figures, dict):
        return dict(figures)
    if isinstance(figures, list):
        normalized = {}
        for index, entry in enumerate(figures):
            if not isinstance(entry, dict) or not entry.get("id"):
                raise Refusal(
                    "%s: figures[%d] is not an object carrying an `id`.\n"
                    "  REPAIR: re-run derive.py; it writes the keyed form."
                    % (figures_path, index))
            normalized[str(entry["id"])] = entry
        return normalized
    raise Refusal(
        "%s: `figures` is %s, expected an object or a list.\n"
        "  REPAIR: re-run derive.py, which is the single source of truth for "
        "every number."
        % (figures_path, type(figures).__name__))


def available_keys(figures, record):
    """Every key a document may reference right now, for a refusal message."""
    keys = sorted(figures)
    keys.extend(name for name in TOP_LEVEL_KEYS if name in record)
    return keys


def describe_keys(keys):
    shown = keys[:MAX_LISTED_KEYS]
    text = ", ".join(shown) if shown else "<none>"
    if len(keys) > len(shown):
        text = text + " (+%d more)" % (len(keys) - len(shown))
    return "%d available key(s): %s" % (len(keys), text)


def resolve(path, figures, record):
    """Resolve `figures.<path>` to (value, figure_key or None).

    `figure_key` is None only for the closed TOP_LEVEL_KEYS set. Every other
    resolution goes through a figure and is therefore subject to the population
    refusal, which is the whole point of returning the key rather than just the
    value.
    """
    if path in figures:
        entry = figures[path]
        if isinstance(entry, dict):
            if "value" not in entry:
                raise Refusal(
                    "figure %r carries no `value`.\n"
                    "  REPAIR: re-run derive.py." % path)
            return entry["value"], path
        return entry, path

    head, _, rest = path.partition(".")
    if rest and head in figures:
        node = figures[head]
        for segment in rest.split("."):
            if not isinstance(node, dict) or segment not in node:
                raise Refusal(
                    "figure %r has no field %r (asked for %r).\n"
                    "  REPAIR: reference a field the figure actually carries, "
                    "or re-run derive.py." % (head, segment, path))
            node = node[segment]
        return node, head

    if path in TOP_LEVEL_KEYS and path in record:
        return record[path], None

    raise Refusal(
        "no figure named %r. %s\n"
        "  REPAIR: re-run derive.py so the figure is authored, or correct the "
        "key reference in the document."
        % (path, describe_keys(available_keys(figures, record))))


def require_population(key, figures):
    """a success criterion's refusal. PREVENTION: an un-populated figure cannot be rendered.

    A bare "a figure is missing its population" would make the operator search,
    so the key is named. `population: 1` is legal; 0 and absent are the
    0/0 pass wearing a figure's clothes.
    """
    entry = figures.get(key)
    if not isinstance(entry, dict):
        return
    if "population" not in entry:
        raise Refusal(
            "figure %r has NO population.\n"
            "  A figure published without its denominator is a claim, not a "
            "measurement, so it is refused here rather than detected later.\n"
            "  REPAIR: give %r a `population` and a `population_label` in the "
            "figure specs and re-run derive.py." % (key, key))
    population = entry["population"]
    if isinstance(population, bool) or not isinstance(population, int):
        raise Refusal(
            "figure %r has population %r, which is %s and not an integer.\n"
            "  REPAIR: re-run derive.py; it writes the denominator it counted."
            % (key, population, type(population).__name__))
    if population < 1:
        raise Refusal(
            "figure %r has population %d. A figure over zero inputs measured "
            "nothing.\n"
            "  population 1 is legal and renders; 0 is not.\n"
            "  REPAIR: measure at least one input, or drop the figure."
            % (key, population))


def guard_rendered_text(key, text):
    """A value that would corrupt the document it is rendered into is refused."""
    if "\n" in text or "\r" in text:
        raise Refusal(
            "figure %r renders to a value containing a line break, which would "
            "split the region it sits in.\n"
            "  REPAIR: give the figure a single-line value." % key)
    if "<!--" in text or "-->" in text:
        raise Refusal(
            "figure %r renders to a value containing an HTML comment delimiter, "
            "which would terminate its own marker.\n"
            "  REPAIR: give the figure a value with no comment delimiters."
            % key)


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------


class Region(object):
    """One paired region: its name, its body span and both marker line numbers."""

    def __init__(self, name, body_start, body_end, begin_line, end_line):
        self.name = name
        self.body_start = body_start
        self.body_end = body_end
        self.begin_line = begin_line
        self.end_line = end_line


def parse_regions(text, document):
    """Every paired region, in order. REFUSES on any marker that is not paired."""
    regions = []
    opened = None
    for match in MARKER_RE.finditer(text):
        name, kind = match.group(1), match.group(2)
        line = line_of(text, match.start())
        if kind == "begin":
            if opened is not None:
                raise Refusal(
                    "%s line %d: region `%s` opens while `%s` (opened at line %d) "
                    "is still open. Regions do not nest.\n"
                    "  REPAIR: close `%s` before opening `%s`."
                    % (document, line, name, opened.name, opened.begin_line,
                       opened.name, name))
            opened = Region(name, match.end(), None, line, None)
            continue
        if opened is None:
            raise Refusal(
                "%s line %d: an end marker for region `%s` with no begin marker "
                "above it.\n"
                "  REPAIR: add `<!-- artifact:%s:begin -->` above it, or delete "
                "this line." % (document, line, name, name))
        if opened.name != name:
            raise Refusal(
                "%s line %d: region `%s` ends, but `%s` was opened at line %d.\n"
                "  REPAIR: make the two marker names match."
                % (document, line, name, opened.name, opened.begin_line))
        opened.body_end = match.start()
        opened.end_line = line
        regions.append(opened)
        opened = None

    if opened is not None:
        raise Refusal(
            "%s line %d: region `%s` is opened and never closed. A begin marker "
            "with no end is a SILENT no-op otherwise -- the region would never "
            "render and the run would report success.\n"
            "  REPAIR: add `<!-- artifact:%s:end -->` below it."
            % (document, opened.begin_line, opened.name, opened.name))
    return regions


def outside_spans(text, regions):
    """(start, end) of every stretch of `text` that is not inside a region."""
    spans = []
    cursor = 0
    for region in regions:
        spans.append((cursor, region.body_start))
        cursor = region.body_end
    spans.append((cursor, len(text)))
    return spans


# ---------------------------------------------------------------------------
# Rendering one document
# ---------------------------------------------------------------------------


class Hole(object):
    """One key reference: where it is, what it says now, what it should say."""

    def __init__(self, document, line, key, current, expected):
        self.document = document
        self.line = line
        self.key = key
        self.current = current
        self.expected = expected

    @property
    def drifted(self):
        return self.current != self.expected

    def describe(self):
        return ("DIFFERS  %s line %d  %s: document says %r, figures.json says %r"
                % (self.document, self.line, self.key, self.current,
                   self.expected))


class DocumentResult(object):
    def __init__(self, relative, text, rendered, regions, clean_regions, holes):
        self.relative = relative
        self.text = text
        self.rendered = rendered
        self.regions = regions
        self.clean_regions = clean_regions
        self.holes = holes

    @property
    def drifted_holes(self):
        return [hole for hole in self.holes if hole.drifted]


def render_document(relative, text, figures, record):
    """Re-render `text` in memory. Returns a DocumentResult. Never writes."""
    regions = parse_regions(text, relative)

    # a design rule, enforced BEFORE anything is rendered: a key reference outside every
    # region can never be rendered by this tool, so leaving it in place would be
    # a dead instruction that looks accepted.
    for start, end in outside_spans(text, regions):
        for match in HOLE_RE.finditer(text, start, end):
            key = match.group("rkey") or match.group("ukey")
            raise Refusal(
                "%s line %d: the key reference for %r sits OUTSIDE every region.\n"
                "  Un-rendered prose may not carry a figure at all: this "
                "tool touches region interiors only, so the reference would stay "
                "un-rendered forever while looking accepted.\n"
                "  REPAIR: move it inside a paired `artifact:` region."
                % (relative, line_of(text, match.start()), key))

    holes = []
    pieces = []
    cursor = 0
    clean_regions = 0

    for region in regions:
        pieces.append(text[cursor:region.body_start])
        body = text[region.body_start:region.body_end]
        rendered_body = _render_body(relative, text, region, body, figures,
                                     record, holes)
        pieces.append(rendered_body)
        if rendered_body == body:
            clean_regions += 1
        cursor = region.body_end

    pieces.append(text[cursor:])
    return DocumentResult(relative, text, "".join(pieces), len(regions),
                          clean_regions, holes)


def _render_body(relative, text, region, body, figures, record, holes):
    """Substitute every hole in one region body, recording each hole's drift."""
    out = []
    cursor = 0
    for match in HOLE_RE.finditer(body):
        key = match.group("rkey") or match.group("ukey")
        if key in RESERVED_KEY_PATHS:
            raise Refusal(
                "%s line %d: %r is a reserved key path -- its rendered marker "
                "would parse as a region marker.\n"
                "  REPAIR: rename the figure."
                % (relative, line_of(text, region.body_start + match.start()),
                   key))

        value, figure_key = resolve(key, figures, record)
        if figure_key is not None:
            require_population(figure_key, figures)
        rendered_value = format_value(key, value)
        guard_rendered_text(key, rendered_value)

        replacement = (RENDERED_OPEN % key) + rendered_value + RENDERED_CLOSE
        holes.append(Hole(
            relative,
            line_of(text, region.body_start + match.start()),
            key,
            match.group(0),
            replacement,
        ))
        out.append(body[cursor:match.start()])
        out.append(replacement)
        cursor = match.end()

    out.append(body[cursor:])
    return "".join(out)


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def load_record(artifact):
    """The figures record, REFUSING on absence, on a parse error, and on empty."""
    path = os.path.join(artifact, FIGURES_RELATIVE)
    if not os.path.isfile(path):
        raise Refusal(
            "no figures.json at %s.\n"
            "  Nothing can be rendered without the record that authored the "
            "numbers.\n"
            "  REPAIR: run `python derive.py --specs figure-specs.json` first."
            % path)
    try:
        record = json.loads(read_bytes(path).decode("utf-8"))
    except ValueError as error:
        raise Refusal(
            "%s does not parse as JSON: %s\n"
            "  REPAIR: re-run derive.py rather than repairing it by hand."
            % (path, error))
    if not isinstance(record, dict):
        raise Refusal("%s is not a JSON object.\n  REPAIR: re-run derive.py."
                      % path)

    figures = normalize_figures(record, path)
    if not figures:
        raise Refusal(
            "%s holds 0 figures. Rendering over zero figures cannot fail, so it "
            "must not be allowed to report success.\n"
            "  REPAIR: run derive.py with figure specs that author at least one "
            "figure." % path)
    return record, figures, path


def run(artifact, write=False, report_path=None, stream=None):
    """Render or check `artifact`. Returns an exit code. Raises Refusal."""
    stream = stream or sys.stdout
    core = load_core()
    artifact = os.path.abspath(str(artifact))

    if not os.path.isdir(artifact):
        raise Refusal(
            "%s is not a directory.\n"
            "  REPAIR: name the artifact directory, e.g. "
            "`python render.py <home>/Research/<slug>`." % artifact)

    record, figures, figures_path = load_record(artifact)

    documents = []
    for relative in RENDERED_DOCUMENTS:
        path = os.path.join(artifact, relative.replace("/", os.sep))
        if os.path.isfile(path):
            documents.append((relative, path))

    if not any(relative == REQUIRED_DOCUMENT for relative, _ in documents):
        raise Refusal(
            "%s has no %s.\n"
            "  REPAIR: generate the artifact with `python -m tools.new_artifact "
            "<slug>`, which writes it from the skeleton."
            % (artifact, REQUIRED_DOCUMENT))

    results = []
    for relative, path in documents:
        text = read_bytes(path).decode("utf-8")
        results.append((path, render_document(relative, text, figures, record)))

    regions_found = sum(result.regions for _, result in results)
    holes_found = sum(len(result.holes) for _, result in results)
    drifted = []
    for _, result in results:
        drifted.extend(result.drifted_holes)

    if write:
        for path, result in results:
            if result.rendered.encode("utf-8") != read_bytes(path):
                core.atomic_write_text(path, result.rendered, encoding="utf-8",
                                       ensure_ascii=False)
        regions_clean = regions_found
        code = core.EXIT_PASS
    else:
        regions_clean = sum(result.clean_regions for _, result in results)
        code = core.EXIT_FINDING if drifted or regions_clean != regions_found \
            else core.EXIT_PASS

    # THE POPULATION LINES, PRINTED ON EVERY BRANCH. A count printed only on
    # success tells a reader nothing about a failure, and a numerator with no
    # denominator beside it is not a claim anyone can evaluate.
    print("documents %d of %d" % (len(documents), len(RENDERED_DOCUMENTS)),
          file=stream)
    print("rendered %d of %d regions" % (regions_clean, regions_found),
          file=stream)
    print("references %d of %d resolved"
          % (holes_found - len(drifted), holes_found), file=stream)

    if not write and drifted:
        for hole in drifted[:MAX_LISTED_FINDINGS]:
            print("  " + hole.describe(), file=stream)
        if len(drifted) > MAX_LISTED_FINDINGS:
            print("  ... and %d more" % (len(drifted) - MAX_LISTED_FINDINGS),
                  file=stream)
        _print_diff(results, stream)
        print("FAIL - the document does NOT match results/figures.json.",
              file=stream)
        print("  REPAIR: re-run derive.py, then `python render.py <artifact> "
              "--write`. A hand edit to a rendered region is a detected error, "
              "not a shortcut.", file=stream)

    if report_path:
        core.atomic_write_json(report_path, {
            "schema": SCHEMA,
            "schema_version": core.SCHEMA_VERSION,
            "action": "write" if write else "check",
            "artifact": artifact,
            "figures_record": figures_path,
            "figures_count": len(figures),
            "documents_found": len(documents),
            "documents_declared": len(RENDERED_DOCUMENTS),
            "regions_found": regions_found,
            "regions_rendered": regions_clean,
            "references_found": holes_found,
            "references_drifted": len(drifted),
            "drift": [{"document": hole.document, "line": hole.line,
                       "key": hole.key, "current": hole.current,
                       "expected": hole.expected} for hole in drifted],
            "code": code,
        })
    return code


def _print_diff(results, stream):
    """A unified diff of current vs re-rendered, bounded and SAID to be bounded."""
    lines = []
    for _, result in results:
        if result.rendered == result.text:
            continue
        lines.extend(difflib.unified_diff(
            result.text.splitlines(),
            result.rendered.splitlines(),
            fromfile="%s (on disk)" % result.relative,
            tofile="%s (re-rendered from results/figures.json)" % result.relative,
            lineterm="", n=1))
    for line in lines[:MAX_DIFF_LINES]:
        print(line, file=stream)
    if len(lines) > MAX_DIFF_LINES:
        print("[diff truncated: %d further line(s)]"
              % (len(lines) - MAX_DIFF_LINES), file=stream)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="render",
        description="Write results/figures.json into a document's regions. "
                    "Reports by default; rewriting requires --write.")
    parser.add_argument("artifact", nargs="?", default=".",
                        help="the artifact directory (default: the current one)")
    parser.add_argument("--write", action="store_true",
                        help="rewrite the regions. Without it, this tool only "
                             "reports and exits non-zero on a difference.")
    parser.add_argument("--report", default=None,
                        help="write the structured report here. A file "
                             "rather than a pipe: a command piped into tail "
                             "returns the PIPE's exit status.")
    args = parser.parse_args(argv)

    core = load_core()
    try:
        return run(args.artifact, write=args.write, report_path=args.report)
    except Refusal as refusal:
        core.die(core.EXIT_DID_NOT_RUN,
                 "%s %s" % (core.REFUSAL_PREFIX, refusal))


if __name__ == "__main__":
    sys.exit(main())
