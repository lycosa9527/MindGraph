# MindGraph API Endpoints Summary

## Total Endpoints: **134**

This document provides a comprehensive list of all API endpoints in the MindGraph application.

---

## Health & Status Endpoints (5)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/health` | Basic health check | No |
| GET | `/health/redis` | Redis health check | No |
| GET | `/health/database` | Database health check | No |
| GET | `/health/all` | Comprehensive health check (all components) | No |
| GET | `/status` | Application status with metrics | No |

---

## Page Routes (13)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/` | Root page (Vue SPA) | No |
| GET | `/editor` | Interactive editor | Yes (varies by mode) |
| GET | `/admin` | Admin management panel | Admin |
| GET | `/admin/{path}` | Admin sub-routes | Admin |
| GET | `/login` | Login page | No |
| GET | `/auth` | Authentication page | No |
| GET | `/demo` | Demo/Bayi passkey page | No |
| GET | `/dashboard` | Dashboard page | Yes |
| GET | `/dashboard/login` | Dashboard login page | No |
| GET | `/pub-dash` | Public dashboard | No |
| GET | `/debug` | Debug page | Admin (or DEBUG mode) |
| GET | `/loginByXz` | Bayi mode authentication | No |
| GET | `/favicon.ico` | Favicon | No |

---

## Main API Endpoints (14)

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

## Authentication Endpoints (37)

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
| GET | `/api/auth/avatars` | Get available avatars | No |
| PUT | `/api/auth/avatar` | Update user avatar | Yes |
| POST | `/api/auth/phone/send-code` | Send SMS code for phone change | Yes |
| POST | `/api/auth/phone/change` | Complete phone number change | Yes |

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

## Public Dashboard Endpoints (4)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/api/public/stats` | Get dashboard statistics | Dashboard Session |
| GET | `/api/public/map-data` | Get active users map data | Dashboard Session |
| GET | `/api/public/activity-history` | Get activity history | Dashboard Session |
| GET | `/api/public/activity-stream` | SSE stream for real-time activity | Dashboard Session |

---

## School Zone Endpoints (9)

Organization-scoped content sharing for MindMate courses and MindGraph diagrams.

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/api/school-zone/posts` | List shared diagrams | Yes + Org |
| POST | `/api/school-zone/posts` | Create shared diagram | Yes + Org |
| GET | `/api/school-zone/posts/{post_id}` | Get specific diagram | Yes + Org |
| DELETE | `/api/school-zone/posts/{post_id}` | Delete shared diagram | Yes + Org |
| POST | `/api/school-zone/posts/{post_id}/like` | Toggle like on diagram | Yes + Org |
| GET | `/api/school-zone/posts/{post_id}/comments` | List comments | Yes + Org |
| POST | `/api/school-zone/posts/{post_id}/comments` | Add comment | Yes + Org |
| DELETE | `/api/school-zone/posts/{post_id}/comments/{comment_id}` | Delete comment | Yes + Org |
| GET | `/api/school-zone/categories` | List available categories | Yes + Org |

---

## Diagram Storage Endpoints (7)

User diagram storage with CRUD operations.

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | `/api/diagrams` | Create new diagram | Yes |
| GET | `/api/diagrams` | List user's diagrams (paginated) | Yes |
| GET | `/api/diagrams/{diagram_id}` | Get specific diagram | Yes |
| PUT | `/api/diagrams/{diagram_id}` | Update diagram | Yes |
| DELETE | `/api/diagrams/{diagram_id}` | Soft delete diagram | Yes |
| POST | `/api/diagrams/{diagram_id}/duplicate` | Duplicate diagram | Yes |
| POST | `/api/diagrams/{diagram_id}/pin` | Pin/unpin diagram | Yes |

---

## Dify Integration Endpoints (10)

Integration with Dify AI platform for chat and file handling.

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | `/api/dify/files/upload` | Upload file to Dify | Yes |
| GET | `/api/dify/app/parameters` | Get Dify app parameters | Yes |
| GET | `/api/dify/conversations` | List user's conversations | Yes |
| DELETE | `/api/dify/conversations/{id}` | Delete conversation | Yes |
| POST | `/api/dify/conversations/{id}/name` | Rename conversation | Yes |
| GET | `/api/dify/conversations/{id}/messages` | Get conversation messages | Yes |
| GET | `/api/dify/user-id` | Get user's Dify ID | Yes |
| POST | `/api/dify/messages/{message_id}/feedback` | Submit message feedback | Yes |
| GET | `/api/dify/pinned` | List pinned conversation IDs | Yes |
| POST | `/api/dify/conversations/{id}/pin` | Toggle pin status | Yes |

---

## Image Proxy Endpoint (1)

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/api/proxy-image` | Proxy external images (CORS bypass) | No |

---

## Endpoint Categories Summary

| Category | Count |
|----------|-------|
| Health & Status | 5 |
| Page Routes | 13 |
| Main API | 14 |
| Authentication | 37 |
| Cache | 3 |
| Node Palette | 6 |
| Admin Environment | 6 |
| Admin Logs | 5 |
| Admin Realtime | 4 |
| Update Notification | 7 |
| Tab Mode | 2 |
| Voice Agent | 1 |
| Public Dashboard | 4 |
| School Zone | 9 |
| Diagram Storage | 7 |
| Dify Integration | 10 |
| Image Proxy | 1 |
| **Total** | **134** |

---

## Authentication Methods

Endpoints may require one of the following authentication methods:

1. **JWT Token**: `Authorization: Bearer <token>` header
2. **API Key**: `X-API-Key: <key>` header
3. **Cookie**: `access_token` cookie (for browser sessions)
4. **Dashboard Session**: `dashboard_access_token` cookie (for public dashboard)
5. **None**: Public endpoints

---

## Notes

- SSE endpoints (Server-Sent Events) stream data continuously
- Admin endpoints require admin role in addition to authentication
- Some endpoints have different behavior based on `AUTH_MODE` (standard, demo, enterprise, bayi)
- API key authentication is supported for external integrations
- All endpoints support CORS for configured origins
- School Zone endpoints require user to belong to an organization (Yes + Org)
- Rate limiting is applied to most endpoints (varies by endpoint type)

---

*Last Updated: 2025-01-08*
*Version: 5.1.1*

