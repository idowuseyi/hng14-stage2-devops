# FIXES.md — Application Bug Documentation

## Fix 1: Hardcoded Redis host in API

**File:** `api/main.py`
**Line:** 8

**Problem:**
Redis connection used a hardcoded `host="localhost", port=6379`. This fails inside Docker containers where Redis runs as a separate service.

**Fix:**
Read Redis connection details from environment variables: `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`.

**Code Change:**

```python
# Before
r = redis.Redis(host="localhost", port=6379)

# After
app.state.redis = Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    password=os.environ.get("REDIS_PASSWORD"),
    decode_responses=True,
)
```

---

## Fix 2: Synchronous Redis client in async FastAPI

**File:** `api/main.py`
**Line:** 2, 8

**Problem:**
Used synchronous `import redis` with `redis.Redis()`. FastAPI is async — synchronous Redis calls block the event loop and degrade performance under load.

**Fix:**
Replaced with `redis.asyncio` (async Redis client) and made all endpoints `async def` with `await` on Redis operations.

**Code Change:**

```python
# Before
import redis
r = redis.Redis(host="localhost", port=6379)

# After
from redis.asyncio import Redis
r: Redis = app.state.redis  # initialized in lifespan
await r.lpush("job:queue", job_id)
```

---

## Fix 3: Redis client created at module level (no async context)

**File:** `api/main.py`
**Line:** 8

**Problem:**
Redis client was instantiated at module level outside of any async context, which doesn't work properly with `redis.asyncio`.

**Fix:**
Used FastAPI's `lifespan` context manager to create and tear down the Redis connection.

**Code Change:**

```python
# Before
r = redis.Redis(host="localhost", port=6379)

# After
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = Redis(...)
    yield
    await app.state.redis.close()
```

---

## Fix 4: Missing Redis password authentication

**File:** `api/main.py` and `worker/worker.py`
**Line:** 8 (API), 6 (worker)

**Problem:**
The `.env` file defined `REDIS_PASSWORD` but it was never used in the Redis connection. Redis was running without authentication.

**Fix:**
Added `password=os.environ.get("REDIS_PASSWORD")` to the Redis constructor in both API and worker.

**Code Change:**

```python
# Before
r = redis.Redis(host="localhost", port=6379)

# After
r = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
)
```

---

## Fix 5: Queue key name collision

**File:** `api/main.py` and `worker/worker.py`
**Line:** 13 (API), 15 (worker)

**Problem:**
The queue key was `"job"`, which could collide with the hash key namespace `"job:{job_id}"`. Redis keys `job` and `job:something` are technically different, but this is confusing and error-prone.

**Fix:**
Changed queue key to `"job:queue"` for clarity and namespace consistency.

**Code Change:**

```python
# Before
r.lpush("job", job_id)
r.brpop("job", timeout=5)

# After
await r.lpush("job:queue", job_id)
r.brpop("job:queue", timeout=5)
```

---

## Fix 6: No error handling in API endpoints

**File:** `api/main.py`
**Line:** 11-15, 18-22

**Problem:**
Redis operations in both `create_job` and `get_job` had no error handling. If Redis was unreachable, the API would return an unhandled 500 Internal Server Error with a stack trace.

**Fix:**
Wrapped all Redis operations in try/except blocks and returned appropriate JSON error responses.

**Code Change:**

```python
# Before
def create_job():
    job_id = str(uuid.uuid4())
    r.lpush("job", job_id)
    r.hset(f"job:{job_id}", "status", "queued")
    return {"job_id": job_id}

# After
async def create_job():
    try:
        r: Redis = app.state.redis
        job_id = str(uuid.uuid4())
        await r.lpush("job:queue", job_id)
        await r.hset(f"job:{job_id}", "status", "queued")
        return {"job_id": job_id}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
```

---

## Fix 7: Wrong HTTP status code for not-found jobs

**File:** `api/main.py`
**Line:** 21

**Problem:**
When a job was not found, the API returned HTTP 200 with `{"error": "not found"}`. This should be HTTP 404.

**Fix:**
Return `JSONResponse` with `status_code=404`.

**Code Change:**

```python
# Before
if not status:
    return {"error": "not found"}

# After
if not status:
    return JSONResponse(status_code=404, content={"error": "not found"})
```

---

## Fix 8: Fragile `.decode()` call on Redis response

**File:** `api/main.py`
**Line:** 22

**Problem:**
`status.decode()` would crash if `status` was `None` (already handled by the not-found check) or if it was not a bytes object. With `decode_responses=True` in the async Redis client, this is no longer needed.

**Fix:**
Using `decode_responses=True` in the Redis constructor eliminates the need for manual `.decode()` calls.

---

## Fix 9: No health check endpoint in API

**File:** `api/main.py`

**Problem:**
No `/health` endpoint existed. Docker HEALTHCHECK and docker-compose `depends_on` with `condition: service_healthy` require a health check endpoint.

**Fix:**
Added `@app.get("/health")` endpoint returning `{"status": "healthy"}`.

**Code Change:**

```python
# Added
@app.get("/health")
async def health():
    return {"status": "healthy"}
```

---

## Fix 10: Hardcoded Redis host in worker

**File:** `worker/worker.py`
**Line:** 6

**Problem:**
Same as Fix 1 — hardcoded `host="localhost", port=6379` fails inside Docker.

**Fix:**
Read from environment variables.

**Code Change:**

```python
# Before
r = redis.Redis(host="localhost", port=6379)

# After
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)
```

---

## Fix 11: Unused import in worker

**File:** `worker/worker.py`
**Line:** 4

**Problem:**
`import signal` was imported but not used in the original code.

**Fix:**
Removed the unused import, then re-added it properly for the graceful shutdown signal handler.

---

## Fix 12: No graceful shutdown in worker

**File:** `worker/worker.py`
**Line:** 14

**Problem:**
The `while True` loop ignored SIGTERM signals. When Docker stops the container, it sends SIGTERM, waits for a grace period, then force-kills with SIGKILL. The worker would always be force-killed, potentially mid-job.

**Fix:**
Added signal handlers for SIGTERM and SIGINT that set a `shutdown_requested` flag, allowing the worker loop to exit gracefully after finishing the current job.

**Code Change:**

```python
# Added
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    logger.info("Shutdown signal received, finishing current job...")
    shutdown_requested = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

while not shutdown_requested:
    ...
```

---

## Fix 13: No health check mechanism in worker

**File:** `worker/worker.py`

**Problem:**
The worker had no HTTP server or health check mechanism. Docker HEALTHCHECK requires an endpoint to probe.

**Fix:**
Added a lightweight HTTP server running in a daemon thread that serves `/health` on port 9090.

**Code Change:**

```python
# Added
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"healthy"}')

def start_health_server():
    server = HTTPServer(("0.0.0.0", WORKER_HEALTH_PORT), HealthHandler)
    server.serve_forever()

health_thread = threading.Thread(target=start_health_server, daemon=True)
health_thread.start()
```

---

## Fix 14: No error handling in worker Redis operations

**File:** `worker/worker.py`
**Line:** 15, 11

**Problem:**
`r.brpop()` and `r.hset()` had no error handling. A Redis connection failure would crash the worker.

**Fix:**
Wrapped the main loop in try/except with specific handling for `redis.ConnectionError` (retry with backoff) and general exceptions.

---

## Fix 15: Hardcoded API URL in frontend

**File:** `frontend/app.js`
**Line:** 6

**Problem:**
`const API_URL = "http://localhost:8000"` is hardcoded. Inside Docker, the API is at `http://api:8000`, not `localhost`.

**Fix:**
Read from environment variable: `process.env.API_URL || "http://localhost:8000"`.

**Code Change:**

```javascript
// Before
const API_URL = 'http://localhost:8000';

// After
const API_URL = process.env.API_URL || 'http://localhost:8000';
```

---

## Fix 16: Hardcoded port in frontend

**File:** `frontend/app.js`
**Line:** 29

**Problem:**
`app.listen(3000)` hardcoded the port. Should be configurable via environment variable.

**Fix:**
Use `process.env.PORT || 5000`.

**Code Change:**

```javascript
// Before
app.listen(3000, () => { ... });

// After
const PORT = process.env.PORT || 5000;
app.listen(PORT, () => { ... });
```

---

## Fix 17: No health check endpoint in frontend

**File:** `frontend/app.js`

**Problem:**
No `/health` route existed for Docker HEALTHCHECK.

**Fix:**
Added `app.get('/health', ...)` endpoint.

**Code Change:**

```javascript
// Added
app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});
```

---

## Fix 18: No error handling in frontend HTML fetch calls

**File:** `frontend/views/index.html`
**Line:** 24-28, 32-37

**Problem:**
`fetch('/submit')` and `fetch('/status/{id}')` had no error handling. Network failures or server errors would cause undefined behavior in the UI.

**Fix:**
Added try/catch blocks and `res.ok` checks in both `submitJob()` and `pollJob()` functions.

---

## Fix 19: `.env` file committed with real password

**File:** `api/.env`

**Problem:**
`api/.env` containing `REDIS_PASSWORD=supersecretpassword123` was committed to the repository. The task explicitly states: "`.env` must never appear in your repository or git history. This will cost you heavily."

**Fix:**

1. Removed `api/.env` from git tracking with `git rm --cached api/.env`
2. Added `.env` to `.gitignore`
3. Scrubbed git history using BFG Repo Cleaner: `bfg --delete-files .env`
4. Created `.env.example` with placeholder values only
