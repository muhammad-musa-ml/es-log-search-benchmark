"""The two index designs under test.

BEFORE - what you get by NOT thinking about mapping. Elasticsearch dynamic
mapping infers every string field as `text` (analyzed, scored) with a
`.keyword` sub-field. This is the real default, not a strawman: it is exactly
what an index looks like when documents are bulk-loaded without an explicit
mapping. The matching query is a broad `multi_match` across every field.

AFTER - the structured-lookup design. Dimension fields are mapped as `keyword`
only (not analyzed, no scoring machinery), the free-text field stays `text`,
numerics and dates get real types. The matching query runs entirely in FILTER
context, so Elasticsearch skips scoring altogether and the results are
cacheable in the node query cache.

Both indices hold byte-identical documents and answer the same logical
questions. Only the mapping and the query formulation differ.
"""
from __future__ import annotations

# Shared so the comparison is not confounded by shard count or replica count.
COMMON_SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "30s",
}

BEFORE_INDEX = "logs-before"
AFTER_INDEX = "logs-after"

# ---------------------------------------------------------------------------
# BEFORE: dynamic mapping left ON. Only @timestamp is pinned, because ES infers
# ISO-8601 strings as dates anyway and pinning it removes an irrelevant
# difference between the two indices. Everything else is inferred: every
# dimension becomes `text` + `.keyword`, which is the default this benchmark
# is about.
# ---------------------------------------------------------------------------
BEFORE_MAPPING = {
    "settings": COMMON_SETTINGS,
    "mappings": {
        "dynamic": True,
        "properties": {
            "@timestamp": {"type": "date"},
        },
    },
}

# ---------------------------------------------------------------------------
# AFTER: explicit. Dimensions are `keyword`; the only analyzed field is the one
# that genuinely needs full-text search.
# ---------------------------------------------------------------------------
AFTER_MAPPING = {
    "settings": COMMON_SETTINGS,
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "@timestamp": {"type": "date"},
            "service": {"type": "keyword"},
            "level": {"type": "keyword"},
            "region": {"type": "keyword"},
            "host": {"type": "keyword"},
            "endpoint": {"type": "keyword"},
            "trace_id": {"type": "keyword"},
            "tenant_id": {"type": "keyword"},
            "status_code": {"type": "integer"},
            "duration_ms": {"type": "integer"},
            "message": {"type": "text"},
        },
    },
}

# Every field the naive multi_match has to fan out across. This is the cost the
# BEFORE design pays: the query is analyzed and scored against each of them.
MULTI_MATCH_FIELDS = [
    "service", "level", "region", "host", "endpoint",
    "trace_id", "tenant_id", "message",
]
