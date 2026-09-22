"""The conformance runner: populations, aggregation, waivers, extras, the report.

    python conformance.py <artifact> [--report FILE] [--min-population CHECK-NN=N]
    python conformance.py --scan [--scan-root DIR] [--report FILE]
    python conformance.py --self [--report FILE]

Capture a run with a redirection and read the file, never with a pipe:

    python conformance.py <artifact> --report out.json > run.txt 2>&1; echo "EXIT=$?"

A command piped into another process reports the PIPE's exit status rather than
its own, so a failing run then reads as EXIT=0. That trap is why a design rule makes the
structured report a FILE rather than something a caller is expected to capture
off a stream, and why no instruction in this file's help text ever builds a
pipeline.

WHAT THIS FILE IS, IN ONE SENTENCE. It is the tool every other checker reports
through: it discovers the check modules, runs each one over an artifact, prints
ONE population line per check, aggregates the per-check codes into a single
artifact-level code without erasing the distinction the codes carry, and writes
a versioned structured report OUTSIDE the artifact.

THE SPINE (CHECK-11, a design rule HARD)
-------------------------------
Every check prints its own population, and a check that ran over zero inputs is
reported as FAIL -- never as PASS and never as the banned verdict word. This
phase has now measured that failure three times in three different disguises:
a test command whose own count was suppressed printed dots and no number; a
guard whose vacuity check only fired at zero ran over 2 directories instead of
25 and PASSED; a register whose rows carrying a figures record were 0 of 12
correctly exited DID-NOT-RUN rather than publishing an empty register.

A count that is PRESENT but WRONG is more dangerous than a missing one, because
a wrong number reads as detail while a missing one reads as a question. So this
runner prints BOTH the number it checked AND the population it was handed, on
every branch, and closes an identity over the scan's own census (see census()).

WHY THIS FILE PRINTS ITS OWN LINE INSTEAD OF CALLING THE CORE'S PRINTER
----------------------------------------------------------------------
canonkit.report() is the population printer and it stays the single source of
the VERDICT: population_line() below calls it and returns what it returned, so
the zero-population branch that overrides `passed` lives in exactly one place
and cannot drift. The core's own line is captured and discarded and this file
re-renders it; test_conformance.py pins the two to agree.

THE REASON THAT CAPTURE EXISTED IS GONE, AND SAYING SO IS THE POINT.
Until 2026-09-21 the core's format carried the count under the label CHECK-11
bans, so the capture was load-bearing: it was the only thing keeping the banned
word out of this tool's output while every standalone check module printed it.
The core now spells the label `not-examined=` itself, so the two renderings
agree by construction rather than by repair. The capture is kept because it is
what makes the VERDICT come from exactly one place, which was always the other
half of the reason -- not because the core's wording needs correcting.

RUNNER PROPERTIES ARE FIRST-CLASS ROWS, NOT SIDE EFFECTS
-------------------------------------------------------------------
CHECK-10 (waivers are countable) and CHECK-11 (every check prints its own
population) are properties of this runner rather than modules under checks/.
They are nevertheless emitted as FIRST-CLASS entries of the report's checks[]
array, with their own ids, codes and populations, on every run that scans an
artifact. The identity a caller can assert is

    len(report["checks"]) == discover().found + len(RUNNER_CHECK_IDS)

and never `== discover().found`, which would silently equate the checks[] count
with the MODULE count. Without a row of their own, an audit that derives its
population from a checks/check_NN.py glob plus a red-transcripts/CHECK-NN.txt
glob would see ten checkers where there are twelve -- a verifying population
that excludes exactly the two cases it was written to cover.

The one run this identity does not govern is `--self`, landed by an earlier plan: it
scans this repository over a named subset rather than an artifact, so there is
no artifact and no waivers record. Both ids appear in `--self`'s printed skip
list with a reason and inside its skipped count -- never simply absent, which is
how a reader would conclude the twelve-checker contract had shrunk.

`--self`: WHY THE SUBSET IS NAMED AND NOT INFERRED (a design rule, Open Question 4)
---------------------------------------------------------------------------
This repository is not an artifact. It has no results/figures.json, no
results/gate.json, no "what this does not show" section, no claim-under-test
block and no waivers record, so most of the twelve checks are inapplicable here
BY CONSTRUCTION -- not failing, not passing: inapplicable.

An unqualified `--self` that ran whichever checks happened to find something to
read and then reported PASS would be announcing a verdict over a population
nobody stated. That is the 0/0 pass wearing a different hat, and it is the exact
failure a design rule exists to catch. So: the subset is DECLARED below beside a committed
count; every declared checker outside it is PRINTED with a reason and counted;
both totals are reported on one parseable line; and a subset that resolves to
zero members REFUSES with exit 2 rather than reporting a clean run.

Each line carries a LABEL. `check` means the line is a member of the twelve-
checker contract a success criterion scopes over. `suite-assertion` means it is a pre-existing
assertion from this repository's own test suite, SURFACED here so a reader of a
self-check sees it -- CORE-CONTRACT re-runs the design rule split assertion an earlier plan
made in test_repo_hygiene.py, VENDOR-CONSISTENCY re-runs the project requirement hash
assertion an earlier plan made in test_vendoring.py. Neither is a checker, neither has
a red-transcripts/*.txt, and a companion test module asserts that neither
appears on either side of the transcript bijection. The label is what keeps that
honest in both directions: without it a reader could count the names here, count
the transcripts, and reconcile the two by assuming transcripts are missing.

MEASURED WHEN THIS LANDED, and recorded because it contradicts the plan that
asked for it. CHECK-07 was specified as a RUNNING member of the subset ("this
repo is a git work tree with commits"). It cannot be: check_07.run() refuses
before it looks at git when the target carries no results/ directory, and this
repository has none --

    REFUSING: <repo> carries no results/ directory, so there is no
    machine-written output to ask git about. This is not a finding: saying "not
    a work tree" about a directory that is not an artifact at all would be a
    verdict on something this check was never pointed at.

That refusal is an earlier plan's deliberate design and it is correct on its own
terms; CHECK-07's population is the machine-written files under results/, which
is zero here. So CHECK-07 carries an APPLICABILITY PREDICATE rather than being
quietly dropped or quietly demoted: the predicate is evaluated BEFORE the check
runs, and a member whose predicate holds and which then refuses is a FAILURE,
never a skip. Demoting a refusal to a skip would make "this check could not look"
indistinguishable from "this check does not apply here", which is the one
distinction this file exists to preserve.

WAIVERS ARE AN OWNER ROUND TRIP, NOT A SWITCH
-----------------------------------------------------------
Build agents run unattended. A checker the thing being checked can silence is
not a checker. So the run's waivers record is compared against the LAST
COMMITTED version of the same file, read back through git, and any waiver
present in the first but not the second is ITSELF a finding. The owner round
trip is the feature, not friction to be engineered away.

EXTRAS ARE COUNTED, NOT CRIED WOLF OVER
-----------------------------------------------
The scan root holds the read-only live data dir and more than twenty unrelated
trees. An artifact-shaped directory that is not in the manifest is REPORTED WITH
A COUNT and does not move the exit code. The MISSING direction still fails, and
the status rule's per-slug `status` decides which absence is a failure: a `built` slug
with no directory FAILS, a `pending` slug with no directory is the expected
not-yet-built state, and a `pending` slug whose directory EXISTS is a finding
because the manifest is stale. `status` is owner/plan-set and this file NEVER
writes it.

THE SCAN ROOT IS DERIVED, NOT SPELLED
--------------------------------------------
A sibling guard in this repository derives its scan root as `<repo>/..` and is
correct in the main checkout and WRONG inside an agent worktree, where it
resolves to the worktrees directory and runs over 2 directories instead of 25 --
and passes either way, because its vacuity check only fires at zero. This file
resolves the MAIN repository root first (walking a worktree's `.git` FILE back
to the checkout it was linked from) and applies the manifest's declared relative
rule to that, so the same population is enumerated from either location. The
directory count the scan actually covered is PRINTED, so the number is auditable
rather than assumed.

Enumeration stops at the IMMEDIATE CHILDREN of the scan root. That depth is the
whole mechanism by which a design rule holds: this repository lives inside the scan root,
so fixtures/broken-artifacts/ IS a descendant of it by naive path containment;
what holds is NON-ENUMERATION, because the fixture tree sits at depth 3.

VENDORING AND WHERE REPORTS GO
---------------------------------------------
This file is part of the vendored set. It is copied to <artifact>/conformance.py
beside <artifact>/canonkit.py and <artifact>/checks/, so a handed-over directory
self-checks with no access to this repository. It is run BY PATH under a bare
module name, never as a dotted package module. Stdlib only, ASCII only.

Reports are written OUTSIDE the artifact by default. --report-inside is required
to write one within an artifact directory, because a checker output inside the
tree becomes an input to any hash over that tree and shows up in git status,
needing a permanent exclusion rule someone will forget. Paired with a design rule, that
is what makes the reader RE-RUN the checker rather than trust a stored verdict.

EXIT CODES (canonkit's contract, a design rule)
    check level:     0 pass | 1 finding | 2 did-not-run | 3 guard-fail
    artifact level:  all 0 -> 0 ; any 1 or any 2 -> 1 ; any 3 -> 3

A check-level 2 aggregates UP to 1 so the artifact-level verdict is unambiguously
a finding. One integer destroys the per-check distinction by construction, so
that distinction lives in two places the aggregate cannot erase: the summary
counts line, and the per-check `code` in the structured report.
"""

import argparse
import ast
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

TOOL = "conformance"
SCHEMA = "canonkit/report"
TOOL_SCHEMA = "canonkit/conformance/1"

HERE = os.path.dirname(os.path.abspath(__file__))

# canonkit.py and checks/ sit BESIDE this file in both layouts: `tools/` in this
# repository, the artifact root in a vendored copy. One expression for both.
CORE_ROOT = HERE
CHECKS_DIRNAME = "checks"
MANIFEST_NAME = "manifest.json"
WAIVERS_NAME = "waivers.json"

# ---------------------------------------------------------------------------
# The two runner properties, as a COMMITTED LITERAL
# ---------------------------------------------------------------------------
#
# Read by tools/tests/test_skeleton_roundtrip.py and by an earlier plan's audit
# rather than re-typed, so the pair has one definition. The count beside it is
# the same derive-and-assert shape the check package applies to its own id
# universe: a purely derived length silently stops checking when an id is
# dropped, because expected falls to match found.

CHECK_10 = "CHECK-10"
CHECK_11 = "CHECK-11"
RUNNER_CHECK_IDS = (CHECK_10, CHECK_11)
RUNNER_CHECK_COUNT = 2

if len(RUNNER_CHECK_IDS) != RUNNER_CHECK_COUNT:
    raise RuntimeError(
        "RUNNER_CHECK_IDS holds %d id(s) but the committed literal "
        "RUNNER_CHECK_COUNT says %d. Update BOTH in the same commit."
        % (len(RUNNER_CHECK_IDS), RUNNER_CHECK_COUNT))

# a design rule: declared per-check IN CODE, overridable on the command line, and the
# EFFECTIVE value is what prints.
RUNNER_DEFAULT_FLOORS = {CHECK_10: 1, CHECK_11: 1}

# The eight fields every checks[] row carries, module-backed or runner-emitted.
# A consumer must not be able to tell a runner property from a module by the
# SHAPE of its row -- only by its id and by the `source` field beside them.
REPORT_CHECK_FIELDS = ("check_id", "code", "verdict", "found", "checked",
                       "floor", "waived", "finding_ids")
REPORT_CHECK_FIELD_COUNT = 8

if len(REPORT_CHECK_FIELDS) != REPORT_CHECK_FIELD_COUNT:
    raise RuntimeError("REPORT_CHECK_FIELDS and its literal disagree")

SOURCE_RUNNER = "runner:conformance.py"
SOURCE_MODULE_PREFIX = "module:"

# ---------------------------------------------------------------------------
# the banned-spelling rule -- the banned results record spelling
# ---------------------------------------------------------------------------
#
# ASSEMBLED FROM PARTS so this file's own source is not a hit for the repo-wide
# lint that looks for the literal. The same shape a sibling test module already
# uses, and the same shape the fail-closed hook guard needed after its first
# draft matched its own explanatory comment.
BANNED_RESULTS_BASENAME = "mani" + "fest" + ".json"
BANNED_RESULTS_RELATIVE = "results/" + BANNED_RESULTS_BASENAME
BANNED_SPELLING_GUARD_ID = "GUARD-BANNED-SPELLING"

# ---------------------------------------------------------------------------
# What makes a directory ARTIFACT-SHAPED
# ---------------------------------------------------------------------------
#
# Deliberately narrow. The scan root holds unrelated trees, backups and the
# read-only live data dir; a predicate wide enough to catch every one of them
# would turn the extras count into noise on day one. A README alone is not
# enough -- this repository has one and is not an artifact.
ARTIFACT_SHAPE_REQUIRED = "README.md"
ARTIFACT_SHAPE_ANY = ("results", "gate.py", "derive.py", ".vendor.json")

STATUS_BUILT = "built"
STATUS_PENDING = "pending"

# A whole-artifact waiver id. An owner may excuse a slug from the scan only with
# a committed waiver carrying this id; the count then prints, so the exclusion
# is countable rather than invisible.
WAIVE_ALL = "CHECK-ALL"

WAIVER_REQUIRED_KEYS = ("check_id", "reason", "dated_at")

MAX_LISTED = 20


class ConformanceRefusal(Exception):
    """The runner could not look. Mapped to the did-not-run exit code."""


# ---------------------------------------------------------------------------
# --self: the named subset (a design rule, Open Question 4). See the module docstring.
# ---------------------------------------------------------------------------

SELF_MODE = "self"

LABEL_CHECK = "check"
LABEL_SUITE_ASSERTION = "suite-assertion"

# The verdict printed for a member that was NOT run. Deliberately not one of
# canonkit's four verdicts: it is not a statement about the repository, it is a
# statement about the population. And deliberately not the banned word, which
# CHECK-11 forbids anywhere in this tool's output because it reads as
# "deliberately and safely omitted".
SELF_NOT_APPLICABLE = "NOT-APPLICABLE"

# The non-check member of a success criterion's scope. A repo-wide lint rather than a check
# module, so it has no CHECK_ID and never will -- but it DOES have a RED
# transcript (red-transcripts/LINT-BANNED-NAMES.txt), which is what puts it
# inside a success criterion's population and outside the check-module glob.
LINT_ID = "LINT-BANNED-NAMES"
LINT_MODULE_NAME = "lint_banned_names.py"

CORE_CONTRACT_ID = "CORE-CONTRACT"
VENDOR_CONSISTENCY_ID = "VENDOR-CONSISTENCY"
VENDOR_MODULE_NAME = "vendor.py"


@dataclass
class SelfMember:
    """One declared member of the `--self` subset.

    `applies` is a predicate on the scanned root, or None for "always". It is
    evaluated BEFORE the member runs, and that ordering is the whole mechanism:
    a member whose predicate holds and which then REFUSES is reported as a
    refusal, never quietly filed as a skip. "This check could not look" and
    "this check does not apply here" are different facts and only the second is
    a stated inapplicability.
    """

    member_id: str
    kind: str
    what: str
    applies: object = None
    inapplicable_reason: str = ""


def _has_results_dir(root):
    return os.path.isdir(os.path.join(root, "results"))


SELF_SUBSET = (
    SelfMember(
        "CHECK-07", LABEL_CHECK,
        "this repository is a git work tree with commits and tracked "
        "machine-written output under results/",
        applies=_has_results_dir,
        inapplicable_reason=(
            "this repository carries no results/ directory, so CHECK-07's "
            "population -- the machine-written files under results/ -- is zero "
            "here BY CONSTRUCTION. check_07.run() refuses on exactly that "
            "condition before it asks git anything, which is an earlier plan's "
            "deliberate design: calling a directory that is not an artifact "
            "\"not a work tree\" would be a verdict on something the check was "
            "never pointed at. The predicate is re-evaluated on every run, so "
            "the moment this tree does carry results/ the check RUNS."),
    ),
    SelfMember(
        "CHECK-08", LABEL_CHECK,
        "every dependency specifier and image reference in this repository is "
        "pinned (the stated reason a design rule exists)"),
    SelfMember(
        LINT_ID, LABEL_CHECK,
        "the the banned-spelling rule banned results-record spelling is LIVE nowhere in the tracked "
        "tree, and every occurrence is classified"),
    SelfMember(
        CORE_CONTRACT_ID, LABEL_SUITE_ASSERTION,
        "canonkit.py is ASCII and stdlib-only, and no repo-side module imports "
        "the vendored set as a package module (an earlier plan's assertion, "
        "re-surfaced here)"),
    SelfMember(
        VENDOR_CONSISTENCY_ID, LABEL_SUITE_ASSERTION,
        "tools/vendor.py's declared set agrees with its committed literal and "
        "every file in it exists and hashes (a project requirement; an earlier plan's assertion, "
        "re-surfaced here)"),
)

# The committed literal beside the derivation, for the same reason every other
# count in this program carries one: a purely derived length silently stops
# checking when a member is dropped, because expected falls to match found.
SELF_SUBSET_COUNT = 5

if len(SELF_SUBSET) != SELF_SUBSET_COUNT:
    raise RuntimeError(
        "SELF_SUBSET names %d member(s) but the committed literal "
        "SELF_SUBSET_COUNT says %d. Update BOTH in the same commit."
        % (len(SELF_SUBSET), SELF_SUBSET_COUNT))

# Why each declared checker outside the subset does not run HERE. Stated per id
# rather than grouped under one sentence, because a shared reason is a reason
# nobody checked against the individual check.
SELF_SKIP_REASONS = {
    "CHECK-01": "no results/figures.json: this repository publishes no figures, "
                "so there is no figure-to-population pairing to lint and no "
                "figure value that could leak into prose.",
    "CHECK-02": "no machine-emitted started_at anywhere: this repository runs no "
                "measurement, so there is no machine date for a README date to "
                "agree with. A date that agrees with nothing is not a date that "
                "agrees.",
    "CHECK-03": "no \"what this does not show\" section: that section is part of "
                "the ARTIFACT contract. This repository is the tooling that "
                "checks for it.",
    "CHECK-04": "no results/gate.json: this repository mints no run token and "
                "records no gate, so there is no ordering claim to make.",
    "CHECK-05": "this repository is not one of the manifest's slugs, so no "
                "register row is expected for it. Asking `expected N, found M` "
                "about a directory the expected set does not name would be a "
                "comparison over nothing wearing the phrasing of a result.",
    "CHECK-06": "no results/ directory: there is no results file that could be "
                "missing a machine-emitted run record.",
    "CHECK-09": "no claim-under-test block: this repository backs no published record "
                "bullet, so there are zero bullet references to examine.",
    "CHECK-10": "no waivers.json and no artifact under scan, so there is no "
                "waiver population to count. CHECK-10 is emitted as a "
                "first-class checks[] row on every ARTIFACT run (an earlier plan); "
                "it is named here rather than omitted, because a checker "
                "silently absent from a self-check report reads as a contract "
                "that shrank.",
    "CHECK-11": "CHECK-11 inspects the population lines an ARTIFACT run printed "
                "for its per-check records. --self scans no artifact, so there "
                "are no such records. Named here for the same reason CHECK-10 "
                "is: absence must be stated, never inferred.",
    "CHECK-20": "CHECK-20 asks whether a built slug corrected the collections "
                "entry its work was supposed to back. This repository is the "
                "TOOLING, not an example project: the expected set does not name it, "
                "it backs no claim, and nothing about it could be corrected. "
                "Running it here would be a verdict on a directory the check "
                "was never pointed at. It IS emitted as a first-class checks[] "
                "row on every artifact run, and it is named here rather than "
                "omitted, because a checker silently absent from a self-check "
                "report reads as a contract that shrank.",
}


# ---------------------------------------------------------------------------
# Per-artifact applicability (the design rules) -- the twin of the --self half above
# ---------------------------------------------------------------------------
#
# READ THIS BESIDE `SelfMember`. The two halves answer the same question about
# two different populations, and the artifact half exists because the --self
# half's shape is the only one that reaches EXIT=0.
#
# WHY NOT AN IN-MODULE REFUSAL. a design rule's wording is "give CHECK-09 an
# applicability predicate, like CHECK-07's". Measured: no check module in this
# repository has one -- `applicab` appears nowhere under tools/checks/ -- and
# what check_07.py carries is an in-module early refusal returning
# EXIT_DID_NOT_RUN. `run_artifact` aggregates every record's code and
# the conventions document section 1 lifts any 2 to 1, so an in-module refusal means a
# slug that correctly backs nothing can NEVER reach exit 0 however conformant
# it is. a design rule refused to buy that with a waiver, in those words: es-log backing
# nothing is CORRECT, not tolerated.
#
# THE MECHANISM, and all three parts are load-bearing. A member whose predicate
# does not hold is
#
#   * NOT run;
#   * kept in `run.records`, so CHECK-11 still counts it and the runner's own
#     population does not silently shrink;
#   * EXCLUDED from the codes the aggregate is built from -- which is the whole
#     point, and which `run_self` already proves is the shape that lets a run
#     be EXIT=0 while naming members it did not run.
#
# THE PREDICATE READS THE MANIFEST ROW THE RUNNER RESOLVED, NEVER A FILE INSIDE
# THE ARTIFACT. An artifact that could declare its own
# inapplicability would be a checker the thing being checked points at its own
# evidence. `status` and `no_row_reason` are owner-set and plan-set under
# the status rule and are never written by a build agent or by this tool.
#
# EVERY PREDICATE BELOW REQUIRES A RECORDED REASON AS ONE OF ITS CONJUNCTS
# Dropping that conjunct would exempt every artifact that has not
# authored its claim block yet, which converts a refusal into a silent
# exemption -- the demotion that the conventions document, section 1, and the `SelfMember`
# docstring both warn about. An unexplained absence is not an exemption, and
# there are negative tests for each of the three members.

# The printed verdict, which is the SAME CONSTANT the --self half prints rather
# than a second spelling of it. Two spellings of one state is how a reader
# learns to scan for one and miss the other.
ARTIFACT_NOT_APPLICABLE = SELF_NOT_APPLICABLE


@dataclass
class ArtifactMember:
    """One declared per-artifact applicability member.

    `applies(artifact, row)` is evaluated BEFORE the module runs, and that
    ordering is the whole mechanism: a member whose predicate HOLDS and which
    then refuses is reported as a refusal, never quietly filed as an
    inapplicability. "This check could not look" and "this check does not apply
    here" are different facts and only the second is a stated inapplicability.

    `reason(row)` is COMPUTED from the row rather than hardcoded. The sentence
    a reader needs is the expected set's OWN `no_row_reason` text, quoted -- a
    reason typed here would be a second, unreviewable copy of it that can
    disagree with the manifest silently.
    """

    member_id: str
    what: str
    applies: object = None
    reason: object = None


def manifest_row(manifest, slug):
    """The expected set's row for `slug`, or an EMPTY row.

    An empty row is the STRICT case by construction: it maps no claim and
    records no reason, so every predicate below says "applicable". A slug the
    expected set does not name can therefore never be exempted by accident.
    """
    for row in (manifest or {}).get("slugs") or []:
        if isinstance(row, dict) and str(row.get("slug") or "") == str(slug):
            return row
    return {}


def recorded_no_row_reason(row):
    """The row's recorded reason, stripped. Empty means NONE was recorded."""
    return str((row or {}).get("no_row_reason") or "").strip()


def owes_no_claim(row):
    """True when the row maps a bullet through NEITHER mapping field.

    Both fields, because the two mean different things and either one is an
    obligation: `bullets` is what a path is responsible for backing, and
    `backs_bullets` is what an already-existing artifact is cited as backing.
    A predicate that read only the first would exempt
    `example-cache-benchmark`, whose one claim arrives through the second.
    """
    return (not ((row or {}).get("bullets") or [])
            and not ((row or {}).get("backs_bullets") or []))


def claim_member_applies(artifact, row):
    """A claim-scoped check applies unless the row owes nothing AND says why."""
    return not (owes_no_claim(row) and recorded_no_row_reason(row))


def register_member_applies(artifact, row):
    """CHECK-05 applies unless `register_row` is false AND a reason is recorded.

    MEASURED, and this is why a re-scope alone cannot reach it:
    `check_05.py`'s `expected_slugs` filters the expected set on a TRUTHY
    `register_row`, so a slug that owes no row is not in the expected set at
    all. After an earlier plan re-scoped the check to this slug's own row, such a
    slug hits the 0/0 refusal and returns code 2, which the aggregate lifts to
    1. A refusal is also the wrong VERDICT: owing no register row is correct,
    which a design rule already encodes by naming the slug in the register's own
    `excluded: N (reasons recorded)` line.
    """
    return bool((row or {}).get("register_row")) or not recorded_no_row_reason(row)


def _claim_member_reason(row):
    return (
        "the expected set's row for this slug maps a claim through NEITHER "
        "`bullets` nor `backs_bullets`, and records why, so there is no claim "
        "here for this check to examine. The expected set's own reason, "
        "verbatim: %s || This is a STATED inapplicability and not a check that "
        "could not look: the predicate is re-evaluated on every run, so the "
        "moment the row names a claim the check RUNS -- and a row that owes "
        "nothing while recording NO reason keeps running and keeps refusing, "
        "because an unexplained absence is not an exemption."
        % recorded_no_row_reason(row))


def _register_member_reason(row):
    return (
        "the expected set's row for this slug carries `register_row: false` "
        "and records why, so no register row is owed and there is none for "
        "this check to judge. The expected set's own reason, verbatim: %s || "
        "The register states the same exclusion in its own header line, with "
        "this reason beside it. A `register_row: false` row that "
        "records NO reason keeps running and keeps refusing."
        % recorded_no_row_reason(row))


ARTIFACT_SUBSET = (
    ArtifactMember(
        "CHECK-05",
        "this artifact's own register row is present and correct -- asked only "
        "of a slug the expected set says owes one",
        applies=register_member_applies,
        reason=_register_member_reason),
    ArtifactMember(
        "CHECK-09",
        "the claim-under-test block names its canon, project, bullet, the "
        "bullet's text verbatim, a measured counterpart and a legal verdict -- "
        "asked only of a slug that owes a claim",
        applies=claim_member_applies,
        reason=_claim_member_reason),
    ArtifactMember(
        "CHECK-20",
        "a built slug corrected the collections entry its work was supposed to "
        "back -- asked only of a slug that owes a correction. The module's own "
        "refusal already points here: \"which the runner's applicability "
        "mechanism states rather than this module passing over it\"",
        applies=claim_member_applies,
        reason=_claim_member_reason),
)

# The committed literal beside the derivation, for the same reason SELF_SUBSET
# carries one: a purely derived length silently stops checking when a member is
# dropped, because `expected` falls to match `found`.
ARTIFACT_SUBSET_COUNT = 3

if len(ARTIFACT_SUBSET) != ARTIFACT_SUBSET_COUNT:
    raise RuntimeError(
        "ARTIFACT_SUBSET names %d member(s) but the committed literal "
        "ARTIFACT_SUBSET_COUNT says %d. Update BOTH in the same commit."
        % (len(ARTIFACT_SUBSET), ARTIFACT_SUBSET_COUNT))


# ---------------------------------------------------------------------------
# Loading the frozen core and the check contract, BY PATH
# ---------------------------------------------------------------------------


def load_core():
    """Load canonkit.py BY PATH, as a sibling. Never a dotted package import."""
    path = os.path.join(CORE_ROOT, "canonkit.py")
    spec = importlib.util.spec_from_file_location("frozen_core", path)
    if spec is None or spec.loader is None:
        raise ImportError("could not build an import spec for %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTRACT_MODULE_NAME = "canonkit_check_contract"


def load_contract():
    """Load checks/__init__.py BY PATH and REGISTER it in sys.modules.

    The registration is load-bearing rather than tidy. A check module's own
    loader prefers an already-loaded copy of this file by matching __file__: if
    the runner's copy were not in sys.modules, each module would mint a SECOND
    CheckResult class and a runner comparing against its own would reject a
    result that is structurally identical.
    """
    target = os.path.join(HERE, CHECKS_DIRNAME, "__init__.py")
    existing = sys.modules.get(CONTRACT_MODULE_NAME)
    if existing is not None and hasattr(existing, "CheckResult"):
        return existing
    spec = importlib.util.spec_from_file_location(CONTRACT_MODULE_NAME, target)
    if spec is None or spec.loader is None:
        raise ImportError("could not build an import spec for %s" % target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[CONTRACT_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


# a success criterion's population, in printing order: the THIRTEEN declared checkers plus the
# one named non-check that has a RED transcript. DERIVED from the check contract
# and from RUNNER_CHECK_IDS rather than re-typed, so a fourteenth check module
# cannot appear here without appearing there first. `--self` reports every one
# of these as either RAN or NOT-APPLICABLE-with-a-reason, and asserts nothing
# else about them.
#
# CORE-CONTRACT and VENDOR-CONSISTENCY are deliberately NOT here. They are suite
# assertions, not checkers; counting them would force the "every member has a RED
# transcript" rule to be relaxed to accommodate two items that can never have one.
#
# THIS LITERAL IS WHAT FOUND ITSELF WHEN CHECK-16 LANDED, and that is the
# argument for having it. A sweep for the number `13` would have had to guess
# that this was one of the places carrying it; instead the derivation moved to
# 14, disagreed with the committed literal, and the import RAISED with both
# numbers named. A purely derived count would have followed the set silently.
DECLARED_SELF_CHECK_IDS = tuple(
    list(load_contract().DECLARED_CHECK_IDS) + list(RUNNER_CHECK_IDS) + [LINT_ID])

DECLARED_SELF_CHECK_COUNT = 14

if len(DECLARED_SELF_CHECK_IDS) != DECLARED_SELF_CHECK_COUNT:
    raise RuntimeError(
        "DECLARED_SELF_CHECK_IDS derives %d id(s) but the committed literal "
        "DECLARED_SELF_CHECK_COUNT says %d. Eleven module-backed checkers plus "
        "the two runner properties plus "
        "%s. Update BOTH in the same commit."
        % (len(DECLARED_SELF_CHECK_IDS), DECLARED_SELF_CHECK_COUNT, LINT_ID))


# ---------------------------------------------------------------------------
# Repository anchors
# ---------------------------------------------------------------------------


def resolve_worktree_main_root(repo_root, marker_text):
    """Pure half of main_repo_root(), so the worktree case is TESTABLE.

    A worktree's `.git` is a FILE holding `gitdir: <main>/.git/worktrees/<name>`.
    Walking that back to <main> is what makes the derived scan root resolve to
    the same population from inside an agent as from the main checkout. Returns
    `repo_root` unchanged for any marker this does not understand -- failing
    back to the observable value rather than to a guess.

    Deliberately a COPY of the same logic in tools/census_live_store.py rather
    than an import of it: this file is vendored into artifacts that have no
    tools/ package at all. tools/tests/test_conformance.py asserts the two
    resolve equal on the same inputs, so the copy cannot drift silently.
    """
    text = (marker_text or "").strip()
    if not text.startswith("gitdir:"):
        return repo_root
    gitdir = text.split(":", 1)[1].strip()
    if not os.path.isabs(gitdir):
        gitdir = os.path.join(repo_root, gitdir)
    gitdir = os.path.abspath(gitdir)
    parts = gitdir.replace(chr(92), "/").rstrip("/").split("/")
    if len(parts) >= 3 and parts[-2] == "worktrees" and parts[-3] == ".git":
        return os.path.abspath(
            os.path.join(gitdir, os.pardir, os.pardir, os.pardir))
    return repo_root


def working_repo_root():
    """The root of the checkout THIS FILE IS RUNNING FROM."""
    return os.path.dirname(HERE)


def main_repo_root(start=None):
    """The MAIN checkout's root, even when this runs from a git worktree."""
    repo_root = os.path.abspath(str(start)) if start else working_repo_root()
    marker = os.path.join(repo_root, ".git")
    if not os.path.isfile(marker):
        return repo_root
    try:
        with open(marker, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return repo_root
    return resolve_worktree_main_root(repo_root, text)


def manifest_path(explicit=None):
    return (os.path.abspath(str(explicit)) if explicit
            else os.path.join(HERE, MANIFEST_NAME))


def load_manifest(explicit=None):
    """The expected set. Absent is legal: a vendored copy has no manifest."""
    path = manifest_path(explicit)
    if not os.path.isfile(path):
        return {}
    with open(path, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def declared_scan_root(manifest, repo_root=None):
    """The scan root, derived from the MAIN repository root plus the manifest rule.

    The manifest declares the rule RELATIVE to the repository root rather than
    as an absolute path, so no tracked file bakes in a home directory and the
    same rule resolves in every checkout. Applying it to main_repo_root() rather
    than to the working root is what makes the population identical from inside
    a worktree.
    """
    root = os.path.abspath(str(repo_root)) if repo_root else main_repo_root()
    rule = ((manifest.get("scan_root") or {}).get("relative_to_repo_root")
            or os.pardir)
    return os.path.abspath(os.path.join(root, rule))


def declared_scan_depth(manifest):
    depth = (manifest.get("scan_root") or {}).get("depth")
    return depth if isinstance(depth, int) and depth > 0 else 1


# ---------------------------------------------------------------------------
# The population line
# ---------------------------------------------------------------------------


@dataclass
class PopulationRecord:
    """One printed population line, kept so CHECK-11 can INSPECT it.

    CHECK-11's population is the check results whose summary line was inspected
    for a printed population, so the line itself is retained rather than a
    boolean somebody set while printing it.
    """

    check_id: str
    verdict: str
    code: int
    found: int
    checked: int
    listed: int
    not_examined: int
    floor: int
    waived: int
    note: str
    line: str
    source: str
    finding_ids: list = field(default_factory=list)

    # False for a member the per-artifact applicability declaration excluded
    # BEFORE it ran (the design rules). Such a record is kept in `run.records` -- so
    # CHECK-11 still counts it and the runner's population does not silently
    # shrink -- and its `code` is deliberately None rather than one of the four:
    # an inapplicability is not a statement about the artifact, and a leak into
    # `core.aggregate()` then RAISES ("None is not an exit code") instead of
    # quietly reinstating the exit-1 this mechanism exists to remove.
    applicable: bool = True

    @property
    def printed_population(self):
        """True when the printed line actually carries this check's population."""
        return ("checked=%d of %d" % (self.checked, self.listed)) in self.line


def population_line(core, check_id, passed, found, checked, floor, waived=0,
                    note="", not_examined=0, listed=None, stream=None):
    """Print ONE population line and return (verdict, line).

    Three properties, copied from the shipped analog that carries the dated
    rationale for all of them:

      (a) the count is printed WITH the verdict, never instead of it, and on
          EVERY branch -- a print guarded by the verdict makes the clean run
          silent, and a silent run is indistinguishable from one that never
          happened;
      (b) every not-examined input is COUNTED and given a reason beside it;
      (c) the numbers close an identity a caller can assert. The core enforces
          `checked + not-examined == listed` and raises on a triple that does
          not close; the census closes the artifact-level one.

    THE VERDICT COMES FROM THE CORE, always. canonkit.report() puts the
    zero-population branch FIRST and overrides `passed` there; re-deriving that
    here would be a second copy of the one branch that matters. Its line is
    captured and discarded so that this function has exactly one printing site
    and the verdict has exactly one deriving site.

    That capture used to carry a SECOND reason -- the core spelled the count
    with the word CHECK-11 bans -- and that reason was retired on 2026-09-21
    when the core's own label became `not-examined=`. The sentence is corrected
    rather than deleted: a comment that still explains a repair which no longer
    happens is how a reader concludes the core is still wrong.
    """
    stream = stream if stream is not None else sys.stdout
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        verdict = core.report(check_id, passed, found, checked, floor,
                              waived=waived, note=note, not_examined=not_examined,
                              listed=listed)
    if listed is None:
        listed = checked + not_examined
    line = ("%-16s %-11s found=%d checked=%d of %d not-examined=%d floor=%d "
            "waived=%d" % (check_id, verdict, found, checked, listed,
                           not_examined, floor, waived))
    if note:
        line = line + "  " + str(note)
    stream.write(line + "\n")
    return verdict, line


def record_for(core, result, source, stream=None):
    """Print `result`'s population line and return the PopulationRecord for it."""
    stream = stream if stream is not None else sys.stdout
    verdict, line = population_line(
        core, result.check_id, result.code == core.EXIT_PASS, result.found,
        result.checked, result.floor, waived=result.waived, note=result.note,
        not_examined=result.not_examined, listed=result.listed, stream=stream)

    # a design rule's demotion, said out loud rather than hidden in an exit code. The
    # line above reports what was FOUND; this one reports that the population
    # was too small for that finding to mean anything. Without it, a reader sees
    # a FAIL beside code 2 and has no way to tell a demotion from a defect.
    if (result.checked and result.checked < result.floor
            and result.code == core.EXIT_DID_NOT_RUN):
        stream.write("  DEMOTED to %s: population %d is below the effective "
                     "floor %d.\n"
                     % (core.VERDICT_DID_NOT_RUN, result.checked, result.floor))

    return PopulationRecord(
        check_id=result.check_id, verdict=verdict, code=result.code,
        found=result.found, checked=result.checked, listed=result.listed,
        not_examined=result.not_examined, floor=result.floor, waived=result.waived,
        note=result.note, line=line, source=source,
        finding_ids=list(result.finding_ids))


def not_applicable_record(check_id, floor, reason, source, stream=None):
    """Print ONE line for a member that did not apply, and return its record.

    The line is in the POPULATION-LINE SHAPE, not a shorter one, and that is
    deliberate on two counts. CHECK-11 scans the lines this runner printed and
    reports any that carries a verdict without its own `checked N of M` -- so a
    bare "CHECK-09 not applicable" would be a finding against the runner, and
    correctly: a verdict with no count is indistinguishable from an unrun
    check. And the count here is honestly zero, printed WITH its reason beside
    it, which is what the conventions document section 2 asks of every input that was not
    examined.

    The verdict word is `NOT-APPLICABLE` -- deliberately not one of canonkit's
    four verdicts, because it is not a statement about the artifact, and
    deliberately not the banned word, which reads as "deliberately and safely
    omitted" and is how a population of zero gets filed as a pass by a human
    reading a log.
    """
    stream = stream if stream is not None else sys.stdout
    line = ("%-16s %-11s found=0 checked=0 of 0 not-examined=0 floor=%d "
            "waived=0" % (check_id, ARTIFACT_NOT_APPLICABLE, floor))
    if reason:
        line = line + "  " + str(reason)
    stream.write(line + "\n")
    return PopulationRecord(
        check_id=check_id, verdict=ARTIFACT_NOT_APPLICABLE, code=None,
        found=0, checked=0, listed=0, not_examined=0, floor=floor, waived=0,
        note=str(reason or ""), line=line, source=source, finding_ids=[],
        applicable=False)


# ---------------------------------------------------------------------------
# git, through subprocess, always
# ---------------------------------------------------------------------------


def _git(args, cwd):
    """Return (stdout, error). A git fact is read from git, never inferred."""
    try:
        completed = subprocess.run(
            ["git"] + list(args), cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace", shell=False)
    except OSError as error:
        return None, str(error)
    if completed.returncode != 0:
        return None, (completed.stderr or completed.stdout or "").strip()
    return completed.stdout, ""


# ---------------------------------------------------------------------------
# Waivers -- CHECK-10
# ---------------------------------------------------------------------------


def waiver_key(entry):
    """A canonical key for one waiver. Any difference makes it a DIFFERENT waiver.

    Deliberately the whole entry rather than its check_id: an owner who
    committed a waiver for one finding has not thereby committed a waiver whose
    reason or date was rewritten afterwards.
    """
    return json.dumps(entry, sort_keys=True, separators=(",", ":"))


def waiver_is_well_formed(entry):
    """a design rule's shape. All three keys, each a non-empty string."""
    if not isinstance(entry, dict):
        return False
    for key in WAIVER_REQUIRED_KEYS:
        value = entry.get(key)
        if not isinstance(value, str) or not value.strip():
            return False
    return True


def parse_waivers(text):
    """(entries, error) from the bytes of a waivers record."""
    try:
        record = json.loads(text)
    except ValueError as error:
        return [], "does not parse as JSON (%s)" % error
    if isinstance(record, list):
        return list(record), ""
    if not isinstance(record, dict):
        return [], "is not a JSON object"
    entries = record.get("waivers")
    if entries is None:
        return [], "carries no `waivers` array"
    if not isinstance(entries, list):
        return [], "`waivers` is %s, expected an array" % type(entries).__name__
    return list(entries), ""


def read_working_waivers(artifact):
    """(present, entries, error) for the run's own waivers record."""
    path = os.path.join(str(artifact), WAIVERS_NAME)
    if not os.path.isfile(path):
        return False, [], ""
    try:
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return True, [], "could not be read (%s)" % error
    entries, error = parse_waivers(text)
    return True, entries, error


def read_committed_waivers(artifact):
    """(resolved, entries, error) for the LAST COMMITTED waivers record.

    Read with `git show HEAD:./<name>` so the path resolves relative to the
    artifact directory rather than to a repository root that may be several
    levels above it. An unresolvable committed copy is NOT treated as an empty
    one: `no committed copy` and `a committed copy holding nothing` are
    different facts, and only one of them means every working waiver is new.
    """
    stdout, error = _git(["show", "HEAD:./%s" % WAIVERS_NAME], artifact)
    if stdout is None:
        return False, [], error or "no committed copy could be read"
    entries, parse_error = parse_waivers(stdout)
    return True, entries, parse_error


@dataclass
class WaiverCensus:
    """Every number the waiver round trip can report, kept SEPARATE."""

    working_present: bool = False
    committed_resolved: bool = False
    working: list = field(default_factory=list)
    committed: list = field(default_factory=list)
    honoured: list = field(default_factory=list)
    uncommitted: list = field(default_factory=list)
    malformed: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def sources_resolved(self):
        return int(self.working_present) + int(self.committed_resolved)

    @property
    def declarations(self):
        """CHECK-10's population: the waiver DECLARATIONS resolved for this run.

        The two records are declarations in their own right, which is why an
        artifact declaring zero waivers still has a population of at least one:
        the shipped waivers record is EMPTY but PRESENT, and "the owner declared
        no waivers" is a fact, not an absence of one.
        """
        return self.sources_resolved + len(self.working) + len(self.committed)

    @property
    def found(self):
        return len(self.uncommitted) + len(self.malformed)

    @property
    def finding_ids(self):
        ids = ["waiver:uncommitted:%s" % entry.get("check_id", "?")
               for entry in self.uncommitted]
        ids += ["waiver:malformed:%d" % index for index, _ in self.malformed]
        return sorted(set(ids))


# ---------------------------------------------------------------------------
# THE THREE RUNNER PROPERTIES.
#
# Each one is isolated in its own function so the RED commit can stub exactly
# the behaviour its transcript captures, and the GREEN commit can replace
# exactly that behaviour and nothing else.
# ---------------------------------------------------------------------------


def resolve_waivers(artifact):
    """THE OWNER ROUND TRIP. Read both copies and compare them.

    The working copy is what this run would honour. The committed copy is what
    the owner actually authorised. A waiver present in the first and absent from
    the second is a finding IN ITS OWN RIGHT, because a checker the thing being
    checked can silence is not a checker, and build agents run unattended.

    The committed copy is read back THROUGH GIT rather than from any cache this
    process wrote. A cached comparison would be the run agreeing with itself.

    An UNRESOLVABLE committed copy is not an empty one. "There is no committed
    copy" and "the committed copy holds nothing" are different facts, and only
    the second means the working copy's entries were all authorised; both are
    recorded separately so no caller can read one as the other.
    """
    census = WaiverCensus()

    census.working_present, working, error = read_working_waivers(artifact)
    if error:
        census.errors.append("%s %s" % (WAIVERS_NAME, error))
    census.working = list(working)

    resolved, committed, committed_error = read_committed_waivers(artifact)
    census.committed_resolved = resolved
    census.committed = list(committed)
    if resolved and committed_error:
        census.errors.append("the committed %s %s"
                             % (WAIVERS_NAME, committed_error))

    authorised = set(waiver_key(entry) for entry in committed
                     if waiver_is_well_formed(entry))

    for index, entry in enumerate(working):
        if not waiver_is_well_formed(entry):
            census.malformed.append((index, entry))
            continue
        if waiver_key(entry) in authorised:
            census.honoured.append(entry)
        else:
            census.uncommitted.append(entry)
    return census


def waived_count_for_line(census, result):
    """The waiver count printed beside a check is THAT CHECK's own suppression.

    Per check rather than per run, because the number has to answer "how many of
    THIS check's findings did an owner excuse". The run's total is carried
    separately, in the summary counts line, so both populations are printed and
    neither stands in for the other.
    """
    return result.waived


def normalize_zero_population(core, result):
    """A check that examined zero inputs is a DID-NOT-RUN. Never a pass.

    The modules already return 2 in that case. This is the RUNNER's own backstop
    and it is not redundant: it is what stops a badly-written or future check
    module from reporting a clean verdict over a population of nothing, which is
    the one failure this whole phase is organised around.
    """
    if result.checked == 0 and result.code == core.EXIT_PASS:
        result.code = core.EXIT_DID_NOT_RUN
        result.note = ("%s (examined zero inputs: DID-NOT-RUN, never a pass)"
                       % result.note).strip()
    return result


def scan_over_zero_artifacts(core, census, stream):
    """A scan that enumerated nothing DID NOT RUN. It never reports `0 of 0`.

    A scan that enumerated nothing and a scan that found everything clean render
    almost identically, and only one of them is evidence.
    """
    population_line(
        core, "SCAN", False, 0, 0, 1,
        note="no slug under %s was both declared built and present, so there "
             "was nothing to check. REPAIR: build one, or correct the expected "
             "set's status field -- which only the owner may change."
             % census.scan_root.replace(chr(92), "/"),
        stream=stream)
    return core.EXIT_DID_NOT_RUN


def check_11_findings(core, records):
    """CHECK-11's detection, over the lines the runner actually printed.

    Four conditions, each one a way a verdict can stop carrying its population:

      population-absent      the printed line does not carry this check's own
                             `checked N of M`. A verdict with no count is an
                             unrun check.
      pass-over-zero         a PASS printed over a population of zero.
      banned-verdict         the banned word anywhere in the line. It reads as
                             "deliberately and safely omitted", which is how a
                             zero population gets filed as a pass by a human
                             reading the log.
      verdict-code-mismatch  the CODE says PASS while the printed verdict does
                             not. Deliberately ONE-DIRECTIONAL: the opposite
                             pairing -- a FAIL line beside code 2 -- is the
                             documented demotion of a population below its
                             effective floor, printed beside the line as such.
                             Flagging that would make the runner refuse its own
                             a design rule behaviour; the dangerous direction is the one
                             where the integer a script branches on is more
                             forgiving than the sentence a human reads.
    """
    findings = []
    for record in records:
        if not record.printed_population:
            findings.append("population-absent:%s" % record.check_id)
        if record.checked == 0 and record.verdict == core.VERDICT_PASS:
            findings.append("pass-over-zero:%s" % record.check_id)
        if core.BANNED_VERDICT.lower() in record.line.lower():
            findings.append("banned-verdict:%s" % record.check_id)
        try:
            mapped = core.code_for(record.verdict)
        except ValueError:
            mapped = None
        if (record.code == core.EXIT_PASS and mapped is not None
                and mapped != core.EXIT_PASS):
            findings.append("verdict-code-mismatch:%s" % record.check_id)
    return sorted(set(findings))


# ---------------------------------------------------------------------------
# The two runner-emitted check results
# ---------------------------------------------------------------------------


def check_10_result(core, contract, census, floor):
    """CHECK-10, as a first-class CheckResult.

    Population: the waiver declarations resolved for this run. `found`: waivers
    honoured-but-uncommitted, plus malformed ones.
    """
    checked = census.declarations
    found = census.found
    if checked < floor:
        code = core.EXIT_DID_NOT_RUN
    elif found:
        code = core.EXIT_FINDING
    else:
        code = core.EXIT_PASS
    note = ("sources=%d working=%d committed=%d honoured=%d uncommitted=%d "
            "malformed=%d" % (census.sources_resolved, len(census.working),
                              len(census.committed), len(census.honoured),
                              len(census.uncommitted), len(census.malformed)))
    if census.errors:
        note = note + " errors=%d" % len(census.errors)
    if not census.committed_resolved:
        note = note + " (no committed copy resolved)"
    result = contract.CheckResult(
        check_id=CHECK_10, code=code, found=found, checked=checked, floor=floor,
        waived=0, note=note, finding_ids=census.finding_ids)
    return result


def check_11_result(core, contract, records, floor):
    """CHECK-11, as a first-class CheckResult.

    Population: the check results whose summary line was INSPECTED for a printed
    population -- at least one whenever any check ran. `found`: results missing a
    population, or reporting PASS over zero inputs, or carrying the banned
    verdict word.

    A check cannot be its own witness, so this result is built after every other
    line has been printed and does not inspect itself. That exclusion is stated
    in the note rather than left for a reader to infer from a count being one
    short.
    """
    inspected = len(records)
    findings = check_11_findings(core, records)
    found = len(findings)
    if inspected < floor:
        code = core.EXIT_DID_NOT_RUN
    elif found:
        code = core.EXIT_FINDING
    else:
        code = core.EXIT_PASS
    kinds = {}
    for finding in findings:
        kinds[finding.split(":", 1)[0]] = kinds.get(finding.split(":", 1)[0], 0) + 1
    note = ("inspected=%d population-absent=%d pass-over-zero=%d "
            "banned-verdict=%d verdict-code-mismatch=%d "
            "(this check is not its own witness)"
            % (inspected, kinds.get("population-absent", 0),
               kinds.get("pass-over-zero", 0), kinds.get("banned-verdict", 0),
               kinds.get("verdict-code-mismatch", 0)))
    return contract.CheckResult(
        check_id=CHECK_11, code=code, found=found, checked=inspected,
        floor=floor, waived=0, note=note, finding_ids=findings)


# ---------------------------------------------------------------------------
# the banned-spelling rule -- the banned results record
# ---------------------------------------------------------------------------


def d02_guard(core, artifact):
    """(code, note). FAILS on the existence of the banned results record.

    A guard rather than a check: it is a structural violation of the naming
    resolution, not a measurement over a population, and it must not appear in
    checks[] or the runner-count identity would stop closing.
    """
    path = os.path.join(str(artifact), "results", BANNED_RESULTS_BASENAME)
    if os.path.isfile(path):
        return core.EXIT_GUARD_FAIL, (
            "the banned record %s exists at %s. the banned-spelling rule bans that spelling "
            "outright: the expected set lives in the tooling repository's "
            "manifest and the numbers live in the figures record, and one file "
            "answering to both names is how the two concepts merge. REPAIR: "
            "delete it and write the figures record instead."
            % (BANNED_RESULTS_RELATIVE, path))
    # The PASS note deliberately does NOT spell the banned path. A checker that
    # printed it on every clean run would seed the literal into every captured
    # transcript in the repository, and the repo-wide lint that hunts that
    # literal would then be reading this tool's own output back to itself.
    return core.EXIT_PASS, "the banned results-record spelling (the banned-spelling rule) is absent"


# ---------------------------------------------------------------------------
# Floors
# ---------------------------------------------------------------------------


def parse_floor_overrides(values, check_ids):
    """`--min-population CHECK-03=5` per check, or a bare int for every check."""
    overrides = {}
    for raw in values or []:
        token = str(raw).strip()
        if "=" in token:
            name, _, number = token.partition("=")
            name = name.strip()
            try:
                overrides[name] = int(number.strip())
            except ValueError:
                raise ConformanceRefusal(
                    "--min-population %r: %r is not an integer" % (raw, number))
        else:
            try:
                number = int(token)
            except ValueError:
                raise ConformanceRefusal(
                    "--min-population %r: expected CHECK-NN=N or a bare integer"
                    % raw)
            for check_id in check_ids:
                overrides[check_id] = number
    return overrides


def manifest_floor_overrides(manifest, slug):
    """a design rule's per-artifact override, read from the manifest and never written."""
    declared = manifest.get("min_population_overrides") or {}
    if not isinstance(declared, dict):
        return {}
    overrides = {}
    flat = dict((key, value) for key, value in declared.items()
                if isinstance(value, int))
    overrides.update(flat)
    per_slug = declared.get(slug)
    if isinstance(per_slug, dict):
        overrides.update(dict((key, value) for key, value in per_slug.items()
                              if isinstance(value, int)))
    return overrides


# ---------------------------------------------------------------------------
# One artifact
# ---------------------------------------------------------------------------


@dataclass
class ArtifactRun:
    artifact_dir: str = ""
    slug: str = ""
    code: int = 0
    records: list = field(default_factory=list)
    guards: list = field(default_factory=list)
    waivers: WaiverCensus = None
    counts: dict = field(default_factory=dict)
    discovered_found: int = 0
    discovered_declared: int = 0
    refusal: str = ""
    # [{check_id, kind, reason}] for every member the applicability
    # declaration excluded before it ran. Mirrors run_self's list exactly, so a
    # consumer reads the artifact half and the --self half the same way.
    not_applicable: list = field(default_factory=list)


def run_artifact(artifact, core, contract, discovery, manifest=None,
                 cli_overrides=None, slug=None, stream=None, live_store="",
                 records_dir=""):
    """Run every discovered check plus the two runner properties over ONE artifact."""
    stream = stream if stream is not None else sys.stdout
    manifest = manifest or {}
    artifact = os.path.abspath(str(artifact))
    slug = slug or os.path.basename(artifact)

    run = ArtifactRun(artifact_dir=artifact, slug=slug,
                      discovered_found=discovery.found,
                      discovered_declared=discovery.declared)

    if not os.path.isdir(artifact):
        run.refusal = ("%s is not a directory, so there was nothing to check"
                       % artifact)
        run.code = core.EXIT_DID_NOT_RUN
        population_line(core, "ARTIFACT", False, 0, 0, 1, note=run.refusal,
                        stream=stream)
        return run

    guard_code, guard_note = d02_guard(core, artifact)
    run.guards.append({"guard_id": BANNED_SPELLING_GUARD_ID, "code": guard_code,
                       "note": guard_note})

    census = resolve_waivers(artifact)
    run.waivers = census
    honoured = list(census.honoured)

    overrides = manifest_floor_overrides(manifest, slug)
    overrides.update(cli_overrides or {})

    # `live_store` and `records_dir` are CHECK-20's two out-of-artifact inputs.
    # Empty means "resolve the real ones", which is right for a real run and
    # wrong for a test -- so a caller that has a fixture pins them here rather
    # than letting the check reach the owner's private record from a temp dir.
    ctx = contract.CheckContext(artifact_slug=slug, floor_overrides=overrides,
                               waivers=honoured, manifest=manifest, strict=True,
                               live_store=live_store, records_dir=records_dir)

    # APPLICABILITY IS DECIDED HERE, BEFORE ANY MODULE RUNS (the design rules).
    #
    # The row comes from the manifest the RUNNER resolved -- never from a file
    # inside the artifact -- and an unknown slug resolves to an
    # empty row, which every predicate reads as "applicable". So the default is
    # always the strict one.
    row = manifest_row(manifest, slug)
    inapplicable = {}
    for member in ARTIFACT_SUBSET:
        if member.applies is not None and not member.applies(artifact, row):
            inapplicable[member.member_id] = member.reason(row)

    modules = sorted(discovery.modules,
                     key=lambda module: getattr(module, "CHECK_ID", ""))
    for module in modules:
        check_id = getattr(module, "CHECK_ID", "CHECK-??")
        source = SOURCE_MODULE_PREFIX + os.path.basename(
            getattr(module, "__file__", "?") or "?")
        floor = ctx.floor_for(check_id,
                              getattr(module, "DEFAULT_FLOOR", 1))
        if check_id in inapplicable:
            reason = inapplicable[check_id]
            run.records.append(not_applicable_record(
                check_id, floor, reason, source, stream=stream))
            run.not_applicable.append({"check_id": check_id,
                                       "kind": LABEL_CHECK,
                                       "reason": reason})
            continue
        try:
            result = module.run(artifact, ctx)
        except Exception as error:               # a module that raised is a guard failure
            result = contract.CheckResult(
                check_id=check_id, code=core.EXIT_GUARD_FAIL, found=0,
                checked=0, floor=floor, waived=0,
                note="the check module raised %s: %s"
                     % (type(error).__name__, error))
        result = normalize_zero_population(core, result)
        printed_waived = waived_count_for_line(census, result)
        result.waived = printed_waived
        run.records.append(record_for(core, result, source, stream=stream))

    floor_10 = ctx.floor_for(CHECK_10, RUNNER_DEFAULT_FLOORS[CHECK_10])
    ten = check_10_result(core, contract, census, floor_10)
    ten = normalize_zero_population(core, ten)
    ten.waived = waived_count_for_line(census, ten)
    run.records.append(record_for(core, ten, SOURCE_RUNNER, stream=stream))

    floor_11 = ctx.floor_for(CHECK_11, RUNNER_DEFAULT_FLOORS[CHECK_11])
    eleven = check_11_result(core, contract, list(run.records), floor_11)
    eleven = normalize_zero_population(core, eleven)
    eleven.waived = waived_count_for_line(census, eleven)
    run.records.append(record_for(core, eleven, SOURCE_RUNNER, stream=stream))

    # THE AGGREGATE IS OVER THE APPLICABLE RECORDS ONLY. This one filter is
    # the mechanism: `run_self` has had it since a design rule (its aggregate is over
    # `ran_ids`), which is why `--self` is EXIT=0 today while naming eleven
    # members it did not run. Without it, a member that does not apply
    # contributes a code and the artifact can never be anything but a finding.
    codes = [record.code for record in run.records if record.applicable]
    counts = core.count_codes(codes)
    counts["waived"] = sum(record.waived for record in run.records
                           if record.applicable)
    run.counts = counts
    stream.write(core.summary_line(counts) + "\n")
    # BOTH counts on ONE parseable line, the same pair --self prints, spelled
    # the same way. A reader told only how many checks RAN cannot tell a run
    # that narrowed its own population from one that had nothing to narrow.
    stream.write("artifact: ran %d, not-applicable %d (every one is named "
                 "above with its reason)\n"
                 % (len(codes), len(run.not_applicable)))

    for guard in run.guards:
        stream.write("guard %-12s %-11s %s\n"
                     % (guard["guard_id"],
                        _verdict_for_code(core, guard["code"]), guard["note"]))

    run.code = core.aggregate(codes + [guard["code"] for guard in run.guards])
    return run


def _verdict_for_code(core, code):
    for verdict, mapped in core.VERDICT_CODES.items():
        if mapped == code:
            return verdict
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# The cross-artifact census (a design rule)
# ---------------------------------------------------------------------------


def is_artifact_shaped(path):
    """A narrow predicate, so the extras count stays a signal rather than noise."""
    path = str(path)
    if not os.path.isdir(path):
        return False
    if not os.path.isfile(os.path.join(path, ARTIFACT_SHAPE_REQUIRED)):
        return False
    return any(os.path.exists(os.path.join(path, name))
               for name in ARTIFACT_SHAPE_ANY)


@dataclass
class ScanCensus:
    """The scan's own population, with every number it can report.

    TWO IDENTITIES, both asserted rather than suggested:

        checked + waived + extras + missing         == expected
        checked + waived + extras + missing + pending == listed

    `listed` is every slug the manifest declared scanned plus every
    artifact-shaped directory found that is not one of them. `expected` is the
    part of that population that ought to be ON DISK right now -- the same
    number with the not-yet-built `pending` slugs removed. Both are printed,
    because a reader who is told only the first cannot tell a clean scan from
    one that quietly narrowed its own population.
    """

    scan_root: str = ""
    depth: int = 1
    enumerated: int = 0
    unrelated: list = field(default_factory=list)
    checked: list = field(default_factory=list)
    waived: list = field(default_factory=list)
    extras: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    pending: list = field(default_factory=list)
    stale_pending: list = field(default_factory=list)
    declared_scanned: int = 0

    @property
    def listed(self):
        return self.declared_scanned + len(self.extras)

    @property
    def expected(self):
        return self.listed - len(self.pending)

    @property
    def closes(self):
        """Both identities, evaluated. A population line whose arithmetic does
        not close is decoration, not evidence."""
        short = (len(self.checked) + len(self.waived) + len(self.extras)
                 + len(self.missing)) == self.expected
        full = (len(self.checked) + len(self.waived) + len(self.extras)
                + len(self.missing) + len(self.pending)) == self.listed
        shape = len(self.unrelated) + self.artifact_shaped == self.enumerated
        return bool(short and full and shape)

    @property
    def artifact_shaped(self):
        return len(self.checked) + len(self.waived) + len(self.extras) \
            + len(self.stale_pending)

    def as_dict(self):
        return {
            "scan_root": self.scan_root.replace(chr(92), "/"),
            "depth": self.depth,
            "enumerated": self.enumerated,
            "unrelated": len(self.unrelated),
            "artifact_shaped": self.artifact_shaped,
            "declared_scanned": self.declared_scanned,
            "listed": self.listed,
            "expected": self.expected,
            "checked": len(self.checked),
            "waived": len(self.waived),
            "extras": len(self.extras),
            "missing": len(self.missing),
            "pending": len(self.pending),
            "stale_pending": len(self.stale_pending),
            "identity_closes": self.closes,
            "checked_slugs": list(self.checked),
            "waived_slugs": list(self.waived),
            "extra_slugs": list(self.extras),
            "missing_slugs": list(self.missing),
            "pending_slugs": list(self.pending),
            "stale_pending_slugs": list(self.stale_pending),
        }


def slug_is_waived(scan_root, slug):
    """A slug is excused from the scan only by a COMMITTED whole-artifact waiver."""
    artifact = os.path.join(scan_root, slug)
    if not os.path.isdir(artifact):
        return False
    resolved, entries, _ = read_committed_waivers(artifact)
    if not resolved:
        return False
    return any(waiver_is_well_formed(entry)
               and entry.get("check_id") == WAIVE_ALL for entry in entries)


def census(scan_root, manifest, waived_slugs=None):
    """Classify every immediate child of the scan root against the expected set.

    Enumeration stops at depth 1. That depth is the whole mechanism by which the
    committed broken-fixture tree is never scanned: this repository lives INSIDE
    the scan root, so the fixture tree IS a descendant of it, and what holds is
    that it is never ENUMERATED.
    """
    scan_root = os.path.abspath(str(scan_root))
    report = ScanCensus(scan_root=scan_root, depth=declared_scan_depth(manifest))

    slugs = manifest.get("slugs") or []
    declared = {}
    for entry in slugs:
        if not isinstance(entry, dict) or not entry.get("scanned"):
            continue
        declared[str(entry.get("slug"))] = str(entry.get("status")
                                               or STATUS_PENDING)
    report.declared_scanned = len(declared)

    children = []
    if os.path.isdir(scan_root):
        children = sorted(name for name in os.listdir(scan_root)
                          if os.path.isdir(os.path.join(scan_root, name)))
    report.enumerated = len(children)

    shaped = set()
    for name in children:
        if is_artifact_shaped(os.path.join(scan_root, name)):
            shaped.add(name)
        else:
            report.unrelated.append(name)

    explicit_waivers = set(waived_slugs or [])

    for name in sorted(declared):
        status = declared[name]
        present = name in shaped
        if status == STATUS_PENDING:
            report.pending.append(name)
            if present:
                report.stale_pending.append(name)
            continue
        if not present:
            report.missing.append(name)
            continue
        if name in explicit_waivers or slug_is_waived(scan_root, name):
            report.waived.append(name)
            continue
        report.checked.append(name)

    for name in sorted(shaped):
        if name not in declared:
            report.extras.append(name)

    # A pending slug whose directory EXISTS is counted in BOTH `pending` (its
    # status) and `stale_pending` (the finding), so the partition stays exact
    # while the finding keeps a count of its own. Its directory is nevertheless
    # artifact-shaped, which is why artifact_shaped adds stale_pending back.
    return report


def print_census(core, report, stream):
    """Print the scan's own population, including the directory count it covered."""
    stream.write("scan root      %s\n" % report.scan_root.replace(chr(92), "/"))
    stream.write("enumerated     %d directory(ies) at depth %d; %d artifact-shaped, "
                 "%d unrelated\n"
                 % (report.enumerated, report.depth, report.artifact_shaped,
                    len(report.unrelated)))
    stream.write("expected set   listed=%d expected=%d checked=%d waived=%d "
                 "extras=%d missing=%d pending=%d stale-pending=%d\n"
                 % (report.listed, report.expected, len(report.checked),
                    len(report.waived), len(report.extras),
                    len(report.missing), len(report.pending),
                    len(report.stale_pending)))
    stream.write("identity       checked + waived + extras + missing == expected: "
                 "%s\n" % ("closes" if report.closes else "DOES NOT CLOSE"))
    if report.extras:
        stream.write("extras         %d (counted, exit unchanged): %s\n"
                     % (len(report.extras),
                        ", ".join(report.extras[:MAX_LISTED])))
    if report.missing:
        stream.write("missing        %d built slug(s) with no directory: %s\n"
                     % (len(report.missing),
                        ", ".join(report.missing[:MAX_LISTED])))
    if report.stale_pending:
        stream.write("stale manifest %d pending slug(s) whose directory EXISTS: %s\n"
                     % (len(report.stale_pending),
                        ", ".join(report.stale_pending[:MAX_LISTED])))
    stream.write("closeout       pending=%d (a project requirement closes when this reaches 0)\n"
                 % len(report.pending))


def census_codes(core, report):
    """The census's own contribution to the aggregate.

    Extras never move the exit code. Missing built slugs and a stale
    manifest do.
    """
    codes = []
    codes.append(core.EXIT_FINDING if report.missing else core.EXIT_PASS)
    codes.append(core.EXIT_FINDING if report.stale_pending else core.EXIT_PASS)
    return codes


# ---------------------------------------------------------------------------
# Reports (the design rules)
# ---------------------------------------------------------------------------


def check_entry(record):
    return {
        "check_id": record.check_id,
        "code": record.code,
        "verdict": record.verdict,
        "found": record.found,
        "checked": record.checked,
        "floor": record.floor,
        "waived": record.waived,
        "finding_ids": list(record.finding_ids),
        "listed": record.listed,
        "not_examined": record.not_examined,
        "note": record.note,
        "source": record.source,
    }


def artifact_entry(run):
    waivers = run.waivers or WaiverCensus()
    return {
        "artifact": run.slug,
        "artifact_dir": run.artifact_dir.replace(chr(92), "/"),
        "code": run.code,
        "refusal": run.refusal,
        "summary": dict(run.counts),
        "guards": list(run.guards),
        "waivers": {
            "working_present": waivers.working_present,
            "committed_resolved": waivers.committed_resolved,
            "declarations": waivers.declarations,
            "working": len(waivers.working),
            "committed": len(waivers.committed),
            "honoured": len(waivers.honoured),
            "uncommitted": len(waivers.uncommitted),
            "malformed": len(waivers.malformed),
            "errors": list(waivers.errors),
        },
        # THE PAIRED SPLIT, mirroring run_self's at the --self half: checks[]
        # holds the members that RAN, not_applicable_checks[] holds the rest
        # WITH their reasons. A member in neither list would be a checker
        # silently absent from the report, which reads as a contract that
        # shrank; a member in both would be a run that both happened and did
        # not.
        "checks": [check_entry(record) for record in run.records
                   if record.applicable],
        "not_applicable_checks": list(run.not_applicable),
    }


def build_report(core, mode, runs, scan=None, discovery=None, code=0):
    checks = []
    not_applicable = []
    if len(runs) == 1:
        checks = [check_entry(record) for record in runs[0].records
                  if record.applicable]
        not_applicable = list(runs[0].not_applicable)
    summary = {"pass": 0, "finding": 0, "did_not_run": 0, "guard_fail": 0,
               "waived": 0, "extras": 0,
               "checked_artifacts": len(runs),
               "expected_artifacts": scan.expected if scan else len(runs)}
    for run in runs:
        for key in ("pass", "finding", "did_not_run", "guard_fail", "waived"):
            summary[key] += run.counts.get(key, 0)
    if scan is not None:
        summary["extras"] = len(scan.extras)
    return {
        "schema": SCHEMA,
        "schema_version": core.SCHEMA_VERSION,
        "tool_schema": TOOL_SCHEMA,
        "tool": TOOL,
        "mode": mode,
        "artifact": runs[0].slug if len(runs) == 1 else "",
        "generated_at": core.now_local(),
        "code": code,
        "runner_check_ids": list(RUNNER_CHECK_IDS),
        "discovered": {
            "found": discovery.found if discovery else 0,
            "declared": discovery.declared if discovery else 0,
            "ids": list(discovery.ids) if discovery else [],
            "missing_ids": list(discovery.missing_ids) if discovery else [],
        },
        "summary": summary,
        "checks": checks,
        "not_applicable_checks": not_applicable,
        "artifacts": [artifact_entry(run) for run in runs],
        "scan": scan.as_dict() if scan is not None else None,
    }


def resolve_report_path(report_path, artifact_dirs, allow_inside):
    """a design rule: refuse to write a report INSIDE an artifact unless told to.

    The checker must not mutate what it checks. A report written inside the tree
    becomes an input to any hash over it and shows up in git status, which then
    needs a permanent exclusion rule someone will forget.
    """
    target = os.path.abspath(str(report_path))
    if allow_inside:
        return target
    for artifact in artifact_dirs:
        root = os.path.abspath(str(artifact))
        if target == root or target.startswith(root + os.sep):
            raise ConformanceRefusal(
                "--report %s resolves INSIDE the artifact %s. The checker must "
                "not mutate what it checks: a report written inside becomes an "
                "input to any hash over that tree. REPAIR: write it outside, or "
                "pass --report-inside to opt in deliberately." % (target, root))
    return target


# ---------------------------------------------------------------------------
# --self: running the named subset against THIS repository
# ---------------------------------------------------------------------------


def load_repo_side(name):
    """Load a REPO-SIDE tool BY PATH, or return None in a vendored copy.

    tools/lint_banned_names.py and tools/vendor.py are not in the vendored set:
    an artifact has no `tools/` directory and nothing to vendor. This file IS
    vendored, so it must be able to run beside them and without them, and it must
    say WHICH. Returning None rather than raising is what lets `--self` report
    "this is a vendored copy; <name> is repo-side only" as a stated skip instead
    of dying with a traceback that names an implementation detail.
    """
    path = os.path.join(CORE_ROOT, name)
    if not os.path.isfile(path):
        return None
    stem = os.path.splitext(name)[0] + "_for_self_check"
    spec = importlib.util.spec_from_file_location(stem, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:                     # a repo-side tool that will not import
        return None
    return module


def _self_result(contract, member_id, code, found, checked, listed=0,
                 not_examined=0, note="", finding_ids=None):
    return contract.CheckResult(
        check_id=member_id, code=code, found=found, checked=checked, floor=1,
        waived=0, not_examined=not_examined,
        listed=listed or (checked + not_examined),
        note=note, finding_ids=sorted(finding_ids or []))


def self_module_check(member_id, core, contract, discovery, root):
    """CHECK-07 / CHECK-08, run UNCHANGED against this repository's root."""
    modules = {getattr(module, "CHECK_ID", ""): module
               for module in discovery.modules}
    module = modules.get(member_id)
    if module is None:
        return _self_result(
            contract, member_id, core.EXIT_DID_NOT_RUN, 0, 0,
            note="%s has no module under %s/, so the subset named a check that "
                 "does not exist here. That is a finding about the subset, not "
                 "about this repository." % (member_id, CHECKS_DIRNAME))
    ctx = contract.CheckContext(artifact_slug=os.path.basename(root),
                                manifest={}, strict=True)
    result = module.run(root, ctx)
    return normalize_zero_population(core, result)


def self_lint_banned_names(core, contract, root):
    """LINT-BANNED-NAMES, over every TRACKED file in this repository (the banned-spelling rule)."""
    lint = load_repo_side(LINT_MODULE_NAME)
    if lint is None:
        return _self_result(
            contract, LINT_ID, core.EXIT_DID_NOT_RUN, 0, 0,
            note="%s is not beside this file. It is repo-side and is not in the "
                 "vendored set, so a vendored copy of this runner cannot reach "
                 "it." % LINT_MODULE_NAME)
    report = lint.scan(root)
    counts = report.counts
    note = ("occurrences=%d lines-with-hits=%d files-with-hits=%d | roles: "
            "live %d, frozen %d, detector %d, unclassified %d | real files at "
            "the banned path: %d"
            % (report.occurrences, report.lines_with_hits,
               report.files_with_hits, counts[lint.ROLE_LIVE],
               counts[lint.ROLE_FROZEN], counts[lint.ROLE_DETECTOR],
               counts[lint.ROLE_UNCLASSIFIED], len(report.real_files)))
    finding_ids = [
        "lint:%s:%s:%d:%d" % (hit.verdict.role, hit.path, hit.line, hit.col)
        for hit in report.hits
        if hit.verdict.role in lint.FINDING_ROLES][:MAX_LISTED]
    return _self_result(
        contract, LINT_ID, report.code, report.findings, report.scanned,
        listed=report.listed, not_examined=max(report.listed - report.scanned, 0),
        note=note, finding_ids=finding_ids)


# The module names no repo-side file may import as a dotted package module
#. ASSEMBLED FROM FRAGMENTS so this file's own source is not a hit for the
# scan it performs -- the same shape the sibling suite assertion uses, and the
# same shape the fail-closed hook guard needed after its first draft matched its
# own explanatory comment.
_CORE_NAME = "canon" + "kit"
_PKG_NAME = "tools" + "."
SELF_FORBIDDEN_MODULES = (
    _CORE_NAME,
    _PKG_NAME + _CORE_NAME,
    _PKG_NAME + "conformance",
    _PKG_NAME + "render",
    _PKG_NAME + "checks",
)

# The two call names that turn a STRING into an import. Nothing else does, and in
# particular spec_from_file_location does NOT: that is the path-based load a design rule
# REQUIRES. Flagging it would make the guard forbid the correct behaviour.
SELF_DYNAMIC_IMPORT_CALLS = ("import_module", "__import__")


def _forbidden_module(name):
    return isinstance(name, str) and any(
        name == mod or name.startswith(mod + ".")
        for mod in SELF_FORBIDDEN_MODULES)


def _called_name(node):
    func = getattr(node, "func", None)
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _package_import_hits(path, relative):
    """Every LIVE package import of the vendored set in one file.

    STRUCTURAL on both axes -- import nodes and the two dynamic-import calls --
    never a text match. an earlier plan wrote the text form twice and both drafts were
    too loose: the first fired against a docstring QUOTING the criterion it
    explained, the second matched the FILENAME `canonkit.py` through
    startswith("canonkit.") and produced 26 confident false findings in the one
    module whose entire job is copying that file.
    """
    hits = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            tree = ast.parse(handle.read(), str(path))
    except (OSError, SyntaxError) as error:
        return ["core:unreadable:%s (%s)" % (relative, type(error).__name__)]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _forbidden_module(alias.name):
                    hits.append("core:package-import:%s:%d" % (relative, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and _forbidden_module(node.module):
                hits.append("core:package-import-from:%s:%d" % (relative, node.lineno))
        elif (isinstance(node, ast.Call)
              and _called_name(node) in SELF_DYNAMIC_IMPORT_CALLS):
            for arg in node.args:
                if (isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                        and _forbidden_module(arg.value.strip())):
                    hits.append("core:dynamic-import:%s:%d"
                                % (relative, node.lineno))
    return hits


def self_core_contract(core, contract, root):
    """The design rule split, re-surfaced: ASCII, stdlib-only, never a package import.

    The population is FILES EXAMINED and it is printed: the frozen core plus
    every repo-side module under tools/ that is not itself vendored. A scan over
    an empty population would make `all(...)` report every input passing, which
    is exactly the shape this runner exists to refuse.
    """
    tools_dir = os.path.join(root, "tools")
    core_path = os.path.join(tools_dir, _CORE_NAME + ".py")
    if not os.path.isfile(core_path):
        return _self_result(
            contract, CORE_CONTRACT_ID, core.EXIT_DID_NOT_RUN, 0, 0,
            note="no frozen core at %s, so the design rule split has nothing to be "
                 "asserted about." % core_path)

    vendor = load_repo_side(VENDOR_MODULE_NAME)
    vendored = set()
    if vendor is not None:
        vendored = {os.path.normcase(os.path.abspath(
            os.path.join(root, rel.replace("/", os.sep))))
            for rel in vendor.resolve_vendored_set(root)}

    checks_dir = os.path.normcase(os.path.abspath(
        os.path.join(tools_dir, CHECKS_DIRNAME)))

    examined, findings = [], []

    # (a) the frozen core: ASCII bytes, stdlib imports only.
    examined.append("tools/" + _CORE_NAME + ".py")
    with open(core_path, "rb") as handle:
        payload = handle.read()
    non_ascii = [index for index, byte in enumerate(payload) if byte > 127]
    if non_ascii:
        findings.append("core:non-ascii:tools/%s.py:%d byte(s)"
                        % (_CORE_NAME, len(non_ascii)))
    try:
        tree = ast.parse(payload.decode("utf-8", "replace"), core_path)
    except SyntaxError:
        findings.append("core:unparseable:tools/%s.py" % _CORE_NAME)
        tree = None
    stdlib = getattr(sys, "stdlib_module_names", frozenset())
    if tree is not None and stdlib:
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            for name in names:
                top = (name or "").split(".")[0]
                if top and top not in stdlib:
                    findings.append("core:non-stdlib-import:tools/%s.py:%d:%s"
                                    % (_CORE_NAME, node.lineno, top))

    # (b) every repo-side module: no package import of the vendored set.
    for walk_root, dirnames, filenames in os.walk(tools_dir):
        dirnames[:] = [name for name in sorted(dirnames)
                       if name not in ("__pycache__",)]
        if os.path.normcase(os.path.abspath(walk_root)) == checks_dir:
            dirnames[:] = []
            continue
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            path = os.path.join(walk_root, name)
            if os.path.normcase(os.path.abspath(path)) in vendored:
                continue
            relative = os.path.relpath(path, root).replace(chr(92), "/")
            examined.append(relative)
            findings.extend(_package_import_hits(path, relative))

    checked = len(examined)
    code = (core.EXIT_DID_NOT_RUN if checked == 0
            else (core.EXIT_FINDING if findings else core.EXIT_PASS))
    note = ("files-examined=%d (frozen core + repo-side modules under tools/, "
            "vendored set and %s/ excluded) | vendored-set resolved=%d"
            % (checked, CHECKS_DIRNAME, len(vendored)))
    return _self_result(contract, CORE_CONTRACT_ID, code, len(findings), checked,
                        note=note, finding_ids=findings[:MAX_LISTED])


def self_vendor_consistency(core, contract, root):
    """a project requirement, re-surfaced: the declaration agrees with its literal and hashes.

    TWO POPULATIONS, both printed, neither standing in for the other. The first
    is the vendored-set files in this repository, which is what `checked`
    counts. The second is the artifacts carrying a `.vendor.json` for those files
    to be compared against, which is ZERO until an artifact is built -- reported
    in the note with its reason rather than folded into the verdict.
    """
    vendor = load_repo_side(VENDOR_MODULE_NAME)
    if vendor is None:
        return _self_result(
            contract, VENDOR_CONSISTENCY_ID, core.EXIT_DID_NOT_RUN, 0, 0,
            note="%s is not beside this file. It is repo-side and is not in the "
                 "vendored set, so a vendored copy of this runner cannot reach "
                 "it." % VENDOR_MODULE_NAME)

    findings = []
    declared = list(vendor.VENDORED_SET)
    if len(declared) != vendor.VENDORED_SET_COUNT:
        findings.append("vendor:declaration-drift:%d declared, literal %d"
                        % (len(declared), vendor.VENDORED_SET_COUNT))

    resolved = vendor.resolve_vendored_set(root)
    checked = 0
    for relative in resolved:
        path = os.path.join(root, relative.replace("/", os.sep))
        if not os.path.isfile(path):
            findings.append("vendor:missing:%s" % relative)
            continue
        try:
            digest = core.sha256_file(path)
        except OSError as error:
            findings.append("vendor:unhashable:%s (%s)"
                            % (relative, type(error).__name__))
            continue
        if not (isinstance(digest, str) and len(digest) == 64):
            findings.append("vendor:bad-digest:%s" % relative)
            continue
        checked += 1

    artifacts_with_record = 0
    scan_root = os.path.dirname(root)
    if os.path.isdir(scan_root):
        for name in sorted(os.listdir(scan_root)):
            candidate = os.path.join(scan_root, name, vendor.VENDOR_RECORD_NAME)
            if os.path.isfile(candidate):
                artifacts_with_record += 1

    code = (core.EXIT_DID_NOT_RUN if checked == 0
            else (core.EXIT_FINDING if findings else core.EXIT_PASS))
    note = ("vendored-set files hashed=%d of %d (declared %d + check modules %d)"
            " | artifacts carrying %s: %d%s"
            % (checked, len(resolved), len(declared),
               len(resolved) - len(declared), vendor.VENDOR_RECORD_NAME,
               artifacts_with_record,
               "" if artifacts_with_record else
               " (none built yet -- the cross-repository comparison has no "
               "second side and is NOT reported as agreeing)"))
    return _self_result(contract, VENDOR_CONSISTENCY_ID, code, len(findings),
                        checked, note=note, finding_ids=findings[:MAX_LISTED])


SELF_RUNNERS = {
    "CHECK-07": lambda core, contract, discovery, root: self_module_check(
        "CHECK-07", core, contract, discovery, root),
    "CHECK-08": lambda core, contract, discovery, root: self_module_check(
        "CHECK-08", core, contract, discovery, root),
    LINT_ID: lambda core, contract, discovery, root: self_lint_banned_names(
        core, contract, root),
    CORE_CONTRACT_ID: lambda core, contract, discovery, root: self_core_contract(
        core, contract, root),
    VENDOR_CONSISTENCY_ID: (
        lambda core, contract, discovery, root: self_vendor_consistency(
            core, contract, root)),
}


def self_line(stream, member_id, kind, verdict, body):
    """ONE line per member, ran or skipped, in a shape a test can PARSE.

    The label sits in its own column rather than inside the prose, so a reader
    and a regex reach the same conclusion about which items a success criterion scopes over.
    """
    stream.write("%-18s %-16s %-11s %s\n" % (member_id, kind, verdict, body))


def run_self(core, contract, discovery, root, stream):
    """Run the named subset against `root` and return (code, payload)."""
    if not SELF_SUBSET:
        raise ConformanceRefusal(
            "the --self subset resolves to ZERO members, so this run would "
            "report a verdict over nothing. A self-check that ran nothing and a "
            "self-check that found everything clean render identically, and "
            "only one of them is evidence. REPAIR: declare at least one member "
            "in SELF_SUBSET.")

    root = os.path.abspath(str(root))
    stream.write("self-check         scope=%s\n" % root.replace(chr(92), "/"))

    runnable, inapplicable = [], []
    for member in SELF_SUBSET:
        if member.applies is None or member.applies(root):
            runnable.append(member)
        else:
            inapplicable.append(member)

    if not runnable:
        raise ConformanceRefusal(
            "every one of the %d declared --self member(s) is inapplicable to "
            "%s, so the subset resolves to zero checks and this run would "
            "report a verdict over nothing. REPAIR: point --self at a tree the "
            "subset applies to, or narrow the applicability predicates."
            % (len(SELF_SUBSET), root))

    kinds = {member.member_id: member.kind for member in SELF_SUBSET}
    records, skipped_entries = {}, {}

    for member in runnable:
        runner = SELF_RUNNERS.get(member.member_id)
        if runner is None:
            result = _self_result(
                contract, member.member_id, core.EXIT_GUARD_FAIL, 1, 0,
                note="%s is declared in SELF_SUBSET with no runner behind it"
                     % member.member_id)
        else:
            try:
                result = runner(core, contract, discovery, root)
            except Exception as error:      # a member that raised is a guard failure
                result = _self_result(
                    contract, member.member_id, core.EXIT_GUARD_FAIL, 1, 0,
                    note="the member raised %s: %s" % (type(error).__name__, error))
        records[member.member_id] = record_for(
            core, normalize_zero_population(core, result),
            SOURCE_RUNNER, stream=io.StringIO())

    for member in inapplicable:
        skipped_entries[member.member_id] = member.inapplicable_reason
    for check_id in DECLARED_SELF_CHECK_IDS:
        if check_id in records or check_id in skipped_entries:
            continue
        skipped_entries[check_id] = SELF_SKIP_REASONS.get(
            check_id,
            "outside the declared --self subset, and no reason was recorded for "
            "it. An unexplained skip is an input silently dropped.")
        kinds.setdefault(check_id, LABEL_CHECK)

    order = list(DECLARED_SELF_CHECK_IDS) + [
        member.member_id for member in SELF_SUBSET
        if member.kind == LABEL_SUITE_ASSERTION]
    for member_id in order:
        kind = kinds.get(member_id, LABEL_CHECK)
        if member_id in records:
            record = records[member_id]
            self_line(stream, member_id, kind, record.verdict,
                      record.line.split(None, 2)[-1] if record.line else "")
        else:
            self_line(stream, member_id, kind, SELF_NOT_APPLICABLE,
                      skipped_entries[member_id])

    ran_ids = [member_id for member_id in order if member_id in records]
    skipped_ids = [member_id for member_id in order if member_id in skipped_entries]

    counts = core.count_codes([records[mid].code for mid in ran_ids])
    counts["waived"] = 0
    stream.write(core.summary_line(counts) + "\n")
    # BOTH counts on ONE parseable line. The second one is spelled
    # `not-applicable` and NOT with canonkit's banned verdict word, which this
    # tool's output may never carry (CHECK-11): that word reads as "deliberately
    # and safely omitted", which is exactly how a population of zero gets filed
    # as a pass by a human reading a log. Same number, same reason printed beside
    # every one of them, a word that cannot be misread -- the identical trade the
    # population line already makes when it renames the core's count to
    # `not-examined`.
    stream.write("self: ran %d, not-applicable %d (every one is named above "
                 "with its reason)\n" % (len(ran_ids), len(skipped_ids)))

    code = core.aggregate([records[mid].code for mid in ran_ids])
    payload = {
        "schema": SCHEMA,
        "schema_version": core.SCHEMA_VERSION,
        "tool_schema": TOOL_SCHEMA,
        "tool": TOOL,
        "mode": SELF_MODE,
        "scope": root.replace(chr(92), "/"),
        "generated_at": core.now_local(),
        "code": code,
        "ran": len(ran_ids),
        "not_applicable": len(skipped_ids),
        "declared_self_check_ids": list(DECLARED_SELF_CHECK_IDS),
        "runner_check_ids": list(RUNNER_CHECK_IDS),
        "summary": dict(counts),
        "checks": [dict(check_entry(records[mid]), kind=kinds.get(mid, LABEL_CHECK))
                   for mid in ran_ids],
        "not_applicable_checks": [
            {"check_id": mid, "kind": kinds.get(mid, LABEL_CHECK),
             "reason": skipped_entries[mid]} for mid in skipped_ids],
        "artifacts": [],
        "scan": None,
    }
    return code, payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def discover_checks(core, contract, stream):
    """Discovery, with its two RAISING conditions surfaced as exit-2 refusals.

    A PARTIAL module set is NOT one of them. N < 9 is the expected state through
    the waves that add the modules one plan at a time, and a runner that refused
    on it could never reach the step that proves the round trip.
    """
    checks_dir = os.path.join(HERE, CHECKS_DIRNAME)
    try:
        return contract.discover(checks_dir)
    except contract.DiscoveryError as error:
        raise ConformanceRefusal(str(error))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="conformance",
        description="Run every conformance check over an artifact, print each "
                    "check's own population, and write a versioned report.",
        epilog="Capture a run by redirecting into a file and reading it back: "
               "conformance.py <artifact> --report out.json > run.txt 2>&1; "
               'echo "EXIT=$?". Never capture it off a pipeline -- the pipeline '
               "reports its last stage's status, not this tool's.")
    parser.add_argument("artifact", nargs="?", default=".",
                        help="the artifact directory (default: the current one)")
    parser.add_argument("--scan", action="store_true",
                        help="scan every artifact under the declared scan root "
                             "instead of one named directory")
    parser.add_argument("--self", action="store_true", dest="self_check",
                        help="check THIS repository over the named subset. "
                             "Prints every declared checker it skipped WITH a "
                             "reason and a count, and refuses with exit 2 when "
                             "the subset resolves to zero members.")
    parser.add_argument("--scan-root", default=None,
                        help="override the derived scan root")
    parser.add_argument("--manifest", default=None,
                        help="path to the expected set (default: beside this file)")
    parser.add_argument("--live-store", default=None,
                        help="the directory holding the collections entries "
                             "CHECK-20 reads. Default: the real store beside "
                             "this repository. Pin it for a test, or every run "
                             "opens the real private record.")
    parser.add_argument("--records-dir", default=None,
                        help="the directory holding the correction records "
                             "CHECK-20 reads. Default: _records/corrections.")
    parser.add_argument("--census-only", action="store_true",
                        help="report the scan's census without running the checks")
    parser.add_argument("--report", default=None,
                        help="write the structured report here. A FILE rather "
                             "than a stream a caller has to capture.")
    parser.add_argument("--report-inside", action="store_true",
                        help="opt in to writing a report inside an artifact")
    parser.add_argument("--min-population", action="append", default=None,
                        dest="min_population",
                        help="override an effective floor: CHECK-NN=N, or a bare "
                             "integer for every check. The OVERRIDDEN value prints.")
    args = parser.parse_args(argv)

    stream = sys.stdout
    core = load_core()
    contract = load_contract()

    try:
        discovery = discover_checks(core, contract, stream)
        manifest = load_manifest(args.manifest)
        known_ids = list(discovery.ids) + list(RUNNER_CHECK_IDS)
        cli_overrides = parse_floor_overrides(args.min_population, known_ids)

        if args.self_check:
            # main_repo_root(), never cwd and never the artifact argument: a
            # vendored copy inside an artifact would otherwise self-check the
            # artifact and call it the repository.
            code, payload = run_self(core, contract, discovery,
                                     main_repo_root(), stream)
            if args.report:
                core.atomic_write_json(
                    resolve_report_path(args.report, [], True), payload)
            return code

        if args.scan:
            scan_root = (os.path.abspath(str(args.scan_root)) if args.scan_root
                         else declared_scan_root(manifest))
            report_obj = census(scan_root, manifest)
            print_census(core, report_obj, stream)

            if not report_obj.checked:
                code = scan_over_zero_artifacts(core, report_obj, stream)
                payload = build_report(core, "scan", [], scan=report_obj,
                                       discovery=discovery, code=code)
                if args.report:
                    core.atomic_write_json(
                        resolve_report_path(args.report, [], True), payload)
                return code

            runs = []
            if not args.census_only:
                for slug in report_obj.checked:
                    stream.write("\nartifact       %s\n" % slug)
                    runs.append(run_artifact(
                        os.path.join(scan_root, slug), core, contract, discovery,
                        manifest=manifest, cli_overrides=cli_overrides, slug=slug,
                        stream=stream, live_store=args.live_store or "",
                        records_dir=args.records_dir or ""))
            codes = [run.code for run in runs] + census_codes(core, report_obj)
            code = core.aggregate(codes)
            payload = build_report(core, "scan", runs, scan=report_obj,
                                   discovery=discovery, code=code)
            if args.report:
                target = resolve_report_path(
                    args.report, [run.artifact_dir for run in runs],
                    args.report_inside)
                core.atomic_write_json(target, payload)
            return code

        artifact = os.path.abspath(str(args.artifact))
        run = run_artifact(artifact, core, contract, discovery,
                           manifest=manifest, cli_overrides=cli_overrides,
                           stream=stream, live_store=args.live_store or "",
                           records_dir=args.records_dir or "")
        payload = build_report(core, "artifact", [run], scan=None,
                               discovery=discovery, code=run.code)
        if args.report:
            target = resolve_report_path(args.report, [artifact],
                                         args.report_inside)
            core.atomic_write_json(target, payload)
        if run.refusal:
            sys.stderr.write("%s %s\n" % (core.REFUSAL_PREFIX, run.refusal))
            sys.stderr.flush()
        return run.code
    except ConformanceRefusal as refusal:
        core.die(core.EXIT_DID_NOT_RUN,
                 "%s %s" % (core.REFUSAL_PREFIX, refusal))


if __name__ == "__main__":
    sys.exit(main())
