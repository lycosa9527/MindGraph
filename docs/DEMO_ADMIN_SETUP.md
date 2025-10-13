# Demo Admin Setup Guide

## Overview
This guide explains how to set up admin access via demo mode passkeys.

## Quick Setup

### 1. Update your `.env` file

Add or update these lines:

```bash
# Demo Mode Configuration
DEMO_PASSKEY=888888                    # Regular demo users
ADMIN_DEMO_PASSKEY=999999              # Admin demo users

# CRITICAL: Include demo-admin phone for admin detection
ADMIN_PHONES=demo-admin@system.com
```

**⚠️ IMPORTANT:** The `ADMIN_PHONES` line is **required** for admin demo access to work!

If you want to add additional admin phone numbers (for standard login), use commas:
```bash
ADMIN_PHONES=demo-admin@system.com,13800000000,13900000000
```

### 2. Restart the server

After updating `.env`, restart your FastAPI server:

```bash
python main.py
```

or

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 9527
```

## Usage

### Regular Demo Access
1. Visit: `http://localhost:9527/demo`
2. Enter passkey: `888888` (or your custom `DEMO_PASSKEY`)
3. **Automatically redirects to `/editor`**
4. No access to `/admin` panel

### Admin Demo Access
1. Visit: `http://localhost:9527/demo`
2. Enter passkey: `999999` (or your custom `ADMIN_DEMO_PASSKEY`)
3. **Automatically redirects to `/admin`** (admin panel)
4. Full admin access - can manage schools, users, and system settings
5. Can also access `/editor` if needed

### Admin Access from Admin Panel
1. Visit: `http://localhost:9527/admin`
2. Click "Demo Mode" button
3. Enter admin passkey: `999999`
4. Redirected back to `/admin` with full access

## Security

### Authentication Model
- **Demo mode uses JWT tokens** - passkey login creates a valid JWT token
- Passkey is only required at login time (like a password)
- After login, JWT token is stored in browser and validated on each request
- Token validation happens via `/api/auth/me` endpoint
- **No authentication bypass** - demo mode still requires valid tokens

### Configuration
- Both passkeys are configurable via `.env`
- Admin detection is based on phone number matching `ADMIN_PHONES`
- Backend creates separate users:
  - `demo@system.com` for regular demo access
  - `demo-admin@system.com` for admin demo access
- All admin API endpoints verify admin status via `is_admin()` check

### Token Persistence
- JWT tokens are stored in browser `localStorage`
- Tokens remain valid for `JWT_EXPIRY_HOURS` (default: 24 hours)
- Users stay logged in across page refreshes
- Only need to re-enter passkey when:
  - Token expires
  - User explicitly logs out
  - Browser data is cleared

## Troubleshooting

### "Admin passkey not working"

**Solution:** Make sure your `.env` includes:
```bash
ADMIN_PHONES=demo-admin@system.com
```

Then restart the server.

### "Can access /editor without passkey"

This was a bug in `auth-helper.js` that has been fixed. The issue was:
- Old code checked server's `AUTH_MODE` and allowed access if mode was "demo"
- New code properly checks for valid JWT token via `/api/auth/me` endpoint

Make sure you're using the latest `static/js/auth-helper.js`.

### "Admin panel shows 'not authenticated'"

1. Verify you're using the **admin passkey** (not regular passkey)
2. Check browser console for errors
3. Verify `.env` has `ADMIN_PHONES=demo-admin@system.com`
4. Restart the server after changing `.env`

## Testing

### Test Regular Demo Access
```bash
# Visit /demo
# Enter: 888888
# Should redirect to /editor (automatic)
# Try visiting /admin → should show "Admin access denied" alert
```

### Test Admin Demo Access
```bash
# Visit /demo
# Enter: 999999
# Should redirect to /admin (automatic, not /editor!)
# Admin panel should load with full access
# Can manually visit /editor if needed
```

## Architecture

### Backend (`routers/auth.py`)
- `/api/auth/demo/verify` endpoint
- Checks passkey against both `DEMO_PASSKEY` and `ADMIN_DEMO_PASSKEY`
- Creates appropriate user: `demo@system.com` or `demo-admin@system.com`
- Returns `is_admin: true` flag for admin passkeys

### Frontend (`templates/demo-login.html`)
- Accepts 6-digit passkey
- Calls `/api/auth/demo/verify` API
- Stores JWT token and sets mode to 'demo'
- Redirects to `/editor` or respects `?redirect=` parameter

### Authentication (`static/js/auth-helper.js`)
- Stores mode in localStorage for redirect purposes
- Always validates authentication via `/api/auth/me` endpoint
- Redirects based on mode when authentication fails

### Admin Panel (`templates/admin.html`)
- Shows overlay if not authenticated
- Offers both standard and demo login options
- Verifies admin status by testing `/api/auth/admin/stats` endpoint
- Blocks non-admins with alert message

---

**Made by MindSpring Team**  
Author: lycosa9527

