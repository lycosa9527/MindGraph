# Demo Mode Redirect Logic

**Author:** lycosa9527  
**Made by:** MindSpring Team

## Overview

This document describes the complete redirect logic for MindGraph in **demo mode** (`AUTH_MODE=demo`).

## Authentication Flow

### 1. Authentication Methods

In demo mode, there are two types of access:

- **Regular Demo User** - Uses `DEMO_PASSKEY` (default: 888888)
- **Admin Demo User** - Uses `ADMIN_DEMO_PASSKEY` (default: 999999)

### 2. Cookie-Based Authentication

When a user successfully authenticates via `/api/auth/demo/verify`:
- Backend creates JWT token
- Token is stored in **HTTP-only cookie** (`access_token`)
- Token is also returned in response for localStorage
- Cookie expires in 7 days

### 3. Token Validation

All page routes use `get_user_from_cookie()` helper function to:
- Extract token from `access_token` cookie
- Decode and validate JWT token
- Fetch user from database
- Return `User` object or `None` if invalid/expired

## Page Route Redirect Rules

### `/` (Landing Page)
- **No authentication required**
- Anyone can access

### `/auth` (Login/Register)
**Demo Mode Behavior:**
- ✅ **Not logged in** → Show auth page
- 🔄 **Already logged in** → Redirect to `/editor`
- ⚠️ **Demo mode active** → Always redirect to `/demo` (auth page doesn't make sense in demo mode)

**Redirect Flow:**
```
GET /auth (demo mode) → Redirect 303 → /demo
```

### `/demo` (Demo Passkey Login)
**Demo Mode Behavior:**
- ✅ **Not logged in** → Show demo passkey page
- 🔄 **Regular demo user logged in** → Redirect to `/editor`
- 🔄 **Admin demo user logged in** → Redirect to `/admin`

**Redirect Flow:**
```
GET /demo + valid cookie (regular user) → Redirect 303 → /editor
GET /demo + valid cookie (admin user)   → Redirect 303 → /admin
```

### `/editor` (Main Editor)
**Demo Mode Behavior:**
- ✅ **Regular demo user** → Show editor ✅
- ✅ **Admin demo user** → Show editor ✅
- 🔄 **Not logged in** → Redirect to `/demo`

**Redirect Flow:**
```
GET /editor + no cookie/invalid cookie → Redirect 303 → /demo
```

### `/admin` (Admin Panel)
**Demo Mode Behavior:**
- ✅ **Admin demo user** → Show admin panel ✅
- 🔄 **Regular demo user** → Redirect to `/editor` (insufficient permissions)
- 🔄 **Not logged in** → Redirect to `/demo`

**Redirect Flow:**
```
GET /admin + no cookie/invalid cookie    → Redirect 303 → /demo
GET /admin + valid cookie (regular user) → Redirect 303 → /editor
```

## Complete Redirect Matrix

| User Type | `/auth` | `/demo` | `/editor` | `/admin` |
|-----------|---------|---------|-----------|----------|
| **Not Logged In** | → `/demo` | ✅ Show | → `/demo` | → `/demo` |
| **Regular Demo User** | → `/demo` | → `/editor` | ✅ Show | → `/editor` |
| **Admin Demo User** | → `/demo` | → `/admin` | ✅ Show | ✅ Show |

## Implementation Details

### Backend Functions

#### `get_user_from_cookie(token: str, db: Session) -> Optional[User]`
Located in `utils/auth.py`

**Purpose:** Validate JWT token from cookie and return User object

**Parameters:**
- `token` - JWT token from cookie
- `db` - Database session

**Returns:**
- `User` object if valid token
- `None` if invalid/expired token

**Usage:**
```python
auth_cookie = request.cookies.get("access_token")
user = get_user_from_cookie(auth_cookie, db) if auth_cookie else None
if not user:
    return RedirectResponse(url="/demo", status_code=303)
```

#### `is_admin(current_user: User) -> bool`
Located in `utils/auth.py`

**Purpose:** Check if user has admin privileges

**Admin Criteria:**
1. User phone in `ADMIN_PHONES` env variable (production admins)
2. User is `demo-admin@system.com` AND server is in demo mode

**Returns:**
- `True` if user is admin
- `False` otherwise

### Page Routes

All authentication-protected routes in `routers/pages.py`:

1. **Inject database session:** `db: Session = Depends(get_db)`
2. **Get cookie token:** `auth_cookie = request.cookies.get("access_token")`
3. **Validate token:** `user = get_user_from_cookie(auth_cookie, db) if auth_cookie else None`
4. **Check authorization and redirect accordingly**

### Frontend (demo-login.html)

After successful passkey verification:
```javascript
// Backend returns user info with is_admin flag
const result = await response.json();

// Redirect based on admin status
let redirectUrl = result.user.is_admin ? '/admin' : '/editor';
window.location.href = redirectUrl;
```

## Security Considerations

### 1. Cookie Security
- `httponly=True` - Prevents JavaScript access (XSS protection)
- `samesite="lax"` - CSRF protection
- `secure=False` - Set to `True` in production with HTTPS

### 2. Token Validation
- All tokens are validated by decoding JWT
- Expired tokens are rejected
- Invalid tokens return `None` (no exception thrown)

### 3. Admin Protection
- `/admin` route checks both:
  - Valid authentication (has cookie)
  - Admin status (`is_admin()` function)
- Regular demo users cannot access admin panel

### 4. Demo Mode Isolation
- Demo admin passkey only grants admin access in demo mode
- Production admin phones work in all modes
- Demo users (`demo@system.com`, `demo-admin@system.com`) are auto-created

## Testing Scenarios

### Scenario 1: First-time Visitor
```
1. Visit /editor → Redirect to /demo
2. Enter demo passkey (888888)
3. → Redirect to /editor ✅
```

### Scenario 2: Admin First-time Visitor
```
1. Visit /editor → Redirect to /demo
2. Enter admin passkey (999999)
3. → Redirect to /admin ✅
```

### Scenario 3: Regular User Tries Admin
```
1. Already logged in as regular demo user
2. Visit /admin
3. → Redirect to /editor (insufficient permissions)
```

### Scenario 4: Return Visitor (Cookie Still Valid)
```
1. Visit /demo (cookie exists)
2. → Redirect to /editor (or /admin if admin)
3. Direct access to /editor works ✅
```

### Scenario 5: Expired Token
```
1. Visit /editor (cookie exists but expired)
2. Token validation fails → user = None
3. → Redirect to /demo
```

## Environment Variables

Required for demo mode:

```env
# Authentication mode
AUTH_MODE=demo

# Demo passkeys (change in production!)
DEMO_PASSKEY=888888
ADMIN_DEMO_PASSKEY=999999

# JWT configuration
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_EXPIRY_HOURS=168  # 7 days

# Optional: Production admin phones (comma-separated)
ADMIN_PHONES=13800138000,13900139000
```

## Common Issues & Solutions

### Issue 1: Redirect Loop
**Symptom:** Page keeps refreshing between `/demo` and `/editor`

**Cause:** Cookie not being set or not being read properly

**Solution:**
- Verify `/api/auth/demo/verify` sets cookie in response
- Check browser Developer Tools → Application → Cookies
- Ensure `access_token` cookie exists

### Issue 2: Admin Passkey Not Working
**Symptom:** Admin user redirected to `/editor` instead of `/admin`

**Cause:** `is_admin()` not recognizing demo admin user

**Solution:**
- Verify `AUTH_MODE=demo` in `.env`
- Check user phone is `demo-admin@system.com`
- Ensure `ADMIN_DEMO_PASSKEY` matches the passkey used

### Issue 3: Regular User Can Access Admin
**Symptom:** Regular demo user can see admin panel

**Cause:** `/admin` route not checking admin status

**Solution:**
- Verify `/admin` route calls `is_admin(user)`
- Check redirect logic in `routers/pages.py`

## Changelog

**2025-01-14:**
- Added cookie-based authentication
- Implemented `get_user_from_cookie()` helper
- Updated all page routes with proper redirect logic
- Added admin status check for `/admin` route
- Fixed redirect loop issue
- Added comprehensive documentation

## Related Files

- `routers/pages.py` - Page route handlers
- `routers/auth.py` - Authentication API endpoints
- `utils/auth.py` - Authentication helper functions
- `templates/demo-login.html` - Demo passkey login page
- `templates/editor.html` - Main editor page
- `templates/admin.html` - Admin panel page

