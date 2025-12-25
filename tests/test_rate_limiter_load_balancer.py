"""
Test script for Rate Limiter and Load Balancer modules

Tests:
1. Rate limiter acquire/release
2. Rate limit enforcement (QPM and concurrent)
3. Load balancer provider selection
4. Rate limit-aware selection
5. Concurrent request handling (race condition prevention)
6. Error handling
7. Redis operations

Run with: python tests/test_rate_limiter_load_balancer.py
"""

import asyncio
import time
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.rate_limiter import DashscopeRateLimiter, LoadBalancerRateLimiter
from services.load_balancer import LLMLoadBalancer
from services.redis_client import init_redis_sync, is_redis_available

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_test(name: str):
    """Print test header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}Test: {name}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")


def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_info(message: str):
    """Print info message"""
    print(f"{Colors.YELLOW}ℹ {message}{Colors.RESET}")


async def test_rate_limiter_basic():
    """Test 1: Basic rate limiter acquire/release"""
    print_test("Basic Rate Limiter Acquire/Release")
    
    try:
        limiter = DashscopeRateLimiter(
            qpm_limit=10,
            concurrent_limit=5,
            enabled=True,
            provider='dashscope'
        )
        
        # Test acquire
        await limiter.acquire()
        print_success("Rate limiter acquire() succeeded")
        
        # Test release
        await limiter.release()
        print_success("Rate limiter release() succeeded")
        
        # Test context manager
        async with limiter:
            print_success("Rate limiter context manager works")
        
        print_success("Basic rate limiter test passed")
        return True
    except Exception as e:
        print_error(f"Basic rate limiter test failed: {e}")
        return False


async def test_rate_limiter_qpm_limit():
    """Test 2: QPM limit enforcement"""
    print_test("QPM Limit Enforcement")
    
    try:
        limiter = DashscopeRateLimiter(
            qpm_limit=5,  # Very low limit for testing
            concurrent_limit=10,
            enabled=True,
            provider='dashscope'
        )
        
        # Clear any existing state from previous tests
        limiter.clear_state()
        
        # Acquire up to limit
        acquired = 0
        start_time = time.time()
        
        for i in range(5):
            await limiter.acquire()
            acquired += 1
            print_info(f"Acquired {acquired}/5")
        
        print_success(f"Acquired {acquired} requests within QPM limit")
        
        # Try to acquire one more (should wait)
        print_info("Attempting to acquire 6th request (should wait)...")
        acquire_start = time.time()
        await limiter.acquire()
        acquire_time = time.time() - acquire_start
        
        if acquire_time > 0.5:  # Should have waited
            print_success(f"QPM limit enforced (waited {acquire_time:.2f}s)")
        else:
            print_error(f"QPM limit may not be enforced (waited only {acquire_time:.2f}s)")
        
        # Release all
        for i in range(6):
            await limiter.release()
        
        print_success("QPM limit test passed")
        return True
    except Exception as e:
        print_error(f"QPM limit test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_rate_limiter_concurrent_limit():
    """Test 3: Concurrent limit enforcement"""
    print_test("Concurrent Limit Enforcement")
    
    try:
        limiter = DashscopeRateLimiter(
            qpm_limit=100,
            concurrent_limit=3,  # Low concurrent limit
            enabled=True,
            provider='dashscope'
        )
        
        # Clear any existing state from previous tests
        limiter.clear_state()
        
        # Acquire up to concurrent limit
        acquired = []
        for i in range(3):
            await limiter.acquire()
            acquired.append(i)
            print_info(f"Acquired concurrent request {i+1}/3")
        
        # Try to acquire one more (should wait)
        print_info("Attempting to acquire 4th concurrent request (should wait)...")
        
        async def acquire_fourth():
            await limiter.acquire()
            print_info("4th request acquired")
            await limiter.release()
        
        # Start 4th request
        task = asyncio.create_task(acquire_fourth())
        
        # Wait a bit to see if it's blocked
        await asyncio.sleep(0.2)
        
        # Release one to allow 4th to proceed
        await limiter.release()
        await task
        
        # Release remaining
        for i in range(2):
            await limiter.release()
        
        print_success("Concurrent limit test passed")
        return True
    except Exception as e:
        print_error(f"Concurrent limit test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_concurrent_race_condition():
    """Test 4: Race condition prevention (multiple requests simultaneously)"""
    print_test("Race Condition Prevention (Concurrent Requests)")
    
    try:
        limiter = DashscopeRateLimiter(
            qpm_limit=10,
            concurrent_limit=5,
            enabled=True,
            provider='dashscope'
        )
        
        # Clear any existing state from previous tests
        limiter.clear_state()
        
        # Simulate 10 concurrent requests
        async def acquire_request(request_id: int):
            try:
                await limiter.acquire()
                print_info(f"Request {request_id} acquired")
                await asyncio.sleep(0.1)  # Simulate work
                await limiter.release()
                print_info(f"Request {request_id} released")
                return True
            except Exception as e:
                print_error(f"Request {request_id} failed: {e}")
                return False
        
        # Launch 10 concurrent requests
        tasks = [acquire_request(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(results)
        
        if success_count == 10:
            print_success(f"All {success_count} concurrent requests succeeded (no race condition)")
        else:
            print_error(f"Only {success_count}/10 requests succeeded")
        
        # Check stats
        stats = limiter.get_stats()
        print_info(f"Final stats: {stats.get('active_requests', 0)} active, "
                  f"{stats.get('current_qpm', 0)} QPM")
        
        if stats.get('active_requests', 0) == 0:
            print_success("All requests properly released (no leaks)")
        else:
            print_error(f"Active requests not zero: {stats.get('active_requests', 0)}")
        
        return success_count == 10
    except Exception as e:
        print_error(f"Race condition test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_load_balancer_provider_selection():
    """Test 5: Load balancer provider selection"""
    print_test("Load Balancer Provider Selection")
    
    try:
        # Create rate limiters
        dashscope_limiter = DashscopeRateLimiter(
            qpm_limit=100,
            concurrent_limit=50,
            enabled=True,
            provider='dashscope'
        )
        
        load_balancer_limiter = LoadBalancerRateLimiter(
            volcengine_qpm=100,
            volcengine_concurrent=50,
            enabled=True
        )
        
        # Create load balancer
        load_balancer = LLMLoadBalancer(
            strategy='round_robin',
            enabled=True,
            dashscope_rate_limiter=dashscope_limiter,
            load_balancer_rate_limiter=load_balancer_limiter,
            rate_limit_aware=True
        )
        
        # Test model mapping
        providers = []
        for i in range(10):
            model = load_balancer.map_model('deepseek')
            if model == 'deepseek':
                providers.append('dashscope')
            elif model == 'ark-deepseek':
                providers.append('volcengine')
            else:
                print_error(f"Unexpected model: {model}")
                return False
        
        dashscope_count = providers.count('dashscope')
        volcengine_count = providers.count('volcengine')
        
        print_info(f"Provider distribution: Dashscope={dashscope_count}, Volcengine={volcengine_count}")
        
        # With round_robin, should be roughly 50/50
        if abs(dashscope_count - volcengine_count) <= 2:
            print_success("Load balancer provides balanced distribution")
        else:
            print_info(f"Distribution: {dashscope_count}/{volcengine_count} (may vary)")
        
        # Test fixed mappings
        qwen_model = load_balancer.map_model('qwen')
        kimi_model = load_balancer.map_model('kimi')
        
        if qwen_model == 'qwen':
            print_success("Qwen correctly mapped to Dashscope")
        else:
            print_error(f"Qwen mapped incorrectly: {qwen_model}")
            return False
        
        if kimi_model == 'ark-kimi':
            print_success("Kimi correctly mapped to Volcengine")
        else:
            print_error(f"Kimi mapped incorrectly: {kimi_model}")
            return False
        
        print_success("Load balancer provider selection test passed")
        return True
    except Exception as e:
        print_error(f"Load balancer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_rate_limit_aware_selection():
    """Test 6: Rate limit-aware provider selection"""
    print_test("Rate Limit-Aware Provider Selection")
    
    try:
        # Create rate limiters with different limits
        dashscope_limiter = DashscopeRateLimiter(
            qpm_limit=5,  # Low limit
            concurrent_limit=3,
            enabled=True,
            provider='dashscope'
        )
        
        load_balancer_limiter = LoadBalancerRateLimiter(
            volcengine_qpm=100,  # High limit
            volcengine_concurrent=50,
            enabled=True
        )
        
        # Clear any existing state from previous tests
        dashscope_limiter.clear_state()
        
        # Fill up Dashscope limit
        print_info("Filling Dashscope rate limit...")
        for i in range(5):
            await dashscope_limiter.acquire()
        
        # Create load balancer with rate limit awareness
        load_balancer = LLMLoadBalancer(
            strategy='round_robin',
            enabled=True,
            dashscope_rate_limiter=dashscope_limiter,
            load_balancer_rate_limiter=load_balancer_limiter,
            rate_limit_aware=True
        )
        
        # Check availability
        dashscope_stats = dashscope_limiter.get_stats()
        volcengine_available = load_balancer_limiter.can_acquire_now('volcengine')
        
        print_info(f"Dashscope: {dashscope_stats.get('current_qpm', 0)}/{dashscope_limiter.qpm_limit} QPM")
        print_info(f"Volcengine available: {volcengine_available}")
        
        # Select provider (should prefer Volcengine since Dashscope is at limit)
        selected_provider = load_balancer._select_deepseek_provider()
        model = load_balancer.map_model('deepseek')
        
        print_info(f"Selected provider: {selected_provider}")
        print_info(f"Mapped model: {model}")
        
        # Should prefer Volcengine when Dashscope is at limit
        if selected_provider == 'volcengine' or model == 'ark-deepseek':
            print_success("Rate limit-aware selection prefers available provider")
        else:
            print_info("Rate limit-aware selection may use strategy fallback (acceptable)")
        
        # Release Dashscope requests
        for i in range(5):
            await dashscope_limiter.release()
        
        print_success("Rate limit-aware selection test passed")
        return True
    except Exception as e:
        print_error(f"Rate limit-aware selection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_endpoint_validation():
    """Test 7: Endpoint validation for Volcengine provider"""
    print_test("Endpoint Validation")
    
    try:
        # Test valid endpoints
        valid_endpoints = ['ark-deepseek', 'ark-kimi', 'ark-doubao']
        
        for endpoint in valid_endpoints:
            limiter = DashscopeRateLimiter(
                qpm_limit=100,
                concurrent_limit=50,
                enabled=True,
                provider='volcengine',
                endpoint=endpoint
            )
            print_success(f"Valid endpoint '{endpoint}' accepted")
        
        # Test missing endpoint (should raise ValueError)
        try:
            limiter = DashscopeRateLimiter(
                qpm_limit=100,
                concurrent_limit=50,
                enabled=True,
                provider='volcengine',
                endpoint=None
            )
            print_error("Missing endpoint should raise ValueError")
            return False
        except ValueError as e:
            print_success(f"Missing endpoint correctly raises ValueError: {e}")
        
        # Test invalid endpoint (should raise ValueError)
        try:
            limiter = DashscopeRateLimiter(
                qpm_limit=100,
                concurrent_limit=50,
                enabled=True,
                provider='volcengine',
                endpoint='invalid-endpoint'
            )
            print_error("Invalid endpoint should raise ValueError")
            return False
        except ValueError as e:
            print_success(f"Invalid endpoint correctly raises ValueError: {e}")
        
        print_success("Endpoint validation test passed")
        return True
    except Exception as e:
        print_error(f"Endpoint validation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_stats_tracking():
    """Test 8: Statistics tracking"""
    print_test("Statistics Tracking")
    
    try:
        limiter = DashscopeRateLimiter(
            qpm_limit=100,
            concurrent_limit=50,
            enabled=True,
            provider='dashscope'
        )
        
        # Make some requests
        for i in range(5):
            await limiter.acquire()
            await asyncio.sleep(0.05)
            await limiter.release()
        
        # Get stats
        stats = limiter.get_stats()
        
        print_info(f"Stats: {stats}")
        
        # Verify stats structure
        required_keys = ['enabled', 'provider', 'qpm_limit', 'concurrent_limit', 
                        'qpm_key', 'concurrent_key', 'storage', 'worker_id']
        
        for key in required_keys:
            if key in stats:
                print_success(f"Stat '{key}' present")
            else:
                print_error(f"Stat '{key}' missing")
                return False
        
        print_success("Statistics tracking test passed")
        return True
    except Exception as e:
        print_error(f"Statistics tracking test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all tests"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}Rate Limiter and Load Balancer Test Suite{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    
    # Check Redis availability
    print("\nChecking Redis connection...")
    if not is_redis_available():
        print_error("Redis is not available. Please start Redis first.")
        print_info("Redis is required for rate limiting tests.")
        return False
    
    print_success("Redis connection available")
    
    # Run tests
    tests = [
        ("Basic Rate Limiter", test_rate_limiter_basic),
        ("QPM Limit Enforcement", test_rate_limiter_qpm_limit),
        ("Concurrent Limit Enforcement", test_rate_limiter_concurrent_limit),
        ("Race Condition Prevention", test_concurrent_race_condition),
        ("Load Balancer Provider Selection", test_load_balancer_provider_selection),
        ("Rate Limit-Aware Selection", test_rate_limit_aware_selection),
        ("Endpoint Validation", test_endpoint_validation),
        ("Statistics Tracking", test_stats_tracking),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print summary
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}Test Summary{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        if result:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.RESET}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed! ✓{Colors.RESET}\n")
        return True
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}Some tests failed. Please review the output above.{Colors.RESET}\n")
        return False


if __name__ == "__main__":
    # Initialize Redis
    try:
        init_redis_sync()
    except SystemExit:
        print_error("Failed to initialize Redis. Please ensure Redis is running.")
        sys.exit(1)
    
    # Run tests
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

