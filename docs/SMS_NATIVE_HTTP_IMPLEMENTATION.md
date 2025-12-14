# SMS Native HTTP Implementation Guide

## Overview

MindGraph uses **native HTTP calls** to Tencent Cloud SMS API, bypassing the official Tencent SDK entirely. This approach provides:

- ✅ **True async/await support** - No blocking synchronous SDK calls
- ✅ **Better performance** - Direct HTTP/2 connections via `httpx`
- ✅ **Full control** - Custom error handling and retry logic
- ✅ **No SDK dependencies** - Lighter deployment footprint
- ✅ **Middleware-ready** - Easy to add rate limiting and queuing

## Architecture

```
┌─────────────────┐
│   FastAPI App   │
│  (auth router)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  SMS Middleware │─────▶│  Rate Limiter    │
│  (NEW)          │      │  (Concurrent/QPM)│
└────────┬────────┘      └──────────────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  SMS Service    │─────▶│  httpx Client    │
│  (Native HTTP)  │      │  (HTTP/2 async)  │
└────────┬────────┘      └──────────────────┘
         │
         ▼
┌─────────────────┐
│ Tencent SMS API │
│  (SendSms v3)   │
└─────────────────┘
```

## Current Implementation

### SMS Service (`services/sms_middleware.py`)

The current implementation uses **native HTTP calls** with manual TC3-HMAC-SHA256 signature:

```python
# Direct HTTP POST to Tencent API
client = await self._get_client()  # httpx.AsyncClient with HTTP/2
response = await client.post(
    TENCENT_SMS_ENDPOINT,  # https://sms.tencentcloudapi.com
    content=payload,
    headers=headers  # Includes TC3-HMAC-SHA256 signature
)
```

**Key Features:**
- ✅ Manual TC3-HMAC-SHA256 signature generation
- ✅ Async httpx client with HTTP/2 support
- ✅ No Tencent SDK dependency
- ✅ Custom error translation
- ✅ Content-Type matches API Explorer format (`"application/json"` without charset)
- ❌ **Missing**: Concurrent request limiting middleware

**Signature Implementation:**
The signature algorithm follows Tencent's official TC3-HMAC-SHA256 specification:
1. Build canonical request string (includes content-type, host, x-tc-action)
2. Build string to sign (algorithm, timestamp, credential scope, hashed canonical)
3. Calculate signature (HMAC-SHA256 with secret key)
4. Build Authorization header

**Critical**: The Content-Type value in canonical headers MUST exactly match the Content-Type header sent in the request. Our implementation uses `"application/json"` (without charset) to match Tencent API Explorer format.

### API Reference

**Tencent Cloud SMS API Documentation:**
- Official API: https://cloud.tencent.com/document/api/382/55981
- Signature Algorithm: https://cloud.tencent.com/document/api/382/52071
- Default Rate Limit: **3000 requests/second** (Tencent side)

**Request Format (API Explorer Format):**
```http
POST / HTTP/1.1
Host: sms.tencentcloudapi.com
Content-Type: application/json
X-TC-Action: SendSms
X-TC-Timestamp: 1765752123
X-TC-Version: 2021-01-11
X-TC-Region: ap-guangzhou
Authorization: TC3-HMAC-SHA256 Credential=... Signature=...

{
    "PhoneNumberSet": ["+8613812345678"],
    "SmsSdkAppId": "1400000000",
    "SignName": "MindGraph",
    "TemplateId": "1234567",
    "TemplateParamSet": ["123456"]
}
```

**Important Notes:**
- Content-Type is `"application/json"` (without charset) - matches Tencent API Explorer
- X-TC-Timestamp is sent as string in headers (httpx handles this)
- The Content-Type in canonical headers MUST match the actual request header exactly
- Our implementation matches the API Explorer format (verified working)

## Problem: Concurrent Request Handling

### Current Issue

If **100 users request SMS simultaneously**:

1. ✅ Database-level rate limiting passes (different phone numbers)
2. ✅ All 100 requests reach `sms_middleware.send_verification_code()`
3. ❌ **100 concurrent HTTP requests** hit Tencent API simultaneously
4. ❌ **No queuing/throttling** - requests compete for resources
5. ❌ **Potential API rate limit errors** from Tencent
6. ❌ **No connection pooling control**

### Why Middleware is Needed

Similar to **Omni WebSocket middleware** (`services/websocket_llm_middleware.py`), SMS needs:

1. **Concurrent Request Limiting**
   - Limit active SMS requests (e.g., max 10 concurrent)
   - Queue excess requests automatically

2. **QPM (Queries Per Minute) Limiting**
   - Respect Tencent API limits
   - Prevent burst traffic

3. **Connection Tracking**
   - Monitor active requests
   - Better error handling and retry logic

4. **Performance Tracking**
   - Track SMS send latency
   - Monitor success/failure rates

## Proposed Solution: SMS Middleware

### Design Pattern (Similar to WebSocket Middleware)

```python
# services/sms_middleware.py

class SMSMiddleware:
    """
    Middleware for SMS service requests.
    
    Provides:
    - Concurrent request limiting
    - QPM rate limiting
    - Request queuing
    - Performance tracking
    """
    
    def __init__(
        self,
        max_concurrent_requests: int = 10,
        qpm_limit: int = 100,
        enable_rate_limiting: bool = True
    ):
        self.max_concurrent_requests = max_concurrent_requests
        self.qpm_limit = qpm_limit
        self._active_requests = 0
        self._request_lock = asyncio.Lock()
        # ... rate limiter integration
    
    @asynccontextmanager
    async def request_context(
        self,
        phone: str,
        purpose: str
    ):
        """
        Context manager for SMS requests.
        
        Usage:
            success, msg, code = await sms_middleware.send_verification_code(phone, purpose)
        """
        # Acquire rate limiter
        # Check concurrent limit
        # Track request
        # Yield context
        # Release on exit
        pass
```

### Integration in Auth Router

```python
# routers/auth.py

from services.sms_middleware import get_sms_middleware

@router.post("/sms/send")
async def send_sms_code(...):
    # ... existing validation ...
    
    sms_middleware = get_sms_middleware()
    
    # Send SMS with middleware (handles rate limiting automatically)
    success, message, _ = await sms_middleware.send_verification_code(
        phone, purpose, code=code
    )
    
    # ... rest of handler ...
```

## Configuration

### Environment Variables

Add to `config/settings.py` and `env.example`:

```python
# SMS Rate Limiting Configuration
SMS_MAX_CONCURRENT_REQUESTS = 10  # Max concurrent SMS API calls
SMS_QPM_LIMIT = 100               # Queries per minute limit
SMS_RATE_LIMITING_ENABLED = true  # Enable/disable middleware
```

### Default Limits

Based on Tencent Cloud SMS API:
- **Tencent API Limit**: 3000 requests/second (server-side)
- **Recommended App Limit**: 10-50 concurrent requests
- **Recommended QPM**: 100-500 QPM (depends on account tier)

## Benefits

### 1. Prevents API Overload
- Queues requests when limit reached
- Prevents hitting Tencent rate limits
- Better error handling

### 2. Better Resource Management
- Controls connection pool size
- Prevents memory exhaustion
- Tracks active requests

### 3. Improved User Experience
- Requests wait in queue instead of failing
- Automatic retry on transient errors
- Better error messages

### 4. Monitoring & Observability
- Track SMS send latency
- Monitor success/failure rates
- Connection pool metrics

## Implementation Steps

1. ✅ **SMS Middleware** (`services/sms_middleware.py`) - Complete SMS service with middleware
   - Similar structure to `websocket_llm_middleware.py`
   - Integrate with existing rate limiter or create SMS-specific one

2. ✅ **Add Configuration** (`config/settings.py`)
   - SMS concurrent limit
   - SMS QPM limit
   - Enable/disable flag

3. ✅ **Update Auth Router** (`routers/auth.py`)
   - Wrap SMS calls with middleware context
   - Maintain existing error handling

4. ✅ **Update Environment Template** (`env.example`)
   - Document new configuration options

5. ✅ **Testing**
   - Test concurrent request handling
   - Verify queuing behavior
   - Test rate limit scenarios

## Comparison: With vs Without Middleware

### Without Middleware (Current)
```
100 users request SMS
  ↓
100 concurrent HTTP requests
  ↓
Tencent API receives burst
  ↓
Potential rate limit errors
  ↓
Some requests fail
```

### With Middleware (Proposed)
```
100 users request SMS
  ↓
Middleware queues requests
  ↓
10 concurrent requests (configurable)
  ↓
Remaining 90 wait in queue
  ↓
Requests processed sequentially
  ↓
All requests succeed (with retry)
```

## Comparison with Tencent API Explorer

### Verification

Comparing our implementation with Tencent's **API Explorer** (official working tool):

| Aspect | API Explorer | Our Implementation | Status |
|--------|-------------|-------------------|--------|
| **Content-Type** | `"application/json"` | `"application/json"` | ✅ Matches |
| **X-TC-Timestamp** | String in header | `str(timestamp)` | ✅ Matches |
| **HTTP Client** | curl/HTTPS | `httpx.AsyncClient` (async) | ✅ Better for async |
| **Signature Algorithm** | TC3-HMAC-SHA256 | TC3-HMAC-SHA256 | ✅ Identical |
| **Canonical Headers** | content-type;host;x-tc-action | content-type;host;x-tc-action | ✅ Identical |
| **SignedHeaders** | content-type;host;x-tc-action | content-type;host;x-tc-action | ✅ Identical |

### API Explorer Example

```bash
curl -H "Content-Type: application/json" \
     -H "X-TC-Action: SendSms" \
     -H "X-TC-Timestamp: 1765752123" \
     -H "X-TC-Version: 2021-01-11" \
     -H "Authorization: TC3-HMAC-SHA256 Credential=..." \
     -d '{}' 'https://sms.tencentcloudapi.com/'
```

**Key Observations:**
- ✅ Content-Type is `"application/json"` (no charset) - matches our implementation
- ✅ X-TC-Timestamp is sent as string in header - matches our implementation
- ✅ Signature format matches exactly

### Why This Matters

The TC3 signature algorithm requires **exact matching** between:
- Content-Type in canonical request string
- Content-Type in actual HTTP headers

Our implementation matches the **API Explorer format** (the official working tool), ensuring signature compatibility.

**Note**: Some Tencent sample code may show `"application/json; charset=utf-8"`, but the actual API Explorer (which generates working requests) uses `"application/json"` without charset. Our implementation follows the API Explorer format.

## References

- **Tencent SMS API**: https://cloud.tencent.com/document/api/382/55981
- **TC3 Signature**: https://cloud.tencent.com/document/api/382/52071
- **Tencent Official Sample**: See sample code in Tencent documentation
- **WebSocket Middleware**: `services/websocket_llm_middleware.py`
- **Rate Limiter**: `services/rate_limiter.py`

## Notes

- The native HTTP implementation is **already working** - we just need middleware for concurrency control
- Tencent SDK is **not needed** - native HTTP is faster and more flexible
- Middleware pattern matches existing WebSocket middleware for consistency
- Configuration should be environment-based for different deployment tiers
