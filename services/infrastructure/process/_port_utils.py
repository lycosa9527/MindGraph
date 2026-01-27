"""
Port checking utilities for process management.

Provides functions to check if ports are in use and find processes using them.
"""

import socket
import subprocess
import sys
from typing import Optional


def check_port_in_use(host: str, port: int) -> tuple[bool, Optional[int]]:
    """
    Check if a port is in use and return the PID of the process using it.

    Uses multiple methods to accurately detect if a port is actually listening:
    1. Use system tools to find the process (lsof/netstat) - most reliable
    2. Try to bind to the port (if we can bind, port is definitely free)
    3. Try to connect to the port (only if bind fails with EADDRINUSE)

    Args:
        host: Host address to check (used for connection test, binding uses 127.0.0.1)
        port: Port number to check

    Returns:
        Tuple of (is_in_use: bool, pid: Optional[int])
    """
    try:
        pid = find_process_on_port(port)
        if pid is not None:
            return (True, pid)
    except Exception:
        pass

    bind_failed_eaddrinuse = False
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            test_sock.bind(('127.0.0.1', port))
            test_sock.close()
            return (False, None)
        except OSError as e:
            test_sock.close()
            errno = getattr(e, 'errno', None)
            error_msg = str(e).lower()
            if errno == 98 or errno == 48 or errno == 10048:
                bind_failed_eaddrinuse = True
            elif 'address already in use' in error_msg or 'address is already in use' in error_msg:
                bind_failed_eaddrinuse = True
    except Exception:
        pass

    if bind_failed_eaddrinuse:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                pid = find_process_on_port(port)
                return (True, pid)
        except Exception:
            pass
        pid = find_process_on_port(port)
        if pid is not None:
            return (True, pid)
        return (True, None)

    return (False, None)


def find_process_on_port(port: int) -> Optional[int]:
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
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            if result.stdout.strip():
                return int(result.stdout.strip())
    except Exception:
        pass
    return None
