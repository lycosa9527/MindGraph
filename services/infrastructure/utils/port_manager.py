"""
Port management utilities for MindGraph application.

Handles:
- Port availability checking
- Process detection on ports
- Stale process cleanup
- Shutdown error filtering for stderr
"""

import os
import sys
import socket
import signal
import time
import subprocess
import logging

logger = logging.getLogger(__name__)


def check_port_available(host: str, port: int):
    """
    Check if a port is available for binding.

    Args:
        host: Host address to check
        port: Port number to check

    Returns:
        tuple: (is_available: bool, pid_using_port: Optional[int])
    """
    # Try to bind to the port
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.close()
        return (True, None)
    except OSError as e:
        # Port is in use - try to find the process
        if e.errno in (10048, 98):  # Windows: 10048, Linux: 98 (EADDRINUSE)
            pid = find_process_on_port(port)
            return (False, pid)
        # Other error - re-raise
        raise


def find_process_on_port(port: int):
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
                timeout=5,
                check=False
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
                timeout=5,
                check=False
            )
            if result.stdout.strip():
                return int(result.stdout.strip())
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Could not detect process on port %s: %s", port, e)

    return None


def cleanup_stale_process(pid: int, port: int) -> bool:
    """
    Attempt to gracefully terminate a stale server process.

    Args:
        pid: Process ID to terminate
        port: Port number (for logging)

    Returns:
        bool: True if cleanup successful, False otherwise
    """
    logger.warning("Found process %s using port %s", pid, port)
    logger.info("Attempting to terminate stale server process...")

    try:
        if sys.platform == 'win32':
            # Windows: taskkill
            # First try graceful termination
            subprocess.run(
                ['taskkill', '/PID', str(pid)],
                capture_output=True,
                timeout=3,
                check=False
            )
            time.sleep(1)

            # Check if still running
            check_result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True,
                text=True,
                timeout=2,
                check=False
            )
            if str(pid) in check_result.stdout:
                # Force kill if graceful failed
                logger.info("Process still running, forcing termination...")
                subprocess.run(
                    ['taskkill', '/F', '/PID', str(pid)],
                    capture_output=True,
                    timeout=2,
                    check=False
                )
        else:
            # Linux/Mac: kill
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            try:
                if hasattr(signal, 'SIGKILL'):
                    sigkill = getattr(signal, 'SIGKILL')  # pylint: disable=no-member
                    os.kill(pid, sigkill)
                else:
                    # Fallback for systems without SIGKILL
                    os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass  # Process already terminated

        # Wait for port to be released
        time.sleep(1)
        port_available, _ = check_port_available('0.0.0.0', port)

        if port_available:
            logger.info("✅ Successfully cleaned up stale process (PID: %s)", pid)
            return True
        else:
            logger.error("❌ Port %s still in use after cleanup attempt", port)
            return False

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Failed to cleanup process %s: %s", pid, e)
        return False


class ShutdownErrorFilter:
    """Filter stderr to suppress expected shutdown errors"""

    def __init__(self, stderr_target):
        self.original_stderr = stderr_target
        self.buffer = ""
        self.in_traceback = False
        self.suppress_current = False

    def write(self, text) -> None:
        """Filter text and only write non-shutdown errors"""
        self.buffer += text

        # Check for start of traceback
        if 'Process SpawnProcess' in text or 'Traceback (most recent call last)' in text:
            self.in_traceback = True
            self.suppress_current = False

        # Check if this traceback is a CancelledError
        if self.in_traceback and 'asyncio.exceptions.CancelledError' in self.buffer:
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

    def flush(self) -> None:
        """Flush the original stderr"""
        if not self.suppress_current and self.buffer and not self.in_traceback:
            self.original_stderr.write(self.buffer)
        self.original_stderr.flush()
        self.buffer = ""

    def __getattr__(self, name):
        """Delegate all other attributes to original stderr"""
        return getattr(self.original_stderr, name)
