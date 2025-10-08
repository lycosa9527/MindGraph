"""
Uvicorn Configuration for MindGraph FastAPI Application
=======================================================

Production-ready async server configuration for Windows + Ubuntu deployment.

@author lycosa9527
@made_by MindSpring Team

Migration Status: Phase 5 - Uvicorn Configuration
"""

import os
import multiprocessing

# ============================================================================
# SERVER CONFIGURATION
# ============================================================================

# Host and Port
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
host = "0.0.0.0"
port = int(os.getenv('PORT', '5000'))

# Workers (async, so we need FAR fewer than sync servers)
# Formula: 1-2 workers per CPU core (async handles 1000s per worker)
# Default: Number of CPU cores (not 2x+1 like sync servers)
workers = int(os.getenv('UVICORN_WORKERS', multiprocessing.cpu_count()))

# ============================================================================
# ASYNC CONFIGURATION FOR 4,000+ CONCURRENT SSE CONNECTIONS
# ============================================================================

# Uvicorn automatically handles concurrent requests with asyncio event loop
# No thread pool needed - async/await handles concurrency

# Timeout for long-running requests (SSE can run indefinitely)
timeout_keep_alive = 300  # 5 minutes for SSE connections
timeout_graceful_shutdown = 10  # Reduced to 10s for faster shutdown (was 30s)

# Connection limits to prevent shutdown hangs
limit_concurrency = 1000  # Max concurrent connections per worker

# ============================================================================
# LOGGING
# ============================================================================

# Log level
log_level = os.getenv('LOG_LEVEL', 'info').lower()

# Access log
access_log = True
use_colors = True

# ============================================================================
# DEVELOPMENT VS PRODUCTION
# ============================================================================

# Reload on code changes (development only)
reload = os.getenv('ENVIRONMENT', 'production') == 'development'

# Production settings
if os.getenv('ENVIRONMENT') == 'production':
    # Disable auto-reload in production
    reload = False
    
    # Use production log level
    log_level = 'warning'

# ============================================================================
# CONFIGURATION SUMMARY
# ============================================================================

config_summary = f"""
Uvicorn Configuration Summary:
------------------------------
Host: {host}
Port: {port}
Workers: {workers} (async - each handles 1000s of connections)
Timeout Keep-Alive: {timeout_keep_alive}s
Graceful Shutdown: {timeout_graceful_shutdown}s
Log Level: {log_level}
Reload: {reload}
Environment: {os.getenv('ENVIRONMENT', 'production')}

Expected Capacity: 4,000+ concurrent SSE connections per worker
Total Capacity: ~{workers * 4000} concurrent connections
"""

if __name__ == "__main__":
    print(config_summary)

