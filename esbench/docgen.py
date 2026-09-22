"""Synthetic log/event document generator.

Shapes documents like a realistic application-log corpus: a handful of
low-cardinality dimensions (service, level, region, host) plus a
high-cardinality identifier (trace_id) and a free-text message.

Deterministic: seeded, so the corpus and the query sample are reproducible
across runs and machines.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

SERVICES = [
    "auth-api", "session-svc", "billing-api", "device-registry", "telemetry-ingest",
    "config-svc", "policy-engine", "notification-svc", "search-api", "audit-log",
    "fleet-manager", "provisioning-api",
]
LEVELS = ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
LEVEL_WEIGHTS = [30, 45, 15, 9, 1]
REGIONS = ["us-west-2", "us-east-1", "eu-central-1", "eu-west-1", "ap-south-1", "ap-northeast-1"]
ENDPOINTS = [
    "/v1/session/refresh", "/v1/session/create", "/v1/device/register",
    "/v1/device/heartbeat", "/v1/policy/evaluate", "/v1/config/fetch",
    "/v1/telemetry/batch", "/v1/audit/query", "/v1/search/events",
    "/v1/fleet/status", "/v1/notify/dispatch", "/v1/billing/usage",
]
STATUS_CODES = [200, 201, 204, 400, 401, 403, 404, 409, 429, 500, 502, 503, 504]
STATUS_WEIGHTS = [40, 8, 6, 9, 7, 4, 6, 3, 4, 5, 3, 3, 2]

MESSAGE_TEMPLATES = [
    "request completed in {ms}ms",
    "connection refused by upstream {svc}",
    "retry {n} of {m} after transient failure",
    "cache miss for key {key}",
    "token validation failed for tenant {tenant}",
    "rate limit exceeded, shedding request",
    "downstream timeout contacting {svc}",
    "device heartbeat received, drift {ms}ms",
    "policy evaluation returned deny",
    "batch accepted, {n} records queued",
    "circuit breaker opened for {svc}",
    "config revision {n} applied successfully",
]

HOST_COUNT = 512
TENANT_COUNT = 4096


def _weighted(rng: random.Random, population, weights):
    return rng.choices(population, weights=weights, k=1)[0]


def generate(count: int, seed: int = 20240517, start: datetime | None = None):
    """Yield `count` log documents as dicts.

    The timestamp walks forward so the corpus looks like a real time-ordered
    ingest rather than uniform noise.
    """
    rng = random.Random(seed)
    if start is None:
        start = datetime(2024, 5, 17, tzinfo=timezone.utc)
    ts = start

    for i in range(count):
        ts = ts + timedelta(milliseconds=rng.randint(5, 60))
        service = rng.choice(SERVICES)
        level = _weighted(rng, LEVELS, LEVEL_WEIGHTS)
        template = rng.choice(MESSAGE_TEMPLATES)
        message = template.format(
            ms=rng.randint(1, 4000),
            svc=rng.choice(SERVICES),
            n=rng.randint(1, 500),
            m=rng.randint(2, 5),
            key=f"k-{rng.randint(0, 99999):05d}",
            tenant=f"t-{rng.randint(0, TENANT_COUNT - 1):04d}",
        )
        yield {
            "@timestamp": ts.isoformat(),
            "service": service,
            "level": level,
            "region": rng.choice(REGIONS),
            "host": f"host-{rng.randint(0, HOST_COUNT - 1):04d}",
            "endpoint": rng.choice(ENDPOINTS),
            "trace_id": f"{rng.getrandbits(64):016x}",
            "tenant_id": f"t-{rng.randint(0, TENANT_COUNT - 1):04d}",
            "status_code": _weighted(rng, STATUS_CODES, STATUS_WEIGHTS),
            "duration_ms": rng.randint(1, 5000),
            "message": message,
        }
