# LLM Provider Rate Limiting Issues

**Extracted from**: WORKSHOP_PRESSURE_TEST_ANALYSIS.md  
**Date**: December 2, 2024  
**Status**: Pending Provider Response

---

## Summary

These issues were identified during the workshop pressure test but require provider-side resolution (rate limit increases). They are tracked separately to focus on code fixes in the main analysis document.

| Provider | Issue | Status | Next Action |
|----------|-------|--------|-------------|
| DashScope (qwen, deepseek, kimi) | Rate Limiting | Request submitted | Wait for RPS/RPM increase |
| Tencent (Hunyuan) | Rate Limiting | Not submitted | Contact Tencent if issues persist |

---

## P1: HTTP 504 Gateway Timeout

### Symptom
```
[LLMEngineManager] API error for qwen | Error: HTTP 504: Gateway Time-out
[LLMEngineManager] API error for kimi | Error: HTTP 504: Gateway Time-out
[LLMEngineManager] API error for hunyuan | Error: HTTP 504: Gateway Time-out
```

### Stack Trace
```javascript
at LLMEngineManager.callLLMWithModel (llm-engine-manager.js:61:23)
at async Promise.allSettled (index 0)
at async LLMEngineManager.callMultipleModels (llm-engine-manager.js:202:25)
at async LLMAutoCompleteManager.handleAutoComplete (llm-autocomplete-manager.js:201:32)
```

### Root Cause
**LLM provider rate limiting** causing requests to take 90+ seconds, exceeding proxy timeout.

During the workshop:
- Application rate limiter: QPM=1000, Concurrent=500 (too high)
- DashScope actual limits: Much lower (~60 QPM)
- Result: Providers rate-limit requests → 90+ second waits → 504 timeout

```
15 users × 4 LLM models = 60 concurrent requests
    ↓
Application rate limiter allows all through (500 concurrent limit)
    ↓
DashScope rate-limits at provider level (429/2003 errors)
    ↓
Requests wait 90+ seconds for retry
    ↓
Nginx Proxy Manager times out (60s default)
    ↓
Frontend receives 504 Gateway Timeout
```

### Resolution
**Pending**: Request submitted to DashScope to increase RPS/RPM limits.

Once DashScope increases limits, the 504 errors should disappear because:
- Requests won't queue at provider level
- LLM calls will complete in normal time (1-30s)
- No proxy timeout

### Note on Hunyuan
Hunyuan is on **Tencent Cloud** (separate from DashScope). If Hunyuan rate limit errors persist after DashScope increase, will need to contact Tencent separately.

---

## P1: LLM Provider Rate Limiting

### Total Occurrences: 2,016

### By Provider

| Provider | Error Code | Message | Count |
|----------|-----------|---------|-------|
| **Hunyuan** | 400/2003 | `请求限频，请稍后重试` (Rate limit, please retry) | ~1,800 |
| **Kimi** | 429 | `limit_requests` - Exceeded request limit | ~200 |
| **Captcha** | 429 | User IP rate limited | ~16 (working as intended) |

### Error Examples

**Hunyuan Rate Limiting:**
```
Error code: 400 - {'error': {'message': '请求限频，请稍后重试', 'type': 'runtime_error', 'code': '2003'}}
```

**Kimi Rate Limiting:**
```
{"error":{"message":"You have exceeded your current request limit","type":"limit_requests","code":"limit_requests"}}
```

### Affected Components
- `[LLMService]` - Direct diagram generation
- `[NodePalette]` - Multi-model node suggestions

### Resolution
**Pending**: Request submitted to DashScope to increase RPS/RPM limits.

**Note**: Hunyuan is on Tencent Cloud (separate provider). If Hunyuan errors persist after DashScope increase, will need to contact Tencent separately.

---

## P1: LLM Timeouts

### Total Occurrences: 90

### By Provider and Timeout Duration

| Provider | 90s | 120s | 150s | 165s+ |
|----------|-----|------|------|-------|
| **qwen** | 5 | 7 | 7 | - |
| **deepseek** | 5 | 7 | 6 | - |
| **kimi** | 5 | 5 | 7 | 1 |
| **hunyuan** | 2 | 1 | - | - |

### Error Pattern
```
[LLMService] qwen failed after 120.67s: 
[LLMService] deepseek failed after 151.70s: 
[LLMService] kimi failed after 165.26s: 
```

### Root Cause
**Same as 504 Gateway Timeout** - Provider-side rate limiting causes requests to queue for 90+ seconds before timing out.

### Resolution
**Pending**: Will be resolved when DashScope increases RPS/RPM limits.

---

## Next Steps

1. **Wait for DashScope response** on RPS/RPM limit increase request
2. **Monitor after DashScope increase** - if Hunyuan errors persist, contact Tencent separately
3. **Re-test under load** once limits are increased to verify fix

