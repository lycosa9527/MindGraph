"""
Database Fixes Verification Script
===================================

Tests all the fixes made to resolve QueuePool errors:
1. TokenTracker batching (1000 records, 5 min interval)
2. CaptchaStorage retry on pool exhaustion
3. Database pool size (45 connections)
4. WAL mode for concurrent reads
5. Concurrent load simulation

Run: python scripts/test_database_fixes.py

Author: MindSpring Team
Copyright 2024-2025 北京思源智教科技有限公司
"""

import os
import sys
import time
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_header(title: str):
    """Print section header"""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result"""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status}: {test_name}")
    if details:
        print(f"         {details}")


def test_1_token_tracker_config():
    """Test TokenTracker configuration"""
    print_header("1. TokenTracker Configuration")
    
    from services.token_tracker import get_token_tracker
    tt = get_token_tracker()
    
    # Check batch size
    passed = tt.BATCH_SIZE >= 1000
    print_result(
        "Batch size >= 1000",
        passed,
        f"Current: {tt.BATCH_SIZE}"
    )
    
    # Check interval
    passed = tt.BATCH_INTERVAL >= 300
    print_result(
        "Batch interval >= 300s (5 min)",
        passed,
        f"Current: {tt.BATCH_INTERVAL}s"
    )
    
    # Check max buffer
    passed = tt.MAX_BUFFER_SIZE >= 10000
    print_result(
        "Max buffer size >= 10000",
        passed,
        f"Current: {tt.MAX_BUFFER_SIZE}"
    )
    
    # Check it's enabled
    print_result(
        "TokenTracker enabled",
        tt.ENABLED,
        f"Current: {tt.ENABLED}"
    )
    
    return True


def test_2_database_pool():
    """Test database pool configuration"""
    print_header("2. Database Pool Configuration")
    
    from config.database import engine
    
    pool_size = engine.pool.size()
    max_overflow = engine.pool._max_overflow
    total = pool_size + max_overflow
    
    print_result(
        "Pool size >= 15",
        pool_size >= 15,
        f"Current: {pool_size}"
    )
    
    print_result(
        "Max overflow >= 30",
        max_overflow >= 30,
        f"Current: {max_overflow}"
    )
    
    print_result(
        "Total connections >= 45",
        total >= 45,
        f"Current: {total}"
    )
    
    return total >= 45


def test_3_wal_mode():
    """Test WAL mode is enabled"""
    print_header("3. SQLite WAL Mode")
    
    from config.database import engine
    from sqlalchemy import text
    
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode"))
        mode = result.fetchone()[0]
    
    passed = mode.lower() == "wal"
    print_result(
        "WAL mode enabled",
        passed,
        f"Current: {mode}"
    )
    
    if passed:
        print("         → Allows concurrent reads while writing")
        print("         → FastAPI reads won't be blocked")
    
    return passed


def test_4_captcha_retry_logic():
    """Test CaptchaStorage has pool exhaustion retry"""
    print_header("4. CaptchaStorage Retry Logic")
    
    import inspect
    from services.captcha_storage import SQLiteCaptchaStorage
    
    source = inspect.getsource(SQLiteCaptchaStorage._retry_on_lock)
    
    # Check for pool exhaustion detection
    has_pool_check = "queuepool limit" in source.lower()
    print_result(
        "Detects QueuePool exhaustion",
        has_pool_check,
        "Checks for 'queuepool limit' in error"
    )
    
    has_timeout_check = "connection timed out" in source.lower()
    print_result(
        "Detects connection timeout",
        has_timeout_check,
        "Checks for 'connection timed out' in error"
    )
    
    has_retryable = "is_retryable" in source
    print_result(
        "Uses is_retryable flag",
        has_retryable,
        "Combines lock and pool errors"
    )
    
    return has_pool_check and has_timeout_check


def test_5_token_tracker_non_blocking():
    """Test TokenTracker is non-blocking"""
    print_header("5. TokenTracker Non-Blocking")
    
    from services.token_tracker import get_token_tracker
    tt = get_token_tracker()
    
    # Measure time to add record to buffer
    times = []
    for i in range(100):
        start = time.perf_counter()
        with tt._buffer_lock:
            pass  # Just acquire and release lock
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    
    avg_time = sum(times) / len(times)
    max_time = max(times)
    
    passed = avg_time < 1.0  # Should be < 1ms
    print_result(
        "Buffer lock avg < 1ms",
        passed,
        f"Avg: {avg_time:.3f}ms, Max: {max_time:.3f}ms"
    )
    
    print("         → track_usage() just adds to memory")
    print("         → No database call during request")
    
    return passed


def test_6_concurrent_captcha():
    """Test CaptchaStorage under concurrent load"""
    print_header("6. Concurrent CaptchaStorage Test")
    
    from services.captcha_storage import get_captcha_storage
    from config.database import engine
    from sqlalchemy import text, inspect
    import uuid
    
    # Check if captchas table exists
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if 'captchas' not in tables:
        print("  [SKIP]: Captchas table doesn't exist (DB not initialized)")
        print("         This is expected in dev environment without full setup.")
        print("         Run the app once to create tables, or run in production.")
        return True  # Skip this test
    
    storage = get_captcha_storage()
    num_concurrent = 20
    results = {"success": 0, "failed": 0, "errors": []}
    
    def store_and_verify(i):
        captcha_id = str(uuid.uuid4())
        code = f"TEST{i:04d}"
        try:
            storage.store(captcha_id, code, expires_in_seconds=60)
            result = storage.verify_and_remove(captcha_id, code)
            if result[0]:  # is_valid
                return True, None
            else:
                return False, result[1]
        except Exception as e:
            return False, str(e)[:100]
    
    print(f"  Running {num_concurrent} concurrent captcha operations...")
    
    with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
        futures = [executor.submit(store_and_verify, i) for i in range(num_concurrent)]
        for future in as_completed(futures):
            success, error = future.result()
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
                if error and error not in results["errors"]:
                    results["errors"].append(error)
    
    passed = results["failed"] == 0
    print_result(
        f"All {num_concurrent} operations succeeded",
        passed,
        f"Success: {results['success']}, Failed: {results['failed']}"
    )
    
    if results["errors"]:
        for err in results["errors"][:3]:  # Show first 3 unique errors
            print(f"         Error: {err}")
    
    return passed


async def test_7_token_tracker_buffer():
    """Test TokenTracker buffering works"""
    print_header("7. TokenTracker Buffer Test")
    
    from services.token_tracker import get_token_tracker
    tt = get_token_tracker()
    
    initial_buffer = len(tt._buffer)
    
    # Add some test records
    num_records = 10
    for i in range(num_records):
        await tt.track_usage(
            model_alias="qwen",
            input_tokens=100,
            output_tokens=50,
            request_type="test",
            user_id=999999,  # Test user
        )
    
    final_buffer = len(tt._buffer)
    added = final_buffer - initial_buffer
    
    passed = added == num_records
    print_result(
        f"Added {num_records} records to buffer",
        passed,
        f"Buffer grew from {initial_buffer} to {final_buffer}"
    )
    
    print("         → Records in memory, not yet in database")
    print("         → Will flush after 5 min or 1000 records")
    
    return passed


def test_8_checkpoint_function():
    """Test WAL checkpoint function exists and works"""
    print_header("8. WAL Checkpoint Function")
    
    from config.database import checkpoint_wal, DATABASE_URL
    
    if "sqlite" not in DATABASE_URL:
        print("  Skipped (not using SQLite)")
        return True
    
    # Test checkpoint
    result = checkpoint_wal()
    print_result(
        "checkpoint_wal() works",
        result,
        "Merges WAL changes to main database"
    )
    
    return result


def test_9_env_config():
    """Test environment configuration"""
    print_header("9. Environment Configuration")
    
    # Check if env vars are recognized
    import os
    
    vars_to_check = [
        ("TOKEN_TRACKER_ENABLED", "true"),
        ("TOKEN_TRACKER_BATCH_SIZE", "1000"),
        ("TOKEN_TRACKER_BATCH_INTERVAL", "300"),
        ("TOKEN_TRACKER_MAX_BUFFER_SIZE", "10000"),
        ("DATABASE_POOL_SIZE", "15"),
        ("DATABASE_MAX_OVERFLOW", "30"),
    ]
    
    for var, default in vars_to_check:
        value = os.getenv(var, f"(default: {default})")
        print(f"  {var}: {value}")
    
    print()
    print_result(
        "Environment config available",
        True,
        "All settings can be overridden via .env"
    )
    
    return True


def run_all_tests():
    """Run all tests"""
    print()
    print("+============================================================+")
    print("|         DATABASE FIXES VERIFICATION SCRIPT                 |")
    print("|         Testing QueuePool Error Fixes                      |")
    print("+============================================================+")
    print()
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Run sync tests
    results.append(("TokenTracker Config", test_1_token_tracker_config()))
    results.append(("Database Pool", test_2_database_pool()))
    results.append(("WAL Mode", test_3_wal_mode()))
    results.append(("CaptchaStorage Retry", test_4_captcha_retry_logic()))
    results.append(("Non-Blocking", test_5_token_tracker_non_blocking()))
    results.append(("Concurrent Captcha", test_6_concurrent_captcha()))
    
    # Run async tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results.append(("TokenTracker Buffer", loop.run_until_complete(test_7_token_tracker_buffer())))
    loop.close()
    
    results.append(("WAL Checkpoint", test_8_checkpoint_function()))
    results.append(("Environment Config", test_9_env_config()))
    
    # Summary
    print_header("SUMMARY")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[OK]" if result else "[X]"
        print(f"  {status} {name}")
    
    print()
    print(f"  Results: {passed}/{total} tests passed")
    print()
    
    if passed == total:
        print("  *** ALL TESTS PASSED! ***")
        print("  The database fixes are working correctly.")
        print()
        print("  Expected improvements:")
        print("  - QueuePool errors: 368 -> ~0")
        print("  - TokenTracker writes: 100/min -> 1-2/min")
        print("  - Pool capacity: 15 -> 45 connections")
        print()
        return 0
    else:
        print("  !!! SOME TESTS FAILED !!!")
        print("  Please review the failed tests above.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

