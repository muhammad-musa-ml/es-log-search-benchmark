"""canonkit -- the frozen contract core. ASCII only, stdlib only, copied never imported.

    "G1 is only as strong as the number of keys compared. A near-empty
     comparison is an UNRUN check, not a pass."
        -- example-cache-benchmark/finalize.py:10-11, this program's owner,
           in a shipped artifact, before this repository existed.

That sentence is this phase's whole thesis and it governs every function below.
A verdict with no population beside it is not a verdict.

WHAT THIS FILE IS
------------------------------
This is the one file that must never differ across fourteen repositories. It is
authored HERE, copied BY BYTES into each artifact by tools/vendor.py, and run
THERE as a sibling module. It is never imported from the `tools` package -- see
tools/tests/test_repo_hygiene.py::test_frozen_core_is_never_imported, which
enforces that split with a test rather than with a convention, because a
convention is exactly what drifts.

Three constraints follow from being copied rather than installed, and all three
are asserted by tests rather than promised by this comment:

  * STDLIB ONLY. An artifact is handed over as a directory. A third-party import
    here would make a handed-over artifact un-runnable without a package index.
  * ASCII ONLY. The Windows console renders correct UTF-8 as replacement
    characters, so "it looked fine" is not evidence about this file's bytes.
    test_canonkit.py decodes the file as ASCII; it does not eyeball it.
  * NO STATE. Every function is pure or writes exactly one named file.

THE EXIT-CODE CONTRACT -- a caller branches on these
----------------------------------------------------
    0  EXIT_PASS         the check ran over a non-empty population and found nothing
    1  EXIT_FINDING      the check ran and found a problem the owner must act on
    2  EXIT_DID_NOT_RUN  the check could NOT look: zero population, missing input,
                         a refused precondition. Do not proceed.
    3  EXIT_GUARD_FAIL   a guard on the measurement itself failed

The framing is borrowed verbatim from placeholder_canon.py:951-959 ("the three
codes are a contract a skill body branches on"), and the fourth code from
redis/finalize.py:155. a design rule is therefore not an invented scheme: two unrelated
shipped codebases converged on the same semantics, and this file writes the
convergence down.

a design rule (HARD) adds the aggregation rule: a check-level 2 aggregates UP to 1 at the
artifact level, so the top-level verdict is unambiguously a finding. The per-check
distinction survives in two places the aggregate cannot erase -- summary_line()
and the --report JSON.

TWO SETTINGS THAT LOOK INCONSISTENT AND ARE NOT
-----------------------------------------------
atomic_write_json() here defaults to ensure_ascii=True because everything this
core writes is ASCII by contract. tools/canon_snapshot.py (an earlier plan)
deliberately passes ensure_ascii=False, because it stores verbatim Arabic and
English canon text and escaping it would destroy the verbatim-ness that is the
entire point of the snapshot. Two different settings for two different files,
each correct for what it writes.
"""

import datetime
import hashlib
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# a design rule's split, enforced BY THIS FILE at import time.
# ---------------------------------------------------------------------------
# This file sits inside the `tools` package directory, so CPython will happily
# resolve `import tools.canonkit` in a source checkout no matter what
# pyproject.toml says -- setuptools has no per-module exclusion, and
# pyproject.toml states that limit rather than pretending otherwise.
#
# an earlier plan asserted that the dotted import fails while this file DID NOT
# EXIST, where it passed for the wrong reason. Now that the file is real, the
# assertion holds only if the file itself refuses, so it does.
#
# A dotted __name__ means the core was reached through the package. Path-based
# loading -- what tools/vendor.py does here and what every artifact does with
# its vendored sibling copy -- gives a BARE name and is unaffected.
#
# Why it matters, restated from a design rule: importing the core here while artifacts
# import their vendored copy lets the two drift in the one file whose entire
# purpose is preventing drift. test_repo_hygiene.py scans for the import
# statement; this catches the import itself.
if "." in __name__:
    raise ImportError(
        "canonkit was imported as the package module %r. It is the FROZEN CORE "
        "(a design rule/a design rule): copied by bytes and loaded by PATH under a bare sibling "
        "name, never imported from the `tools` package. Load it with "
        "importlib.util.spec_from_file_location(), or run the vendored copy "
        "inside the artifact." % __name__)

# The schema token stamped into every record this core writes or validates.
# Neither shipped artifact carries a schema_version anywhere (measured: 0 hits
# across both trees), so there is no convention to inherit. an earlier round re-runs
# every artifact from a clean checkout and will read records written as early as
# an earlier round -- this field is how a reader then knows which shape it is holding.
SCHEMA_VERSION = "canonkit/1"

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_PASS = 0
EXIT_FINDING = 1
EXIT_DID_NOT_RUN = 2
EXIT_GUARD_FAIL = 3

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_DID_NOT_RUN = "DID-NOT-RUN"
VERDICT_GUARD_FAIL = "GUARD-FAIL"

# The mapping a caller uses to turn a printed verdict back into a code. Kept as
# data rather than an if-chain so a test can assert the two vocabularies are the
# same size and cover each other.
VERDICT_CODES = {
    VERDICT_PASS: EXIT_PASS,
    VERDICT_FAIL: EXIT_FINDING,
    VERDICT_DID_NOT_RUN: EXIT_DID_NOT_RUN,
    VERDICT_GUARD_FAIL: EXIT_GUARD_FAIL,
}

# The word this file refuses to print. A check that could not look must say so;
# "skipped" reads as "deliberately and safely omitted" and is how a zero
# population gets filed as a pass by a human reading the log (a design rule, CHECK-11).
#
# THIS DECLARATION IS THE DETECTOR'S NEEDLE, so the word appears here and here
# only. Until 2026-09-21 it also appeared as this file's OWN population label --
# `report()` printed `skipped=N` while every runner re-rendered the same line as
# `not-examined=N` -- so the frozen core and the convention disagreed and the
# core was the copy a reader of a standalone check actually saw. The label is
# now `not-examined=` at the one site that prints it, and the keyword that feeds
# it is `not_examined`.
#
# THE NAME IS `BANNED_VERDICT` AND THE SCAN IS NOT NARROWED TO THE VERDICT.
# tools/conformance.py::check_11_findings tests `BANNED_VERDICT in record.line`
# -- the WHOLE printed line, not the verdict column -- and
# tools/tests/test_exit_codes.py proves that with a line whose verdict is PASS
# and whose banned word sits in a count label. The name is kept because two
# committed RED transcripts cite it by name and a frozen transcript may not be
# edited to match a later rename.
BANNED_VERDICT = "skipped"


def die(code, message):
    """Print `message` to stderr and exit with `code`. Never returns.

    Refusals carry the `REFUSING:` prefix and a repair instruction. The shape is
    copied from redis/run_k6_sweep.py:101-107, which appears four times across
    that artifact -- so it is the artifact's convention rather than one author's
    habit -- and the repair-instruction variant from run_benchmark.py:36-43,
    which is the one worth copying because it tells the operator what to do.

    stderr rather than stdout is load-bearing: a caller redirecting stdout into
    a report file still sees the refusal.
    """
    sys.stderr.write("%s\n" % message)
    sys.stderr.flush()
    raise SystemExit(code)


# ---------------------------------------------------------------------------
# The population printer
# ---------------------------------------------------------------------------


def report(check_id, passed, found, checked, floor, waived=0, note="",
           not_examined=0, listed=None):
    """Print one population line. UNCONDITIONALLY, on every branch. Return the verdict.

    Source: pii-scanner.py:379-398, whose own dated comment states the reason --
    "until this print existed a clean scan over the whole list and a scan over
    zero files were byte-identical at the seam the pre-commit hook and the
    orchestrator's commit script read". The print is not logging. It is the
    only thing that distinguishes those two runs.

    THREE PROPERTIES, each load-bearing:

    1. It prints on a PASS and on a FAIL. Never conditional on the verdict. A
       print guarded by `if not passed` makes the clean run silent, and a silent
       run is indistinguishable from a run that never happened.

    2. `found` and `checked` are SEPARATE numbers. `found=1200 checked=0` makes
       a filter that removed everything visible; one number cannot. The
       not-examined count is printed beside them with the same reasoning.

    3. The identity `checked + not-examined == listed` is ENFORCED, not suggested.
       a shared pattern's strongest instance (pii-scanner.py:395-396) is "the two skip counts
       above go to stderr so a caller can assert scanned + never-ship +
       unreadable == listed" -- an identity a caller can assert is what separates
       a population line from decoration. Here the caller does not have to
       remember to assert it; passing an inconsistent triple raises.

    The EFFECTIVE floor and the waiver count are printed too (a design rule, CHECK-10).
    a design rule's load-bearing half is the PRINT: it turns `checked N of M` into a claim
    a reader can evaluate, and it stops a floor being quietly lowered.

    Args:
        check_id: the check's id, e.g. "CHECK-03".
        passed: the check's own boolean verdict. IGNORED when checked == 0.
        found: how many findings the check produced.
        checked: how many inputs it actually examined.
        floor: the EFFECTIVE minimum population for this check.
        waived: how many findings an owner-authored waiver suppressed.
        note: free text appended to the line.
        not_examined: inputs listed but not examined. Every one of them should
            have a reason printed by the caller beside this line. The keyword is
            spelled this way, and the label prints this way, because the obvious
            alternative is the word BANNED_VERDICT holds -- it reads as
            "deliberately and safely omitted", which is how a zero population
            gets filed as a pass by a human reading the log.
        listed: the population the check was handed. Defaults to
            checked + not_examined.

    Returns:
        One of VERDICT_PASS / VERDICT_FAIL / VERDICT_DID_NOT_RUN. Never
        BANNED_VERDICT.

    Raises:
        ValueError: on a negative count, or when checked + not_examined != listed.
    """
    for name, value in (("found", found), ("checked", checked),
                        ("floor", floor), ("waived", waived),
                        ("not_examined", not_examined)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(
                "report(%s): %s must be an int, got %r" % (check_id, name, value))
        if value < 0:
            raise ValueError(
                "report(%s): %s must be >= 0, got %d" % (check_id, name, value))

    if listed is None:
        listed = checked + not_examined
    if checked + not_examined != listed:
        raise ValueError(
            "report(%s): population identity broken -- checked(%d) + "
            "not-examined(%d) != listed(%d). A population line whose own "
            "arithmetic does not close is decoration, not evidence."
            % (check_id, checked, not_examined, listed))

    # THE ZERO-POPULATION BRANCH COMES FIRST AND OVERRIDES `passed`.
    # `verdict = VERDICT_PASS if passed else VERDICT_FAIL` is the simplification
    # a future maintainer will reach for. It is correct on every branch except
    # the one that matters, and the RED for this line is committed at 7dec844.
    if checked == 0:
        verdict = VERDICT_DID_NOT_RUN
    elif passed:
        verdict = VERDICT_PASS
    else:
        verdict = VERDICT_FAIL

    line = ("%-16s %-11s found=%d checked=%d of %d not-examined=%d floor=%d "
            "waived=%d"
            % (check_id, verdict, found, checked, listed, not_examined, floor,
               waived))
    if note:
        line = line + "  " + str(note)
    print(line)
    return verdict


def code_for(verdict):
    """Map a verdict string to its exit code. Unknown verdicts are a programming error."""
    if verdict not in VERDICT_CODES:
        raise ValueError(
            "code_for(): unknown verdict %r; known verdicts are %s"
            % (verdict, sorted(VERDICT_CODES)))
    return VERDICT_CODES[verdict]


def aggregate(codes):
    """Collapse per-check codes into one artifact-level code.

        every code 0            -> 0
        any code 3             -> 3
        anything else          -> 1     (so a check-level 2 aggregates UP to 1)
        NO codes at all        -> 2     (an aggregate over zero checks DID NOT RUN)

    THE EMPTY CASE IS THE WHOLE REASON THIS FUNCTION EXISTS RATHER THAN `all()`.
    `all([])` is True, so the obvious one-liner reports PASS over a check set
    that was never populated -- a glob that matched nothing, a discovery that
    imported nothing, a manifest that parsed empty. The research note calls this the
    highest-leverage pitfall in the phase, and the shared pattern note records the shipped
    analog: redis/finalize.py:139 is `all(g["passed"] for g in guards)` with no
    length check, safe ONLY because its seven appends happen to be unconditional.
    A copy of it whose guards were conditional would pass on zero guards.

    a design rule wants the per-check distinction to SURVIVE. Collapsing to one integer
    destroys it here by design, so it lives in two places this function cannot
    erase: summary_line() and the --report JSON's per-check `code`.
    """
    codes = list(codes)
    if not codes:
        return EXIT_DID_NOT_RUN
    for code in codes:
        if not isinstance(code, int) or isinstance(code, bool):
            raise ValueError("aggregate(): %r is not an exit code" % (code,))
    if EXIT_GUARD_FAIL in codes:
        return EXIT_GUARD_FAIL
    if all(code == EXIT_PASS for code in codes):
        return EXIT_PASS
    return EXIT_FINDING


def summary_line(counts):
    """Render the counts line that survives aggregation.

    "checks: N pass, N finding, N did-not-run, N guard-fail, N waived"

    Unknown keys raise rather than being ignored: a caller that misspells
    `did_not_run` would otherwise silently report zero for the one number this
    line exists to carry.
    """
    known = ("pass", "finding", "did_not_run", "guard_fail", "waived")
    unknown = sorted(set(counts) - set(known))
    if unknown:
        raise ValueError(
            "summary_line(): unknown count key(s) %s; known keys are %s"
            % (unknown, list(known)))
    return ("checks: %d pass, %d finding, %d did-not-run, %d guard-fail, %d waived"
            % (counts.get("pass", 0), counts.get("finding", 0),
               counts.get("did_not_run", 0), counts.get("guard_fail", 0),
               counts.get("waived", 0)))


def count_codes(codes):
    """Turn a list of per-check codes into the dict summary_line() consumes."""
    counts = {"pass": 0, "finding": 0, "did_not_run": 0, "guard_fail": 0, "waived": 0}
    for code in codes:
        if code == EXIT_PASS:
            counts["pass"] += 1
        elif code == EXIT_FINDING:
            counts["finding"] += 1
        elif code == EXIT_DID_NOT_RUN:
            counts["did_not_run"] += 1
        elif code == EXIT_GUARD_FAIL:
            counts["guard_fail"] += 1
        else:
            raise ValueError("count_codes(): %r is not an exit code" % (code,))
    return counts


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


def now_local():
    """Local time, ISO-8601, with a REAL UTC offset.

    NEVER the naive UTC constructor followed by a literal "Z". That constructor
    returns a datetime carrying NO timezone at all, and the appended "Z" is a
    lie that type-checks: the string claims UTC while the object is unaware, so
    every downstream consumer parsing it gets an aware datetime built from an
    unaware one.

    (The banned call is not named here in full. test_canonkit.py's guard is
    token-scoped and would not fire on this paragraph -- but the plan's own
    acceptance criterion for this file is a plain text grep, and a criterion
    that cannot tell a call from its prohibition should be given nothing to
    misread.)

    a design rule needs a real offset because CHECK-02 compares the LOCAL date component
    of a machine-emitted started_at against the README's date. On this machine
    that comparison is wrong by a day for several hours of every day if the
    stamp is silently UTC.
    """
    return datetime.datetime.now().astimezone().isoformat()


def now_utc():
    """UTC counterpart of now_local(), for cross-run ordering.

    Both are stored. Two fields cost nothing; picking one costs either the
    reader's intuition or correct ordering across a ~103-day program.
    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Hashing (tamper-EVIDENCE and integrity, NOT authentication)
# ---------------------------------------------------------------------------


def sha256_bytes(payload):
    """sha256 of a bytes object. Bytes in, hex out."""
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("sha256_bytes(): expected bytes, got %s" % type(payload).__name__)
    return hashlib.sha256(bytes(payload)).hexdigest()


def sha256_file(path):
    """sha256 of a file's BYTES. Never its decoded text.

    Source: redis/provenance.py:38-39. Reading as text would re-introduce the
    line-ending translation that a design rule and atomic_write_text() both exist to
    prevent, and would do it invisibly -- the same content would hash two ways
    on two machines.

    Chunked rather than read_bytes() so a multi-GB input (a corpus, a dump)
    cannot exhaust RAM. The digest is identical either way.
    """
    digest = hashlib.sha256()
    with open(str(path), "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Atomic, translation-free writes
# ---------------------------------------------------------------------------


def _assert_ascii(text, path):
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "refusing to write %s: byte offset %d is not ASCII (%r). This core "
            "and everything it writes are ASCII by contract. Pass "
            "ensure_ascii=False only for a file whose verbatim non-ASCII text is "
            "the point, such as the canon snapshot."
            % (path, exc.start, text[exc.start:exc.end])) from exc


def atomic_write_text(path, text, encoding="ascii", ensure_ascii=True):
    """Write `text` to `path` atomically, with NO line-ending translation.

    Source: the-upstream-project/scripts/shared/atomic.py:34-53.

    `newline=""` IS THE LINE THAT MATTERS MOST IN THIS FILE. a design rule fixes line
    endings at the GIT layer; this fixes them at the WRITE layer. A template or
    a vendored copy written without it gets every "\\n" translated to "\\r\\n"
    on the way out on Windows, and the sha256 an artifact then records differs
    from the sha256 this repository computes -- the exact a project requirement failure
    arriving through a door .gitattributes does not cover. BOTH fixes are
    needed; neither substitutes for the other.

    The temp file is created in the SAME directory as the target, because
    os.replace is atomic within a volume and is NOT atomic across one. Its name
    carries pid + uuid so two writers aiming at the same target cannot truncate
    each other mid-write. The `finally` unlink means a raise mid-stream leaves no
    .tmp sibling behind -- a stale .tmp is how a later glob counts a population
    that includes a half-written file.
    """
    path = str(path)
    if ensure_ascii:
        _assert_ascii(text, path)

    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

    tmp = "%s.%d.%s.tmp" % (path, os.getpid(), uuid.uuid4().hex)
    try:
        with open(tmp, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def atomic_write_json(path, obj, ensure_ascii=True):
    """Serialize `obj` and hand it to atomic_write_text().

    sort_keys=True is not cosmetic: a record whose key order varies between runs
    hashes differently on every write, which would make every sha256 assertion
    over a written record report tampering on a byte-identical payload.

    ensure_ascii defaults True here -- see the module docstring on why
    canon_snapshot.py correctly passes False.
    """
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=ensure_ascii) + "\n"
    atomic_write_text(path, text, encoding="utf-8" if not ensure_ascii else "ascii",
                      ensure_ascii=ensure_ascii)


# ---------------------------------------------------------------------------
# The run token (a design rule, HARD -- this DEPARTS from the research's formula)
# ---------------------------------------------------------------------------


def _normalize_realized(realized):
    """Render `realized` as a sorted list of stable "key=value" strings.

    json.dumps with sort_keys=True is used for the value so a nested dict
    renders identically on every run and in every process. Python's own repr()
    would not be safe here: set iteration order and float formatting can vary,
    and a token that is not reproducible is not a token.
    """
    if realized is None:
        return []
    if isinstance(realized, dict):
        return ["%s=%s" % (key, json.dumps(realized[key], sort_keys=True))
                for key in sorted(realized)]
    return [str(item) for item in realized]


def mint_run_token(slug, assertions, realized, inputs_hash):
    """Mint the gate's run token. sha256 over CONTENT ONLY.

        sha256(slug || sorted(assertions + realized) || inputs_hash)

    WHY `dated_at` IS NOT AN ARGUMENT.
    The research's formula folds `dated_at` into the digest. a design rule overrides it, and
    the reason is a discrimination argument rather than a preference. an earlier finding names
    two failures the token exists to catch:

      (i)  results produced under a gate that has since CHANGED -- caught
           exactly by a token over the gate's CONTENT, which is what this is;
      (ii) results copied from an EARLIER SESSION -- caught by `dated_at`,
           which is stamped BESIDE the token in every results file and names
           the gate INSTANCE.

    Folding the date in buys no discrimination over that pair, and costs a full
    re-measure after any gate re-run -- on a machine whose free VRAM has been
    observed at three values across two days, a gate re-run is routine.

    `assertions` and `realized` are SORTED, so the token does not depend on the
    order a gate happened to evaluate its preconditions in.

    Framing (Security Domain): this is tamper-EVIDENCE and integrity, NOT
    authentication. It does not make forgery impossible. It makes the two
    common real failures visible. Neither the README nor the register may
    overstate it.
    """
    parts = [str(slug)]
    combined = [str(item) for item in (assertions or [])] + _normalize_realized(realized)
    parts.extend(sorted(combined))
    parts.append(str(inputs_hash))
    # THERE IS NO `dated_at` PARAMETER, AND ITS ABSENCE IS THE GUARANTEE.
    # A parameter accepted-but-ignored would not hold this decision: the next
    # caller passes it and the one after that uses it. The RED that proves the
    # signature test discriminates is committed at c158f21.
    return sha256_bytes("\n".join(parts).encode("ascii", "backslashreplace"))


# ---------------------------------------------------------------------------
# The gate's refusal
# ---------------------------------------------------------------------------

REFUSAL_PREFIX = "REFUSING:"


def require_gate(results_dir, audit=False):
    """Refuse to proceed unless a dated, passing gate exists. Return its run token.

    Source shape: redis/run_k6_sweep.py:101-107, which appears four times
    across that artifact, plus run_benchmark.py:36-43's repair-instruction
    variant -- the one worth copying, because it tells the operator what to do
    rather than only what went wrong.

    Exits 2 (DID-NOT-RUN, not 1) on every refusal: an absent or failed gate
    means the check COULD NOT LOOK, which is a different claim from "looked and
    found a problem".

    AUDIT MODE. A FAILED gate still writes a full record and still MINTS
    its token, then exits 3. `audit=True` returns that token instead of
    refusing, so a tool auditing what actually ran can compare a measurement's
    stamped token against the FAILED gate's and say "this ran under a gate that
    did not pass". Minting no token on failure would leave such a measurement
    with no key at all and therefore UNDETECTABLE; minting one means it carries
    a POISONED token that verify.py rejects loudly.

    `ok` vs `passed`: the research sketch reads `ok`, the schema in this plan
    fixes `passed`. Both are accepted HERE so a record written against either
    spelling is still refused correctly; validate_gate() requires the schema's
    `passed` and is the place that enforces one name.
    """
    gate_path = os.path.join(str(results_dir), "gate.json")
    if not os.path.isfile(gate_path):
        die(EXIT_DID_NOT_RUN,
            "%s %s absent. Nothing has authorised a measurement here.\n"
            "  REPAIR: run `python gate.py` in the artifact root, then re-run this."
            % (REFUSAL_PREFIX, gate_path))

    try:
        with open(gate_path, "rb") as handle:
            gate = json.loads(handle.read().decode("utf-8"))
    except ValueError as exc:
        die(EXIT_DID_NOT_RUN,
            "%s %s is not parseable JSON (%s).\n"
            "  REPAIR: delete it and re-run `python gate.py`; never hand-edit a gate record."
            % (REFUSAL_PREFIX, gate_path, exc))

    if not gate.get("dated_at"):
        die(EXIT_DID_NOT_RUN,
            "%s %s carries no dated_at. An undated verdict is not a record -- it "
            "cannot be ordered against a measurement's started_at (CHECK-04).\n"
            "  REPAIR: re-run `python gate.py`, which stamps dated_at and dated_at_utc."
            % (REFUSAL_PREFIX, gate_path))

    token = gate.get("run_token")
    if not token:
        die(EXIT_DID_NOT_RUN,
            "%s %s carries no run_token. Even a FAILED gate mints one; a "
            "record without it leaves any measurement that ran anyway undetectable.\n"
            "  REPAIR: re-run `python gate.py`."
            % (REFUSAL_PREFIX, gate_path))

    passed = gate.get("ok", gate.get("passed"))
    if not passed:
        if audit:
            return token
        die(EXIT_DID_NOT_RUN,
            "%s the gate FAILED on %s. The canon's fallback wording governs and is\n"
            "quoted here verbatim from the record:\n%s\n"
            "  REPAIR: this path does not measure. Record the fallback wording in the\n"
            "  artifact's claim block; do not re-run the gate until the failure is fixed."
            % (REFUSAL_PREFIX, gate.get("failed_ids", "<no failed_ids recorded>"),
               gate.get("fallback_wording", "<no fallback_wording recorded>")))

    return token


# ---------------------------------------------------------------------------
# The schema validators -- hand-written, stdlib only
# ---------------------------------------------------------------------------
#
# a design rule forbids importing a JSON-schema LIBRARY here. The research note names this as
# the ONE place where hand-rolling is mandatory rather than merely acceptable.
#
# Each validator returns a LIST of violation strings rather than a bool, so a
# caller can print a COUNT. `[]` means valid. A bool would reduce every one of
# these to the bare verdict this whole file exists to refuse.
#
# READING IS PERMISSIVE ABOUT UNKNOWN KEYS, AND THAT IS MEASURED RATHER THAN
# LENIENT: 2 of the 49 canon bullets carry an extra `public` key, and a strict
# reader fails on them. An unknown key is never a violation here.

_COMPOUND_BULLET_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_-]*$")

SIMILARITY_VERDICTS = ("CONFIRMS", "SUPPORTS", "SUPPORTS-WITH-REVISION",
                       "DOES-NOT-SUPPORT", "REFRESH")


def _require_keys(obj, keys, where, violations):
    if not isinstance(obj, dict):
        violations.append("%s is %s, expected an object" % (where, type(obj).__name__))
        return False
    for key in keys:
        if key not in obj:
            violations.append("%s is missing required key %r" % (where, key))
    return True


def _require_type(obj, key, types, type_name, where, violations):
    if key not in obj:
        return
    value = obj[key]
    if isinstance(value, bool) and bool not in types:
        violations.append("%s.%s is a bool, expected %s" % (where, key, type_name))
        return
    if not isinstance(value, types):
        violations.append("%s.%s is %s, expected %s"
                          % (where, key, type(value).__name__, type_name))


GATE_REQUIRED_KEYS = ("schema", "schema_version", "artifact", "passed", "run_token",
                      "dated_at", "dated_at_utc", "assertions", "realized",
                      "inputs_hash", "failed_ids", "fallback_wording",
                      "fallback_source", "env")

FALLBACK_SOURCE_KEYS = ("path", "sha256", "read_at")


def validate_gate(obj):
    """Validate a gate.json record. Returns a list of violation strings."""
    violations = []
    if not _require_keys(obj, GATE_REQUIRED_KEYS, "gate", violations):
        return violations
    _require_type(obj, "passed", (bool,), "a bool", "gate", violations)
    _require_type(obj, "assertions", (list, tuple), "a list", "gate", violations)
    _require_type(obj, "failed_ids", (list, tuple), "a list", "gate", violations)
    _require_type(obj, "realized", (dict,), "an object", "gate", violations)
    _require_type(obj, "env", (dict,), "an object", "gate", violations)
    _require_type(obj, "run_token", (str,), "a string", "gate", violations)
    _require_type(obj, "inputs_hash", (str,), "a string", "gate", violations)
    _require_type(obj, "fallback_wording", (str,), "a string", "gate", violations)

    source = obj.get("fallback_source")
    if source is not None:
        _require_keys(source, FALLBACK_SOURCE_KEYS, "gate.fallback_source", violations)

    # a design rule: a FAILED gate is a legal, complete record -- but it must SAY which
    # assertions failed. `passed: false` with an empty failed_ids is a refusal
    # that names nothing, which is the same shape as a verdict with no count.
    if obj.get("passed") is False and not obj.get("failed_ids"):
        violations.append(
            "gate.passed is false but failed_ids is empty -- a refusal that names "
            "nothing cannot be acted on")
    if obj.get("passed") is True and obj.get("failed_ids"):
        violations.append(
            "gate.passed is true but failed_ids lists %d id(s)"
            % len(obj["failed_ids"]))
    return violations


FIGURES_REQUIRED_KEYS = ("schema", "schema_version", "artifact", "gate_token",
                         "dated_at", "started_at", "started_at_utc", "figures")

FIGURE_REQUIRED_KEYS = ("value", "unit", "population", "population_label",
                        "derived_from", "canon_bullet", "canon_value", "similar",
                        "similar_reason_ref", "tier_achieved",
                        "reproduce_criterion", "threshold_claim", "not_shown")

# a design rule: a figure claiming a THRESHOLD was crossed needs replicates. One run that
# lands the right side of a line is not evidence that the line was crossed.
THRESHOLD_CLAIM_MIN_RUNS = 3


def validate_figures(obj):
    """Validate a figures.json record. Returns a list of violation strings."""
    violations = []
    if not _require_keys(obj, FIGURES_REQUIRED_KEYS, "figures", violations):
        return violations
    figures = obj.get("figures")
    if not isinstance(figures, dict):
        violations.append("figures.figures is %s, expected an object"
                          % type(figures).__name__)
        return violations
    if not figures:
        violations.append(
            "figures.figures is EMPTY. A results file carrying zero figures is a "
            "did-not-run, and every count derived from it would be a 0/0 pass")
        return violations

    for key in sorted(figures):
        where = "figures.figures[%r]" % key
        entry = figures[key]
        if not _require_keys(entry, FIGURE_REQUIRED_KEYS, where, violations):
            continue

        # a design rule: population: 1 is LEGAL and rendered. Peak VRAM, free VRAM at run
        # start and disk free are legitimately single-sample population facts.
        # Zero or missing is not: it is the 0/0 pass wearing a figure's clothes.
        population = entry.get("population")
        if not isinstance(population, int) or isinstance(population, bool):
            violations.append("%s.population is %s, expected an int"
                              % (where, type(population).__name__))
        elif population < 1:
            violations.append(
                "%s.population is %d. A figure over zero inputs did not measure "
                "anything; population 1 is legal, 0 is not" % (where, population))

        _require_type(entry, "population_label", (str,), "a string", where, violations)
        if isinstance(entry.get("population_label"), str) and not entry["population_label"].strip():
            violations.append("%s.population_label is empty -- the integer counts "
                              "nothing a reader can name" % where)
        _require_type(entry, "derived_from", (list, tuple), "a list", where, violations)
        _require_type(entry, "threshold_claim", (bool,), "a bool", where, violations)

        bullet = entry.get("canon_bullet")
        if not isinstance(bullet, str) or not _COMPOUND_BULLET_RE.match(bullet):
            violations.append(
                "%s.canon_bullet is %r; it must be COMPOUND-KEYED as "
                "'<canon>:<bullet-id>'. 17 of 49 bullet ids exist in BOTH canons, "
                "so a bare id is ambiguous in 35%% of cases" % (where, bullet))

        criterion = entry.get("reproduce_criterion")
        if criterion is not None:
            _require_keys(criterion, ("kind", "tolerance"),
                          where + ".reproduce_criterion", violations)

        if entry.get("threshold_claim") is True:
            runs = entry.get("runs")
            count = len(runs) if isinstance(runs, (list, tuple)) else 0
            if count < THRESHOLD_CLAIM_MIN_RUNS:
                violations.append(
                    "%s carries threshold_claim: true with %d recorded run(s); "
                    "a design rule requires at least %d. A single run landing the right "
                    "side of a line does not establish that the line was crossed"
                    % (where, count, THRESHOLD_CLAIM_MIN_RUNS))

        similar = entry.get("similar")
        if isinstance(similar, str) and similar not in SIMILARITY_VERDICTS:
            violations.append("%s.similar is %r, expected one of %s"
                              % (where, similar, list(SIMILARITY_VERDICTS)))
    return violations


PROVENANCE_REQUIRED_KEYS = ("schema", "schema_version", "sources", "images",
                            "host", "run", "free_vram_mib")

PROVENANCE_RUN_KEYS = ("started_at", "finished_at", "started_at_utc",
                       "finished_at_utc", "api_spend_usd", "gpu_minutes",
                       "wall_seconds")


def validate_provenance(obj):
    """Validate a provenance.json record. Returns a list of violation strings."""
    violations = []
    if not _require_keys(obj, PROVENANCE_REQUIRED_KEYS, "provenance", violations):
        return violations
    _require_type(obj, "sources", (dict,), "an object", "provenance", violations)
    _require_type(obj, "images", (dict,), "an object", "provenance", violations)
    _require_type(obj, "host", (dict,), "an object", "provenance", violations)

    run = obj.get("run")
    if _require_keys(run, PROVENANCE_RUN_KEYS, "provenance.run", violations):
        for key in ("api_spend_usd", "gpu_minutes", "wall_seconds"):
            _require_type(run, key, (int, float), "a number", "provenance.run",
                          violations)

    # a project requirement + the standing blocker: free VRAM on this machine has been observed
    # at three values across two days. It is a POPULATION FACT recorded at the
    # moment of the run, not housekeeping, and nothing may compute against the
    # card's nameplate 6,141 MiB.
    vram = obj.get("free_vram_mib")
    if not isinstance(vram, (int, float)) or isinstance(vram, bool):
        violations.append(
            "provenance.free_vram_mib is %s, expected a number measured at run "
            "time" % type(vram).__name__)
    elif vram <= 0:
        violations.append("provenance.free_vram_mib is %r, which cannot have been "
                          "measured" % (vram,))

    sources = obj.get("sources")
    if isinstance(sources, dict) and not sources:
        violations.append(
            "provenance.sources is EMPTY -- a provenance record over zero source "
            "files is an unrun census, not a clean one")
    return violations


# ---------------------------------------------------------------------------
# The guard record shape (owner ruling C1, an earlier plan)
# ---------------------------------------------------------------------------
#
# THE MEASUREMENT THAT FORCED THE RULING, recorded so it is not re-litigated.
# Read first-hand from example-cache-benchmark/results/results.json:
#
#   guards in the array ................................. 7
#   keys invariant across all seven ..................... 2   (`id`, `passed`)
#   DISTINCT names used for the population integer ...... 5   (compared_keys,
#       hits/misses, redis_dbsize_after_run, driver_ceiling_rps,
#       distinct_tenants_in_sequence)
#   guards carrying a field named `minimum_required` .... 1 of 7  (G2-coverage)
#   guards carrying a DIFFERENTLY named floor ........... 1 more  (G3, required_factor)
#   guards carrying NO floor at all ..................... 5 of 7
#   occurrences of `population` as a field name ......... 0 across both artifacts
#
# So CHECK-11 cannot mechanically locate "the population field" when its name
# varies five ways, and a design rule's "print the EFFECTIVE floor" has nothing to print
# for five of seven guards as shipped. The second artifact uses a THIRD
# convention (`"n": 500`), which is the argument for fixing one name here rather
# than adopting either.
#
# C1 therefore requires the fixed triple `population` / `population_label` /
# `minimum_required` on EVERY guard, with the domain-specific key kept beside it
# for readability. It mirrors figures.json's {population, population_label} so
# the whole program runs on ONE population convention rather than three.
#
# THE CONSEQUENCE IS NEW WORK, NOT A RENAME, AND AN EARLIER ROUND OWNS IT: an earlier round must
# ADD `population` and `population_label` to all seven redis guards, and must
# INVENT a defensible `minimum_required` floor for the five that declare none.
# Renaming an existing key cannot produce a floor that was never recorded.

GUARD_REQUIRED_KEYS = ("id", "passed", "population", "population_label",
                       "minimum_required")


def validate_guards(obj):
    """Validate a guards record under ruling C1. Returns a list of violation strings.

    `obj` is the CONTAINING record: {"guards": [...], "all_guards_passed": bool}.
    A bare list is accepted and treated as a container missing its top-level
    field, so `validate_guards([...])` reports exactly that rather than silently
    passing a record whose summary flag was never written. There is no mode in
    which the top-level flag goes unchecked.

    len(guards) >= 1 is REQUIRED. redis/finalize.py:139 is
    `all(g["passed"] for g in guards)` with no length check -- safe there only
    because its seven appends are unconditional, and a copy whose guards were
    conditional would report every guard passing over zero guards.
    """
    violations = []
    if isinstance(obj, (list, tuple)):
        obj = {"guards": list(obj)}
    if not isinstance(obj, dict):
        return ["guards record is %s, expected an object or a list"
                % type(obj).__name__]

    if "all_guards_passed" not in obj:
        violations.append(
            "guards record is missing top-level 'all_guards_passed'")
    elif not isinstance(obj["all_guards_passed"], bool):
        violations.append("all_guards_passed is %s, expected a bool"
                          % type(obj["all_guards_passed"]).__name__)

    guards = obj.get("guards")
    if not isinstance(guards, (list, tuple)):
        violations.append("guards is %s, expected a list" % type(guards).__name__)
        return violations
    if len(guards) == 0:
        violations.append(
            "guards is EMPTY. Zero guards is a DID-NOT-RUN, never a pass: "
            "all() over an empty sequence is True, which is how a guard array "
            "that was never populated reports every guard passing")
        return violations

    seen = {}
    for index, guard in enumerate(guards):
        where = "guards[%d]" % index
        if not _require_keys(guard, GUARD_REQUIRED_KEYS, where, violations):
            continue
        if isinstance(guard.get("id"), str):
            where = "guards[%d] (%s)" % (index, guard["id"])
            seen.setdefault(guard["id"], []).append(index)
        _require_type(guard, "id", (str,), "a string", where, violations)
        _require_type(guard, "passed", (bool,), "a bool", where, violations)
        _require_type(guard, "population_label", (str,), "a string", where, violations)
        _require_type(guard, "minimum_required", (int, float), "a number", where,
                      violations)

        population = guard.get("population")
        if not isinstance(population, int) or isinstance(population, bool):
            violations.append("%s.population is %s, expected an int"
                              % (where, type(population).__name__))
        elif population < 0:
            violations.append("%s.population is %d" % (where, population))

        floor = guard.get("minimum_required")
        if (isinstance(population, int) and not isinstance(population, bool)
                and isinstance(floor, (int, float)) and not isinstance(floor, bool)):
            if guard.get("passed") is True and population < floor:
                violations.append(
                    "%s reports passed: true on population %d, below its own "
                    "declared floor of %s -- a guard that passes under its floor "
                    "measures nothing" % (where, population, floor))

    duplicates = sorted(gid for gid, idx in seen.items() if len(idx) > 1)
    for gid in duplicates:
        violations.append("guard id %r appears at indices %s; ids must be unique"
                          % (gid, seen[gid]))

    flag = obj.get("all_guards_passed")
    if isinstance(flag, bool):
        derived = all(bool(g.get("passed")) for g in guards if isinstance(g, dict))
        if flag != derived:
            violations.append(
                "all_guards_passed is %r but the %d guard record(s) derive %r"
                % (flag, len(guards), derived))
    return violations


# ---------------------------------------------------------------------------
# The shared numeral allow-list (a design rule and a design rule -- ONE implementation)
# ---------------------------------------------------------------------------
#
# CONTEXT.md pairs a design rule and a design rule explicitly, so they get one implementation
# rather than two that drift. BOTH rules run, and neither is sufficient alone:
#
#   SHAPE allow-list (primary) -- a numeral is permitted only if it is a bullet
#       id, an ISO date, a {{figures.*}} key reference, a version string or a
#       port. Everything else is unclassified and is a finding.
#   VALUE check (beside it) -- any figures.json VALUE appearing outside a key
#       reference is a leak, EVEN WHEN the shape allow-list would permit it.
#
# Deny-by-value alone misses a hand-typed number that happens not to match a
# figure, which is exactly an earlier finding's back-solving failure (deriving a numerator from
# a canon percentage and typing it into a sentence). Shape alone misses a real
# figure value typed into prose in a permitted shape -- a measured port, a
# measured version count. The overlap is the point.

_KEY_REFERENCE_RE = re.compile(r"\{\{\s*figures\.[A-Za-z0-9_.\[\]-]+\s*\}\}")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_.:+-]*[0-9][A-Za-z0-9_.:+-]*")
_ISO_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?$")
_BULLET_ID_RE = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9_-]*:)?[A-Z]{1,6}-?\d+(?:-[A-Za-z0-9]+)*$")
# A VERSION RULE LOOSE ENOUGH TO PERMIT A MEASUREMENT IS NOT A VERSION RULE.
# The first draft was `^v?\d+(?:\.\d+)+$`, which classifies `12.5` -- a latency
# in milliseconds, exactly the figure a design rule exists to keep out of un-rendered
# prose -- as a version string. A two-component numeral is therefore a version
# ONLY with a `v` prefix, or a specifier cue (`version`, `==`, `>=`, ...)
# immediately before it. Three or more components stands alone.
_VERSION_RE = re.compile(r"^v\d+(?:\.\d+)*(?:[.-][A-Za-z0-9]+)*$"
                         r"|^\d+(?:\.\d+){2,}(?:[.-][A-Za-z0-9]+)*$")
_TWO_PART_NUMERAL_RE = re.compile(r"^\d+\.\d+(?:[.-][A-Za-z0-9]+)*$")
_VERSION_CUE_RE = re.compile(r"(?i)(?:\bversions?\b\s*[:=]?\s*|[=<>~!]=\s*)$")
_HOST_PORT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*:\d{1,5}$")
_BARE_INT_RE = re.compile(r"^\d+$")
# A bare integer counts as a port ONLY when the word `port` immediately precedes
# it. An earlier draft also accepted "anything after a colon", which would have
# classified the 42 in "count: 42" as a port -- a rule loose enough to permit
# the thing it exists to catch.
_PORT_CUE_RE = re.compile(r"(?i)\bports?\b\s*[:=]?\s*$")

KIND_KEY_REFERENCE = "key_reference"
KIND_ISO_DATE = "iso_date"
KIND_BULLET_ID = "bullet_id"
KIND_VERSION = "version"
KIND_PORT = "port"
KIND_UNCLASSIFIED = "unclassified"

ALLOWED_KINDS = (KIND_KEY_REFERENCE, KIND_ISO_DATE, KIND_BULLET_ID,
                 KIND_VERSION, KIND_PORT)


@dataclass
class NumeralHit:
    """One numeral-bearing token and what the allow-list made of it."""

    token: str
    kind: str
    line: int
    col: int
    context: str = ""


@dataclass
class NumeralReport:
    """Counts plus LOCATED hits. A bare count would not be actionable."""

    classified: int = 0
    unclassified: int = 0
    value_leaks: int = 0
    hits: list = field(default_factory=list)
    leaks: list = field(default_factory=list)

    @property
    def counts(self):
        return {"classified": self.classified,
                "unclassified": self.unclassified,
                "value_leaks": self.value_leaks}

    @property
    def total(self):
        return self.classified + self.unclassified


def _line_col(text, offset):
    prefix = text[:offset]
    line = prefix.count("\n") + 1
    col = offset - (prefix.rfind("\n") + 1)
    return line, col


def _figure_value_strings(figure_values):
    """Render every figure value into the strings it could be typed as."""
    values = []
    if figure_values is None:
        return values
    if isinstance(figure_values, dict):
        iterable = list(figure_values.values())
    else:
        iterable = list(figure_values)
    for item in iterable:
        if isinstance(item, dict) and "value" in item:
            item = item["value"]
        if isinstance(item, bool) or item is None:
            continue
        if isinstance(item, int):
            values.append(str(item))
            if abs(item) >= 1000:
                values.append("{:,}".format(item))
        elif isinstance(item, float):
            values.append(repr(item))
            values.append("%g" % item)
        elif isinstance(item, str) and item.strip():
            values.append(item.strip())
    # Deduplicate while keeping the order stable, so a report's leak list does
    # not reorder between runs.
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def classify_numerals(text, figure_values=None):
    """Classify every numeral in `text` and report leaks of `figure_values`.

    Returns a NumeralReport. `[]` unclassified and 0 value_leaks means clean.

    `figure_values` accepts a list of values, a mapping of key -> value, or a
    mapping of key -> {"value": ...} (a figures.json `figures` block), so a
    caller does not have to reshape its own record to use this.
    """
    text = "" if text is None else str(text)
    report_obj = NumeralReport()

    # Mask key references with spaces so offsets survive, and count them as
    # classified. A masked span is invisible to both the token scan and the
    # value scan, which is what makes `{{figures.p95_ms}}` the ONE permitted
    # way to put a figure in prose.
    masked = list(text)
    for match in _KEY_REFERENCE_RE.finditer(text):
        line, col = _line_col(text, match.start())
        report_obj.hits.append(NumeralHit(match.group(0), KIND_KEY_REFERENCE,
                                          line, col))
        report_obj.classified += 1
        for index in range(match.start(), match.end()):
            masked[index] = " "
    masked = "".join(masked)

    for match in _TOKEN_RE.finditer(masked):
        raw = match.group(0)
        stripped = raw.strip(".:,;+-_")
        if not stripped or not any(char.isdigit() for char in stripped):
            continue
        start = match.start() + raw.index(stripped)
        line, col = _line_col(masked, start)
        before = masked[:start]

        if _ISO_DATE_RE.match(stripped):
            kind = KIND_ISO_DATE
        elif _VERSION_RE.match(stripped):
            kind = KIND_VERSION
        elif (_TWO_PART_NUMERAL_RE.match(stripped)
                and _VERSION_CUE_RE.search(before)):
            kind = KIND_VERSION
        elif _HOST_PORT_RE.match(stripped):
            kind = KIND_PORT
        elif _BARE_INT_RE.match(stripped) and _PORT_CUE_RE.search(before):
            kind = KIND_PORT
        elif _BULLET_ID_RE.match(stripped):
            kind = KIND_BULLET_ID
        else:
            kind = KIND_UNCLASSIFIED

        context = masked[max(0, start - 24):start + len(stripped) + 24].replace("\n", " ")
        report_obj.hits.append(NumeralHit(stripped, kind, line, col, context))
        if kind == KIND_UNCLASSIFIED:
            report_obj.unclassified += 1
        else:
            report_obj.classified += 1

    # THE BOUNDARY IS "NOT PART OF A LONGER NUMBER", NOT "NOT NEXT TO A DOT".
    # The first draft used a plain `(?![0-9A-Za-z.])` lookahead, which rejected
    # `0.081` at the END OF A SENTENCE because the following character was the
    # full stop. A figure typed into prose is overwhelmingly likely to sit at a
    # sentence end, so the leak detector missed precisely the engagement it
    # exists to catch. The lookahead now rejects only a continuing digit, or a
    # dot that is itself followed by one.
    for value in _figure_value_strings(figure_values):
        pattern = re.compile(r"(?<![0-9A-Za-z_.])" + re.escape(value)
                             + r"(?![0-9A-Za-z_])(?!\.[0-9])")
        for match in pattern.finditer(masked):
            line, col = _line_col(masked, match.start())
            context = masked[max(0, match.start() - 24):match.end() + 24].replace("\n", " ")
            report_obj.leaks.append(NumeralHit(value, "value_leak", line, col, context))
            report_obj.value_leaks += 1

    return report_obj
