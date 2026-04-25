# =============================================================================
# GitHub Discovery — Multi-stage Production Dockerfile
# =============================================================================
# Supports three runtime modes:
#   MCP stdio (default):  docker run -i github-discovery/mcp-server
#   API server:           docker run github-discovery/mcp-server api
#   Worker:               docker run github-discovery/mcp-server worker
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder — compile wheel from source
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Build dependencies (kept separate for layer caching)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install build backend first (layer cache for dependency resolution)
COPY pyproject.toml ./
# Hatchling needs to see the package directory to compute version,
# but we only need metadata at this point — copy a minimal stub.
COPY src/ src/

# Build the wheel
RUN pip install --no-cache-dir --upgrade pip build \
    && python -m build --wheel --no-isolation 2>/dev/null \
    && ls -lh dist/

# ---------------------------------------------------------------------------
# Stage 2: Runtime — lean production image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="GitHub Discovery"
LABEL org.opencontainers.image.description="MCP-native agentic discovery engine for high-quality GitHub repositories"
LABEL org.opencontainers.image.version="0.1.0-alpha"
LABEL org.opencontainers.image.source="https://github.com/user/github-discovery"
LABEL org.opencontainers.image.vendor="GitHub Discovery Team"

# Security: run as non-root user
RUN groupadd --gid 1000 ghdisc \
    && useradd --uid 1000 --gid ghdisc --create-home ghdisc

# Persistent data directory (SQLite sessions, feature store, job store)
RUN mkdir -p /home/ghdisc/.ghdisc \
    && chown -R ghdisc:ghdisc /home/ghdisc/.ghdisc
VOLUME ["/home/ghdisc/.ghdisc"]

WORKDIR /home/ghdisc

# Copy wheel from builder and install (no dev deps)
COPY --from=builder /build/dist/github_discovery-*.whl /tmp/

RUN pip install --no-cache-dir /tmp/github_discovery-*.whl \
    && rm -f /tmp/github_discovery-*.whl \
    && find /usr/local -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

# Default environment (can be overridden at runtime)
ENV GHDISC_GITHUB_TOKEN="" \
    GHDISC_API_HOST=0.0.0.0 \
    GHDISC_API_PORT=8000 \
    GHDISC_MCP_SESSION_STORE_PATH=/home/ghdisc/.ghdisc/sessions.db \
    GHDISC_API_JOB_STORE_PATH=/home/ghdisc/.ghdisc/jobs.db \
    GHDISC_LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Entrypoint dispatch script
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

USER ghdisc

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["mcp"]
