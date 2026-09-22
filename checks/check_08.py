"""CHECK-08 -- pins at pull sites, with provenance OUTPUTS scoped out and counted.

    python check_08.py <root> [--report FILE] [--min-population N]
                              [--include-drivers]

the project requirements document states the check as: fails on any unpinned dependency specifier,
any image reference lacking `@sha256:`, and the floating tag whose name means
"newest" ANYWHERE.

That requirement is PARAPHRASED rather than quoted, and the substitution is the
first thing this module has to explain about itself. See the assembled-needle
paragraph below: a source file that quoted the banned string would be a hit for
its own rule.

THE MEASURED FALSE POSITIVE, AND WHY SCOPE IS THE WHOLE DESIGN
----------------------------------------------------------------
A literal implementation of "any floating tag anywhere" flags a CORRECT artifact,
and the case is real rather than imagined. The shipped results/provenance.json
carries, verbatim:

    "images": {"grafana/k6:<the floating tag>": "grafana/k6@sha256:e7ee..."}

The KEY is the human-readable name of what was resolved and the VALUE is the
digest it resolved TO. That record is not a defect -- it is the artifact
DOCUMENTING its resolution, which is the entire purpose of a provenance record.
A check that flagged it would be reporting a repudiation risk as a pin failure,
and the obvious "fix" a reader would reach for is DELETING THE PROVENANCE KEY:
destroying the evidence to silence the checker.

So the rules are scoped to references that cause a PULL, and provenance records
are OUTPUTS rather than inputs and are excluded by FILE SCOPE.

TWO WARNING SIGNS, recorded here so a future reader diagnoses the checker rather
than the artifact:

    1. a CHECK-08 finding whose `path:line` is inside results/ is a SCOPING BUG
       in this module. results/ is not a pull site and never becomes one.
    2. a "fix" that consists of deleting a provenance key is the failure this
       paragraph exists to prevent. The record is the evidence; the checker is
       the thing that is wrong.

AN EXCLUSION THAT DOES NOT PRINT IS AN EXCLUSION LIST THAT GROWS SILENTLY
---------------------------------------------------------------------------
So both numbers print, always:

    pull-sites checked N file(s), provenance entries not-examined M

M is counted by READING the provenance records and counting their image entries
-- not by ignoring the directory and hoping. An input that was not examined is
counted and given a reason; a scope decision nobody can see is a scope decision
nobody can review.

THE WHOLE FILE IS SCANNED FOR THE FLOATING TAG, NOT ONLY THE `image:` KEYS
----------------------------------------------------------------------------
This is not this module's invention. templates/docker-compose.yml states it as
the contract that template was written against, and gives the reason: A
COMMENTED-OUT SERVICE IS ONE UNCOMMENT AWAY FROM BEING A PULL SITE. The
requirement's own wording agrees: the floating tag is banned ANYWHERE, not
merely in the position where an image is declared.

The template also records the consequence it measured: a comment explaining the
ban by QUOTING the banned string is itself a hit, in every artifact generated
from that template, forever. Its first draft did exactly that and failed this
check. The template now describes the tag in words instead.

THIS MODULE IS UNDER THE SAME CONSTRAINT, and handles it the way check_03.py
handles the skeleton's TODO marker: the needle is ASSEMBLED FROM PARTS at import
time, so this file's own source is not a hit for a sweep that hunts it across the
tree. That is a real requirement, not fastidiousness -- this module is a .py file
inside the repository it can be pointed at.

DRIVER SCRIPTS ARE A DECLARED, TESTED, OPT-IN SCOPE
------------------------------------------------------
The template also says the ban applies to "any image a DRIVER script launches
rather than compose". That capability is built and tested here and is reached
with `--include-drivers`; it is OFF by default, for two statable reasons rather
than as a deferral:

    a driver's image string is a pull site only if the script actually launches
    it, which is interpretation this module cannot do; and the needle inside a
    .py file is genuinely ambiguous -- a test fixture, a docstring or a regex
    carries it without pulling anything.

Default or not, the scope is PRINTED (`drivers=scanned` or `drivers=excluded`),
so a reader never has to infer which population produced the verdict. an earlier plan
wires a design rule's `--self` subset; with the flag already implemented and covered, that
wiring is a configuration change rather than a rewrite.

DIRECTORIES NAMED `broken-*` ARE PRUNED FROM THE WALK, AND COUNTED
--------------------------------------------------------------------
a design rule established that prefix as the mechanically locatable marker of the
deliberately-broken fixture tree, precisely so a tool can enumerate or avoid that
tree without a hand-maintained list. Without the prune, a run rooted at this
repository would report the committed `elasticsearch` defect as a finding about
the TOOLING REPOSITORY -- a permanent wall of findings against files that are
broken on purpose, which is the failure a design rule exists to prevent arriving through
the other door.

The prune applies to DESCENDANTS only, never to the root, so pointing this check
straight at a `broken-*` fixture still checks it. The pruned count prints.

ONE REFERENCE, ONE FINDING
-----------------------------
A reference that is BOTH tag-only and the floating tag is one defect with one
repair -- add the digest -- so it produces one finding, classified by the more
specific kind. The three kinds are separate finding ids because they are
separate defects, not because one string can satisfy two greps.

EXIT CODES (canonkit's contract, a design rule)
    0  every reference at every pull site is pinned
    1  at least one unpinned specifier, digest-less image, or floating tag
    2  it could not look: no pull site of any kind, or a population below the
       effective floor

VENDORING. Enumerated into the vendored set by tools/vendor.py's check-module
glob and copied to <artifact>/checks/check_08.py, beside <artifact>/canonkit.py.
Run BY PATH under a bare module name, never as a dotted package module. Stdlib
only, ASCII only.
"""

import argparse
import fnmatch
import importlib.util
import json
import os
import re
import sys

CHECK_ID = "CHECK-08"

# a design rule: the POPULATION floor, declared per-check IN CODE, overridable on the
# command line, and the EFFECTIVE value is what prints as `floor=`. One
# pin-relevant reference is the smallest population over which this means
# anything.
DEFAULT_FLOOR = 1

SCHEMA = "canonkit/check-08/1"

HERE = os.path.dirname(os.path.abspath(__file__))
CORE_ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------------------
# THE DECLARED SCOPE. Every glob this module will ever open, in one place, so a
# reader can reconcile the printed counts against the rules that produced them
# without reading the walk.
# ---------------------------------------------------------------------------

REQUIREMENTS_GLOBS = ("requirements*.txt",)
COMPOSE_GLOBS = ("docker-compose.yml", "docker-compose.yaml",
                 "compose.yml", "compose.yaml")
DOCKERFILE_GLOBS = ("Dockerfile", "Dockerfile.*", "*.Dockerfile", "*.dockerfile")
DRIVER_GLOBS = ("*.py", "*.sh")

# OUTPUTS, never inputs. Excluded by FILE SCOPE and counted -- see the false
# positive paragraph above.
RESULTS_DIR = "results"
PROVENANCE_NAME = "provenance.json"

# Never walked into. `results` is the exclusion that matters; the rest are
# caches and vendored trees that hold no pull site of this repository's making.
PRUNED_DIRS = (RESULTS_DIR, ".git", ".venv", "venv", "node_modules",
               "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
               ".reports")

# a design rule's mechanically locatable marker for the deliberately-broken tree.
BROKEN_PREFIX = "broken-"

# The banned floating tag, ASSEMBLED FROM PARTS so this module's own source is
# not a hit for a sweep that hunts it across the tree. templates/
# docker-compose.yml records that its first draft failed this check by quoting
# the string in a comment explaining the ban.
FLOATING_TAG = "lat" + "est"
FLOATING_REF = ":" + FLOATING_TAG

DIGEST_MARKER = "@sha256:"

IMAGE_RE = re.compile(r"^\s*image\s*:\s*(?P<ref>[^\s#]+)", re.I)
FROM_RE = re.compile(r"^\s*FROM\s+(?:--[a-z-]+=\S+\s+)*(?P<ref>\S+)", re.I)

# A pinned specifier. `===` is PEP 440's arbitrary-equality form and pins just as
# hard as `==`; `@` is a direct reference, which pins to a URL rather than a
# range and is treated as pinned when it carries a hash fragment.
PINNED_SPECIFIER_RE = re.compile(r"===?\s*[^\s,;]+")
DIRECT_REFERENCE_RE = re.compile(r"@\s*\S+#(sha256|md5)=")

SITE_SPECIFIER = "specifier"
SITE_IMAGE = "image"
SITE_TEXT = "text"

FINDING_UNPINNED = "unpinned-specifier"
FINDING_NO_DIGEST = "image-without-digest"
FINDING_FLOATING_TAG = FLOATING_TAG + "-tag"

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
    """The check-module contract (CheckResult, CheckContext).

    PREFERS AN ALREADY-LOADED COPY, for the reason check_03.py records.
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
# THE SCAN. Its scope is declared above and its counts are reported by run().
# ---------------------------------------------------------------------------


def matches_any(name, globs):
    return any(fnmatch.fnmatch(name, glob) for glob in globs)


def walk_scope(root, include_drivers=False):
    """Every pull-site file under `root`, WITH the counts the scan is judged by.

    Returns (sites, stats). A search's negative is only as strong as its pattern
    and its scope, so both are reported: `stats` carries the number of
    directories visited, the number pruned and why, and the file count per
    category. "No unpinned specifier found" then means something a reader can
    check rather than something they have to trust.
    """
    root = os.path.abspath(str(root))
    found = {"requirements": [], "compose": [], "dockerfile": [], "driver": []}
    stats = {"dirs_visited": 0, "dirs_pruned_broken": 0,
             "dirs_pruned_other": 0, "root": root,
             "drivers": "scanned" if include_drivers else "excluded"}

    for dirpath, dirnames, filenames in os.walk(root):
        stats["dirs_visited"] += 1
        keep = []
        for name in dirnames:
            if name in PRUNED_DIRS:
                stats["dirs_pruned_other"] += 1
                continue
            # DESCENDANTS only. The root itself is never pruned, so pointing the
            # check straight at a broken-* fixture still checks it.
            if name.startswith(BROKEN_PREFIX):
                stats["dirs_pruned_broken"] += 1
                continue
            keep.append(name)
        dirnames[:] = keep

        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if matches_any(name, REQUIREMENTS_GLOBS):
                found["requirements"].append(path)
            elif matches_any(name, COMPOSE_GLOBS):
                found["compose"].append(path)
            elif matches_any(name, DOCKERFILE_GLOBS):
                found["dockerfile"].append(path)
            elif include_drivers and matches_any(name, DRIVER_GLOBS):
                found["driver"].append(path)

    stats["files"] = {key: len(value) for key, value in found.items()}
    stats["file_count"] = sum(stats["files"].values())
    return found, stats


def provenance_records(root):
    """Every provenance record under results/, and the image entries it holds.

    The exclusion is COUNTED by reading these, not by ignoring the directory.
    An exclusion that does not print is an exclusion list that grows silently.
    """
    base = os.path.join(str(root), RESULTS_DIR)
    records = []
    entries = 0
    for dirpath, _dirnames, filenames in os.walk(base):
        for name in sorted(filenames):
            if name != PROVENANCE_NAME:
                continue
            path = os.path.join(dirpath, name)
            count = 0
            try:
                with open(path, "r", encoding="utf-8", newline="") as handle:
                    payload = json.loads(handle.read())
                images = payload.get("images")
                if isinstance(images, dict):
                    count = len(images)
                elif isinstance(images, list):
                    count = len(images)
            except (OSError, ValueError, AttributeError):
                count = 0
            records.append({"path": path, "entries": count})
            entries += count
    return records, entries


# ---------------------------------------------------------------------------
# Parsing one file into pin-relevant SITES
# ---------------------------------------------------------------------------


def read_lines(path):
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            return handle.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return []


def split_image(ref):
    """(name, tag, digest) for an image reference.

    Parsed rather than split on the first colon, because a registry host may
    carry a port -- `myregistry:5000/app:1.2` has two colons and only the second
    introduces a tag.
    """
    digest = ""
    if "@" in ref:
        ref, _, digest = ref.partition("@")
    last = ref.rsplit("/", 1)[-1]
    if ":" in last:
        name_tail, _, tag = last.rpartition(":")
        name = ref[:len(ref) - len(last)] + name_tail
    else:
        tag = ""
        name = ref
    return name, tag, digest


def requirement_sites(path, root):
    """One site per requirement specifier, with continuations joined.

    Lines beginning with `-` are pip OPTIONS (`-r`, `-e`, `--hash`,
    `--index-url`) rather than requirements, and are not pull sites of their own.
    """
    relative = os.path.relpath(path, root).replace(os.sep, "/")
    sites = []
    buffer = ""
    start = 0
    for number, raw in enumerate(read_lines(path), start=1):
        line = raw.split(" #", 1)[0].rstrip()
        if not buffer:
            start = number
        if line.endswith(chr(92)):
            buffer += line[:-1].strip() + " "
            continue
        joined = (buffer + line).strip()
        buffer = ""
        if not joined or joined.startswith("#") or joined.startswith("-"):
            continue
        sites.append({"file": relative, "line": start, "kind": SITE_SPECIFIER,
                      "text": joined})
    if buffer.strip():
        sites.append({"file": relative, "line": start, "kind": SITE_SPECIFIER,
                      "text": buffer.strip()})
    return sites


def image_sites(path, root):
    """One site per image reference, PLUS one per floating-tag occurrence
    anywhere else in the file.

    The whole-file arm is templates/docker-compose.yml's stated contract, and its
    reason is that a commented-out service is one uncomment away from being a
    pull site.
    """
    relative = os.path.relpath(path, root).replace(os.sep, "/")
    sites = []
    for number, raw in enumerate(read_lines(path), start=1):
        match = IMAGE_RE.match(raw) or FROM_RE.match(raw)
        if match:
            sites.append({"file": relative, "line": number, "kind": SITE_IMAGE,
                          "text": match.group("ref")})
            continue
        if FLOATING_REF in raw:
            sites.append({"file": relative, "line": number, "kind": SITE_TEXT,
                          "text": raw.strip()})
    return sites


def driver_sites(path, root):
    """Floating-tag occurrences in a driver script. Opt-in; see the docstring."""
    relative = os.path.relpath(path, root).replace(os.sep, "/")
    return [{"file": relative, "line": number, "kind": SITE_TEXT,
             "text": raw.strip()}
            for number, raw in enumerate(read_lines(path), start=1)
            if FLOATING_REF in raw]


def collect_sites(found, root):
    """Every pin-relevant site, in a stable order."""
    sites = []
    for path in found["requirements"]:
        sites.extend(requirement_sites(path, root))
    for path in found["compose"] + found["dockerfile"]:
        sites.extend(image_sites(path, root))
    for path in found["driver"]:
        sites.extend(driver_sites(path, root))
    return sites


# ---------------------------------------------------------------------------
# THE DETECTION. A pure function of the collected sites, so the RED commit stubs
# exactly this and the GREEN commit replaces exactly this.
# ---------------------------------------------------------------------------


def specifier_is_pinned(text):
    """True when a requirement line names EXACTLY ONE version.

    `==` and PEP 440's arbitrary-equality `===` both pin. A direct reference
    (`name @ url#sha256=...`) pins to bytes rather than to a range and counts.
    Everything else -- a range, a compatible-release `~=`, an exclusion, or no
    specifier at all -- leaves the resolver free to choose, which is the thing
    an earlier step is about: a floating specifier is a dependency-substitution surface.
    """
    body = text.split(";", 1)[0]
    if DIRECT_REFERENCE_RE.search(body):
        return True
    return bool(PINNED_SPECIFIER_RE.search(body))


def classify_image(ref):
    """(kind, detail_fragment) for one image reference, or (None, "") when pinned.

    ONE REFERENCE, ONE FINDING. A reference that is both digest-less AND the
    floating tag is one defect with one repair -- resolve the digest -- so the
    more specific kind wins rather than both firing. Emitting two findings for
    one string would make `found=` a count of rules that matched rather than of
    things that are wrong.
    """
    _name, tag, digest = split_image(ref)
    if digest.startswith("sha256:"):
        return None, ""
    if tag == FLOATING_TAG:
        return (FINDING_FLOATING_TAG,
                "resolves to whatever was pushed most recently, so the bytes "
                "this artifact measured cannot be re-obtained by anyone, "
                "including its author")
    if not tag:
        return (FINDING_FLOATING_TAG,
                "carries no tag at all, which the daemon resolves to the "
                "floating tag -- the same defect, written more quietly")
    return (FINDING_NO_DIGEST,
            "is pinned by the tag %r, and a tag is a moving target: it resolves "
            "to different bytes on different days, so \"the same benchmark\" "
            "can silently mean different software" % tag)


def pin_findings(sites):
    """Every reference at a pull site that does not name fixed bytes.

    A pure function of the collected sites -- no filesystem, no walk -- so what
    it decides is entirely a function of what it is handed, and the RED commit
    could stub exactly this while every measurement around it stayed live.

    Three kinds, three finding ids, each carrying the file and line so a repair
    is a place rather than a search:

        unpinned-specifier    a requirement that names a range, not a version
        image-without-digest  an image named by tag
        latest-tag            the floating tag, anywhere at a pull site
    """
    findings = []

    for site in sites:
        kind = None
        detail = ""

        if site["kind"] == SITE_SPECIFIER:
            if not specifier_is_pinned(site["text"]):
                kind = FINDING_UNPINNED
                detail = ("the specifier %r does not name exactly one version, "
                          "so the resolver chooses and two installs of this "
                          "artifact can differ. REPAIR: pin with == and, under "
                          "a design rule, a hash." % site["text"])

        elif site["kind"] == SITE_IMAGE:
            kind, fragment = classify_image(site["text"])
            if kind:
                detail = ("the image reference %r %s. REPAIR: resolve the digest "
                          "(docker buildx imagetools inspect <ref>) and pin "
                          "name@sha256:<digest>, pasting the value rather than a "
                          "shortened form of it." % (site["text"], fragment))

        elif site["kind"] == SITE_TEXT:
            kind = FINDING_FLOATING_TAG
            detail = ("the floating tag appears here, outside an image key. It "
                      "is banned ANYWHERE at a pull site because a commented-out "
                      "service is one uncomment away from being one. REPAIR: "
                      "resolve the digest, or describe the tag in words as "
                      "templates/docker-compose.yml does.")

        if not kind:
            continue

        findings.append({
            "kind": kind,
            "id": "pins:%s:%s:%d" % (kind, site["file"], site["line"]),
            "file": site["file"],
            "line": site["line"],
            "text": site["text"],
            "detail": detail,
        })

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
        for key in ("finding_id", "id"):
            value = waiver.get(key)
            if isinstance(value, str) and value:
                ids.add(value)
    return ids


def scope_note(stats, entries, sites=None):
    """The scan's SCOPE and its counts, printed on every path including refusal.

    THE REFUSAL PATH NEEDS THIS MOST, and that is the opposite of the intuition.
    A run that reports "no pull site of any kind" after PRUNING the directories
    that held them has stated a conclusion and withheld the fact that explains it
    -- and a reader has no way to tell "this tree declares no dependencies" from
    "I refused to look where they live". Measured while writing this module: a
    run rooted at fixtures/ refused with zero pull sites, and the note said
    nothing about the two broken-* trees it had just pruned.
    """
    # THE WORD IS `not-examined`, NEVER THE BANNED ONE. canonkit declares
    # BANNED_VERDICT because it "reads as deliberately and safely omitted" and is
    # how a zero population gets filed as a pass by a human reading the log;
    # conformance.py owns the `not-examined=` vocabulary and CHECK-11 fails a run
    # in which the banned word appears anywhere in a population line. This note
    # is appended to that line, so it is inside the ban -- MEASURED: the first
    # draft of this function spelled it the banned way and turned CHECK-11 red
    # across eight integration tests that had nothing to do with pins.
    parts = [
        "pull-sites checked %d file(s), provenance entries not-examined %d"
        % (stats["file_count"], entries),
    ]
    if sites is not None:
        parts.append(
            "references=%d (specifiers=%d images=%d text=%d)"
            % (len(sites),
               len([s for s in sites if s["kind"] == SITE_SPECIFIER]),
               len([s for s in sites if s["kind"] == SITE_IMAGE]),
               len([s for s in sites if s["kind"] == SITE_TEXT])))
    parts.append(
        "requirements=%d compose=%d dockerfile=%d drivers=%s"
        % (stats["files"]["requirements"], stats["files"]["compose"],
           stats["files"]["dockerfile"], stats["drivers"]))
    parts.append(
        "dirs visited=%d pruned=%d (%d %s*)"
        % (stats["dirs_visited"],
           stats["dirs_pruned_other"] + stats["dirs_pruned_broken"],
           stats["dirs_pruned_broken"], BROKEN_PREFIX))
    return " | ".join(parts)


def run(root, ctx=None, include_drivers=False):
    """Measure. Returns a CheckResult. DOES NOT PRINT -- the caller prints.

    `root` is an ARTIFACT directory in ordinary use and may equally be this
    repository's own root under a design rule's --self. Nothing here assumes the artifact
    layout: results/ is pruned whether or not it exists, and the pull-site globs
    are the same either way.
    """
    core = load_core()
    contract = load_contract()
    ctx = ctx if ctx is not None else contract.CheckContext()
    floor = ctx.floor_for(CHECK_ID, DEFAULT_FLOOR)
    root = os.path.abspath(str(root))

    def refused(note, detail=None):
        result = contract.CheckResult(
            check_id=CHECK_ID, code=core.EXIT_DID_NOT_RUN, found=0, checked=0,
            floor=floor, waived=0, note=note)
        base = {"root": root, "findings": [], "sites": [], "stats": {},
                "provenance_records": [], "provenance_entries": 0}
        base.update(detail or {})
        result.detail = base
        return result

    if not os.path.isdir(root):
        return refused("%s is not a directory" % root)

    found, stats = walk_scope(root, include_drivers=include_drivers)
    records, entries = provenance_records(root)

    if stats["file_count"] == 0:
        return refused(
            "no pull site of any kind under %s: no %s, no %s, no %s. There is "
            "nothing that causes a pull, so there is nothing to check for a pin. "
            "REPAIR: none needed unless this artifact does declare dependencies, "
            "in which case they are somewhere this scan's declared scope does "
            "not reach."
            % (root, "/".join(REQUIREMENTS_GLOBS), "/".join(COMPOSE_GLOBS[:2]),
               "/".join(DOCKERFILE_GLOBS[:2]))
            + " | " + scope_note(stats, entries),
            {"stats": stats, "provenance_records": records,
             "provenance_entries": entries})

    sites = collect_sites(found, root)
    findings = list(pin_findings(sites))

    waived_ids = waiver_ids(getattr(ctx, "waivers", None))
    kept = [finding for finding in findings if finding["id"] not in waived_ids]
    waived = len(findings) - len(kept)

    checked = len(sites)
    found_count = len(kept)
    if checked == 0 or checked < floor:
        code = core.EXIT_DID_NOT_RUN
    elif found_count:
        code = core.EXIT_FINDING
    else:
        code = core.EXIT_PASS

    note = scope_note(stats, entries, sites)

    result = contract.CheckResult(
        check_id=CHECK_ID, code=code, found=found_count, checked=checked,
        floor=floor, waived=waived, not_examined=entries, note=note,
        finding_ids=sorted({finding["id"] for finding in kept}))
    result.detail = {
        "root": root,
        "findings": kept,
        "sites": sites,
        "stats": stats,
        "provenance_records": records,
        "provenance_entries": entries,
    }
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_report(result, core):
    """The structured record, over stable fields only."""
    detail = getattr(result, "detail", {}) or {}
    stats = detail.get("stats", {}) or {}
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
        "root": detail.get("root", ""),
        "pull_site_files": stats.get("file_count", 0),
        "files_by_category": stats.get("files", {}),
        "dirs_visited": stats.get("dirs_visited", 0),
        "dirs_pruned_broken": stats.get("dirs_pruned_broken", 0),
        "dirs_pruned_other": stats.get("dirs_pruned_other", 0),
        "drivers": stats.get("drivers", "excluded"),
        "provenance_records": list(detail.get("provenance_records", [])),
        "provenance_entries": detail.get("provenance_entries", 0),
        "sites": list(detail.get("sites", [])),
        "findings": detail.get("findings", []),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_08",
        description="CHECK-08: fails on any unpinned dependency specifier, any "
                    "image reference lacking a digest, and the floating tag "
                    "anywhere at a pull site. Provenance records are OUTPUTS "
                    "and are excluded by file scope, and the exclusion is "
                    "counted and printed.")
    parser.add_argument("root", nargs="?", default=".",
                        help="the artifact directory, or this repository's own "
                             "root under a design rule (default: the current one)")
    parser.add_argument("--include-drivers", action="store_true",
                        help="also scan driver scripts (%s) for the floating "
                             "tag. OFF by default -- see the module docstring "
                             "for the two reasons. The scope PRINTS either way."
                             % ", ".join(DRIVER_GLOBS))
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

    result = run(args.root, ctx, include_drivers=args.include_drivers)

    core.report(CHECK_ID, result.code == core.EXIT_PASS, result.found,
                result.checked, result.floor, waived=result.waived,
                note=result.note, not_examined=result.not_examined, listed=result.listed)

    if result.checked and result.checked < result.floor:
        print("  DEMOTED to DID-NOT-RUN: population %d is below the effective "
              "floor %d." % (result.checked, result.floor))

    detail = getattr(result, "detail", {}) or {}
    for record in detail.get("provenance_records", []):
        print("  not-examined (output) %s: %d image entry(ies), excluded because "
              "a provenance record DOCUMENTS a resolution rather than causing a "
              "pull" % (record["path"], record["entries"]))
    for finding in detail.get("findings", [])[:MAX_LISTED_FINDINGS]:
        print("  %-22s %s:%d: %s" % (finding["kind"], finding["file"],
                                     finding["line"], finding["detail"]))
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
