"""Bulk-load the identical corpus into both indices."""
from __future__ import annotations

import sys
import time

from elasticsearch import Elasticsearch, helpers

from .docgen import generate
from .mappings import BEFORE_INDEX, AFTER_INDEX, BEFORE_MAPPING, AFTER_MAPPING


def connect(host: str = "http://localhost:9200", timeout: int = 120) -> Elasticsearch:
    return Elasticsearch(host, request_timeout=timeout, retry_on_timeout=True, max_retries=3)


def recreate(es: Elasticsearch, name: str, body: dict) -> None:
    if es.indices.exists(index=name):
        es.indices.delete(index=name)
    es.indices.create(index=name, **body)
    print(f"[load] created {name}")


def _actions(index: str, docs):
    for doc in docs:
        yield {"_index": index, "_source": doc}


def load_index(es: Elasticsearch, index: str, count: int, seed: int,
               chunk_size: int = 5000) -> float:
    """Bulk-load `count` documents. Returns elapsed seconds."""
    t0 = time.time()
    done = 0
    for ok, item in helpers.streaming_bulk(
        es,
        _actions(index, generate(count, seed=seed)),
        chunk_size=chunk_size,
        max_retries=3,
        request_timeout=180,
        raise_on_error=True,
    ):
        done += 1
        if done % 250000 == 0:
            print(f"[load] {index}: {done:,}/{count:,} "
                  f"({time.time() - t0:,.0f}s)", flush=True)
    elapsed = time.time() - t0
    print(f"[load] {index}: {done:,} docs in {elapsed:,.1f}s", flush=True)
    return elapsed


def finalize(es: Elasticsearch, index: str) -> int:
    """Refresh, force-merge to one segment, and return the live doc count.

    Force-merging BOTH indices to the same segment count is what keeps the
    comparison fair - segment count materially affects query latency, so
    leaving it to chance would confound the result.
    """
    es.indices.refresh(index=index)
    es.indices.forcemerge(index=index, max_num_segments=1, request_timeout=1800)
    es.indices.refresh(index=index)
    n = es.count(index=index)["count"]
    print(f"[load] {index}: {n:,} docs live, force-merged to 1 segment")
    return n


def main(count: int, host: str = "http://localhost:9200", seed: int = 20240517) -> dict:
    es = connect(host)
    info = es.info()
    print(f"[load] Elasticsearch {info['version']['number']} at {host}")

    recreate(es, BEFORE_INDEX, BEFORE_MAPPING)
    recreate(es, AFTER_INDEX, AFTER_MAPPING)

    # Same seed for both -> byte-identical corpora. Only the mapping differs.
    t_before = load_index(es, BEFORE_INDEX, count, seed)
    t_after = load_index(es, AFTER_INDEX, count, seed)

    n_before = finalize(es, BEFORE_INDEX)
    n_after = finalize(es, AFTER_INDEX)

    if n_before != n_after:
        raise SystemExit(f"corpora differ: before={n_before} after={n_after}")

    return {
        "doc_count": n_before,
        "load_seconds_before": round(t_before, 1),
        "load_seconds_after": round(t_after, 1),
        "es_version": info["version"]["number"],
    }


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2_500_000
    main(n)
