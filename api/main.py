import os
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Redis connection lifecycle."""
    # Skip Redis initialization if already set (e.g., in tests)
    if not hasattr(app.state, "redis") or app.state.redis is None:
        app.state.redis = Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            password=os.environ.get("REDIS_PASSWORD"),
            decode_responses=True,
        )
    yield
    if hasattr(app.state, "redis") and app.state.redis is not None:
        # Only close if we created it (not a test mock)
        if hasattr(app.state.redis, "close"):
            try:
                await app.state.redis.close()
            except Exception:
                pass


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check endpoint for Docker HEALTHCHECK and docker-compose depends_on."""
    return {"status": "healthy"}


@app.post("/jobs")
async def create_job():
    """Create a new job and push it to the Redis queue."""
    try:
        r: Redis = app.state.redis
        job_id = str(uuid.uuid4())
        await r.lpush("job:queue", job_id)
        await r.hset(f"job:{job_id}", "status", "queued")
        logger.info(f"Created job {job_id}")
        return {"job_id": job_id}
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get the status of a job by its ID."""
    try:
        r: Redis = app.state.redis
        status = await r.hget(f"job:{job_id}", "status")
        if not status:
            return JSONResponse(
                status_code=404, content={"error": "not found"}
            )
        return {"job_id": job_id, "status": status}
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
