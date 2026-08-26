# OAuth QR login (WeChat + DingTalk)

MindGraph supports **WeChat Open Platform 网站应用** and **DingTalk OAuth 2.0 扫码登录** for end-user sign-in. This is separate from Gewe (admin WeChat bot) and from MindBot pair-code binding.

## Feature flags

| Variable | Default | Purpose |
|----------|---------|---------|
| `FEATURE_WECHAT_LOGIN` | **`False`** | WeChat QR login/bind. WeChat Open Platform allows **one** callback domain — enable only on production |
| `FEATURE_DINGTALK_LOGIN` | **`False`** | DingTalk QR login/bind (per school AppKey/Secret). Enable on production. |
| `WECHAT_OAUTH_APP_ID` | *(empty)* | Global WeChat 网站应用 AppID — required when WeChat is on |
| `WECHAT_OAUTH_APP_SECRET` | *(empty)* | Global WeChat AppSecret |

WeChat login is **platform-wide**: `FEATURE_WECHAT_LOGIN` plus AppID/Secret. It is not a per-school setting. DingTalk stays off until the school adds AppKey/Secret under `FEATURE_DINGTALK_LOGIN`. The public flags API exposes `feature_wechat_login` and `feature_dingtalk_login`. Shared `/providers` and `/links` stay up if either flag is on. Production validates WeChat secrets only when `FEATURE_WECHAT_LOGIN=True` (warns if unset; fails if only one of AppID/Secret is set). Leftover `FEATURE_OAUTH_LOGIN` is ignored (startup warning) — delete it from `.env`.

## Official API references

Cross-check implementation against these docs (do **not** use legacy DingTalk `oapi.dingtalk.com` / `ddLogin.js` 0.0.5):

| Provider | Official docs | MindGraph usage |
|----------|---------------|-----------------|
| WeChat 网站应用 | [网站应用微信登录](https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Wechat_Login.html) | `wxLogin.js`, scope `snsapi_login`, callback `?code=&state=` |
| WeChat UnionID | [授权后接口 UnionID](https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Authorized_Interface_Calling_UnionID.html) | Store `unionid` (fallback `openid`) in `oauth_user_links` |
| DingTalk OAuth 2.0 | [统一授权登录第三方网站](https://developers.dingtalk.com/document/app/use-dingtalk-account-to-log-on-to-third-party-websites-1) | `ddlogin.js` 0.21.0, `DTFrameLogin`, `prompt: "consent"` |
| DingTalk user token | [获取用户 token (userAccessToken)](https://open.dingtalk.com/document/development/obtain-user-token) | `POST api.dingtalk.com/v1.0/oauth2/userAccessToken` with `authCode` **immediately** |
| DingTalk profile | [获取用户通讯录个人信息](https://open.dingtalk.com/document/orgapp/tutorial-obtaining-user-personal-information) | `GET contact/users/me` → `unionId` |
| DingTalk corp scope | [获取登录用户的访问凭证](https://open.dingtalk.com/document/development/obtain-identity-credentials) | When `dingtalk_corp_id` set: scope `openid corpid`, validate `corpId` from token response |

### End-to-end flow (matches official embed + server exchange)

```mermaid
flowchart LR
  subgraph wechat [WeChat official flow]
    W1[WxLogin iframe] --> W2["redirect ?code=&state="]
    W2 --> W3[GET /oauth/wechat/callback]
    W3 --> W4[sns/oauth2/access_token]
  end
  subgraph dingtalk [DingTalk official flow]
    D1[DTFrameLogin iframe] --> D2[successCb authCode]
    D2 --> D3[POST /oauth/dingtalk/complete]
    D3 --> D4[userAccessToken + contact/users/me]
  end
  W4 --> Link[oauth_user_links lookup]
  D4 --> Link
  Link --> Session[JWT cookies]
```

## Login behavior

- **Pre-linked users only** — scan succeeds at WeChat but MindGraph returns `oauth_not_linked` and **does not create an account**. Teachers sign in with password first, then **账户 → 账户绑定 → 绑定微信**. Login stays blocked until that row exists (or an admin pre-links).
- **Login UI** — Login modal: 忘记密码 \| 验证码登录 / **微信登录** → WeChat QR (hidden when `feature_wechat_login` is false). The panel asks the user to scan; `oauth_not_linked` is a toast after a scan that has no bind row.
- **Org context** — WeChat login does not need an invitation code; the bound account is resolved after the scan. DingTalk QR login still needs `?invite=` or the register-form invitation code.
- **Callback cookies** — WeChat GET callback sets JWT cookies on the returned `RedirectResponse` (same pattern as Word embed auth). `WxLogin` uses `self_redirect: false` so the top window follows that redirect.

## Account bindings (three providers)

| Provider | Mechanism | Purpose |
|----------|-----------|---------|
| MindBot | Pair-code (`DingTalkPairModal`) | Save diagrams to DingTalk via robot |
| WeChat | OAuth bind (`GET /oauth/wechat/bind/start`) | QR sign-in to MindGraph |
| DingTalk | OAuth bind (`POST /oauth/dingtalk/bind/complete`) | QR sign-in to MindGraph |

## Admin UI (组织管理)

**DingTalk AppKey / AppSecret / CorpId** live under **组织管理 → 编辑学校 → 其他设置** (General tab). WeChat status (AppID + callback) is shown there for operators but is not a school toggle — credentials stay in server `.env`. Saving **其他设置** persists DingTalk org fields.

## Data model

- **`organization_oauth_configs`** — per org DingTalk AppKey/Secret and optional `dingtalk_corp_id`.
- **`oauth_user_links`** — maps `(org_id, provider, external_id)` → `user_id`. Stores WeChat `unionid` and DingTalk `unionId`.

## API routes (`/api/auth/oauth`)

| Route | Auth | Purpose |
|-------|------|---------|
| `GET /providers` | Public | Enabled providers; `?invite=` required for DingTalk |
| `GET /wechat/start`, `/wechat/callback` | Public / redirect | WeChat login |
| `GET /dingtalk/start`, `POST /dingtalk/complete` | Public | DingTalk login (prefer JS `authCode` POST) |
| `GET /links`, `DELETE /links/{provider}` | Session | Self-bind status / unbind (`wechat_enabled` is platform-wide) |
| `GET /wechat/bind/start`, `/wechat/bind/callback` | Session | WeChat self-bind |
| `GET /dingtalk/bind/start`, `POST /dingtalk/bind/complete` | Session | DingTalk self-bind |

Admin: `GET/PUT /api/auth/admin/organizations/{id}/oauth-config`.

## Callback URLs

Configure in external consoles (DingTalk requires **exact** URL match):

- WeChat **授权回调域**: production domain only (e.g. `mindgraph.example.com`)
- WeChat redirect: `https://{domain}/api/auth/oauth/wechat/callback`
- DingTalk **钉钉登录与分享**: `https://{domain}/api/auth/oauth/dingtalk/callback`

## Security

- Redis OAuth `state` — 10 minute TTL, one-time use (matches WeChat `code` lifetime).
- Anonymous WeChat/DingTalk login callbacks bind `system_bootstrap` RLS (same as `/login`) so `resolve_login_user` can load the bound `users` row. Without it, deny-default RLS finds the link then returns `oauth_not_linked` (`user missing`).
- DingTalk `authCode` — exchange immediately on receipt; no retry queue.
- When `dingtalk_corp_id` is set, validate `corpId` from the token response (`oauth_corp_mismatch` on mismatch).
- Production guard warns when OAuth is enabled without HTTPS `EXTERNAL_BASE_URL`.
- CSP must allow official widget hosts or the bind/login modal cannot load the QR
  ([`oauth_csp.py`](../../services/auth/oauth/oauth_csp.py), HTTP header + Vite `index.html` meta):
  - WeChat parent: `script-src` `res.wx.qq.com`, `frame-src` `open.weixin.qq.com`,
    `connect-src` `open.weixin.qq.com` + `long.open.weixin.qq.com` (QR uuid poll)
  - DingTalk: `script-src` `g.alicdn.com`, `frame-src` / `connect-src` `login.dingtalk.com`
  - Not listed: 企业微信 `open.work.weixin.qq.com`, 公众号 `mp.weixin.qq.com`, 网页微信 `wx.qq.com`

## Operator checklist

### WeChat (MindGraph operator, once)

1. Register **网站应用** at [open.weixin.qq.com](https://open.weixin.qq.com) — see [Wechat_Login](https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Wechat_Login.html).
2. Set **授权回调域** to your production domain.
3. Set `FEATURE_WECHAT_LOGIN=True` and `WECHAT_OAUTH_APP_ID` / `WECHAT_OAUTH_APP_SECRET` on the **production** server only.
4. Restart the app. WeChat bind/login is then available for every school. Leave both flags `False` on local/dev. Set `FEATURE_DINGTALK_LOGIN=True` on production when school DingTalk QR is needed.

### DingTalk (per school, with school IT)

1. Set `FEATURE_DINGTALK_LOGIN=True` on the production server `.env` (defaults off).
2. Create **企业内部应用** with **登录第三方网站 / 扫码登录** — see [DingTalk OAuth doc](https://developers.dingtalk.com/document/app/use-dingtalk-account-to-log-on-to-third-party-websites-1).
3. In **钉钉登录与分享**, set redirect URL to the DingTalk callback above (**exact match**).
4. Apply **个人权限**: `permission-open_app_api_base`, `Contact.User.Read` (+ 个人手机号信息权限 if storing `mobile`).
5. Provide AppKey, AppSecret, optional CorpId to MindGraph admin.
6. Enter credentials in **组织管理 → 其他设置 → 扫码登录** and enable DingTalk login.

## Code ↔ official doc audit (verified in repo)

| Official requirement | Doc source | Code location | Status |
|---------------------|------------|---------------|--------|
| WxLogin.js from `res.wx.qq.com` + iframe `open.weixin.qq.com` + poll `long.open.weixin.qq.com` | [Wechat_Login](https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Wechat_Login.html) | CSP `oauth_csp.py` + Vite `index.html` | Match |
| WxLogin + `snsapi_login` + `self_redirect: false` | [Wechat_Login](https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Wechat_Login.html) | `useOAuthQrLogin.ts` (`wxLogin.js`, official default top-window jump) | Match |
| Callback `?code=&state=` | WeChat doc | `router.py` `wechat_oauth/callback` | Match |
| `GET sns/oauth2/access_token` | WeChat doc | `wechat_oauth_client.py` | Match |
| Store `unionid` (fallback `openid`) | [UnionID doc](https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Authorized_Interface_Calling_UnionID.html) | `WechatOauthClient.resolve_external_id` | Match |
| `ddlogin.js` 0.21.0 + `DTFrameLogin` | [DingTalk tutorial](https://open.dingtalk.com/document/orgapp/tutorial-obtaining-user-personal-information) | `useOAuthQrLogin.ts` | Match |
| `prompt: "consent"` required | DingTalk OAuth doc | `useOAuthQrLogin.ts` | Match |
| JS callback returns `authCode` (not `code`) | DingTalk doc | `useOAuthQrLogin.ts` → POST `/dingtalk/complete` | Match |
| `POST …/oauth2/userAccessToken` body `{ clientId, clientSecret, code, grantType }` | [userAccessToken](https://open.dingtalk.com/document/development/obtain-user-token) | `dingtalk_oauth_client.py` | Match |
| `GET contact/users/me` + `x-acs-dingtalk-access-token` | DingTalk doc | `dingtalk_oauth_client.py` | Match |
| Store DingTalk `unionId` | DingTalk doc | `oauth_login_service.exchange_dingtalk_identity` | Match |
| Iframe embed `scope: openid` only (not `openid corpid`) | DingTalk tutorial | `oauth_login_service._dingtalk_scope_for_config` | Match (fixed) |
| No legacy `oapi.dingtalk.com` OAuth | — | OAuth module only uses `api.dingtalk.com` | Match |
| State TTL 10 min (WeChat code lifetime) | WeChat doc | `oauth_constants.OAUTH_STATE_TTL_SECONDS = 600` | Match |

Regression tests: `tests/test_oauth_official_alignment.py`, `tests/test_oauth_login.py`.

## Error handling and user notifications

Backend exposes stable `oauth_*` codes via redirects (`/auth?error=…`) and JSON `detail` on POST complete endpoints. Internal client codes (`wechat_exchange_failed`, etc.) are normalized in `normalize_oauth_error_code()` before reaching the client.

| Code | Meaning | Frontend toast |
|------|---------|----------------|
| `oauth_not_linked` | Scan succeeded but no `oauth_user_links` row — QR login never creates an account | Warning — register, password sign-in, then bind under Account linking |
| `oauth_already_bound` | This user already has a different WeChat/DingTalk linked | Warning — unbind first |
| `oauth_external_taken` | Identity already linked to another user | Warning |
| `oauth_invalid_code` | WeChat `40029` / `40163` / `41008` — expired or reused `code` | Error — rescan |
| `oauth_rate_limited` | WeChat `-1` / `45009` / `45011` | Error — wait and retry |
| `oauth_misconfigured` | WeChat `40013` / `40125` or missing AppID/Secret | Error — admin |
| `oauth_invalid_state` | Expired or invalid Redis state | Error — rescan |
| `oauth_corp_mismatch` | DingTalk corpId ≠ school config | Error |
| `oauth_exchange_failed` | Token/userinfo exchange failed | Error |
| `oauth_disabled` | Feature off, or DingTalk not enabled for the school | Error |

WeChat `errcode` / `errmsg` / `rid` from [全局错误码](https://developers.weixin.qq.com/doc/oplatform/developers/errCode/) are logged on the backend (`WeChat sns/oauth2/access_token failed errcode=…`). Only the website-login subset is mapped to toasts.

Frontend: `useOAuthRouteFeedback` in `App.vue` handles `/auth?error=…` (login) and `/?error=…` / `/?oauth_bind=wechat|dingtalk` (bind); `useOAuthQrLogin.ts` handles DingTalk JS POST and QR start failures. Shared mapping in `oauthLoginUi.ts`. Query params are stripped after toast.

**Note:** MindBot robot/media still uses `oapi.dingtalk.com` — that is a separate DingTalk OpenAPI feature, not OAuth QR login.

## Related docs

- MindBot pair binding: [`dingtalk_account_binding.md`](dingtalk_account_binding.md)
- Production deploy: [`production_security_deploy.md`](production_security_deploy.md)
