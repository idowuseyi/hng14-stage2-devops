import os
import time
import signal
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# --- Configuration from environment variables ---
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")
WORKER_HEALTH_PORT = int(os.environ.get("WORKER_HEALTH_PORT", "9090"))

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
)

shutdown_requested = False


def signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global shutdown_requested
    logger.info("Shutdown signal received, finishing current job...")
    shutdown_requested = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# --- Health check HTTP server ---
class HealthHandler(BaseHTTPRequestHandler):
    """Lightweight HTTP server for Docker HEALTHCHECK."""

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"healthy"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default access logs."""
        pass


def start_health_server():
    """Start the health check HTTP server in a background thread."""
    server = HTTPServer(("0.0.0.0", WORKER_HEALTH_PORT), HealthHandler)
    logger.info(f"Health check server listening on port {WORKER_HEALTH_PORT}")
    server.serve_forever()


def process_job(job_id):
    """Simulate job processing and mark as completed."""
    logger.info(f"Processing job {job_id}")
    time.sleep(2)  # simulate work
    try:
        r.hset(f"job:{job_id}", "status", "completed")
        logger.info(f"Done: {job_id}")
    except Exception as e:
        logger.error(f"Failed to update job {job_id}: {e}")


# --- Main worker loop ---
if __name__ == "__main__":
    # Start health server in background daemon thread
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    logger.info("Worker started, waiting for jobs...")

    while not shutdown_requested:
        try:
            job = r.brpop("job:queue", timeout=5)
            if job:
                _, job_id = job
                process_job(job_id)
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error: {e}, retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Error processing job: {e}")
            time.sleep(1)

    logger.info("Worker shut down gracefully.")
