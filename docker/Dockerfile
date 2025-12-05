# MindGraph - Optimized Docker Build
# Multi-stage build with aggressive size optimization
# Version: 4.0.0 (FastAPI + Uvicorn)

# ============================================================================
# STAGE 1: Base Python Environment (Minimal)
# ============================================================================
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install only essential system dependencies
RUN apt-get update && apt-get install -y \
    # Minimal build tools
    gcc \
    g++ \
    make \
    # Node.js for D3.js
    curl \
    # System utilities
    procps \
    # Clean up immediately
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y \
    && apt-get autoclean

# Install Node.js (minimal)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# ============================================================================
# STAGE 2: Python Dependencies
# ============================================================================
FROM base AS python-deps

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with optimization
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================================
# STAGE 3: Playwright Dependencies (Minimal)
# ============================================================================
FROM python-deps AS playwright-deps

# Install only essential Playwright dependencies
RUN playwright install-deps chromium

# Install Chromium browser only
RUN playwright install chromium

# Aggressive cleanup
RUN rm -rf /root/.cache \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/* \
    && rm -rf /var/cache/apt \
    && apt-get clean \
    && apt-get autoremove -y \
    && apt-get autoclean

# ============================================================================
# STAGE 4: Final Application (Minimal)
# ============================================================================
FROM playwright-deps AS app

# Create non-root user
RUN groupadd -r mindgraph && useradd -r -g mindgraph mindgraph

# Copy only essential application files (FastAPI structure)
COPY --chown=mindgraph:mindgraph main.py run_server.py uvicorn_config.py LICENSE ./
COPY --chown=mindgraph:mindgraph scripts/setup.py ./scripts/
COPY --chown=mindgraph:mindgraph agents/ ./agents/
COPY --chown=mindgraph:mindgraph prompts/ ./prompts/
COPY --chown=mindgraph:mindgraph static/ ./static/
COPY --chown=mindgraph:mindgraph templates/ ./templates/
COPY --chown=mindgraph:mindgraph test/ ./test/
COPY --chown=mindgraph:mindgraph routers/ ./routers/
COPY --chown=mindgraph:mindgraph models/ ./models/
COPY --chown=mindgraph:mindgraph clients/ ./clients/
COPY --chown=mindgraph:mindgraph services/ ./services/
COPY --chown=mindgraph:mindgraph config/ ./config/

# Create minimal directories and files
RUN mkdir -p logs static/images test/images \
    && touch logs/app.log logs/agent.log \
    && chown -R mindgraph:mindgraph logs static/images test/images

# Copy entrypoint script
COPY --chown=mindgraph:mindgraph docker/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Switch to non-root user
USER mindgraph

# Expose port
EXPOSE 9527

# Health check (using Python instead of curl for reliability)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9527/health')" || exit 1

# Environment variables
ENV PORT=9527 \
    MINDGRAPH_ENV=production

# Final cleanup
RUN rm -rf /tmp/* \
    && rm -rf /var/tmp/* \
    && find /usr/local -name "*.pyc" -delete \
    && find /usr/local -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Use entrypoint script
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command
CMD ["python", "run_server.py"]
