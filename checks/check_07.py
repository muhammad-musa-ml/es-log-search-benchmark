"""CHECK-07 -- a git work tree, with commits, whose results are TRACKED.

    python check_07.py <artifact> [--report FILE] [--min-population N]

the project requirements document states the check verbatim: "Fails when the artifact is not a git
work tree, has zero commits, or has no tracked machine-written file under
`results/` -- verified with `git ls-files`, not with 'the file exists'."

THIS CHECK IS THE TRUE ROOT, AND BOTH SHIPPED ARTIFACTS FAIL IT TODAY
----------------------------------------------------------------------
Measured and recorded in the shared pattern note: `ls -d <artifact>/.git` returns "No such
file or directory" for BOTH artifacts that existed before this programme did.
Neither is a repository. Four other checks are unsatisfiable until that is fixed,
and an earlier round owns the fix. This module is not reporting a surprise; it is the
thing that makes an already-known absence countable.

EXISTENCE AND TRACKED-NESS ARE DIFFERENT CLAIMS, AND ONLY ONE SURVIVES A CLONE
-------------------------------------------------------------------------------
`os.path.exists` answers "is this file on this disk right now". `git ls-files`
answers "will a reader who clones this repository have it". an earlier round re-runs
every artifact FROM A CLEAN CHECKOUT, so the second question is the one that
decides whether an artifact can be handed to anybody. This module therefore never
asks the filesystem a question about version control. It shells out to git.

THE PER-ITEM RECORDS, AND WHY A TRACKED figures.json IS NOT ENOUGH
--------------------------------------------------------------------------
THE MOST IMPORTANT PARAGRAPH IN THIS FILE. A literal reading of the requirement
is satisfied by ONE tracked machine-written file under results/, and
results/figures.json is always the first one to qualify. That reading was tried
and it is measurably too weak.

MEASURED, in a throwaway git repository carrying templates/.gitignore verbatim,
BEFORE the repair that now ships in that file:

    git check-ignore -v results/raw/item-0001.json
      -> .gitignore:56:raw/    results/raw/item-0001.json
    git add -A   staged only:  .gitignore, results/figures.json

The artifact's own ignore rules swallowed results/raw/, where the PER-ITEM RUN
RECORDS live. The rule `raw/` sits in a licence block whose job is keeping source
corpora out of the index, and a bare directory pattern matches at ANY DEPTH, so
two different meanings of the word "raw" collided.

The consequence is not that a check failed. It is that a check PASSED:

    the chain is  per-item records -> count(predicate) -> numerator
                  -> / denominator -> rendered,  and verify.py re-walks it
    figures.json was tracked, so CHECK-07 reported a clean artifact
    the eight records that figure rests on were absent from the index
    a reader who clones gets the CONCLUSION and none of the EVIDENCE
    verify.py --tier derive on that clone re-derives over ZERO items

So this check asserts the PROPERTY -- the evidence a reader can re-walk is in the
index -- rather than the PROXY that a machine-written file exists under results/.
An artifact carrying a TRACKED figures.json must also carry its per-item records
in the index, and the two failure modes get two different finding ids because
they have two different repairs:

    records-untracked  the records are ON DISK and git is ignoring them. The
                       repair is to the ignore rules, and this check runs
                       `git check-ignore -v` and NAMES THE RULE AND LINE that is
                       swallowing them, because that one line of output is the
                       whole diagnosis.
    records-absent     no per-item records exist at all. A figure claims a
                       population and nothing under results/ holds the items it
                       counted.

The requirement is not being widened for its own sake. The records ARE
"machine-written files under results/"; what changed is that satisfying the check
now requires the ones the chain actually rests on, not merely the cheapest one
that matches the words.

A DIRECTORY NESTED IN ANOTHER REPOSITORY IS NOT A WORK TREE
-------------------------------------------------------------
`git rev-parse --is-inside-work-tree` answers TRUE for any directory beneath any
repository, so a plain folder sitting inside this one would pass a naive version
of branch one. The committed fixture is exactly that shape -- it must NOT be a
work tree while living inside one that is -- so omitting a nested .git is not
enough on its own.

This module therefore compares `git rev-parse --show-toplevel` against the
artifact directory and treats "inside a work tree whose root is somewhere else"
as NOT a work tree, with its own message NAMING the enclosing toplevel. That is
the difference between a check that works in a fixture and one that works on
disk.

WHEN THE WORK-TREE BRANCHES FIRE, THE TRACKED-NESS BRANCHES ARE NOT EVALUATED
------------------------------------------------------------------------------
Deliberate, and the reason is that they would be measuring the WRONG REPOSITORY.
Inside the enclosing checkout, `git ls-files` over a nested directory answers
about the ENCLOSING repository's index -- so the committed fixture's own files
are tracked, by this repository, and a check that reported that would print a
reassuring truth about an artifact that has no version control at all.

So those branches report `not-evaluated` WITH A REASON and the count is printed.
An input that was not examined is counted and given a reason; it is never
silently folded into a pass.

EXIT CODES (canonkit's contract, a design rule)
    0  a work tree, with commits, whose machine-written results AND per-item
       records are in the index
    1  at least one of the five conditions. The check DID look.
    2  it could not look: no results/ directory at all, git unavailable, or a
       population below the effective floor.

THE POPULATION IS THE FILES UNDER results/ THAT WERE EXAMINED, and it is printed.
A directory with no results/ at all has a population of zero and is DID-NOT-RUN
-- the check could not look, rather than found a problem. Reporting "not a work
tree" about a directory that is not an artifact at all would be a finding about
something that was never in scope.

VENDORING. Enumerated into the vendored set by tools/vendor.py's check-module
glob and copied to <artifact>/checks/check_07.py, beside <artifact>/canonkit.py.
Run BY PATH under a bare module name, never as a dotted package module. Stdlib
only, ASCII only.
"""

import argparse
import importlib.util
import os
import subprocess
import sys

CHECK_ID = "CHECK-07"

# a design rule: the POPULATION floor, declared per-check IN CODE, overridable on the
# command line, and the EFFECTIVE value is what prints as `floor=`. One file
# under results/ is the smallest population over which this check means anything.
DEFAULT_FLOOR = 1

SCHEMA = "canonkit/check-07/1"

HERE = os.path.dirname(os.path.abspath(__file__))
CORE_ROOT = os.path.dirname(HERE)

RESULTS_DIR = "results"

# Where runmeta.raw_dir() writes the PER-ITEM RUN RECORDS. The directory whose
# name collided with the licence block's `raw/` rule -- see the known hazard paragraph.
RAW_DIR = "raw"
RAW_RELATIVE = "%s/%s" % (RESULTS_DIR, RAW_DIR)

# The machine-written names, declared rather than inferred from a suffix.
# RESULTS.md is deliberately absent: an author writes prose into it, so its
# presence says nothing about whether a run happened.
MACHINE_WRITTEN = ("figures.json", "gate.json", "provenance.json", "run.json")

# The record whose presence makes per-item evidence REQUIRED. A figure is a claim
# about a population; the records are the population. Gating on this rather than
# demanding records unconditionally keeps the rule precise: the evidence is
# required BECAUSE a figure claims to rest on it.
FIGURES_NAME = "figures.json"
FIGURES_RELATIVE = "%s/%s" % (RESULTS_DIR, FIGURES_NAME)

FINDING_NOT_A_WORK_TREE = "not-a-work-tree"
FINDING_ENCLOSED = "enclosed-by-other-toplevel"
FINDING_ZERO_COMMITS = "zero-commits"
FINDING_NO_TRACKED_RESULTS = "no-tracked-results"
FINDING_RECORDS_UNTRACKED = "records-untracked"
FINDING_RECORDS_ABSENT = "records-absent"

NOT_EVALUATED = "not-evaluated"

MAX_LISTED_FINDINGS = 20

GIT_TIMEOUT = 60


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

    PREFERS AN ALREADY-LOADED COPY, for the reason check_03.py records: loading
    __init__.py by path a second time mints a SECOND CheckResult class that a
    runner comparing against its own would reject despite being identical.
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
# git, by subprocess. Never os.path.exists('.git').
# ---------------------------------------------------------------------------


def git(artifact, *args):
    """Run one git command in `artifact`. Returns (returncode, stdout, stderr).

    shell=False always, and the returned code is the CHILD's own. A shell
    pipeline would report its last stage's status, which is how a failing command
    reports success.
    """
    try:
        completed = subprocess.run(
            ["git", "-C", str(artifact)] + [str(arg) for arg in args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=GIT_TIMEOUT, shell=False)
    except OSError as error:
        raise CheckRefusal(
            "git could not be run (%s), so no fact about version control could "
            "be established. REPAIR: install git, or put it on PATH." % error)
    return completed.returncode, completed.stdout or "", completed.stderr or ""


def same_directory(left, right):
    """True when two path strings name the same directory.

    Compared after realpath and normcase because git prints forward slashes and
    Windows paths differ in case and separator without differing in meaning. A
    string comparison here would report every artifact on this machine as nested
    inside something else.
    """
    try:
        return (os.path.normcase(os.path.realpath(str(left)))
                == os.path.normcase(os.path.realpath(str(right))))
    except (OSError, ValueError):
        return False


def listed_files(artifact, pathspec):
    """`git ls-files` under one pathspec, as a sorted list of posix paths.

    THE INDEX, not the disk. This is the whole point of the check.
    """
    code, out, _ = git(artifact, "ls-files", "--", pathspec)
    if code != 0:
        return []
    return sorted(line.strip().replace(chr(92), "/")
                  for line in out.splitlines() if line.strip())


def files_on_disk(root, relative):
    """Every file under `<root>/<relative>`, as sorted posix paths from `root`."""
    base = os.path.join(str(root), *relative.split("/"))
    out = []
    for dirpath, _dirnames, filenames in os.walk(base):
        for name in filenames:
            full = os.path.join(dirpath, name)
            out.append(os.path.relpath(full, str(root)).replace(os.sep, "/"))
    return sorted(out)


def ignore_rule_for(artifact, relative_path):
    """The .gitignore RULE swallowing a path, as `file:line:pattern`, or "".

    `git check-ignore -v` is the one command that turns "this file is missing
    from the index" into "line 56 of .gitignore did it". That one line of output
    is the entire diagnosis of a known hazard, so the check emits it rather than leaving an
    author to rediscover it.
    """
    code, out, _ = git(artifact, "check-ignore", "-v", "--", relative_path)
    if code != 0 or not out.strip():
        return ""
    first = out.splitlines()[0].strip()
    # `<source>:<line>:<pattern>\t<path>` -- keep the rule, drop the path.
    return first.split(chr(9))[0].strip()


def git_facts(artifact):
    """Every MEASURED fact this check reasons about. No verdicts here.

    Live in the RED commit, so the transcript records a check that really
    measured its inputs and only got the verdict wrong.
    """
    artifact = os.path.abspath(str(artifact))
    facts = {
        "artifact": artifact,
        "is_work_tree": False,
        "toplevel": "",
        "enclosing_toplevel": "",
        "commits": 0,
        "results_on_disk": [],
        "tracked_results": [],
        "machine_written_tracked": [],
        "figures_tracked": False,
        "records_on_disk": [],
        "records_tracked": [],
        "records_ignore_rule": "",
        "tracked_evaluated": False,
        "not_evaluated_reason": "",
    }

    facts["results_on_disk"] = files_on_disk(artifact, RESULTS_DIR)

    code, out, _ = git(artifact, "rev-parse", "--is-inside-work-tree")
    inside = (code == 0 and out.strip() == "true")

    toplevel = ""
    if inside:
        code, out, _ = git(artifact, "rev-parse", "--show-toplevel")
        if code == 0:
            toplevel = out.strip()

    if inside and toplevel and same_directory(toplevel, artifact):
        facts["is_work_tree"] = True
        facts["toplevel"] = toplevel
    elif inside and toplevel:
        facts["enclosing_toplevel"] = toplevel

    if not facts["is_work_tree"]:
        facts["not_evaluated_reason"] = (
            "the artifact is not a work tree of its own, so `git ls-files` here "
            "would answer about %s's index rather than this artifact's"
            % (facts["enclosing_toplevel"] or "another repository"))
        return facts

    code, out, _ = git(artifact, "rev-list", "--count", "HEAD")
    if code == 0 and out.strip().isdigit():
        facts["commits"] = int(out.strip())

    facts["tracked_evaluated"] = True
    facts["tracked_results"] = listed_files(artifact, RESULTS_DIR)
    facts["machine_written_tracked"] = [
        path for path in facts["tracked_results"]
        if os.path.basename(path) in MACHINE_WRITTEN]
    facts["figures_tracked"] = FIGURES_RELATIVE in facts["tracked_results"]

    facts["records_on_disk"] = files_on_disk(artifact, RAW_RELATIVE)
    facts["records_tracked"] = [path for path in facts["tracked_results"]
                                if path.startswith(RAW_RELATIVE + "/")]

    if facts["records_on_disk"] and not facts["records_tracked"]:
        facts["records_ignore_rule"] = ignore_rule_for(
            artifact, facts["records_on_disk"][0])

    return facts


# ---------------------------------------------------------------------------
# THE DETECTION. A pure function of the measured facts, so the RED commit stubs
# exactly this and the GREEN commit replaces exactly this.
# ---------------------------------------------------------------------------


def worktree_findings(facts):
    """Every way an artifact fails to be a re-verifiable repository.

    A pure function of the measured facts -- no filesystem, no subprocess -- so
    what it decides is entirely a function of what it is handed, and the RED
    commit could stub exactly this while every measurement around it stayed live.

    THE EARLY RETURN IS LOAD-BEARING. When the work-tree branch fires, the
    tracked-ness branches are NOT evaluated, because `git ls-files` run inside a
    directory that is not its own work tree answers about the ENCLOSING
    repository's index. Reporting that would be a reassuring truth about an
    artifact with no version control at all. run() prints `not-evaluated` and the
    reason instead: an input that was not examined is counted and given a reason,
    never folded into a pass.
    """
    findings = []

    if not facts["is_work_tree"]:
        if facts["enclosing_toplevel"]:
            findings.append({
                "kind": FINDING_ENCLOSED,
                "id": "worktree:%s" % FINDING_ENCLOSED,
                "detail": "this directory is INSIDE a work tree whose root is "
                          "%s, and is not a work tree of its own. git answers "
                          "`--is-inside-work-tree` TRUE for any directory "
                          "beneath any repository, so the absence of a nested "
                          ".git is not by itself the thing that matters -- the "
                          "toplevel not being this directory is. Its history, "
                          "its index and its commits all belong to the "
                          "enclosing repository. REPAIR: `git init` here, then "
                          "commit the artifact."
                          % facts["enclosing_toplevel"],
            })
        else:
            findings.append({
                "kind": FINDING_NOT_A_WORK_TREE,
                "id": "worktree:%s" % FINDING_NOT_A_WORK_TREE,
                "detail": "this directory is not a git work tree and is not "
                          "inside one. Nothing about it can be re-obtained by a "
                          "reader, and every downstream check that asks what is "
                          "TRACKED has nothing to ask. REPAIR: `git init` here, "
                          "then commit the artifact.",
            })
        return findings

    if facts["commits"] == 0:
        findings.append({
            "kind": FINDING_ZERO_COMMITS,
            "id": "worktree:%s" % FINDING_ZERO_COMMITS,
            "detail": "this is a work tree with no commits. An index is not "
                      "history: a clone of a repository with an unborn HEAD "
                      "carries no files at all, however full the index looks "
                      "here. REPAIR: commit.",
        })

    if not facts["machine_written_tracked"]:
        findings.append({
            "kind": FINDING_NO_TRACKED_RESULTS,
            "id": "worktree:%s" % FINDING_NO_TRACKED_RESULTS,
            "detail": "%d file(s) sit under %s/ on disk and git tracks none of "
                      "the machine-written ones (%s). \"The file exists\" and "
                      "\"git tracks the file\" are different claims and only the "
                      "second survives the clean checkout an earlier round re-runs from. "
                      "REPAIR: `git add` the run's output, or fix the ignore "
                      "rule keeping it out."
                      % (len(facts["results_on_disk"]), RESULTS_DIR,
                         ", ".join(MACHINE_WRITTEN)),
        })

    # The per-item records. Gated on a TRACKED figures record, because that is
    # what makes them required: a figure is a claim about a population, and the
    # records are the population it counted. Without a figures record there is no
    # claim, and the branch above is the one that speaks.
    if facts["figures_tracked"]:
        on_disk = facts["records_on_disk"]
        tracked = facts["records_tracked"]
        if not on_disk and not tracked:
            findings.append({
                "kind": FINDING_RECORDS_ABSENT,
                "id": "worktree:%s" % FINDING_RECORDS_ABSENT,
                "detail": "%s is tracked and %s/ holds no per-item run records "
                          "at all. The chain a reader re-walks is `per-item "
                          "records -> count(predicate) -> numerator -> / "
                          "denominator -> rendered`, and its first link is "
                          "missing, so the figure is a conclusion with no "
                          "evidence under it. REPAIR: keep the run's per-item "
                          "records and commit them."
                          % (FIGURES_RELATIVE, RAW_RELATIVE),
            })
        elif len(tracked) < len(on_disk):
            rule = facts["records_ignore_rule"]
            findings.append({
                "kind": FINDING_RECORDS_UNTRACKED,
                "id": "worktree:%s" % FINDING_RECORDS_UNTRACKED,
                "detail": "%s is tracked but only %d of %d per-item record(s) "
                          "under %s/ are in the index%s. THIS IS THE FAILURE "
                          "THAT LOOKS LIKE A PASS: the proxy is satisfied -- a "
                          "machine-written file under %s/ IS tracked -- while "
                          "the property is broken, because a fresh clone gets "
                          "the figure and none of the items it counted, and "
                          "`verify.py --tier derive` there re-derives over zero "
                          "of them. REPAIR: fix the rule named above, then "
                          "`git add %s/`."
                          % (FIGURES_RELATIVE, len(tracked), len(on_disk),
                             RAW_RELATIVE,
                             (", and they are ignored by %s" % rule) if rule
                             else "",
                             RESULTS_DIR, RAW_RELATIVE),
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


def run(artifact, ctx=None):
    """Measure. Returns a CheckResult. DOES NOT PRINT -- the caller prints."""
    core = load_core()
    contract = load_contract()
    ctx = ctx if ctx is not None else contract.CheckContext()
    floor = ctx.floor_for(CHECK_ID, DEFAULT_FLOOR)
    artifact = os.path.abspath(str(artifact))

    def refused(note, detail=None):
        result = contract.CheckResult(
            check_id=CHECK_ID, code=core.EXIT_DID_NOT_RUN, found=0, checked=0,
            floor=floor, waived=0, note=note)
        base = {"artifact": artifact, "findings": [], "facts": {}}
        base.update(detail or {})
        result.detail = base
        return result

    if not os.path.isdir(artifact):
        return refused("%s is not a directory" % artifact)

    if not os.path.isdir(os.path.join(artifact, RESULTS_DIR)):
        return refused(
            "%s carries no %s/ directory, so there is no machine-written output "
            "to ask git about. This is not a finding: saying \"not a work tree\" "
            "about a directory that is not an artifact at all would be a verdict "
            "on something this check was never pointed at. REPAIR: generate the "
            "artifact from the skeleton and run it."
            % (artifact, RESULTS_DIR))

    try:
        facts = git_facts(artifact)
    except CheckRefusal as refusal:
        return refused(str(refusal))

    checked = len(facts["results_on_disk"])
    findings = list(worktree_findings(facts))

    waived_ids = waiver_ids(getattr(ctx, "waivers", None))
    kept = [finding for finding in findings if finding["id"] not in waived_ids]
    waived = len(findings) - len(kept)

    found = len(kept)
    if checked == 0 or checked < floor:
        code = core.EXIT_DID_NOT_RUN
    elif found:
        code = core.EXIT_FINDING
    else:
        code = core.EXIT_PASS

    if facts["tracked_evaluated"]:
        tracked_note = ("tracked-under-results=%d of %d machine-written=%d "
                        "per-item-records on-disk=%d tracked=%d"
                        % (len(facts["tracked_results"]), checked,
                           len(facts["machine_written_tracked"]),
                           len(facts["records_on_disk"]),
                           len(facts["records_tracked"])))
    else:
        tracked_note = "tracked-ness %s (%s)" % (NOT_EVALUATED,
                                                 facts["not_evaluated_reason"])

    note = ("work-tree=%s commits=%d results-on-disk=%d | %s"
            % ("yes" if facts["is_work_tree"] else "NO", facts["commits"],
               checked, tracked_note))
    if facts["enclosing_toplevel"]:
        note += " | enclosing-toplevel=%s" % facts["enclosing_toplevel"]
    if facts["records_ignore_rule"]:
        note += " | ignored-by=%s" % facts["records_ignore_rule"]

    result = contract.CheckResult(
        check_id=CHECK_ID, code=code, found=found, checked=checked, floor=floor,
        waived=waived, note=note,
        finding_ids=sorted({finding["id"] for finding in kept}))
    result.detail = {"artifact": artifact, "findings": kept, "facts": facts}
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_report(result, core):
    """The structured record, over stable fields only."""
    detail = getattr(result, "detail", {}) or {}
    facts = detail.get("facts", {}) or {}
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
        "is_work_tree": facts.get("is_work_tree", False),
        "toplevel": facts.get("toplevel", ""),
        "enclosing_toplevel": facts.get("enclosing_toplevel", ""),
        "commits": facts.get("commits", 0),
        "results_on_disk": list(facts.get("results_on_disk", [])),
        "tracked_results": list(facts.get("tracked_results", [])),
        "machine_written_tracked": list(facts.get("machine_written_tracked", [])),
        "figures_tracked": facts.get("figures_tracked", False),
        "records_on_disk": list(facts.get("records_on_disk", [])),
        "records_tracked": list(facts.get("records_tracked", [])),
        "records_ignore_rule": facts.get("records_ignore_rule", ""),
        "tracked_evaluated": facts.get("tracked_evaluated", False),
        "not_evaluated_reason": facts.get("not_evaluated_reason", ""),
        "findings": detail.get("findings", []),
        "artifact": detail.get("artifact", ""),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_07",
        description="CHECK-07: fails when the artifact is not a git work tree, "
                    "has zero commits, or has no tracked machine-written file "
                    "under results/ -- including the per-item run records.")
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
        print("  %-27s %s" % (finding["kind"], finding["detail"]))
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
