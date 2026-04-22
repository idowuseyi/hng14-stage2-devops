import pytest
import fakeredis.aioredis


@pytest.fixture
async def fake_redis():
    """Provide a fake Redis instance for testing."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
async def setup_app(fake_redis):
    """Set up the FastAPI app with a fake Redis instance."""
    from main import app
    app.state.redis = fake_redis
    yield app
    app.state.redis = None
