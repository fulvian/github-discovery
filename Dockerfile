# GitHub Discovery — Multi-stage Docker image
# Stage 1: Build with uv
# Stage 2: Distroless runtime with binaries

# ============================================================
# Stage 1 — Build stage with full Python + uv
# ============================================================
FROM python:3.13-slim AS builder

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set up build environment
WORKDIR /build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for layer caching
COPY pyproject.toml ./
COPY src/ src/

# Install project dependencies and the package itself
RUN uv sync --frozen --no-dev --no-editable

# ============================================================
# Stage 2 — Minimal runtime image
# ============================================================
FROM gcr.io/distroless/python3-debian12:nonroot AS runtime

# Copy installed packages from builder
COPY --from=builder /build/.venv/lib/python3.13/site-packages/ /site-packages/
COPY --from=builder /build/src/ /src/
COPY --from=builder /build/pyproject.toml /pyproject.toml

# Copy system tools needed for screening (git for clone, gitleaks/scc for security)
COPY --from=builder /usr/bin/git /usr/bin/git

# Set Python path to include both site-packages and source
ENV PYTHONPATH=/src:/site-packages \
    GHDISC_SESSION_BACKEND=sqlite \
    GHDISC_MCP_TRANSPORT=stdio

# Default entry point — MCP server over stdio
ENTRYPOINT ["python", "-m", "github_discovery.mcp", "serve", "--transport", "stdio"]
