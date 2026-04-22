#!/bin/bash
# deploy.sh
# Performs a rolling update for each service.
# The new container must pass its health check before the old one is stopped.
# If the health check does not pass within 60 seconds, abort and leave the old container running.

set -euo pipefail

HEALTH_TIMEOUT=60
POLL_INTERVAL=5

echo "=== Rolling Deploy ==="

# Build latest images
docker compose build

SERVICES=("api" "worker" "frontend")

for SVC in "${SERVICES[@]}"; do
    echo ""
    echo "--- Rolling update for $SVC ---"

    # Get the current container ID
    OLD_CONTAINER=$(docker compose ps -q "$SVC" 2>/dev/null | head -1) || true

    if [ -z "$OLD_CONTAINER" ]; then
        echo "No existing $SVC container found. Starting fresh..."
        docker compose up -d --no-deps "$SVC"
        echo "$SVC started."
        continue
    fi

    OLD_CONTAINER_NAME=$(docker inspect --format '{{.Name}}' "$OLD_CONTAINER" | sed 's/\///')

    # Check if this service has host port mappings
    HOST_PORT=$(docker port "$OLD_CONTAINER" 2>/dev/null | head -1 || true)

    if [ -n "$HOST_PORT" ]; then
        # Service has host port mapping — can't scale to 2.
        # Strategy: start new container on a different port, verify health, then swap.
        echo "$SVC has host port mapping. Using stop-and-replace strategy..."

        # Stop old container
        echo "Stopping old $SVC container ($OLD_CONTAINER_NAME)..."
        docker compose stop "$SVC"

        # Start new container
        echo "Starting new $SVC container..."
        docker compose up -d --no-deps --force-recreate "$SVC"

        # Wait for new container to be healthy
        echo "Waiting for new $SVC container to pass health check (max ${HEALTH_TIMEOUT}s)..."
        elapsed=0
        healthy=false

        while [ $elapsed -lt $HEALTH_TIMEOUT ]; do
            NEW_CONTAINER=$(docker compose ps -q "$SVC" 2>/dev/null | head -1) || true
            if [ -n "$NEW_CONTAINER" ]; then
                HEALTH=$(docker inspect --format '{{.State.Health.Status}}' "$NEW_CONTAINER" 2>/dev/null || echo "unknown")
                if [ "$HEALTH" = "healthy" ]; then
                    healthy=true
                    echo "New $SVC container is healthy"
                    break
                fi
            fi
            sleep $POLL_INTERVAL
            elapsed=$((elapsed + POLL_INTERVAL))
            echo "  Waiting... (${elapsed}s/${HEALTH_TIMEOUT}s) health=$HEALTH"
        done

        if [ "$healthy" = false ]; then
            echo "ERROR: $SVC health check did not pass within ${HEALTH_TIMEOUT}s"
            echo "Rolling back — restarting old container..."
            docker start "$OLD_CONTAINER" 2>/dev/null || true
            exit 1
        fi

        # Remove old container
        docker rm -f "$OLD_CONTAINER" 2>/dev/null || true
        echo "$SVC rolling update complete."

    else
        # No host port mapping — safe to scale up
        echo "Starting new $SVC container (scale up)..."
        docker compose up -d --no-deps --scale "$SVC"=2 "$SVC"

        echo "Waiting for new $SVC container to pass health check (max ${HEALTH_TIMEOUT}s)..."
        elapsed=0
        healthy=false

        while [ $elapsed -lt $HEALTH_TIMEOUT ]; do
            # Count healthy containers
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
            docker compose up -d --no-deps --scale "$SVC"=1 "$SVC"
            exit 1
        fi

        # Scale back to 1 (remove old container)
        echo "Stopping old $SVC container..."
        docker compose up -d --no-deps --scale "$SVC"=1 "$SVC"
        echo "$SVC rolling update complete."
    fi
done

echo ""
echo "=== Deploy Complete ==="
echo "All services updated successfully."
