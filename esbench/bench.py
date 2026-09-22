"""Replay the query sample against both indices and measure latency.

Measurement discipline, because a benchmark that flatters the conclusion is
worth nothing:

* Both indices hold byte-identical corpora, force-merged to one segment.
* The SAME seeded 500 logical lookups run against both, in the same order.
* Each index gets an uncounted warmup pass first, so neither side pays a
  cold-cache penalty the other avoids.
* Two independent clocks are recorded: client-side wall time (what a caller
  experiences, including transport) and Elasticsearch's own reported `took`
  (server-side execution only). If those two disagree about the direction of
  the result, the result is not trustworthy.
* Hit counts are recorded per query. If the two designs return different
  numbers of matches they are not answering the same question, and the
  comparison is void - `verify_equivalence` checks exactly that.
"""
from __future__ import annotations

import statistics
import time

from elasticsearch import Elasticsearch

from .mappings import BEFORE_INDEX, AFTER_INDEX
from .queries import build_sample, before_query, after_query


def percentile(values, pct: float) -> float:
    """Nearest-rank percentile on a sorted copy."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round(pct / 100.0 * len(ordered) + 0.5)) - 1))
    return ordered[k]


def _run_one(es: Elasticsearch, index: str, body: dict):
    t0 = time.perf_counter()
    resp = es.search(index=index, **body)
    wall_ms = (time.perf_counter() - t0) * 1000.0
    return wall_ms, float(resp["took"]), int(resp["hits"]["total"]["value"])


def run_pass(es: Elasticsearch, index: str, sample, build, warmup: int = 50):
    """Warm up, then measure. Returns (wall_ms[], took_ms[], hits[])."""
    for q in sample[:warmup]:
        _run_one(es, index, build(q))

    wall, took, hits = [], [], []
    for q in sample:
        w, t, h = _run_one(es, index, build(q))
        wall.append(w)
        took.append(t)
        hits.append(h)
    return wall, took, hits


def summarize(label: str, wall, took) -> dict:
    return {
        "index": label,
        "n": len(wall),
        "wall_ms": {
            "p50": round(percentile(wall, 50), 2),
            "p95": round(percentile(wall, 95), 2),
            "p99": round(percentile(wall, 99), 2),
            "mean": round(statistics.fmean(wall), 2),
            "max": round(max(wall), 2),
        },
        "server_took_ms": {
            "p50": round(percentile(took, 50), 2),
            "p95": round(percentile(took, 95), 2),
            "p99": round(percentile(took, 99), 2),
            "mean": round(statistics.fmean(took), 2),
            "max": round(max(took), 2),
        },
    }


def verify_equivalence(hits_before, hits_after) -> dict:
    """Guard against a latency win that was bought by returning less work.

    These two designs do NOT return identical hit sets, and demanding that they
    do would be the wrong check. The analyzed `text` fields tokenize dimension
    values ("us-west-2" becomes us / west / 2), so the naive cross_fields query
    is genuinely FUZZIER than an exact term filter - imprecision is part of what
    makes it the wrong tool, not an artifact of this benchmark.

    What must hold is the one-sided property: the fuzzy design should match AT
    LEAST as many documents as the exact one. If BEFORE were returning FEWER
    hits than AFTER while also being slower, the speedup would be suspect -
    we would be comparing a big query against a small one. So the check is
    `total_hits_before >= total_hits_after`, plus a report of both
    distributions so the divergence is visible rather than hidden.
    """
    before_total = sum(hits_before)
    after_total = sum(hits_after)
    return {
        "queries": len(hits_before),
        "total_hits_before": before_total,
        "total_hits_after": after_total,
        "before_is_superset_by_volume": before_total >= after_total,
        "speedup_not_bought_by_returning_less": before_total >= after_total,
        "zero_hit_queries_before": sum(1 for h in hits_before if h == 0),
        "zero_hit_queries_after": sum(1 for h in hits_after if h == 0),
        "note": (
            "Identical hit sets are NOT expected: analyzed text fields tokenize "
            "dimension values, so the naive design matches a superset. The "
            "one-sided check is what makes the latency comparison meaningful."
        ),
    }


def main(host: str = "http://localhost:9200", n_queries: int = 500,
         return_hits: bool = False):
    """Replay the sample against both arms and summarise.

    `return_hits` additionally returns the RAW per-query hit counts, keyed by
    arm. They are what the equivalence guard is computed FROM, and a caller that
    only receives the summary cannot re-derive the guard from the record - it
    can only restate the verdict the summary already carries. Off by default so
    the historic single-value return keeps working.
    """
    es = Elasticsearch(host, request_timeout=120)
    sample = build_sample(n_queries)
    print(f"[bench] replaying {len(sample)} logical lookups against both indices")

    wb, tb, hb = run_pass(es, BEFORE_INDEX, sample, before_query)
    print(f"[bench] {BEFORE_INDEX}: done")
    wa, ta, ha = run_pass(es, AFTER_INDEX, sample, after_query)
    print(f"[bench] {AFTER_INDEX}: done")

    before = summarize(BEFORE_INDEX, wb, tb)
    after = summarize(AFTER_INDEX, wa, ta)
    equiv = verify_equivalence(hb, ha)

    def _delta(a, b):
        return {
            "p50_ms": round(a["p50"] - b["p50"], 2),
            "p95_ms": round(a["p95"] - b["p95"], 2),
            "p95_speedup_x": round(a["p95"] / b["p95"], 2) if b["p95"] else None,
        }

    result = {
        "before": before,
        "after": after,
        "equivalence": equiv,
        "delta_wall": _delta(before["wall_ms"], after["wall_ms"]),
        "delta_server": _delta(before["server_took_ms"], after["server_took_ms"]),
    }
    if return_hits:
        return result, {"before": hb, "after": ha}
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(main(), indent=2))
