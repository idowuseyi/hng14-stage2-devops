import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test that the health endpoint returns 200 and healthy status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_create_job(fake_redis):
    """Test that creating a job returns a job_id and queues it in Redis."""
    app.state.redis = fake_redis
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
async def test_get_job_status(fake_redis):
    """Test that getting a job status returns the correct status."""
    # Pre-populate Redis with a completed job
    await fake_redis.hset("job:test-123-456", "status", "completed")
    app.state.redis = fake_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/jobs/test-123-456")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-123-456"
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_get_job_not_found(fake_redis):
    """Test that getting a non-existent job returns 404."""
    app.state.redis = fake_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/jobs/nonexistent-job-id")
    assert response.status_code == 404
    assert response.json()["error"] == "not found"
