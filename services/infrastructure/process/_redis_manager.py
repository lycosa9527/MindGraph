"""
Redis server management for MindGraph application.

Handles starting Redis server via systemctl or manual startup.
"""

import os
import sys
import time
import subprocess
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import redis as redis_module
else:
    try:
        import redis as redis_module
    except ImportError:
        redis_module = None

from services.infrastructure.process._port_utils import check_port_in_use


def _get_process_name(pid: int) -> Optional[str]:
    """
    Get the process name for a given PID.
    
    Args:
        pid: Process ID
        
    Returns:
        Process name or None if not found
    """
    if sys.platform == 'win32':
        try:
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
                capture_output=True,
                text=True,
                timeout=2,
                check=False
            )
            if result.stdout.strip():
                parts = result.stdout.strip().split(',')
                if len(parts) > 0:
                    return parts[0].strip('"').lower()
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ['ps', '-p', str(pid), '-o', 'comm=', '--no-headers'],
                capture_output=True,
                text=True,
                timeout=2,
                check=False
            )
            if result.stdout.strip():
                return result.stdout.strip().lower()
        except Exception:
            pass
    return None


def _get_redis_client(host: str, port: int, timeout: int = 2):
    """Helper function to create Redis client with proper type narrowing"""
    if redis_module is None:
        raise RuntimeError("Redis module not available")
    redis_client_class = getattr(redis_module, 'Redis')
    return redis_client_class(host=host, port=port, socket_connect_timeout=timeout)


def _verify_redis_on_port(host: str, port: int) -> bool:
    """
    Verify that Redis is actually running on the specified port.

    Args:
        host: Redis host
        port: Redis port

    Returns:
        bool: True if Redis is responding, False otherwise
    """
    if redis_module is None:
        return False
    try:
        r = _get_redis_client(host, port, timeout=2)
        r.ping()
        return True
    except Exception:
        return False


def start_redis_server(server_state) -> None:
    """
    Start Redis server if not already running (REQUIRED).

    Assumes Redis installation has been verified. Checks if Redis is running,
    and if not, attempts to start it via systemctl. Application will exit if
    Redis cannot be started.

    Args:
        server_state: ServerState instance to update
    """
    if redis_module is None:
        print("[ERROR] Redis module not available despite installation check passing.")
        sys.exit(1)

    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port_str = os.getenv('REDIS_PORT', '6379')
    redis_port = int(redis_port_str)

    port_in_use, pid = check_port_in_use(redis_host, redis_port)
    if port_in_use:
        if _verify_redis_on_port(redis_host, redis_port):
            print(f"[REDIS] Port {redis_port} is in use by existing Redis instance (PID: {pid})")
            print("[REDIS] ✓ Using existing Redis server")
            return
        if pid is None:
            print(f"[REDIS] Port {redis_port} appears in use but no process found")
            print("[REDIS] Attempting to start Redis anyway (port may be in TIME_WAIT state)")
        else:
            process_name = _get_process_name(pid)
            if process_name and ('redis' in process_name or 'redis-server' in process_name):
                print(f"[REDIS] Port {redis_port} is in use by process '{process_name}' (PID: {pid})")
                print("[REDIS] Process appears to be Redis, waiting for readiness...")
                for i in range(10):
                    try:
                        r = _get_redis_client(redis_host, redis_port, timeout=2)
                        r.ping()
                        print(f"[REDIS] ✓ Using existing Redis server (PID: {pid})")
                        return
                    except Exception:
                        if i < 9:
                            time.sleep(1)
                        else:
                            break
                print(f"[WARNING] Redis process found (PID: {pid}) but not responding")
                print("[REDIS] Attempting to start new instance anyway...")
            else:
                print(f"[ERROR] Port {redis_port} is in use but not by Redis")
                print(f"        Process using port: PID {pid} ({process_name or 'unknown'})")
                print("        Stop the process using this port or use a different port")
                print(f"        Check: lsof -i :{redis_port} (Linux/Mac) or netstat -ano | findstr :{redis_port} (Windows)")
                sys.exit(1)

    try:
        r = _get_redis_client(redis_host, redis_port, 2)
        r.ping()
        print("[REDIS] Redis server is already running")
        return
    except Exception:
        pass

    if sys.platform != 'win32':
        try:
            print("[REDIS] Starting Redis server via systemctl...")
            start_result = subprocess.run(
                ['sudo', 'systemctl', 'start', 'redis-server'],
                capture_output=True,
                timeout=5,
                check=False
            )

            if start_result.returncode != 0:
                error_msg = start_result.stderr.decode('utf-8', errors='ignore')
                if 'already active' not in error_msg.lower() and 'already started' not in error_msg.lower():
                    print("[ERROR] Failed to start Redis server via systemctl.")
                    print(f"        Error: {error_msg}")
                    print("        Try manually: sudo systemctl start redis-server")
                    print("        Application cannot start without Redis.")
                    sys.exit(1)

            server_state.redis_started_by_app = True
            print("[REDIS] Redis server started via systemctl")

            for i in range(10):
                try:
                    r = _get_redis_client(redis_host, redis_port, 1)
                    r.ping()
                    print("[REDIS] Redis server is ready")
                    return
                except Exception:
                    if i < 9:
                        time.sleep(1)
                    else:
                        break

            print("[ERROR] Redis server started but not responding after 10 seconds")
            print("        Check Redis logs: sudo journalctl -u redis-server -n 50")
            print("        Application cannot start without Redis.")
            sys.exit(1)
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            print(f"[ERROR] Cannot start Redis server: {e}")
            print("        Redis is REQUIRED. Please start Redis manually:")
            print("        sudo systemctl start redis-server")
            print("        Application cannot start without Redis.")
            sys.exit(1)
    else:
        print("[ERROR] Redis is REQUIRED but not running on Windows.")
        print("        Please start Redis manually or install Redis for Windows.")
        print("        Application cannot start without Redis.")
        sys.exit(1)
