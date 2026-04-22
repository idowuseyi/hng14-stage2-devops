#!/bin/bash
# integration-test.sh
# Brings up the full stack, submits a job, polls until complete, and asserts the result.
# Tears down regardless of outcome.

set -euo pipefail

FRONTEND_PORT="${FRONTEND_PORT:-5000}"
API_PORT="${API_PORT:-8000}"
MAX_WAIT=60
POLL_INTERVAL=2

echo "=== Integration Test ==="

# Step 1: Create .env file for docker-compose
cat > .env <<EOF
REDIS_PASSWORD=${REDIS_PASSWORD:?REDIS_PASSWORD is required}
FRONTEND_PORT=${FRONTEND_PORT}
EOF

# Step 2: Start the stack
echo "Starting docker-compose stack..."
docker compose up -d --build --wait

# Ensure teardown happens on exit (success or failure)
cleanup() {
    echo "Tearing down docker-compose stack..."
    docker compose down -v --remove-orphans 2>/dev/null || true
    rm -f .env
}
trap cleanup EXIT

# Step 3: Wait for services to be healthy
echo "Waiting for services to be healthy..."
elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    if curl -sf "http://localhost:${FRONTEND_PORT}/health" > /dev/null 2>&1; then
        echo "Frontend is healthy"
        break
    fi
    sleep $POLL_INTERVAL
    elapsed=$((elapsed + POLL_INTERVAL))
done

if [ $elapsed -ge $MAX_WAIT ]; then
    echo "ERROR: Frontend did not become healthy within ${MAX_WAIT}s"
    docker compose logs
    exit 1
fi

# Step 4: Submit a job via the frontend
echo "Submitting job via frontend..."
submit_response=$(curl -sf -X POST "http://localhost:${FRONTEND_PORT}/submit")
if [ -z "$submit_response" ]; then
    echo "ERROR: No response from /submit"
    exit 1
fi

job_id=$(echo "$submit_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
echo "Job submitted: $job_id"

# Step 5: Poll the API until the job completes
echo "Polling job status..."
elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    status_response=$(curl -sf "http://localhost:${FRONTEND_PORT}/status/${job_id}")
    status=$(echo "$status_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))")
    echo "  Job status: $status (${elapsed}s elapsed)"

    if [ "$status" = "completed" ]; then
        echo "=== Integration Test PASSED ==="
        echo "Job $job_id completed successfully"
        exit 0
    fi

    sleep $POLL_INTERVAL
    elapsed=$((elapsed + POLL_INTERVAL))
done

echo "=== Integration Test FAILED ==="
echo "Job $job_id did not complete within ${MAX_WAIT}s (last status: $status)"
exit 1
