"""
Tests for health check endpoints.
These are the first tests in the project — they verify the application
starts and the health endpoints respond correctly.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_root_health_check():
    """GET /health should return 200 with status ok."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_v1_liveness():
    """GET /api/v1/health/ should return 200."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_v1_readiness_structure():
    """GET /api/v1/health/ready should return correct structure."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert "checks" in data
    assert "total_latency_ms" in data
    assert "postgres" in data["checks"]
    assert "redis" in data["checks"]
    assert "qdrant" in data["checks"]