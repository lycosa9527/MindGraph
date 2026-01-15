#!/usr/bin/env python3
"""
MindGraph Uvicorn Server Launcher
==================================

Async server launcher using Uvicorn for FastAPI application.
Works on both Windows 11 (development) and Ubuntu (production).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import sys
import asyncio
import subprocess
import atexit

# CRITICAL: Set Windows event loop policy BEFORE any other imports or event loop creation
# Playwright requires WindowsProactorEventLoopPolicy for subprocess support
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Verify it was set correctly
    policy = asyncio.get_event_loop_policy()
    print(f"[run_server] Windows event loop policy set: {type(policy).__name__}")

import signal
import logging
import importlib.util
import multiprocessing

# Suppress multiprocessing errors during shutdown on Windows
import warnings
warnings.filterwarnings('ignore', category=RuntimeWarning, module='multiprocessing')

# Configure logging early to catch uvicorn startup messages
# Set to DEBUG for full verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

class ShutdownErrorFilter:
    """Filter stderr to suppress expected shutdown errors"""
    
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        self.buffer = ""
        self.in_traceback = False
        self.suppress_current = False
        
    def write(self, text):
        """Filter text and only write non-shutdown errors"""
        self.buffer += text
        
        # Check for start of traceback
        if 'Process SpawnProcess' in text or 'Traceback (most recent call last)' in text:
            self.in_traceback = True
            self.suppress_current = False
            
        # Check if this traceback is a CancelledError or Windows Proactor error
        if self.in_traceback:
            if 'asyncio.exceptions.CancelledError' in self.buffer:
                self.suppress_current = True
            # Suppress Windows Proactor pipe transport errors (harmless cleanup errors)
            if '_ProactorBasePipeTransport._call_connection_lost' in self.buffer:
                self.suppress_current = True
            if 'Exception in callback _ProactorBasePipeTransport' in self.buffer:
                self.suppress_current = True
        
        # If we hit a blank line or new process line, decide whether to flush
        if text.strip() == '' or text.startswith('Process '):
            if self.in_traceback and not self.suppress_current:
                # This was a real error, write it
                self.original_stderr.write(self.buffer)
            # Reset state
            if text.strip() == '':
                self.buffer = ""
                self.in_traceback = False
                self.suppress_current = False
        elif not self.in_traceback:
            # Not in a traceback, write immediately
            self.original_stderr.write(text)
            self.buffer = ""
    
    def flush(self):
        """Flush the original stderr"""
        if not self.suppress_current and self.buffer and not self.in_traceback:
            self.original_stderr.write(self.buffer)
        self.original_stderr.flush()
        self.buffer = ""
    
    def __getattr__(self, name):
        """Delegate all other attributes to original stderr"""
        return getattr(self.original_stderr, name)

def check_package_installed(package_name):
    """Check if a package is installed"""
    spec = importlib.util.find_spec(package_name)
    return spec is not None


# Global reference to Celery worker process
_celery_worker_process = None


def start_celery_worker():
    """Start Celery worker as a subprocess"""
    global _celery_worker_process
    
    if not check_package_installed('celery'):
        print("[WARNING] Celery not installed. Document processing will not work.")
        print("          Install with: pip install celery redis")
        return None
    
    # Check if Redis is available
    try:
        import redis
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', '6379'))
        r = redis.Redis(host=redis_host, port=redis_port, socket_connect_timeout=2)
        r.ping()
    except Exception as e:
        print(f"[WARNING] Redis not available ({e}). Celery worker will not start.")
        print("          Make sure Redis is running on localhost:6379")
        return None
    
    # Check if Qdrant is in server mode (required for multi-process)
    qdrant_host = os.getenv('QDRANT_HOST', '')
    qdrant_url = os.getenv('QDRANT_URL', '')
    
    if not qdrant_host and not qdrant_url:
        print("[WARNING] Qdrant server not configured (QDRANT_HOST not set).")
        print("          Celery worker requires Qdrant server for concurrent access.")
        print("          Setup instructions: docs/QDRANT_SETUP.md")
        print("          Quick start: See docs/QDRANT_SETUP.md for Qdrant installation")
        print("          Then add QDRANT_HOST=localhost:6333 to .env")
        return None
    
    # Start Celery worker
    print("[CELERY] Starting Celery worker for background task processing...")
    
    # Determine Python executable
    python_exe = sys.executable
    
    # Build celery command with DEBUG logging
    celery_cmd = [
        python_exe, '-m', 'celery',
        '-A', 'config.celery',
        'worker',
        '--loglevel=debug',  # DEBUG for full verbose logging
        '--concurrency=2',
        '-Q', 'default,knowledge',  # Listen to both queues
    ]
    
    # Add Windows-specific flags
    if sys.platform == 'win32':
        celery_cmd.extend(['--pool=solo'])  # Windows doesn't support prefork
    
    try:
        # Start worker process with console output for logging
        # Use None for stdout/stderr to show logs in console
        # Start Celery worker with logs going to console
        # Use PIPE and redirect to stdout/stderr so we see all logs
        _celery_worker_process = subprocess.Popen(
            celery_cmd,
            stdout=sys.stdout,  # Direct output to console
            stderr=sys.stderr,  # Direct errors to console
            cwd=os.path.dirname(os.path.abspath(__file__)),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
            bufsize=1,  # Line buffered for real-time output
        )
        
        # Register cleanup on exit
        atexit.register(stop_celery_worker)
        
        print(f"[CELERY] Worker started (PID: {_celery_worker_process.pid})")
        return _celery_worker_process
        
    except Exception as e:
        print(f"[ERROR] Failed to start Celery worker: {e}")
        return None


def stop_celery_worker():
    """Stop the Celery worker subprocess"""
    global _celery_worker_process
    
    if _celery_worker_process is not None:
        print("[CELERY] Stopping Celery worker...")
        try:
            if sys.platform == 'win32':
                _celery_worker_process.terminate()
            else:
                import signal
                os.killpg(os.getpgid(_celery_worker_process.pid), signal.SIGTERM)
            _celery_worker_process.wait(timeout=5)
        except Exception as e:
            print(f"[CELERY] Error stopping worker: {e}")
            try:
                _celery_worker_process.kill()
            except:
                pass
        _celery_worker_process = None
        print("[CELERY] Worker stopped")

def run_uvicorn():
    """Run MindGraph with Uvicorn (FastAPI async server)"""
    if not check_package_installed('uvicorn'):
        print("[ERROR] Uvicorn not installed. Install with: pip install uvicorn[standard]>=0.24.0")
        sys.exit(1)
    
    # Setup signal handlers for graceful shutdown (Linux/macOS)
    # This ensures SIGTERM kills all worker processes, not just the main process
    _shutdown_in_progress = False
    
    if sys.platform != 'win32':
        def signal_handler(signum, _frame):
            """Handle SIGTERM/SIGINT by killing entire process group"""
            global _shutdown_in_progress
            
            # Prevent infinite loop - only handle shutdown once
            if _shutdown_in_progress:
                return
            
            _shutdown_in_progress = True
            sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
            print(f"\n[SHUTDOWN] Received {sig_name}, stopping all workers...")
            
            # Stop Celery worker first
            stop_celery_worker()
            
            # Kill entire process group (includes all uvicorn workers)
            try:
                pgid = os.getpgid(os.getpid())
                # Use SIGKILL to avoid recursive signal handling
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # Process group already dead
            except Exception as e:
                print(f"[SHUTDOWN] Error killing process group: {e}")
            
            sys.exit(0)
        
        # Become process group leader (allows killing all children)
        try:
            os.setpgrp()
        except OSError:
            pass  # Already a process group leader
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
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
        debug = config.DEBUG
        log_level = config.LOG_LEVEL.lower()
        
        # Derive environment and reload from DEBUG setting
        environment = 'development' if debug else 'production'
        reload = debug
        
        # For async servers: 1-2 workers per CPU core (NOT 2x+1 like sync servers!)
        # Each worker can handle 1000s of concurrent connections via async event loop
        # Allow override via UVICORN_WORKERS env var for fine-tuning
        # NOTE: Use single worker on Windows due to Playwright multi-process compatibility issues
        default_workers = 1 if sys.platform == 'win32' else min(multiprocessing.cpu_count(), 4)
        workers = int(os.getenv('UVICORN_WORKERS', default_workers))
        
        # Display fancy ASCII art banner
        print()
        print("    ███╗   ███╗██╗███╗   ██╗██████╗  ██████╗ ██████╗  █████╗ ██████╗ ██╗  ██╗")
        print("    ████╗ ████║██║████╗  ██║██╔══██╗██╔════╝ ██╔══██╗██╔══██╗██╔══██╗██║  ██║")
        print("    ██╔████╔██║██║██╔██╗ ██║██║  ██║██║  ███╗██████╔╝███████║██████╔╝███████║")
        print("    ██║╚██╔╝██║██║██║╚██╗██║██║  ██║██║   ██║██╔══██╗██╔══██║██╔═══╝ ██╔══██║")
        print("    ██║ ╚═╝ ██║██║██║ ╚████║██████╔╝╚██████╔╝██║  ██║██║  ██║██║     ██║  ██║")
        print("    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝")
        print("=" * 80)
        print("    AI-Powered Visual Thinking Tools for K12 Education")
        print(f"    Version {config.VERSION} | 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)")
        print("=" * 80)
        print()
        print(f"Environment: {environment} (DEBUG={debug})")
        print(f"Host: {host}")
        print(f"Port: {port}")
        print(f"Workers: {workers}")
        print(f"Log Level: {log_level.upper()}")
        print(f"Auto-reload: {reload}")
        print(f"Expected Capacity: 4,000+ concurrent SSE connections")
        print("=" * 80)
        print(f"Server ready at: http://localhost:{port}")
        print(f"API Docs: http://localhost:{port}/docs")
        print()
        print("Frontend (Vue SPA):")
        print(f"  Development: Run 'npm run dev' in frontend/ → http://localhost:3000")
        print(f"  Production:  Run 'npm run build' in frontend/ → http://localhost:{port}")
        print("=" * 80)
        print(f"Press Ctrl+C to stop the server")
        print()
        
        # Print configuration summary (same as main.py)
        config.print_config_summary()
        
        # Start Celery worker for background task processing
        celery_worker = start_celery_worker()
        if celery_worker:
            print("[CELERY] Background task processing enabled")
        else:
            print("[WARNING] Background task processing disabled - check Redis connection")
        print()
        
        # Install stderr filter to suppress multiprocessing shutdown tracebacks
        original_stderr = sys.stderr
        sys.stderr = ShutdownErrorFilter(original_stderr)
        
        # Install custom exception hook to suppress shutdown errors
        original_excepthook = sys.excepthook
        
        def custom_excepthook(exc_type, exc_value, exc_traceback):
            """Custom exception hook to suppress expected shutdown errors"""
            import asyncio
            # Suppress CancelledError during shutdown
            if exc_type == asyncio.CancelledError:
                return
            # Suppress BrokenPipeError and ConnectionResetError during shutdown
            if exc_type in (BrokenPipeError, ConnectionResetError):
                return
            # Call original handler for other exceptions
            original_excepthook(exc_type, exc_value, exc_traceback)
        
        sys.excepthook = custom_excepthook
        
        try:
            # Load custom uvicorn logging config for consistent formatting
            from uvicorn_config import LOGGING_CONFIG
            
            # Run uvicorn with proper shutdown configuration
            uvicorn.run(
                "main:app",
                host=host,
                port=port,
                workers=1 if reload else workers,  # Use 1 worker in dev mode for reload
                reload=reload,
                log_level=log_level,
                log_config=LOGGING_CONFIG,  # Use our unified formatter
                use_colors=False,  # Disable uvicorn colors (we use our own)
                timeout_keep_alive=300,  # 5 minutes for SSE
                timeout_graceful_shutdown=5,  # 5s for graceful shutdown
                access_log=False,  # Disable HTTP request logging (reduces noise)
                limit_concurrency=1000 if not reload else None,
            )
        except OSError as e:
            # Handle port binding errors
            if e.errno == 98 or "Address already in use" in str(e) or "address is already in use" in str(e).lower():
                print(f"\n[ERROR] Port {port} is already in use!")
                print(f"        Another process is using port {port}.")
                print("\n        Solutions:")
                print(f"        1. Stop the process using port {port}:")
                if sys.platform == 'win32':
                    print(f"           netstat -ano | findstr :{port}")
                    print(f"           taskkill /PID <PID> /F")
                else:
                    print(f"           lsof -ti:{port} | xargs kill -9")
                    print(f"           or: sudo fuser -k {port}/tcp")
                print(f"        2. Use a different port:")
                print(f"           Set PORT=<different_port> in .env")
                print(f"           Example: PORT=9528")
                print(f"        3. Check if another MindGraph instance is running")
                sys.exit(1)
            else:
                # Re-raise other OSErrors
                raise
        except KeyboardInterrupt:
            # Graceful shutdown on Ctrl+C
            print("\n" + "=" * 80)
            print("Shutting down gracefully...")
            stop_celery_worker()
            print("=" * 80)
        finally:
            # Restore original stderr and exception hook
            sys.stderr = original_stderr
            sys.excepthook = original_excepthook
            # Ensure Celery worker is stopped
            stop_celery_worker()
            
    except KeyboardInterrupt:
        # Handle Ctrl+C during startup
        print("\n" + "=" * 80)
        print("Startup interrupted by user")
        print("=" * 80)
        sys.exit(0)
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
