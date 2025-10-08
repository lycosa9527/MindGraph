#!/usr/bin/env python3
"""
MindGraph Uvicorn Server Launcher
==================================

Async server launcher using Uvicorn for FastAPI application.
Works on both Windows 11 (development) and Ubuntu (production).

@author lycosa9527
@made_by MindSpring Team
"""

import os
import sys
import importlib.util
import multiprocessing

def check_package_installed(package_name):
    """Check if a package is installed"""
    spec = importlib.util.find_spec(package_name)
    return spec is not None

def run_uvicorn():
    """Run MindGraph with Uvicorn (FastAPI async server)"""
    if not check_package_installed('uvicorn'):
        print("[ERROR] Uvicorn not installed. Install with: pip install uvicorn[standard]>=0.24.0")
        sys.exit(1)
    
    try:
        # Ensure we're in the correct directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)
        
        # Load uvicorn config
        import uvicorn
        from config.settings import config
        
        # Get configuration from centralized settings
        host = config.HOST
        port = config.PORT
        # For async servers: 1-2 workers per CPU core (NOT 2x+1 like sync servers!)
        # Each worker can handle 1000s of concurrent connections via async event loop
        workers = int(os.getenv('UVICORN_WORKERS', min(multiprocessing.cpu_count(), 4)))
        log_level = os.getenv('LOG_LEVEL', 'info').lower()
        environment = os.getenv('ENVIRONMENT', 'production')
        reload = environment == 'development'
        
        # Display banner
        print("=" * 80)
        print("MindGraph FastAPI Server Starting...")
        print("=" * 80)
        print(f"Environment: {environment}")
        print(f"Host: {host}")
        print(f"Port: {port}")
        print(f"Workers: {workers}")
        print(f"Log Level: {log_level}")
        print(f"Auto-reload: {reload}")
        print(f"Expected Capacity: 4,000+ concurrent SSE connections")
        print("=" * 80)
        print(f"Server ready at: http://localhost:{port}")
        print(f"Interactive Editor: http://localhost:{port}/editor")
        print(f"API Docs: http://localhost:{port}/docs")
        print("=" * 80)
        print(f"Press Ctrl+C to stop the server")
        print()
        
        # Run uvicorn
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            workers=1 if reload else workers,  # Use 1 worker in dev mode for reload
            reload=reload,
            log_level=log_level,
            timeout_keep_alive=300,  # 5 minutes for SSE
            timeout_graceful_shutdown=10,  # Reduced from 30s to 10s for faster shutdown
            access_log=True,
            use_colors=True,
            # Limit worker connections to prevent hanging on shutdown
            limit_concurrency=1000 if not reload else None
        )
    except Exception as e:
        print(f"[ERROR] Failed to start Uvicorn: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """Main entry point"""
    run_uvicorn()

if __name__ == '__main__':
    main()
