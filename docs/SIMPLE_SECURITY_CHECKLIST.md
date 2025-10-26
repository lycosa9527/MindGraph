# Simple Security Checklist for MindGraph

**Document Version:** 1.0  
**Date:** 2025-10-26  
**Author:** lyc9527  
**Made by:** MTEL Team from Educational Technology, Beijing Normal University

---

## 🎯 Philosophy: Small & Simple Security

This is an **educational application** for K12 teachers. We don't need enterprise-grade security infrastructure, but we need essential protections that are **simple to implement and maintain**.

---

## ✅ Current Security Status (Excellent!)

| Security Feature | Status | Rating |
|-----------------|--------|--------|
| **Password Hashing** | ✅ bcrypt (12 rounds) | Excellent |
| **JWT Authentication** | ✅ 24-hour expiry | Good |
| **CORS Configuration** | ✅ Dev/Prod modes | Good |
| **Account Lockout** | ✅ 5 attempts = 15 min | Good |
| **Rate Limiting** | ✅ Auth endpoints | Good |
| **SQL Injection** | ✅ SQLAlchemy ORM | Protected |
| **Input Validation** | ✅ Pydantic models | Good |
| **Secret Management** | ✅ .env + .gitignore | Good |
| **Error Handling** | ✅ Custom handlers | Good |
| **Request Logging** | ✅ Full tracking | Good |

**Overall Grade: B+ (Production Ready for Educational Use)**

---

## 🔧 Simple Improvements (Optional but Recommended)

### 1. Add Security Headers (5 minutes) ⭐ **High Priority**

**What it does:** Protects against common web attacks (XSS, clickjacking, MIME sniffing)

**How to add:** Add to `main.py` after line 567 (after GZip middleware):

```python
# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Prevent clickjacking (stops your site being embedded in iframes)
    response.headers["X-Frame-Options"] = "DENY"
    
    # Prevent MIME sniffing (stops browser from guessing content types)
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # XSS Protection (blocks reflected XSS attacks)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Content Security Policy (controls what resources can load)
    # Adjust if you use external CDNs or APIs
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:;"
    )
    
    # Referrer Policy (controls what info is sent in Referer header)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response
```

**Test:** Check headers with:
```bash
curl -I http://localhost:9527/health
```

---

### 2. HTTPS in Production ⭐ **Critical Before Public Deployment**

**Why:** Encrypts data in transit (passwords, JWT tokens, etc.)

**Options (pick the easiest for you):**

#### Option A: Cloudflare (Easiest - Zero Config)
1. Sign up at cloudflare.com
2. Point your domain DNS to Cloudflare
3. Enable "Full (Strict)" SSL mode
4. ✅ Done! Free SSL certificate included

**Pros:** Free, automatic, no server changes  
**Cons:** Traffic routes through Cloudflare

#### Option B: Nginx Reverse Proxy (Recommended for VPS)
```nginx
# /etc/nginx/sites-available/mindgraph
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Security headers (can also add here instead of FastAPI)
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    location / {
        proxy_pass http://127.0.0.1:9527;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Get free SSL certificate:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

**Pros:** Full control, free SSL, works offline  
**Cons:** Requires server setup

#### Option C: Uvicorn with SSL (Simple but not recommended)
```bash
uvicorn main:app --host 0.0.0.0 --port 443 --ssl-keyfile key.pem --ssl-certfile cert.pem
```

**Pros:** No extra software  
**Cons:** Uvicorn isn't designed as SSL terminator, use Nginx instead

---

### 3. File Upload Security (Only if you add file uploads)

**If you add file upload features later:**

```python
from fastapi import UploadFile, HTTPException

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

async def validate_file_upload(file: UploadFile):
    """Validate uploaded file"""
    # Check extension
    ext = file.filename.split('.')[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type not allowed: {ext}")
    
    # Check file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large (max 10MB)")
    
    # Reset file pointer for processing
    await file.seek(0)
    
    return True
```

---

### 4. API Rate Limiting (Optional - only if public API)

**Current:** Rate limiting on auth endpoints only  
**Recommendation:** Add rate limiting to public API endpoints if you expose them

**Simple implementation** (if needed):

```python
# Install: pip install slowapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/generate")
@limiter.limit("10/minute")  # Max 10 requests per minute
async def generate_diagram(request: Request):
    # Your code here
    pass
```

**But:** You already have manual rate limiting in `utils/auth.py`, so this is optional.

---

## 📋 Pre-Deployment Checklist

Before deploying to production, verify:

### Environment Variables
- [ ] `DEBUG=False` in production
- [ ] Strong `JWT_SECRET_KEY` (64+ characters)
- [ ] Change `DEMO_PASSKEY` from default
- [ ] Change `ADMIN_DEMO_PASSKEY` from default
- [ ] Set real `ADMIN_PHONES`
- [ ] Real API keys (not placeholders)

### Database
- [ ] Database file permissions (chmod 600)
- [ ] Regular backups configured
- [ ] SQLite in production is OK for <100 concurrent users

### Server
- [ ] HTTPS enabled (see Option A or B above)
- [ ] Firewall configured (only ports 80, 443, SSH)
- [ ] SSH key authentication (disable password login)
- [ ] Non-root user running the app
- [ ] Systemd service for auto-restart

### Monitoring
- [ ] Check logs regularly: `logs/app.log`
- [ ] Monitor disk space (SQLite can grow)
- [ ] Set up uptime monitoring (e.g., UptimeRobot - free)

---

## 🚫 What You DON'T Need (Overkill for Small Apps)

❌ **WAF (Web Application Firewall)** - Too complex for your use case  
❌ **DDoS Protection** - Cloudflare free tier covers this  
❌ **Penetration Testing** - Unless handling sensitive student data  
❌ **SIEM/Log Analysis** - Your logs/ folder is sufficient  
❌ **Multi-factor Authentication** - Nice to have, not essential for K12 tools  
❌ **OAuth2** - JWT is fine for your use case  
❌ **API Gateway** - Single FastAPI app doesn't need this  

---

## 🎯 Priority Recommendations

### Before Public Launch (Must-Have):
1. ✅ **HTTPS** - Use Cloudflare (easiest) or Nginx + Let's Encrypt
2. ✅ **Security Headers** - Add the middleware above
3. ✅ **Change default secrets** - JWT key, demo passkeys

### Nice to Have (Optional):
- ⚪ Regular database backups (weekly cron job)
- ⚪ Monitoring/alerting (UptimeRobot for uptime)
- ⚪ Update dependencies quarterly (`pip list --outdated`)

### Don't Worry About (Not Needed):
- ❌ Advanced rate limiting (unless you get >1000 users)
- ❌ Container orchestration (Docker Compose is fine)
- ❌ Load balancing (single server handles 100s of users)

---

## 📊 Security by Deployment Type

### Type 1: Internal School Network (VPN/Intranet)
**You have:**
- Network-level security ✅
- Controlled user base ✅

**You need:**
- HTTPS: Optional (HTTP is OK on trusted network)
- Security Headers: Yes (easy win)
- Rate Limiting: Optional (trusted users)

**Grade: B (Good enough for internal use)**

---

### Type 2: Public Internet (teachers register freely)
**You have:**
- User authentication ✅
- Password security ✅
- Rate limiting on auth ✅

**You need:**
- HTTPS: **Required** ⚠️
- Security Headers: Yes
- Regular updates: Yes

**Grade: B+ → A (with HTTPS + headers)**

---

### Type 3: High-Security Environment (sensitive student data)
**Additional requirements:**
- Data encryption at rest
- Audit logging
- GDPR/FERPA compliance
- Penetration testing
- Regular security audits

**Note:** This guide doesn't cover high-security scenarios. Consult a security professional.

---

## 🛠️ Quick Security Test

Test your deployment with these free tools:

### 1. SSL Labs (if using HTTPS)
```
https://www.ssllabs.com/ssltest/analyze.html?d=yourdomain.com
```
**Target:** Grade A or A+

### 2. Security Headers Check
```
https://securityheaders.com/?q=yourdomain.com
```
**Target:** Grade A or B

### 3. Mozilla Observatory
```
https://observatory.mozilla.org/analyze/yourdomain.com
```
**Target:** B+ or higher

---

## 📝 Minimal Security Maintenance Plan

**Monthly (5 minutes):**
- [ ] Check `logs/app.log` for unusual activity
- [ ] Verify backups are running

**Quarterly (30 minutes):**
- [ ] Update Python dependencies: `pip list --outdated`
- [ ] Check FastAPI security advisories
- [ ] Review admin accounts

**Annually (1 hour):**
- [ ] Rotate JWT secret key (requires user re-login)
- [ ] Review and update invitation codes
- [ ] Security headers audit

---

## 🎓 Security Philosophy for Educational Apps

**Remember:**
- ✅ **Good security** protects against common attacks
- ✅ **Perfect security** is impossible and expensive
- ✅ **Your priority:** Protect passwords, prevent unauthorized access
- ✅ **Not your priority:** Military-grade encryption, zero-trust architecture

**You're building a tool for teachers, not a banking system.**

Your current security is **good enough for educational use**. Add HTTPS + security headers, and you're ready to deploy! 🚀

---

## 📚 Further Reading (If Interested)

- **FastAPI Security:** https://fastapi.tiangolo.com/tutorial/security/
- **OWASP Top 10:** https://owasp.org/www-project-top-ten/
- **Let's Encrypt:** https://letsencrypt.org/
- **Security Headers:** https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers

---

## 🆘 Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│  MindGraph Security Quick Reference                         │
├─────────────────────────────────────────────────────────────┤
│  ✅ Passwords: bcrypt (12 rounds)                           │
│  ✅ Auth: JWT (24h expiry)                                  │
│  ✅ Database: SQLAlchemy (SQL injection safe)               │
│  ⚠️  HTTPS: Required for production                         │
│  ⚠️  Headers: Add security middleware (5 min)               │
│  📝 Logs: logs/app.log                                       │
│  🔑 Secrets: .env (never commit!)                           │
│  🗄️  Backup: mindgraph.db (weekly)                          │
│  📊 Monitor: https://securityheaders.com                    │
└─────────────────────────────────────────────────────────────┘
```

---

**End of Document**

