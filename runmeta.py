"""The run recorder: machine timestamps, the gate token, and what else was running.

WHY THIS FILE EXISTS, IN ONE SENTENCE: every number this benchmark publishes was
produced by a process that started at some instant, ended at another, and shared
one Docker VM with whatever else happened to be running - and until now none of
those three facts was written down by the machine that knew them.

THE TIMESTAMPS ARE WRITTEN BY THE RUN, NEVER BY A HUMAN.
Both forms are stored. The local stamp carries a REAL offset, because a reader
asking "when was this measured" means the day it was on the machine; the UTC
counterpart sits beside it so two runs can be ordered without reasoning about
offsets. Both come from the shared core's now_local() / now_utc(). The naive UTC
constructor is never used: it returns a datetime carrying no timezone at all, so
a literal offset appended to it produces a string that claims what the object
never had. That failure type-checks, which is why it is worth a paragraph.

THE COST TRIPLE IS {api_spend_usd, gpu_minutes, wall_seconds}, ALL THREE REQUIRED.
This benchmark calls no metered API and touches no GPU - Elasticsearch is CPU
and memory only - so both of the first two are recorded as 0.0. They are not
OMITTED. An omitted key and a recorded zero are different claims, and a reader
doing `record.get("api_spend_usd", 0.0)` cannot tell them apart - so a run that
never recorded its cost would read, downstream, as a run that was free.

`wall_seconds` is DERIVED from the handle and cannot be supplied. It is measured
on the monotonic clock rather than by subtracting the two wall-clock stamps, so a
clock adjustment or a DST transition mid-run cannot produce a negative duration.

WHAT ELSE WAS ON THE MACHINE, RECORDED PER RUN AND NOT ONCE.
`results/RESULTS.md` lists "no concurrent load" among the conditions its numbers
were read under, and that is a claim about the environment a run happened in
rather than about the benchmark. It is invisible after the fact unless the run
writes it down - and on a single Docker VM shared with whatever else the machine
is doing, an Elasticsearch node at a fixed 2 GiB heap is exactly the workload a
neighbour distorts. So every run brackets itself with two container censuses -
`docker_contention` at the start and `docker_contention_at_finish` at the end -
and a container that appeared mid-run shows up as a difference between them. A
run with no contention evidence cannot honestly be compared with another.

The census records container NAMES, IMAGES and STATUS. It records no
environment, no command line and no mounted path, because a run record is not a
place a credential may land.

A RUN THAT CANNOT NAME ITS GATE IS REFUSED, NOT WRITTEN.
start_run() raises on an empty gate token. A record with no token cannot be tied
back to the gate that authorised it, so nothing downstream can tell it from a
measurement that ran without one - and that is the exact confusion the token
exists to prevent.
"""
from __future__ import annotations

import os
import subprocess
import time

import canonkit

SCHEMA = "eslogbench/run/1"

# Where a run's own record lives, and where any per-item records live. Kept
# apart deliberately: a run record sitting in the same directory as the per-item
# records would be counted as an item by anything that enumerates them, which
# inflates a denominator with a file that is not one.
RAW_DIRNAME = "raw"
ITEMS_DIRNAME = "items"

# The sentinel that makes an omitted cost field a refusal rather than a zero. A
# default of 0.0 would silently record "this run was free" for every caller who
# forgot, which is the exact confusion the triple exists to prevent.
_REQUIRED = object()

# The container census. `--no-trunc` so a long name is not silently cut to
# something ambiguous; the three fields are the ones that identify a neighbour
# without quoting its configuration.
DOCKER_PS_ARGV = ("docker", "ps", "--no-trunc",
                  "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}")
DOCKER_PS_TIMEOUT_SECONDS = 30


class RunHandle(object):
    """What start_run returns and finish_run consumes."""

    def __init__(self, results_dir, run_id, gate_token, started_at,
                 started_at_utc, started_monotonic, path, record):
        self.results_dir = results_dir
        self.run_id = run_id
        self.gate_token = gate_token
        self.started_at = started_at
        self.started_at_utc = started_at_utc
        self.started_monotonic = started_monotonic
        self.path = path
        self.record = record


def raw_dir(results_dir):
    return os.path.join(str(results_dir), RAW_DIRNAME)


def items_dir(results_dir):
    return os.path.join(str(results_dir), RAW_DIRNAME, ITEMS_DIRNAME)


def environment_fingerprint():
    """What the machine was, recorded PER RUN rather than once."""
    import platform
    import sys

    return {
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
    }


def docker_contention(read_at, runner=None):
    """Who else was on the Docker VM, READ at this instant. Never assumed.

    An unreachable engine is recorded as an ERROR STRING with an empty container
    list and a NULL count - never as zero containers. "Nothing else was running"
    and "I could not look" are different claims, and a zero would let the second
    be read as the first by anyone comparing two runs.
    """
    census = {
        "probe": " ".join(DOCKER_PS_ARGV),
        "read_at": read_at,
        "containers": [],
        "container_count": None,
        "error": None,
    }
    runner = runner or _default_docker_ps
    try:
        raw = runner(list(DOCKER_PS_ARGV))
    except Exception as exc:                                    # noqa: BLE001
        census["error"] = "%s: %s" % (exc.__class__.__name__, exc)
        return census

    containers = []
    for line in str(raw).splitlines():
        line = line.strip()
        if not line:
            continue
        fields = line.split("\t")
        containers.append({
            "name": fields[0] if len(fields) > 0 else "",
            "image": fields[1] if len(fields) > 1 else "",
            "status": fields[2] if len(fields) > 2 else "",
        })
    census["containers"] = containers
    census["container_count"] = len(containers)
    return census


def _default_docker_ps(argv):
    completed = subprocess.run(argv, capture_output=True, text=True,
                               timeout=DOCKER_PS_TIMEOUT_SECONDS, shell=False)
    if completed.returncode != 0:
        raise OSError("docker ps exited %d: %s"
                      % (completed.returncode,
                         (completed.stderr or "").strip()[-300:]))
    return completed.stdout


def start_run(results_dir, run_id, gate_token, extra=None, clock_local=None,
              clock_utc=None, monotonic=None, contention=None):
    """Open a run record. Refuses a run that carries no gate token.

    The token is what later ties this record to the gate that authorised it. A
    run with a blank one cannot be checked against anything, so it is refused
    here rather than written and discovered later.
    """
    if gate_token is None or not str(gate_token).strip():
        raise ValueError(
            "start_run(%r): refusing to open a run with an empty gate token. A "
            "run record with no token cannot be tied to the gate that "
            "authorised it, so nothing downstream can tell it from a run that "
            "measured without one. Call canonkit.require_gate() first and pass "
            "what it returns." % (run_id,))

    clock_local = clock_local or canonkit.now_local
    clock_utc = clock_utc or canonkit.now_utc
    monotonic = monotonic or time.monotonic

    started_at = clock_local()
    started_at_utc = clock_utc()
    path = os.path.join(raw_dir(results_dir), "%s.json" % run_id)

    census = contention if contention is not None else docker_contention(started_at)

    record = {
        "schema": SCHEMA,
        "schema_version": canonkit.SCHEMA_VERSION,
        "run_id": run_id,
        "gate_token": gate_token,
        "started_at": started_at,
        "started_at_utc": started_at_utc,
        "finished_at": None,
        "finished_at_utc": None,
        "env": environment_fingerprint(),
        "docker_contention": census,
    }
    if extra:
        record.update(extra)

    canonkit.atomic_write_json(path, record)
    return RunHandle(results_dir, run_id, gate_token, started_at, started_at_utc,
                     monotonic(), path, record)


def finish_run(handle, api_spend_usd=_REQUIRED, gpu_minutes=_REQUIRED,
               clock_local=None, clock_utc=None, monotonic=None, extra=None,
               contention=None, **derived):
    """Close a run record. All three cost fields are REQUIRED.

    THE REFUSALS HAPPEN BEFORE ANYTHING IS WRITTEN, so a refused call leaves the
    opening record exactly as start_run wrote it. A partial record written and
    then rejected would be indistinguishable, to any later reader, from a run
    that genuinely recorded nothing.

    `wall_seconds` is REFUSED rather than accepted-and-ignored. An
    accepted-but-ignored parameter does not hold a decision: the next caller
    passes it, and the one after that reads it back expecting to see what they
    sent.
    """
    clock_local = clock_local or canonkit.now_local
    clock_utc = clock_utc or canonkit.now_utc
    monotonic = monotonic or time.monotonic

    missing = [name for name, value in (("api_spend_usd", api_spend_usd),
                                        ("gpu_minutes", gpu_minutes))
               if value is _REQUIRED]
    if missing:
        raise ValueError(
            "finish_run(%r): the cost triple is incomplete -- %s not supplied. "
            "All three of api_spend_usd, gpu_minutes and wall_seconds are "
            "REQUIRED; a run that spent nothing writes 0.0 and does not omit "
            "the key. An omitted field reads downstream as a run that cost "
            "nothing, because .get(key, 0.0) cannot tell an absence from a "
            "zero." % (handle.run_id, " and ".join(missing)))

    if "wall_seconds" in derived:
        raise ValueError(
            "finish_run(%r): wall_seconds is DERIVED from the handle and cannot "
            "be supplied (got %r). It is measured on the monotonic clock, so a "
            "clock adjustment or a DST transition mid-run cannot produce a "
            "negative duration -- and a caller-supplied duration would record "
            "what the caller believed rather than what elapsed."
            % (handle.run_id, derived["wall_seconds"]))

    unknown = sorted(set(derived) - {"wall_seconds"})
    if unknown:
        raise ValueError(
            "finish_run(%r): unknown field(s) %s. Pass run-specific values "
            "through `extra=` so they are recorded deliberately rather than "
            "absorbed by a signature that accepts anything."
            % (handle.run_id, unknown))

    wall_seconds = monotonic() - handle.started_monotonic
    finished_at = clock_local()
    census = (contention if contention is not None
              else docker_contention(finished_at))

    record = dict(handle.record)
    record.update({
        "finished_at": finished_at,
        "finished_at_utc": clock_utc(),
        "api_spend_usd": float(api_spend_usd),
        "gpu_minutes": float(gpu_minutes),
        "wall_seconds": wall_seconds,
        "docker_contention_at_finish": census,
    })
    if extra:
        record.update(extra)

    canonkit.atomic_write_json(handle.path, record)
    handle.record = record
    return handle.path


def run_block(handle):
    """The stamp a MEASUREMENT FILE carries, copied out of the run record.

    A results file is what a reader opens; the run record is where the machine
    wrote its stamps. Copying the fields into the results file means the two
    cannot be separated by a move or a partial copy - and a reader who opens the
    output alone can still see when it was produced, how long it took, what it
    cost and which gate authorised it.

    Called AFTER finish_run, so the closing fields are present. Called before,
    it returns a block whose `finished_at` is null, which is an UNFINISHED run
    and is reported as such rather than as a recorded nothing.
    """
    record = handle.record
    block = {
        "run_id": record.get("run_id"),
        "gate_token": record.get("gate_token"),
        "started_at": record.get("started_at"),
        "started_at_utc": record.get("started_at_utc"),
        "finished_at": record.get("finished_at"),
        "finished_at_utc": record.get("finished_at_utc"),
        "api_spend_usd": record.get("api_spend_usd"),
        "gpu_minutes": record.get("gpu_minutes"),
        "wall_seconds": record.get("wall_seconds"),
        "record_path": str(handle.path).replace(chr(92), "/"),
    }
    for key in ("docker_contention", "docker_contention_at_finish"):
        if key in record:
            block[key] = record[key]
    return block


def write_item(results_dir, item_id, payload):
    """Write ONE per-item record - the first link of the chain a re-derivation walks.

    Per-item records are what make a figure re-derivable: a count over them is
    reproducible, while a numerator typed into a summary is not.
    """
    path = os.path.join(items_dir(results_dir), "%s.json" % item_id)
    record = dict(payload)
    record.setdefault("item_id", item_id)
    canonkit.atomic_write_json(path, record)
    return path
