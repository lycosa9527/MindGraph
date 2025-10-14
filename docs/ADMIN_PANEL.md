# Admin Panel - Settings & Logs Documentation

**Author:** lycosa9527  
**Made by:** MindSpring Team  
**Date:** October 14, 2025

---

## Overview

The MindGraph admin panel provides complete .env configuration management and real-time debug log viewing through a web interface.

**Access:** Login as admin → Navigate to Settings or Debug Logs tabs

---

## 🎯 Features

### 1. Settings Management
- Edit all .env configuration via web UI
- Automatic backup before every save
- Validation before saving
- View & restore from backups (keeps last 30)
- Sensitive data masking (API keys show `***...last4`)
- Categorized, collapsible interface

### 2. Debug Log Viewer
- Real-time log streaming (Server-Sent Events)
- Color-coded log levels
- Filter by level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Search functionality
- Download logs
- Auto-scroll toggle

---

## 📁 Implementation Files

### Backend Services
| File | Lines | Purpose |
|------|-------|---------|
| `services/env_manager.py` | 493 | .env read/write, backup/restore |
| `services/log_streamer.py` | 348 | Log tailing and streaming |
| `models/env_settings.py` | 343 | Pydantic validation models |
| `routers/admin_env.py` | 357 | Settings API endpoints (6) |
| `routers/admin_logs.py` | 269 | Log viewing endpoints (5) |

### Frontend
| File | Lines | Purpose |
|------|-------|---------|
| `static/js/admin-logs.js` | 377 | Log viewer UI |
| `templates/admin.html` | 1670 | Admin interface (updated) |

**Total:** 7 files, 11 API endpoints, 2 admin tabs

---

## 🔌 API Endpoints

### Settings Endpoints (`/api/auth/admin/env/*`)
1. `GET /settings` - Get all settings with masked sensitive data
2. `PUT /settings` - Update settings (creates backup automatically)
3. `POST /validate` - Validate settings without saving
4. `GET /backups` - List all backup files
5. `POST /restore?backup_filename=X` - Restore from backup
6. `GET /schema` - Get settings metadata

### Log Endpoints (`/api/auth/admin/logs/*`)
1. `GET /files` - List available log files
2. `GET /read?source=app&start_line=0&num_lines=100` - Read log range
3. `GET /stream?source=app&follow=true` - Real-time SSE streaming
4. `GET /tail?source=app&lines=50` - Get last N lines
5. `GET /search?query=error&source=app` - Search logs

**Security:** All endpoints require JWT authentication + admin role check

---

## 🎮 How to Use

### Settings Tab

**View/Edit Settings:**
1. Click "⚙️ 系统设置 Settings" tab
2. Click category headers to expand/collapse sections
3. Modify values in input fields
4. See inline descriptions and validation constraints

**Validate & Save:**
1. Click "✓ Validate" to test without saving
2. Fix any validation errors shown
3. Click "💾 Save All Settings"
4. Automatic backup created (`.env.backup.YYYY-MM-DD_HH-MM-SS`)
5. Server restart required for changes to take effect

**Manage Backups:**
1. Click "📦 Backups" button
2. View list of all backups (sorted newest first)
3. Click "Restore" next to desired backup
4. Confirm restoration (creates safety backup first)

**Settings Categories:**
1. 🖥️ **Application Server** - HOST, PORT, DEBUG, EXTERNAL_HOST
2. 🤖 **Qwen API Configuration** - API key, models, temperature, timeout, max tokens
3. ⚙️ **Logging & Feature Flags** - LOG_LEVEL, VERBOSE_LOGGING, FEATURE flags
4. 🔐 **Authentication & Security** - AUTH_MODE, JWT, ADMIN_PHONES, PASSKEYS, INVITATION_CODES

---

### Debug Logs Tab

**Start Viewing Logs:**
1. Click "📋 调试日志 Debug Logs" tab
2. Select log source: Application, Uvicorn, or Errors
3. Click "▶ Start Stream" for real-time updates
4. Logs appear with color-coded levels

**Filter & Search:**
- **Filter by Level:** Select from dropdown (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Search:** Type query and press Enter (case-insensitive substring match)
- **Clear Search:** Click "✕ Clear" to reset

**Controls:**
- **⏸ Pause Stream** - Stop/resume streaming
- **📜 Auto-scroll** - Toggle auto-scroll to latest (ON by default)
- **🗑️ Clear** - Clear current log display
- **💾 Download** - Save last 500 lines as .log file

**Color Coding:**
- 🔵 INFO (blue)
- 🟠 WARNING (orange)
- 🔴 ERROR (red)
- 🔴 CRITICAL (dark red)
- 🟦 DEBUG (gray)

---

## 🔒 Security

### Authentication & Authorization
- ✅ JWT authentication required on ALL endpoints
- ✅ Admin role check (via `is_admin()` function)
- ✅ Session-based access control

### Data Protection
- ✅ API keys/secrets masked: `***...last4`
- ✅ JWT_SECRET_KEY completely hidden
- ✅ DATABASE_URL completely hidden
- ✅ Path traversal prevention in backup restore
- ✅ Read-only log access (no deletion/modification)

### Audit & Logging
- ✅ All changes logged with admin user ID
- ✅ Sensitive values masked in audit logs
- ✅ Backup/restore operations logged

**Forbidden Actions:**
- Cannot modify `JWT_SECRET_KEY` via web (edit .env directly)
- Cannot modify `DATABASE_URL` via web (edit .env directly)

---

## 🛠️ Technical Details

### Environment File Management (`services/env_manager.py`)
- **Backup Strategy:** Timestamped backups (`.env.backup.YYYY-MM-DD_HH-MM-SS`)
- **Retention:** Keeps last 30 backups, auto-deletes older ones
- **Atomic Writes:** Write to temp file → rename (prevents corruption)
- **File Permissions:** 600 (owner read/write only)
- **Comment Preservation:** Preserves comments and structure
- **Cross-Platform:** Windows + Linux compatible (conditional `fcntl` import)

### Log Streaming (`services/log_streamer.py`)
- **Technology:** Server-Sent Events (SSE) for real-time streaming
- **Rate Limiting:** Max 100 lines/second to prevent overwhelming clients
- **Buffer Management:** Max 1000 lines in memory
- **Log Rotation:** Detects and handles log file rotation
- **Parsing:** Regex-based parsing for Uvicorn and Python logging formats
- **Fallback:** Sync file reading if `aiofiles` unavailable

### Validation (`models/env_settings.py`)
- **Framework:** Pydantic models with field validators
- **Constraints:** Type checking, range validation, enum validation
- **Categories:** 10 model classes for organized validation
- **Examples:**
  - PORT: 1-65535
  - Temperature: 0.0-2.0
  - Passkeys: 6 digits
  - Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

---

## 📝 Configuration Categories

### 1. Application Server (`AppSettings`)
- `HOST` - Server host address (default: 0.0.0.0)
- `PORT` - Server port (1-65535, default: 9527)
- `DEBUG` - Debug mode (True/False)
- `EXTERNAL_HOST` - Public IP for external access (optional)

### 2. Qwen API (`QwenAPISettings`)
- `QWEN_API_KEY` - API key (required, masked)
- `QWEN_API_URL` - API endpoint URL
- `QWEN_MODEL_CLASSIFICATION` - Fast/cheap model
- `QWEN_MODEL_GENERATION` - High quality model
- `QWEN_TEMPERATURE` - 0.0-2.0 (default: 0.7)
- `LLM_TEMPERATURE` - Diagram generation (0.0-2.0, default: 0.3)
- `QWEN_MAX_TOKENS` - Max tokens per request
- `QWEN_TIMEOUT` - Request timeout (5-120 seconds, default: 40)

### 3. Logging (`LoggingSettings`)
- `LOG_LEVEL` - DEBUG, INFO, WARNING, ERROR, CRITICAL
- `VERBOSE_LOGGING` - Enable verbose logging (True/False)

### 4. Feature Flags (`FeatureFlagSettings`)
- `FEATURE_LEARNING_MODE` - Enable learning mode
- `FEATURE_THINKGUIDE` - Enable ThinkGuide mode

### 5. Authentication (`AuthSettings`)
- `AUTH_MODE` - standard, enterprise, demo
- `JWT_EXPIRY_HOURS` - JWT token expiry (1-168 hours)
- `ADMIN_PHONES` - Comma-separated admin phone numbers
- `INVITATION_CODES` - ORG:CODE:DATE format
- `DEMO_PASSKEY` - 6-digit demo passkey
- `ADMIN_DEMO_PASSKEY` - 6-digit admin demo passkey

---

## 🔍 Troubleshooting

### Settings Not Saving
- **Check validation:** Click "✓ Validate" to see errors
- **Check logs:** View Debug Logs tab for error messages
- **Check permissions:** Ensure .env file is writable
- **Check backups:** Backup should be created automatically

### Changes Not Taking Effect
- **Restart required:** Server must be restarted for .env changes
- **Cache:** Config has 30-second cache (in `config/settings.py`)
- **Check .env:** Verify changes were written to file

### Log Stream Not Working
- **Check log files exist:** Logs should be in `logs/` directory
- **Check permissions:** Ensure log files are readable
- **Browser compatibility:** EventSource (SSE) required
- **Check network:** EventSource connection may timeout

### Permission Denied
- **Admin role required:** Must be in ADMIN_PHONES list
- **JWT token:** Ensure logged in with valid token
- **Demo mode:** Use admin-demo@system.com in demo mode

---

## 📦 Dependencies

**All dependencies already in `requirements.txt`:**
- `fastapi` - Web framework
- `pydantic` - Validation models
- `python-dotenv` - .env file handling
- `aiofiles` - Async file I/O (with sync fallback)

**No new dependencies required** ✅

---

## 🚀 Quick Start

```bash
# Start the server
python run_server.py

# Access admin panel
# 1. Open browser: http://localhost:9527/admin
# 2. Login with admin credentials
# 3. Navigate to Settings or Debug Logs tabs
```

**Test Checklist:**
- [ ] View settings (all fields populated)
- [ ] Edit a setting value
- [ ] Validate (should pass)
- [ ] Save (backup created)
- [ ] View backups list
- [ ] Restore from backup
- [ ] Start log stream
- [ ] Filter logs by level
- [ ] Search logs
- [ ] Download logs

---

## 📚 Related Documentation

- `docs/API_REFERENCE.md` - Complete API documentation
- `docs/API_KEY_SECURITY_IMPLEMENTATION.md` - API key security
- `env.example` - All available environment variables
- `README.md` - Project overview

---

## 🎯 Summary

**What's Built:**
- ✅ 11 API endpoints (6 settings + 5 logs)
- ✅ 2 admin tabs (Settings + Debug Logs)
- ✅ Complete .env management with backup/restore
- ✅ Real-time log streaming with search/filter
- ✅ Enterprise-grade security
- ✅ Professional, categorized UI

**File Size:** All modules under 500 lines ✅  
**Dependencies:** No new dependencies required ✅  
**Platform:** Windows + Linux compatible ✅  
**Status:** Production ready ✅

