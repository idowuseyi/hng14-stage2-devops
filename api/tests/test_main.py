import pytest
import os
from unittest.mock import patch, AsyncMock
from httpx import ASGITransport, AsyncClient
import fakeredis.aioredis

from main import app


@pytest.fixture
async def setup_app(fake_redis):
    """Set up the FastAPI app with a fake Redis instance.

    We patch the Redis class so the lifespan context manager
    creates a fake Redis instead of trying to connect to a real one.
    """
    app.state.redis = fake_redis
    yield
    # Reset state after test
    if hasattr(app.state, "redis"):
        app.state.redis = None


# We need to prevent the lifespan from creating a real Redis connection.
# The simplest approach: set REDIS_HOST to a dummy value and mock Redis
# at import time, OR just set app.state.redis before the client is created
# and make the lifespan skip if redis is already set.


@pytest.mark.asyncio
async def test_health_endpoint(setup_app):
    """Test that the health endpoint returns 200 and healthy status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_create_job(setup_app, fake_redis):
    """Test that creating a job returns a job_id and queues it in Redis."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["job_id"]

    # Verify job was queued in Redis
    queued = await fake_redis.lrange("job:queue", 0, -1)
    assert data["job_id"] in queued

    # Verify job status was set
    status = await fake_redis.hget(f"job:{data['job_id']}", "status")
    assert status == "queued"


@pytest.mark.asyncio
async def test_get_job_status(setup_app, fake_redis):
    """Test that getting a job status returns the correct status."""
    # Pre-populate Redis with a completed job
    await fake_redis.hset("job:test-123-456", "status", "completed")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/jobs/test-123-456")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-123-456"
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_get_job_not_found(setup_app):
    """Test that getting a non-existent job returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/jobs/nonexistent-job-id")
    assert response.status_code == 404
    assert response.json()["error"] == "not found"
