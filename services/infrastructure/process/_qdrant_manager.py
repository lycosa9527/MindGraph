"""
Qdrant server management for MindGraph application.

Handles starting and stopping Qdrant server processes.
"""

import os
import sys
import time
import signal
import atexit
import subprocess
import urllib.request
from typing import Optional

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


def _verify_qdrant_on_port(host: str, port: int) -> bool:
    """
    Verify that Qdrant is actually running on the specified port.

    Args:
        host: Qdrant host
        port: Qdrant port

    Returns:
        bool: True if Qdrant is responding, False otherwise
    """
    try:
        url = f'http://{host}:{port}/collections'
        urllib.request.urlopen(url, timeout=2)
        return True
    except Exception:
        return False


def start_qdrant_server(server_state) -> Optional[subprocess.Popen[bytes]]:
    """
    Start Qdrant server as a subprocess if not already running (REQUIRED).

    Assumes Qdrant installation has been verified. Checks if Qdrant is running,
    and if not, attempts to start it. Application will exit if Qdrant cannot be started.

    Args:
        server_state: ServerState instance to update

    Returns:
        Optional[subprocess.Popen[bytes]]: Qdrant process or None if using existing
    """
    qdrant_host = os.getenv('QDRANT_HOST', 'localhost')
    qdrant_port_str = os.getenv('QDRANT_PORT', '6333')
    qdrant_port = int(qdrant_port_str)

    port_in_use, pid = check_port_in_use(qdrant_host, qdrant_port)
    if port_in_use:
        if _verify_qdrant_on_port(qdrant_host, qdrant_port):
            print(f"[QDRANT] Port {qdrant_port} is in use by existing Qdrant instance (PID: {pid})")
            print("[QDRANT] ✓ Using existing Qdrant server")
            return None
        if pid is None:
            print(f"[QDRANT] Port {qdrant_port} appears in use but no process found")
            print("[QDRANT] Attempting to start Qdrant anyway (port may be in TIME_WAIT state)")
        else:
            process_name = _get_process_name(pid)
            if process_name and 'qdrant' in process_name:
                print(f"[QDRANT] Port {qdrant_port} is in use by process '{process_name}' (PID: {pid})")
                print("[QDRANT] Process appears to be Qdrant, waiting for readiness...")
                for i in range(10):
                    try:
                        urllib.request.urlopen(f'http://{qdrant_host}:{qdrant_port}/collections', timeout=2)
                        print(f"[QDRANT] ✓ Using existing Qdrant server (PID: {pid})")
                        return None
                    except Exception:
                        if i < 9:
                            time.sleep(1)
                        else:
                            break
                print(f"[WARNING] Qdrant process found (PID: {pid}) but not responding")
                print("[QDRANT] Attempting to start new instance anyway...")
            else:
                print(f"[ERROR] Port {qdrant_port} is in use but not by Qdrant")
                print(f"        Process using port: PID {pid} ({process_name or 'unknown'})")
                print("        Stop the process using this port or use a different port")
                print(f"        Check: lsof -i :{qdrant_port} (Linux/Mac) or "
                      f"netstat -ano | findstr :{qdrant_port} (Windows)")
                sys.exit(1)

    try:
        urllib.request.urlopen(f'http://{qdrant_host}:{qdrant_port}/collections', timeout=2)
        print(f"[QDRANT] Qdrant server is already running on {qdrant_host}:{qdrant_port}")
        return None
    except Exception:
        pass

    if sys.platform != 'win32':
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', '--quiet', 'qdrant'],
                capture_output=True,
                timeout=1,
                check=False
            )
            if result.returncode == 0:
                print("[QDRANT] Qdrant systemd service is active (waiting for readiness...)")
                for i in range(10):
                    try:
                        urllib.request.urlopen('http://localhost:6333/collections', timeout=1)
                        print("[QDRANT] Qdrant systemd service is ready")
                        return None
                    except Exception:
                        if i < 9:
                            time.sleep(1)
                        else:
                            break
                print("[ERROR] Qdrant systemd service is active but not responding after 10 seconds")
                print("        Check Qdrant logs: sudo journalctl -u qdrant -n 50")
                print("        Application cannot start without Qdrant.")
                sys.exit(1)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    qdrant_paths = [
        os.path.expanduser('~/qdrant/qdrant'),
        '/usr/local/bin/qdrant',
        '/usr/bin/qdrant',
    ]

    qdrant_binary = None
    for path in qdrant_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            qdrant_binary = path
            break

    if not qdrant_binary:
        print("[ERROR] Qdrant binary not found despite installation check passing.")
        print("        This may indicate a configuration issue.")
        print("        Application cannot start without Qdrant.")
        sys.exit(1)

    qdrant_dir = os.path.dirname(qdrant_binary)
    qdrant_storage = os.path.join(qdrant_dir, 'storage')
    os.makedirs(qdrant_storage, exist_ok=True)

    print("[QDRANT] Starting Qdrant server as subprocess...")

    qdrant_cmd = [qdrant_binary]

    try:
        server_state.qdrant_process = subprocess.Popen(
            qdrant_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=qdrant_dir,
            env={
                **os.environ,
                'QDRANT__STORAGE__STORAGE_PATH': qdrant_storage,
                'QDRANT__SERVICE__HTTP_PORT': '6333',
            },
            bufsize=1,
        )

        def stop_wrapper():
            stop_qdrant_server(server_state)
        atexit.register(stop_wrapper)

        time.sleep(2)

        try:
            urllib.request.urlopen('http://localhost:6333/collections', timeout=2)
            print(f"[QDRANT] Server started successfully (PID: {server_state.qdrant_process.pid})")
            return server_state.qdrant_process
        except Exception:
            print("[ERROR] Qdrant server process started but not responding on port 6333")
            print("        Check if port 6333 is available: lsof -i :6333")
            print("        Application cannot start without Qdrant.")
            sys.exit(1)

    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        print(f"[ERROR] Failed to start Qdrant server: {e}")
        print("        Application cannot start without Qdrant.")
        sys.exit(1)


def stop_qdrant_server(server_state) -> None:
    """Stop the Qdrant server subprocess"""
    if server_state.qdrant_process is not None:
        try:
            print("[QDRANT] Stopping Qdrant server...")
        except (ValueError, OSError):
            pass
        try:
            if sys.platform == 'win32':
                server_state.qdrant_process.terminate()
            else:
                if hasattr(os, 'getpgid') and hasattr(os, 'killpg'):
                    pgid = os.getpgid(server_state.qdrant_process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    server_state.qdrant_process.terminate()
            server_state.qdrant_process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError, ProcessLookupError) as e:
            try:
                print(f"[QDRANT] Error stopping server: {e}")
            except (ValueError, OSError):
                pass
            try:
                server_state.qdrant_process.kill()
            except (OSError, ProcessLookupError):
                pass
        server_state.qdrant_process = None
        try:
            print("[QDRANT] Server stopped")
        except (ValueError, OSError):
            pass
