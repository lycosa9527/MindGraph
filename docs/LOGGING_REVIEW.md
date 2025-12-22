# Logging Review - Current Log Levels and Coverage

## Overview

This document reviews the current logging implementation for key user operations:
- User login/authentication
- SMS operations
- Node palette operations
- Auto-complete operations
- Success/error tracking

## Current Log Level Configuration

**Global Setting:** Controlled by `LOG_LEVEL` environment variable (default: `INFO`)

**Special Cases:**
- `frontend_logger`: Always set to `DEBUG` (accepts all frontend logs)
- `openai` logger: Respects global `LOG_LEVEL` (fixed in v4.37.1)
- Third-party loggers (httpx, httpcore, qcloud_cos, urllib3): Set to `WARNING`

---

## 1. User Login & Authentication

### Current Logging

| Event | Level | Location | Message Format |
|-------|-------|----------|----------------|
| **Successful Login** | `INFO` | `routers/auth.py:516` | `"User logged in: {phone}"` |
| **SMS Login Success** | `INFO` | `routers/auth.py:1461` | `"User logged in via SMS: {phone}"` |
| **SMS Registration** | `INFO` | `routers/auth.py:1352` | `"User registered via SMS: {phone} (Org: {org.code})"` |
| **Login Rate Limit** | `WARNING` | `routers/auth.py:358` | `"Rate limit exceeded for {phone}"` |
| **Org Locked** | `WARNING` | `routers/auth.py:474` | `"Login blocked: Organization {code} is locked"` |
| **Org Expired** | `WARNING` | `routers/auth.py:485` | `"Login blocked: Organization {code} expired on {date}"` |
| **SMS Login Blocked** | `WARNING` | `routers/auth.py:1409,1418` | `"SMS login blocked: Organization {code} is locked/expired"` |
| **API Key Auth** | `INFO` | `utils/auth.py:1021` | `"[Auth] Valid API key access: {name} (ID: {id})"` |
| **API Key Auth (Debug)** | `DEBUG` | `utils/auth.py:993` | `"Authenticated teacher: {name} (ID: {id}, Phone: {phone})"` |
| **WebSocket Auth Failed** | `WARNING` | `routers/voice.py:2588,2597,2605` | `"WebSocket auth failed: {reason}"` |
| **WebSocket Auth Success** | `DEBUG` | `routers/voice.py:2608` | `"WebSocket authenticated: user {id}"` |

### Missing Information

**Currently NOT logged:**
- ❌ User ID in login messages (only phone number)
- ❌ Login timestamp (implicit in log timestamp)
- ❌ Login method (captcha vs SMS vs API key)
- ❌ Organization name (only code)
- ❌ Login IP address
- ❌ Failed login attempts (only rate limit warnings)

### Recommendations

**To track user operations better, consider adding:**

```python
# Enhanced login logging
logger.info(f"User logged in: {user.phone} (ID: {user.id}, Org: {org.name if org else 'None'}, Method: captcha, IP: {client_ip})")

# Failed login attempt logging
logger.warning(f"Failed login attempt: {phone} (Reason: {reason}, IP: {client_ip})")
```

---

## 2. SMS Operations

### Current Logging

| Event | Level | Location | Message Format |
|-------|-------|----------|----------------|
| **SMS Code Sent** | `INFO` | `routers/auth.py:1067` | `"SMS code sent to {phone} for {purpose}"` |
| **SMS Sent Success** | `INFO` | `services/sms_middleware.py:369` | `"SMS sent successfully to {phone} for {purpose}"` |
| **SMS Send Failed** | `ERROR` | `services/sms_middleware.py:374` | `"SMS send failed: {error_code} - {error_msg}"` |
| **SMS API Error** | `ERROR` | `services/sms_middleware.py:361` | `"SMS API error: {error_code} - {error_msg}"` |
| **SMS Timeout** | `ERROR` | `services/sms_middleware.py:381` | `"SMS request timeout"` |
| **SMS HTTP Error** | `ERROR` | `services/sms_middleware.py:384` | `"SMS HTTP error: {error}"` |
| **SMS Rate Limit** | `WARNING` | `services/sms_middleware.py:612` | `"[SMSMiddleware] Rate limiter acquisition failed: {error}"` |
| **SMS Service Init** | `INFO` | `services/sms_middleware.py:108` | `"Tencent SMS service initialized (native async mode)"` |
| **SMS Service Shutdown** | `INFO` | `services/sms_middleware.py:805` | `"SMS service shut down"` |

### Missing Information

**Currently NOT logged:**
- ❌ SMS verification code (for security, should NOT be logged)
- ❌ SMS verification success/failure
- ❌ SMS code expiration
- ❌ SMS code usage (when code is consumed)
- ❌ User ID associated with SMS operations
- ❌ SMS purpose breakdown (register vs login vs reset_password)

### Recommendations

**To track SMS operations better, consider adding:**

```python
# SMS verification success
logger.info(f"SMS code verified: {phone} (Purpose: {purpose}, User: {user_id})")

# SMS code expired
logger.debug(f"SMS code expired: {phone} (Purpose: {purpose}, Age: {age}s)")

# SMS code consumed
logger.info(f"SMS code consumed: {phone} (Purpose: {purpose}, User: {user_id})")
```

---

## 3. Node Palette Operations

### Current Logging

| Event | Level | Location | Message Format |
|-------|-------|----------|----------------|
| **Node Palette Start** | `DEBUG` | `routers/node_palette.py:70` | `"[NodePalette-API] POST /start | Session: {id} | User: {id}"` |
| **Node Selection** | `DEBUG` | `routers/node_palette.py:567` | `"[NodePalette-Selection] User {action} node | Session: {id} | Node: '{text}'"` |
| **Content Filter Error** | `WARNING` | `routers/node_palette.py:237` | `"[NodePalette-API] Content filter | Session: {id} | Error: {error}"` |
| **Rate Limit Error** | `WARNING` | `routers/node_palette.py:246` | `"[NodePalette-API] Rate limit | Session: {id} | Error: {error}"` |
| **Timeout Error** | `WARNING` | `routers/node_palette.py:255` | `"[NodePalette-API] Timeout | Session: {id} | Error: {error}"` |
| **LLM Service Error** | `ERROR` | `routers/node_palette.py:300` | `"[NodePalette-API] LLM service error | Session: {id} | Error: {error}"` |
| **Stream Error** | `ERROR` | `routers/node_palette.py:309` | `"[NodePalette-API] Stream error | Session: {id} | Error: {error}"` |
| **Start Error** | `ERROR` | `routers/node_palette.py:336` | `"[NodePalette-API] Start error: {error}"` |
| **Slow Request** | `WARNING` | `main.py:1120` | `"Slow node palette: {method} {path} took {time}s"` |

### Missing Information

**Currently NOT logged:**
- ❌ Node palette completion (when user finishes selecting nodes)
- ❌ Number of nodes generated per session
- ❌ Number of nodes selected per session
- ❌ Diagram type used
- ❌ User ID (only session ID)
- ❌ Success metrics (nodes generated, nodes selected, time taken)

### Recommendations

**To track node palette operations better, consider adding:**

```python
# Node palette completion
logger.info(f"[NodePalette] Session completed: {session_id} (User: {user_id}, Nodes generated: {count}, Selected: {selected_count}, Diagram: {type})")

# Node palette start (INFO level)
logger.info(f"[NodePalette] Started: {session_id} (User: {user_id}, Diagram: {type}, Topic: {topic})")
```

---

## 4. Auto-Complete Operations

### Current Logging

| Event | Level | Location | Message Format |
|-------|-------|----------|----------------|
| **Button Clicked** | `INFO` | `static/js/editor/toolbar-manager.js:202` | `"=== AUTO-COMPLETE BUTTON CLICKED ==="` |
| **Auto-Complete Started** | `INFO` | `static/js/managers/toolbar/llm-autocomplete-manager.js:150` | `"=== AUTO-COMPLETE STARTED ==="` |
| **Topic Identified** | `INFO` | `static/js/managers/toolbar/llm-autocomplete-manager.js:190` | `"Topic identified: {topic}"` |
| **First Result Rendered** | `INFO` | `static/js/managers/toolbar/llm-autocomplete-manager.js:434` | `"First result from {model} rendered"` |
| **All Models Failed** | `ERROR` | `static/js/managers/toolbar/llm-autocomplete-manager.js:488` | `"All LLM models failed: {errors}"` |
| **Partial Success** | `INFO` | `static/js/managers/toolbar/llm-autocomplete-manager.js:497` | `"{success}/4 models succeeded"` |
| **Rendering Success** | `INFO` | `static/js/managers/toolbar/llm-autocomplete-manager.js:540` | `"✓ Diagram rendered successfully"` |
| **Rendering Failed** | `ERROR` | `static/js/managers/toolbar/llm-autocomplete-manager.js:564` | `"Cannot render: editor not initialized"` |
| **Voice Triggered** | `INFO` | `routers/voice.py:2447` | `"Triggering AI auto-complete from text/voice command"` |

**Note:** Auto-complete has extensive DEBUG logging (18+ points) but most are at DEBUG level and won't show with `LOG_LEVEL=INFO`.

### Missing Information

**Currently NOT logged (at INFO level):**
- ❌ User ID
- ❌ Diagram type
- ❌ Number of nodes added
- ❌ Which LLM model succeeded
- ❌ Time taken for auto-complete
- ❌ Success rate metrics

### Recommendations

**To track auto-complete operations better, consider adding:**

```python
# Auto-complete completion (backend)
logger.info(f"[AutoComplete] Completed: User {user_id}, Diagram {type}, Nodes added: {count}, Model: {model}, Time: {duration}s")

# Auto-complete start (backend)
logger.info(f"[AutoComplete] Started: User {user_id}, Diagram {type}, Topic: {topic}")
```

---

## 5. Success/Error Tracking

### Current Error Logging

**General Pattern:**
- `ERROR`: Critical failures, exceptions, service errors
- `WARNING`: Non-critical issues, rate limits, fallbacks
- `INFO`: Successful operations, important state changes
- `DEBUG`: Detailed debugging information

### Error Categories

| Category | Level | Examples |
|----------|-------|----------|
| **Authentication Errors** | `WARNING` | Rate limits, invalid credentials, org locked |
| **SMS Errors** | `ERROR` | API failures, timeouts, HTTP errors |
| **LLM Errors** | `ERROR` | Service errors, stream errors |
| **LLM Warnings** | `WARNING` | Rate limits, content filters, timeouts |
| **Database Errors** | `ERROR` | Migration failures, connection errors |
| **Performance Issues** | `WARNING` | Slow requests (>3s for node palette) |

### Success Tracking

**Currently logged as INFO:**
- ✅ User login success
- ✅ SMS code sent success
- ✅ SMS login success
- ✅ SMS registration success
- ✅ Password reset success
- ✅ Auto-complete button clicked
- ✅ Auto-complete rendering success

**Currently NOT logged:**
- ❌ Diagram generation success (only errors)
- ❌ Node palette completion
- ❌ API key usage success (only failures)
- ❌ Cache hits/misses
- ❌ Performance metrics

---

## Summary & Recommendations

### Current State

**Strengths:**
- ✅ Login events are logged at INFO level
- ✅ SMS operations have good error logging
- ✅ Auto-complete has extensive DEBUG logging
- ✅ Error tracking is comprehensive

**Gaps:**
- ❌ User ID not consistently included in logs
- ❌ Success metrics not tracked (completion, counts, durations)
- ❌ Node palette operations mostly at DEBUG level
- ❌ Auto-complete details mostly at DEBUG level
- ❌ No user activity summary logs

### Recommended Changes

1. **Elevate Node Palette logging to INFO:**
   - Start, completion, node counts
   - Include user ID and diagram type

2. **Add completion tracking:**
   - Node palette: nodes generated, selected, time taken
   - Auto-complete: nodes added, model used, time taken
   - SMS: verification success/failure

3. **Include user context:**
   - Add user ID to all operation logs
   - Add organization name (not just code)
   - Add IP address for security events

4. **Add success metrics:**
   - Track completion rates
   - Track performance metrics
   - Track feature usage statistics

5. **Create user activity summary:**
   - Daily summary of user operations
   - Feature usage breakdown
   - Error rate tracking

---

## Example Enhanced Logging

### Before (Current)
```
[23:35:05] INFO  | API  | User logged in: 138****1234
[23:35:58] DEBUG | API  | [NodePalette-API] POST /start | Session: abc12345
```

### After (Recommended)
```
[23:35:05] INFO  | API  | User logged in: 138****1234 (ID: 123, Org: School A, Method: captcha, IP: 192.168.1.1)
[23:35:58] INFO  | API  | [NodePalette] Started: Session abc12345 (User: 123, Diagram: circle_map, Topic: "自动备份")
[23:36:15] INFO  | API  | [NodePalette] Completed: Session abc12345 (User: 123, Generated: 20 nodes, Selected: 5 nodes, Duration: 17s)
```

---

## Next Steps

1. Review this document and identify priority logging enhancements
2. Implement enhanced logging for critical operations
3. Add user activity tracking
4. Create logging dashboard/analytics

