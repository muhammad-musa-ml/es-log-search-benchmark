"""The replayed query sample.

One logical workload, expressed two ways.

Each sampled query asks the SAME question of both indices - "show me events
matching this combination of dimensions" - so the comparison measures the
mapping-and-query design, not two different workloads.

The sample is seeded, so the identical 500 queries run against both indices in
the same order on every run.
"""
from __future__ import annotations

import random

from .docgen import SERVICES, LEVELS, REGIONS, ENDPOINTS, HOST_COUNT, TENANT_COUNT
from .mappings import MULTI_MATCH_FIELDS


def build_sample(n: int = 500, seed: int = 902024):
    """Return `n` logical lookups as dicts of dimension -> value."""
    rng = random.Random(seed)
    sample = []
    for _ in range(n):
        # Vary the shape so the workload is not one single query repeated:
        # some lookups pin 2 dimensions, some 3, some 4.
        q = {
            "service": rng.choice(SERVICES),
            "level": rng.choice(LEVELS),
        }
        width = rng.randint(2, 4)
        if width >= 3:
            q["region"] = rng.choice(REGIONS)
        if width >= 4:
            q["endpoint"] = rng.choice(ENDPOINTS)
        sample.append(q)
    return sample


def before_query(q: dict) -> dict:
    """The naive formulation: one broad multi_match over every field.

    The dimension values are concatenated into a single query string and fanned
    out across all fields, which is what you write when the mapping has not told
    you which fields are structured. Runs in QUERY context, so every hit is
    scored across every field.
    """
    terms = " ".join(str(v) for v in q.values())
    return {
        "query": {
            "multi_match": {
                "query": terms,
                "fields": MULTI_MATCH_FIELDS,
                # cross_fields, NOT the best_fields default: the dimension values
                # live in DIFFERENT fields, so best_fields + operator:and would
                # require one single field to contain every term and would match
                # almost nothing. cross_fields treats the listed fields as one
                # blended field, which is the formulation that actually answers
                # this lookup - and is what someone reaches for when the mapping
                # has not distinguished structured fields from prose.
                "type": "cross_fields",
                "operator": "and",
            }
        },
        "size": 10,
    }


def after_query(q: dict) -> dict:
    """The structured formulation: term filters on mapped keyword fields.

    Entirely in FILTER context - no scoring, and the individual clauses are
    eligible for the node query cache.
    """
    return {
        "query": {
            "bool": {
                "filter": [{"term": {field: value}} for field, value in q.items()]
            }
        },
        "size": 10,
    }
