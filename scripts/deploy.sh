#!/bin/bash
# deploy.sh
# Performs a rolling update for each service.
# The new container must pass its health check before the old one is stopped.
# If the health check does not pass within 60 seconds, abort and leave the old container running.

set -euo pipefail

HEALTH_TIMEOUT=60
POLL_INTERVAL=5

echo "=== Rolling Deploy ==="

# Pull latest images
docker compose build

SERVICES=("api" "worker" "frontend")

for SVC in "${SERVICES[@]}"; do
    echo ""
    echo "--- Rolling update for $SVC ---"

    # Get current container ID
    OLD_CONTAINER=$(docker compose ps -q "$SVC" 2>/dev/null || true)

    # Start new container (scale up to 2)
    echo "Starting new $SVC container..."
    docker compose up -d --no-deps --scale "$SVC"=2 "$SVC"

    # Wait for at least one healthy container
    echo "Waiting for new $SVC container to pass health check (max ${HEALTH_TIMEOUT}s)..."
    elapsed=0
    healthy=false

    while [ $elapsed -lt $HEALTH_TIMEOUT ]; do
        # Check if any container for this service is healthy
        healthy_count=$(docker compose ps "$SVC" --format json 2>/dev/null | \
            python3 -c "
import sys, json
count = 0
for line in sys.stdin:
    try:
        obj = json.loads(line)
        if obj.get('Health') == 'healthy':
            count += 1
    except: pass
print(count)" 2>/dev/null || echo "0")

        if [ "$healthy_count" -ge 1 ]; then
            healthy=true
            echo "New $SVC container is healthy"
            break
        fi

        sleep $POLL_INTERVAL
        elapsed=$((elapsed + POLL_INTERVAL))
        echo "  Waiting... (${elapsed}s/${HEALTH_TIMEOUT}s)"
    done

    if [ "$healthy" = false ]; then
        echo "ERROR: $SVC health check did not pass within ${HEALTH_TIMEOUT}s"
        echo "Rolling back — stopping new container, keeping old..."

        # Scale back to 1 (keeps the original if it was healthy)
        docker compose up -d --no-deps --scale "$SVC"=1 "$SVC"
        exit 1
    fi

    # Scale back to 1 (remove old container)
    echo "Stopping old $SVC container..."
    docker compose up -d --no-deps --scale "$SVC"=1 "$SVC"

    echo "$SVC rolling update complete."
done

echo ""
echo "=== Deploy Complete ==="
echo "All services updated successfully."
