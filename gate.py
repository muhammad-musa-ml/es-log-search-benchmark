"""The opening gate: read the conditions this measurement depends on, then mint its token.

THE GATE RECORDS FACTS READ FROM THE WORLD; it does not assert them. Every value
under `realized` was read at gate time, and the run token is a digest of what was
read.

WHAT THE TOKEN IS MINTED FROM, AND WHY THOSE THINGS
-----------------------------------------------------
The inputs are the things that would INVALIDATE a latency comparison if they
changed between the gate and the run. A token minted from an empty or incidental
input set certifies nothing, so they are listed by name in GATE_INPUTS below
rather than globbed. For this benchmark they are four kinds:

  THE CORPUS       docgen.py generates it from a seed; load.py passes that seed
                   and force-merges both indices. Change either and the two
                   indices no longer hold the corpus the numbers were read over.
  THE DESIGNS      mappings.py IS the variable under test. It is the one file
                   whose change is supposed to move the result, which is exactly
                   why a results file must say which version produced it.
  THE WORKLOAD     queries.py holds the seeded sample and both formulations;
                   bench.py holds the warmup, the replay and the percentile
                   rule. A percentile computed by a different rule is a
                   different number wearing the same name.
  THE SOFTWARE     docker-compose.yml pins the Elasticsearch node by INDEX
                   DIGEST; requirements.txt pins the client by version AND by
                   hash. The July run recorded only the SERVER version, so the
                   client that produced its numbers is unrecoverable -- this
                   gate exists partly so that cannot happen twice.

A file named here but ABSENT is recorded as absent rather than dropped from the
digest. A missing input that simply vanished from the hash would be
indistinguishable from one that was never declared.

WHAT IS DELIBERATELY NOT IN THE INPUT SET: gate.py and runmeta.py. Neither
contributes to a measured value -- they record. Folding gate.py into its own
digest would also make every edit to a comment in this file invalidate every
measurement taken under it, which is a false invalidation rather than a
detection. `run_benchmark.py` IS in the set, because it chooses the document
count and the query count the run measures over.

TWO DIFFERENT FAILURES, AND THEY MUST NOT BE COLLAPSED
--------------------------------------------------------
    REFUSAL (exit 2)     A precondition makes measuring impossible or
                         meaningless. The gate COULD NOT LOOK. No record is
                         written, because a record would imply it did.
    FAILED GATE (exit 3) The gate looked, and a declared assertion did not hold.
                         A FULL record IS written, `passed: false`, the failing
                         ids named - AND THE TOKEN IS STILL MINTED.

WHY A FAILED GATE STILL MINTS ITS TOKEN.
Minting no token would leave a failed gate with no key at all, and a measurement
that ran anyway would then be undetectable - there would be nothing to compare.
Minting one means such a measurement carries a token that ties it to a gate
whose own record says it did not pass. The failure becomes evidence instead of a
silence.

WHY THE DATE IS NOT PART OF THE DIGEST.
The token is a function of gate CONTENT ONLY, and `dated_at` is stamped BESIDE
it. The two failures a run token exists to catch are (i) results produced under
a gate that has since CHANGED, caught exactly by a content digest, and (ii)
results copied from an EARLIER SESSION, caught by the separately stamped
`dated_at`, which names the gate INSTANCE. Folding the date into the digest buys
no discrimination over that pair and forces a full re-measure after any gate
re-run.

ORDERING IS BY THE RECORDED TIMESTAMPS INSIDE THE JSON, never by file mtime.
mtime is weak across the Windows/WSL2 boundary, it is preserved by ordinary
copies, and it is trivially touched - so a results file copied forward from an
earlier session keeps an entirely plausible mtime while its recorded stamps
cannot be laundered the same way.

WHAT IS RECORDED BUT DELIBERATELY NOT MINTED.
Whether the Docker engine is reachable is written into `environment_probe`,
outside `realized`, and therefore outside the token. The engine being down at
gate time and up at run time is the NORMAL path, not a corruption, so folding it
into the digest would report a false invalidation every time. What the engine
was actually running is recorded per run, by the run recorder, at the instant it
mattered.
"""

# ORDERING RULE, and why it is a comment rather than prose in the docstring: a
# scan over this file that judges by token type sees a docstring as a string
# expression, not a comment. Stating the rule here puts it where such a scan can
# tell an explanation apart from a use.
#
# Records are ordered by the recorded timestamps INSIDE the JSON, never by file
# mtime, for the reasons given above.

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

import canonkit

SCHEMA = "eslogbench/gate/1"

# The Windows path ceiling this repository works under. Printed on EVERY branch:
# a limit that is only mentioned when it is breached leaves the passing run
# unable to say what it measured.
MAX_PATH_CHARS = 240

# Assertions whose failure is a REFUSAL (exit 2) rather than a failed gate.
# These say the gate could not look at all.
REFUSAL_ASSERTION_IDS = (
    "ENV-PATH-LENGTH",
    "ENV-PATH-CASE",
)

ONEDRIVE_MARKERS = ("onedrive",)

# THE DECLARED INPUT SET. See the module docstring for why each one is here, and
# for the two files deliberately left out.
GATE_INPUTS = (
    # the corpus: the generator, and the loader that passes it a seed
    "esbench/docgen.py",
    "esbench/load.py",
    # the variable under test
    "esbench/mappings.py",
    # the workload: the seeded sample, both formulations, and the measurement
    "esbench/queries.py",
    "esbench/bench.py",
    "esbench/__init__.py",
    # the guard array a run asserts over its own records
    "esbench/guards.py",
    # the driver, which chooses the document count and the query count
    "run_benchmark.py",
    # the node, pinned by index digest
    "docker-compose.yml",
    # the client, pinned by version and by hash
    "requirements.txt",
    "requirements.in",
)

GATE_INPUT_COUNT = 11

if len(GATE_INPUTS) != GATE_INPUT_COUNT:
    raise RuntimeError(
        "GATE_INPUTS lists %d file(s) but the committed literal says %d. Update "
        "BOTH in the same commit, or the derived count silently stops checking "
        "and the input set can shrink without anyone seeing it."
        % (len(GATE_INPUTS), GATE_INPUT_COUNT))

# Where the node this benchmark runs is named, and how a pinned one looks. There
# is no Dockerfile here: the client runs on the host and only the node is
# containerised, so the compose file is the only place an image enters.
COMPOSE_FILE = "docker-compose.yml"
DIGEST_MARKER = "@sha256:"
_IMAGE_RE = re.compile(r"^\s*image:\s*(\S+)\s*$")

# The pinned client set. A requirement line is `name==version`; the hash lines
# that follow it are what make the install reproducible rather than merely
# repeatable.
REQUIREMENTS_FILE = "requirements.txt"
_PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)")
_HASH_RE = re.compile(r"--hash=sha256:([0-9a-f]{64})")

# The corpus seed is declared in TWO files and they must agree: docgen's own
# default and the value load.py passes. Two different seeds would mean the two
# indices no longer hold the corpus the numbers were read over.
SEED_SOURCES = ("esbench/docgen.py", "esbench/load.py")
_SEED_RE = re.compile(r"seed[^=\n]*=\s*(\d+)")

# How many logical lookups the reproducibility probe builds. Deliberately the
# run's own default rather than a round number, so the probe exercises the
# sample the measurement actually replays.
QUERY_PROBE_N = 500

DOCKER_INFO_ARGV = ("docker", "info", "--format", "{{.ServerVersion}}")
DOCKER_INFO_TIMEOUT_SECONDS = 30


class AssertionResult(object):
    """One declared assertion, its verdict, and the value READ FROM THE WORLD."""

    def __init__(self, id, passed, realized, detail=""):
        self.id = id
        self.passed = passed
        self.realized = realized
        self.detail = detail

    def as_string(self):
        """The stable rendering that enters the token.

        json.dumps with sort_keys so a nested value renders identically in every
        process. repr() would not be safe: float formatting and set iteration
        order can both vary, and a token that is not reproducible is not a token.
        """
        return "%s=%s" % (self.id, json.dumps(self.passed, sort_keys=True))


# ---------------------------------------------------------------------------
# Reading the world
# ---------------------------------------------------------------------------

# Directories excluded from the path enumeration, and the exclusion is
# load-bearing rather than tidiness:
#
#   __pycache__ EXISTS ONLY AFTER A RUN. The longest path is a `realized` value,
#   so it enters the digest; with the cache directory included, a cold run and a
#   warm one mint DIFFERENT tokens for a gate whose content has not changed by a
#   byte.
#
#   results/ IS WRITTEN BY THE RUNS THIS GATE AUTHORISES. Enumerating it would
#   make the gate's own token depend on the output of measurements taken under
#   it, so re-running the gate after a measurement would invalidate that
#   measurement. The gate describes the environment it authorises, never the
#   results of what it authorised.
EXCLUDED_DIRS = ("__pycache__", ".git", ".venv", "venv", ".pytest_cache",
                 ".mypy_cache", ".ruff_cache", "node_modules", "results")


def enumerate_paths(root):
    """Every path under `root`, as ABSOLUTE forward-slash strings.

    ABSOLUTE, because the ceiling this feeds is a limit on absolute paths. A
    relative measurement under-reports by the whole length of the leading
    directories - it would report a comfortable 40 characters for a tree whose
    real paths sit near the limit, which is to say it could not detect the
    condition it exists to detect.
    """
    found = []
    for base, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for name in filenames:
            full = os.path.abspath(os.path.join(base, name))
            found.append(str(full).replace(chr(92), "/"))
    return sorted(found)


def assert_path_length(paths, limit=MAX_PATH_CHARS):
    longest = max((len(p) for p in paths), default=0)
    return AssertionResult(
        "ENV-PATH-LENGTH", longest < limit, longest,
        "longest path is %d character(s), limit %d" % (longest, limit))


def assert_no_case_collision(paths):
    seen = {}
    for path in paths:
        seen.setdefault(path.lower(), []).append(path)
    collisions = sorted(v for v in seen.values() if len(v) > 1)
    return AssertionResult(
        "ENV-PATH-CASE", not collisions, len(collisions),
        "case-only collision(s): %s" % (collisions or "none"))


def assert_not_synced(root):
    """Refuse a sync-managed directory. Matched against the ABSOLUTE root.

    Matching the root AS PASSED would be a check that can never fire: the
    documented way to run this file is `python gate.py` from the repository
    root, which makes `root` the string ".", and no sync marker can appear in
    ".". The realized value is the matched marker rather than a bare bool, so
    the record says WHICH marker fired instead of only that something did.

    It matters here because this repository measures latency percentiles, and a
    sync client that decides to walk the tree mid-run adds I/O the measurement
    would silently attribute to Elasticsearch.
    """
    lowered = os.path.abspath(str(root)).replace(chr(92), "/").lower()
    hit = [marker for marker in ONEDRIVE_MARKERS if marker in lowered]
    return AssertionResult(
        "ENV-NOT-SYNCED", not hit, hit,
        "repository root matched %s" % (hit or "no sync marker"))


def read_image_references(root):
    """Every image this benchmark runs, with the file that names it.

    Returns a list of (source, reference) pairs. The compose file's `image:`
    lines are the only place an image enters this repository: the benchmark
    client runs on the host, so there is no Dockerfile to read.
    """
    references = []
    compose = os.path.join(str(root), COMPOSE_FILE)
    if os.path.isfile(compose):
        with open(compose, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.lstrip().startswith("#"):
                    continue
                match = _IMAGE_RE.match(line)
                if match:
                    references.append((COMPOSE_FILE, match.group(1)))
    return references


def assert_images_digest_pinned(root):
    """Every image the benchmark runs is pinned by digest, not by a tag.

    A tag is a moving reference, so "the same benchmark" would otherwise
    silently mean different software on a different day. For a benchmark whose
    subject IS how a search engine behaves, the engine's build is the
    measurement's single largest input.

    A population of ZERO is a FAILURE, not a pass. Finding no image reference at
    all means the file that names them was not read, and `all()` over an empty
    sequence is True - which is exactly how a check that examined nothing
    reports that everything is fine.
    """
    references = read_image_references(root)
    unpinned = sorted("%s: %s" % (src, ref) for src, ref in references
                      if DIGEST_MARKER not in ref)
    passed = bool(references) and not unpinned
    return AssertionResult(
        "IMAGES-DIGEST-PINNED", passed,
        sorted("%s: %s" % (src, ref) for src, ref in references),
        "%d image reference(s) read, %d not digest-pinned%s"
        % (len(references), len(unpinned),
           (": " + ", ".join(unpinned)) if unpinned else ""))


def read_client_pins(root):
    """Every pinned requirement, with the hashes declared for it.

    Returns {name: {"version": str, "hashes": [str, ...]}}. Hash lines belong to
    the pin they follow, which is how pip reads the file, so the parser carries
    the current pin forward rather than treating hashes as free-floating.
    """
    pins = {}
    path = os.path.join(str(root), REQUIREMENTS_FILE)
    if not os.path.isfile(path):
        return pins
    current = None
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            match = _PIN_RE.match(stripped)
            if match:
                current = match.group(1).lower()
                pins[current] = {"version": match.group(2), "hashes": []}
            for digest in _HASH_RE.findall(stripped):
                if current is not None:
                    pins[current]["hashes"].append(digest)
    return pins


def assert_client_hash_pinned(root):
    """The Elasticsearch client is pinned by version AND by hash.

    THIS ASSERTION HAS A MEASURED REASON. The July run recorded `es_version`,
    which is the SERVER's version; the client library that produced its wall
    clock numbers is recorded nowhere and is unrecoverable. Wall time includes
    the client's own transport, so a different client is a different number.
    Pinning by hash rather than only by version closes the second half: a
    version is a name a registry can re-point, a hash is the bytes.

    A population of ZERO is a FAILURE for the same reason as the image check.
    """
    pins = read_client_pins(root)
    unhashed = sorted(name for name, pin in pins.items() if not pin["hashes"])
    passed = bool(pins) and not unhashed
    return AssertionResult(
        "CLIENT-HASH-PINNED", passed,
        dict((name, {"version": pin["version"], "hashes": len(pin["hashes"])})
             for name, pin in pins.items()),
        "%d pinned requirement(s) read, %d without a hash%s"
        % (len(pins), len(unhashed),
           (": " + ", ".join(unhashed)) if unhashed else ""))


def read_declared_seeds(root):
    """The corpus seed as each source declares it, keyed by file.

    Read from the SOURCE rather than by importing, so this assertion holds even
    before `pip install -r requirements.txt` has run. A file declaring more than
    one distinct seed is recorded as the sorted list it declares, so the
    disagreement is visible rather than collapsed to whichever one was read
    last.
    """
    seeds = {}
    for relative in SEED_SOURCES:
        path = os.path.join(str(root), relative)
        if not os.path.isfile(path):
            seeds[relative] = None
            continue
        with open(path, "r", encoding="utf-8") as handle:
            found = sorted(set(int(v) for v in _SEED_RE.findall(handle.read())))
        seeds[relative] = found
    return seeds


def assert_corpus_seed_agrees(root):
    """Both files that name the corpus seed name the SAME one.

    The generator carries a default and the loader passes a value. Two different
    seeds would mean the two indices no longer hold the corpus the numbers were
    read over, and nothing in the output would say so: the load would succeed,
    the doc counts would match, and the equivalence guard would compare two
    different corpora.
    """
    seeds = read_declared_seeds(root)
    missing = sorted(name for name, found in seeds.items() if not found)
    distinct = sorted(set(value for found in seeds.values()
                          for value in (found or [])))
    passed = not missing and len(distinct) == 1
    if missing:
        detail = "no seed declared in %s" % ", ".join(missing)
    elif len(distinct) != 1:
        detail = "%d DIFFERENT seeds declared: %s" % (len(distinct), distinct)
    else:
        detail = ("%d source(s) agree on seed %d"
                  % (len(seeds), distinct[0]))
    return AssertionResult("CORPUS-SEED-AGREES", passed,
                           {"by_source": seeds, "distinct": distinct}, detail)


def _import_esbench(root, module):
    """Import an esbench submodule from `root`, restoring sys.path afterwards.

    Only stdlib-importing modules may be passed here: `mappings` and `queries`
    reach no further than `random` and `datetime`, so this works on a host where
    the Elasticsearch client is not installed yet. `bench` and `load` do import
    it and must never be imported from the gate.
    """
    root = os.path.abspath(str(root))
    inserted = False
    if root not in sys.path:
        sys.path.insert(0, root)
        inserted = True
    try:
        return __import__("esbench.%s" % module, fromlist=[module])
    finally:
        if inserted and root in sys.path:
            sys.path.remove(root)


def read_index_designs(root):
    """The two index designs, read from the module that declares them."""
    facts = {"before_index": None, "after_index": None, "designs_read": 0,
             "settings_shared": None, "mappings_differ": None,
             "after_properties": None, "error": None}
    try:
        mappings = _import_esbench(root, "mappings")
        facts["before_index"] = mappings.BEFORE_INDEX
        facts["after_index"] = mappings.AFTER_INDEX
        before = mappings.BEFORE_MAPPING
        after = mappings.AFTER_MAPPING
        facts["designs_read"] = 2
        facts["settings_shared"] = before.get("settings") == after.get("settings")
        facts["mappings_differ"] = before.get("mappings") != after.get("mappings")
        facts["after_properties"] = len(
            (after.get("mappings") or {}).get("properties") or {})
    except Exception as exc:                                    # noqa: BLE001
        facts["error"] = "%s: %s" % (exc.__class__.__name__, exc)
    return facts


def assert_index_designs_comparable(root):
    """The two designs differ in mapping and agree in everything else.

    Both halves matter and they fail in opposite directions. If the SETTINGS
    diverge, shard or replica or refresh differences confound the latency
    comparison and the number stops being about the mapping. If the MAPPINGS do
    NOT differ, the benchmark is comparing a design against itself, every
    percentile is noise, and the speedup would be reported anyway.

    A population of ZERO designs is a FAILURE: reading no design at all and
    reporting the pair comparable is the empty-`all()` failure again.
    """
    facts = read_index_designs(root)
    passed = (facts["error"] is None
              and facts["designs_read"] == 2
              and facts["before_index"] != facts["after_index"]
              and facts["settings_shared"] is True
              and facts["mappings_differ"] is True)
    if facts["error"]:
        detail = "could not read the index designs: %s" % facts["error"]
    else:
        detail = ("%d design(s) read: %s vs %s; settings shared=%s "
                  "mappings differ=%s; the explicit design maps %s field(s)"
                  % (facts["designs_read"], facts["before_index"],
                     facts["after_index"], facts["settings_shared"],
                     facts["mappings_differ"], facts["after_properties"]))
    return AssertionResult("INDEX-DESIGNS-COMPARABLE", passed, facts, detail)


def read_query_sample_facts(root, n=QUERY_PROBE_N):
    """Re-BUILD the sample twice and report what came out.

    Re-derived rather than trusted. The description beside the sample says it is
    seeded; this builds it and checks, so a sample that stopped being
    reproducible is visible at gate time rather than after a run has been spent.
    """
    facts = {"requested": int(n), "built": None, "reproducible": None,
             "distinct_widths": None, "distinct_queries": None, "error": None}
    try:
        queries = _import_esbench(root, "queries")
        first = queries.build_sample(int(n))
        second = queries.build_sample(int(n))
        facts["built"] = len(first)
        facts["reproducible"] = first == second
        facts["distinct_widths"] = len(set(len(q) for q in first))
        facts["distinct_queries"] = len(set(
            tuple(sorted(q.items())) for q in first))
    except Exception as exc:                                    # noqa: BLE001
        facts["error"] = "%s: %s" % (exc.__class__.__name__, exc)
    return facts


def assert_query_sample_reproducible(root):
    """The same seeded sample comes out of two independent builds.

    Both arms replay this sample in the same order, and every percentile this
    benchmark publishes is a function of it. A sample that changed between the
    two arms would compare two workloads and report the difference as a mapping
    effect.

    A population of ZERO built queries is a FAILURE.
    """
    facts = read_query_sample_facts(root)
    passed = (facts["error"] is None
              and facts["built"] == facts["requested"]
              and facts["built"] > 0
              and facts["reproducible"] is True)
    if facts["error"]:
        detail = "could not build the query sample: %s" % facts["error"]
    else:
        detail = ("built %s of %s requested lookup(s), reproducible=%s, over "
                  "%s distinct shape(s) and %s distinct lookup(s)"
                  % (facts["built"], facts["requested"], facts["reproducible"],
                     facts["distinct_widths"], facts["distinct_queries"]))
    return AssertionResult("QUERY-SAMPLE-REPRODUCIBLE", passed, facts, detail)


def probe_docker(runner=None):
    """Is the engine reachable, and what is it? RECORDED, never minted.

    Outside `realized` on purpose - see the module docstring. A down engine at
    gate time is the normal path: the gate authorises a measurement that has not
    started yet, and the node is brought up between the two.
    """
    runner = runner or _default_docker_info
    try:
        version = str(runner(list(DOCKER_INFO_ARGV))).strip()
    except Exception as exc:                                    # noqa: BLE001
        return {"reachable": False, "server_version": None,
                "error": "%s: %s" % (exc.__class__.__name__, exc)}
    return {"reachable": True, "server_version": version, "error": None}


def _default_docker_info(argv):
    completed = subprocess.run(argv, capture_output=True, text=True,
                               timeout=DOCKER_INFO_TIMEOUT_SECONDS, shell=False)
    if completed.returncode != 0:
        raise OSError("docker info exited %d: %s"
                      % (completed.returncode,
                         (completed.stderr or "").strip()[-300:]))
    return completed.stdout


def compute_inputs_hash(root, inputs):
    """Digest the DECLARED input set, recording absences rather than skipping them.

    A file simply missing from the digest is indistinguishable from one that was
    never declared. Recording `<absent>` keeps the two apart, so a disappearing
    input MOVES the token instead of quietly shrinking its domain.
    """
    lines = []
    for relative in sorted(inputs or []):
        full = os.path.join(str(root), relative)
        if os.path.isfile(full):
            lines.append("%s=%s" % (relative, canonkit.sha256_file(full)))
        else:
            lines.append("%s=<absent>" % relative)
    return canonkit.sha256_bytes("\n".join(lines).encode("ascii", "backslashreplace"))


def missing_inputs(root, inputs):
    """The declared inputs that are not on disk. Reported, never silently dropped."""
    return sorted(rel for rel in (inputs or [])
                  if not os.path.isfile(os.path.join(str(root), rel)))


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def evaluate_assertions(root, paths=None):
    """Evaluate every declared assertion and return the results in a fixed order."""
    if paths is None:
        paths = enumerate_paths(root)
    return [
        assert_path_length(paths),
        assert_no_case_collision(paths),
        assert_not_synced(root),
        assert_images_digest_pinned(root),
        assert_client_hash_pinned(root),
        assert_corpus_seed_agrees(root),
        assert_index_designs_comparable(root),
        assert_query_sample_reproducible(root),
    ]


def _repair_for(result):
    if result.id == "ENV-PATH-LENGTH":
        return ("move this repository nearer the drive root so its longest path "
                "is under %d characters, then re-run `python gate.py`."
                % MAX_PATH_CHARS)
    if result.id == "ENV-PATH-CASE":
        return ("rename one of the colliding paths so no two differ only by "
                "case, then re-run `python gate.py`.")
    return "fix the condition named above, then re-run `python gate.py`."


def build_gate_record(slug, results, inputs_hash, dated_at, dated_at_utc,
                      declared_inputs, absent_inputs, environment_probe):
    """Assemble the record. THE TOKEN IS MINTED FROM CONTENT ONLY."""
    assertions = [r.as_string() for r in results]
    realized = {}
    for result in results:
        realized[result.id] = result.realized
    failed_ids = [r.id for r in results if not r.passed]

    # CONTENT ONLY. `dated_at` is a parameter of this function and is
    # deliberately NOT passed to the mint - it is stamped into the record below,
    # BESIDE the token, for the reason given in the module docstring.
    token = canonkit.mint_run_token(slug, assertions, realized, inputs_hash)

    return {
        "schema": SCHEMA,
        "schema_version": canonkit.SCHEMA_VERSION,
        "artifact": slug,
        "passed": not failed_ids,
        "run_token": token,
        "dated_at": dated_at,
        "dated_at_utc": dated_at_utc,
        "assertions": assertions,
        "realized": realized,
        "inputs_hash": inputs_hash,
        "failed_ids": failed_ids,
        # This repository's gate quotes no fallback wording: its failure mode is
        # "do not measure", and `failed_ids` above is what says why. The two
        # fields are kept because the record's shape is shared, and an empty
        # string is a recorded emptiness rather than an absent key.
        "fallback_wording": "",
        "fallback_source": None,
        "env": {
            "platform": sys.platform,
            "python": sys.version.split()[0],
        },
        "declared_inputs": sorted(declared_inputs),
        "declared_input_count": len(declared_inputs),
        "absent_inputs": absent_inputs,
        "environment_probe": environment_probe,
    }


def run_gate(root, slug, paths=None, inputs=GATE_INPUTS, clock_local=None,
             clock_utc=None, docker_runner=None, stream=None):
    """Run the gate. Returns 0 (pass) or 3 (failed gate); refusals exit 2."""
    clock_local = clock_local or canonkit.now_local
    clock_utc = clock_utc or canonkit.now_utc
    stream = stream if stream is not None else sys.stdout

    results = evaluate_assertions(root, paths=paths)
    by_id = dict((r.id, r) for r in results)

    # PRINTED ON EVERY BRANCH, before any decision. A measurement the passing run
    # never reports is indistinguishable from one it never took.
    absent = missing_inputs(root, inputs)
    stream.write("[gate] slug = %s\n" % slug)
    stream.write("[gate] longest path = %d characters (limit %d)\n"
                 % (by_id["ENV-PATH-LENGTH"].realized, MAX_PATH_CHARS))
    stream.write("[gate] declared inputs = %d, absent = %d%s\n"
                 % (len(inputs), len(absent),
                    (" (" + ", ".join(absent) + ")") if absent else ""))
    for result in results:
        stream.write("[gate]   %-28s %-4s %s\n"
                     % (result.id, "pass" if result.passed else "FAIL",
                        result.detail))

    # REFUSE FIRST. Before any record, before the token, before measuring.
    for result in results:
        if result.id in REFUSAL_ASSERTION_IDS and not result.passed:
            canonkit.die(
                canonkit.EXIT_DID_NOT_RUN,
                "%s the gate cannot measure here -- %s failed: %s\n"
                "  REPAIR: %s"
                % (canonkit.REFUSAL_PREFIX, result.id, result.detail,
                   _repair_for(result)))

    dated_at = clock_local()
    dated_at_utc = clock_utc()
    failed = [r for r in results if not r.passed]

    record = build_gate_record(
        slug, results, compute_inputs_hash(root, inputs), dated_at,
        dated_at_utc, inputs, absent, probe_docker(docker_runner))

    violations = canonkit.validate_gate(record)
    if violations:
        canonkit.die(canonkit.EXIT_DID_NOT_RUN,
                     "%s the gate assembled a record its own validator rejects "
                     "(%d violation(s)):\n%s\n  REPAIR: this is a defect in "
                     "gate.py, not in the environment."
                     % (canonkit.REFUSAL_PREFIX, len(violations),
                        "\n".join(violations)))

    # THE RECORD IS WRITTEN ON BOTH BRANCHES, before the verdict is known. A
    # failed gate is a complete record that happens to say `passed: false`, not
    # an absence. A measurement that ran anyway then carries a token tying it to
    # a gate whose record says it did not pass, instead of no key at all.
    results_dir = os.path.join(str(root), "results")
    canonkit.atomic_write_json(os.path.join(results_dir, "gate.json"), record)

    if failed:
        canonkit.report("GATE", False, len(failed), len(results), 1,
                        note="FAILED: %s -- token %s minted anyway"
                             % (", ".join(r.id for r in failed),
                                record["run_token"][:12]))
        return canonkit.EXIT_GUARD_FAIL

    canonkit.report("GATE", True, 0, len(results), 1,
                    note="token %s dated %s"
                         % (record["run_token"][:12], dated_at))
    return canonkit.EXIT_PASS


def default_slug(root):
    """This repository's own directory name.

    A DEFAULT rather than a required argument, deliberately: the command a
    reader is told to run must be runnable exactly as written, and a gate whose
    documented invocation exits for want of an argument is a dead instruction.
    The resolved value prints on every branch and is recorded in the gate, so
    nothing about which name was minted under is left implicit.
    """
    return os.path.basename(os.path.abspath(str(root))) or "artifact"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read the conditions this measurement depends on, record "
                    "them, and mint the run token run_benchmark.py requires.")
    parser.add_argument("--root", default=".",
                        help="repository root to gate (default: the current "
                             "directory)")
    parser.add_argument("--slug", default=None,
                        help="the name this gate is minted under (default: the "
                             "root's directory name)")
    args = parser.parse_args(argv)
    slug = args.slug or default_slug(args.root)
    return run_gate(args.root, slug)


if __name__ == "__main__":
    sys.exit(main())
