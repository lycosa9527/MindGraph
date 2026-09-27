# Tencent Cloud VOD (云点播)

Standalone media library for school and platform admins. Videos are hosted in Tencent VOD. MindGraph stores FileIds and metadata, then issues short-lived signatures. The management-panel tab **在线视频库** is the first UI.

## Flag and env

`FEATURE_VOD` (default off). Admin → Features. `/api/vod/*` returns 404 when the flag is off.

When the flag is on, the document policy allows the upload hosts and TCPlayer playback. `connect-src` includes `https://vod2.qcloud.com`, backup `https://vod2.dnsv1.com`, one-label COS wildcards for the mainland upload parks (`*.cos.ap-shanghai.myqcloud.com` and the same shape for Chongqing, Guangzhou, Beijing, Chengdu, Nanjing, plus `tencentcos.cn`), the playvideo/license hosts baked into TCPlayer 5.3, and `https://*.vod2.myqcloud.com`. `script-src` includes `https://tcsdk.com` (hls and crypto helpers). `media-src` includes `https://*.vod2.myqcloud.com`, which is the default play domain (`{appId}.vod2.myqcloud.com`). `*.myqcloud.com` does not match those hosts. The Vite `index.html` meta lists the same origins for local dev. A custom `TENCENT_VOD_LICENSE_URL` host is added to `connect-src` as well.

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

- `GET /config` — `{ configured, appId, licenseUrl, licenseKey }`
- `POST /uploads/sign` — one-time client upload signature for `vod-js-sdk-v6`
- `POST /media` — register FileId after upload
- `GET /media` — org catalog
- `GET /media/{id}/play` — `{ appId, fileId, psign, licenseUrl, licenseKey, expireAt }` for TCPlayer. With no upload task flow, `psign` uses `audioVideoType: Original` so the uploaded file plays immediately. When `TENCENT_VOD_PROCEDURE` is set, `psign` uses RawAdaptive template `TENCENT_VOD_ADAPTIVE_DEFINITION`.
- `POST /media/{id}/refresh` — `DescribeMediaInfos` (duration/status only)
- `DELETE /media/{id}` — best-effort `DeleteMedia` then drop the row
- `GET /folders` — one-level folders in the selected school
- `POST /folders` — create a folder (`tab.vod.edit`)
- `PATCH /folders/{id}` — rename a folder; duplicate names in the same school return 409
- `DELETE /folders/{id}` — delete a folder; its videos become unfiled
- `PATCH /media/{id}` — move a video into a folder, or clear `folder_id` to leave it unfiled

Cloud API is TC3-HMAC-SHA256 against `vod.tencentcloudapi.com` version `2018-07-17` (server API PDF 266/7784). Player FileID params match 播放器 SDK PDF 266/7786. `psign` algorithm: [266/45554](https://cloud.tencent.com/document/product/266/45554). Client upload HMAC-SHA1: [266/9221](https://cloud.tencent.com/document/product/266/9221).

## Persistence

`vod_media` (Alembic 0113): org, owner, FileId, title, status, duration_ms. `vod_folders` (Alembic 0130): one-level folders per school; deleting a folder sets `vod_media.folder_id` to null. FORCE RLS with `rls_is_system_mode()`. Authz is in the service layer.

## Admin UI

Top-level management-panel tab **在线视频库**. Hidden when `FEATURE_VOD` is off. Grid/table library with search, status filter, and paging, upload dialog (`vod-js-sdk-v6`), preview drawer (TCPlayer 5+ needs `licenseUrl`), refresh metadata, and delete. Editors can create, rename, and delete one-level folders, filter the catalog by folder (including unfiled), move a video between folders, and upload into the folder that is currently open. Superadmins can filter by school (empty filter lists every org); upload and folder actions require a selected school. School admins stay in their org.
