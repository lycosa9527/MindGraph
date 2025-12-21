# Health Check Implementation Guide

**Last Updated**: 2025-12-21  
**Status**: ✅ Production Ready

## Overview

MindGraph provides comprehensive health check endpoints for monitoring application and service status. The implementation follows industry standards with proper HTTP status codes, parallel execution, and secure error handling.

---

## Available Endpoints

### 1. Basic Application Health
```
GET /health
```
Returns basic application status and version.

**Response** (200 OK):
```json
{
  "status": "ok",
  "version": "4.12.0"
}
```

### 2. Application Status (with Metrics)
```
GET /status
```
Returns detailed application metrics including uptime and memory usage.

**Response** (200 OK):
```json
{
  "status": "running",
  "framework": "FastAPI",
  "version": "4.12.0",
  "uptime_seconds": 3600.5,
  "memory_percent": 45.2,
  "timestamp": 1642012345.678
}
```

### 3. LLM Services Health Check
```
GET /api/llm/health
```
Checks health of all LLM models (qwen, deepseek, kimi, hunyuan, doubao, omni).

**HTTP Status Codes**:
- `200 OK`: All models healthy
- `503 Service Unavailable`: Some models unhealthy (degraded state)
- `500 Internal Server Error`: Health check itself failed

**Response** (200 OK - All Healthy):
```json
{
  "status": "success",
  "health": {
    "available_models": ["qwen", "qwen-turbo", "qwen-plus", "deepseek", "kimi", "hunyuan", "doubao", "omni"],
    "qwen": {"status": "healthy", "latency": 0.8},
    "qwen-turbo": {"status": "healthy", "latency": 0.34},
    "omni": {"status": "healthy", "latency": 0.18, "note": "WebSocket-based real-time voice service"}
  },
  "circuit_states": {
    "qwen": "closed",
    "qwen-turbo": "closed"
  },
  "timestamp": 1642012345
}
```

**Response** (503 Service Unavailable - Degraded):
```json
{
  "status": "success",
  "health": {
    "available_models": ["qwen", "qwen-turbo"],
    "qwen": {"status": "healthy", "latency": 0.8},
    "qwen-turbo": {"status": "unhealthy", "error": "Connection failed", "error_type": "connection_error"}
  },
  "degraded": true,
  "unhealthy_count": 1,
  "healthy_count": 1,
  "total_models": 2,
  "timestamp": 1642012345
}
```

### 4. Database Health Check
```
GET /health/database
```
Checks database integrity and returns statistics.

**HTTP Status Codes**:
- `200 OK`: Database is healthy
- `503 Service Unavailable`: Database is unhealthy or corrupted
- `500 Internal Server Error`: Health check failed

**Response** (200 OK):
```json
{
  "status": "healthy",
  "database_healthy": true,
  "database_message": "Database integrity check passed",
  "database_stats": {
    "path": "data/mindgraph.db",
    "size_mb": 2.5,
    "modified": "2025-12-21 07:00:00",
    "total_rows": 650
  },
  "timestamp": 1642012345
}
```

---

## How Health Checks Work

### LLM Model Health Determination

**Simple Rule**:
- ✅ **Healthy**: Test operation succeeds (no exceptions)
- ❌ **Unhealthy**: Test operation fails (any exception)

### For HTTP-Based Models

**Process**:
1. Attempts to call `chat()` with a simple "Test" prompt
2. If call succeeds → Status = `'healthy'`
3. If call raises exception → Status = `'unhealthy'`

**What Makes a Model Unhealthy?**:
- Connection failures (network unreachable)
- Timeout errors (> 5 seconds)
- Authentication errors (invalid API key)
- Rate limiting (too many requests)
- API errors (service unavailable)
- Invalid responses (wrong format)
- Quota exhausted

### For WebSocket Model (Omni)

**Process**:
1. Attempts to create WebSocket connection
2. If connection succeeds → Status = `'healthy'`
3. If connection fails → Status = `'unhealthy'`

**What Makes Omni Unhealthy?**:
- WebSocket connection failures
- Authentication errors
- Timeout (connection > 5 seconds)
- Network issues
- API endpoint unavailable

### Database Health Determination

**Process**:
1. Checks if database file exists
2. Runs SQLite `PRAGMA integrity_check`
3. If result is `"ok"` → Healthy
4. If result is not `"ok"` → Unhealthy

**What Makes Database Unhealthy?**:
- Database corruption detected
- Integrity check fails
- File access errors
- Invalid SQLite format

---

## Implementation Details

### Performance Optimization

**Parallel Execution**: All model health checks run concurrently using `asyncio.gather()`.

**Performance**:
- **Before**: Sequential (~40 seconds for 8 models)
- **After**: Parallel (~5 seconds for 8 models)
- **Speedup**: ~8x faster

**Code**:
```python
# Create health check tasks for all models (parallel execution)
tasks = []
for model in available_models:
    if model == 'omni':
        tasks.append(self._check_omni_health(model))
    else:
        tasks.append(self._check_model_health(model))

# Execute all health checks in parallel
health_results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Error Handling

**Error Categorization**: Errors are categorized to avoid exposing sensitive details.

**Error Types**:
- `connection_error` - Connection failures
- `timeout` - Request timeouts
- `rate_limit` - Rate limit exceeded
- `quota_exhausted` - Quota exhausted
- `service_error` - Generic service errors
- `unknown` - Unknown errors

**Security**: Error messages are generic and don't expose sensitive information.

### HTTP Status Codes

**Industry Standard Compliance** (RFC 7231, Kubernetes conventions):

- **200 OK**: All services healthy
- **503 Service Unavailable**: Some services unhealthy (degraded state)
- **500 Internal Server Error**: Health check itself failed

**Implementation**:
```python
# Check if any models are unhealthy
unhealthy_count = sum(
    1 for model in available_models
    if model in health_data 
    and health_data[model].get('status') != 'healthy'
)

# Return appropriate HTTP status code
if unhealthy_count == 0:
    status_code = 200  # All healthy
else:
    status_code = 503  # Degraded (some unhealthy)
```

### Response Models

**Pydantic Models** for type safety and OpenAPI schema generation:

- `LLMHealthResponse` - LLM health check response
- `DatabaseHealthResponse` - Database health check response
- `ModelHealthStatus` - Individual model health status

---

## Testing

### Test Script

Use the provided test script to verify health checks:

```bash
# Test via HTTP endpoint
python tests/test_health_check.py

# Test with custom endpoint
python tests/test_health_check.py --endpoint http://localhost:9527

# Test service directly (no HTTP)
python tests/test_health_check.py --direct

# Test both methods
python tests/test_health_check.py --both

# Get JSON output
python tests/test_health_check.py --json
```

### Manual Testing

```bash
# Basic health check
curl http://localhost:9527/health

# LLM health check
curl http://localhost:9527/api/llm/health

# Database health check
curl http://localhost:9527/health/database
```

---

## Monitoring Integration

### Load Balancers

Health check endpoints can be used with load balancers:

- **Basic Health**: `/health` - Always returns 200 if app is running
- **Service Health**: `/api/llm/health` - Returns 200/503 based on model health
- **Database Health**: `/health/database` - Returns 200/503 based on DB health

### Monitoring Tools

The endpoints provide detailed information for monitoring:

- Model-by-model health status
- Latency measurements
- Circuit breaker states
- Error categorization
- Timestamp information

### Example Monitoring Setup

```yaml
# Prometheus/Grafana example
health_check_endpoint: http://localhost:9527/api/llm/health
expected_status: 200
alert_on_status: 503  # Alert when degraded
```

---

## Best Practices

### 1. Use Appropriate Endpoints

- **Load Balancers**: Use `/health` (always fast, always 200 if running)
- **Monitoring**: Use `/api/llm/health` (detailed status)
- **Database Monitoring**: Use `/health/database` (DB-specific)

### 2. Handle Degraded States

When receiving `503 Service Unavailable`:
- Check `unhealthy_count` to see how many models are down
- Review individual model statuses in `health` object
- Consider fallback strategies for critical operations

### 3. Error Handling

- Don't expose error details to end users
- Use error types for monitoring and alerting
- Log full error details server-side

### 4. Performance

- Health checks run in parallel (fast)
- Timeout is 5 seconds per model
- Total time limited by slowest model, not sum

---

## Troubleshooting

### Health Check Returns 503

**Possible Causes**:
1. Some LLM models are unavailable
2. Network connectivity issues
3. API rate limits exceeded
4. Invalid API keys

**Solution**:
- Check individual model statuses in response
- Review error types for each unhealthy model
- Verify API keys and network connectivity

### Health Check Returns 500

**Possible Causes**:
1. Health check itself failed
2. Service initialization error
3. Internal error in health check code

**Solution**:
- Check application logs
- Verify service is properly initialized
- Review error message in response

### Health Check is Slow

**Possible Causes**:
1. Network latency to LLM APIs
2. Models taking longer than 5 seconds
3. Too many models to check

**Solution**:
- Health checks run in parallel (should be fast)
- If consistently slow, check network connectivity
- Consider reducing timeout or number of models checked

---

## API Reference

See `docs/API_REFERENCE.md` for complete API documentation including health check endpoints.

---

## References

- [RFC 7231 - HTTP/1.1 Semantics](https://tools.ietf.org/html/rfc7231)
- [Kubernetes Health Checks](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [FastAPI Response Models](https://fastapi.tiangolo.com/tutorial/response-model/)
- [Health Check Best Practices](https://microservices.io/patterns/observability/health-check-api.html)

