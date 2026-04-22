# Task

## Overview

As a DevOps engineer, you will rarely be writing the application, but you will always be responsible for how it runs, how it gets there, and whether it survives a restart. This task puts that responsibility squarely on you.

The application is provided for you. It has bugs. Finding them is part of the task.

### The Application

You are given a job processing system made up of three services:

- A frontend (Node.js) where users submit and track jobs
- An API (Python/FastAPI) that creates jobs and serves status updates
- A worker (Python) that picks up and processes jobs from a queue

A Redis instance shared between the API and worker.
The source code is intentionally shipped with bugs — misconfigurations, bad practices, and missing production requirements are present throughout. You are not told where they are or how many there are. Finding them, fixing them, and documenting every single one is a graded part of this assessment.

**Starter repo:** https://github.com/chukwukelu2023/hng14-stage2-devops

Fork it. Do all your work in your fork.

## What You Must Do

**1. Fix the Application:** Read through all the source files carefully before touching any infrastructure. Some things will not work correctly as written. Others will appear to work locally but fail inside containers. Document every issue you find in a `FIXES.md` file — state the file, the line, what the problem was, and what you changed. Vague entries will not receive marks.

**2. Containerize It:** Write a production-quality `Dockerfile` for each of the three services:

- Use multi-stage builds where appropriate — your final image should not contain build tools or dev dependencies
- All services must run as a non-root user
- Each Dockerfile must include a working `HEALTHCHECK` instruction
- No secrets, .env files, or credentials may be copied into any image

Write a `docker-compose.yml` that brings the full stack up:

- All services must communicate over a named internal network
- Redis must not be exposed on the host machine
- Services must only start after their dependencies are confirmed healthy — not just started
- All configuration must come from environment variables, nothing hardcoded in the Compose file
- Include CPU and memory limits for every service

**3. Build the Pipeline:** Implement a CI/CD pipeline using **GitHub Actions** on `ubuntu-latest` (free tier — no self-hosted runners, no paid services). Your pipeline must run the following stages in strict order:

`lint → test → build → security scan → integration test → deploy`

- **Lint:** Python (`flake8`), JavaScript (`eslint`), and all Dockerfiles (`hadolint`)
- **Test:** At least 3 unit tests for the API using `pytest`, with Redis mocked. Generate and upload a coverage report as a pipeline artifact
- **Build:** Build all three images, tag each with the git SHA and `latest`, push to a local Docker registry running as a service container within the job
- **Security scan:** Scan all images with Trivy, fail the pipeline on any `CRITICAL` severity finding, upload results as a SARIF artifact
- **Integration test:** Bring the full stack up inside the runner, submit a job through the frontend, poll until it completes, assert the final status is correct, tear the stack down cleanly regardless of outcome
- **Deploy:** Runs on pushes to `main` only. Must perform a scripted rolling update — the new container must pass its health check before the old one is stopped. If the health check does not pass within 60 seconds, abort and leave the old container running

A failure in any stage must prevent all subsequent stages from running.

**4. Document It**

- A `README.md` that explains how to bring the entire stack up on a clean machine from scratch — list prerequisites, all commands, and what a successful startup looks like
- A `FIXES.md` documenting every bug found — file, line number, what it was, and how you fixed it
- A `.env.example` committed with placeholder values for every required variable

### Rules

- Your fork must be public. Private repositories will not be graded
- Everything must be committed — nothing should only exist locally
- `.env` must never appear in your repository or git history. This will cost you heavily
- Do not hardcode secrets, passwords, or tokens anywhere — YAML files, Python, JavaScript, or git history all count
- No cloud accounts required. This task runs entirely on your machine a️nd GitHub’s free tier
- Do not open a pull request to the starter repo
