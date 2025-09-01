# Waitress Configuration for MindGraph
# Waitress is a pure-Python WSGI server that works on all platforms
# This provides better performance than Flask development server

import os

# Basic Configuration
host = '0.0.0.0'
port = int(os.getenv('PORT', 9527))  # Use MindGraph default port

# Connection settings
listen = f"{host}:{port}"
threads = 6  # Increased for better concurrency (was 4)

# Timeouts
cleanup_interval = 30
channel_timeout = 120

# Logging
access_log = True
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Performance settings
send_bytes = 8192
recv_bytes = 65536
# map_async is not a valid Waitress setting - removed

# Environment
os.environ['MINDGRAPH_ENV'] = 'production'

# Configuration loaded silently
