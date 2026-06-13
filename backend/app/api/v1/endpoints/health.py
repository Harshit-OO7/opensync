"""
Health check endpoints.

GET /api/v1/health/       — liveness (always 200 if app is running)
GET /api/v1/health/ready  — readiness (checks DB, Redis, Qdrant)
"""

import time

import structlog
from fastapi import APIRouter

logger = structlog.get_logger()
router = APIRouter()


@router.get("/")
async def liveness():
    """
    Liveness probe.
    Returns 200 if the application process is running.
    """
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    """
    Readiness probe. Checks all downstream dependencies.

    Phase 0: Returns mock status.
    Phase 1: Replace mock checks with real connection checks.
    """
    checks = {}
    overall_ok = True
    start = time.monotonic()

    # TODO Phase 1: replace with real DB ping
    checks["postgres"] = {"status": "not_configured", "latency_ms": None}

    # TODO Phase 1: replace with real Redis ping
    checks["redis"] = {"status": "not_configured", "latency_ms": None}

    # TODO Phase 2: replace with real Qdrant ping
    checks["qdrant"] = {"status": "not_configured", "latency_ms": None}

    total_ms = round((time.monotonic() - start) * 1000, 2)

    return {
        "status": "ok" if overall_ok else "degraded",
        "checks": checks,
        "total_latency_ms": total_ms,
    }
