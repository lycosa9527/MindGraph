# Tencent Cloud VOD (云点播)

Standalone media library for school and platform admins. Videos are hosted in Tencent VOD. MindGraph stores FileIds and metadata, then issues short-lived signatures. The management-panel tab **云点播** is the first UI.

## Flag and env

`FEATURE_VOD` (default off). Admin → Features. `/api/vod/*` returns 404 when the flag is off.

| Variable | Role |
|----------|------|
| `TENCENT_VOD_APP_ID` | VOD application / SubAppId |
| `TENCENT_VOD_PLAY_KEY` | Default-distribution **播放密钥** (8–20 alnum). **Not** KEY 防盗链 |
| `TENCENT_VOD_LICENSE_URL` | Public TCPlayer license URL (视立方 console) |
| `TENCENT_VOD_LICENSE_KEY` | Public TCPlayer license key (视立方 console) |
| `TENCENT_VOD_REGION` | Cloud API region (default `ap-guangzhou`) |
| `TENCENT_VOD_PROCEDURE` | Optional task-flow name on client upload signatures |
| `TENCENT_VOD_PSIGN_TTL` | Player JWT lifetime (default 21600s) |
| `TENCENT_VOD_UPLOAD_TTL` | Upload signature lifetime (default 7200s, max 90 days) |
| `TENCENT_VOD_ADAPTIVE_DEFINITION` | `contentInfo.rawAdaptiveDefinition` (default 10) |
| `TENCENT_VOD_SECRET_ID` / `TENCENT_VOD_SECRET_KEY` | Optional CAM override; else `TENCENT_SMS_SECRET_*` |

## Secrets

- CAM SecretId/SecretKey sign Cloud API calls and client upload HMAC-SHA1.
- PlayKey signs JWT `psign` only.
- JSON never returns PlayKey, SecretKey, or durable `*.myqcloud.com` / `vod2` URLs.

## API

Prefix `/api/vod`. Caps: `tab.vod.view` (list/play/config), `tab.vod.edit` (sign/register/refresh/delete). Superadmin and school admin both have these caps. School admins stay in their org.

- `GET /config` — `{ configured, appId, licenseUrl }`
- `POST /uploads/sign` — one-time client upload signature for `vod-js-sdk-v6`
- `POST /media` — register FileId after upload
- `GET /media` — org catalog
- `GET /media/{id}/play` — `{ appId, fileId, psign, licenseUrl, expireAt }` for TCPlayer
- `POST /media/{id}/refresh` — `DescribeMediaInfos` (duration/status only)
- `DELETE /media/{id}` — best-effort `DeleteMedia` then drop the row

Cloud API is TC3-HMAC-SHA256 against `vod.tencentcloudapi.com` version `2018-07-17` (server API PDF 266/7784). Player FileID params match 播放器 SDK PDF 266/7786. `psign` algorithm: [266/45554](https://cloud.tencent.com/document/product/266/45554). Client upload HMAC-SHA1: [266/9221](https://cloud.tencent.com/document/product/266/9221).

## Persistence

`vod_media` (Alembic 0113): org, owner, FileId, title, status, duration_ms. FORCE RLS with `rls_is_system_mode()`. Authz is in the service layer.

## Admin UI

Top-level management-panel tab **云点播**. Hidden when `FEATURE_VOD` is off. Grid/table library, upload dialog (`vod-js-sdk-v6`), preview drawer (TCPlayer 5+ needs `licenseUrl`). Superadmins can filter by school (empty filter lists every org); upload requires a selected school. School admins stay in their org.
