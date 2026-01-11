# Session Logout Debugging Guide

## Issue Description

**Symptom**: User gets logged out with message "您已被登出，因为登录设备数量超过上限" (max device limit exceeded) even when using only a single device.

**Frequency**: Happens frequently after periods of inactivity (1-2 hours, e.g., after a nap).

**Status**: Under investigation. Debug logging has been added to trace the root cause.

---

## Session Management Overview

### TTL Configuration

| Setting | Default Value | Env Variable |
|---------|---------------|--------------|
| Access Token TTL | 60 minutes | `ACCESS_TOKEN_EXPIRY_MINUTES` |
| Refresh Token TTL | 7 days | `REFRESH_TOKEN_EXPIRY_DAYS` |
| Max Concurrent Sessions | 2 devices | `MAX_CONCURRENT_SESSIONS` |
| Redis Session SET TTL | 60 minutes | (Same as access token) |

### Complete Auth Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LOGIN FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. User submits credentials (captcha/SMS/passkey)                          │
│  2. Backend validates credentials                                            │
│  3. Compute device_hash from headers:                                        │
│     - User-Agent, Accept-Language, Accept-Encoding                          │
│     - Sec-CH-UA-Platform, Sec-CH-UA-Mobile (Client Hints)                   │
│  4. Create access token (JWT, 60 min expiry)                                │
│  5. Create refresh token (random, 7 days)                                   │
│  6. store_session(user_id, access_token, device_hash)                       │
│     - Revoke existing sessions from same device_hash                        │
│     - Add new entry: timestamp:device_hash:token_hash                       │
│     - Check if count > MAX_CONCURRENT_SESSIONS                              │
│     - If exceeded: remove oldest, create invalidation notification          │
│  7. store_refresh_token(user_id, refresh_hash, device_hash)                 │
│  8. Set httpOnly cookies (access_token, refresh_token)                      │
│  9. Log: [TokenAudit] Login success + device fingerprint                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         API REQUEST FLOW                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Request arrives with access_token cookie                                 │
│  2. get_current_user() dependency:                                           │
│     a. Decode JWT (verify signature + expiry)                               │
│     b. is_session_valid(user_id, token)                                     │
│        - Look up session in Redis SET                                       │
│        - Match token_hash against stored entries                            │
│     c. If invalid: return 401                                               │
│  3. Execute endpoint logic                                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     TOKEN REFRESH FLOW (/api/auth/refresh)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Get refresh_token from cookie                                            │
│  2. Decode access_token (ignore expiry) to get user_id                      │
│  3. Compute current_device_hash from request headers                        │
│  4. validate_refresh_token(user_id, refresh_hash, current_device_hash)      │
│     - Look up stored device_hash                                            │
│     - Compare: stored_device_hash == current_device_hash                    │
│     - If mismatch: FAIL with "Device mismatch"                              │
│  5. delete_session(user_id, old_access_token)                               │
│  6. store_session(user_id, new_access_token, current_device_hash)           │
│  7. rotate_refresh_token (revoke old, create new)                           │
│  8. Set new cookies                                                          │
│  9. Log: [TokenAudit] Token refreshed                                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    SESSION MONITORING (Frontend)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  - Interval: every 120 seconds                                               │
│  - Only runs when document.visibilityState === 'visible'                    │
│  - Calls GET /api/auth/session-status                                       │
│                                                                              │
│  If response.status === 401:                                                 │
│    → Try refreshAccessToken()                                               │
│    → If fails: handleSessionInvalidation("max device limit exceeded")       │
│                                                                              │
│  If response.data.status === 'invalidated':                                 │
│    → handleSessionInvalidation(data.message)                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              LOGOUT FLOW                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. delete_session(user_id, access_token)                                   │
│  2. revoke_refresh_token(user_id, refresh_hash, reason="logout")            │
│  3. Clear cookies                                                            │
│  4. Log: [TokenAudit] Logout                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Debug Log Locations

### Backend Logs (INFO level)

Look for these log prefixes:

```
[Session]       - Redis session operations (store, validate, delete)
[RefreshToken]  - Refresh token validation and storage
[TokenAudit]    - Auth endpoint operations (login, logout, refresh, session-status)
[Auth]          - get_current_user authentication
```

### Key Log Messages

**Login:**
```
[TokenAudit] Login device fingerprint: user={id}, device_hash={hash}, UA=..., lang=..., platform=..., mobile=...
[TokenAudit] Login success: user={id}, phone=..., org=..., method=..., ip=..., device={hash}
```

**Session Storage:**
```
[Session] store_session called: user={id}, device_hash={hash}..., allow_multiple=...
[Session] Before store: user={id}, existing_sessions={count}, max={max}
[Session] Revoked {n} existing session(s) for same device: user={id}, device={hash}...
[Session] After add: user={id}, session_count={count}, max={max}, stale_removed={n}
[Session] LIMIT EXCEEDED: user={id}, count={count}, max={max} - will remove oldest
[Session] Removing session[{i}]: user={id}, device={hash}..., token={hash}..., age={n}s
[Session] Created invalidation notification: user={id}, token={hash}...
[Session] store_session complete: user={id}, final_count={count}/{max}, device={hash}...
```

**Session Validation:**
```
[Session] is_session_valid called: user={id}, token={hash}...
[Session] Validating token against {count} session(s): user={id}
[Session] Session VALID: user={id}, matched session[{idx}], age={n}s
[Session] Session INVALID: user={id}, token={hash}... not found in {count} session(s)
[Session] Session INVALID: user={id}, no session found (expired or never created)
```

**Session Delete:**
```
[Session] delete_session called: user={id}, token={hash}...
[Session] delete_session: user={id}, existing_sessions={count}
[Session] Removed specific token: user={id}, token={hash}..., device={hash}...
[Session] Token not found in session set: user={id}, token={hash}...
[Session] No session set found for user {id} (may have expired)
```

**Refresh Token Validation:**
```
[RefreshToken] validate_refresh_token called: user={id}, token={hash}..., current_device={hash}..., strict=...
[RefreshToken] INVALID - token not found in Redis: user={id}, token={hash}...
[RefreshToken] Token found: user={id}, stored_device={hash}..., created=..., ip=...
[RefreshToken] DEVICE MISMATCH: user={id}, stored_device={A}, current_device={B}
[RefreshToken] VALID: user={id}, token={hash}...
```

**Refresh Endpoint:**
```
[TokenAudit] /refresh called: ip={ip}
[TokenAudit] Decoded access token: user={id}, exp={exp}, expired_ago={n}s, ip={ip}
[TokenAudit] Device fingerprint headers: user={id}, UA=..., lang=..., encoding=..., platform=..., mobile=...
[TokenAudit] Validating refresh token: user={id}, refresh_token={hash}..., current_device={hash}
[TokenAudit] Refresh FAILED: user={id}, ip={ip}, reason={reason}, stored_device={hash}, current_device={hash}
[TokenAudit] Token refreshed: user={id}, ip={ip}
```

**Session Status Endpoint:**
```
[TokenAudit] /session-status called: user={id}, ip={ip}
[TokenAudit] Session status: ACTIVE: user={id}, token={hash}...
[TokenAudit] Session status: INVALIDATED (max devices): user={id}, notification_ip={ip}
[TokenAudit] Session status: INVALIDATED (expired): user={id}, token={hash}...
```

**Logout:**
```
[TokenAudit] /logout called: user={id}, ip={ip}
[TokenAudit] Logout deleting session: user={id}, token={hash}...
[TokenAudit] Logout revoking refresh token: user={id}, token={hash}...
[TokenAudit] Logout: user={id}, phone=..., ip={ip}
```

**Auth Middleware:**
```
[Auth] get_current_user session check: user={id}, token={hash}..., exp={exp}, expired_ago={n}s
[Auth] get_current_user FAILED: user={id}, token={hash}... - session invalid
```

### Frontend Console Logs

Look for these in browser Developer Tools > Console:

```javascript
[Auth] Starting session monitoring (interval: 120s)
[Auth] Stopping session monitoring
[Auth] Session monitor triggered (tab visible)
[Auth] Session monitor skipped (tab hidden)
[Auth] checkSessionStatus: user={id}
[Auth] /session-status response: status={status}
[Auth] Got 401 from /session-status, attempting token refresh...
[Auth] Token refresh result: SUCCESS|FAILED
[Auth] Refresh failed, calling handleSessionInvalidation
[Auth] Session status: {status} message: {message}
[Auth] Session invalidated by backend: {message}
[Auth] refreshAccessToken called
[Auth] /refresh response: status={status}, ok={ok}
[Auth] /refresh error detail: {...}
[Auth] /refresh failed with no JSON body
[Auth] handleSessionInvalidation called: message="{message}"
```

---

## Potential Root Causes (Hypotheses)

### 1. Device Hash Instability

The device hash is computed from HTTP headers:
- User-Agent
- Accept-Language
- Accept-Encoding
- Sec-CH-UA-Platform (Client Hint)
- Sec-CH-UA-Mobile (Client Hint)

**Issue**: Client Hints (Sec-CH-*) are not consistently sent by browsers. If headers differ between login and refresh, the device hash changes, causing "Device mismatch" error.

**Evidence Needed**: Look for logs showing:
```
[RefreshToken] DEVICE MISMATCH: stored_device={A}, current_device={B}
```

### 2. Session Accumulation Race Condition

Multiple concurrent requests could add sessions without properly cleaning up old ones.

**Evidence Needed**: Look for logs showing:
```
[Session] LIMIT EXCEEDED: user={id}, count=3, max=2
```

### 3. Redis Key Expiry

The Redis session SET expires after 60 minutes. If no activity extends the TTL, the session is lost.

**Evidence Needed**: Look for logs showing:
```
[Session] Session INVALID: user={id}, token not found in 0 session(s)
```

### 4. Misleading Error Message

The frontend shows "max device limit exceeded" for ALL refresh failures, not just the actual device limit scenario.

**Location**: `frontend/src/composables/useLanguage.ts` line 138

---

## How to Analyze Logs

When the issue occurs again:

1. **Note the exact time** when the logout message appeared

2. **Check backend logs** around that time for:
   - Any `FAILED` or `INVALID` log entries
   - The specific `reason` in refresh failures
   - Session counts before/after operations

3. **Check browser console** for:
   - The `/refresh` response status and error detail
   - The sequence of events leading to `handleSessionInvalidation`

4. **Compare device hashes**:
   - Look for `stored_device` vs `current_device` values
   - If they differ, the device hash instability hypothesis is confirmed

---

## Temporary Workaround

If needed, increase the max concurrent sessions limit:

```bash
# In .env file
MAX_CONCURRENT_SESSIONS=5
```

This won't fix the root cause but reduces the likelihood of hitting the limit.

---

## Files Modified for Debug Logging

### Backend

| File | Functions/Endpoints | Log Prefix |
|------|---------------------|------------|
| `services/redis_session_manager.py` | `store_session`, `is_session_valid`, `delete_session`, `validate_refresh_token` | `[Session]`, `[RefreshToken]` |
| `routers/auth/session.py` | `/refresh`, `/session-status`, `/logout` | `[TokenAudit]` |
| `routers/auth/login.py` | `/login`, `/sms/login`, `/loginByXz` | `[TokenAudit]` |
| `utils/auth.py` | `get_current_user` | `[Auth]` |

### Frontend

| File | Functions | Console Prefix |
|------|-----------|----------------|
| `frontend/src/stores/auth.ts` | `startSessionMonitoring`, `checkSessionStatus`, `refreshAccessToken`, `handleSessionInvalidation` | `[Auth]` |

---

## Date Created

2026-01-11

## Status

Comprehensive debug logging added. Waiting for issue to recur to capture logs and confirm root cause.

## Quick Debug Checklist

When issue recurs:

1. Note exact time of logout
2. Search backend logs for `[TokenAudit]` entries around that time
3. Look for:
   - `DEVICE MISMATCH` → Device hash instability (Client Hints issue)
   - `LIMIT EXCEEDED` → Session accumulation bug
   - `token not found in Redis` → Refresh token expired/missing
   - `no session found` → Redis session expired
4. Check browser console for `[Auth]` entries
5. Compare `device_hash` values between login and refresh logs
