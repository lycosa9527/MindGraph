"""
Interactive Captcha Full Flow Concurrency Test
==============================================

Tests the complete captcha flow: generation (with image), storage, and verification.
Interactive mode - prompts for test parameters instead of command-line arguments.

IMPORTANT: This test uses ACTUAL production code:
- Uses real captcha generation function from routers/auth.py
- Uses real SQLiteCaptchaStorage with actual SQLite database
- Uses actual SQLite WAL mode (verified at startup)
- Tests real database operations with WAL/SHM files

SAFETY: Test database is created in tests/ folder (tests/test_captcha.db)
- Completely isolated from production database
- Automatically cleaned up after test completes
- Production database is never touched

This ensures the test accurately reflects production behavior and performance.

Usage:
    python tests/test_captcha_full_interactive.py
"""

import time
import uuid
import random
import statistics
import base64
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
import sys
import os
import threading
from collections import defaultdict

# System monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.captcha_storage import SQLiteCaptchaStorage
from config.database import init_db, DATABASE_URL
import logging
import shutil

# Import actual captcha generation from routers/auth.py
from routers.auth import _generate_custom_captcha

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise during testing
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def generate_captcha_code() -> str:
    """Generate a 4-character captcha code (matches routers/auth.py)."""
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=4))


def generate_captcha_image(code: str) -> BytesIO:
    """
    Generate custom captcha image using the ACTUAL implementation from routers/auth.py.
    
    This ensures the test uses the exact same code as production, including:
    - Same font loading logic
    - Same character rendering with rotation
    - Same noise generation
    - Same image filtering
    
    Args:
        code: The captcha code string to render (4 characters)
        
    Returns:
        BytesIO object containing PNG image data
    """
    # Use actual production function - ensures 100% accuracy in testing
    return _generate_custom_captcha(code)


class ProgressTracker:
    """Thread-safe progress tracker for real-time updates."""
    
    def __init__(self, total_users: int, duration_seconds: float):
        self.total_users = total_users
        self.duration_seconds = duration_seconds
        self.completed_users = 0
        self.start_time = None
        self.lock = threading.Lock()
        self.operation_counts = defaultdict(int)
        self.last_update_time = 0
        self.update_interval = 0.5  # Update every 0.5 seconds
        
        # System monitoring
        self.cpu_percent = 0.0
        self.disk_read_mb_per_sec = 0.0
        self.disk_write_mb_per_sec = 0.0
        self.last_disk_io = None
        self.last_cpu_time = None
    
    def user_completed(self):
        """Mark a user as completed."""
        with self.lock:
            self.completed_users += 1
    
    def add_operation(self, op_type: str):
        """Record an operation."""
        with self.lock:
            self.operation_counts[op_type] += 1
    
    def update_system_stats(self):
        """Update CPU and disk I/O statistics."""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            # CPU usage
            self.cpu_percent = psutil.cpu_percent(interval=None)
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            if disk_io and self.last_disk_io:
                # Calculate MB/s
                time_diff = time.time() - self.last_cpu_time if self.last_cpu_time else 1.0
                if time_diff > 0:
                    read_diff = disk_io.read_bytes - self.last_disk_io.read_bytes
                    write_diff = disk_io.write_bytes - self.last_disk_io.write_bytes
                    self.disk_read_mb_per_sec = (read_diff / (1024 * 1024)) / time_diff
                    self.disk_write_mb_per_sec = (write_diff / (1024 * 1024)) / time_diff
            
            self.last_disk_io = disk_io
            self.last_cpu_time = time.time()
        except Exception as e:
            logger.debug(f"Failed to update system stats: {e}")
    
    def get_stats(self) -> Dict:
        """Get current statistics."""
        with self.lock:
            elapsed = time.time() - self.start_time if self.start_time else 0
            total_ops = sum(self.operation_counts.values())
            ops_per_sec = total_ops / elapsed if elapsed > 0 else 0
            return {
                "completed_users": self.completed_users,
                "total_users": self.total_users,
                "elapsed": elapsed,
                "duration_seconds": self.duration_seconds,
                "remaining": max(0, self.duration_seconds - elapsed),
                "total_operations": total_ops,
                "ops_per_sec": ops_per_sec,
                "operation_counts": dict(self.operation_counts),
                "cpu_percent": self.cpu_percent,
                "disk_read_mb_per_sec": self.disk_read_mb_per_sec,
                "disk_write_mb_per_sec": self.disk_write_mb_per_sec,
            }


class OperationResult:
    """Thread-safe result tracker for a single operation type."""
    
    def __init__(self, operation_type: str):
        self.operation_type = operation_type
        self._success_count = 0
        self._error_count = 0
        self._latencies: List[float] = []
        self._errors: List[str] = []
        self._lock = threading.Lock()
    
    def add_success(self, latency_ms: float):
        """Record a successful operation (thread-safe)."""
        with self._lock:
            self._success_count += 1
            self._latencies.append(latency_ms)
    
    def add_error(self, error_msg: str, latency_ms: float = 0):
        """Record a failed operation (thread-safe)."""
        with self._lock:
            self._error_count += 1
            self._errors.append(error_msg[:100])  # Limit error message length
            if latency_ms > 0:
                self._latencies.append(latency_ms)
    
    @property
    def success_count(self) -> int:
        """Get success count (thread-safe)."""
        with self._lock:
            return self._success_count
    
    @property
    def error_count(self) -> int:
        """Get error count (thread-safe)."""
        with self._lock:
            return self._error_count
    
    def get_stats(self) -> Dict:
        """Get statistics for this operation type (thread-safe snapshot)."""
        with self._lock:
            # Create a snapshot of current state
            latencies = self._latencies.copy()
            success_count = self._success_count
            error_count = self._error_count
        
        total_ops = success_count + error_count
        
        if not latencies:
            return {
                "operation": self.operation_type,
                "success_count": success_count,
                "error_count": error_count,
                "total_operations": total_ops,
                "success_rate": 0.0 if total_ops == 0 else success_count / total_ops,
                "avg_latency_ms": 0.0,
                "min_latency_ms": 0.0,
                "max_latency_ms": 0.0,
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
            }
        
        sorted_latencies = sorted(latencies)
        len_latencies = len(sorted_latencies)
        
        return {
            "operation": self.operation_type,
            "success_count": success_count,
            "error_count": error_count,
            "total_operations": total_ops,
            "success_rate": success_count / total_ops if total_ops > 0 else 0.0,
            "avg_latency_ms": statistics.mean(latencies),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "p50_latency_ms": statistics.median(sorted_latencies),
            "p95_latency_ms": sorted_latencies[int(len_latencies * 0.95)] if len_latencies > 0 else 0.0,
            "p99_latency_ms": sorted_latencies[int(len_latencies * 0.99)] if len_latencies > 0 else 0.0,
        }


def simulate_user_full_flow(
    user_id: int,
    storage: SQLiteCaptchaStorage,
    operations_per_user: int,
    duration_seconds: float,
    results: Dict[str, OperationResult],
    progress: Optional[ProgressTracker] = None
) -> Dict[str, int]:
    """
    Simulate a single user performing random captcha operations concurrently.
    This creates realistic stress testing by mixing all operations randomly.
    
    Operations performed:
    1. Generate captcha code + image (together)
    2. Store captcha
    3. Get captcha
    4. Verify captcha
    
    Returns:
        Dict with operation counts
    """
    end_time = time.time() + duration_seconds
    operation_counts = {
        "generate_code": 0,
        "generate_image": 0,
        "store": 0,
        "get": 0,
        "verify": 0,
        "errors": 0
    }
    
    # Store captcha IDs and codes for this user (for get/verify operations)
    user_captchas = {}  # {captcha_id: code}
    
    # Operation weights (higher = more frequent)
    # This simulates realistic usage: more generates/stores than gets/verifies
    operation_weights = {
        "generate_and_store": 40,  # Most common: new captcha generation
        "get": 25,                  # Retrieve existing captcha
        "verify": 25,                # Verify existing captcha
        "generate_only": 10,         # Just generate (no store)
    }
    
    total_ops = 0
    
    while time.time() < end_time and total_ops < operations_per_user:
        try:
            # Randomly choose operation type based on weights
            rand = random.random() * sum(operation_weights.values())
            cumulative = 0
            chosen_op = None
            
            for op, weight in operation_weights.items():
                cumulative += weight
                if rand <= cumulative:
                    chosen_op = op
                    break
            
            if chosen_op == "generate_and_store":
                # Generate code + image + store (most common flow)
                start = time.time()
                code = generate_captcha_code()
                code_latency = (time.time() - start) * 1000
                results["generate_code"].add_success(code_latency)
                operation_counts["generate_code"] += 1
                if progress:
                    progress.add_operation("generate_code")
                
                start = time.time()
                img_bytes = generate_captcha_image(code)
                # Image is generated but not used (simulating real flow)
                _ = base64.b64encode(img_bytes.getvalue()).decode()  # Simulate encoding
                img_latency = (time.time() - start) * 1000
                results["generate_image"].add_success(img_latency)
                operation_counts["generate_image"] += 1
                if progress:
                    progress.add_operation("generate_image")
                
                captcha_id = str(uuid.uuid4())
                start = time.time()
                storage.store(captcha_id, code, expires_in_seconds=300)
                store_latency = (time.time() - start) * 1000
                results["store"].add_success(store_latency)
                operation_counts["store"] += 1
                if progress:
                    progress.add_operation("store")
                
                # Store for later get/verify operations
                user_captchas[captcha_id] = code
                total_ops += 1
                
            elif chosen_op == "get" and user_captchas:
                # Get an existing captcha
                captcha_id = random.choice(list(user_captchas.keys()))
                expected_code = user_captchas[captcha_id]
                start = time.time()
                result = storage.get(captcha_id)
                latency = (time.time() - start) * 1000
                
                if result and result.get("code"):
                    # Verify the code matches
                    # Storage stores codes in uppercase (see captcha_storage.py line 64, 69)
                    # result["code"] is already uppercase, but we compare case-insensitively for safety
                    if result["code"].upper() == expected_code.upper():
                        results["get"].add_success(latency)
                        operation_counts["get"] += 1
                    else:
                        results["get"].add_error("code_mismatch", latency)
                        operation_counts["errors"] += 1
                        user_captchas.pop(captcha_id, None)
                else:
                    results["get"].add_error("not_found", latency)
                    operation_counts["errors"] += 1
                    # Remove if not found (might have expired)
                    user_captchas.pop(captcha_id, None)
                
                if progress:
                    progress.add_operation("get")
                total_ops += 1
                
            elif chosen_op == "verify" and user_captchas:
                # Verify an existing captcha
                # Note: verify_and_remove does case-insensitive comparison
                # and removes the captcha after verification (one-time use)
                captcha_id = random.choice(list(user_captchas.keys()))
                code = user_captchas[captcha_id]
                start = time.time()
                is_valid, error = storage.verify_and_remove(captcha_id, code)
                latency = (time.time() - start) * 1000
                
                if is_valid:
                    results["verify"].add_success(latency)
                    operation_counts["verify"] += 1
                else:
                    # Error could be: "not_found", "expired", "incorrect", or "error"
                    results["verify"].add_error(error or "unknown", latency)
                    operation_counts["errors"] += 1
                
                # Remove from our list (one-time use - captcha is deleted by verify_and_remove)
                user_captchas.pop(captcha_id, None)
                if progress:
                    progress.add_operation("verify")
                total_ops += 1
                
            elif chosen_op == "generate_only":
                # Just generate code + image (no store) - simulates failed generation
                start = time.time()
                code = generate_captcha_code()
                code_latency = (time.time() - start) * 1000
                results["generate_code"].add_success(code_latency)
                operation_counts["generate_code"] += 1
                if progress:
                    progress.add_operation("generate_code")
                
                start = time.time()
                img_bytes = generate_captcha_image(code)
                # Image is generated but not used (simulating real flow)
                _ = base64.b64encode(img_bytes.getvalue()).decode()  # Simulate encoding
                img_latency = (time.time() - start) * 1000
                results["generate_image"].add_success(img_latency)
                operation_counts["generate_image"] += 1
                if progress:
                    progress.add_operation("generate_image")
                
                total_ops += 1
            
            # Small random delay to avoid overwhelming the database
            time.sleep(random.uniform(0.005, 0.02))
            
        except Exception as e:
            operation_counts["errors"] += 1
            error_msg = str(e).lower()
            
            # Categorize errors appropriately
            if "database is locked" in error_msg or "database locked" in error_msg:
                # Try to attribute to the right operation type
                if not user_captchas or "store" in error_msg:
                    results["store"].add_error("database_locked", 0)
                else:
                    results["get"].add_error("database_locked", 0)
            elif "timeout" in error_msg or "busy" in error_msg:
                results["store"].add_error("timeout", 0)
            else:
                # Generic error - attribute to store as fallback
                results["store"].add_error(f"error: {str(e)[:50]}", 0)
    
    if progress:
        progress.user_completed()
    
    return operation_counts


def print_progress_bar(progress: ProgressTracker, results: Dict[str, OperationResult]):
    """Print a progress bar and real-time statistics."""
    # Update system stats
    progress.update_system_stats()
    stats = progress.get_stats()
    
    # Calculate progress percentage (based on time, since users complete at different rates)
    time_progress = min(100, (stats["elapsed"] / stats["duration_seconds"]) * 100) if stats["duration_seconds"] > 0 else 0
    user_progress = min(100, (stats["completed_users"] / stats["total_users"]) * 100) if stats["total_users"] > 0 else 0
    
    # Progress bar (50 characters wide) - use time-based progress
    bar_width = 50
    filled = int(bar_width * time_progress / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    
    # Calculate success rate
    total_success = sum(r.success_count for r in results.values())
    total_ops = sum(r.success_count + r.error_count for r in results.values())
    success_rate = (total_success / total_ops * 100) if total_ops > 0 else 0.0
    
    # Format time
    elapsed_str = f"{stats['elapsed']:.1f}s"
    remaining_str = f"{stats['remaining']:.1f}s" if stats['remaining'] > 0 else "0.0s"
    
    # Get operation breakdown from results (more accurate than progress tracker)
    generate_count = results["generate_code"].success_count + results["generate_image"].success_count
    store_count = results["store"].success_count
    get_count = results["get"].success_count
    verify_count = results["verify"].success_count
    
    # CPU and Disk I/O bars
    cpu_bar_width = 20
    cpu_filled = int(cpu_bar_width * min(100, stats.get('cpu_percent', 0)) / 100)
    cpu_bar = "█" * cpu_filled + "░" * (cpu_bar_width - cpu_filled)
    
    # Disk I/O (scale to reasonable max - 100 MB/s)
    disk_read_bar_width = 15
    disk_write_bar_width = 15
    max_disk_mb = 100.0
    disk_read_filled = int(disk_read_bar_width * min(100, (stats.get('disk_read_mb_per_sec', 0) / max_disk_mb) * 100) / 100)
    disk_write_filled = int(disk_write_bar_width * min(100, (stats.get('disk_write_mb_per_sec', 0) / max_disk_mb) * 100) / 100)
    disk_read_bar = "█" * disk_read_filled + "░" * (disk_read_bar_width - disk_read_filled)
    disk_write_bar = "█" * disk_write_filled + "░" * (disk_write_bar_width - disk_write_filled)
    
    # Clear screen and print progress (use ANSI escape codes)
    # Move cursor up 2 lines to overwrite previous output
    # Check if terminal supports ANSI codes (Windows compatibility)
    try:
        if sys.stdout.isatty():
            print("\033[2A\033[K", end="")  # Move up 2 lines and clear
            print("\033[K", end="")  # Clear current line
    except (AttributeError, OSError):
        # Fallback for terminals that don't support ANSI codes
        print("\n", end="")
    
    # Main progress bar
    print(f"[{bar}] {time_progress:.1f}% | "
          f"Users: {stats['completed_users']}/{stats['total_users']} ({user_progress:.1f}%) | "
          f"Generate: {generate_count} | Store: {store_count} | Get: {get_count} | Verify: {verify_count} | "
          f"Success: {success_rate:.1f}% | "
          f"Time: {elapsed_str}/{stats['duration_seconds']:.1f}s (Remaining: {remaining_str})")
    
    # System resources (CPU and Disk I/O)
    cpu_pct = stats.get('cpu_percent', 0)
    disk_read = stats.get('disk_read_mb_per_sec', 0)
    disk_write = stats.get('disk_write_mb_per_sec', 0)
    
    if PSUTIL_AVAILABLE:
        print(f"💻 CPU: [{cpu_bar}] {cpu_pct:.1f}% | "
              f"📀 Disk Read: [{disk_read_bar}] {disk_read:.2f} MB/s | "
              f"📀 Disk Write: [{disk_write_bar}] {disk_write:.2f} MB/s", 
              end="", flush=True)
    else:
        print(f"💻 CPU: N/A (psutil not available) | "
              f"📀 Disk I/O: N/A", 
              end="", flush=True)


def check_wal_status() -> Dict[str, any]:
    """Check WAL file status and size."""
    try:
        db_url = DATABASE_URL
        # Handle different SQLite URL formats
        if db_url.startswith("sqlite:////"):
            # Absolute path (4 slashes: sqlite:////absolute/path)
            # Remove sqlite://// and handle Windows paths correctly
            path_str = db_url.replace("sqlite:////", "")
            # Handle Windows absolute paths (C:/path) and Unix paths (/path)
            if os.path.isabs(path_str):
                db_path = Path(path_str)
            else:
                # Fallback: try as Unix-style absolute path
                db_path = Path("/" + path_str)
        elif db_url.startswith("sqlite:///"):
            # Relative or absolute path (3 slashes: sqlite:///./path or sqlite:///path)
            db_path_str = db_url.replace("sqlite:///", "")
            if db_path_str.startswith("./"):
                db_path_str = db_path_str[2:]
            # Check if it's an absolute path (handles Windows paths like C:/path)
            if os.path.isabs(db_path_str):
                db_path = Path(db_path_str)
            else:
                db_path = Path.cwd() / db_path_str
        else:
            # Fallback: assume it's a file path
            db_path = Path(db_url.replace("sqlite:///", ""))
        
        wal_path = Path(f"{db_path}-wal")
        shm_path = Path(f"{db_path}-shm")
        
        wal_size = wal_path.stat().st_size if wal_path.exists() else 0
        shm_size = shm_path.stat().st_size if shm_path.exists() else 0
        
        return {
            "wal_exists": wal_path.exists(),
            "wal_size_bytes": wal_size,
            "wal_size_mb": wal_size / (1024 * 1024),
            "shm_exists": shm_path.exists(),
            "shm_size_bytes": shm_size,
            "shm_size_mb": shm_size / (1024 * 1024),
        }
    except Exception as e:
        logger.warning(f"Failed to check WAL status: {e}")
        return {
            "wal_exists": False,
            "wal_size_bytes": 0,
            "wal_size_mb": 0,
            "shm_exists": False,
            "shm_size_bytes": 0,
            "shm_size_mb": 0,
        }


def setup_test_database(cleanup_after: bool = True) -> tuple[str, bool]:
    """
    Set up a test database for captcha testing.
    
    Creates a separate test database file in the tests/ folder to avoid affecting production data.
    The test database is completely isolated from the production database.
    
    Args:
        cleanup_after: Whether to clean up the database after test (default: True)
    
    Returns:
        Tuple of (test_db_path, should_cleanup)
    """
    # Create test database in tests/ directory (completely isolated from production)
    test_db_path = Path(__file__).parent / "test_captcha.db"
    test_db_path.parent.mkdir(exist_ok=True)
    
    # Clean up old test database if it exists
    if test_db_path.exists():
        print(f"Removing existing test database: {test_db_path}")
        try:
            # Close any existing connections first
            from config.database import engine
            engine.dispose()
        except Exception:
            pass
        
        # Remove database files
        for suffix in ["", "-wal", "-shm"]:
            db_file = Path(f"{test_db_path}{suffix}")
            if db_file.exists():
                try:
                    db_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove {db_file}: {e}")
    
    # Set environment variable to override DATABASE_URL
    # This ensures the test uses the test database
    original_db_url = os.environ.get("DATABASE_URL")
    # Use absolute path to avoid any confusion with relative paths
    test_db_absolute = test_db_path.resolve()
    test_db_url = f"sqlite:///{test_db_absolute.as_posix()}"
    os.environ["DATABASE_URL"] = test_db_url
    
    # Re-import to get updated DATABASE_URL
    import importlib
    import config.database
    importlib.reload(config.database)
    
    # Get the updated DATABASE_URL
    from config.database import DATABASE_URL as updated_db_url
    
    print(f"Test Database Location: {test_db_path}")
    print(f"Test Database URL: {updated_db_url}")
    print(f"✅ Test database is isolated in tests/ folder - production database is safe")
    
    return str(test_db_path), cleanup_after


def cleanup_test_database(test_db_path: str):
    """
    Clean up test database files.
    
    Args:
        test_db_path: Path to the test database file
    """
    print(f"\n{'='*80}")
    print("Cleaning up test database...")
    print(f"{'='*80}")
    
    db_path = Path(test_db_path)
    
    # Close database connections first
    try:
        from config.database import engine
        engine.dispose()
        # Small delay to ensure connections are closed
        time.sleep(0.1)
    except Exception as e:
        logger.debug(f"Error disposing engine: {e}")
    
    # Remove database files (main DB, WAL, SHM)
    removed_files = []
    for suffix in ["", "-wal", "-shm"]:
        db_file = Path(f"{db_path}{suffix}")
        if db_file.exists():
            try:
                db_file.unlink()
                removed_files.append(db_file.name)
            except Exception as e:
                logger.warning(f"Failed to remove {db_file}: {e}")
                # On Windows, file might still be locked - try again after a short delay
                time.sleep(0.2)
                try:
                    db_file.unlink()
                    removed_files.append(db_file.name)
                except Exception:
                    pass
    
    if removed_files:
        print(f"✅ Removed test database files: {', '.join(removed_files)}")
    else:
        print("ℹ️  No test database files to remove")
    
    # Restore original DATABASE_URL
    original_db_url = os.environ.pop("DATABASE_URL", None)
    if original_db_url and not original_db_url.endswith("test_captcha.db"):
        os.environ["DATABASE_URL"] = original_db_url
    elif "DATABASE_URL" in os.environ:
        # Remove test database URL
        del os.environ["DATABASE_URL"]
    
    # Reload database config to restore original settings
    try:
        import importlib
        import config.database
        importlib.reload(config.database)
    except Exception as e:
        logger.debug(f"Error reloading database config: {e}")


def verify_wal_mode() -> Dict[str, any]:
    """
    Verify that SQLite WAL mode is actually enabled.
    
    Returns:
        Dict with WAL mode status and journal mode
    """
    try:
        from sqlalchemy import text
        from config.database import engine
        
        with engine.connect() as conn:
            # Check journal mode (should be 'wal')
            result = conn.execute(text("PRAGMA journal_mode"))
            journal_mode = result.fetchone()[0].lower()
            
            # Check busy timeout (should be 5000ms)
            result = conn.execute(text("PRAGMA busy_timeout"))
            busy_timeout = result.fetchone()[0]
            
            wal_enabled = journal_mode == 'wal'
            
            return {
                "wal_enabled": wal_enabled,
                "journal_mode": journal_mode,
                "busy_timeout_ms": busy_timeout,
                "status": "✅ WAL mode enabled" if wal_enabled else f"⚠️  WAL mode NOT enabled (current: {journal_mode})"
            }
    except Exception as e:
        logger.warning(f"Failed to verify WAL mode: {e}")
        return {
            "wal_enabled": False,
            "journal_mode": "unknown",
            "busy_timeout_ms": 0,
            "status": f"❌ Failed to check WAL mode: {e}"
        }


def get_user_input(prompt: str, default: int = None, min_val: int = 1, max_val: int = None) -> int:
    """Get integer input from user with validation."""
    while True:
        try:
            if default is not None:
                user_input = input(f"{prompt} (default: {default}): ").strip()
                if not user_input:
                    return default
            else:
                user_input = input(f"{prompt}: ").strip()
            
            value = int(user_input)
            
            if value < min_val:
                print(f"Value must be at least {min_val}")
                continue
            
            if max_val is not None and value > max_val:
                print(f"Value must be at most {max_val}")
                continue
            
            return value
            
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("\n\nTest cancelled by user")
            sys.exit(0)


def run_concurrency_test(
    num_users: int,
    duration_seconds: float,
    operations_per_user: int,
    max_workers: int = None,
    cleanup_after: bool = True
) -> Dict:
    """
    Run concurrent captcha full flow test.
    
    Args:
        num_users: Number of concurrent users to simulate
        duration_seconds: How long to run the test
        operations_per_user: Maximum operations per user
        max_workers: Max thread pool workers (default: num_users)
        cleanup_after: Whether to clean up test database after test (default: True)
    
    Returns:
        Dict with test results
    """
    # Set up test database
    test_db_path, should_cleanup = setup_test_database(cleanup_after)
    
    try:
        print(f"\n{'='*80}")
        print(f"CAPTCHA FULL FLOW CONCURRENCY TEST")
        print(f"{'='*80}")
        print(f"Test Database: {test_db_path}")
        print(f"Concurrent Users: {num_users}")
        print(f"Test Duration: {duration_seconds} seconds")
        print(f"Operations per User: {operations_per_user}")
        print(f"Max Workers: {max_workers or num_users}")
        print(f"{'='*80}\n")
        
        # Initialize database
        print("Initializing test database...")
        init_db()
    
        # Verify WAL mode is enabled
        wal_mode_status = verify_wal_mode()
        print(f"\nSQLite WAL Mode Verification:")
        print(f"  {wal_mode_status['status']}")
        if wal_mode_status['wal_enabled']:
            print(f"  Journal Mode: {wal_mode_status['journal_mode'].upper()}")
            print(f"  Busy Timeout: {wal_mode_status['busy_timeout_ms']} ms")
        else:
            print(f"  ⚠️  WARNING: WAL mode is not enabled! Test may not reflect production behavior.")
            print(f"  Current journal mode: {wal_mode_status['journal_mode']}")
        
        # Check WAL status before test
        wal_before = check_wal_status()
        print(f"\nWAL File Status (Before Test):")
        print(f"  WAL file exists: {wal_before['wal_exists']}")
        if wal_before['wal_exists']:
            print(f"  WAL size: {wal_before['wal_size_mb']:.2f} MB")
        print(f"  SHM file exists: {wal_before['shm_exists']}")
        if wal_before['shm_exists']:
            print(f"  SHM size: {wal_before['shm_size_mb']:.2f} MB")
        
        # Initialize storage
        storage = SQLiteCaptchaStorage()
        
        # Initialize results tracking
        results = {
            "generate_code": OperationResult("generate_code"),
            "generate_image": OperationResult("generate_image"),
            "store": OperationResult("store"),
            "get": OperationResult("get"),
            "verify": OperationResult("verify"),
        }
        
        # Initialize progress tracker
        progress = ProgressTracker(num_users, duration_seconds)
        
        # Run test
        print(f"\n{'='*80}")
        print(f"🚀 Starting STRESS TEST with {num_users} concurrent users...")
        print(f"{'='*80}")
        print("🔥 Mixed Operations Mode: All operations happening randomly and concurrently!")
        print("   - Generate Code + Image + Store (40%)")
        print("   - Get existing captcha (25%)")
        print("   - Verify existing captcha (25%)")
        print("   - Generate only (10%)")
        print(f"\n{'─'*80}")
        print("📊 Real-time Progress:")
        print(f"{'─'*80}\n")
        
        # Initialize system monitoring baseline
        if PSUTIL_AVAILABLE:
            try:
                progress.last_disk_io = psutil.disk_io_counters()
                progress.last_cpu_time = time.time()
            except Exception:
                pass
        
        start_time = time.time()
        progress.start_time = start_time
        
        # Print initial empty lines for progress display (2 lines: progress bar + system stats)
        print("\n")
        
        # Start progress update thread
        stop_progress = threading.Event()
        
        def update_progress():
            """Update progress display periodically."""
            while not stop_progress.is_set():
                print_progress_bar(progress, results)
                time.sleep(0.5)  # Update every 0.5 seconds
        
        progress_thread = threading.Thread(target=update_progress, daemon=True)
        progress_thread.start()
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers or num_users) as executor:
                futures = []
                for user_id in range(num_users):
                    future = executor.submit(
                        simulate_user_full_flow,
                        user_id,
                        storage,
                        operations_per_user,
                        duration_seconds,
                        results,
                        progress
                    )
                    futures.append(future)
                
                # Wait for all users to complete
                user_results = []
                for future in as_completed(futures):
                    try:
                        user_result = future.result(timeout=duration_seconds + 10)
                        user_results.append(user_result)
                    except Exception as e:
                        logger.error(f"User simulation failed: {e}")
        finally:
            # Stop progress updates
            stop_progress.set()
            try:
                progress_thread.join(timeout=2)
            except Exception:
                pass  # Thread may have already finished
            
            # Final progress update
            try:
                print_progress_bar(progress, results)
                print("\n\n")  # New lines after progress bar
            except Exception:
                print("\n")  # Fallback if progress bar fails
            
            print(f"{'─'*80}")
            print("✅ Test completed! Compiling results...")
            print(f"{'─'*80}\n")
        
        end_time = time.time()
        actual_duration = end_time - start_time
        
        # Check WAL status after test
        wal_after = check_wal_status()
        
        # Compile results
        test_results = {
            "test_config": {
                "num_users": num_users,
                "duration_seconds": duration_seconds,
                "operations_per_user": operations_per_user,
                "actual_duration": actual_duration,
                "max_workers": max_workers or num_users,
            },
            "wal_status": {
                "before": wal_before,
                "after": wal_after,
                "wal_growth_mb": wal_after['wal_size_mb'] - wal_before['wal_size_mb'],
            },
            "results": {
                "generate_code": results["generate_code"].get_stats(),
                "generate_image": results["generate_image"].get_stats(),
                "store": results["store"].get_stats(),
                "get": results["get"].get_stats(),
                "verify": results["verify"].get_stats(),
            },
            "summary": {
                "total_operations": sum(r.get_stats()["total_operations"] for r in results.values()),
                "total_success": sum(r.get_stats()["success_count"] for r in results.values()),
                "total_errors": sum(r.get_stats()["error_count"] for r in results.values()),
                "overall_success_rate": 0.0,
                "operations_per_second": 0.0,
            }
        }
        
        # Calculate summary metrics
        total_ops = test_results["summary"]["total_operations"]
        if total_ops > 0:
            test_results["summary"]["overall_success_rate"] = test_results["summary"]["total_success"] / total_ops
            test_results["summary"]["operations_per_second"] = total_ops / actual_duration
        
        return test_results
    finally:
        # Clean up test database if requested (always runs, even on error)
        if should_cleanup:
            cleanup_test_database(test_db_path)


def run_capacity_test(
    start_users: int,
    max_users: int,
    duration_seconds: float,
    operations_per_user: int,
    target_workload_percent: float = 60.0,
    step_size: int = 5,
    stabilization_time: float = 5.0,
    cleanup_after: bool = True
) -> Dict:
    """
    Run capacity test to find how many users 1 worker can handle at target workload.
    
    Incrementally increases users until server reaches target workload (default 60%).
    Workload is calculated as a combination of CPU and disk I/O usage.
    
    Args:
        start_users: Starting number of users
        max_users: Maximum users to test (safety limit)
        duration_seconds: How long to run each test phase
        operations_per_user: Maximum operations per user
        target_workload_percent: Target combined workload percentage (default: 60%)
        step_size: Number of users to add per step
        stabilization_time: Time to wait for metrics to stabilize after adding users
    
    Returns:
        Dict with capacity test results
    """
    if not PSUTIL_AVAILABLE:
        print("ERROR: psutil is required for capacity testing. Install it with: pip install psutil")
        return {}
    
    # Set up test database
    test_db_path, should_cleanup = setup_test_database(cleanup_after)
    
    try:
        print(f"\n{'='*80}")
        print(f"CAPACITY TEST: Finding Users per Worker at {target_workload_percent}% Workload")
        print(f"{'='*80}")
        print(f"Test Database: {test_db_path}")
        print(f"Target Workload: {target_workload_percent}% (CPU + Disk I/O combined)")
        print(f"Starting Users: {start_users}")
        print(f"Max Users: {max_users}")
        print(f"Step Size: {step_size} users per increment")
        print(f"Test Duration per Phase: {duration_seconds} seconds")
        print(f"Stabilization Time: {stabilization_time} seconds")
        print(f"{'='*80}\n")
        
        # Initialize database
        print("Initializing test database...")
        init_db()
        
        # Verify WAL mode is enabled
        wal_mode_status = verify_wal_mode()
        print(f"\nSQLite WAL Mode Verification:")
        print(f"  {wal_mode_status['status']}")
        if wal_mode_status['wal_enabled']:
            print(f"  Journal Mode: {wal_mode_status['journal_mode'].upper()}")
            print(f"  Busy Timeout: {wal_mode_status['busy_timeout_ms']} ms")
        else:
            print(f"  ⚠️  WARNING: WAL mode is not enabled! Test may not reflect production behavior.")
            print(f"  Current journal mode: {wal_mode_status['journal_mode']}")
        
        # Check WAL status before test
        wal_before = check_wal_status()
        print(f"\nWAL File Status (Before Test):")
        print(f"  WAL file exists: {wal_before['wal_exists']}")
        if wal_before['wal_exists']:
            print(f"  WAL size: {wal_before['wal_size_mb']:.2f} MB")
        print(f"  SHM file exists: {wal_before['shm_exists']}")
        if wal_before['shm_exists']:
            print(f"  SHM size: {wal_before['shm_size_mb']:.2f} MB")
        
        # Initialize storage
        storage = SQLiteCaptchaStorage()
        
        # Baseline measurements (idle)
        print("\nMeasuring baseline system usage (idle)...")
        time.sleep(2)
        
        # Baseline CPU
        baseline_cpu_samples = []
        for _ in range(5):
            baseline_cpu_samples.append(psutil.cpu_percent(interval=0.5))
            time.sleep(0.5)
        baseline_cpu = statistics.mean(baseline_cpu_samples)
        
        # Baseline disk I/O
        baseline_disk_start = psutil.disk_io_counters()
        time.sleep(2)
        baseline_disk_end = psutil.disk_io_counters()
        baseline_time_diff = 2.0
        
        baseline_disk_read_mb_per_sec = 0.0
        baseline_disk_write_mb_per_sec = 0.0
        if baseline_disk_start and baseline_disk_end:
            read_diff = baseline_disk_end.read_bytes - baseline_disk_start.read_bytes
            write_diff = baseline_disk_end.write_bytes - baseline_disk_start.write_bytes
            baseline_disk_read_mb_per_sec = (read_diff / (1024 * 1024)) / baseline_time_diff
            baseline_disk_write_mb_per_sec = (write_diff / (1024 * 1024)) / baseline_time_diff
        
        # Define maximum expected disk I/O (for normalization)
        # These are reasonable maximums for a typical server - can be adjusted
        MAX_DISK_READ_MB_PER_SEC = 200.0  # 200 MB/s read
        MAX_DISK_WRITE_MB_PER_SEC = 100.0  # 100 MB/s write
        
        print(f"Baseline CPU: {baseline_cpu:.1f}%")
        print(f"Baseline Disk Read: {baseline_disk_read_mb_per_sec:.2f} MB/s")
        print(f"Baseline Disk Write: {baseline_disk_write_mb_per_sec:.2f} MB/s")
        
        current_users = start_users
        capacity_results = []
        max_workers = 1  # Testing with 1 worker
        
        print(f"\n{'='*80}")
        print(f"🚀 Starting Capacity Test...")
        print(f"{'='*80}\n")
        print(f"Phase | Users | CPU % | Disk R/W MB/s | Combined % | Status")
        print(f"{'─'*80}")
        
        while current_users <= max_users:
            # Initialize results tracking for this phase
            results = {
                "generate_code": OperationResult("generate_code"),
                "generate_image": OperationResult("generate_image"),
                "store": OperationResult("store"),
                "get": OperationResult("get"),
                "verify": OperationResult("verify"),
            }
            
            # Initialize progress tracker
            progress = ProgressTracker(current_users, duration_seconds)
            
            # Initialize system monitoring baseline
            try:
                progress.last_disk_io = psutil.disk_io_counters()
                progress.last_cpu_time = time.time()
            except Exception:
                pass
            
            start_time = time.time()
            progress.start_time = start_time
            
            # Initialize variables in case of early exception
            avg_cpu = 0.0
            net_cpu = 0.0
            avg_disk_read_mb_per_sec = 0.0
            avg_disk_write_mb_per_sec = 0.0
            net_disk_read = 0.0
            net_disk_write = 0.0
            disk_read_percent = 0.0
            disk_write_percent = 0.0
            combined_workload = 0.0
            
            # Run test phase
            phase_success = False
            try:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = []
                    for user_id in range(current_users):
                        future = executor.submit(
                            simulate_user_full_flow,
                            user_id,
                            storage,
                            operations_per_user,
                            duration_seconds,
                            results,
                            progress
                        )
                        futures.append(future)
                    
                    # Wait for stabilization period, then measure system metrics
                    time.sleep(stabilization_time)
                    
                    # Measure CPU and disk I/O during active load
                    cpu_samples = []
                    disk_read_samples = []
                    disk_write_samples = []
                    
                    # Get initial disk I/O counter
                    disk_io_start = psutil.disk_io_counters()
                    measurement_start_time = time.time()
                    
                    for _ in range(10):  # Sample 10 times over 5 seconds
                        cpu_percent = psutil.cpu_percent(interval=0.5)
                        cpu_samples.append(cpu_percent)
                        progress.update_system_stats()
                    
                    # Get final disk I/O counter
                    disk_io_end = psutil.disk_io_counters()
                    measurement_duration = time.time() - measurement_start_time
                    
                    # Calculate average CPU
                    avg_cpu = statistics.mean(cpu_samples)
                    
                    # Calculate disk I/O rates
                    avg_disk_read_mb_per_sec = 0.0
                    avg_disk_write_mb_per_sec = 0.0
                    if disk_io_start and disk_io_end and measurement_duration > 0:
                        read_diff = disk_io_end.read_bytes - disk_io_start.read_bytes
                        write_diff = disk_io_end.write_bytes - disk_io_start.write_bytes
                        avg_disk_read_mb_per_sec = (read_diff / (1024 * 1024)) / measurement_duration
                        avg_disk_write_mb_per_sec = (write_diff / (1024 * 1024)) / measurement_duration
                    
                    # Calculate net disk I/O (excluding baseline)
                    net_disk_read = max(0, avg_disk_read_mb_per_sec - baseline_disk_read_mb_per_sec)
                    net_disk_write = max(0, avg_disk_write_mb_per_sec - baseline_disk_write_mb_per_sec)
                    
                    # Calculate normalized disk usage (0-100%)
                    disk_read_percent = min(100, (net_disk_read / MAX_DISK_READ_MB_PER_SEC) * 100) if MAX_DISK_READ_MB_PER_SEC > 0 else 0
                    disk_write_percent = min(100, (net_disk_write / MAX_DISK_WRITE_MB_PER_SEC) * 100) if MAX_DISK_WRITE_MB_PER_SEC > 0 else 0
                    
                    # Calculate combined workload (weighted: 60% CPU, 20% disk read, 20% disk write)
                    # Net CPU (excluding baseline)
                    net_cpu = max(0, avg_cpu - baseline_cpu)
                    combined_workload = (net_cpu * 0.6) + (disk_read_percent * 0.2) + (disk_write_percent * 0.2)
                    
                    # Wait for all users to complete
                    user_results = []
                    for future in as_completed(futures):
                        try:
                            user_result = future.result(timeout=duration_seconds + 10)
                            user_results.append(user_result)
                        except Exception as e:
                            logger.error(f"User simulation failed: {e}")
                
                phase_success = True
            except Exception as e:
                logger.error(f"Test phase failed: {e}")
                # If phase failed, skip storing results and break
                break
            
            # Only store phase results if phase completed successfully
            if phase_success:
                end_time = time.time()
                actual_duration = end_time - start_time
                
                # Calculate summary metrics
                total_ops = sum(r.get_stats()["total_operations"] for r in results.values())
                total_success = sum(r.get_stats()["success_count"] for r in results.values())
                success_rate = (total_success / total_ops * 100) if total_ops > 0 else 0.0
                ops_per_sec = total_ops / actual_duration if actual_duration > 0 else 0.0
                
                # Store phase results
                phase_result = {
                "users": current_users,
                "cpu_percent": avg_cpu,
                "baseline_cpu": baseline_cpu,
                "net_cpu": net_cpu,
                "disk_read_mb_per_sec": avg_disk_read_mb_per_sec,
                "disk_write_mb_per_sec": avg_disk_write_mb_per_sec,
                "net_disk_read_mb_per_sec": net_disk_read,
                "net_disk_write_mb_per_sec": net_disk_write,
                "disk_read_percent": disk_read_percent,
                "disk_write_percent": disk_write_percent,
                "combined_workload_percent": combined_workload,
                "total_operations": total_ops,
                "success_rate": success_rate,
                    "operations_per_second": ops_per_sec,
                    "duration": actual_duration,
                }
                capacity_results.append(phase_result)
                
                # Print phase status
                disk_info = f"{net_disk_read:.1f}/{net_disk_write:.1f}"
                status = "✅ OK"
                if combined_workload >= target_workload_percent:
                    status = f"🎯 TARGET REACHED ({target_workload_percent}%)"
                elif combined_workload > target_workload_percent * 0.9:
                    status = "⚠️  APPROACHING TARGET"
                
                print(f"  {len(capacity_results):3d}  | {current_users:5d} | {avg_cpu:5.1f}% | {disk_info:15s} | {combined_workload:6.1f}% | {status}")
                
                # Check if we've reached target workload
                if combined_workload >= target_workload_percent:
                    print(f"\n{'─'*80}")
                    print(f"✅ Target workload ({target_workload_percent}%) reached at {current_users} users!")
                    print(f"   CPU: {avg_cpu:.1f}% | Disk Read: {net_disk_read:.2f} MB/s | Disk Write: {net_disk_write:.2f} MB/s")
                    break
                
                # Increment users for next phase
                current_users += step_size
                
                # Small delay between phases
                time.sleep(1)
        
        # Check WAL status after test
        wal_after = check_wal_status()
        
        # Find the phase closest to target workload
        target_phase = None
        min_diff = float('inf')
        for phase in capacity_results:
            diff = abs(phase['combined_workload_percent'] - target_workload_percent)
            if diff < min_diff:
                min_diff = diff
                target_phase = phase
        
        # Compile final results
        test_results = {
            "test_type": "capacity_test",
            "test_config": {
                "start_users": start_users,
                "max_users": max_users,
                "target_workload_percent": target_workload_percent,
                "step_size": step_size,
                "duration_seconds": duration_seconds,
                "operations_per_user": operations_per_user,
                "max_workers": max_workers,
                "baseline_cpu": baseline_cpu,
                "baseline_disk_read_mb_per_sec": baseline_disk_read_mb_per_sec,
                "baseline_disk_write_mb_per_sec": baseline_disk_write_mb_per_sec,
                "max_disk_read_mb_per_sec": MAX_DISK_READ_MB_PER_SEC,
                "max_disk_write_mb_per_sec": MAX_DISK_WRITE_MB_PER_SEC,
            },
            "wal_status": {
                "before": wal_before,
                "after": wal_after,
                "wal_growth_mb": wal_after['wal_size_mb'] - wal_before['wal_size_mb'],
            },
            "phases": capacity_results,
            "capacity": {
                "users_at_target": target_phase['users'] if target_phase else None,
                "cpu_at_target": target_phase['cpu_percent'] if target_phase else None,
                "combined_workload_at_target": target_phase['combined_workload_percent'] if target_phase else None,
                "disk_read_at_target": target_phase['net_disk_read_mb_per_sec'] if target_phase else None,
                "disk_write_at_target": target_phase['net_disk_write_mb_per_sec'] if target_phase else None,
                "users_per_worker": target_phase['users'] if target_phase else None,
                "operations_per_second_at_target": target_phase['operations_per_second'] if target_phase else None,
                "success_rate_at_target": target_phase['success_rate'] if target_phase else None,
            }
        }
        
        return test_results
    finally:
        # Clean up test database if requested (always runs, even on error)
        if should_cleanup:
            cleanup_test_database(test_db_path)


def print_results(results: Dict):
    """Print test results in a readable format."""
    print(f"\n{'='*80}")
    print(f"📋 TEST RESULTS")
    print(f"{'='*80}\n")
    
    config = results["test_config"]
    users_per_worker = config['num_users'] / config['max_workers'] if config['max_workers'] > 0 else config['num_users']
    
    print(f"Configuration:")
    print(f"  Total Concurrent Users: {config['num_users']}")
    print(f"  Thread Pool Workers: {config['max_workers']}")
    print(f"  Users per Worker: {users_per_worker:.1f}")
    print(f"  Test Duration: {config['duration_seconds']:.1f}s (actual: {config['actual_duration']:.1f}s)")
    print(f"  Operations per User: {config['operations_per_user']}")
    
    summary = results["summary"]
    print(f"\nSummary:")
    print(f"  Total Operations: {summary['total_operations']}")
    print(f"  Successful: {summary['total_success']}")
    print(f"  Errors: {summary['total_errors']}")
    print(f"  Success Rate: {summary['overall_success_rate']*100:.2f}%")
    print(f"  Throughput: {summary['operations_per_second']:.2f} ops/sec")
    
    wal_status = results["wal_status"]
    print(f"\nWAL File Status:")
    print(f"  WAL Before: {wal_status['before']['wal_size_mb']:.2f} MB")
    print(f"  WAL After: {wal_status['after']['wal_size_mb']:.2f} MB")
    print(f"  WAL Growth: {wal_status['wal_growth_mb']:.2f} MB")
    print(f"  SHM Before: {wal_status['before']['shm_size_mb']:.2f} MB")
    print(f"  SHM After: {wal_status['after']['shm_size_mb']:.2f} MB")
    
    print(f"\n📊 Operation Details:")
    print(f"{'─'*80}")
    for op_type in ["generate_code", "generate_image", "store", "get", "verify"]:
        op_stats = results["results"][op_type]
        op_name = op_type.replace('_', ' ').title()
        status_icon = "✅" if op_stats['success_rate'] > 0.95 else "⚠️" if op_stats['success_rate'] > 0.90 else "❌"
        print(f"\n  {status_icon} {op_name}:")
        print(f"    Total: {op_stats['total_operations']}")
        print(f"    Success: {op_stats['success_count']} ({op_stats['success_rate']*100:.2f}%)")
        if op_stats['error_count'] > 0:
            print(f"    Errors: {op_stats['error_count']}")
        if op_stats['success_count'] > 0:
            print(f"    Latency (ms):")
            print(f"      Avg:  {op_stats['avg_latency_ms']:.2f}")
            print(f"      Min:  {op_stats['min_latency_ms']:.2f}")
            print(f"      Max:  {op_stats['max_latency_ms']:.2f}")
            print(f"      P50:  {op_stats['p50_latency_ms']:.2f}")
            print(f"      P95:  {op_stats['p95_latency_ms']:.2f}")
            print(f"      P99:  {op_stats['p99_latency_ms']:.2f}")
    
    # Analysis
    print(f"\n{'='*80}")
    print(f"📈 ANALYSIS")
    print(f"{'='*80}\n")
    
    if summary['overall_success_rate'] < 0.95:
        print("⚠️  WARNING: Success rate below 95% - may indicate concurrency issues")
    
    if "database_locked" in str(results["results"]):
        print("⚠️  WARNING: Database lock errors detected - SQLite may be hitting concurrency limits")
    
    # Estimate concurrent user capacity
    if summary['operations_per_second'] > 0:
        # Calculate average operations per user per second
        total_user_seconds = config['num_users'] * config['actual_duration']
        ops_per_user_per_sec = summary['total_operations'] / total_user_seconds if total_user_seconds > 0 else 0
        
        # Estimate capacity based on maintaining 80% of current throughput
        # This gives a conservative estimate
        if ops_per_user_per_sec > 0:
            target_ops_per_sec = summary['operations_per_second'] * 0.8
            estimated_total_capacity = int(target_ops_per_sec / ops_per_user_per_sec)
        else:
            estimated_total_capacity = 0
        
        # For multi-worker scenarios (like Gunicorn), estimate per-worker capacity
        # Assuming similar worker distribution
        if config['max_workers'] > 0 and estimated_total_capacity > 0:
            estimated_per_worker = int(estimated_total_capacity / config['max_workers'])
        else:
            estimated_per_worker = estimated_total_capacity
        
        users_per_worker = config['num_users'] / config['max_workers'] if config['max_workers'] > 0 else config['num_users']
        
        print(f"💡 Capacity Analysis:")
        print(f"   Current Test: {config['num_users']} total users ({users_per_worker:.1f} per worker)")
        print(f"   Throughput: {summary['operations_per_second']:.2f} ops/sec")
        print(f"   Operations per user per second: {ops_per_user_per_sec:.3f}")
        print(f"\n   📊 Estimated Safe Capacity:")
        print(f"      Total concurrent users (all workers): ~{estimated_total_capacity}")
        print(f"      Per worker (if using {config['max_workers']} workers): ~{estimated_per_worker} users")
        print(f"\n   ⚠️  Note: This assumes:")
        print(f"      - Similar operation mix (40% generate+store, 25% get, 25% verify, 10% generate-only)")
        print(f"      - SQLite WAL mode with 5s busy timeout")
        print(f"      - Single database instance (shared across all workers)")
        print(f"      - For multi-process deployments (Gunicorn), each process shares the same SQLite DB")
    
    print(f"\n{'='*80}\n")


def print_capacity_results(results: Dict):
    """Print capacity test results in a readable format."""
    print(f"\n{'='*80}")
    print(f"📋 CAPACITY TEST RESULTS")
    print(f"{'='*80}\n")
    
    config = results["test_config"]
    capacity = results["capacity"]
    
    print(f"Configuration:")
    print(f"  Target Workload: {config['target_workload_percent']}% (CPU + Disk I/O combined)")
    print(f"  Baseline CPU: {config['baseline_cpu']:.1f}%")
    print(f"  Baseline Disk Read: {config.get('baseline_disk_read_mb_per_sec', 0):.2f} MB/s")
    print(f"  Baseline Disk Write: {config.get('baseline_disk_write_mb_per_sec', 0):.2f} MB/s")
    print(f"  Max Workers: {config['max_workers']} (testing 1 worker capacity)")
    print(f"  Test Duration per Phase: {config['duration_seconds']:.1f}s")
    print(f"  Operations per User: {config['operations_per_user']}")
    print(f"  Step Size: {config['step_size']} users per increment")
    print(f"  Workload Formula: 60% CPU + 20% Disk Read + 20% Disk Write")
    
    print(f"\n{'='*80}")
    print(f"🎯 CAPACITY FINDINGS")
    print(f"{'='*80}\n")
    
    if capacity['users_at_target']:
        print(f"✅ Capacity at {config['target_workload_percent']}% Combined Workload:")
        print(f"   Users per Worker: {capacity['users_per_worker']}")
        print(f"   Combined Workload: {capacity['combined_workload_at_target']:.1f}%")
        print(f"   CPU Usage: {capacity['cpu_at_target']:.1f}%")
        print(f"   Disk Read: {capacity['disk_read_at_target']:.2f} MB/s")
        print(f"   Disk Write: {capacity['disk_write_at_target']:.2f} MB/s")
        print(f"   Operations per Second: {capacity['operations_per_second_at_target']:.2f}")
        print(f"   Success Rate: {capacity['success_rate_at_target']:.2f}%")
    else:
        print(f"⚠️  Target workload ({config['target_workload_percent']}%) not reached")
        print(f"   Maximum users tested: {config['max_users']}")
        if results['phases']:
            last_phase = results['phases'][-1]
            print(f"   Last Combined Workload: {last_phase.get('combined_workload_percent', 0):.1f}%")
            print(f"   Last CPU reading: {last_phase['cpu_percent']:.1f}%")
    
    print(f"\n{'='*80}")
    print(f"📊 PHASE DETAILS")
    print(f"{'='*80}\n")
    print(f"{'Phase':<8} {'Users':<8} {'CPU %':<10} {'Disk R/W':<15} {'Combined %':<12} {'Ops/sec':<12} {'Success %':<12}")
    print(f"{'─'*80}")
    
    if results['phases']:
        for i, phase in enumerate(results['phases'], 1):
            disk_info = f"{phase.get('net_disk_read_mb_per_sec', 0):.1f}/{phase.get('net_disk_write_mb_per_sec', 0):.1f}"
            combined = phase.get('combined_workload_percent', 0)
            print(f"{i:<8} {phase['users']:<8} {phase['cpu_percent']:<10.1f} {disk_info:<15s} {combined:<12.1f} "
                  f"{phase['operations_per_second']:<12.2f} {phase['success_rate']:<12.2f}")
    else:
        print("  No phases completed.")
    
    wal_status = results["wal_status"]
    print(f"\nWAL File Status:")
    print(f"  WAL Before: {wal_status['before']['wal_size_mb']:.2f} MB")
    print(f"  WAL After: {wal_status['after']['wal_size_mb']:.2f} MB")
    print(f"  WAL Growth: {wal_status['wal_growth_mb']:.2f} MB")
    
    print(f"\n{'='*80}")
    print(f"💡 ANALYSIS")
    print(f"{'='*80}\n")
    
    if capacity['users_at_target']:
        print(f"Based on this test, 1 worker can handle approximately {capacity['users_per_worker']} users")
        print(f"while maintaining {config['target_workload_percent']}% combined workload (CPU + Disk I/O).")
        print(f"\nFor multi-worker deployments:")
        print(f"  - Per-worker capacity: ~{capacity['users_per_worker']} users")
        print(f"  - Example: With 4 workers, estimated total capacity: ~{capacity['users_per_worker'] * 4} users")
        print(f"\n⚠️  Note: Actual capacity may vary based on:")
        print(f"  - Server hardware specifications")
        print(f"  - Database performance (SQLite WAL mode)")
        print(f"  - Disk I/O performance (SSD vs HDD)")
        print(f"  - Network latency")
        print(f"  - Other system processes")
        print(f"\n💡 Workload Calculation:")
        print(f"   Combined Workload = (Net CPU % × 0.6) + (Disk Read % × 0.2) + (Disk Write % × 0.2)")
        print(f"   Where Disk % = (Actual MB/s / Max Expected MB/s) × 100")
    else:
        print(f"⚠️  Could not determine capacity - target workload not reached.")
        print(f"   Consider increasing max_users or checking system resources.")
    
    print(f"\n{'='*80}\n")


def print_banner():
    """Display the MindGraph ASCII banner for the test tool."""
    banner = """
    ███╗   ███╗██╗███╗   ██╗██████╗ ███╗   ███╗ █████╗ ████████╗███████╗
    ████╗ ████║██║████╗  ██║██╔══██╗████╗ ████║██╔══██╗╚══██╔══╝██╔════╝
    ██╔████╔██║██║██╔██╗ ██║██║  ██║██╔████╔██║███████║   ██║   █████╗  
    ██║╚██╔╝██║██║██║╚██╗██║██║  ██║██║╚██╔╝██║██╔══██║   ██║   ██╔══╝  
    ██║ ╚═╝ ██║██║██║ ╚████║██████╔╝██║ ╚═╝ ██║██║  ██║   ██║   ███████╗
    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝
================================================================================
    Captcha Storage Concurrency Stress Test Tool
    ============================================
    SQLite WAL Mode Performance Testing & Capacity Analysis
    """
    print(banner)


def main():
    """Main entry point with interactive prompts."""
    # Print banner
    print_banner()
    
    print("\nThis test simulates the complete captcha flow:")
    print("  1. Generate captcha code")
    print("  2. Generate captcha image")
    print("  3. Store captcha in database")
    print("  4. Get captcha from database")
    print("  5. Verify captcha code")
    print("\n" + "-"*80 + "\n")
    
    try:
        # Choose test mode
        print("Test Modes:")
        print("  1. Standard Concurrency Test (fixed number of users)")
        print("  2. Capacity Test (find users per worker at 60% workload - CPU + Disk I/O)")
        print()
        
        test_mode_input = input("Select test mode (1 or 2, default: 1): ").strip()
        test_mode = int(test_mode_input) if test_mode_input.isdigit() else 1
        
        if test_mode not in [1, 2]:
            print("Invalid selection, using default: Standard Concurrency Test")
            test_mode = 1
        
        if test_mode == 2:
            # Capacity test mode
            if not PSUTIL_AVAILABLE:
                print("\nERROR: Capacity test requires psutil.")
                print("Install it with: pip install psutil")
                print("\nFalling back to standard concurrency test...")
                test_mode = 1
            else:
                print(f"\n{'='*80}")
                print("CAPACITY TEST MODE")
                print(f"{'='*80}")
                print("This test will incrementally increase users until server reaches 60% combined workload.")
                print("Workload is calculated as: 60% CPU + 20% Disk Read + 20% Disk Write")
                print("It will report how many users 1 worker can handle at that workload.")
                print(f"{'='*80}\n")
                
                start_users = get_user_input(
                    "Enter starting number of users",
                    default=10,
                    min_val=1,
                    max_val=100
                )
                
                max_users = get_user_input(
                    "Enter maximum users to test (safety limit)",
                    default=200,
                    min_val=start_users,
                    max_val=1000
                )
                
                duration = get_user_input(
                    "Enter test duration per phase in seconds",
                    default=15,
                    min_val=5,
                    max_val=120
                )
                
                operations = get_user_input(
                    "Enter maximum operations per user",
                    default=20,
                    min_val=1,
                    max_val=1000
                )
                
                step_size_input = input(f"Enter step size (users to add per increment, default: 5): ").strip()
                step_size = int(step_size_input) if step_size_input.isdigit() else 5
                if step_size < 1 or step_size > 50:
                    print(f"Invalid step_size, using default: 5")
                    step_size = 5
                
                target_workload_input = input(f"Enter target workload percentage (default: 60): ").strip()
                target_workload = float(target_workload_input) if target_workload_input.replace('.', '').isdigit() else 60.0
                if target_workload < 10 or target_workload > 90:
                    print(f"Invalid target workload, using default: 60%")
                    target_workload = 60.0
                
                print(f"\n{'='*80}")
                print("Starting capacity test...")
                print(f"{'='*80}\n")
                
                results = run_capacity_test(
                    start_users=start_users,
                    max_users=max_users,
                    duration_seconds=float(duration),
                    operations_per_user=operations,
                    target_workload_percent=target_workload,
                    step_size=step_size
                )
                
                print_capacity_results(results)
        
        if test_mode == 1:
            # Standard concurrency test mode
            num_users = get_user_input(
                "Enter number of concurrent users to simulate",
                default=50,
                min_val=1,
                max_val=1000
            )
            
            duration = get_user_input(
                "Enter test duration in seconds",
                default=30,
                min_val=5,
                max_val=300
            )
            
            operations = get_user_input(
                "Enter maximum operations per user",
                default=20,
                min_val=1,
                max_val=1000
            )
            
            max_workers_input = input(f"Enter max thread pool workers (default: {num_users}, press Enter to use default): ").strip()
            max_workers = int(max_workers_input) if max_workers_input else None
            
            if max_workers is not None and (max_workers < 1 or max_workers > 1000):
                print(f"Invalid max_workers, using default: {num_users}")
                max_workers = None
            
            print(f"\n{'='*80}")
            print("Starting test...")
            print(f"{'='*80}\n")
            
            results = run_concurrency_test(
                num_users=num_users,
                duration_seconds=float(duration),
                operations_per_user=operations,
                max_workers=max_workers
            )
            
            print_results(results)
        
        # Ask if user wants to run another test
        print("\n" + "-"*80)
        another_test = input("Run another test? (y/n): ").strip().lower()
        if another_test == 'y':
            main()
        else:
            print("\nTest completed. Thank you!")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

