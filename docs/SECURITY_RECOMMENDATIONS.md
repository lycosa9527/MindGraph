# MindGraph Security Recommendations

This document summarizes the security review findings for the MindGraph application, including the current security posture and actionable recommendations for improvement.

**Last Updated:** January 2026  
**Review Scope:** Frontend, API, Database, Authentication, Session Management

---

## Current Security Posture

### Authentication & Session Management

| Feature | Status | Implementation |
|---------|--------|----------------|
| JWT Tokens | Implemented | `utils/auth.py` - JWT with configurable expiry |
| httpOnly Cookies | Implemented | `routers/auth/helpers.py` - Prevents XSS token theft |
| Secure Cookie Flag | Implemented | Dynamic based on HTTPS detection |
| SameSite Cookies | Implemented | `lax` for access, `strict` for refresh tokens |
| Refresh Token Binding | Implemented | Device hash + IP binding in Redis |
| Session Invalidation | Implemented | Old sessions invalidated on new login |
| Account Lockout | Implemented | 10 failed attempts triggers 5-minute lockout |
| Redis JWT Secret | Implemented | Auto-generated, shared across workers |

### Rate Limiting

| Endpoint | Limit | Implementation |
|----------|-------|----------------|
| Login | 10 attempts / 15 min | `services/redis_rate_limiter.py` |
| SMS Send | 3 sends / hour | `routers/auth/sms.py` |
| Registration | Distributed lock + captcha | `routers/auth/registration.py` |
| API Diagrams | 100 req / min per user | `routers/api/diagrams.py` |
| Dashboard Passkey | 5 attempts / 15 min per IP | `routers/auth/login.py` |

### Input Validation

| Validation | Limit | Location |
|------------|-------|----------|
| Request Body Size | 5 MB | `main.py` middleware |
| Diagram Spec Size | 500 KB | `services/redis_diagram_cache.py` |
| Prompt Length | 10,000 chars | `frontend/src/pages/CanvasPage.vue` |
| Thumbnail Size | 150 KB | `models/requests.py` |
| Phone Format | 11 digits, starts with 1 | `models/requests.py` validators |
| Name Format | Min 2 chars, no numbers | `models/requests.py` validators |

### Security Headers

All headers implemented in `main.py` via `add_security_headers` middleware:

| Header | Value | Purpose |
|--------|-------|---------|
| X-Frame-Options | DENY | Clickjacking protection |
| X-Content-Type-Options | nosniff | MIME sniffing prevention |
| X-XSS-Protection | 1; mode=block | Reflected XSS protection |
| Content-Security-Policy | Tailored per env | Resource loading control |
| Referrer-Policy | strict-origin-when-cross-origin | Information leakage prevention |
| Permissions-Policy | microphone only | Browser feature restrictions |

### Database Security

| Protection | Status | Implementation |
|------------|--------|----------------|
| SQL Injection | Protected | SQLAlchemy ORM throughout |
| User Data Isolation | Protected | Composite Redis keys `diagram:{user_id}:{diagram_id}` |
| Identifier Validation | Protected | `utils/db_type_migration.py` validates table/column names |
| Path Traversal | Protected | Backup filename validation in `routers/admin_env.py` |

### CSRF Protection

| Feature | Status | Implementation |
|---------|--------|----------------|
| CSRF Token Generation | Implemented | `main.py` - `secrets.token_urlsafe(32)` |
| Token Validation | Implemented | Middleware checks `X-CSRF-Token` header |
| Cookie-based Tokens | Implemented | Non-httpOnly for JS access |

### Password Security

| Feature | Status | Implementation |
|---------|--------|----------------|
| Hashing Algorithm | bcrypt | `utils/auth.py` |
| Salt Rounds | Configurable | `BCRYPT_ROUNDS` env variable |
| 72-byte Limit Handling | Implemented | Proper truncation for long passwords |

---

## Recommendations

### Priority 1: Medium Risk

#### 1.1 Password Complexity Policy

**Current State:** Password validation only requires minimum 8 characters.

**Risk:** Weak passwords are vulnerable to brute force and dictionary attacks.

**Recommendation:** Add password complexity requirements.

**Implementation Location:** `models/requests.py`

```python
@field_validator('password')
@classmethod
def validate_password_strength(cls, v):
    """Validate password meets complexity requirements"""
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not any(c.isupper() for c in v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one number")
    # Optional: require special character
    # if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
    #     raise ValueError("Password must contain at least one special character")
    return v
```

**Affected Models:**
- `RegisterRequest`
- `RegisterWithSMSRequest`
- `ResetPasswordWithSMSRequest`
- `ChangePasswordRequest`

---

#### 1.2 HSTS Header (Strict-Transport-Security)

**Current State:** No HSTS header is set.

**Risk:** Users could be redirected to HTTP version of the site (downgrade attacks).

**Recommendation:** Add HSTS header for production environments.

**Implementation Location:** `main.py` in `add_security_headers` middleware

```python
# Add after other security headers (inside the non-DEBUG block)
if not config.DEBUG:
    # Force HTTPS for 1 year, include subdomains
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
```

**Note:** Only enable after confirming HTTPS is properly configured and all resources load over HTTPS.

---

#### 1.3 Trusted Proxy Validation

**Current State:** `get_client_ip()` trusts `X-Forwarded-For` header unconditionally.

**Risk:** Attackers can spoof their IP address by setting this header directly.

**Recommendation:** Only trust `X-Forwarded-For` from known proxy IPs.

**Implementation Location:** `utils/auth.py`

```python
import os

# List of trusted proxy IPs (comma-separated in env)
TRUSTED_PROXIES = set(
    ip.strip() 
    for ip in os.getenv('TRUSTED_PROXIES', '127.0.0.1,::1').split(',')
    if ip.strip()
)

def get_client_ip(request: Request) -> str:
    """
    Get real client IP address, validating proxy trust.
    
    Only trusts X-Forwarded-For from known proxy IPs to prevent spoofing.
    """
    direct_ip = request.client.host if request.client else 'unknown'
    
    # Only trust forwarded headers from known proxies
    if direct_ip in TRUSTED_PROXIES:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
            logger.debug(f"Client IP from trusted proxy: {client_ip}")
            return client_ip
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
    
    return direct_ip
```

**Environment Variable:**
```ini
# .env - Add trusted proxy IPs
TRUSTED_PROXIES=127.0.0.1,::1,10.0.0.1
```

---

### Priority 2: Low Risk

#### 2.1 CORS Method/Header Restriction

**Current State:** CORS allows all methods and headers (`["*"]`).

**Risk:** Overly permissive CORS could allow unexpected request types.

**Recommendation:** Restrict to actually used methods and headers.

**Implementation Location:** `main.py`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type", 
        "X-CSRF-Token",
        "X-API-Key",
        "X-Language",
        "Accept",
        "Origin",
    ],
)
```

---

#### 2.2 WebSocket Token Visibility

**Current State:** WebSocket authentication token can be passed via query parameter.

**Risk:** Tokens in URLs may appear in server logs and browser history.

**Recommendation:** Document that cookie-based auth is preferred; query param is fallback only.

**Current Implementation (acceptable):**
```python
# routers/voice.py - Token is still validated and session-checked
token = websocket.query_params.get('token')
if not token:
    token = websocket.cookies.get('access_token')
```

**Note:** This is acceptable because:
1. Cookie-based auth is tried first
2. Token is validated against Redis session
3. WebSocket connections are typically short-lived

---

## Security Checklist

| Category | Status | Notes |
|----------|--------|-------|
| Authentication | Good | JWT + httpOnly cookies |
| Authorization (RBAC) | Good | Admin/Manager/User roles |
| Rate Limiting | Good | Redis-backed, per-user and per-IP |
| Input Validation | Good | Pydantic + middleware |
| Output Encoding | Good | Vue.js auto-escaping |
| CSRF Protection | Good | Token-based |
| Session Management | Good | Redis sessions with invalidation |
| Password Hashing | Good | bcrypt |
| Security Headers | Good | Add HSTS for production |
| SQL Injection | Protected | ORM usage |
| XSS | Protected | CSP + encoding |
| IDOR | Protected | User isolation |
| Path Traversal | Protected | Filename validation |
| Logging Secrets | None Found | Passwords/tokens not logged |
| Hardcoded Secrets | None Found | All secrets from env |

---

## Environment Security Checklist

Before deploying to production, verify:

- [ ] `DEBUG=False` in `.env`
- [ ] Strong `REDIS_URL` with password authentication
- [ ] `TRUSTED_PROXIES` configured if behind reverse proxy
- [ ] HTTPS enabled and properly configured
- [ ] Rate limiting thresholds appropriate for expected traffic
- [ ] Backup strategy for SQLite database
- [ ] Log rotation configured to prevent disk exhaustion
- [ ] Nginx/reverse proxy configured with additional rate limiting

---

## References

- OWASP Top 10 (2021): https://owasp.org/Top10/
- OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP Session Management Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- Content Security Policy Reference: https://content-security-policy.com/
