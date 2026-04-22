# Job Processing System — DevOps Stage 2

A containerized job processing system with three services: a Node.js frontend, a Python/FastAPI API, and a Python worker, backed by Redis.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v24+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2+)
- [Git](https://git-scm.com/)

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/hng14-stage2-devops.git
cd hng14-stage2-devops
```

### 2. Create environment file

```bash
cp .env.example .env
```

Edit `.env` and set your own `REDIS_PASSWORD`:

```env
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_secure_password_here
FRONTEND_PORT=5000
API_URL=http://api:8000
WORKER_HEALTH_PORT=9090
```

### 3. Build and start all services

```bash
docker compose up -d --build
```

### 4. Verify all services are healthy

```bash
docker compose ps
```

Expected output:

```
NAME                IMAGE                      STATUS                    PORTS
frontend            frontend-latest            Up (healthy)              0.0.0.0:5000->5000/tcp
api                 api-latest                 Up (healthy)              8000/tcp
worker              worker-latest              Up (healthy)              9090/tcp
redis               redis:7-alpine             Up (healthy)              6379/tcp
```

### 5. Access the application

Open your browser at [http://localhost:5000](http://localhost:5000)

- Click **"Submit New Job"** to create a job
- The job will be queued, processed by the worker, and marked as completed
- The dashboard auto-polls and updates the status

### 6. Check service health

```bash
# Frontend health
curl http://localhost:5000/health
# {"status":"healthy"}

# API health (from inside the network)
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"
# {"status":"healthy"}

# Worker health (from inside the network)
docker compose exec worker python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:9090/health').read().decode())"
# {"status":"healthy"}
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend    │────▶│     API     │────▶│    Redis     │
│  (Node.js)   │     │ (FastAPI)   │     │             │
│  :5000       │     │  :8000      │     │  :6379      │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                     ┌─────────────┐             │
                     │   Worker    │─────────────┘
                     │  (Python)   │
                     │  :9090      │
                     └─────────────┘
```

- **Frontend**: Express.js server serving a web dashboard. Users submit jobs and track status.
- **API**: FastAPI service that creates jobs (pushes to Redis queue) and serves job status.
- **Worker**: Python process that pops jobs from the Redis queue, simulates work, and marks them completed.
- **Redis**: Message broker and data store. Not exposed to the host machine.

All services communicate over a named Docker bridge network (`app-network`).

## Useful Commands

```bash
# Start services
docker compose up -d --build

# View logs
docker compose logs -f

# View logs for a specific service
docker compose logs -f api

# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v

# Restart a single service
docker compose restart api

# Check resource usage
docker stats
```

## CI/CD Pipeline

The GitHub Actions pipeline runs on every push and PR:

```
lint → test → build → security scan → integration test → deploy
```

- **Lint**: flake8 (Python), eslint (JS), hadolint (Dockerfiles)
- **Test**: pytest with mocked Redis (minimum 3 tests, coverage report)
- **Build**: Build all Docker images, tag with git SHA + latest
- **Security**: Trivy scan, fails on CRITICAL vulnerabilities
- **Integration**: Full stack test — submit job, poll until complete, assert status
- **Deploy**: Rolling update on push to main (new container must pass health check within 60s)

## Project Structure

```
.
├── .github/workflows/pipeline.yml   # CI/CD pipeline
├── .env.example                     # Environment variable template
├── .gitignore                       # Git ignore rules
├── docker-compose.yml               # Full stack orchestration
├── FIXES.md                         # Bug documentation
├── README.md                        # This file
├── api/
│   ├── Dockerfile                   # Multi-stage API image
│   ├── main.py                      # FastAPI application
│   ├── requirements.txt             # Python dependencies
│   └── tests/
│       ├── conftest.py              # Pytest fixtures
│       └── test_main.py             # API unit tests
├── frontend/
│   ├── Dockerfile                   # Multi-stage frontend image
│   ├── app.js                       # Express.js application
│   ├── package.json                 # Node dependencies
│   ├── .eslintrc.json               # ESLint configuration
│   └── views/
│       └── index.html               # Web dashboard
├── scripts/
│   ├── deploy.sh                    # Rolling deploy script
│   └── integration-test.sh          # Integration test script
└── worker/
    ├── Dockerfile                   # Multi-stage worker image
    ├── worker.py                    # Python worker
    └── requirements.txt             # Python dependencies
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `redis` | Redis hostname (container name) |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | — | Redis authentication password (required) |
| `FRONTEND_PORT` | `5000` | Host port for frontend |
| `API_URL` | `http://api:8000` | URL for frontend to reach API |
| `WORKER_HEALTH_PORT` | `9090` | Worker health check server port |
