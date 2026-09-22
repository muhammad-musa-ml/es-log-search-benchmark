"""Driver: load both indices, replay the query sample, write ONE replicate's records.

    python gate.py
    python run_benchmark.py [doc_count] [n_queries] [--replicate N]

Defaults to 2,500,000 documents, 500 queries and replicate 1.

WHY THE GATE COMES FIRST, AND WHY THIS REFUSES WITHOUT IT
-----------------------------------------------------------
`canonkit.require_gate` is called before anything is connected to, read or
measured, and it exits 2 when `results/gate.json` is absent or records a failed
gate. That ordering is the point: a gate minted AFTER a measurement proves
nothing about what preceded what, so the token this run stamps into every record
it writes has to already exist when the run starts. The gate's `dated_at` is
therefore strictly earlier than this run's `started_at`, and that ordering is
asserted rather than assumed.

WHY EACH REPLICATE WRITES ITS OWN FILES AND NOTHING OVERWRITES results.json
-----------------------------------------------------------------------------
This driver used to write one file, `results/results.json`, and the numbers it
published rested on the single run that wrote it last. Two things change here.

The first is REPLICATION. A speedup derived from one run of each arm cannot
distinguish the effect from the run, so each replicate writes its own records
and the replicates are reported individually. No statistic is computed across
them here or anywhere downstream: if three runs of an arm disagree, the
disagreement is the finding, and averaging it away would delete exactly the
information the replication was taken to obtain.

The second is that `results/results.json` IS NOT TOUCHED. It holds the July run
- the record of what was claimed before this programme measured anything - and
that is the BEFORE side a measurement-wins programme needs. It is excluded from
the derivation, COUNTED as excluded with its reason, and never deleted or
overwritten. A superseded machine record that has been overwritten cannot be
compared against; it can only be described.

WHAT EACH REPLICATE WRITES
----------------------------
    results/raw/replicate-N.json        the run record: machine timestamps in
                                        both forms, the gate token, the cost
                                        triple, and a container census at the
                                        start AND at the finish.
    results/replicate-N-before.json     one arm's distributions and hit volume.
    results/replicate-N-after.json      the other arm's.
    results/replicate-N-pair.json       what only the PAIR can say: the
                                        equivalence check, the two deltas, and
                                        the guard array.

The arms are split into their own files because they are separately countable
populations, and the pair is a third file because the equivalence check and the
deltas are properties of the COMPARISON rather than of either arm. Putting them
in an arm's file would make a reader counting arm records count the comparison
twice.

Both arms still run inside ONE process against ONE loaded corpus, and that is
deliberate: the corpora are generated from the same seed, force-merged to the
same segment count, and replayed with the same seeded sample in the same order.
Splitting the arms across separate runs would give up that pairing, which is the
thing that makes the comparison a comparison.

THE CLIENT VERSION IS RECORDED, WHICH IT WAS NOT BEFORE
---------------------------------------------------------
The July record wrote `es_version`, which is the SERVER's. Wall-clock latency
includes the Python client's own transport, so the client library is an input to
half the numbers this benchmark publishes - and the one that produced July's is
unrecoverable. Every record written here names both.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import platform
import sys
import time

import canonkit
import runmeta

from esbench import load, bench
from esbench.guards import build_guards

ROOT = pathlib.Path(__file__).parent
RESULTS = ROOT / "results"

SCHEMA_ARM = "eslogbench/arm/1"
SCHEMA_PAIR = "eslogbench/pair/1"

DEFAULT_DOC_COUNT = 2_500_000
DEFAULT_N_QUERIES = 500
DEFAULT_REPLICATE = 1


def client_version():
    """The Elasticsearch PYTHON CLIENT's version, read from the installed package.

    Read rather than declared: requirements.txt says what should be installed,
    and this says what actually was. A record that quoted the pin would restate
    an intention while claiming to report a fact.
    """
    try:
        import importlib.metadata as metadata
        return metadata.version("elasticsearch")
    except Exception:                                           # noqa: BLE001
        try:
            import elasticsearch
            return ".".join(str(part) for part in elasticsearch.VERSION)
        except Exception:                                       # noqa: BLE001
            return None


def environment_block():
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "elasticsearch_client": client_version(),
    }


def replicate_paths(results_dir, replicate):
    """The three measurement files one replicate writes, by name."""
    stem = "replicate-%d" % int(replicate)
    return {
        "run_id": stem,
        "before": os.path.join(str(results_dir), "%s-before.json" % stem),
        "after": os.path.join(str(results_dir), "%s-after.json" % stem),
        "pair": os.path.join(str(results_dir), "%s-pair.json" % stem),
    }


def refuse_existing(paths, overwrite):
    """A replicate that would silently overwrite another is a LOST measurement.

    Three runs that all wrote `replicate-1` would leave one file and a record
    claiming three replicates, and nothing in the output would say which two
    were destroyed. So the collision is refused by default and the override has
    to be typed.
    """
    if overwrite:
        return
    existing = sorted(os.path.basename(p) for key, p in paths.items()
                      if key != "run_id" and os.path.isfile(p))
    if existing:
        canonkit.die(
            canonkit.EXIT_DID_NOT_RUN,
            "%s replicate %s already has %d record(s) on disk (%s). Writing "
            "over them would destroy a measurement and leave a count that still "
            "says three.\n"
            "  REPAIR: pass a --replicate index that is not taken, or pass "
            "--overwrite if you mean to discard those records."
            % (canonkit.REFUSAL_PREFIX, paths["run_id"], len(existing),
               ", ".join(existing)))


def arm_record(slug, token, replicate, arm, summary, hits, equivalence,
               corpus, n_queries, environment, run_block):
    """ONE arm's record.

    `started_at`, `started_at_utc` and `gate_token` sit at the TOP LEVEL as well
    as inside the run block. That is not duplication for its own sake: the
    ordering and date checks read the top level, while the run-record check
    reads the block, and a record that satisfied only one of them would be
    reported as unstamped by the other.
    """
    return {
        "schema": SCHEMA_ARM,
        "schema_version": canonkit.SCHEMA_VERSION,
        "artifact": slug,
        "record_kind": "arm",
        "replicate": int(replicate),
        "arm": arm,
        "index": summary["index"],
        "n": summary["n"],
        "wall_ms": summary["wall_ms"],
        "server_took_ms": summary["server_took_ms"],
        "total_hits": int(sum(hits)),
        "zero_hit_queries": int(sum(1 for h in hits if h == 0)),
        "queries_compared_with_other_arm": int(equivalence["queries"]),
        "corpus": corpus,
        "n_queries": n_queries,
        "environment": environment,
        "gate_token": token,
        "started_at": run_block.get("started_at"),
        "started_at_utc": run_block.get("started_at_utc"),
        "finished_at": run_block.get("finished_at"),
        "finished_at_utc": run_block.get("finished_at_utc"),
        "run": run_block,
    }


def pair_record(slug, token, replicate, result, corpus, n_queries, environment,
                total_runtime_seconds, guards, run_block):
    """What only the PAIR can say: the equivalence check, the deltas, the guards."""
    record = {
        "schema": SCHEMA_PAIR,
        "schema_version": canonkit.SCHEMA_VERSION,
        "artifact": slug,
        "record_kind": "pair",
        "replicate": int(replicate),
        "corpus": corpus,
        "n_queries": n_queries,
        "environment": environment,
        "total_runtime_seconds": total_runtime_seconds,
        "before": result["before"],
        "after": result["after"],
        "equivalence": result["equivalence"],
        "delta_wall": result["delta_wall"],
        "delta_server": result["delta_server"],
        "gate_token": token,
        "started_at": run_block.get("started_at"),
        "started_at_utc": run_block.get("started_at_utc"),
        "finished_at": run_block.get("finished_at"),
        "finished_at_utc": run_block.get("finished_at_utc"),
        "run": run_block,
    }
    record.update(guards)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Load both indices, replay the seeded query sample, and "
                    "write one replicate's records. Requires a gate token: run "
                    "`python gate.py` first.")
    parser.add_argument("doc_count", nargs="?", type=int,
                        default=DEFAULT_DOC_COUNT,
                        help="documents loaded into EACH index (default: "
                             "%d)" % DEFAULT_DOC_COUNT)
    parser.add_argument("n_queries", nargs="?", type=int,
                        default=DEFAULT_N_QUERIES,
                        help="logical lookups replayed against EACH index "
                             "(default: %d)" % DEFAULT_N_QUERIES)
    parser.add_argument("--replicate", type=int, default=DEFAULT_REPLICATE,
                        help="which replicate of this arm pair this run is "
                             "(default: %d). Each replicate writes its own "
                             "records; nothing is averaged across them."
                             % DEFAULT_REPLICATE)
    parser.add_argument("--overwrite", action="store_true",
                        help="permit this replicate to replace records already "
                             "on disk. Refused by default.")
    parser.add_argument("--host", default="http://localhost:9200",
                        help="the Elasticsearch node to measure against")
    args = parser.parse_args(argv)

    results_dir = str(RESULTS)
    os.makedirs(results_dir, exist_ok=True)
    slug = os.path.basename(os.path.abspath(str(ROOT))) or "artifact"

    # REFUSES (exit 2) BEFORE ANYTHING IS MEASURED when no gate authorised this.
    # Called first, deliberately: a run that connected, loaded 2.5 million
    # documents and then discovered it had no token would have spent the machine
    # to learn something a file read answers.
    token = canonkit.require_gate(results_dir)

    paths = replicate_paths(results_dir, args.replicate)
    refuse_existing(paths, args.overwrite)

    handle = runmeta.start_run(
        results_dir, paths["run_id"], token,
        extra={
            "doc_count_requested": args.doc_count,
            "n_queries_requested": args.n_queries,
            "replicate": int(args.replicate),
            "host": args.host,
            "argv": list(sys.argv[1:]),
        })
    print("[run] replicate %d, gate token %s, started %s"
          % (args.replicate, token[:12], handle.started_at), flush=True)

    t0 = time.time()

    print("=== LOAD: %s docs into each index ===" % format(args.doc_count, ","),
          flush=True)
    corpus = load.main(args.doc_count, host=args.host)

    print("\n=== BENCH: %d queries against each index ===" % args.n_queries,
          flush=True)
    result, hits = bench.main(host=args.host, n_queries=args.n_queries,
                              return_hits=True)
    total_runtime_seconds = round(time.time() - t0, 1)

    environment = environment_block()
    payload = {
        "corpus": corpus,
        "n_queries": args.n_queries,
        "before": result["before"],
        "after": result["after"],
        "equivalence": result["equivalence"],
    }
    guards = build_guards(payload)

    runmeta.finish_run(
        handle, api_spend_usd=0.0, gpu_minutes=0.0,
        extra={
            "doc_count_loaded": corpus.get("doc_count"),
            "es_server_version": corpus.get("es_version"),
            "elasticsearch_client": environment["elasticsearch_client"],
            "total_runtime_seconds": total_runtime_seconds,
            "all_guards_passed": guards["all_guards_passed"],
        })
    block = runmeta.run_block(handle)

    for arm, key in (("before", "before"), ("after", "after")):
        canonkit.atomic_write_json(
            paths[arm],
            arm_record(slug, token, args.replicate, arm, result[key],
                       hits[key], result["equivalence"], corpus,
                       args.n_queries, environment, block))
    canonkit.atomic_write_json(
        paths["pair"],
        pair_record(slug, token, args.replicate, result, corpus,
                    args.n_queries, environment, total_runtime_seconds,
                    guards, block))

    b = result["before"]["server_took_ms"]
    a = result["after"]["server_took_ms"]
    bw = result["before"]["wall_ms"]
    aw = result["after"]["wall_ms"]
    print("\n--- server-side took(ms) ---")
    print("  before  p50=%8s  p95=%8s  p99=%8s" % (b["p50"], b["p95"], b["p99"]))
    print("  after   p50=%8s  p95=%8s  p99=%8s" % (a["p50"], a["p95"], a["p99"]))
    print("--- client wall(ms) ---")
    print("  before  p50=%8s  p95=%8s  p99=%8s"
          % (bw["p50"], bw["p95"], bw["p99"]))
    print("  after   p50=%8s  p95=%8s  p99=%8s"
          % (aw["p50"], aw["p95"], aw["p99"]))

    # The guard array, printed with its population AND its floor on every line.
    # A verdict with no count beside it cannot be read as a pass.
    for guard in guards["guards"]:
        print("[guard] %-34s %-4s population=%d of >=%s  %s"
              % (guard["id"], "pass" if guard["passed"] else "FAIL",
                 guard["population"], guard["minimum_required"],
                 guard["population_label"]))
    print("[guard] all_guards_passed = %s over %d guard(s)"
          % (guards["all_guards_passed"], len(guards["guards"])))

    print("\n[done] replicate %d wrote %s, %s and %s in %.1f s"
          % (args.replicate, os.path.basename(paths["before"]),
             os.path.basename(paths["after"]),
             os.path.basename(paths["pair"]), total_runtime_seconds))
    return canonkit.EXIT_PASS if guards["all_guards_passed"] else canonkit.EXIT_GUARD_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
