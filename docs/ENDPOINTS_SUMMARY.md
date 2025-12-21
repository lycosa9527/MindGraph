# MindGraph API Endpoints Summary

## Total Endpoints: **91**

This document provides a comprehensive list of all API endpoints in the MindGraph application.

---

## Health & Status Endpoints (3)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/health` | Basic health check | No |
| GET | `/status` | Application status with metrics | No |
| GET | `/health/database` | Database health check | No |

---

## Page Routes (8)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/` | Root page (redirects based on auth mode) | No |
| GET | `/debug` | Debug page | Admin (or DEBUG mode) |
| GET | `/editor` | Interactive editor | Yes (varies by mode) |
| GET | `/auth` | Authentication page | No |
| GET | `/loginByXz` | Bayi mode authentication | No |
| GET | `/demo` | Demo/Bayi passkey page | No |
| GET | `/favicon.ico` | Favicon | No |
| GET | `/admin` | Admin management panel | Admin |

---

## Main API Endpoints (13)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | `/api/ai_assistant/stream` | AI assistant streaming (SSE) | Yes |
| POST | `/api/generate_graph` | Generate interactive graph | Yes |
| POST | `/api/export_png` | Export PNG from graph data | Yes |
| POST | `/api/generate_png` | Generate PNG directly | Yes |
| POST | `/api/generate_dingtalk` | Generate PNG for DingTalk | Yes |
| GET | `/api/temp_images/{filename}` | Get temporary image | No |
| POST | `/api/frontend_log` | Frontend logging | No |
| POST | `/api/frontend_log_batch` | Frontend batch logging | No |
| POST | `/api/recalculate_mindmap_layout` | Recalculate mindmap layout | Yes |
| GET | `/api/llm/metrics` | LLM service metrics | No |
| POST | `/api/generate_multi_parallel` | Multi-generation (parallel) | Yes |
| GET | `/api/llm/health` | LLM services health | No |
| POST | `/api/generate_multi_progressive` | Multi-generation (progressive) | Yes |
| POST | `/api/feedback` | Submit feedback | Yes |

---

## Authentication Endpoints (33)

### Public Auth Endpoints

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/api/auth/mode` | Get authentication mode | No |
| GET | `/api/auth/organizations` | List organizations | No |
| POST | `/api/auth/register` | User registration | No |
| POST | `/api/auth/login` | User login | No |
| GET | `/api/auth/captcha/generate` | Generate captcha | No |
| POST | `/api/auth/sms/send` | Send SMS code | No |
| POST | `/api/auth/sms/verify` | Verify SMS code | No |
| POST | `/api/auth/register_sms` | Register with SMS | No |
| POST | `/api/auth/login_sms` | Login with SMS | No |
| POST | `/api/auth/reset_password` | Reset password | No |
| GET | `/api/auth/me` | Get current user | Yes |
| POST | `/api/auth/demo/verify` | Verify demo passkey | No |
| POST | `/api/auth/logout` | User logout | Yes |

### Admin Auth Endpoints

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/api/auth/admin/organizations` | List all organizations | Admin |
| POST | `/api/auth/admin/organizations` | Create organization | Admin |
| PUT | `/api/auth/admin/organizations/{org_id}` | Update organization | Admin |
| DELETE | `/api/auth/admin/organizations/{org_id}` | Delete organization | Admin |
| GET | `/api/auth/admin/users` | List all users | Admin |
| PUT | `/api/auth/admin/users/{user_id}` | Update user | Admin |
| DELETE | `/api/auth/admin/users/{user_id}` | Delete user | Admin |
| PUT | `/api/auth/admin/users/{user_id}/unlock` | Unlock user | Admin |
| PUT | `/api/auth/admin/users/{user_id}/reset-password` | Reset user password | Admin |
| GET | `/api/auth/admin/settings` | Get admin settings | Admin |
| PUT | `/api/auth/admin/settings` | Update admin settings | Admin |
| GET | `/api/auth/admin/stats` | Get admin statistics | Admin |
| GET | `/api/auth/admin/token-stats` | Get token usage statistics | Admin |
| GET | `/api/auth/admin/stats/trends` | Get statistics trends | Admin |
| GET | `/api/auth/admin/api_keys` | List API keys | Admin |
| POST | `/api/auth/admin/api_keys` | Create API key | Admin |
| PUT | `/api/auth/admin/api_keys/{key_id}` | Update API key | Admin |
| DELETE | `/api/auth/admin/api_keys/{key_id}` | Delete API key | Admin |
| PUT | `/api/auth/admin/api_keys/{key_id}/toggle` | Toggle API key | Admin |

---

## Cache Endpoints (3)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/cache/status` | Cache status | Yes |
| GET | `/cache/performance` | Cache performance metrics | Yes |
| GET | `/cache/modular` | Modular cache status | Yes |

---

## Node Palette Endpoints (6)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | `/thinking_mode/node_palette/start` | Start node palette (SSE) | Yes |
| POST | `/thinking_mode/node_palette/next_batch` | Get next batch (SSE) | Yes |
| POST | `/thinking_mode/node_palette/select_node` | Log node selection | Yes |
| POST | `/thinking_mode/node_palette/finish` | Finish node palette | Yes |
| POST | `/thinking_mode/node_palette/cancel` | Cancel node palette | Yes |
| POST | `/thinking_mode/node_palette/cleanup` | Cleanup session | Yes |

---

## Admin Environment Settings (6)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/api/auth/admin/env/settings` | Get environment settings | Admin |
| PUT | `/api/auth/admin/env/settings` | Update environment settings | Admin |
| POST | `/api/auth/admin/env/validate` | Validate settings | Admin |
| GET | `/api/auth/admin/env/backups` | List backups | Admin |
| POST | `/api/auth/admin/env/restore` | Restore from backup | Admin |
| GET | `/api/auth/admin/env/schema` | Get settings schema | Admin |

---

## Admin Log Streaming (5)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/api/auth/admin/logs/files` | List log files | Admin |
| GET | `/api/auth/admin/logs/read` | Read log file | Admin |
| GET | `/api/auth/admin/logs/stream` | Stream logs (SSE) | Admin |
| GET | `/api/auth/admin/logs/tail` | Tail log file | Admin |
| GET | `/api/auth/admin/logs/search` | Search logs | Admin |

---

## Admin Realtime Monitoring (4)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/api/auth/admin/realtime/stats` | Get realtime stats | Admin |
| GET | `/api/auth/admin/realtime/active-users` | Get active users | Admin |
| GET | `/api/auth/admin/realtime/activities` | Get recent activities | Admin |
| GET | `/api/auth/admin/realtime/stream` | Stream updates (SSE) | Admin |

---

## Update Notification Endpoints (7)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/api/update-notification` | Get notification | Yes |
| POST | `/api/update-notification/dismiss` | Dismiss notification | Yes |
| GET | `/api/admin/update-notification` | Get config (admin) | Admin |
| PUT | `/api/admin/update-notification` | Set config (admin) | Admin |
| DELETE | `/api/admin/update-notification` | Disable notification (admin) | Admin |
| POST | `/api/admin/update-notification/reset-dismissed` | Reset dismissed states | Admin |
| POST | `/api/admin/update-notification/upload-image` | Upload image | Admin |

---

## Tab Mode Endpoints (2)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | `/api/tab_suggestions` | Get autocomplete suggestions | Yes |
| POST | `/api/tab_expand` | Expand node | Yes |

---

## Voice Agent Endpoints (1)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | `/api/voice/cleanup/{diagram_session_id}` | Cleanup voice session | Yes |

---

## Endpoint Categories Summary

| Category | Count |
|----------|-------|
| Health & Status | 3 |
| Page Routes | 8 |
| Main API | 13 |
| Authentication | 33 |
| Cache | 3 |
| Node Palette | 6 |
| Admin Environment | 6 |
| Admin Logs | 5 |
| Admin Realtime | 4 |
| Update Notification | 7 |
| Tab Mode | 2 |
| Voice Agent | 1 |
| **Total** | **91** |

---

## Authentication Methods

Endpoints may require one of the following authentication methods:

1. **JWT Token**: `Authorization: Bearer <token>` header
2. **API Key**: `X-API-Key: <key>` header
3. **Cookie**: `access_token` cookie (for browser sessions)
4. **None**: Public endpoints

---

## Testing

Run the comprehensive endpoint test script:

```bash
python tests/test_all_endpoints.py
python tests/test_all_endpoints.py --base-url http://localhost:9527
python tests/test_all_endpoints.py --json
```

---

## Notes

- SSE endpoints (Server-Sent Events) stream data continuously
- Admin endpoints require admin role in addition to authentication
- Some endpoints have different behavior based on `AUTH_MODE` (standard, demo, enterprise, bayi)
- API key authentication is supported for external integrations
- All endpoints support CORS for configured origins

---

*Last Updated: 2025-12-21*
*Version: 4.37.3*

