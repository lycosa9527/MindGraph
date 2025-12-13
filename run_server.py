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
import signal
import logging
import importlib.util
import multiprocessing

# Suppress multiprocessing errors during shutdown on Windows
import warnings
warnings.filterwarnings('ignore', category=RuntimeWarning, module='multiprocessing')

# Configure logging early to catch uvicorn startup messages
logging.basicConfig(
    level=logging.INFO,
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

def run_uvicorn():
    """Run MindGraph with Uvicorn (FastAPI async server)"""
    if not check_package_installed('uvicorn'):
        print("[ERROR] Uvicorn not installed. Install with: pip install uvicorn[standard]>=0.24.0")
        sys.exit(1)
    
    # Setup signal handlers for graceful shutdown (Linux/macOS)
    # This ensures SIGTERM kills all worker processes, not just the main process
    if sys.platform != 'win32':
        def signal_handler(signum, frame):
            """Handle SIGTERM/SIGINT by killing entire process group"""
            sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
            print(f"\n[SHUTDOWN] Received {sig_name}, stopping all workers...")
            
            # Kill entire process group (includes all uvicorn workers)
            try:
                os.killpg(os.getpgid(os.getpid()), signal.SIGTERM)
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
        print(f"Interactive Editor: http://localhost:{port}/editor")
        print(f"API Docs: http://localhost:{port}/docs")
        print("=" * 80)
        print(f"Press Ctrl+C to stop the server")
        print()
        
        # Print configuration summary (same as main.py)
        config.print_config_summary()
        
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
        except KeyboardInterrupt:
            # Graceful shutdown on Ctrl+C
            print("\n" + "=" * 80)
            print("Shutting down gracefully...")
            print("=" * 80)
        finally:
            # Restore original stderr and exception hook
            sys.stderr = original_stderr
            sys.excepthook = original_excepthook
            
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
