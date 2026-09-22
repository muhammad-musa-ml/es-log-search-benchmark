"""CHECK-05 -- a missing register row, reported as `expected N, found M`.

    python check_05.py <artifact> [--register FILE] [--manifest FILE]
                                  [--artifacts-root DIR] [--report FILE]
                                  [--min-population N]

the project requirements document states the check verbatim: "Fails on a missing register row,
reported as `expected N, found M`."

THE EXPECTED NUMBER IS READ, NEVER TYPED
-----------------------------------------
`counts.register_rows_expected` is read from tools/manifest.json at run time.
That number is NOT written into this file, and a grep gate in the plan's
acceptance criteria asserts it is absent from this source. The reason is a design rule's
derive-and-assert shape seen from the other side: the manifest already holds a
committed literal asserted against its own derivation (the slugs carrying
`register_row: true`), so the manifest is the tripwire. A second copy of the
number HERE would be a third value that can drift from both, and the drift would
be invisible -- a checker agreeing with itself.

So this module's contribution is to ASSERT the manifest's literal against the
manifest's own derivation on every run, and to report both numbers. If the two
disagree, THAT disagreement is the finding, never a value to pick between.

A SET COMPARISON, NOT A COUNT COMPARISON, AND THIS IS THE LOAD-BEARING CHOICE
------------------------------------------------------------------------------
`expected N, found M` reads like a count, and a check that compared only counts
would report a clean run over a register that carries the right NUMBER of rows
with the WRONG SLUG in one of them. That is a defect a reader of the register
would be actively misled by, so the comparison here is over the SLUG SETS and
the counts are derived from the sets:

    missing-row   a slug the manifest expects, absent from the register
    extra-row     a row in the register for a slug the manifest does not expect

The second is not in the requirement's wording. It is here because it is the
inverse half of the same question, it costs nothing, and without it the set
comparison collapses back into a count comparison the moment the two errors
cancel.

"COULD NOT LOOK" VERSUS "FOUND A PROBLEM"
--------------------------------------------------
    no register document reachable
        -> code 2, DID-NOT-RUN. This is the LIVE state of the programme today
           and it is CORRECT rather than a defect: `tools/build_register.py`
           refuses to publish a register until at least one artifact carries a
           figures record, and at the time this module was written that count
           was zero. Reporting every expected row as "missing" against a
           register nobody has generated yet would be a wall of findings about
           an absence that is scheduled, not broken. Reporting a PASS would be
           worse. The check says it could not look, and says why.
    a register that EXISTS and is short a row
        -> code 1. The document IS the register and the row is not in it.

`expected 0, found 0` IS REFUSED OUTRIGHT
-------------------------------------------
An expected set of zero produces a comparison in which everything agrees and
nothing was checked. It is the 0/0 pass wearing the phrasing of a real result,
and it is the exact failure mode the population floor exists to catch -- so this
module refuses a population of zero UNCONDITIONALLY, before the floor is even
consulted. A caller passing `--min-population 0` cannot talk it into a pass.

THE `status` FIELD
----------------------------------------------------
tools/manifest.json carries a per-slug `status` of `built` or `pending`, a
ratified extension to HARD a design rule. Three rules keep the field from becoming a
silencer, and all three are implemented here:

    a `pending` slug whose directory EXISTS   -> a FINDING. The manifest is
                                                 stale: something was built and
                                                 the expected set was not told.
    a `built` slug whose directory is MISSING -> a FINDING. The manifest claims
                                                 a build that is not on disk.
    `pending` reaching zero                   -> printed as a project requirement's closeout
                                                 criterion, so the milestone is
                                                 read off the run rather than
                                                 tracked by hand.

`status` IS OWNER-SET AND PLAN-SET, NEVER BUILD-AGENT-SET. This module READS the
field and never writes it, exactly the posture a design rule gives waivers. A checker the
thing being checked can edit is not a checker.

THE POPULATION THIS CHECK COVERED IS PRINTED, INCLUDING THE ROOTS IT RESOLVED
------------------------------------------------------------------------------
Measured in this phase, twice: a guard anchored on a repository-relative path
ran over 2 directories instead of 25 from inside an agent worktree and PASSED,
because its vacuity check only fired at zero. A count that is present but wrong
reads as detail where a missing one would have read as a question.

This check's population is the manifest's expected SET -- a committed list, not
a filesystem scan -- so it cannot shrink that way. But its `status` arm DOES
touch the filesystem, so the resolved artifacts root and the number of
directories probed are both printed, and a reader can reconcile them without
reading this file.

EXIT CODES (canonkit's contract, a design rule)
    0  every expected row present, no stale-pending, no missing-built
    1  at least one of the finding kinds above. The check DID look.
    2  it could not look: no manifest, no register, an expected set of zero, or
       a population below the effective floor.

VENDORING. Enumerated into the vendored set by tools/vendor.py's check-module
glob and copied to <artifact>/checks/check_05.py, beside <artifact>/canonkit.py.
A VENDORED COPY CANNOT REACH tools/manifest.json -- an artifact has no tools/
directory -- so a vendored run refuses with code 2 and a message naming the
missing expected set, rather than inventing one. Run BY PATH under a bare module
name, never as a dotted package module. Stdlib only, ASCII only.
"""

import argparse
import importlib.util
import json
import os
import re
import sys

CHECK_ID = "CHECK-05"

# a design rule: the POPULATION floor, declared per-check IN CODE, overridable on the
# command line, and the EFFECTIVE value is what prints as `floor=`. One expected
# row is the smallest population over which this check means anything.
DEFAULT_FLOOR = 1

SCHEMA = "canonkit/check-05/1"

HERE = os.path.dirname(os.path.abspath(__file__))

# `tools/` in this repository, `<artifact>/` in a vendored copy. ONE expression
# for both layouts: the checks package always sits one directory below the core.
CORE_ROOT = os.path.dirname(HERE)

# The repository root in this repository; the ARTIFACTS root in a vendored copy.
# The manifest lookup below therefore resolves in this repository and resolves to
# a path that does not exist inside an artifact, which is the intended refusal.
SOURCE_ROOT = os.path.dirname(CORE_ROOT)

REGISTER_NAME = "backing-artifacts.md"
MANIFEST_RELATIVE = os.path.join("tools", "manifest.json")

STATUS_BUILT = "built"
STATUS_PENDING = "pending"

# A register ROW is an H2 whose text is a bare slug. `## Excluded slugs`
# is an H2 and is deliberately NOT matched -- it carries spaces, brackets and
# capitals, none of which a slug may hold. `### Similarity judgment` is an H3 and
# fails the `##` + whitespace shape.
ROW_RE = re.compile(r"^##[ \t]+(?P<slug>[a-z0-9][a-z0-9-]*)[ \t]*$", re.M)

FINDING_MISSING_ROW = "missing-row"
FINDING_EXTRA_ROW = "extra-row"
FINDING_STALE_PENDING = "stale-pending"
FINDING_MISSING_BUILT = "missing-built"
FINDING_MANIFEST_DRIFT = "manifest-drift"

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

    PREFERS AN ALREADY-LOADED COPY, for the reason check_03.py records: a runner
    that loaded the package holds one class object, and loading __init__.py by
    path a second time would mint a SECOND CheckResult class that the runner
    would reject as foreign despite being structurally identical.
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
# Reading the expected set and the register
# ---------------------------------------------------------------------------


def default_manifest_path():
    return os.path.join(SOURCE_ROOT, MANIFEST_RELATIVE)


def read_manifest(path):
    """The expected set. Raises CheckRefusal -- every refusal is a code 2."""
    path = str(path)
    if not os.path.isfile(path):
        raise CheckRefusal(
            "no expected set at %s, so there is nothing to compare the register "
            "against. A vendored copy inside an artifact cannot reach one -- an "
            "artifact has no tools/ directory -- and inventing a number here "
            "would make `expected N, found M` two derived values agreeing with "
            "each other. REPAIR: pass --manifest, or run from the tooling "
            "repository." % path)
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            payload = json.loads(handle.read())
    except (OSError, ValueError) as error:
        raise CheckRefusal("%s could not be read as JSON: %s" % (path, error))
    if not isinstance(payload, dict) or not isinstance(payload.get("slugs"), list):
        raise CheckRefusal(
            "%s carries no slugs[]. An expected set with no members produces a "
            "comparison in which everything agrees and nothing was checked."
            % path)
    return payload


def expected_literal(manifest, path):
    """`counts.register_rows_expected`, READ. Raises CheckRefusal when absent."""
    counts = manifest.get("counts") or {}
    value = counts.get("register_rows_expected")
    if not isinstance(value, int):
        raise CheckRefusal(
            "%s carries no counts.register_rows_expected. That committed "
            "literal is the tripwire on the derivation's own input; without it "
            "`expected N, found M` is two derived numbers agreeing with each "
            "other." % path)
    return value


def expected_slugs(manifest):
    """The slugs the manifest says MUST carry a register row."""
    return sorted(
        str(slug.get("slug")) for slug in manifest["slugs"]
        if isinstance(slug, dict) and slug.get("register_row") and slug.get("slug"))


def excluded_slugs(manifest):
    """The slugs deliberately outside the expected set, WITH their reasons.

    An excluded input that is not counted and not given a reason is an input
    that was silently dropped, which is the shape a growing exclusion list hides
    inside.
    """
    out = []
    for slug in manifest["slugs"]:
        if not isinstance(slug, dict) or slug.get("register_row"):
            continue
        name = slug.get("slug")
        if not name:
            continue
        out.append({
            "slug": str(name),
            "reason": str(slug.get("no_row_reason")
                          or "no reason recorded in the expected set"),
        })
    return sorted(out, key=lambda item: item["slug"])


def status_facts(manifest, artifacts_root):
    """Per-slug `status` beside whether that slug's DIRECTORY exists.

    The only filesystem read this check performs, and both the root it resolved
    and the number of directories probed are reported by run().
    """
    root = str(artifacts_root)
    facts = []
    for slug in manifest["slugs"]:
        if not isinstance(slug, dict) or not slug.get("slug"):
            continue
        name = str(slug["slug"])
        facts.append({
            "slug": name,
            "status": str(slug.get("status") or ""),
            "directory_exists": os.path.isdir(os.path.join(root, name)),
        })
    return sorted(facts, key=lambda item: item["slug"])


def resolve_register(artifact, artifacts_root, explicit=None):
    """Where the register document is, in declared order, or None.

    THE ORDER MATTERS AND THE SECOND ENTRY IS THE ONE THAT IS EASY TO MISS. The
    register's published copy sits at the ARTIFACTS ROOT'S OWN ROOT, beside the
    artifact directories rather than inside one of them. A resolver that only
    looked under <artifacts-root>/<slug>/ would report a confident "no register"
    against a register that is present -- the scope half of the measured
    search-negative failure, where a glob at <dir>/<x>/<y>/ silently excludes the
    aggregate file at <dir>'s own root.
    """
    if explicit:
        return os.path.abspath(str(explicit))
    candidates = [
        os.path.join(str(artifacts_root), REGISTER_NAME),
        os.path.join(SOURCE_ROOT, REGISTER_NAME),
        os.path.join(str(artifact), REGISTER_NAME),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def register_rows(text):
    """Every slug the register carries a row for, in document order."""
    return [match.group("slug") for match in ROW_RE.finditer(text)]


# ---------------------------------------------------------------------------
# THE DETECTION. Isolated in one function so the RED commit stubs exactly this
# and the GREEN commit replaces exactly this.
# ---------------------------------------------------------------------------


def _drift(name, literal, derived, consequence):
    return {
        "kind": FINDING_MANIFEST_DRIFT,
        "id": "register:%s:%s" % (FINDING_MANIFEST_DRIFT, name),
        "slug": "counts.%s" % name,
        "detail": "the expected set's committed literal says %r but %d slug(s) "
                  "derive. %s THAT disagreement is the finding, never a value to "
                  "pick between. REPAIR: update BOTH in the same commit."
                  % (literal, derived, consequence),
    }


def register_findings(expected, rows, facts, literal, derived,
                      built_literal, built_derived,
                      pending_literal, pending_derived):
    """Every way the register and the expected set can disagree.

    Isolated here so the RED commit stubs exactly this and the GREEN commit
    replaces exactly this. Takes only values -- no filesystem, no manifest
    reading -- so what it decides is entirely a function of what it is handed.

    FIVE KINDS, in the order a reader wants them:

      manifest-drift  the expected set disagrees with ITSELF, so every number
                      below it is suspect. Reported first for that reason.
      missing-row     a slug the manifest expects, absent from the register.
                      The requirement.
      extra-row       a row for a slug the manifest does not expect. The inverse
                      half, without which the set comparison collapses back into
                      a count comparison the moment two errors cancel.
      stale-pending   the status rule, rule one.
      missing-built   the status rule, rule two.
    """
    findings = []

    # a design rule read from both ends. A derived count silently stops checking when a
    # slug is dropped, because expected falls to match found; the literal is the
    # tripwire on the derivation's own input. Reported FIRST because a manifest
    # that disagrees with itself makes every count under it suspect.
    if literal != derived:
        findings.append(_drift(
            "register_rows_expected", literal, derived,
            "The register comparison below was made against the DERIVED set."))
    if isinstance(built_literal, int) and built_literal != built_derived:
        findings.append(_drift(
            "built_expected", built_literal, built_derived,
            "The `built` arm of the status rule was applied to the DERIVED set."))
    if isinstance(pending_literal, int) and pending_literal != pending_derived:
        findings.append(_drift(
            "pending_expected", pending_literal, pending_derived,
            "The `pending` arm of the status rule was applied to the DERIVED set."))

    present = set(rows)
    wanted = set(expected)

    for slug in sorted(wanted - present):
        findings.append({
            "kind": FINDING_MISSING_ROW,
            "id": "register:%s:%s" % (FINDING_MISSING_ROW, slug),
            "slug": slug,
            "detail": "the expected set marks this slug `register_row: true` and "
                      "the register carries no `## %s` row for it. A register "
                      "short a row reads as a complete one. REPAIR: regenerate "
                      "the register, or record a no_row_reason if the slug "
                      "genuinely backs no bullet." % slug,
        })

    for slug in sorted(present - wanted):
        findings.append({
            "kind": FINDING_EXTRA_ROW,
            "id": "register:%s:%s" % (FINDING_EXTRA_ROW, slug),
            "slug": slug,
            "detail": "the register carries a row for this slug and the expected "
                      "set does not name it. Nothing reconciles such a row "
                      "against the canons, and its presence keeps the ROW COUNT "
                      "right while the ROW SET is wrong -- which is the state a "
                      "count comparison reports as clean. REPAIR: add the slug "
                      "to the expected set, or remove the row.",
        })

    # The status rule's anti-silencer rules. `status` is owner-set and plan-set; this
    # module reads it and never writes it. Both directions are checked, because
    # a field that only fired in one direction could be set to the other value to
    # make the check stop looking.
    for fact in facts:
        if fact["status"] == STATUS_PENDING and fact["directory_exists"]:
            findings.append({
                "kind": FINDING_STALE_PENDING,
                "id": "register:%s:%s" % (FINDING_STALE_PENDING, fact["slug"]),
                "slug": fact["slug"],
                "detail": "the expected set marks this slug `pending` and its "
                          "directory EXISTS. Something was built and the expected "
                          "set was not told, so every count derived from `status` "
                          "is now stale. REPAIR: an owner or plan sets status to "
                          "`built`. A build agent must never set this field.",
            })
        elif fact["status"] == STATUS_BUILT and not fact["directory_exists"]:
            findings.append({
                "kind": FINDING_MISSING_BUILT,
                "id": "register:%s:%s" % (FINDING_MISSING_BUILT, fact["slug"]),
                "slug": fact["slug"],
                "detail": "the expected set marks this slug `built` and no "
                          "directory for it exists at the artifacts root. The "
                          "manifest claims a build that is not on disk. REPAIR: "
                          "build it, or an owner corrects the status.",
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


def run(artifact, ctx=None, manifest_path=None, register_path=None,
        artifacts_root=None):
    """Measure. Returns a CheckResult. DOES NOT PRINT -- the caller prints."""
    core = load_core()
    contract = load_contract()
    ctx = ctx if ctx is not None else contract.CheckContext()
    floor = ctx.floor_for(CHECK_ID, DEFAULT_FLOOR)
    artifact = os.path.abspath(str(artifact))
    root = (os.path.abspath(str(artifacts_root)) if artifacts_root
            else os.path.dirname(artifact))

    def refused(note, detail=None):
        result = contract.CheckResult(
            check_id=CHECK_ID, code=core.EXIT_DID_NOT_RUN, found=0, checked=0,
            floor=floor, waived=0, note=note)
        base = {
            "artifact": artifact, "artifacts_root": root, "register": "",
            "manifest": "", "expected": 0, "found_rows": 0, "excluded": [],
            "built": 0, "pending": 0, "slugs_probed": 0, "findings": [],
        }
        base.update(detail or {})
        result.detail = base
        return result

    # THE RUNNER'S OWN COPY WINS WHEN IT HAS ONE. conformance.py resolves the
    # expected set once and hands it to every check through
    # CheckContext(manifest=...); re-reading it from disk here would give the
    # check a SECOND source of truth that can disagree with the one the runner
    # printed its scan root from -- and the disagreement would be silent, because
    # both reads succeed. An explicit --manifest still wins over both, because a
    # caller naming a file means it.
    explicit = manifest_path is not None
    supplied = getattr(ctx, "manifest", None)
    usable_supplied = (isinstance(supplied, dict)
                       and isinstance(supplied.get("slugs"), list)
                       and bool(supplied["slugs"]))

    if explicit:
        manifest_path = os.path.abspath(str(manifest_path))
    elif usable_supplied:
        manifest_path = "the expected set supplied by the runner"
    else:
        manifest_path = default_manifest_path()

    try:
        if explicit or not usable_supplied:
            manifest = read_manifest(manifest_path)
        else:
            manifest = supplied
        literal = expected_literal(manifest, manifest_path)
    except CheckRefusal as refusal:
        return refused(str(refusal), {"manifest": manifest_path})

    expected = expected_slugs(manifest)
    derived = len(expected)
    excluded = excluded_slugs(manifest)
    facts = status_facts(manifest, root)

    built_derived = len([f for f in facts if f["status"] == STATUS_BUILT])
    pending_derived = len([f for f in facts if f["status"] == STATUS_PENDING])
    counts = manifest.get("counts") or {}
    built_literal = counts.get("built_expected")
    pending_literal = counts.get("pending_expected")

    # a design rule, and the answer to an earlier plan open item 9: THIS CHECK ASKS ABOUT THE
    # ARTIFACT IT WAS HANDED.
    #
    # It used to ask whether the whole expected set was present in the register,
    # which is a PROGRAMME-level question -- and it printed the same
    # expected-versus-found pair on every artifact, because the paths nobody has
    # built yet cannot be made to appear by anything a built one does. (No count
    # is spelled in this comment on purpose: a literal here is a third copy of a
    # number that is READ from the manifest, and test_the_expected_count_is_not_
    # typed_into_the_check_source greps this file for exactly that.)
    # A check whose output
    # is the same whatever it is pointed at has not examined what it was pointed
    # at, and a project requirement needs both existing artifacts to reach EXIT=0.
    #
    # The slug comes from the runner when there is one. There is NOT always one:
    # main() below builds a CheckContext with no artifact_slug, which is how the
    # CLI and every test in test_check_05.py invoke this module, so an empty
    # context falls back to the directory's own name -- the same derivation
    # conformance.py's self_module_check uses. Reading it off the path keeps the
    # CLI and the runner answering the same question.
    slug_under_test = (getattr(ctx, "artifact_slug", "") or "").strip()
    if not slug_under_test:
        slug_under_test = os.path.basename(artifact.rstrip("/" + chr(92)))

    # The twelve-row programme count does NOT disappear; it stops being this
    # check's verdict and becomes a structured field a project requirement reads at closeout.
    # Dropping it would be a narrower scope hiding the wider fact.
    programme = {
        "expected": derived,
        "expected_literal": literal,
        "built": built_derived,
        "pending": pending_derived,
        "slugs_probed": len(facts),
        "slug_under_test": slug_under_test,
    }

    # The 0/0 refusal, BEFORE the floor is consulted. An expected set of zero
    # produces a comparison in which everything agrees and nothing was checked,
    # and no --min-population value may talk this check into calling that a pass.
    if derived == 0 or literal == 0:
        return refused(
            "the expected set holds no slug carrying a register row (literal %d, "
            "derived %d), so `expected 0, found 0` would be a comparison over "
            "nothing wearing the phrasing of a result. REPAIR: an expected set "
            "with at least one register_row slug."
            % (literal, derived),
            {"manifest": manifest_path, "expected": 0,
             "excluded": excluded, "slugs_probed": len(facts),
             "built": built_derived, "pending": pending_derived})

    # THE SECOND REFUSAL, and it is the per-artifact half of the one above.
    #
    # A directory whose slug no expected set names is not an artifact this check
    # can judge. Passing would be a verdict over a slug that does not exist --
    # the 0/0 pass wearing a directory name -- so it refuses, and it names the
    # slug so the reason is actionable rather than a shrug.
    #
    # NOTE FOR AN EARLIER PLAN, because this branch is deliberately WIDER than it
    # eventually should be: a slug carrying `register_row: false` AND a recorded
    # `no_row_reason` is a CORRECT state, not a defect -- `example-search-benchmark`
    # is the live one. expected_slugs() filters the expected set on a truthy
    # `register_row`, so such a slug is not in `expected` at all and lands here,
    # returning 2 for something that is right. That is NOT repaired in this
    # module: an in-module exemption returns 2 and the aggregate lifts it to 1,
    # which is the defect the per-artifact NOT-APPLICABLE mechanism exists to
    # avoid. an earlier plan declares CHECK-05 a member of that mechanism and decides
    # applicability BEFORE this module runs. Until then es-log refuses here, and
    # that is the expected intermediate state.
    if slug_under_test not in set(expected):
        return refused(
            "`%s` is not a slug this expected set names as carrying a register "
            "row, so there is no row for this artifact to be judged against. A "
            "verdict here would be a comparison over a slug that does not "
            "exist. The programme-level figures are recorded in this result's "
            "detail rather than thrown away: expected %d, built %d, pending %d "
            "over %d probed slug(s). REPAIR: point the check at an artifact the "
            "expected set names, or add this slug to it -- and if the slug "
            "genuinely backs no bullet, that is a `register_row: false` plus a "
            "recorded `no_row_reason`, which the runner's applicability "
            "mechanism handles rather than this module."
            % (slug_under_test, derived, built_derived, pending_derived,
               len(facts)),
            dict(programme, manifest=manifest_path, excluded=excluded))

    register = resolve_register(artifact, root, register_path)
    if register is None:
        return refused(
            "no %s is reachable from %s, so there is no register to compare "
            "against. This is the programme's CORRECT state until an artifact "
            "has actually run: tools/build_register.py refuses to publish a "
            "register while no artifact carries a figures record. Reporting %d "
            "missing rows against a document nobody has generated would be a "
            "wall of findings about a scheduled absence. REPAIR: run an "
            "artifact, then generate the register."
            % (REGISTER_NAME, root, derived),
            {"manifest": manifest_path, "expected": derived,
             "excluded": excluded, "slugs_probed": len(facts),
             "built": built_derived, "pending": pending_derived})

    try:
        with open(register, "r", encoding="utf-8", newline="") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as error:
        return refused(
            "%s could not be read as UTF-8 (%s)" % (register, error),
            {"manifest": manifest_path, "register": register,
             "expected": derived, "excluded": excluded,
             "slugs_probed": len(facts),
             "built": built_derived, "pending": pending_derived})

    rows = register_rows(text)

    programme_findings = list(register_findings(
        expected, rows, facts, literal, derived,
        built_literal, built_derived, pending_literal, pending_derived))

    # WHAT "SCOPED" MEANS HERE, DECIDED BY KIND RATHER THAN BY SLUG.
    #
    # The question this check now asks is "is THIS artifact's register row
    # present and correct". Exactly ONE finding kind is a property of that row.
    # The other four are properties of the EXPECTED SET or of the register as a
    # whole, and scoping them to an artifact would not narrow them -- it would
    # DELETE them, because no per-artifact run can reach them. The full ruling,
    # with the reasoning that lost, is in the scope decision.
    #
    #   missing-row     SCOPED. This artifact's own row, absent. It is also the
    #                   kind that made the check useless: eleven paths nobody
    #                   has built carry no rows, so every artifact failed for a
    #                   reason none of them could fix.
    #
    #   extra-row       PROGRAMME. A row for a slug the expected set does not
    #                   name. It can never be ABOUT the slug under test -- such a
    #                   slug refuses above, before reaching here -- so scoping it
    #                   by slug deletes the check outright.
    #
    #   missing-built   PROGRAMME, and this one is structural: the finding says a
    #                   slug marked built has NO DIRECTORY. There is nothing to
    #                   point a per-artifact run at, so if this is not reported
    #                   from someone else's run it is never reported at all.
    #
    #   stale-pending   PROGRAMME. The status rule's other anti-silencer. Both arms are
    #                   checked precisely so a status cannot be flipped to make
    #                   the check stop looking; keeping only one arm per-artifact
    #                   would restore exactly that hole.
    #
    #   manifest-drift  PROGRAMME. The expected set disagrees with ITSELF, which
    #                   makes every count below it suspect -- including the one
    #                   this artifact's verdict is derived from. It carries a
    #                   synthetic `counts.<name>` slug, so it is unreachable by a
    #                   slug comparison anyway.
    #
    # The honest consequence, stated rather than hidden: two artifacts can still
    # share a programme-level finding, so their reports are not disjoint. What
    # they no longer share is a verdict driven by paths nobody has built, which
    # is what a project requirement was blocked on.
    SCOPED_KINDS = (FINDING_MISSING_ROW,)

    def in_scope(finding):
        if finding.get("kind") not in SCOPED_KINDS:
            return True
        return finding.get("slug") == slug_under_test

    findings = [f for f in programme_findings if in_scope(f)]
    out_of_scope = len(programme_findings) - len(findings)

    waived_ids = waiver_ids(getattr(ctx, "waivers", None))
    kept = [finding for finding in findings if finding["id"] not in waived_ids]
    waived = len(findings) - len(kept)

    # ONE row is what this check now examines: this artifact's own.
    checked = 1
    found = len(kept)
    if checked == 0 or checked < floor:
        code = core.EXIT_DID_NOT_RUN
    elif found:
        code = core.EXIT_FINDING
    else:
        code = core.EXIT_PASS

    # BOTH numbers, on one line, as separate facts. The verdict is this
    # artifact's row; the programme counts are printed beside it because a
    # narrower scope that hides the wider fact is the population line lying by
    # omission. `programme-findings-not-mine` is printed too, so a reader can
    # see that findings were EXCLUDED rather than that none existed.
    # EVERY PUBLISHED PHRASE OF THE OLD NOTE IS PRESERVED VERBATIM in the
    # programme section. Re-scoping the VERDICT is this plan's job; retiring
    # vocabulary other modules match on is not, and doing both at once would
    # make a needle failure indistinguishable from a scoping failure.
    #
    # The five consumers were enumerated rather than discovered one failure at a
    # time: `expected N,` and `rows N of N` and `excluded: N (reasons recorded)`
    # and `pending reached 0` in test_check_05.py, and `expected N, found N` in
    # test_skeleton_roundtrip.py's round trip.
    #
    # `found %d` and `rows %d of %d` do say the same thing twice. That is
    # deliberate: they are two separately published spellings of one fact, read
    # by two different modules, and collapsing them to save a few characters
    # would break one reader to tidy a line nobody measures.
    note = ("row %s: %s | this artifact 1 row checked, %d finding(s) "
            "| programme: expected %d, found %d, rows %d of %d, "
            "built %d of %d, pending %d"
            ", other slugs' findings not counted here: %d "
            "| excluded: %d (reasons recorded) | artifacts-root=%s slugs-probed=%d"
            % (slug_under_test,
               "present" if slug_under_test in set(rows) else "MISSING",
               found, derived, len(rows), len(rows), derived,
               built_derived, len(facts),
               pending_derived, out_of_scope, len(excluded),
               root.replace(chr(92), "/"), len(facts)))
    if pending_derived == 0:
        note += " | pending reached 0: a project requirement's closeout criterion is met"

    result = contract.CheckResult(
        check_id=CHECK_ID, code=code, found=found, checked=checked, floor=floor,
        waived=waived, not_examined=len(excluded), note=note,
        finding_ids=sorted({finding["id"] for finding in kept}))
    result.detail = {
        "artifact": artifact,
        "artifacts_root": root,
        "register": register,
        "manifest": manifest_path,
        "expected": derived,
        "expected_literal": literal,
        "found_rows": len(rows),
        "rows": rows,
        "excluded": excluded,
        "built": built_derived,
        "pending": pending_derived,
        # The same two numbers under the names a project requirement's closeout assertion
        # reads. They are ADDED rather than renamed: `built` and `pending` are
        # already read by this module's own tests and by the runner's report, and
        # a rename to satisfy a new reader would break an existing one.
        "built_derived": built_derived,
        "pending_derived": pending_derived,
        "slug_under_test": slug_under_test,
        "programme_findings_not_mine": out_of_scope,
        "slugs_probed": len(facts),
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
        "expected": detail.get("expected", 0),
        "expected_literal": detail.get("expected_literal", 0),
        "found_rows": detail.get("found_rows", 0),
        "rows": list(detail.get("rows", [])),
        "excluded": list(detail.get("excluded", [])),
        "built": detail.get("built", 0),
        "pending": detail.get("pending", 0),
        "built_derived": detail.get("built_derived", detail.get("built", 0)),
        "pending_derived": detail.get("pending_derived", detail.get("pending", 0)),
        "slug_under_test": detail.get("slug_under_test", ""),
        "programme_findings_not_mine": detail.get("programme_findings_not_mine", 0),
        "slugs_probed": detail.get("slugs_probed", 0),
        "register": detail.get("register", ""),
        "manifest": detail.get("manifest", ""),
        "artifacts_root": detail.get("artifacts_root", ""),
        "findings": detail.get("findings", []),
        "artifact": detail.get("artifact", ""),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_05",
        description="CHECK-05: fails on a missing register row, reported as "
                    "`expected N, found M`.")
    parser.add_argument("artifact", nargs="?", default=".",
                        help="the artifact directory (default: the current one)")
    parser.add_argument("--register", default=None,
                        help="the register document. Default: %s at the "
                             "artifacts root, then at the source root."
                             % REGISTER_NAME)
    parser.add_argument("--manifest", default=None,
                        help="the expected set. Default: tools/manifest.json "
                             "beside this module's core.")
    parser.add_argument("--artifacts-root", default=None,
                        help="the directory holding the artifact slugs. "
                             "Default: the artifact's parent.")
    parser.add_argument("--report", default=None,
                        help="write the structured report here. A file "
                             "rather than a stream a caller has to capture: a "
                             "command joined to another process reports the "
                             "other process's exit status.")
    parser.add_argument("--min-population", type=int, default=None,
                        help="override the effective POPULATION floor. "
                             "The OVERRIDDEN value is what prints as floor=. It "
                             "cannot produce a pass over a population of zero.")
    args = parser.parse_args(argv)

    core = load_core()
    contract = load_contract()

    overrides = {}
    if args.min_population is not None:
        overrides[CHECK_ID] = args.min_population
    ctx = contract.CheckContext(floor_overrides=overrides)

    result = run(args.artifact, ctx, manifest_path=args.manifest,
                 register_path=args.register,
                 artifacts_root=args.artifacts_root)

    core.report(CHECK_ID, result.code == core.EXIT_PASS, result.found,
                result.checked, result.floor, waived=result.waived,
                note=result.note, not_examined=result.not_examined, listed=result.listed)

    if result.checked and result.checked < result.floor:
        print("  DEMOTED to DID-NOT-RUN: population %d is below the effective "
              "floor %d." % (result.checked, result.floor))

    detail = getattr(result, "detail", {}) or {}
    for item in detail.get("excluded", []):
        print("  excluded             %s: %s" % (item["slug"], item["reason"]))
    for finding in detail.get("findings", [])[:MAX_LISTED_FINDINGS]:
        print("  %-20s %s: %s" % (finding["kind"], finding["slug"],
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
