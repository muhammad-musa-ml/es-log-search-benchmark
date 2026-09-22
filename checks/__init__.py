"""The check-module contract and its discovery. Vendored beside canonkit.py.

NO PLAN THAT ADDS A CHECK MODULE ALSO EDITS THIS FILE -- except one that adds an
ID, which is a different act and is described four paragraphs down.

That is a scheduling property, not a style preference. Five separate plans add
check modules and three of them run in the SAME WAVE. A shared literal that each
of them had to increment would make those three plans conflict on one file, so
the universe of check ids is DECLARED UP FRONT and each check plan then adds
only its own `check_NN.py`. The five check plans own disjoint files and can
share a wave. Declaring the universe removes the shared write.

WHY THE COUNT IS 11 AND NOT 13.
CHECK-01..CHECK-09, CHECK-16 and CHECK-20 are MODULE-backed checks, transcribed
once from the project requirements document. CHECK-10 (waivers are countable) and
CHECK-11 (every check prints its own population) are properties of the RUNNER,
not modules -- an earlier plan owns them. A module count of 13 would be looking for
two files that will never exist.

CHECK-20 TAKES THE NEXT FREE ID, NOT THE NEXT NUMBER. CHECK-12..CHECK-19 were
already reserved in the project requirements document for named v2 triggers before it was
declared, so renumbering to close the gap would have moved eight reservations to
buy tidiness. The tuple below is ordered as the requirements file writes it and
the gap is deliberate.

CHECK-16 ARRIVED BY ITS OWN TRIGGER FIRING, WHICH IS WHY THIS FILE MOVED.
The paragraph above this one used to say that no later plan edits this file, and
the reason it gave was a SCHEDULING one: five check plans running in overlapping
waves cannot share a literal each of them has to increment. That reason still
holds for those five and it did its job. It was never an argument that the
declared universe is closed forever -- CHECK-12..CHECK-19 were reserved here
precisely because more checkers were expected. CHECK-16's reservation reads
"trigger: the first retraction", and the first retraction happened, so the id
moves from the reserved list into this tuple and both literals move with it in
the same commit.

THE DERIVE-AND-ASSERT SHAPE (a design rule, applied to the check set).
`DECLARED_MODULE_COUNT` is a committed integer literal asserted against
`len(DECLARED_CHECK_IDS)` at import time. A purely derived count silently stops
checking when an id is dropped, because expected falls to match found. The
literal is the tripwire on the derivation's own input.

DURING AN EARLIER ROUND-8, N IS LESS THAN THE DECLARED COUNT BY DESIGN.
`discover()` prints `checks found N of 11 declared` with BOTH numbers and does
NOT fail on a partial set: the check modules arrive one plan at a time. Plan
an earlier plan asserts N == the declared count once every check has landed. A discovery
that failed on a partial set would be red for six plans and would be ignored by
the seventh.
"""

import importlib.util
import os
from dataclasses import dataclass, field

__all__ = [
    "CheckResult",
    "CheckContext",
    "DiscoverReport",
    "DiscoveryError",
    "DECLARED_CHECK_IDS",
    "DECLARED_MODULE_COUNT",
    "discover",
]


# ---------------------------------------------------------------------------
# The declared universe
# ---------------------------------------------------------------------------

# Transcribed ONCE from the project requirements document, "Conformance checker -- the
# v1 contract". One line each, so a reader can reconcile this tuple against the
# requirements file without opening a third document.
DECLARED_CHECK_IDS = (
    "CHECK-01",   # a figure without its population; count unclassified numerals
    "CHECK-02",   # README date absent, or != a machine-emitted started_at's date
    "CHECK-03",   # "what this does not show" absent / template-identical / thin
    "CHECK-04",   # gate.json absent, mis-ordered, or a measurement with no token
    "CHECK-05",   # a missing register row, reported as `expected N, found M`
    "CHECK-06",   # a results file with no machine-emitted run record
    "CHECK-07",   # not a git work tree / zero commits / no tracked results file
    "CHECK-08",   # an unpinned specifier, a digest-less image, a floating tag
    "CHECK-09",   # a claim-under-test block missing its ids, text or verdict
    "CHECK-16",   # a figure declared retracted that is still being asserted
    "CHECK-20",   # a built slug that left its collections entry uncorrected
)

# The committed literal. Raised as a real exception rather than asserted with
# `assert`, because `python -O` strips assert statements and a tripwire that
# disappears under an optimisation flag is not a tripwire.
DECLARED_MODULE_COUNT = 11

if len(DECLARED_CHECK_IDS) != DECLARED_MODULE_COUNT:
    raise RuntimeError(
        "DECLARED_CHECK_IDS holds %d id(s) but the committed literal "
        "DECLARED_MODULE_COUNT says %d. Update BOTH in the same commit, or the "
        "derived count silently stops checking."
        % (len(DECLARED_CHECK_IDS), DECLARED_MODULE_COUNT))

if len(set(DECLARED_CHECK_IDS)) != len(DECLARED_CHECK_IDS):
    raise RuntimeError("DECLARED_CHECK_IDS contains a duplicate id")

CHECK_MODULE_GLOB_PREFIX = "check_"


class DiscoveryError(Exception):
    """A found check module violates the declared universe."""


# ---------------------------------------------------------------------------
# The result and context a check module exchanges with the runner
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """What every check module's run() returns.

    `found` and `checked` are SEPARATE numbers for the same reason
    canonkit.report() prints them separately: `found=1200 checked=0` makes a
    filter that removed everything visible, and one number cannot.

    `code` is the check-level exit code (0/1/2/3). A check that examined zero
    inputs must return 2, never 0 -- canonkit.aggregate() then lifts it to 1 at
    the artifact level without erasing the distinction, which
    survives in the summary counts line and in the --report JSON.

    `not_examined` is spelled that way because the obvious alternative is the
    word canonkit declares BANNED_VERDICT. It was the obvious alternative here
    until 2026-09-21, and the field name is not cosmetic: it is the name every
    check module types when it builds its result and the key every module's
    --report JSON carries, so the contract's own vocabulary is where the banned
    spelling would keep being re-seeded, one check module at a time.
    """

    check_id: str
    code: int
    found: int
    checked: int
    floor: int
    waived: int = 0
    not_examined: int = 0
    listed: int = None
    finding_ids: list = field(default_factory=list)
    note: str = ""

    def __post_init__(self):
        if self.listed is None:
            self.listed = self.checked + self.not_examined


@dataclass
class CheckContext:
    """Everything a check module needs from the runner, passed rather than imported.

    Kept deliberately small and additive. an earlier plan owns the runner and may add
    fields; a check module must read what it needs by name and never assume the
    set is closed.

    `floor_overrides` carries a design rule's command-line and per-artifact overrides. The
    EFFECTIVE floor -- the one actually applied after overrides -- is what the
    runner prints, because printing the declared floor while applying a
    different one is a population line that lies.
    """

    artifact_slug: str = ""
    floor_overrides: dict = field(default_factory=dict)
    waivers: list = field(default_factory=list)
    manifest: dict = field(default_factory=dict)
    strict: bool = True

    # WHERE THE OUT-OF-ARTIFACT EVIDENCE LIVES, when the caller pins it.
    #
    # CHECK-20 is the only check that reads anything outside the directory under
    # test: the live collections entries, and the records that say what a
    # measurement did to each claim. Neither can be found inside an artifact,
    # and neither may be SUPPLIED by one -- a checker the thing being checked
    # can point at its own evidence is not a checker. So they ride here, set by
    # the runner from its own flags, and default to the real ones when unset.
    #
    # Left empty this resolves to the owner's live store, which is correct for a
    # real run and wrong for a test: until these existed, every conformance run
    # in the suite opened the real private record from a pytest temp directory.
    live_store: str = ""
    records_dir: str = ""

    def floor_for(self, check_id, default_floor):
        """The EFFECTIVE floor for `check_id`: an override if one exists, else the default."""
        return self.floor_overrides.get(check_id, default_floor)


@dataclass
class DiscoverReport:
    """What discover() found, with both numbers."""

    found: int = 0
    declared: int = 0
    modules: list = field(default_factory=list)
    ids: list = field(default_factory=list)
    missing_ids: list = field(default_factory=list)
    protocol_violations: list = field(default_factory=list)

    @property
    def complete(self):
        return self.found == self.declared


# ---------------------------------------------------------------------------
# discover()
# ---------------------------------------------------------------------------


def _load_module_by_path(path):
    """Load one check module BY PATH, without registering it in sys.modules.

    Not registering is deliberate: a test loads a TEMP COPY of this package with
    the same file stems as the real one, and a sys.modules entry keyed on the
    stem would hand the second caller the first caller's module. The check
    modules are self-contained, so nothing needs the registration.
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(stem, path)
    if spec is None or spec.loader is None:
        raise DiscoveryError("could not build an import spec for %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover(package_dir, verbose=True):
    """Import every check_*.py in `package_dir` and assert the declared universe.

    RAISES on exactly two conditions, and no others:

      1. a found module whose CHECK_ID is outside DECLARED_CHECK_IDS -- a stray
         module, or one whose CHECK_ID attribute is absent entirely (absent
         reads as None, which is outside the universe);
      2. two modules declaring the SAME CHECK_ID.

    Removing a check_*.py from the directory is NOT one of them. A partial set
    is the EXPECTED state through an earlier round-8 and is reported, not raised.

    A module that satisfies (1) and (2) but is missing DEFAULT_FLOOR or run() is
    recorded in `report.protocol_violations` and PRINTED with a count, rather
    than raised: the runner (an earlier plan) decides what an unusable module does to
    a run, and this function's contract is the two conditions above. The
    information is surfaced, not dropped.

    PRINTS `checks found N of 11 declared` with both numbers.
    """
    package_dir = str(package_dir)
    report_obj = DiscoverReport(declared=len(DECLARED_CHECK_IDS))

    if not os.path.isdir(package_dir):
        raise DiscoveryError("discover(): %s is not a directory" % package_dir)

    names = sorted(
        name for name in os.listdir(package_dir)
        if name.startswith(CHECK_MODULE_GLOB_PREFIX) and name.endswith(".py")
    )

    seen = {}
    for name in names:
        path = os.path.join(package_dir, name)
        module = _load_module_by_path(path)
        check_id = getattr(module, "CHECK_ID", None)

        if check_id not in DECLARED_CHECK_IDS:
            raise DiscoveryError(
                "%s declares CHECK_ID=%r, which is OUTSIDE the declared universe "
                "of %d id(s): %s. A stray check module is a finding: it runs, it "
                "reports, and nothing reconciles it against the requirements."
                % (name, check_id, len(DECLARED_CHECK_IDS),
                   list(DECLARED_CHECK_IDS)))

        if check_id in seen:
            raise DiscoveryError(
                "%s and %s both declare CHECK_ID=%r. Two modules under one id "
                "means one of them silently never runs, and the runner's count "
                "would still read as complete."
                % (seen[check_id], name, check_id))

        seen[check_id] = name
        report_obj.modules.append(module)
        report_obj.ids.append(check_id)

        if not isinstance(getattr(module, "DEFAULT_FLOOR", None), int):
            report_obj.protocol_violations.append(
                "%s declares no int DEFAULT_FLOOR (a design rule needs a per-check floor "
                "declared IN CODE)" % name)
        if not callable(getattr(module, "run", None)):
            report_obj.protocol_violations.append(
                "%s exposes no callable run(artifact, ctx)" % name)

    report_obj.found = len(report_obj.modules)
    report_obj.missing_ids = [cid for cid in DECLARED_CHECK_IDS if cid not in seen]

    if verbose:
        print("checks found %d of %d declared"
              % (report_obj.found, report_obj.declared))
        if report_obj.missing_ids:
            print("  (not yet landed: %d -- %s)"
                  % (len(report_obj.missing_ids), ", ".join(report_obj.missing_ids)))
        if report_obj.protocol_violations:
            print("  (protocol violations: %d)" % len(report_obj.protocol_violations))
            for violation in report_obj.protocol_violations:
                print("    %s" % violation)

    return report_obj
