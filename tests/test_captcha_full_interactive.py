"""
Interactive Captcha Full Flow Concurrency Test
==============================================

Tests the complete captcha flow: generation (with image), storage, and verification.
Interactive mode - prompts for test parameters instead of command-line arguments.

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

# Import captcha generation dependencies
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise during testing
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Captcha generation constants (from routers/auth.py)
CAPTCHA_FONTS = [
    os.path.join('static', 'fonts', 'inter-600.ttf'),
    os.path.join('static', 'fonts', 'inter-700.ttf'),
]

CAPTCHA_COLORS = [
    '#E74C3C',  # Red
    '#F39C12',  # Orange
    '#F1C40F',  # Yellow
    '#27AE60',  # Green
    '#3498DB',  # Blue
    '#9B59B6',  # Purple
    '#E91E63',  # Pink
    '#16A085',  # Teal
]


def generate_captcha_code() -> str:
    """Generate a 4-character captcha code."""
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=4))


def generate_captcha_image(code: str) -> BytesIO:
    """
    Generate custom captcha image (simplified version of routers/auth.py).
    
    Args:
        code: The captcha code string to render (4 characters)
        
    Returns:
        BytesIO object containing PNG image data
    """
    width, height = 140, 50
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # Load font
    font_path = CAPTCHA_FONTS[1] if os.path.exists(CAPTCHA_FONTS[1]) else CAPTCHA_FONTS[0]
    try:
        font_size = int(height * 0.7)
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()
        font_size = 24
    
    # Measure characters
    char_widths = []
    char_bboxes = []
    
    for char in code:
        try:
            bbox = draw.textbbox((0, 0), char, font=font)
            char_width = bbox[2] - bbox[0]
            char_bboxes.append(bbox)
        except AttributeError:
            char_width, char_height = draw.textsize(char, font=font)
            char_bboxes.append((0, 0, char_width, char_height))
            char_width = char_width
        
        char_widths.append(char_width)
    
    # Calculate spacing
    total_char_width = sum(char_widths)
    padding = width * 0.08
    available_width = width - (padding * 2)
    spacing = (available_width - total_char_width) / (len(code) - 1) if len(code) > 1 else 0
    
    current_x = padding
    image_center_y = height / 2
    
    # Draw each character
    for i, char in enumerate(code):
        color = CAPTCHA_COLORS[i % len(CAPTCHA_COLORS)]
        bbox = char_bboxes[i]
        char_width = char_widths[i]
        char_height = bbox[3] - bbox[1]
        
        char_center_x = current_x + char_width / 2
        rotation = random.uniform(-10, 10)
        
        padding_size = max(char_width, char_height) * 0.6
        char_img_width = int(char_width + padding_size * 2)
        char_img_height = int(char_height + padding_size * 2)
        char_img = Image.new('RGBA', (char_img_width, char_img_height), (255, 255, 255, 0))
        char_draw = ImageDraw.Draw(char_img)
        
        text_x = char_img_width / 2 - bbox[0] - char_width / 2
        text_y = char_img_height / 2 - bbox[1] - char_height / 2
        char_draw.text((text_x, text_y), char, fill=color, font=font)
        
        rotated_char = char_img.rotate(rotation, center=(char_img_width/2, char_img_height/2), expand=False)
        
        paste_x = int(char_center_x - rotated_char.width / 2)
        paste_y = int(image_center_y - rotated_char.height / 2)
        
        if paste_x < 0:
            paste_x = 0
        elif paste_x + rotated_char.width > width:
            paste_x = width - rotated_char.width
            
        if paste_y < 0:
            paste_y = 0
        elif paste_y + rotated_char.height > height:
            paste_y = height - rotated_char.height
        
        image.paste(rotated_char, (paste_x, paste_y), rotated_char)
        current_x += char_width + spacing
    
    # Add noise
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        noise_color = random.choice(['#E0E0E0', '#E8E8E8', '#F0F0F0'])
        draw.line([(x1, y1), (x2, y2)], fill=noise_color, width=1)
    
    for _ in range(15):
        x = random.randint(0, width)
        y = random.randint(0, height)
        noise_color = random.choice(['#E0E0E0', '#E8E8E8'])
        draw.ellipse([x-1, y-1, x+1, y+1], fill=noise_color)
    
    image = image.filter(ImageFilter.SMOOTH)
    
    img_bytes = BytesIO()
    image.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes


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
                    # Verify the code matches (storage converts to uppercase)
                    # The actual codebase stores codes in uppercase
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
        if db_url.startswith("sqlite:////"):
            db_path = Path(db_url.replace("sqlite:////", "/"))
        elif db_url.startswith("sqlite:///"):
            db_path_str = db_url.replace("sqlite:///", "")
            if db_path_str.startswith("./"):
                db_path_str = db_path_str[2:]
            db_path = Path(db_path_str) if Path(db_path_str).is_absolute() else Path.cwd() / db_path_str
        else:
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
    max_workers: int = None
) -> Dict:
    """
    Run concurrent captcha full flow test.
    
    Args:
        num_users: Number of concurrent users to simulate
        duration_seconds: How long to run the test
        operations_per_user: Maximum operations per user
        max_workers: Max thread pool workers (default: num_users)
    
    Returns:
        Dict with test results
    """
    print(f"\n{'='*80}")
    print(f"CAPTCHA FULL FLOW CONCURRENCY TEST")
    print(f"{'='*80}")
    print(f"Database: {DATABASE_URL}")
    print(f"Concurrent Users: {num_users}")
    print(f"Test Duration: {duration_seconds} seconds")
    print(f"Operations per User: {operations_per_user}")
    print(f"Max Workers: {max_workers or num_users}")
    print(f"{'='*80}\n")
    
    # Initialize database
    print("Initializing database...")
    init_db()
    
    # Check WAL status before test
    wal_before = check_wal_status()
    print(f"\nWAL Status (Before Test):")
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
        # Get test parameters interactively
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

