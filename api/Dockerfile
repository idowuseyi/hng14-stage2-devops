# Stage 1: Builder - install dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime - minimal image
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies only
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd -r app && useradd -r -g app -s /sbin/nologin app

# Copy application code
COPY . .
RUN chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
