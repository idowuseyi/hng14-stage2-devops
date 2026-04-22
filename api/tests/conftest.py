import pytest
import fakeredis.aioredis


@pytest.fixture
async def fake_redis():
    """Provide a fake Redis instance for testing."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)
