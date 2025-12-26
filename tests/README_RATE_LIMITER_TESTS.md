# Rate Limiter and Load Balancer Test Suite

## Overview

This test suite verifies that the rate limiter and load balancer modules work correctly, including:

1. **Basic Functionality**: Acquire/release operations
2. **QPM Limit Enforcement**: Queries per minute limits
3. **Concurrent Limit Enforcement**: Concurrent request limits
4. **Race Condition Prevention**: Multiple concurrent requests
5. **Load Balancer**: Provider selection and routing
6. **Rate Limit-Aware Selection**: Intelligent provider selection based on availability
7. **Endpoint Validation**: Volcengine endpoint parameter validation
8. **Statistics Tracking**: Rate limiter statistics collection

## Prerequisites

1. **Redis must be running**: The rate limiter requires Redis for coordination
   ```bash
   # Check if Redis is running
   redis-cli ping
   
   # If not running, start Redis:
   # Windows: Start Redis service
   # Linux/Mac: redis-server
   # Docker: docker run -d -p 6379:6379 redis:alpine
   ```

2. **Python dependencies**: Ensure all required packages are installed
   ```bash
   pip install redis asyncio
   ```

## Running the Tests

### Basic Usage

```bash
python tests/test_rate_limiter_load_balancer.py
```

### Expected Output

The test script will:
- Check Redis connection
- Run 8 test suites
- Display colored output (green for success, red for errors)
- Print a summary at the end

### Example Output

```
============================================================
Rate Limiter and Load Balancer Test Suite
============================================================

Checking Redis connection...
✓ Redis connection available

============================================================
Test: Basic Rate Limiter Acquire/Release
============================================================
✓ Rate limiter acquire() succeeded
✓ Rate limiter release() succeeded
✓ Rate limiter context manager works
✓ Basic rate limiter test passed

...

============================================================
Test Summary
============================================================
✓ Basic Rate Limiter: PASSED
✓ QPM Limit Enforcement: PASSED
✓ Concurrent Limit Enforcement: PASSED
✓ Race Condition Prevention: PASSED
✓ Load Balancer Provider Selection: PASSED
✓ Rate Limit-Aware Selection: PASSED
✓ Endpoint Validation: PASSED
✓ Statistics Tracking: PASSED

Results: 8/8 tests passed

All tests passed! ✓
```

## Test Details

### 1. Basic Rate Limiter Test
- Tests basic acquire/release operations
- Verifies context manager support
- Ensures no errors in normal operation

### 2. QPM Limit Enforcement
- Creates a rate limiter with low QPM limit (5)
- Acquires 5 requests (should succeed)
- Attempts 6th request (should wait)
- Verifies QPM limit is enforced

### 3. Concurrent Limit Enforcement
- Creates a rate limiter with low concurrent limit (3)
- Acquires 3 concurrent requests
- Attempts 4th concurrent request (should wait)
- Releases one to allow 4th to proceed
- Verifies concurrent limit is enforced

### 4. Race Condition Prevention
- Launches 10 concurrent requests simultaneously
- Verifies all requests succeed without race conditions
- Checks that Lua script prevents limit violations
- Verifies no leaks (all requests properly released)

### 5. Load Balancer Provider Selection
- Tests round-robin strategy
- Verifies DeepSeek routing (Dashscope vs Volcengine)
- Tests fixed mappings (Qwen → Dashscope, Kimi → Volcengine)
- Checks provider distribution

### 6. Rate Limit-Aware Selection
- Fills Dashscope rate limit
- Verifies load balancer prefers Volcengine when Dashscope is at limit
- Tests intelligent provider selection

### 7. Endpoint Validation
- Tests valid endpoints (ark-deepseek, ark-kimi, ark-doubao)
- Verifies ValueError is raised for missing endpoint
- Verifies ValueError is raised for invalid endpoint

### 8. Statistics Tracking
- Makes multiple requests
- Retrieves statistics
- Verifies all required stat fields are present

## Troubleshooting

### Redis Connection Failed
```
✗ Redis is not available. Please start Redis first.
```

**Solution**: Start Redis server
```bash
# Check Redis status
redis-cli ping

# Start Redis if needed
redis-server
```

### Import Errors
```
ModuleNotFoundError: No module named 'services'
```

**Solution**: Run from project root directory
```bash
cd /path/to/MG
python tests/test_rate_limiter_load_balancer.py
```

### Rate Limit Not Enforced
If tests show rate limits aren't being enforced:
1. Check Redis is running and accessible
2. Verify Redis keys are being created (check with `redis-cli KEYS "llm:rate:*"`)
3. Check logs for errors

### Tests Taking Too Long
Some tests intentionally wait for rate limits. If tests hang:
1. Check Redis is responsive (`redis-cli ping`)
2. Check for deadlocks in logs
3. Reduce wait times in test code if needed

## Notes

- Tests use low rate limits for faster execution
- Some tests may take a few seconds due to intentional waits
- All tests clean up after themselves (release acquired limits)
- Tests are designed to verify the fixes implemented in the code review

## Integration with CI/CD

To run tests in CI/CD:

```bash
# Set up Redis
docker run -d -p 6379:6379 --name redis-test redis:alpine

# Run tests
python tests/test_rate_limiter_load_balancer.py

# Cleanup
docker stop redis-test && docker rm redis-test
```

## Contributing

When adding new tests:
1. Follow the existing test structure
2. Use `print_test()`, `print_success()`, `print_error()` for output
3. Return `True` on success, `False` on failure
4. Add test to `run_all_tests()` function
5. Update this README with test description







