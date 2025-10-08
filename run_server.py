#!/usr/bin/env python3
"""
MindGraph Uvicorn Server Launcher
==================================

Async server launcher using Uvicorn for FastAPI application.
Works on both Windows 11 (development) and Ubuntu (production).

@author lycosa9527
@made_by MindSpring Team

Migration Status: Phase 5 - Uvicorn Server Runner
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
        
        # Get configuration from environment
        host = os.getenv('HOST', '0.0.0.0')
        port = int(os.getenv('PORT', '5000'))
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

def run_flask_legacy():
    """Legacy: Run Flask + Waitress (deprecated)"""
    print("[WARNING] Flask + Waitress is deprecated. FastAPI + Uvicorn is now the default.")
    print("[WARNING] This mode is only for temporary fallback during migration.")
    print()
    
    if not check_package_installed('waitress'):
        print("[ERROR] Waitress not installed. Install with: pip install waitress>=3.0.0")
        print("[INFO] Or use the new FastAPI server by removing MINDGRAPH_SERVER=flask")
        sys.exit(1)
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        os.makedirs("logs", exist_ok=True)
        
        from waitress import serve
        from app import app, print_banner
        
        # Load configuration
        config_module = {}
        with open('waitress.conf.py', 'r') as f:
            exec(f.read(), config_module)
        
        display_host = "localhost" if config_module['host'] == '0.0.0.0' else config_module['host']
        print_banner(display_host, config_module['port'])
        print(f"Press Ctrl+C to stop the server")
        
        serve(
            app, 
            host=config_module['host'], 
            port=config_module['port'],
            threads=config_module['threads'],
            cleanup_interval=config_module['cleanup_interval'],
            channel_timeout=config_module['channel_timeout'],
            send_bytes=config_module['send_bytes'],
            recv_bytes=config_module['recv_bytes']
        )
    except Exception as e:
        print(f"[ERROR] Failed to start Flask + Waitress: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """Main entry point"""
    # Check if legacy mode is requested
    force_server = os.getenv('MINDGRAPH_SERVER', '').lower()
    
    if force_server == 'flask':
        run_flask_legacy()
    else:
        # Default to FastAPI + Uvicorn
        run_uvicorn()

if __name__ == '__main__':
    main()
