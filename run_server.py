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
import socket
import subprocess
import time

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

def _check_port_available(host: str, port: int):
    """
    Check if a port is available for binding.
    
    Args:
        host: Host address to check
        port: Port number to check
        
    Returns:
        tuple: (is_available: bool, pid_using_port: Optional[int])
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.close()
        return (True, None)
    except OSError as e:
        # Port is in use - try to find the process
        if e.errno in (10048, 98):  # Windows: 10048, Linux: 98 (EADDRINUSE)
            pid = _find_process_on_port(port)
            return (False, pid)
        # Other error - re-raise
        raise

def _find_process_on_port(port: int):
    """
    Find the PID of the process using the specified port.
    Cross-platform implementation.
    
    Args:
        port: Port number to check
        
    Returns:
        Optional[int]: PID of process using the port, or None if not found
    """
    try:
        if sys.platform == 'win32':
            # Windows: use netstat
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        return int(parts[-1])
        else:
            # Linux/Mac: use lsof
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout.strip():
                # lsof can return multiple PIDs, get the first one
                pids = result.stdout.strip().split('\n')
                return int(pids[0]) if pids else None
    except Exception as e:
        print(f"[WARNING] Could not detect process on port {port}: {e}")
    
    return None

def _cleanup_stale_process(pid: int, port: int) -> bool:
    """
    Attempt to gracefully terminate a stale server process.
    
    Args:
        pid: Process ID to terminate
        port: Port number (for logging)
        
    Returns:
        bool: True if cleanup successful, False otherwise
    """
    print(f"[WARNING] Found process {pid} using port {port}")
    print(f"[INFO] Attempting to terminate stale server process...")
    
    try:
        if sys.platform == 'win32':
            # Windows: taskkill
            # First try graceful termination
            subprocess.run(
                ['taskkill', '/PID', str(pid)],
                capture_output=True,
                timeout=3
            )
            time.sleep(1)
            
            # Check if still running
            check_result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if str(pid) in check_result.stdout:
                # Force kill if graceful failed
                print("[INFO] Process still running, forcing termination...")
                subprocess.run(
                    ['taskkill', '/F', '/PID', str(pid)],
                    capture_output=True,
                    timeout=2
                )
        else:
            # Linux/Mac: kill
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # Process already terminated
        
        # Wait for port to be released
        time.sleep(1)
        is_available, _ = _check_port_available('0.0.0.0', port)
        
        if is_available:
            print(f"[INFO] Successfully cleaned up stale process (PID: {pid})")
            return True
        else:
            print(f"[ERROR] Port {port} still in use after cleanup attempt")
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to cleanup process {pid}: {e}")
        return False

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
        debug = config.DEBUG
        log_level = config.LOG_LEVEL.lower()
        
        # Pre-flight port availability check
        # NOTE: This check happens BEFORE uvicorn starts.
        # When uvicorn runs with workers=N, the master process binds to the port
        # and manages worker processes. All workers share the SAME port.
        # This check prevents multiple SEPARATE uvicorn processes from starting.
        print("[INFO] Checking port availability...")
        is_available, pid_using_port = _check_port_available(host, port)
        
        if not is_available:
            print(f"[WARNING] Port {port} is already in use")
            
            if pid_using_port:
                print(f"[WARNING] Process {pid_using_port} is using the port")
                print(f"[INFO] This might be:")
                print(f"   - Another uvicorn server instance (will be cleaned up)")
                print(f"   - Uvicorn master process (if restarting, this is expected)")
                
                # Attempt automatic cleanup
                if _cleanup_stale_process(pid_using_port, port):
                    print("[INFO] Port cleanup successful, proceeding with startup...")
                    # Wait a bit for port to be fully released
                    time.sleep(0.5)
                else:
                    print("=" * 80)
                    print(f"[ERROR] Cannot start server - port {port} is still in use")
                    print(f"[INFO] Manual cleanup required:")
                    if sys.platform == 'win32':
                        print(f"   Windows: taskkill /F /PID {pid_using_port}")
                    else:
                        print(f"   Linux/Mac: kill -9 {pid_using_port}")
                    print("=" * 80)
                    sys.exit(1)
            else:
                print("=" * 80)
                print(f"[ERROR] Cannot start server - port {port} is in use")
                print(f"[INFO] Could not detect the process using the port")
                print(f"   Please check manually and free the port")
                print("=" * 80)
                sys.exit(1)
        else:
            print(f"[INFO] Port {port} is available")
        
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
