"""
PostgreSQL server management for MindGraph application.

Handles starting and stopping PostgreSQL server processes.
"""

import os
import sys
import time
import signal
import atexit
import subprocess
import shlex
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from services.infrastructure.process._port_utils import check_port_in_use

if TYPE_CHECKING:
    import psycopg2
    from psycopg2 import sql
else:
    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        psycopg2 = None
        sql = None


def _verify_postgresql_on_port(host: str, port: int, db_url: Optional[str] = None) -> bool:
    """
    Verify that PostgreSQL is actually running on the specified port.

    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        db_url: Optional database URL for connection test

    Returns:
        bool: True if PostgreSQL is responding, False otherwise
    """
    if psycopg2 is None:
        return False
    try:
        if db_url and 'postgresql' in db_url:
            conn = psycopg2.connect(db_url, connect_timeout=2)
            conn.close()
            return True
        test_url = f'postgresql://postgres@{host}:{port}/postgres'
        conn = psycopg2.connect(test_url, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


def start_postgresql_server(server_state) -> Optional[subprocess.Popen[bytes]]:
    """
    Start PostgreSQL server as a subprocess if not already running (REQUIRED).

    Assumes PostgreSQL installation has been verified. Checks if PostgreSQL is running,
    and if not, attempts to start it. Application will exit if PostgreSQL cannot be started.

    For subprocess mode:
    - Initializes data directory with initdb if needed
    - Generates postgresql.conf and pg_hba.conf
    - Creates database/user on first startup
    - Starts postgres binary as subprocess

    Args:
        server_state: ServerState instance to update

    Returns:
        Optional[subprocess.Popen[bytes]]: PostgreSQL process or None if using existing
    """
    if psycopg2 is None:
        print("[ERROR] psycopg2 is not available")
        print("        Install with: pip install psycopg2-binary")
        print("        Application cannot start without PostgreSQL.")
        sys.exit(1)

    port = os.getenv('POSTGRESQL_PORT', '5432')
    port_int = int(port)
    db_url = os.getenv('DATABASE_URL', '')

    port_in_use, pid = check_port_in_use('localhost', port_int)
    if port_in_use:
        if _verify_postgresql_on_port('localhost', port_int, db_url):
            print(f"[POSTGRESQL] Port {port} is in use by existing PostgreSQL instance (PID: {pid})")
            print("[POSTGRESQL] ✓ Using existing PostgreSQL server")
            return None
        if pid is None:
            postgres_pids = []
            if sys.platform != 'win32':
                try:
                    result = subprocess.run(
                        ['pgrep', '-f', 'postgres.*-D'],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False
                    )
                    if result.stdout.strip():
                        postgres_pids = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
                except Exception:
                    pass
            if postgres_pids:
                print(f"[ERROR] Port {port} is in use but no process found on port")
                print(f"        Found PostgreSQL processes: {', '.join(postgres_pids)}")
                print("        These processes may be using the port in a different namespace.")
                print("        Solutions:")
                print(f"        1. Kill PostgreSQL processes: kill -9 {' '.join(postgres_pids)}")
                print(f"        2. Check port usage: sudo netstat -tlnp | grep :{port}")
                print("        3. Use a different port: Set POSTGRESQL_PORT=<different_port> in .env")
            else:
                print(f"[ERROR] Port {port} is in use but no process found (may be in different namespace)")
                print("        This can happen in WSL or Docker environments.")
                print("        Solutions:")
                print(f"        1. Check for processes: lsof -i :{port} or sudo netstat -tlnp | grep :{port}")
                print("        2. Try killing any PostgreSQL processes: pkill -9 postgres")
                print("        3. Wait a few seconds for TIME_WAIT sockets to clear")
                print("        4. Use a different port: Set POSTGRESQL_PORT=<different_port> in .env")
            print("        Application cannot start without PostgreSQL.")
            sys.exit(1)
        else:
            print(f"[ERROR] Port {port} is in use but not by PostgreSQL")
            print(f"        Process using port: PID {pid}")
            print("        Stop the process using this port or use a different port")
            print(f"        Check: lsof -i :{port} (Linux/Mac) or netstat -ano | findstr :{port} (Windows)")
            sys.exit(1)

    if db_url and 'postgresql' in db_url:
        try:
            conn = psycopg2.connect(db_url, connect_timeout=2)
            conn.close()
            try:
                print("[POSTGRESQL] PostgreSQL server is already running")
                print("[POSTGRESQL] Using existing PostgreSQL instance")
            except (ValueError, OSError):
                pass
            return None
        except Exception:
            pass

    user = os.getenv('POSTGRESQL_USER', 'mindgraph_user')
    password = os.getenv('POSTGRESQL_PASSWORD', 'mindgraph_password')
    database = os.getenv('POSTGRESQL_DATABASE', 'mindgraph')

    postgresql_managed = os.getenv('POSTGRESQL_MANAGED_BY_APP', 'true').lower() not in ('false', '0', 'no')
    if not postgresql_managed:
        if sys.platform != 'win32':
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', '--quiet', 'postgresql'],
                    capture_output=True,
                    timeout=1,
                    check=False
                )
                if result.returncode == 0:
                    try:
                        print("[POSTGRESQL] PostgreSQL systemd service is active (waiting for readiness...)")
                    except (ValueError, OSError):
                        pass
                    for i in range(10):
                        try:
                            conn = psycopg2.connect(db_url, connect_timeout=2)
                            conn.close()
                            try:
                                print("[POSTGRESQL] PostgreSQL systemd service is ready")
                            except (ValueError, OSError):
                                pass
                            return None
                        except Exception:
                            if i < 9:
                                time.sleep(1)
                            else:
                                break
                    try:
                        print("[ERROR] PostgreSQL systemd service is active but not responding after 10 seconds")
                        print("        Check PostgreSQL logs: sudo journalctl -u postgresql -n 50")
                        print("        Application cannot start without PostgreSQL.")
                    except (ValueError, OSError):
                        pass
                    sys.exit(1)
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

    postgres_paths = [
        '/usr/lib/postgresql/18/bin/postgres',
        '/usr/lib/postgresql/16/bin/postgres',
        '/usr/lib/postgresql/15/bin/postgres',
        '/usr/lib/postgresql/14/bin/postgres',
        '/usr/local/pgsql/bin/postgres',
        '/usr/bin/postgres',
    ]

    postgres_binary = None
    initdb_binary = None
    for path in postgres_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            postgres_binary = path
            postgres_dir = os.path.dirname(path)
            initdb_path = os.path.join(postgres_dir, 'initdb')
            if os.path.exists(initdb_path) and os.access(initdb_path, os.X_OK):
                initdb_binary = initdb_path
            break

    if not postgres_binary:
        try:
            print("[ERROR] PostgreSQL postgres binary not found despite installation check passing.")
            print("        This may indicate a configuration issue.")
            print("        Application cannot start without PostgreSQL.")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    if not initdb_binary:
        try:
            print("[ERROR] PostgreSQL initdb binary not found.")
            print("        Install PostgreSQL with: sudo apt-get install postgresql postgresql-contrib")
            print("        Application cannot start without PostgreSQL.")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    data_dir = os.getenv('POSTGRESQL_DATA_DIR', './storage/postgresql')
    port = os.getenv('POSTGRESQL_PORT', '5432')
    user = os.getenv('POSTGRESQL_USER', 'mindgraph_user')
    password = os.getenv('POSTGRESQL_PASSWORD', 'mindgraph_password')
    database = os.getenv('POSTGRESQL_DATABASE', 'mindgraph')

    data_path = Path(data_dir).resolve()

    resolved_str = str(data_path)
    is_wsl_windows_fs = resolved_str.startswith('/mnt/')

    if not is_wsl_windows_fs:
        try:
            current = data_path
            while current != current.parent:
                if current.is_symlink():
                    link_target = current.readlink()
                    if str(link_target.resolve()).startswith('/mnt/'):
                        is_wsl_windows_fs = True
                        break
                current = current.parent
        except Exception:
            pass

    if is_wsl_windows_fs:
        linux_native_dir = Path.home() / '.mindgraph' / 'postgresql'
        linux_native_dir.mkdir(parents=True, exist_ok=True)

        try:
            print("[POSTGRESQL] Detected Windows-mounted filesystem - using Linux-native path")
            print(f"[POSTGRESQL] Original path: {data_path}")
            print(f"[POSTGRESQL] Using Linux-native path: {linux_native_dir}")
            print("[POSTGRESQL] (To use a custom path, set POSTGRESQL_DATA_DIR to a Linux-native location)")
        except (ValueError, OSError):
            pass

        data_path = linux_native_dir.resolve()

    data_path.mkdir(parents=True, exist_ok=True)

    try:
        os.chmod(data_path, 0o700)
    except OSError:
        pass

    pg_version_file = data_path / 'PG_VERSION'
    if not pg_version_file.exists():
        try:
            print("[POSTGRESQL] Initializing PostgreSQL data directory...")
        except (ValueError, OSError):
            pass
        
        # Check if running as root
        is_root = False
        if sys.platform != 'win32':
            try:
                is_root = os.geteuid() == 0
            except AttributeError:
                # Windows doesn't have geteuid
                is_root = False
        
        initdb_user = 'postgres'
        initdb_base_cmd = [initdb_binary, '-D', str(data_path), '-U', initdb_user, '--locale=C', '--encoding=UTF8']
        use_shell = False
        
        # If running as root, ensure postgres user exists and can access the data directory
        if is_root:
            # Step 1: Ensure postgres user exists (find or create)
            postgres_user_exists = False
            try:
                result = subprocess.run(
                    ['id', '-u', 'postgres'],
                    capture_output=True,
                    timeout=2,
                    check=False
                )
                postgres_user_exists = result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
            
            if not postgres_user_exists:
                # Try to create postgres user
                try:
                    print("[POSTGRESQL] Creating 'postgres' user for PostgreSQL initialization...")
                    create_result = subprocess.run(
                        ['useradd', '-r', '-s', '/bin/bash', '-d', '/var/lib/postgresql', '-m', 'postgres'],
                        capture_output=True,
                        timeout=5,
                        check=False
                    )
                    if create_result.returncode == 0:
                        postgres_user_exists = True
                        try:
                            print("[POSTGRESQL] 'postgres' user created successfully")
                        except (ValueError, OSError):
                            pass
                    else:
                        # Try sudo -u postgres as fallback
                        sudo_available = False
                        try:
                            result = subprocess.run(
                                ['which', 'sudo'],
                                capture_output=True,
                                timeout=2,
                                check=False
                            )
                            sudo_available = result.returncode == 0
                        except (subprocess.SubprocessError, FileNotFoundError):
                            pass
                        
                        if not sudo_available:
                            try:
                                print("[ERROR] Cannot create 'postgres' user and sudo is not available")
                                print("        PostgreSQL's initdb cannot be run as root for security reasons.")
                                print("        Solutions:")
                                print("        1. Run the script as a non-root user")
                                print("        2. Create a 'postgres' user manually: useradd -r -s /bin/bash -d /var/lib/postgresql -m postgres")
                                print("        3. Initialize PostgreSQL manually:")
                                print(f"           sudo -u postgres {initdb_binary} -D {data_path} -U postgres --locale=C --encoding=UTF8")
                                print("        4. Or use an existing PostgreSQL installation")
                            except (ValueError, OSError):
                                pass
                            sys.exit(1)
                except (subprocess.SubprocessError, FileNotFoundError) as e:
                    try:
                        print(f"[WARNING] Could not create postgres user: {e}")
                    except (ValueError, OSError):
                        pass
            
            # Step 2: If data directory is under /root/, change ownership to postgres user
            data_path_str = str(data_path)
            is_under_root = data_path_str.startswith('/root/')
            
            if is_under_root and postgres_user_exists:
                try:
                    print("[POSTGRESQL] Changing ownership of data directory to 'postgres' user...")
                    # Ensure parent storage directory exists and is accessible
                    storage_dir = data_path.parent
                    if not storage_dir.exists():
                        storage_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Change ownership of storage directory recursively (includes all subdirectories)
                    subprocess.run(
                        ['chown', '-R', 'postgres:postgres', str(storage_dir)],
                        check=True,
                        timeout=10,
                        capture_output=True
                    )
                    
                    # Ensure parent directories have execute permission for postgres to traverse
                    # Change ownership and permissions of parent directories in the path
                    current_path = storage_dir.parent  # scripts/db
                    while str(current_path) != '/' and str(current_path).startswith('/root/'):
                        # Change ownership to postgres so it can traverse
                        subprocess.run(
                            ['chown', 'postgres:postgres', str(current_path)],
                            check=False,
                            timeout=5,
                            capture_output=True
                        )
                        # Set execute permission for directory traversal
                        subprocess.run(
                            ['chmod', '755', str(current_path)],
                            check=False,
                            timeout=5,
                            capture_output=True
                        )
                        # Stop at /root/MindGraph level (don't change /root itself)
                        if str(current_path.parent) == '/root':
                            break
                        current_path = current_path.parent
                    
                    # Set proper permissions for PostgreSQL data directory
                    subprocess.run(
                        ['chmod', '-R', '700', str(data_path)],
                        check=False,
                        timeout=5,
                        capture_output=True
                    )
                    try:
                        print("[POSTGRESQL] Ownership changed successfully")
                    except (ValueError, OSError):
                        pass
                except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
                    try:
                        print(f"[WARNING] Could not change ownership: {e}")
                        print("[POSTGRESQL] Will attempt to continue, but initdb may fail")
                    except (ValueError, OSError):
                        pass
            
            # Step 3: Set up initdb command to run as postgres user
            if postgres_user_exists:
                # Try sudo -u postgres first (most reliable)
                sudo_available = False
                try:
                    result = subprocess.run(
                        ['which', 'sudo'],
                        capture_output=True,
                        timeout=2,
                        check=False
                    )
                    sudo_available = result.returncode == 0
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass
                
                if sudo_available:
                    # Try sudo -u postgres
                    try:
                        result = subprocess.run(
                            ['sudo', '-u', 'postgres', 'id'],
                            capture_output=True,
                            timeout=2,
                            check=False
                        )
                        if result.returncode == 0:
                            initdb_cmd = ['sudo', '-u', 'postgres'] + initdb_base_cmd
                            use_shell = False
                            try:
                                print("[POSTGRESQL] Running initdb via sudo as 'postgres' user (running as root)")
                            except (ValueError, OSError):
                                pass
                        else:
                            # Fallback to su
                            cmd_str = ' '.join(shlex.quote(str(arg)) for arg in initdb_base_cmd)
                            initdb_cmd = ['su', '-', 'postgres', '-c', cmd_str]
                            use_shell = False
                            try:
                                print("[POSTGRESQL] Running initdb as 'postgres' user (running as root)")
                            except (ValueError, OSError):
                                pass
                    except (subprocess.SubprocessError, FileNotFoundError):
                        # Fallback to su
                        cmd_str = ' '.join(shlex.quote(str(arg)) for arg in initdb_base_cmd)
                        initdb_cmd = ['su', '-', 'postgres', '-c', cmd_str]
                        use_shell = False
                        try:
                            print("[POSTGRESQL] Running initdb as 'postgres' user (running as root)")
                        except (ValueError, OSError):
                            pass
                else:
                    # Use su directly
                    cmd_str = ' '.join(shlex.quote(str(arg)) for arg in initdb_base_cmd)
                    initdb_cmd = ['su', '-', 'postgres', '-c', cmd_str]
                    use_shell = False
                    try:
                        print("[POSTGRESQL] Running initdb as 'postgres' user (running as root)")
                    except (ValueError, OSError):
                        pass
            else:
                # Last resort: provide helpful error
                try:
                    print("[ERROR] Cannot run initdb as root")
                    print("        PostgreSQL's initdb cannot be run as root for security reasons.")
                    print("        Solutions:")
                    print("        1. Run the script as a non-root user")
                    print("        2. Create a 'postgres' user: useradd -r -s /bin/bash -d /var/lib/postgresql -m postgres")
                    print("        3. Initialize PostgreSQL manually:")
                    print(f"           sudo -u postgres {initdb_binary} -D {data_path} -U postgres --locale=C --encoding=UTF8")
                    print("        4. Or use an existing PostgreSQL installation")
                except (ValueError, OSError):
                    pass
                sys.exit(1)
        else:
            initdb_cmd = initdb_base_cmd
        
        try:
            initdb_result = subprocess.run(
                initdb_cmd,
                capture_output=True,
                timeout=30,
                check=False,
                text=True,
                shell=use_shell
            )
            if initdb_result.returncode != 0:
                error_msg = initdb_result.stderr
                # Check for root error specifically
                if 'cannot be run as root' in error_msg.lower():
                    try:
                        print("[ERROR] Failed to initialize PostgreSQL data directory: cannot run as root")
                        print("        PostgreSQL's initdb cannot be run as root for security reasons.")
                        print("        Solutions:")
                        print("        1. Run the script as a non-root user")
                        print("        2. Create a 'postgres' user: sudo useradd -r -s /bin/bash -d /var/lib/postgresql -m postgres")
                        print("        3. Initialize PostgreSQL manually:")
                        print(f"           sudo -u postgres {initdb_binary} -D {data_path} -U postgres --locale=C --encoding=UTF8")
                        print("        4. Or use an existing PostgreSQL installation")
                    except (ValueError, OSError):
                        pass
                else:
                    try:
                        print(f"[ERROR] Failed to initialize PostgreSQL data directory: {error_msg}")
                        print("        Application cannot start without PostgreSQL.")
                    except (ValueError, OSError):
                        pass
                sys.exit(1)
            try:
                print("[POSTGRESQL] Data directory initialized")
            except (ValueError, OSError):
                pass
        except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
            try:
                print(f"[ERROR] Failed to initialize PostgreSQL data directory: {e}")
                if is_root:
                    print("        Running as root - PostgreSQL initdb requires a non-root user.")
                    print("        Solutions:")
                    print("        1. Run the script as a non-root user")
                    print("        2. Create a 'postgres' user: sudo useradd -r -s /bin/bash -d /var/lib/postgresql -m postgres")
                    print("        3. Initialize PostgreSQL manually:")
                    print(f"           sudo -u postgres {initdb_binary} -D {data_path} -U postgres --locale=C --encoding=UTF8")
                print("        Application cannot start without PostgreSQL.")
            except (ValueError, OSError):
                pass
            sys.exit(1)

    postgresql_conf = data_path / 'postgresql.conf'
    socket_dir = data_path / 'sockets'
    socket_dir.mkdir(exist_ok=True)
    try:
        os.chmod(socket_dir, 0o700)
    except OSError:
        pass

    try:
        config_needs_update = True
        if postgresql_conf.exists():
            with open(postgresql_conf, 'r', encoding='utf-8') as f:
                content = f.read()
                has_correct_socket = f'unix_socket_directories = \'{socket_dir}\'' in content
                has_c_locale = 'lc_messages = \'C\'' in content
                if has_correct_socket and has_c_locale:
                    config_needs_update = False

        if config_needs_update:
            with open(postgresql_conf, 'w', encoding='utf-8') as f:
                f.write(f"""# PostgreSQL configuration for MindGraph subprocess mode
port = {port}
listen_addresses = '127.0.0.1'
# Use our socket directory (user-owned) instead of /var/run/postgresql/
unix_socket_directories = '{socket_dir}'
max_connections = 100
shared_buffers = 128MB
dynamic_shared_memory_type = posix
log_destination = 'stderr'
logging_collector = off
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_timezone = 'UTC'
datestyle = 'iso, mdy'
timezone = 'UTC'
# Locale settings - use C locale to avoid locale validation issues
lc_messages = 'C'
lc_monetary = 'C'
lc_numeric = 'C'
lc_time = 'C'
default_text_search_config = 'pg_catalog.english'
""")
            try:
                print(f"[POSTGRESQL] Updated postgresql.conf with socket directory: {socket_dir}")
            except (ValueError, OSError):
                pass
    except Exception as e:
        try:
            print(f"[ERROR] Failed to update postgresql.conf: {e}")
        except (ValueError, OSError):
            pass

    pg_hba_conf = data_path / 'pg_hba.conf'
    if not pg_hba_conf.exists():
        try:
            with open(pg_hba_conf, 'w', encoding='utf-8') as f:
                f.write("""# PostgreSQL host-based authentication configuration
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
""")
        except Exception as e:
            try:
                print(f"[ERROR] Failed to create pg_hba.conf: {e}")
            except (ValueError, OSError):
                pass

    try:
        print("[POSTGRESQL] Starting PostgreSQL server as subprocess...")
    except (ValueError, OSError):
        pass

    if not socket_dir.exists():
        socket_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(socket_dir, 0o700)
    except OSError:
        pass

    if not os.access(socket_dir, os.W_OK):
        try:
            print(f"[ERROR] Socket directory is not writable: {socket_dir}")
            print(f"        Fix permissions: chmod 700 {socket_dir}")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    socket_dir_abs = str(socket_dir.resolve())

    test_file = socket_dir / '.test_write'
    try:
        test_file.write_text('test')
        test_file.unlink()
    except Exception as e:
        try:
            print(f"[ERROR] Cannot write to socket directory {socket_dir_abs}: {e}")
            print(f"        Fix permissions: chmod 700 {socket_dir_abs}")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    postgres_env = os.environ.copy()
    postgres_env['PGHOST'] = socket_dir_abs

    postgres_cmd = [
        postgres_binary,
        '-D', str(data_path),
        '-c', f'unix_socket_directories={socket_dir_abs}',
        '-c', 'listen_addresses=127.0.0.1'
    ]

    try:
        print(f"[POSTGRESQL] Socket directory: {socket_dir_abs}")
    except (ValueError, OSError):
        pass

    try:
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        postgres_log = logs_dir / 'postgresql.log'

        postgres_stdout = open(postgres_log, 'a', encoding='utf-8') if sys.platform != 'win32' else sys.stdout
        postgres_stderr = open(postgres_log, 'a', encoding='utf-8') if sys.platform != 'win32' else sys.stderr

        server_state.postgresql_process = subprocess.Popen(
            postgres_cmd,
            stdout=postgres_stdout,
            stderr=postgres_stderr,
            cwd=str(data_path),
            env=postgres_env,
            start_new_session=sys.platform != 'win32',
            bufsize=1,
        )

        def stop_wrapper():
            stop_postgresql_server(server_state)
        atexit.register(stop_wrapper)

        last_error = None
        superuser_name = 'postgres'
        current_user = os.getenv('USER') or os.getenv('USERNAME') or 'postgres'

        for i in range(30):
            try:
                conn = psycopg2.connect(
                    f'postgresql://{superuser_name}@127.0.0.1:{port}/postgres',
                    connect_timeout=2
                )
                conn.close()
                break
            except Exception as e:
                if 'role "postgres" does not exist' in str(e) and current_user != 'postgres':
                    try:
                        conn = psycopg2.connect(
                            f'postgresql://{current_user}@127.0.0.1:{port}/postgres',
                            connect_timeout=2
                        )
                        conn.close()
                        superuser_name = current_user
                        try:
                            print(
                                f"[POSTGRESQL] Using current Linux user '{current_user}' "
                                "as superuser (postgres role not found)"
                            )
                        except (ValueError, OSError):
                            pass
                        break
                    except Exception:
                        pass
                last_error = e
                if i < 29:
                    time.sleep(1)
                else:
                    if server_state.postgresql_process.poll() is not None:
                        try:
                            if postgres_log.exists():
                                with open(postgres_log, 'r', encoding='utf-8') as f:
                                    log_lines = f.readlines()
                                    if log_lines:
                                        last_log_lines = '\n'.join(log_lines[-10:])
                                        print("[ERROR] PostgreSQL server process terminated")
                                        print(f"[ERROR] Last log entries:\n{last_log_lines}")
                        except Exception:
                            pass
                    else:
                        try:
                            print("[ERROR] PostgreSQL server process started but not responding after 30 seconds")
                            print(f"[ERROR] Last connection error: {last_error}")
                            print(f"[ERROR] Check PostgreSQL logs: tail -f {postgres_log}")
                            print(f"[ERROR] Data directory: {data_path}")
                            print(f"[ERROR] Try manually: psql -U {superuser_name} -h 127.0.0.1 -p {port} -d postgres")
                        except (ValueError, OSError):
                            pass
                    sys.exit(1)

        try:
            if sql is None:
                raise RuntimeError("psycopg2.sql not available")

            conn = psycopg2.connect(
                f'postgresql://{superuser_name}@127.0.0.1:{port}/postgres',
                connect_timeout=5
            )
            conn.autocommit = True
            cursor = conn.cursor()

            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
            if not cursor.fetchone():
                create_user_query = sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier(user)
                )
                cursor.execute(create_user_query, (password,))
                try:
                    print(f"[POSTGRESQL] Created user: {user}")
                except (ValueError, OSError):
                    pass

            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            if not cursor.fetchone():
                create_db_query = sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(database),
                    sql.Identifier(user)
                )
                cursor.execute(create_db_query)
                try:
                    print(f"[POSTGRESQL] Created database: {database}")
                except (ValueError, OSError):
                    pass

            cursor.close()
            conn.close()
        except Exception as e:
            try:
                print(f"[WARNING] Failed to create database/user (may already exist): {e}")
            except (ValueError, OSError):
                pass

        try:
            conn = psycopg2.connect(db_url, connect_timeout=5)
            conn.close()
            try:
                print(f"[POSTGRESQL] Server started successfully (PID: {server_state.postgresql_process.pid})")
                if sys.platform != 'win32':
                    print(f"[POSTGRESQL] Logs: {postgres_log}")
            except (ValueError, OSError):
                pass
            return server_state.postgresql_process
        except Exception as e:
            try:
                print(f"[ERROR] PostgreSQL server started but connection test failed: {e}")
                print("        Check PostgreSQL logs: tail -f logs/postgresql.log")
                print("        Application cannot start without PostgreSQL.")
            except (ValueError, OSError):
                pass
            sys.exit(1)

    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        try:
            print(f"[ERROR] Failed to start PostgreSQL server: {e}")
            print("        Application cannot start without PostgreSQL.")
        except (ValueError, OSError):
            pass
        sys.exit(1)


def stop_postgresql_server(server_state) -> None:
    """Stop the PostgreSQL server subprocess"""
    if server_state.postgresql_process is not None:
        try:
            print("[POSTGRESQL] Stopping PostgreSQL server...")
        except (ValueError, OSError):
            pass
        try:
            if sys.platform == 'win32':
                server_state.postgresql_process.terminate()
            else:
                if hasattr(os, 'getpgid') and hasattr(os, 'killpg'):
                    pgid = os.getpgid(server_state.postgresql_process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    server_state.postgresql_process.terminate()
            server_state.postgresql_process.wait(timeout=10)
        except (subprocess.TimeoutExpired, OSError, ProcessLookupError) as e:
            try:
                print(f"[POSTGRESQL] Error stopping server: {e}")
            except (ValueError, OSError):
                pass
            try:
                server_state.postgresql_process.kill()
            except (OSError, ProcessLookupError):
                pass
        server_state.postgresql_process = None
        try:
            print("[POSTGRESQL] Server stopped")
        except (ValueError, OSError):
            pass
