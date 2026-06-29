# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [5.132.0] - 2026-06-29

> **Chrome extension document extract, SmartEdu file-reader tab, and Celery broker Redis RESP2 hardening.**

### Added

- **Chrome extension — Extract document** — Popup and context-menu action on ~25 Chinese education/document hosts; four engines (`canvas-pdf`, `html2canvas-pdf`, `api-binary`, `dom-article`) with auto-scroll, progress stages, and local download ([`doc-extract/`](chrome-extension/doc-extract/), [`background.js`](chrome-extension/background.js), [`popup.js`](chrome-extension/popup.js)).
- **Chrome extension — SmartEdu pipeline** — `doc-extract/smartedu/` URL parser, metadata fetch, binary downloader, and page-token reader; shared fixtures with Python tests ([`tests/fixtures/doc-extract/smartedu/`](tests/fixtures/doc-extract/smartedu/)).
- **Chrome extension — vitest** — Engine helper tests and npm scripts ([`chrome-extension/package.json`](chrome-extension/package.json), [`vitest.config.js`](chrome-extension/vitest.config.js)).
- **File reader — SmartEdu tab** — WebView2 login + paste-token fallback, `classActivity` URL parse, four-asset checklist, ffmpeg MP4 merge, optional Document Summary package upload ([`smartedu_panel.py`](clients/file-reader/file_reader/smartedu_panel.py), [`smartedu/`](clients/file-reader/file_reader/smartedu/)).
- **File reader — chat platform modules** — WeChat, DingTalk, and WeCom split into dedicated packages with DPAPI key stores, DB readers, and export helpers ([`wechat/`](clients/file-reader/file_reader/wechat/), [`dingtalk/`](clients/file-reader/file_reader/dingtalk/), [`wecom/`](clients/file-reader/file_reader/wecom/)).
- **File reader — GUI notebook** — Two-tab shell (Chat history + SmartEdu) with auth dialog, platform status, edition subtitle, and mousewheel scroll fixes ([`gui.py`](clients/file-reader/file_reader/gui.py)).
- **Celery broker RESP2 patch** — Force kombu Redis `ConnectionPool` to RESP2 so Celery workers skip redis-py 8 SCH `CLIENT MAINT_NOTIFICATIONS` probes ([`celery_broker_redis.py`](config/celery_broker_redis.py)).

### Changed

- **File reader build** — Embedded ffmpeg essentials in onefile exe (~80–110 MB); `deploy_to_desktop.ps1` for Desktop ship ([`build_windows.ps1`](clients/file-reader/build_windows.ps1)).
- **Redis connection options** — Document Celery broker RESP2 split; async SCH disable gated on redis-py signature parity ([`redis_connection_options.py`](services/redis/redis_connection_options.py)).
- **README** — Document Summary chat handoff and SmartEdu/file-reader capabilities.

### Fixed

- **File reader server URL** — Additional localhost/dev origin normalization tests ([`test_file_reader_server_url.py`](tests/test_file_reader_server_url.py)).
- **Redis connection options tests** — Cover async maint-notifications support probe and RESP3 default toggle ([`test_redis_connection_options.py`](tests/test_redis_connection_options.py)).

### Tests

- **File reader / SmartEdu** — `test_smartedu_*`, `test_wechat_*`, `test_dingtalk_*`, `test_wecom_*`, `test_conversation_list.py`.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): syncs with root **`VERSION`** (5.132.0) on next `npm run build` (`prebuild` → `sync-version`).

## [5.131.0] - 2026-06-28

> **MindMate SSE keepalive, unified Dify conversation routing, DingTalk history badges, and panel RLS create fixes.**

### Added

- **MindMate SSE upstream keepalive** — `iter_upstream_with_keepalive` emits SSE comment keepalives every 25s during long Dify vision/workflow silence so reverse proxies do not close `/api/ai_assistant/stream` before the first token ([`sse_upstream_keepalive.py`](services/infrastructure/http/sse_upstream_keepalive.py), [`sse_streaming.py`](routers/api/sse_streaming.py)).
- **Unified Dify conversation routing** — Conversation list rows carry `server` and `mindbot_config_id`; delete/rename/messages/feedback resolve the correct Dify endpoint across web MindMate and bound MindBot identities; usage telemetry supplements MindBot threads missing from Dify list APIs ([`unified_conversations.py`](services/dify/unified_conversations.py), [`difyConversationRoute.ts`](frontend/src/utils/difyConversationRoute.ts)).
- **DingTalk MindBot history badge** — Sidebar and MindMate history show a DingTalk badge on MindBot-sourced threads ([`MindMateDingtalkBadge.vue`](frontend/src/components/sidebar/MindMateDingtalkBadge.vue), [`ChatHistoryConversationTitle.vue`](frontend/src/components/sidebar/ChatHistoryConversationTitle.vue)).
- **Panel RLS create policies** — Alembic `0072`/`0073`: experts can INSERT organizations they invite; school managers can INSERT users with `organization_id` set before `id` is assigned ([`rev_0072_rls_expert_org_create.py`](alembic/versions/rev_0072_rls_expert_org_create.py), [`rev_0073_rls_panel_user_create.py`](alembic/versions/rev_0073_rls_panel_user_create.py)).

### Changed

- **DingTalk bind/unbind** — Invalidate Dify conversation queries after pair-code bind or unbind so MindBot threads appear immediately ([`AccountInfoModal.vue`](frontend/src/components/auth/AccountInfoModal.vue), [`DingTalkPairModal.vue`](frontend/src/components/auth/DingTalkPairModal.vue)).
- **Production deploy docs** — Nginx/NPM `proxy_read_timeout` / `proxy_send_timeout` 300s and `proxy_buffering off` for MindMate SSE ([`production_security_deploy.md`](docs/architecture/production_security_deploy.md), [`VUE_SETUP.md`](docs/VUE_SETUP.md)).

### Fixed

- **SSE keepalive typing** — basedpyright-clean typed sentinel queue in `iter_upstream_with_keepalive`.
- **MindMate TypeScript / i18n CI** — Fix `mindmateDifyUserIdFromSession` call arity in optimistic conversation cache update; propagate `sidebar.chatHistory.dingtalkBadge*` keys across all locale bundles.
- **Panel admin create flows** — RLS `rls_panel_org_invited_by_actor` and expanded `users`/`organizations` tenant policies unblock expert org invite and school user creation in panel mode.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): syncs with root **`VERSION`** (5.131.0) on next `npm run build` (`prebuild` → `sync-version`).

## [5.130.0] - 2026-06-28

> **Document Summary portal, chat handoff pairing, and Windows file-reader helper.**

### Added

- **Document Summary (文档总结) Knowledge portal** — Canvas panel auto-provisions a session package (`POST /api/knowledge-space/doc-summary/session/start`), ingests documents/images/web URLs/chat transcripts into the package corpus, and generates RAG-backed mind maps via `POST /api/canvas/generate_mindmap_from_package`. Deep link: `?openDocSummary=1` (alias `?openFileCenter=1`).
- **Chat handoff + Windows file-reader** — Pairing codes on the **聊天记录** tab; `POST /api/knowledge-space/chat-handoff/*` ingest with `mgat_` auth; `clients/file-reader/` tkinter helper and `/api/downloads/mindgraph-file-reader` build script.

### Changed

- **User-facing naming** — **Document Summary** / **文档总结** replaces "File Center" in toolbar, panel, Chrome extension save labels, and Knowledge Space library subtitle.

### Fixed

- **Document Summary production hardening** — RAG scope aligns with session package fallback; invalid session `package_id` rejected; chat pairing codes are single-use with rate limits; ingest validates package before URL fetch; file-reader download served via tier-gated `/api/downloads/mindgraph-file-reader`; frontend session/package race and pending-package link-on-first-save fixes.
- **File-reader client type-checking** — basedpyright clean for `AppError` keyword construction, Windows `ctypes.windll` guards, typed status dock row frame, and `clients/file-reader` on pytest/basedpyright `extraPaths`.

## [5.129.0] - 2026-06-27

> **OAuth QR login, thinking coins production hardening, and canvas AI UX fixes.**

### Added

- **OAuth QR login (WeChat + DingTalk)** — `FEATURE_OAUTH_LOGIN=False` by default; per-school DingTalk keys in **组织管理 → 其他设置**; login modal **二维码登录**; account **账户绑定** ([`docs/architecture/oauth_qr_login.md`](docs/architecture/oauth_qr_login.md)).
- **Thinking coins — production hardening** — Central `event_hub` for earn/spend mutations, single-debit multi-LLM billing, canvas translate and Omni settlement fixes, API/SSE `thinking_coins` footers, and frontend `useThinkingCoinSync` ([`docs/architecture/thinking_coins.md`](docs/architecture/thinking_coins.md)).

### Fixed

- **OAuth QR login — bind redirect feedback** — Bind failures redirect to `/?error=…` (not `/auth`) so signed-in users see toasts; WeChat/DingTalk bind success uses `/?oauth_bind=` with global handling in `App.vue` ([`useOAuthRouteFeedback.ts`](frontend/src/composables/auth/useOAuthRouteFeedback.ts)).
- **Account bindings UI — TypeScript** — `shouldShowAccountBindingsSection` accepts string `schoolId` to match auth store types ([`oauthLoginUi.ts`](frontend/src/utils/oauthLoginUi.ts)).
- **Canvas auto-complete — thinking coins** — When all three parallel models fail with insufficient balance, only the wallet modal is shown (no duplicate error toast); `LLMResult` retains `errorType` for aggregate failure handling ([`llmResults.ts`](frontend/src/stores/llmResults.ts), [`useAutoComplete.ts`](frontend/src/composables/editor/useAutoComplete.ts)).
- **Tab inline recommendations** — Warn when the topic is not ready or the API returns zero labels (`startRecommendations` centralizes UX) ([`useInlineRecommendations.ts`](frontend/src/composables/editor/useInlineRecommendations.ts)).
- **Mind map RAG branch expand** — Auto-expand marks a branch as attempted only after a successful subgraph preview, so transient failures can be retried ([`useMindMapRagBranchExpand.ts`](frontend/src/composables/editor/useMindMapRagBranchExpand.ts)).
- **Mind map subgraph / RAG expand** — Suppress duplicate error toast when thinking coins are insufficient (wallet modal only), matching full auto-complete ([`useMindMapSubgraphSuggest.ts`](frontend/src/composables/editor/useMindMapSubgraphSuggest.ts)).
- **Tab inline rec entry points** — Removed redundant `!isReady` early returns so `startRecommendations` always shows the centralized topic warning ([`useCanvasPageMountedHandlers.ts`](frontend/src/composables/canvasPage/useCanvasPageMountedHandlers.ts), mobile/kitty callers).

### Changed

- **Canvas auto-complete validation** — Pure `validateAutoCompleteRules` extracted for unit tests ([`autoCompleteValidation.ts`](frontend/src/composables/editor/autoCompleteValidation.ts)).
- **i18n** — Added `notification.conceptMapTabNeedsAi`, `notification.nodeNotEligible`, `notification.inlineRecEmpty`, and inline-rec picker aria keys; removed unused `autoComplete.collabOwnerOnly`.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): syncs with root **`VERSION`** (5.129.0) on next `npm run build` (`prebuild` → `sync-version`).

## [5.128.0] - 2026-06-27

> **Mind map appearance presets, layout connectors, presentation tools, learning sheet UX, and post-add inline edit.**

### Added

- **Mind map appearance** — Five diagram styles (`classic`, `formal`, `bubble`, `underline`, `soft`) plus curated vibrant classroom color themes and rainbow preset; toolbar dropdown persists `_mindmap_theme` and `_mindmap_diagram_style` ([`mindMapDiagramStyles.ts`](frontend/src/config/mindMapDiagramStyles.ts), [`MindMapAppearanceDropdown.vue`](frontend/src/components/canvas/MindMapAppearanceDropdown.vue)).
- **Mind map post-add inline edit** — Tab, Enter, toolbar +, and directional **+** overlays open inline edit on the newly added node ([`mindMapOps.ts`](frontend/src/stores/diagram/mindMapOps.ts), [`InlineEditableText.vue`](frontend/src/components/diagram/nodes/InlineEditableText.vue)).
- **Presentation tools (mind map v2)** — Pointer, hand, laser, highlighter, pen, spotlight, timer HUD, and slides in the simplified presentation rail ([`MindMapPresentationSideToolbar.vue`](frontend/src/components/canvas/MindMapPresentationSideToolbar.vue)).
- **Learning sheet float bar** — Custom pick and random blank sessions with presentation suspend/resume ([`LearningSheetFloatBar.vue`](frontend/src/components/canvas/LearningSheetFloatBar.vue), [`useLearningSheetCustomMode.ts`](frontend/src/composables/mindMap/useLearningSheetCustomMode.ts)).

### Changed

- **New mind map defaults** — Blank templates initialize with vibrant blue theme and classic diagram style ([`defaultTemplates.ts`](frontend/src/stores/specLoader/defaultTemplates.ts)).
- **Mind map editing shortcuts** — Tab saves and adds a child; Enter saves and adds a sibling (topic excluded).
- **Windows event loop default** — Native Windows dev uses `WindowsSelectorEventLoopPolicy` for psycopg async; set `WINDOWS_PROACTOR_EVENT_LOOP=1` if Playwright PNG export fails ([`startup.py`](services/infrastructure/lifecycle/startup.py)).

### Fixed

- **Mind map style preservation** — Child add no longer inherits parent `nodeShape` onto unrelated siblings ([`mindMapStylePreservation.ts`](frontend/src/stores/diagram/mindMapStylePreservation.ts)).
- **Mind map underline connectors** — Single underline leaf uses flat horizontal at shared anchor Y ([`mindMapLayout.ts`](frontend/src/stores/diagram/mindMapLayout.ts), [`MindMapOrthogonalEdge.vue`](frontend/src/components/diagram/edges/MindMapOrthogonalEdge.vue)).
- **Mind map single-side L1 branch** — Sole branch on a side aligns to topic anchor with straight connectors ([`mindMapLayoutLegacy.ts`](frontend/src/stores/diagram/mindMapLayoutLegacy.ts)).
- **Post-add inline edit lifecycle** — Cancel pending edit retries on diagram reset; clear `mindMapPendingEditNodeId` ([`mindMapOps.ts`](frontend/src/stores/diagram/mindMapOps.ts)).
- **Learning sheet UI reset** — Module-level pick/float-bar state clears on canvas exit and session reset ([`useLearningSheetCustomMode.ts`](frontend/src/composables/mindMap/useLearningSheetCustomMode.ts)).
- **Mind map toolbar reset** — Wire `useCanvasReset` for in-toolbar reset button ([`CanvasToolbarMindMap.vue`](frontend/src/components/canvas/CanvasToolbarMindMap.vue)).
- **CI / production hardening** — Ruff format on MindBot display modules; TypeScript fixes for mobile import loader, diagram title save, and inline-edit pane-click handler; i18n canvas key sync across 77 locales; frontend package version 5.128.0.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): syncs with root **`VERSION`** (5.128.0) on next `npm run build` (`prebuild` → `sync-version`).

## [5.127.0] - 2026-06-27

> **DingTalk MindBot ↔ MindMate identity bridge — unified conversation history, generation-session registry, diagram display adapter, and Dify HTTP error mapping.**

### Added

- **Generation session registry** — Redis links `conversation_id` / Dify `user` strings to MindGraph callers when MindMate or MindBot opens a chat; `/api/generate_dingtalk` resolves library-save identity without browser cookies ([`generation_session_registry.py`](services/diagram/generation_session_registry.py), [`dify_user_resolve.py`](services/diagram/dify_user_resolve.py)).
- **MindBot linked-user resolution** — Staff bind lookup for generation-session registration when Dify omits the MindGraph user id ([`generation_session_bind.py`](services/mindbot/diagram/generation_session_bind.py)).
- **DingTalk diagram display adapter** — MindBot post-processes canonical Dify markdown at send time only (`![mg:uuid](url)` → `![](url)`, hide HTML comments); one inline markdown bubble, AI card skipped for diagram replies ([`assistant_markdown.py`](services/diagram/assistant_markdown.py), [`dingtalk_diagram_display.py`](services/mindbot/diagram/dingtalk_diagram_display.py), [`dify_paths.py`](services/mindbot/pipeline/dify_paths.py)).
- **`mg_conversation_id` on generate_dingtalk** — Optional body field (same as `conversation_id`) for Dify HTTP tool inputs ([`requests_diagram.py`](models/requests/requests_diagram.py)).
- **Dify conversation HTTP error mapping** — `DifyConversationNotFoundError` and related API errors map to proper HTTP status on conversation routes ([`dify_http_errors.py`](clients/dify_http_errors.py), [`dify_conversations.py`](routers/api/dify_conversations.py)).
- **Tests** — Unified conversation merge, identity resolution, generation-session registry, assistant markdown parse, DingTalk diagram display, and Dify conversation HTTP 404 ([`test_unified_conversations.py`](tests/test_unified_conversations.py), [`test_generation_session_registry.py`](tests/test_generation_session_registry.py), [`test_generate_dingtalk_identity.py`](tests/test_generate_dingtalk_identity.py), [`test_assistant_markdown.py`](tests/test_assistant_markdown.py), [`test_mindbot_dingtalk_diagram_display.py`](tests/test_mindbot_dingtalk_diagram_display.py), [`test_dify_conversations_http.py`](tests/test_dify_conversations_http.py)).
- **Canvas history baseline** — Undo stack seeds index 0 on fresh diagram load/reset so the first edit is undoable; undo/redo reconciles layout caches and selection ([`history.ts`](frontend/src/stores/diagram/history.ts), [`historyRestore.ts`](frontend/src/stores/diagram/historyRestore.ts), [`applyCanvasHistoryNavigationSync.ts`](frontend/src/composables/canvasPage/applyCanvasHistoryNavigationSync.ts)).
- **Diagram save guards** — Shared eligibility for autosave, flush, and per-LLM-round persistence (collab guest, subgraph preview, generating) ([`diagramSaveFeedback.ts`](frontend/src/composables/editor/diagramSaveFeedback.ts), [`useDiagramAutoSave.ts`](frontend/src/composables/editor/useDiagramAutoSave.ts)).
- **Canvas session reset** — Central reset aborts AI streams, clears ephemeral Pinia, and emits `diagram:reset_requested` for page-local cleanup ([`applyCanvasSessionReset.ts`](frontend/src/composables/canvasPage/applyCanvasSessionReset.ts), [`registerCanvasPageResetHandler.ts`](frontend/src/composables/canvasPage/registerCanvasPageResetHandler.ts)).
- **Tests** — Canvas history baseline, session reset, and diagram save flow ([`canvasHistoryBaseline.spec.ts`](frontend/tests/canvasHistoryBaseline.spec.ts), [`applyCanvasSessionReset.spec.ts`](frontend/tests/applyCanvasSessionReset.spec.ts), [`diagramSaveFlow.spec.ts`](frontend/tests/diagramSaveFlow.spec.ts)).

### Changed

- **Unified MindMate conversation list** — Web MindMate and bound DingTalk MindBot threads merge into one history; Dify user resolution probes MindBot keys before defaulting to web ([`unified_conversations.py`](services/dify/unified_conversations.py)).
- **MindBot Dify stream** — Registers generation sessions on stream start and passes `conversation_id` through the pipeline ([`dify_stream.py`](services/mindbot/core/dify_stream.py), [`callback.py`](services/mindbot/pipeline/callback.py), [`context.py`](services/mindbot/pipeline/context.py)).
- **MindBot reply delivery** — `send_dingtalk_formatted_reply()` applies display-only diagram formatting at outbound; Dify answer and usage logs keep canonical `mg` markers ([`text.py`](services/mindbot/outbound/text.py), [`dify_paths.py`](services/mindbot/pipeline/dify_paths.py)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): syncs with root **`VERSION`** (5.127.0) on next `npm run build` (`prebuild` → `sync-version`).

## [5.126.0] - 2026-06-27

> **MindMate ↔ canvas navigation, diagram preview cache, presentation spotlight/timer, and mind map fit/toolbar polish.**

### Added

- **MindMate diagram preview cache** — IndexedDB persists DingTalk-generated preview PNGs (30-day TTL) so chat bubbles and share/export keep thumbnails after server `temp_images` cleanup ([`mindmateDiagramPreviewCache.ts`](frontend/src/utils/mindmateDiagramPreviewCache.ts), [`useMindmateDiagramPreviewImage.ts`](frontend/src/composables/mindmate/useMindmateDiagramPreviewImage.ts), [`ShareExportModal.vue`](frontend/src/components/panels/ShareExportModal.vue)).
- **Presentation spotlight and timer** — Mind map presentation rail restores spotlight overlay and countdown timer tools ([`MindMapPresentationSideToolbar.vue`](frontend/src/components/canvas/MindMapPresentationSideToolbar.vue), [`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue)).
- **Mind map side-toolbar fit reserve** — Fit-view padding accounts for the v2 floating side toolbar width/expand state so nodes are not hidden under the handle ([`mindMapSideToolbarFitReserve.ts`](frontend/src/utils/mindMapSideToolbarFitReserve.ts), [`uiConfig.ts`](frontend/src/config/uiConfig.ts)).
- **Sidebar personal edition label** — Compact brand header for users without a paid org tier; paid schools keep org edition subtitle ([`useAppSidebar.ts`](frontend/src/composables/sidebar/useAppSidebar.ts), [`AppSidebar.vue`](frontend/src/components/sidebar/AppSidebar.vue)).
- **Tests** — Active-thread restore guards, canvas back to MindMate, side-toolbar fit reserve, and diagram preview cache ([`mindMateActiveThread.spec.ts`](frontend/tests/mindMateActiveThread.spec.ts), [`canvasBackNavigation.spec.ts`](frontend/tests/canvasBackNavigation.spec.ts), [`mindMapSideToolbarFitReserve.spec.ts`](frontend/tests/mindMapSideToolbarFitReserve.spec.ts), [`mindmateDiagramPreviewCache.spec.ts`](frontend/tests/mindmateDiagramPreviewCache.spec.ts)).

### Changed

- **MindMate thread persistence** — Active chat thread survives canvas navigation; Dify history revalidation rejects empty/partial server copies that lag behind Pinia; `onActivated` restores thread when returning from canvas ([`useMindMate.ts`](frontend/src/composables/mindmate/useMindMate.ts), [`mindmateActiveThread.ts`](frontend/src/stores/mindmateActiveThread.ts)).
- **Canvas back navigation** — Back from editor returns to `/mindmate` when that was the entry route, not only `/mindgraph` ([`canvasBackNavigation.ts`](frontend/src/utils/canvasBackNavigation.ts)).
- **Mind map v2 fit behavior** — One-shot fit on enter; no auto-refit while editing (manual zoom only) ([`DiagramCanvas.vue`](frontend/src/components/diagram/DiagramCanvas.vue), [`useDiagramCanvasFit.ts`](frontend/src/composables/diagramCanvas/useDiagramCanvasFit.ts)).
- **Mind map reset control** — Reset-to-template moved from editing toolbar to canvas top bar for mind maps ([`CanvasToolbarMindMap.vue`](frontend/src/components/canvas/CanvasToolbarMindMap.vue), [`CanvasTopBar.vue`](frontend/src/components/canvas/CanvasTopBar.vue)).
- **Toolbar button styles** — Shared [`mindMapToolbarButtons.css`](frontend/src/components/canvas/mindMapToolbarButtons.css) for top bar and mind map toolbar.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): syncs with root **`VERSION`** (5.126.0) on next `npm run build` (`prebuild` → `sync-version`).

## [5.125.0] - 2026-06-27

> **Security audit hardening — CSP script nonce, upload path-traversal containment, OTP brute-force rate limits, signed chat fan-out, SSRF/CSWSH/host-header defenses, and production startup guards.**

### Security

- **CSP script nonce** — The Vue SPA shell is served with a per-request nonce stamped onto its inline scripts and in-document CSP meta tag, and `add_security_headers` emits a matching `script-src 'self' 'nonce-…'` header (no `'unsafe-inline'` for scripts) for the same response. Shell responses are `no-store` so the nonce never goes stale. `style-src` keeps `'unsafe-inline'` (Vue/Element Plus inject styles at runtime via JS). Legacy template responses without a nonce keep the permissive fallback ([`vue_spa.py`](routers/core/vue_spa.py), [`spa_handler.py`](services/infrastructure/utils/spa_handler.py), [`middleware.py`](services/infrastructure/http/middleware.py)). **Takes effect after `npm run build`.**
- **Upload path traversal (CWE-22)** — New [`safe_upload.py`](services/utils/safe_upload.py) centralizes `safe_upload_basename` (strips directory components) and `ensure_within_directory` (resolves + asserts containment before write). Applied to Knowledge Space upload, chunk-test upload, and batch upload, plus announcement image upload ([`knowledge_space_service.py`](services/knowledge/knowledge_space_service.py), [`chunk_test_document_service.py`](services/knowledge/chunk_test_document_service.py), [`document_batch_service.py`](services/knowledge/document_batch_service.py), [`update_notification.py`](routers/core/update_notification.py)).
- **OTP brute-force** — SMS and email OTP login now enforce per-identifier and per-IP rate limits before verify-and-consume; counters clear on success ([`routers/auth/login.py`](routers/auth/login.py)).
- **Signed chat WS fan-out** — Chat envelopes are stamped with `COLLAB_FANOUT_ORIGIN_SECRET` on publish (Redis + PG-NOTIFY paths) and rejected on receipt when the origin is missing/invalid, mirroring workshop fan-out. Prevents a Redis/PG-write-capable attacker from forging channel/DM/presence frames ([`ws_redis_fanout_publish_core.py`](services/features/ws_redis_fanout_publish_core.py), [`ws_redis_fanout_publish.py`](services/features/ws_redis_fanout_publish.py), [`ws_redis_fanout_listener.py`](services/features/ws_redis_fanout_listener.py)).
- **SSRF hardening** — URL fetch now blocks all non-public resolved IPs (private, loopback, link-local, multicast, unspecified, IPv4-mapped), re-validates the host immediately before the request to shrink the DNS-rebind window, and rejects 3xx redirects ([`web_content_generation.py`](routers/api/web_content_generation.py)).
- **Cross-site WebSocket hijacking (CSWSH)** — Origin validation added to the ASR, live-translate, and workshop-chat WebSocket endpoints via shared [`close_ws_if_origin_disallowed`](utils/collab_ws_origin.py) ([`asr_realtime_ws.py`](routers/api/asr_realtime_ws.py), [`live_translate_ws.py`](routers/api/live_translate_ws.py), [`workshop_chat_ws.py`](routers/features/workshop_chat_ws.py)).
- **Host-header injection** — `TrustedHostMiddleware` rejects requests whose `Host` is not in `ALLOWED_HOSTS` (permissive `*` by default; `localhost`/`127.0.0.1` always allowed) ([`middleware.py`](services/infrastructure/http/middleware.py)).
- **Upload content-type spoofing** — Dify file upload enforces an extension allowlist + magic-byte validation for images; announcement image extension is derived from the validated content-type only ([`dify_files.py`](routers/api/dify_files.py), [`update_notification.py`](routers/core/update_notification.py)).
- **Account enumeration** — Password reset (SMS/email) returns a generic `400` for unknown accounts instead of `404` ([`routers/auth/password.py`](routers/auth/password.py)).
- **Production startup guards** — Non-debug boot is blocked when `DATABASE_URL` is unset; unauthenticated `REDIS_URL` warns (or fails when `REQUIRE_REDIS_AUTH=true`) ([`production_secrets_guard.py`](services/infrastructure/security/production_secrets_guard.py)).
- **Constant-time secrets** — Bayi/dashboard passkey checks use `hmac.compare_digest`; captcha codes use `secrets.choice` ([`passkey_utils.py`](utils/auth/passkey_utils.py), [`routers/auth/captcha.py`](routers/auth/captcha.py)).
- **Password policy** — Registration/reset/change validators reject common passwords and single-character repeats beyond length-only checks ([`requests_auth.py`](models/requests/requests_auth.py)).
- **Session cleanup** — `csrf_token` cookie is cleared on logout ([`routers/auth/session.py`](routers/auth/session.py)).
- **Deprecated header** — Removed `X-XSS-Protection` (obsolete; CSP is the correct control) ([`middleware.py`](services/infrastructure/http/middleware.py)).

### Changed

- **Bayi SSO cookies** — The SSO flow issues a standard rotating refresh token and sets access/refresh/CSRF cookies via `set_auth_cookies`, aligning lifetimes with the core auth flow ([`routers/core/pages.py`](routers/core/pages.py)).

### Added

- **Security audit report** — [`docs/security/SECURITY_AUDIT_2026-06.md`](docs/security/SECURITY_AUDIT_2026-06.md): findings mapped to OWASP/ASVS, remediation, positive controls, and a deployment hardening checklist.
- **Security regression tests** — CSP nonce vs. `'unsafe-inline'` fallback, DB/Redis startup guards, and existing hardening checks ([`tests/test_security_production_hardening.py`](tests/test_security_production_hardening.py)).

### Deployment notes (operator action)

- **`DATABASE_URL` now required** — Non-debug deployments must set `DATABASE_URL` explicitly, or startup fails by design.
- **`COLLAB_FANOUT_ORIGIN_SECRET`** — Set explicitly and **share the same value across all workers**; chat fan-out now enforces it (previously workshop-only).
- **`ALLOWED_HOSTS`** (new, optional) — Set to the production hostname(s) to enforce host-header validation.
- **`REQUIRE_REDIS_AUTH`** (new, optional) — Set `true` to fail startup on an unauthenticated `REDIS_URL`.
- Rotate any API key that previously appeared in committed docs ([`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) placeholder).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): syncs with root **`VERSION`** (5.125.0) on next `npm run build` (`prebuild` → `sync-version`).

## [5.124.0] - 2026-06-26

> **DingTalk pair-code binding — rotating 6-digit codes replace QR; MindBot tool ingress; production security hardening (CSRF, fail-closed auth).**

### Added

- **DingTalk pair-code binding** — Rotating 6-digit HMAC codes displayed as `000-000` on web; teachers send the code to MindBot; universal bind/unbind claim pipeline with org+code Redis index, claim lock, and guess-rate limits ([`dingtalk_account_binding.md`](docs/architecture/dingtalk_account_binding.md)).
- **DingTalkPairModal** — Bluetooth-style pairing UI (bind and unbind) with countdown ring, status polling, and client audit logging ([`DingTalkPairModal.vue`](frontend/src/components/auth/DingTalkPairModal.vue), [`dingtalkPairAuditLog.ts`](frontend/src/utils/dingtalkPairAuditLog.ts)).
- **MindBot tool ingress** — Pre-Dify handler framework for admin tools that must skip the LLM; pair-code handler registered in [`services/mindbot/tools/`](services/mindbot/tools/) ([`mindbot_tool_ingress.md`](docs/architecture/mindbot_tool_ingress.md)).
- **Bind/unbind audit logging** — Distinct `[MindBotTool]`, `[DingtalkBind:web]`, `[DingtalkBind:claim]`, and `[DingtalkPair:client]` prefixes; client events POST to `/api/frontend_log` with `source=dingtalk_pair`.
- **Production security deploy guide** — Pre-deploy env, openresty `X-Forwarded-Proto`, paired backend/frontend rollout, ESP32 header requirement, and post-deploy curl checks ([`production_security_deploy.md`](docs/architecture/production_security_deploy.md)).
- **JWT rotation CLI** — [`scripts/ops/rotate_jwt_secret.py`](scripts/ops/rotate_jwt_secret.py) moves the active Redis JWT secret to `jwt:secret:previous` and issues a new signing key.
- **CSRF hardening** — Migration-safe double-submit CSRF middleware, `csrf_token` cookie at login/refresh, global fetch interceptor ([`installCsrfFetchInterceptor.ts`](frontend/src/utils/installCsrfFetchInterceptor.ts)), and [`tests/test_csrf_protection.py`](tests/test_csrf_protection.py).
- **Security regression tests** — Fail-closed session, HSTS, API key masking, SSRF redirect block ([`tests/test_security_production_hardening.py`](tests/test_security_production_hardening.py)).
- **Gewe webhook auth** — HMAC signature verification and optional IP allowlist when `FEATURE_GEWE=True` ([`gewe_webhook_auth.py`](services/infrastructure/security/gewe_webhook_auth.py)).
- **Session refresh mutex** — Shared [`sessionRefresh.ts`](frontend/src/utils/sessionRefresh.ts) prevents duplicate `/auth/refresh` races between Pinia and `apiClient`.
- **Saved login identifier** — Remember-me prefills username only; password never stored ([`savedLoginCredentials.ts`](frontend/src/utils/savedLoginCredentials.ts)).
- **PWA install early capture** — [`pwa-install-early.js`](frontend/public/pwa-install-early.js) retains `beforeinstallprompt` before the SPA bundle loads.
- **PDF worker version check** — CI script verifies committed worker version matches `pdfjs-dist` ([`check-pdf-worker-version.ts`](frontend/scripts/check-pdf-worker-version.ts)).
- **Tests** — Pair-code parse/handler, bind org resolve, unbind pair, code index, audit log, CSRF, Gewe webhook, refresh-token reuse, workshop chat file service, and frontend interceptor specs.

### Security

- **Fail-closed auth** — Session validation and `/session-status` deny on Redis errors; weak/placeholder secrets blocked at startup via [`production_secrets_guard.py`](services/infrastructure/security/production_secrets_guard.py).
- **CSRF** — Cookie + `X-CSRF-Token` on authenticated mutations; one-request bootstrap for legacy sessions (logged as `[Security] CSRF_BOOTSTRAP`).
- **Headers** — Production CSP drops `unsafe-eval`; HSTS when HTTPS is detected (`FORCE_SECURE_COOKIES` / `X-Forwarded-Proto` behind reverse proxy).
- **Trusted proxy client IP** — Forwarded `X-Forwarded-For` / `X-Real-IP` are honored only from peers matching `TRUSTED_PROXY_IPS`, which now accepts exact IPs, CIDR ranges, and the `private` / `loopback` keywords so Docker / Nginx Proxy Manager deployments trust the proxy without pinning a container IP; resolution is logged once at startup ([`request_helpers.py`](utils/auth/request_helpers.py)). Accurate IPs are required for rate limits and AbuseIPDB / CrowdSec blocking.
- **IDOR / exposure** — Device status requires registration secret; admin API keys masked in list; workshop chat static uploads blocked; SSRF fetch disables redirects.
- **Frontend** — DOMPurify link hook on live markdown path; sensitive caches moved to `sessionStorage`; remember-me stores identifier only.

### Changed

- **DingTalk bind ingress** — QR picture decode removed; teachers confirm bind/unbind by sending the rotating code to MindBot (text tool ingress, no Dify round-trip).
- **Direct unbind disabled** — `POST /dingtalk-bind/unbind` returns **410 Gone**; unbind requires MindBot pair-code confirmation via `POST /dingtalk-bind/unbind/start`.
- **BindDingTalkAccountModal** — Simplified to launch [`DingTalkPairModal`](frontend/src/components/auth/DingTalkPairModal.vue); QR upload/decode UI removed.
- **i18n** — DingTalk pair strings synced across all locale bundles ([`sync-dingtalk-pair-locale-keys.py`](frontend/scripts/sync-dingtalk-pair-locale-keys.py)).

### Removed

- **QR bind backend** — [`picture_handler.py`](services/mindbot/bind/picture_handler.py), [`qr_backend.py`](services/mindbot/bind/qr_backend.py), and [`qr_decode.py`](services/mindbot/bind/qr_decode.py) deleted; pair-code text replaces QR image ingress.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.124.0).

## [5.123.0] - 2026-06-26

> **MindMate export — Dify raw dump library: upload snapshots, merge into a cumulative store, search and export from the library.**

### Added

- **Dify raw dump host script** — [`dump_raw.sh`](scripts/dify/dump_raw.sh) on each Dify/NeoDify server (PostgreSQL COPY, manifest, zip); optional [`import_dump_zip.sh`](scripts/dify/import_dump_zip.sh) CLI on MindGraph.
- **Cumulative dump library** — Each import merges CSVs into `library/{dify|neodify}/`; conversations/messages upsert by id; snapshot archives kept under `{label}/{timestamp}/`; deleting an archive rebuilds the library from remaining snapshots ([`raw_dump_library.py`](services/dify/export/raw_dump_library.py)).
- **Admin Dump files tab** — Upload zips, import pending, library stats (merged count, messages, last merged), snapshot archive tables; Swiss segmented control in the admin header toggles **Search & filters** vs **Dump files**.
- **Backend dump modules** — Import with zip-slip/sha256 guards, `MultiServerDumpStore`, dump-only export router (no live Dify API fallback), admin API under `/api/admin/mindmate-export/dumps/*`.
- **Tests** — Library merge, dump index, import, collect backend, admin helpers ([`test_dify_raw_library.py`](tests/test_dify_raw_library.py) and related).

### Changed

- **Per-user daily token cap** — Default `USER_DAILY_TOKEN_CAP` raised from **1,000,000** to **5,000,000** tokens per Beijing calendar day.
- **MindMate export data source** — Search, sync download, and background jobs read the merged **library** per server label (falls back to latest snapshot only when no library exists).
- **Library staleness** — Merged libraries are never marked stale; age limits apply to raw snapshot archives only.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.123.0).

## [5.122.0] - 2026-06-26

> **Classic mind map canvas — restore pre-v2 layout and connectors; even topic handles; Enter adds branches with default children.**

### Added

- **Classic / v2 mind map separation** — Legacy layout, geometry, and Material branch palette extracted into dedicated modules (`mindMapLegacyLayout`, `mindMapV2Layout`, `mindMapMeasurements`, `mindMapLegacyGeometry`, `mindMapLegacyColors`); spec loader branches on canvas mode ([`mindmap_v2_separation.md`](docs/architecture/mindmap_v2_separation.md)).
- **Classic topic handles** — Per-side evenly spaced exit points with sequential handle ids and runtime `sourceHandle` normalization ([`classicMindMapTopicHandles.ts`](frontend/src/utils/classicMindMapTopicHandles.ts)).
- **Pill boundary handles** — Topic handle positions inset onto the semicircle so curved connectors meet the node border at high zoom.
- **Mind map separation tests** — Regression coverage for legacy palette, layout, clockwise add-branch, handle spread, and v2 gating ([`mindMapSeparation.spec.ts`](frontend/tests/mindMapSeparation.spec.ts)).

### Changed

- **Add branch (legacy)** — Toolbar and clockwise redistribution seed two default child nodes; **Enter** (sibling on a top-level branch) now matches that behavior in legacy mode.
- **Admin dashboard trends** — Org/user token trend charts use shared [`AdminTrendChartModal.vue`](frontend/src/components/admin/AdminTrendChartModal.vue) instead of separate dialog wiring.

### Fixed

- **Classic topic→branch lines** — Handles no longer fall back to bottom/center when sides are uneven; stale `sourceHandle` ids remapped at render time.
- **Curved edge gaps** — Mind map curved edges use round line caps; pill-aware handle inset removes sub-pixel gaps when zoomed in.
- **Legacy canvas bleed** — TopicNode, BranchNode, node management, and canvas-mode switch no longer apply v2-only shapes, themes, or estimators on the classic canvas.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.122.0).

## [5.121.0] - 2026-06-25

> **MindMate active thread — instant chat restore after canvas navigation, with silent background sync from Dify.**

### Added

- **MindMate active thread (Pinia)** — Current conversation messages persist in `useMindMateStore` across route unmounts (MindMate → canvas → back); [`mindmateActiveThread.ts`](frontend/src/stores/mindmateActiveThread.ts) sanitizes stored messages and maps Dify history rows with `difyMessageId` / feedback metadata.
- **Stale-while-revalidate** — Warm-thread restore shows the chat immediately; a silent background fetch reconciles with Dify when the server copy differs (e.g. MindBot updates elsewhere).

### Changed

- **`useMindMate` lifecycle** — Composable restores from Pinia on init, syncs mutations via a deep watch, and `destroy()` no longer clears the store thread on unmount ([`useMindMate.ts`](frontend/src/composables/mindmate/useMindMate.ts)).
- **`loadConversation`** — Uses in-memory thread when available (no loading overlay); blocking Dify fetch only for cold start or sidebar conversation switches.

### Fixed

- **MindMate remount delay** — Returning from the canvas editor no longer blanks the chat and waits for a full Dify history reload on every navigation.
- **Mobile MindMate** — Same instant restore path as desktop (handled in composable init, not panel-only `onMounted` logic).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.121.0).

## [5.120.0] - 2026-06-25

> **Mind map v2 canvas (dev flag), File Center, generate pipeline hardening, classic/v2 separation, Dify multi-slot health failover, and admin school activity tabs.**

### Added

- **Mind map v2 canvas (dev flag)** — Side-toolbar chrome, File Center, subgraph preview bar, and orthogonal edges when `FEATURE_MINDMAP_V2_CANVAS=True` and the user opts in via Language settings; classic canvas remains the default.
- **Mind map v2 visual design** — Theme presets (`mindMapThemes`), node shapes (rectangle / oval / underline), unified connection stroke in v2; dual `_mindmap_canvas.legacy` / `.v2` style buckets with mode-switch reconciliation ([`mindmap_v2_separation.md`](docs/architecture/mindmap_v2_separation.md)).
- **File Center API** — Knowledge packages CRUD, source ingest (file, text, web), and wiki endpoints under `/api/knowledge-space/packages`; Alembic migration `rev_0070` adds package fields.
- **Landing generate_graph SSE** — Stream now emits `detecting`, `requirements`, and `progress` (with resolved topic and diagram type) in addition to `accepted`, `waiting`, and `streaming`.
- **Generate pipeline** — Typed event contract (`GenerateGraphEvent`) and `run_generate_pipeline` entry point with cooperative cancellation when the client disconnects.
- **Canvas autocomplete** — Cancel control on the 3-LLM model selector while generation is in flight.
- **Admin org activity tab** — School modal activity timeline with cursor pagination and source filter (MindGraph / MindMate / DingTalk); `GET /admin/organizations/{org_id}/activity` ([`AdminOrgActivityTab.vue`](frontend/src/components/admin/AdminOrgActivityTab.vue)).
- **Admin school teachers tab** — School modal members list sorted by all-time token usage with role pills ([`AdminSchoolTeachersTab.vue`](frontend/src/components/admin/AdminSchoolTeachersTab.vue)).
- **Dify multi-slot health poller** — Schema-driven server slots, deduped probe plan, Redis health cache with failure threshold, and configurable poll interval / max age / concurrency; MindMate routing uses stale-aware failover partner selection ([`dify_health_poller.py`](services/dify/dify_health_poller.py)).

### Changed

- **Mind map v2 canvas (dev flag)** — Classic canvas remains the default; v2 chrome is gated behind `FEATURE_MINDMAP_V2_CANVAS` (off by default). The classic/new toggle in Language settings is hidden unless the flag is enabled.
- **Classic mind map default** — `mindMapCanvasMode` defaults to `legacy`; v2 layout and orthogonal edges apply only when explicitly opted in.
- **Collab AI policy** — `generate_graph` and inline recommendations return 403 for all users (except superadmin) when the diagram is in a live workshop session.
- **Dify server helpers** — Generalized from hard-coded slots 1+2 to ORM schema-driven slots with `failover_partner_server` for arbitrary two-slot pairs ([`dify_servers.py`](services/dify/dify_servers.py)).
- **i18n** — `thinkingCoins` message namespace synced across all locale bundles.

### Fixed

- **Fixed-structure templates (tree/brace/flow)** — Fixed label lists (`children`, `parts`, `steps`) are enforced even when a dimension or dimension preference is also present; structure kwargs are passed on every agent route.
- **Landing error UX** — Validation and generation failures include `error_type` and optional `show_guidance`; stream HTTP 5xx responses no longer fall through to a duplicate JSON retry.
- **File Center** — Web ingest requires page content; RAG UI and auto-expand require a saved diagram linked to the package.
- **Generation library claim** — Preview outcomes record owner user/org; claim rejects mismatched authenticated users as not-found to avoid leaking preview existence ([`generation_library_claim.py`](services/diagram/generation_library_claim.py)).
- **MindMate library card metadata** — Library skip lookup uses authenticated fetch so metadata loads for signed-in users ([`MessageBubble.vue`](frontend/src/components/panels/mindmate/MessageBubble.vue)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.120.0).

## [5.119.0] - 2026-06-21

> **Thinking coins (思维币) — trial-teacher wallet, earn tasks, AI spend metering, and admin economy tab; PostgreSQL-only database stack.**

### Added

- **Thinking coin wallet** — Per-user balance + append-only ledger (`thinking_coin_wallets`, `thinking_coin_ledger`; migrations `rev_0065`–`rev_0069` with RLS); signup grant, daily check-in, referral/case rewards, and configurable AI spend costs ([`thinking_coin.py`](models/domain/thinking_coin.py), [`wallet_service.py`](services/auth/thinking_coin/wallet_service.py)).
- **Earn tasks** — Admin-configurable task registry (auto-login, usage-daily, client-event, navigate, custom CTA handlers); seeded exploration tasks (MindMate share, diagram export/save/translate/snapshot, learning sheet, workshop join) with daily/monthly earn caps ([`task_registry.py`](services/auth/thinking_coin/task_registry.py), [`client_event_service.py`](services/auth/thinking_coin/client_event_service.py)).
- **LLM spend wiring** — Trial-org teachers/school admins debit thinking coins instead of the daily token cap for MindMate turns, diagram generation, and canvas assist (autocomplete / node palette); pre-flight `ThinkingCoinInsufficientError` with localized modal ([`usage_wire.py`](services/auth/thinking_coin/usage_wire.py), [`services/llm/__init__.py`](services/llm/__init__.py)).
- **User API** — `GET /api/thinking-coins/wallet`, `/ledger`, `/checkin`, `POST /claim-event` ([`thinking_coins.py`](routers/auth/thinking_coins.py)).
- **Admin economy tab** — 系统设置 → 思维币: task CRUD, cost/cap settings, wallet preview ([`AdminThinkingCoinsTab.vue`](frontend/src/components/admin/AdminThinkingCoinsTab.vue), [`thinking_coins.py`](routers/auth/admin/thinking_coins.py)).
- **Frontend UX** — Sidebar balance widget + task promo, wallet modal (ledger + subscription reference), upgrade page/panel, insufficient-balance listener across canvas/MindMate flows ([`ThinkingCoinsModal.vue`](frontend/src/components/auth/ThinkingCoinsModal.vue), [`AppSidebarAccountFooter.vue`](frontend/src/components/sidebar/AppSidebarAccountFooter.vue)).
- **Feature flag** — `FEATURE_THINKING_COINS` (default off; trial-tier teachers/school admins only).

### Changed

- **PostgreSQL-only** — Removed SQLite migration CLI, merge/orphan services, and legacy `utils/migration/sqlite*` tree; docs and `env.example` now require PostgreSQL ([`README.md`](README.md), [`AGENTS.md`](AGENTS.md)).
- **Admin database tab** — PostgreSQL merge/orphan/export paths refactored into `pg_merge_*`, `pg_orphan_service`, `pg_sequence_reset`, and `pg_backup_manifest`; simplified UI ([`AdminDatabaseTab.vue`](frontend/src/components/admin/AdminDatabaseTab.vue)).
- **Backup scheduler** — PostgreSQL dump/import uses manifest-aware paths and improved failure logging.

### Fixed

- **MindMate export — dual Dify servers (MindBot)** — Org-linked MindBot export now queries every configured org Dify server (1 and 2), matching web export failover/history coverage.
- **MindMate export — date-only range** — Admin date picker defaults to 00:00; date-only selections normalize to full calendar days (start 00:00:00, end 23:59:59) instead of 08:00–18:00.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.119.0).

## [5.118.3] - 2026-06-21

> **MindMate export — DingTalk group + cross-org coverage, activity-window filtering, usage telemetry supplement.**

### Fixed

- **MindMate export — DingTalk group & 1:1 threads** — School and user exports now merge MindBot threads from `mindbot_usage_events` when the Dify conversation list omits per-group `conversation_id` rows (same Dify user, separate Redis-bound threads).
- **MindMate export — cross-org (LWCP) groups** — Whole-school, all-schools, and org-scoped user exports always include the shared `mindbot_{org}_unknown` Dify identity; usage supplement also queries `dingtalk_chat_scope=cross_org_group` so external-group chats are not dropped.
- **MindMate export — date range** — Conversation inclusion uses activity overlap (`created_at`/`updated_at` or usage event timestamps); matched threads fetch full message history (no per-bubble date clip).
- **MindMate export — background jobs** — Cross-org target is collected on the first user batch only (avoids duplicate Dify list fetches); summary JSONL checkpoints are deduped before message fetch.

### Changed

- **MindMate export — UI & artifacts** — Conversation list and downloaded HTML show DingTalk chat-scope badges (group / cross-org group / 1:1); JSON/ZIP carry `dingtalk_chat_scope` and `dingtalk_conversation_id` metadata.
- **MindBot telemetry** — `dingtalk_chat_scope()` records `cross_org_group` for LWCP senders (aligned with `CROSS_ORG_STAFF_PLACEHOLDER` / `mindbot_{org}_unknown`).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.118.3).

## [5.118.2] - 2026-06-20

> **Prompt understanding layer — landing + canvas one-sentence generate extract topic and fixed structure before agent spec generation.**

### Added

- **Requirements extraction (stage 2)** — After diagram classification, `extract_prompt_requirements` parses type-native JSON (`structure_mode`, central topic, fixed branches/steps/categories) via centralized prompts in [`prompts/requirements_schemas.py`](prompts/requirements_schemas.py) and [`agents/core/prompt_requirements.py`](agents/core/prompt_requirements.py).
- **Workflow wiring** — [`workflow.py`](agents/core/workflow.py) merges NL requirements with API fields (`fixed_dimension`, `existing_analogies`); agents receive clean central topic plus optional fixed-structure context; RAG stays a separate user-message block.
- **Mind map Case 2** — `mind_map_fixed_children_{en|zh}` prompt + `MindMapAgent` branch validates user-specified main branch labels verbatim.
- **API field** — Optional `generation_instructions` on `GenerateRequest`; canvas auto-complete sends it separately (concat fallback retained).
- **Richer inputs** — International landing textarea + inspiration chips; classic landing removes 50-char cap; canvas one-sentence examples and copy updated (zh/en/zh-tw).

> **App-wide structured error collection — admin Errors tab across LLM, MindBot, RAG, collab, Celery, auth, and production frontend.**

### Added

- **Error reporting helper** — [`error_reporting.py`](services/monitoring/error_reporting.py) centralizes `record_failure` / `record_exception` for all subsystems; Celery-safe `record_exception_from_celery`.
- **PostgreSQL persistence** — `error_groups` / `error_events` tables (migration `rev_0064_error_collection`); fingerprint grouping, occurrence counts, and stacktrace storage ([`error_collector.py`](services/monitoring/error_collector.py), [`error_event.py`](models/domain/error_event.py)).
- **Admin Errors tab** — 系统设置 → 错误收集: Swiss KPI summary, event vs grouped views, severity/source/time filters, detail dialog, and group mute ([`AdminErrorsTab.vue`](frontend/src/components/admin/AdminErrorsTab.vue), [`errors.py`](routers/auth/admin/errors.py)).
- **Retention & alerting** — Daily purge of events older than `ERROR_RETENTION_DAYS` (default 90) via [`error_retention_scheduler.py`](services/monitoring/error_retention_scheduler.py); threshold-based webhook/DingTalk robot alerts through [`alert_dispatcher.py`](services/monitoring/alert_dispatcher.py) (`ERROR_ALERT_*` in [`env.example`](env.example)).
- **Subsystem hooks** — Structured errors from LLM (`chat` / `chat_stream` / `chat_with_usage`), MindBot/Dify/DingTalk, knowledge-space & MindMate export tasks, RAG/Qdrant, workshop collab WS, live-spec flush, SMS/SES provider failures.
- **Production frontend reporting** — Vue `errorHandler`, `window.onerror`, and `unhandledrejection` POST to `/api/frontend_log` (prod only; deduped; skips headless export) via [`installFrontendErrorReporting.ts`](frontend/src/utils/installFrontendErrorReporting.ts).
- **Admin source filters** — Errors tab filters: `application`, `llm`, `frontend`, `background`, `mindbot`, `rag`, `collab`, `auth`.

### Fixed

- **Critical alert persistence** — Error collection no longer gated on SMS being enabled; unhandled exceptions no longer double-record when SMS alerts fire.
- **CSS import order** — `@import` for admin Swiss styles moved to top of [`admin-swiss-controls.css`](frontend/src/styles/admin-swiss-controls.css).

> **Auto-complete LLM buttons — per-model phase colors via SSE (green → blue → model color).**

### Added

- **Auto-complete stream API** — `POST /api/generate_graph/stream` emits SSE phase events (`accepted`, `waiting`, `streaming`, `complete` / `error`) for canvas auto-complete only; JSON `POST /api/generate_graph` unchanged for landing, subgraph, and other callers ([`diagram_generation.py`](routers/api/diagram_generation.py)).
- **LLM phase dispatch** — [`llm_spec_stream.py`](agents/core/llm_spec_stream.py) routes autocomplete agents through `chat_stream` with phase signals; thinking-map and mind-map `_generate_*_spec` paths updated.
- **Frontend phase UI** — `llmResultsStore.modelPhases` drives AIModelSelector traveling-ring colors (sending / waiting / streaming); [`useAutoComplete`](frontend/src/composables/editor/useAutoComplete.ts) consumes SSE with JSON fallback on non-stream responses.
- **Shared phase ring** — [`LlmPhaseRing.vue`](frontend/src/components/shared/LlmPhaseRing.vue) and [`llmLoadPhase.ts`](frontend/src/utils/llmLoadPhase.ts) reused by canvas model buttons and MindMate avatar.

### Fixed

- **Mind map auto-complete streaming** — `MindMapAgent` now passes `phase_emit` into spec generation (previously referenced undefined `kwargs`, breaking stream phases on mind maps).
- **LLM results teardown** — `clearCache()` aborts registered in-flight auto-complete controllers and resets model phases (prevents orphaned loading states).

> **MindMate — unified web + DingTalk history and load-phase avatar ring.**

### Added

- **Unified conversation list** — [`unified_conversations.py`](services/dify/unified_conversations.py) merges web MindMate and bound DingTalk MindBot identities; list rows include `channel` (`web` | `mindbot`) and `dify_user` for message/rename/delete routing ([`dify_conversations.py`](routers/api/dify_conversations.py)).
- **MindMate load phases** — [`mindMateLoadPhase.ts`](frontend/src/composables/mindmate/mindMateLoadPhase.ts) drives the same sending / waiting / streaming ring on [`MindmateAgentAvatar.vue`](frontend/src/components/panels/mindmate/MindmateAgentAvatar.vue) during chat SSE.

### Changed

- **Chat history mutations** — Sidebar rename/delete pass `dify_user` so MindBot conversations route to the correct Dify identity ([`ChatHistory.vue`](frontend/src/components/sidebar/ChatHistory.vue)).

> **Mind map themes, canvas export prep, and circle-map topic sizing.**

### Added

- **Mind map palette expansion** — Nord (Frost/Aurora/Polar Night), Radix light scales (teal, jade, cyan, violet, mauve, crimson, amber), and ColorHunt Sunset/Rose Warm presets with verifiable `sourceNote` on each theme ([`mindMapThemes.ts`](frontend/src/config/mindMapThemes.ts), [`nordMindMapPresets.ts`](frontend/src/config/nordMindMapPresets.ts), [`radixMindMapPresets.ts`](frontend/src/config/radixMindMapPresets.ts)).
- **Shared canvas export menu** — [`canvasExportMenu.ts`](frontend/src/config/canvasExportMenu.ts) unifies PNG/SVG/PDF/MG dropdown items between CanvasTopBar and mind-map toolbar.
- **Raster export prep** — [`diagramExportPrep.ts`](frontend/src/utils/diagramExportPrep.ts) fits canvas for capture, waits for fonts/paint, and restores viewport after community share ([`useDiagramCanvasExport.ts`](frontend/src/composables/diagramCanvas/useDiagramCanvasExport.ts)).
- **Auth pixel battle** — Optional retro canvas background on `/auth` (black cat vs Ultraman), gated by `FEATURE_AUTH_PIXEL_BATTLE` ([`AuthPixelBattleBg.vue`](frontend/src/components/auth/AuthPixelBattleBg.vue), [`authPixelBattle.ts`](frontend/src/utils/mascot/authPixelBattle.ts)).

### Fixed

- **Circle map topic radius** — Topic text measurement prefers intrinsic plain/markdown blocks instead of full-width inline-edit display, fixing oversized circular topic nodes ([`CircleNode.vue`](frontend/src/components/diagram/nodes/CircleNode.vue)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.118.2).

## [5.118.1] - 2026-06-19

> **Production log hardening — scheduled backup alerts, LLM retry/timeouts, JSON tab escape, DingTalk response normalization, Playwright async lookup.**

### Added

- **Backup — failure visibility** — Scheduled pg_dump logs the connection username before export; failures trigger SMS via `CriticalAlertService.send_runtime_error_alert` ([`backup_scheduler.py`](services/utils/backup_scheduler.py)). Admin manual export logs the same username ([`database_export_service.py`](services/admin/database_export_service.py)).
- **Backup — ops docs** — [`env.example`](env.example) documents that `DATABASE_MIGRATION_URL` must use the `mindgraph_migrate` role (BYPASSRLS) for pg_dump after RLS on `api_keys`.
- **LLM — doubao no-retry** — `LLMUtils.is_no_retry_model()`; doubao / ark-doubao fail fast with a single attempt (no burst backoff/retry).
- **Prompt-to-diagram normalizer** — [`prompt_to_diagram_result.py`](agents/core/prompt_to_diagram_result.py) wraps bare LLM spec dicts; shared [`_resolve_prompt_to_diagram_payload()`](routers/api/png_export.py) for `/api/generate_png` and `/api/generate_dingtalk`.

### Changed

- **LLM executor — per-attempt timeout and rate limiting** — Non-doubao models apply `asyncio.wait_for` inside each `with_retry` attempt (timeouts can actually retry); rate limiter slots are acquired per attempt, not held for the full retry loop ([`llm_request_executor.py`](services/llm/llm_request_executor.py)).
- **Playwright — async Chromium lookup** — Best executable selection runs in `asyncio.to_thread` from async browser context ([`browser.py`](services/infrastructure/utils/browser.py)).

### Fixed

- **JSON parser — control chars in strings** — Tabs, newlines, and carriage returns inside JSON string literals are escaped before `json.loads` (production flow-map failures) ([`json_parser.py`](agents/core/json_parser.py)).
- **GenerateDingTalk — invalid LLM shape** — Bare spec dicts without `diagram_type`/`spec` wrapper no longer 500; clarification/error dicts return 400 with the same user-facing message as generate_png.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.118.1).

## [5.118.0] - 2026-06-19

> **Dual Dify server failover, MindMate 记录导出 (sync + Celery background jobs), per-user daily token cap, and admin user activity timeline.**

### Added

- **Dual Dify servers per school** — `Organization` now stores a second Dify server (`dify_api_base_url_2` / `dify_api_key_2`), a primary/active selector (`dify_active_server`), and a `dify_failover_enabled` flag (migration `rev_0058_dify_dual_server`). 组织管理 / MindMate鉴权 gains an Element Plus segmented control to edit each server's URL + key with its own auth test, an active-server selector, and an auto-failover switch.
- **Heartbeat failover for live MindMate chat** — A background poller probes each org's configured Dify servers (~30s) and records health in Redis with anti-flap hysteresis (`redis_dify_server_health_cache.py`). `resolve_mindmate_dify_client` prefers the active server, fails over to the standby when the active is unhealthy, and switches back on recovery.
- **MindMate 记录导出** — New admin subtab under 新功能开发 (gated by `FEATURE_MINDMATE_EXPORT` + per-org `feature_org_access` + the `tab.settings.mindmate_export` capability). View and export Dify conversation history for a single user, multiple users, or a whole school over a date range. History is collected from **both** Dify servers over the Service API (full pagination), merged and deduped by conversation id, and rendered as WeChat/Telegram-style chat bubbles with a per-conversation server badge.
- **MindMate export — background Celery jobs** — Large exports (whole-school scope, more than `MINDMATE_EXPORT_SYNC_MAX_USERS` users, or more than `MINDMATE_EXPORT_SYNC_MAX_CONVERSATIONS` conversations) run as persisted Celery tasks (`mindmate_export_jobs`, migrations `rev_0062` / RLS `rev_0063`). Batched user/message collection writes JSONL checkpoints; admins can pause, resume, or cancel; live progress streams over SSE (Redis pub/sub); completed artifacts download as HTML / JSON / ZIP; artifacts expire after `MINDMATE_EXPORT_ARTIFACT_TTL_SECONDS` (default 24h) with periodic cleanup (`temp_export_cleaner.py`).
- **MindMate export — verification** — Post-collect reconciliation compares expected vs actual scope; job statuses include `completed_with_gaps` and `failed_verification`; optional spot-check sampling (`MINDMATE_EXPORT_VERIFY_SPOT_CHECK_N`); verification report embedded in JSON/ZIP artifacts (`MINDMATE_EXPORT_BLOCK_ON_GAPS` to fail hard on gaps).
- **Export formats** — JSON (full-fidelity source of truth, including the source server) and a self-contained HTML transcript (inline CSS, scrollable bubbles, opens offline), plus a ZIP of both. Each download is audited via the security logger (who exported which org/users/range/format).
- **Per-user daily token cap** — Authenticated LLM usage (`token_usage` paths) is capped at **1,000,000 tokens per user per Beijing calendar day** by default (`USER_DAILY_TOKEN_CAP`; set `0` to disable). Enforcement uses a Redis daily counter with pre-flight checks on `LLMService`, MindMate SSE, and Kitty Omni voice; admin user APIs expose `token_used_today` / `token_remaining_today`.
- **用户管理 — 活动记录** — Clicking a user in 用户管理 now opens a tabbed modal: **Token 趋势** (unchanged chart) plus **活动记录**, a curated timeline of MindGraph diagram topics, MindMate Q&A previews, and DingTalk chat/diagram activity (stored in `user_usage_activities` with 120-char previews, migrations `rev_0060` / RLS `rev_0061`). Historical MindGraph saves can be backfilled via `scripts/db/backfill_user_usage_activities.py`.
- **Auth — Software Agreement** — `/auth` footer opens a combined Terms of Use & Privacy Policy modal ([`SoftwareAgreementModal.vue`](frontend/src/components/auth/SoftwareAgreementModal.vue), [`authSoftwareAgreement.ts`](frontend/src/content/authSoftwareAgreement.ts); locale bundles `auth.softwareAgreement*`).
- **Docs — Celery setup** — [`docs/CELERY_SETUP.md`](docs/CELERY_SETUP.md) operator guide (Redis broker DB 1, app-managed worker, MindMate export jobs, RLS bootstrap on worker import).

### Changed

- **MindMate export — hybrid routing** — Small scopes stay synchronous in-request; larger scopes auto-route to background jobs ([`export_routing.py`](services/dify/export/export_routing.py), [`export_config.py`](services/dify/export/export_config.py)).
- **Admin user modal** — Token chart extracted to [`AdminUserTokenUsageTab.vue`](frontend/src/components/admin/AdminUserTokenUsageTab.vue); activity timeline in [`AdminUserActivityTab.vue`](frontend/src/components/admin/AdminUserActivityTab.vue); shared [`AdminSwissSegmented.vue`](frontend/src/components/admin/swiss/AdminSwissSegmented.vue) for filter toggles.
- **Error handling** — Added a narrow `DIFY_API_ERRORS` tuple in `services/utils/error_types.py` for failure-tolerant Dify Service API collection (one user/server error never aborts an export).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.118.0).

## [5.117.47] - 2026-06-18

> **MindMate / DingTalk diagram library unity — QR bind, library save, canvas entry.**

### Added

- **DingTalk QR bind** — Account modal **绑定账户** mints a QR; any channel that receives the QR (MindBot picture today) calls universal `claim_dingtalk_qr_bind`; one user ↔ one DingTalk staff per org (`dingtalk_staff_links`, migration 0056).
- **Library save on `/api/generate_dingtalk`** — Resolves user via JWT, `X-MG-Dify-User` / `dify_user_id` / `mg_dify_user`, or DingTalk bind table; embeds `![mg:uuid](url)` and `<!-- mg-diagram-id:uuid -->` in responses.
- **MindMate / MindBot Dify inputs** — Streams inject `mg_dify_user` (and `mg_conversation_id` when known) so the Dify HTTP tool can forward `{{inputs.mg_dify_user}}` to the generation endpoint.
- **MindMate canvas button** — **在画布中编辑** below generated diagram images when a library uuid is present in message markdown.
- **Ops** — [`docs/ops/dify_generate_dingtalk_header.md`](docs/ops/dify_generate_dingtalk_header.md): Dify HTTP tool forwards `conversation_id` / `sys.user_id`; MindGraph session registry bridges MindMate/MindBot callers to library save (custom header optional).

### Changed

- **Diagram cross-user alignment** — `generate_dingtalk` resolves `organization_id` with Dify-key users; validates `mg_user_{id}` against `users`; structured library-save skip logging (`no_user`, `unbound_staff`, `limit_reached`, `save_error`).
- **MindMate canvas entry** — Library-uuid-only button (removed `POST /api/diagrams/materialize_from_generation` and 24h Redis `dingtalk_gen:*` cache); auth required before navigate.
- **MindBot DingTalk skip notices** — Redis skip registry + MindBot outbound prepends teacher-facing library-save errors (zh/en); plain-streaming sends a follow-up notice chunk when needed.
- **Canvas library load errors** — Toast + URL cleanup when `?diagramId=` fetch fails; MindMate **图库已满** hint wired to `mindmate.diagramLibraryFull`.
- **generate_dingtalk skip notices** — When library save is skipped, plain-text responses include a short user-facing line (`unbound_staff`, `no_user`, `save_error`, `limit_reached`) in request language; MindMate shows a UI hint only for legacy messages without an embedded notice.
- **MindBot pipeline** — Picture pre-flight tries bind QR decode before Dify; bind replies use plain markdown outbound.
- **DingTalk bind QR security** — Rotating 30s HMAC code embedded in QR (`?t=…&c=…`), same model as quick registration room codes; atomic Redis consume; guess-rate limits per staff/token.
- **MindMate library reclaim** — Web MindMate auto-saves generate_dingtalk previews for the logged-in user when Dify strips library ids; preview outcome registry stores diagram id + reclaimable spec.
- **Import layout** — Diagram library save helpers moved to `services/diagram/` (fixes `helpers.py` vs `helpers/` package shadowing that broke app startup).

## [5.117.46] - 2026-06-18

> **Language settings modal — light Swiss stone shell and segmented canvas toggle.**

### Added

- **Frontend — language settings styles** — [`settings-language-swiss.css`](frontend/src/styles/settings-language-swiss.css): light stone dialog shell, inset sections, kickers, and reusable 50/50 segmented control pattern for binary settings (dark mode included).

### Changed

- **Frontend — LanguageSettingsModal** — Redesigned [`LanguageSettingsModal.vue`](frontend/src/components/settings/LanguageSettingsModal.vue) with custom header (glyph, title, subtitle note), stone inset layout, styled selects and footer buttons; mind map canvas mode uses plain `role="radio"` buttons instead of `ElRadioGroup` (no visible radio circles).
- **Frontend — i18n** — Added `settings.language.headerNote` in en, zh, and zh-tw locale bundles.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.46).

## [5.117.45] - 2026-06-17

> **Canonical copyright headers across application Python modules.**

### Changed

- **Backend — proprietary notices** — Added or normalized the Beijing Siyuan Zhijiao copyright block inside module docstrings across application Python (`services/`, `routers/`, `agents/`, `config/`, `utils/`, `models/`, `clients/`, `tasks/`, `repositories/`, `llm_chunking/`, `db_rls/`, `main.py`); fixed non-standard variants (English-only, mojibake UTF-8, `#` comment placement, 2024–2026 year range).

### Fixed

- **fail2ban_integration package** — Restored missing opening `"""` in [`__init__.py`](services/infrastructure/security/fail2ban_integration/__init__.py) after docstring copyright insert.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.45).

## [5.117.44] - 2026-06-17

> **Full-repo pylint gate, four-rule hardening completion, config import-cycle splits, and workshop WS module extraction.**

### Removed

- **Legacy JS cache routes** — Orphaned `/cache/status`, `/cache/performance`, and `/cache/modular` endpoints removed ([`routers/core/cache.py`](routers/core/cache.py)); superseded by Vue SPA asset serving since v5.0.0. Redis health remains at `/health/redis`; admin Performance tab covers server memory.

### Added

- **CI — four-rule audit gate** — [`audit_pylint_four_rules.py`](scripts/lint/audit_pylint_four_rules.py) with `--fail` in [`ci.yml`](.github/workflows/ci.yml) for `global-statement`, `import-outside-toplevel`, `protected-access`, and `broad-except`.
- **Config — db leaf modules** — [`db_sessions.py`](config/db_sessions.py) and [`database_alembic.py`](config/database_alembic.py) break `config.database` ↔ RLS/Alembic import cycles.
- **Clients — Dify exceptions** — Typed Dify API errors moved to [`dify_exceptions.py`](clients/dify_exceptions.py); shared by client and HTTP error mapping.
- **Lifecycle — app runtime** — Process-wide uptime holder in [`app_runtime.py`](services/infrastructure/lifecycle/app_runtime.py).
- **Workshop WS — feature modules** — Connection registry, broadcast core, disconnect cleanup, and shutdown constants split out of router modules ([`workshop_ws_registry.py`](services/features/workshop_ws_registry.py), [`workshop_ws_broadcast_core.py`](services/features/workshop_ws_broadcast_core.py), [`workshop_ws_disconnect_cleanup.py`](services/features/workshop_ws_disconnect_cleanup.py), [`workshop_ws_shutdown_constants.py`](services/features/workshop_ws_shutdown_constants.py)).
- **Scripts — lint helpers** — Docstring/import fixers and [`audit_pylint_four_rules.py`](scripts/lint/audit_pylint_four_rules.py) for the hardening sweep.

### Changed

- **CI — full pylint** — Python job runs pylint on `services`, `routers`, `agents`, `clients`, `config`, `utils`, `scripts`, `tests`, `loadtests`, `tasks`, and `alembic/env.py` with `--fail-under=10.0` (replaces collab/WS-only subset).
- **pyproject.toml — minimal pylint disables** — Main and `messages_control` lists trimmed to four pattern-level disables (`duplicate-code`, `too-few-public-methods`, `arguments-renamed`, `too-many-positional-arguments`); re-enabled docstring, import-order, design, and four hardening rules repo-wide.
- **Repo — pylint sweep (~780 files)** — Module/class/function docstrings, top-level imports, narrow `except` tuples from [`error_types.py`](services/utils/error_types.py), holder singletons (`instance` instead of `_instance`), and optional-import fallbacks without inline suppressions.
- **Singleton holders** — Email/SMS middleware, captcha, geolocation, health/process monitors, rate limiters, activity tracker, and document processor use public `instance` on holder classes.
- **Alembic — env.py** — `DATABASE_MIGRATION_URL` import hoisted to module top after path bootstrap.
- **Docs — AGENTS.md** — Documents full-tree pylint command, four-rule audit, and no-inline-suppression policy.

### Fixed

- **PostgreSQL startup (`.env`-driven)** — [`_postgresql_runtime.py`](services/infrastructure/process/_postgresql_runtime.py) derives connect-only vs app-managed mode from `DATABASE_URL` (RLS roles → never `initdb`); system cluster start via [`_postgresql_external.py`](services/infrastructure/process/_postgresql_external.py); `PG_CONNECT_ERRORS` in dependency check; `DATABASE_URL` verified after RLS bootstrap ([`postgres_app_startup.py`](scripts/db/postgres_app_startup.py)).
- **basedpyright — dump/import script** — Rich progress bar optional imports in [`dump_import_postgres.py`](scripts/db/dump_import_postgres.py) use the same top-level alias pattern as migration progress (fixes `reportOptionalCall` in CI).
- **basedpyright — psycopg2 stubs** — [`types-psycopg2`](https://pypi.org/project/types-psycopg2/) in [`requirements.txt`](requirements.txt) (typeshed stubs for optional legacy `psycopg2` imports; fixes `reportMissingModuleSource` in CI).
- **Inline suppressions** — Remaining `# type: ignore` in optional-import fallbacks replaced with module-top `try`/`ImportError` aliases; [`lint_no_inline_disables.py`](scripts/lint/lint_no_inline_disables.py) passes on the production tree.
- **Redis async startup** — Split sync vs async SCH kwargs in [`redis_connection_options.py`](services/redis/redis_connection_options.py): redis-py 8.0.0 accepts ``maint_notifications_config`` on sync connections only; async pools use ``redis_async_connection_options()`` so lifespan no longer crashes on first command. CI guard [`lint_redis_connection_options.py`](scripts/lint/lint_redis_connection_options.py) and [`test_redis_connection_options.py`](tests/test_redis_connection_options.py) prevent regression.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.44).

## [5.117.43] - 2026-06-16

> **basedpyright strict typing, CI lint gates, ORM Mapped migration, db_rls extraction, and repo-wide inline-suppression cleanup.**

### Added

- **CI — Ruff** — `ruff check` and `ruff format --check` in the Python job ([`ci.yml`](.github/workflows/ci.yml)).
- **CI — basedpyright** — Strict static typing gate via `[tool.basedpyright]` in [`pyproject.toml`](pyproject.toml); added to [`requirements.txt`](requirements.txt).
- **CI — no inline suppressions** — [`lint_no_inline_disables.py`](scripts/lint/lint_no_inline_disables.py) fails on `# pylint: disable`, `# noqa`, and `# type: ignore` outside allowed paths (typings, alembic versions).
- **Typings — third-party stubs** — [`typings/`](typings/) for Alembic RLS helpers, `psycopg`, `locust`, and `websocket` so basedpyright resolves optional/runtime imports.
- **db_rls — PostgreSQL RLS package** — RLS SQL and policy builders moved out of [`alembic/`](alembic/) into [`db_rls/`](db_rls/); migration revisions import from the new package.
- **Utils — typing helpers** — [`typing_helpers.py`](services/utils/typing_helpers.py), [`connection_types.py`](utils/auth/connection_types.py), and [`user_avatar_defaults.py`](utils/user_avatar_defaults.py) for shared typing and avatar defaults.

### Changed

- **pyproject.toml — pyright → basedpyright** — Renamed config section, tightened diagnostics (`reportPossiblyUnboundVariable`, `reportUndefinedVariable`), WSL conda `extraPaths`, and `stubPath = "typings"`.
- **Pylint — policy docs** — Documented pattern-level disables only (no inline `# pylint: disable`); removed `broad-except` from the main disable list; added `typings/` to ignore paths.
- **ORM — domain models** — Seventeen [`models/domain/`](models/domain/) modules migrated from legacy `Column` to SQLAlchemy 2.0 `Mapped` / `mapped_column` with `TYPE_CHECKING` relationship imports.
- **Repo — inline suppressions stripped** — ~280 Python files cleaned of inline `# pylint: disable`, `# noqa`, and `# type: ignore` comments; structural fixes applied instead (narrower imports, null checks, typed helpers).
- **Docs — AGENTS.md** — Documents `python -m basedpyright .` and the no-project-wide-suppression policy.

### Fixed

- **HTTP — request logging** — Guard `request.client.host` when the client is absent ([`middleware.py`](services/infrastructure/http/middleware.py)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.43).

## [5.117.42] - 2026-06-16

> **Sidebar brand header layout, user emoji avatar rendering on Edge, and centralized avatar defaults.**

### Changed

- **Sidebar — brand header** — Larger M logo with two-line left-aligned text beside it: 迈特教研 on top and truncated “{org}专属版” beneath when signed in; tighter line spacing and `text-xs` org subtitle ([`AppSidebar.vue`](frontend/src/components/sidebar/AppSidebar.vue), [`useAppSidebar.ts`](frontend/src/composables/sidebar/useAppSidebar.ts)).

### Fixed

- **Auth — user emoji avatars on Edge** — Sidebar and chat showed a black square when the default black-cat ZWJ emoji (`🐈‍⬛`) or other composite picker glyphs rendered without a color-emoji font. Centralized display via [`resolveUserAvatarEmoji()`](frontend/src/utils/userAvatarEmoji.ts) (shared default in [`user_avatar_defaults.py`](utils/auth/user_avatar_defaults.py)); `.mg-user-avatar-emoji` font stack on sidebar, MindMate, account/avatar modals, mobile, workshop, and share export ([`index.css`](frontend/src/styles/index.css)); non-default ZWJ picker choices fall back to their leading emoji for safe display; black cat stays the stored and displayed default. Tests: [`userAvatarEmoji.spec.ts`](frontend/tests/userAvatarEmoji.spec.ts).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.42).

## [5.117.41] - 2026-06-16

> **Sidebar philosophy quotes for signed-in users, org edition label in the header, offline quote import pipeline, and static-asset load optimizations.**

### Added

- **Sidebar — philosophy quotes** — Authenticated users see a random quote under their name in the account footer; rotates on login, full refresh, UI locale change, and every 5 minutes (session-scoped, pauses when the tab is hidden) ([`useSidebarPhilosophyQuote.ts`](frontend/src/composables/sidebar/useSidebarPhilosophyQuote.ts), [`sidebarQuotePicker.ts`](frontend/src/composables/sidebar/sidebarQuotePicker.ts), [`SidebarQuoteMarquee.vue`](frontend/src/components/sidebar/SidebarQuoteMarquee.vue)).
- **Sidebar — quote libraries** — Shipped zh/en JSON assets (~2.2 MB) merged from wisdom-quotes and frozen echoes extracts ([`sidebar-quotes-zh.json`](frontend/src/assets/sidebar-quotes-zh.json), [`sidebar-quotes-en.json`](frontend/src/assets/sidebar-quotes-en.json), [`import-sidebar-quotes/`](frontend/scripts/import-sidebar-quotes/), [`ATTRIBUTIONS.md`](frontend/scripts/vendor/sidebar-quotes/ATTRIBUTIONS.md)).
- **Sidebar — lazy load** — Locale bucket fetched via dynamic `import('…json?url')` + `fetch()` after login; not bundled into main JS chunks ([`sidebarQuotePicker.ts`](frontend/src/composables/sidebar/sidebarQuotePicker.ts)).
- **Scripts — import & verify** — `npm run import:sidebar-quotes` and `check:sidebar-quotes` in prebuild/CI ([`check-sidebar-quotes-shipped.ts`](frontend/scripts/check-sidebar-quotes-shipped.ts), [`package.json`](frontend/package.json)).
- **Scripts — PWA workbox guard** — `check:pwa-workbox` ensures shell-only precache plus runtime `/assets/*` caching ([`check-pwa-workbox.ts`](frontend/scripts/check-pwa-workbox.ts)).
- **Tests** — Quote picker, pool loader, import pipeline, and public-static middleware skip ([`useSidebarPhilosophyQuote.spec.ts`](frontend/tests/useSidebarPhilosophyQuote.spec.ts), [`loadSidebarQuotePool.spec.ts`](frontend/tests/loadSidebarQuotePool.spec.ts), [`import-sidebar-quotes.spec.ts`](frontend/tests/import-sidebar-quotes.spec.ts), [`test_public_static_middleware.py`](tests/services/test_public_static_middleware.py)).

### Changed

- **Sidebar — org edition label** — School/org name moves to a truncated “{org} 专属版” line under the brand logo; full name on hover ([`AppSidebar.vue`](frontend/src/components/sidebar/AppSidebar.vue), [`useAppSidebar.ts`](frontend/src/composables/sidebar/useAppSidebar.ts), [`sidebar.ts`](frontend/src/locales/messages/en/sidebar.ts)).
- **Sidebar — account footer** — Replaces static school subtitle with scrolling quote marquee when text overflows ([`AppSidebarAccountFooter.vue`](frontend/src/components/sidebar/AppSidebarAccountFooter.vue)).
- **Backend — static asset middleware** — `auth_context_middleware` and request debug logs skip `/assets/*`, `/static/*`, `/gallery/*`, PWA bootstrap, and health paths so cold loads no longer trigger hundreds of Redis session checks ([`spa_handler.py`](services/infrastructure/utils/spa_handler.py), [`middleware.py`](services/infrastructure/http/middleware.py)).
- **PWA — Workbox** — Precache shell + icons only; lazy JS/CSS/fonts load on demand and cache at runtime via CacheFirst on `/assets/*` and `/gallery/*` ([`vite.config.ts`](frontend/vite.config.ts)); sidebar quote JSON still excluded from precache.
- **Docs — AGENTS.md** — Sidebar quote asset paths, rotation rules, and import refresh commands.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.41).

## [5.117.40] - 2026-06-16

> **CI Node 26, GitHub Actions v6, and i18n key parity restored across all UI locales.**

### Changed

- **CI — Node 26** — Frontend job pins Node via [`frontend/.nvmrc`](frontend/.nvmrc); `engines.node` raised to `>=26.0.0` ([`package.json`](frontend/package.json)).
- **CI — GitHub Actions** — `actions/checkout@v6`, `actions/setup-node@v6`, and `actions/setup-python@v6` in [`ci.yml`](.github/workflows/ci.yml) and [`nightly-collab.yml`](.github/workflows/nightly-collab.yml) (Node 24 action runtime; clears Node 20 deprecation warnings).
- **i18n — zh canonical keys** — Added missing `admin.displayNameHint`, `admin.schoolManagersTab`, `admin.invitationCodeMaskedHint`, and demo login strings to zh/en ([`zh/admin.ts`](frontend/src/locales/messages/zh/admin.ts), [`zh/common.ts`](frontend/src/locales/messages/zh/common.ts)).
- **i18n — locale sync** — Re-aligned all non-zh UI bundles to zh key parity via [`sync-messages-keys-from-reference.ts`](frontend/scripts/sync-messages-keys-from-reference.ts); `check-i18n-keys.ts` passes (2832 keys × 77 locales).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.40).

## [5.117.39] - 2026-06-15

> **Sidebar site QR hover modal, SPA static MIME types via mimetypes, and explicit `/index.html` for Workbox fallback.**

### Added

- **Sidebar — site QR on logo hover** — Pointer devices show a blurred overlay with the public site URL QR (`/api/qrcode`); click-through still opens the update log on tap ([`LogoQrScanModal.vue`](frontend/src/components/sidebar/LogoQrScanModal.vue), [`AppSidebar.vue`](frontend/src/components/sidebar/AppSidebar.vue)).
- **Tests** — Vue dist MIME helper and `/index.html` / catch-all HTML content-type ([`test_vue_spa_static_mime.py`](tests/test_vue_spa_static_mime.py)).

### Changed

- **SPA — static MIME types** — Shared `media_type_for_vue_dist_relpath()` uses `mimetypes.guess_type` so `.html`, `.woff2`, and other extensions are not served as `application/octet-stream` ([`spa_handler.py`](services/infrastructure/utils/spa_handler.py), [`vue_spa.py`](routers/core/vue_spa.py)).
- **SPA — `/index.html` route** — Dedicated handler serves the SPA shell for Workbox `navigateFallback` and direct requests ([`vue_spa.py`](routers/core/vue_spa.py)).
- **HTTP — cache control** — `/index.html` included in no-cache HTML paths ([`middleware.py`](services/infrastructure/http/middleware.py)).
- **HTTP — cache control sweep** — SPA no-cache uses shared `is_spa_route()` / `should_apply_no_cache()` ([`spa_handler.py`](services/infrastructure/utils/spa_handler.py)); covers all client routes, PWA bootstrap files, and default `/api/*` no-store when handlers omit `Cache-Control` ([`middleware.py`](services/infrastructure/http/middleware.py), [`test_spa_cache_control.py`](tests/services/test_spa_cache_control.py)).
- **i18n — sidebar QR strings** — Site QR title and scan hint across en/zh/zh-tw ([`sidebar.ts`](frontend/src/locales/messages/en/sidebar.ts)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.39).

## [5.117.38] - 2026-06-15

> **School member email import, PWA cross-platform install hardening, dynamic manifest, and teaching-researcher role labels.**

### Added

- **School members — email contact** — Single and batch school user create accept mobile number or email; uniqueness checks for both ([`school_user_create.py`](services/auth/school_user_create.py), [`phone_uniqueness.py`](services/auth/phone_uniqueness.py), [`school_users.py`](routers/auth/admin/school_users.py)).
- **School members — batch import UX** — Paste parser detects email columns; invalid-row preview; post-import result screen with per-row failure reasons ([`parseBatchMemberPaste.ts`](frontend/src/utils/parseBatchMemberPaste.ts), [`SchoolAddMemberDialog.vue`](frontend/src/components/school/SchoolAddMemberDialog.vue)).
- **School members — batch skip registered** — Already-registered phones/emails are skipped (not failed); `skipped_count` and all-skipped success message ([`school_user_create.py`](services/auth/school_user_create.py), [`bundled_messages.py`](models/domain/message_catalog/bundled_messages.py)).
- **PWA — dynamic manifest** — `GET /manifest.webmanifest` serves origin-aware absolute `start_url`/`id` behind proxies ([`pwa_manifest.py`](services/infrastructure/utils/pwa_manifest.py), [`vue_spa.py`](routers/core/vue_spa.py)).
- **PWA — cross-platform install** — Surface detection (iOS, Android, Safari macOS, Chromium, Firefox); secure-origin guard; Android/Safari macOS/insecure hints ([`pwaInstall.ts`](frontend/src/utils/pwaInstall.ts), [`usePwaInstall.ts`](frontend/src/composables/usePwaInstall.ts)).
- **PWA — manifest metadata** — `lang`, `dir`, `display_override`, `categories`, and `prefer_related_applications` in Vite manifest ([`vite.config.ts`](frontend/vite.config.ts)).
- **Tests** — PWA platform detection and composable ([`pwaInstall.platforms.spec.ts`](frontend/tests/pwaInstall.platforms.spec.ts), [`usePwaInstall.spec.ts`](frontend/tests/usePwaInstall.spec.ts)); backend manifest origin ([`test_pwa_manifest.py`](tests/test_pwa_manifest.py)); email batch paste and create ([`parseBatchMemberPaste.spec.ts`](frontend/tests/parseBatchMemberPaste.spec.ts), [`test_school_user_create.py`](tests/auth/test_school_user_create.py)).

### Changed

- **Admin — role labels** — UI copy renames “Operations” to “Teaching Researcher” (教研员); Data Center tab “Platform Overview” ([`sidebar.ts`](frontend/src/locales/messages/en/sidebar.ts), [`admin.ts`](frontend/src/locales/messages/en/admin.ts), [`roles.py`](utils/auth/roles.py)).
- **PWA — install UI** — Sidebar and mobile account share [`usePwaInstall`](frontend/src/composables/usePwaInstall.ts); `apple-mobile-web-app-capable` meta ([`index.html`](frontend/index.html)).
- **i18n — school add member & PWA** — Contact/email batch strings and platform install hints across en/zh/zh-tw ([`admin.ts`](frontend/src/locales/messages/en/admin.ts), [`auth.ts`](frontend/src/locales/messages/en/auth.ts)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.38).

## [5.117.37] - 2026-06-11

> **PWA install, miniconda setup runtime, PostgreSQL fresh-install bootstrap, admin org-edit permissions, and removal of SWOT academic-email enforcement.**

### Added

- **PWA — installable web app** — [`vite-plugin-pwa`](frontend/vite.config.ts) manifest, Workbox service worker (`registerType: autoUpdate`), apple-touch and maskable icons ([`generate-pwa-icons.mjs`](frontend/scripts/generate-pwa-icons.mjs)); `npm run dev:pwa` for local install testing; SPA serves `.webmanifest` as `application/manifest+json` ([`vue_spa.py`](routers/core/vue_spa.py)).
- **PWA — install UI** — Sidebar account menu and mobile account page expose “Add to desktop”; captures `beforeinstallprompt`, iOS/desktop/dev hints ([`pwaInstall.ts`](frontend/src/utils/pwaInstall.ts), [`AppSidebarAccountFooter.vue`](frontend/src/components/sidebar/AppSidebarAccountFooter.vue), [`MobileAccountPage.vue`](frontend/src/pages/mobile/MobileAccountPage.vue)).
- **Setup — conda runtime** — [`conda_runtime.py`](scripts/setup/conda_runtime.py) resolves the active `mindgraph` miniconda env, runs pip/Playwright as the project user under sudo, and rejects PEP 668 externally-managed system Python.
- **PostgreSQL — server reachability probe** — [`ensure_postgresql_server_reachable()`](scripts/db/pg_ensure.py) checks host/port before MindGraph RLS roles exist (fresh install).
- **RLS bootstrap — peer auth + database create** — Distro PostgreSQL via `sudo -u postgres` unix socket first; auto-`createdb` when the application database is missing ([`rls_roles_bootstrap.py`](scripts/db/rls_roles_bootstrap.py)).
- **Tests** — PWA install eligibility and prompt flow ([`pwaInstall.spec.ts`](frontend/tests/pwaInstall.spec.ts)); overseas registration message keys without academic-email copy ([`test_overseas_registration_messages.py`](tests/test_overseas_registration_messages.py)).

### Changed

- **Setup — miniconda-first workflow** — [`setup.py`](scripts/setup/setup.py) uses project conda Python for pip, Playwright, and Qdrant client checks; README, [`requirements.txt`](requirements.txt), [`docs/QDRANT_SETUP.md`](docs/QDRANT_SETUP.md), and launch hints document `conda activate mindgraph` + `sudo -E env PATH="$PATH" "$(which python)"`.
- **Migrations CLI — fresh install** — When roles are not connected yet, probe PostgreSQL reachability instead of failing on credential probe ([`run_migrations.py`](scripts/db/run_migrations.py)).
- **Overseas registration — any email** — Registration and email-code flows always allow any valid non-mainland-China address; UI copy uses generic email labels ([`registration_overseas.py`](routers/auth/registration_overseas.py), [`useLoginModal.ts`](frontend/src/composables/auth/useLoginModal.ts), [`overseas_registration_messages.py`](utils/auth/overseas_registration_messages.py)).
- **Auth mode API** — Removed `overseas_education_email_required` from `GET /api/auth/mode` ([`public.py`](routers/auth/public.py), [`auth.ts`](frontend/src/stores/auth.ts)).
- **Admin — organization edit permissions** — School org tier/extra-seat fields and trend modal General tab honor `tab.organizations.edit` instead of a blanket read-only panel ([`AdminSchoolOrgGeneralTab.vue`](frontend/src/components/admin/AdminSchoolOrgGeneralTab.vue), [`AdminSchoolsTab.vue`](frontend/src/components/admin/AdminSchoolsTab.vue), [`AdminTrendChartModal.vue`](frontend/src/components/admin/AdminTrendChartModal.vue), [`adminCapabilities.ts`](frontend/src/utils/adminCapabilities.ts)).
- **i18n — PWA install strings** — Add-to-desktop label and platform install hints across locales ([`auth.ts`](frontend/src/locales/messages/en/auth.ts), [`common.ts`](frontend/src/locales/messages/en/common.ts)).
- **systemd template** — Comment clarifies miniconda env Python path ([`mindgraph.service.template`](scripts/setup/mindgraph.service.template)).

### Removed

- **SWOT academic email** — `pyswot` dependency, [`swot_academic.py`](services/auth/swot_academic.py), [`swot_config.py`](utils/auth/swot_config.py), Kikobeats sync scripts, `SWOT_ACADEMIC_EMAIL_REQUIRED` env setting, and related bundled error messages ([`env_settings.py`](models/domain/env_settings.py), [`bundled_messages.py`](models/domain/message_catalog/bundled_messages.py)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.37).

## [5.117.36] - 2026-06-10

> **Mobile canvas/Kitty TypeScript fixes, Kitty mic hold feedback, CI Python deps, and collab test alignment.**

### Changed

- **Mobile canvas — inline rec types** — `startRecommendations`, `selectOptionByGlobalIndex`, and `fetchNextBatch` signatures aligned with the editor coordinator return types ([`useMobileCanvasEventHandlers.ts`](frontend/src/composables/mobile/useMobileCanvasEventHandlers.ts), [`useMobileCanvasInlineRecBar.ts`](frontend/src/composables/mobile/useMobileCanvasInlineRecBar.ts)).
- **Mobile canvas — route loader** — Import `useInlineRecommendationsCoordinator` from the editor composables path; cast `currentLanguage` to `LocaleCode` for default diagram names ([`useMobileCanvasRouteLoader.ts`](frontend/src/composables/mobile/useMobileCanvasRouteLoader.ts)).
- **Mobile Kitty — mic PTT hold state** — Expose `pttPointerActive` so the mic button shows hold/active styling during pointer-down PTT ([`useMobileKittyMicPtt.ts`](frontend/src/composables/mobile/useMobileKittyMicPtt.ts), [`MobileKittyPage.vue`](frontend/src/pages/mobile/MobileKittyPage.vue)).
- **Mobile Kitty — bootstrap typing** — Page lifecycle uses shared `MobileKittyBootstrapPayload` instead of an inline payload shape ([`useMobileKittyPageLifecycle.ts`](frontend/src/composables/mobile/useMobileKittyPageLifecycle.ts)).

### Fixed

- **CI — backend smoke tests** — Install `requirements.txt` before Python smoke steps so `dotenv` and other imports resolve ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).
- **Mobile Mind Graph page — vue-tsc** — Repair corrupted import/const line that broke TypeScript checking ([`MobileMindGraphPage.vue`](frontend/src/pages/mobile/MobileMindGraphPage.vue)).
- **Collab tests — Redis snapshot keys** — Pin `COLLAB_REDIS_HASH_TAGS=0` in pattern assertions so hash-tag env does not skew expected key strings ([`test_online_collab_phase8.py`](tests/test_online_collab_phase8.py)).
- **Collab tests — granular merge** — Connection merge cases include endpoint nodes; delete+patch same id expects tombstone skip (not re-add); `asyncio.run` for hexpire participant test ([`test_workshop_collab_backend.py`](tests/test_workshop_collab_backend.py)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.36).

## [5.117.35] - 2026-06-10

> **School extra member seats, API-key usage flush to Postgres, and mobile canvas/Kitty refactor with router redirect fixes.**

### Added

- **School tier — extra member seats** — Organizations on paid tiers can receive bonus seats (0–500) above the tier base member cap via `extra_member_seats`; effective limit exposed as `member_limit_effective`; trial tier clears stored bonus seats ([`rev_0054_organization_extra_member_seats.py`](alembic/versions/rev_0054_organization_extra_member_seats.py), [`school_tier.py`](utils/auth/school_tier.py), [`school_tier_defs.py`](utils/auth/school_tier_defs.py), [`organizations.py`](routers/auth/admin/organizations.py)).
- **Admin — extra seats UI** — Preset chips and numeric input on school General tab and org trend modal; tier downgrade blocked against effective member cap ([`AdminSchoolOrgGeneralTab.vue`](frontend/src/components/admin/AdminSchoolOrgGeneralTab.vue), [`AdminTrendChartModal.vue`](frontend/src/components/admin/AdminTrendChartModal.vue), [`schoolTier.ts`](frontend/src/constants/schoolTier.ts), locale `admin.ts`).
- **API key usage — Redis flush worker** — Periodic drain of `apikey:usage:{id}` deltas into `api_keys.usage_count` plus shutdown flush ([`redis_api_key_usage_flush.py`](services/redis/cache/redis_api_key_usage_flush.py), [`lifespan.py`](services/infrastructure/lifecycle/lifespan.py), [`lifespan_shutdown.py`](services/infrastructure/lifecycle/lifespan_shutdown.py)).
- **Mobile canvas — composables** — Route loader, event handlers, toolbar, inline rec bar, unsaved-leave guard, and auto-save status extracted from [`MobileCanvasPage.vue`](frontend/src/pages/mobile/MobileCanvasPage.vue); styles split to [`mobileCanvasPage.global.css`](frontend/src/pages/mobile/mobileCanvasPage.global.css) / [`mobileCanvasPage.scoped.css`](frontend/src/pages/mobile/mobileCanvasPage.scoped.css).
- **Mobile Kitty — composables** — Mic PTT and page lifecycle logic moved to [`useMobileKittyMicPtt.ts`](frontend/src/composables/mobile/useMobileKittyMicPtt.ts) and [`useMobileKittyPageLifecycle.ts`](frontend/src/composables/mobile/useMobileKittyPageLifecycle.ts).
- **Mobile routing helpers** — Shared redirect map and client detection ([`mobileRouteRedirect.ts`](frontend/src/utils/mobileRouteRedirect.ts), [`isMobileClient.ts`](frontend/src/utils/isMobileClient.ts), [`diagramTypeKeys.ts`](frontend/src/utils/diagramTypeKeys.ts)).
- **Tests** — Extra member seats and org cache ([`test_school_tier.py`](tests/test_school_tier.py), [`test_school_user_create.py`](tests/auth/test_school_user_create.py)); mobile redirects and canvas back navigation ([`mobileRouterRedirects.spec.ts`](frontend/tests/mobileRouterRedirects.spec.ts), [`canvasBackNavigation.spec.ts`](frontend/tests/canvasBackNavigation.spec.ts)); mobile detect and canvas touch ([`useMobileDetect.spec.ts`](frontend/tests/useMobileDetect.spec.ts), [`useDiagramCanvasMobileTouch.spec.ts`](frontend/tests/useDiagramCanvasMobileTouch.spec.ts)).

### Changed

- **API keys — quota and admin counts** — Validation and admin list include pending Redis usage before enforcing quota or displaying totals ([`api_keys.py`](utils/auth/api_keys.py), [`redis_api_key_cache.py`](services/redis/cache/redis_api_key_cache.py), [`api_keys.py`](routers/auth/admin/api_keys.py)).
- **Mobile router — MindMate redirect** — Desktop `/mindmate` now maps to `/m/mindmate` instead of the mobile hub ([`mobileRouteRedirect.ts`](frontend/src/utils/mobileRouteRedirect.ts), [`index.ts`](frontend/src/router/index.ts)).
- **Mobile detect** — `useMobileDetect` delegates to shared `isMobileClient` helpers ([`useMobileDetect.ts`](frontend/src/composables/core/useMobileDetect.ts)).
- **Node palette / root concept panels** — Tabbed header layout with title, refresh, and close on one toolbar row ([`NodePalettePanel.vue`](frontend/src/components/panels/NodePalettePanel.vue), [`RootConceptModal.vue`](frontend/src/components/panels/RootConceptModal.vue), [`useNodePalette.ts`](frontend/src/composables/nodePalette/useNodePalette.ts)).
- **Admin — DingTalk card total** — Platform dashboard uses `dingtalk_generations.total` from token stats instead of summing API-key usage rows ([`AdminTokenOverviewRow.vue`](frontend/src/components/admin/AdminTokenOverviewRow.vue)).
- **Mobile layout** — Safe-area padding and back/home `aria-label`s ([`MobileLayout.vue`](frontend/src/layouts/MobileLayout.vue)).
- **Auth captcha row** — Responsive layout tweaks ([`auth-captcha.css`](frontend/src/styles/auth-captcha.css)).
- **i18n** — Extra member seat admin strings (en/zh/zh-tw); mobile nav and Kitty strings for zh-tw ([`admin.ts`](frontend/src/locales/messages/en/admin.ts), [`common.ts`](frontend/src/locales/messages/zh-tw/common.ts)).

### Fixed

- **Org Redis cache** — `extra_member_seats` round-trips through org cache; legacy payloads default to 0 ([`redis_org_cache.py`](services/redis/cache/redis_org_cache.py)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.35).

## [5.117.34] - 2026-06-07

> **Production log fixes: RLS-safe scheduled backups, PostgreSQL hourly token trends, multi-worker startup SMS.**

### Fixed

- **Backup — scheduled pg_dump RLS** — [`backup_scheduler.py`](services/utils/backup_scheduler.py) now uses shared `build_pg_dump_cmd()` with `--no-policies` (matches admin export and CLI dump; fixes nightly backup failure on `api_keys` RLS).
- **Admin — hourly token trends on PostgreSQL** — Replaced SQLite `func.strftime` with `date_trunc('hour', …)` via [`token_stats_queries.py`](utils/auth/token_stats_queries.py) in [`stats_trends.py`](routers/auth/admin/stats_trends.py) and [`mindbot_token_stats.py`](utils/auth/mindbot_token_stats.py).
- **Startup SMS — staggered multi-worker duplicate** — Keep Redis startup SMS lock until TTL after successful send; release only on real failures, not provider rate-limit duplicates ([`lifespan.py`](services/infrastructure/lifecycle/lifespan.py), [`sms_service.py`](services/auth/sms_service.py), [`keys.py`](services/redis/keys.py) `TTL_LOCK_STARTUP` 300s).

### Changed

- **SMS — rate-limit log severity** — Provider duplicate/rate-limit notification failures log as WARNING ([`sms_service.py`](services/auth/sms_service.py)).
- **pg_dump — shared command builder** — [`build_pg_dump_cmd()`](services/utils/pg_client_binaries.py) used by scheduled backup, admin export, and CLI dump.

### Added

- **Tests** — [`test_pg_dump_cmd.py`](tests/test_pg_dump_cmd.py), [`test_token_stats_hour_bucket.py`](tests/test_token_stats_hour_bucket.py), [`test_startup_sms_lock.py`](tests/test_startup_sms_lock.py), [`test_sms_rate_limit.py`](tests/test_sms_rate_limit.py).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.34).

## [5.117.33] - 2026-06-07

> **Diagram save reliability: UUID assignment for unlimited tiers, RLS org context, and clearer API errors.**

### Fixed

- **Diagram save — unlimited tier UUID** — New diagrams on paid/unlimited tiers no longer skip UUID assignment (previously caused `id` NOT NULL violations). Quota check and id generation extracted to [`diagram_new_id.py`](services/redis/cache/diagram_new_id.py) ([`test_diagram_save_uuid.py`](tests/test_diagram_save_uuid.py)).
- **Diagram save — RLS org context** — Create, update, duplicate, and quota count pass `organization_id` into `user_rls_session` so org-scoped RLS policies apply correctly ([`redis_diagram_cache.py`](services/redis/cache/redis_diagram_cache.py), [`_redis_diagram_cache_helpers.py`](services/redis/cache/_redis_diagram_cache_helpers.py), [`diagrams.py`](routers/api/diagrams.py)).
- **Diagram save — slot limit count** — Frontend uses server `total` instead of loaded list length for remaining slots and “slots full” checks ([`savedDiagrams.ts`](frontend/src/stores/savedDiagrams.ts)).
- **Auth — session expiry on mode check** — `GET /api/auth/mode` returning 401 triggers token-expired handling ([`auth.ts`](frontend/src/stores/auth.ts)).

### Changed

- **Diagram save — API error detail** — DB failures map to safe messages (RLS, field length, id assignment) via [`diagram_save_errors.py`](services/redis/cache/diagram_save_errors.py); frontend surfaces `detail` from failed save/update responses instead of generic throws ([`savedDiagrams.ts`](frontend/src/stores/savedDiagrams.ts)).
- **Editor — auto-save backoff** — After three consecutive save failures, debounced auto-save stops until the user edits again ([`useDiagramAutoSave.ts`](frontend/src/composables/editor/useDiagramAutoSave.ts)).

### Added

- **Tests** — UUID assignment and DB error mapping ([`test_diagram_save_uuid.py`](tests/test_diagram_save_uuid.py), [`test_diagram_db_errors.py`](tests/test_diagram_db_errors.py)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.33).

## [5.117.32] - 2026-06-06

> **Admin token stats include MindBot usage with shared trend modals; auth supports verification-code login (SMS/email) and optional overseas education email.**

### Changed

- **Admin — token statistics consistency** — School week totals and organizations list include MindBot usage; user rankings merge linked-user MindBot tokens (including promote-only users); org scoping unified on rankings; phones masked in token-stats rankings; schools tab token column opens all-time trend chart ([`stats.py`](routers/auth/admin/stats.py), [`stats_helpers.py`](routers/auth/admin/stats_helpers.py), [`mindbot_token_stats.py`](utils/auth/mindbot_token_stats.py), [`AdminSchoolsTab.vue`](frontend/src/components/admin/AdminSchoolsTab.vue)).
- **Admin — trend modals** — Shared org trend dialog on platform dashboard; empty-chart states; i18n for service names and load errors; `AdminStatsResponse` types aligned with API; chart locale follows UI language; org period cards resolve `organization_id` from trends when opened by name ([`AdminDashboardTab.vue`](frontend/src/components/admin/AdminDashboardTab.vue), [`useOrgTokenTrendModal.ts`](frontend/src/composables/admin/useOrgTokenTrendModal.ts), [`useAdminTrendChart.ts`](frontend/src/composables/admin/useAdminTrendChart.ts), [`adminApi.ts`](frontend/src/composables/queries/adminApi.ts)).
- **Admin — org data center** — User trend guard when id missing; top-users empty state; shared school invitation clipboard helper ([`AdminOrgDataCenterPanel.vue`](frontend/src/components/admin/AdminOrgDataCenterPanel.vue), [`copySchoolInvitationCode.ts`](frontend/src/utils/admin/copySchoolInvitationCode.ts)).
- **Auth — verification code login label** — `/auth` link text **短信登录** → **验证码登录** (SMS or email OTP). Password login, OTP login, and forgot-password flows accept phone or email; placeholders and validation copy aligned ([`LoginModal.vue`](frontend/src/components/auth/LoginModal.vue), [`useLoginModal.ts`](frontend/src/composables/auth/useLoginModal.ts), locale `auth.ts`).

### Added

- **Admin — shared stats helpers** — [`token_stats_queries.py`](utils/auth/token_stats_queries.py), [`stats_helpers.py`](routers/auth/admin/stats_helpers.py), [`useAdminTrendChart.ts`](frontend/src/composables/admin/useAdminTrendChart.ts); tests in [`test_admin_stats_http.py`](tests/auth/test_admin_stats_http.py), [`test_admin_stats_trends_http.py`](tests/auth/test_admin_stats_trends_http.py).
- **Auth — optional overseas education email** — `SWOT_ACADEMIC_EMAIL_REQUIRED` now defaults to **`false`**: overseas users may register with any non-mainland-China email (e.g. gmail.com). Set `SWOT_ACADEMIC_EMAIL_REQUIRED=true` to restore SWOT academic + Kikobeats free-domain enforcement. Exposed to the registration UI via `GET /api/auth/mode` → `overseas_education_email_required` ([`services/auth/swot_academic.py`](services/auth/swot_academic.py), [`routers/auth/public.py`](routers/auth/public.py), [`frontend/src/stores/auth.ts`](frontend/src/stores/auth.ts), [`frontend/src/composables/auth/useLoginModal.ts`](frontend/src/composables/auth/useLoginModal.ts)).
- **Tests** — Academic-email toggle and `/api/auth/mode` field ([`tests/test_overseas_registration_academic_flag.py`](tests/test_overseas_registration_academic_flag.py)).

### Fixed

- **Auth — overseas email verify parity** — `POST /email/verify` and `verify_and_consume_email_code` with `purpose=register` now reject mainland China email domains (same as `/email/send` and `/register-overseas`).
- **Auth — acknowledgement errors** — Generic `register_overseas_acknowledgment_required_any` when `SWOT_ACADEMIC_EMAIL_REQUIRED` is false ([`routers/auth/registration_overseas.py`](routers/auth/registration_overseas.py), [`bundled_messages.py`](models/domain/message_catalog/bundled_messages.py)).
- **Frontend — SC browser overseas ack** — `acknowledgeOverseasAnyScBrowser` shown when education email is optional but the browser prefers Simplified Chinese ([`useLoginModal.ts`](frontend/src/composables/auth/useLoginModal.ts)).
- **Auth — flag-aware overseas API errors** — GeoIP, mainland-CN domain, and acknowledgement messages use generic `*_any` copy when education email is optional ([`utils/auth/overseas_registration_messages.py`](utils/auth/overseas_registration_messages.py), [`bundled_messages.py`](models/domain/message_catalog/bundled_messages.py)).
- **Auth — live SWOT flag reads** — `SWOT_ACADEMIC_EMAIL_REQUIRED` is read from the environment on each check (not cached at import); `GET /api/auth/mode` reflects the current value after restart.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.32).

## [5.117.31] - 2026-06-05

> **RLS bootstrap reliability on managed PostgreSQL.** Fixes `sudo psql` connecting to the wrong socket and Alembic `0042` failing when `pg_stat_statements` is installed.

### Fixed

- **RLS role bootstrap psql host** — [`rls_roles_bootstrap.py`](scripts/db/rls_roles_bootstrap.py) resolves host/port from `DATABASE_URL` (admin URL first) instead of the distro default socket, so managed Postgres on `127.0.0.1` or `POSTGRESQL_DATA_DIR/sockets` is targeted correctly.
- **Alembic `0042` EXECUTE grants** — [`build_grant_rls_functions_to_app_sql()`](alembic/rls_functions_sql.py) grants `EXECUTE` only on `public.rls_*` helpers to `mindgraph_app`; avoids `GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public`, which fails when `pg_stat_statements` (rev `0031`) is present. Shared SQL reused in [`rls_roles_sql.py`](alembic/rls_roles_sql.py).

### Added

- **Tests** — Connection-arg coverage for RLS bootstrap psql ([`test_rls_roles_bootstrap.py`](tests/scripts/test_rls_roles_bootstrap.py)) and scoped grant SQL ([`test_rls_functions_sql.py`](tests/test_rls_functions_sql.py)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.31).

## [5.117.30] - 2026-06-02

> **RLS panel fixes (Alembic `0051`–`0053`) and Python dependency sweep.** Run migrations through `0053` before deploy. Upgrade Qdrant server to **1.18.1** when refreshing `qdrant-client` (`scripts/setup/update_qdrant_server.py`). Reinstall deps: `pip install -U -r requirements.txt`.

### Fixed

- **platform_bd RLS global read** — [`admin_scope_to_session_vars()`](utils/db/rls_admin_scope.py) checks `CAP_SCOPE_GLOBAL` before invited-org mapping so operations gets `panel_global_read=1` on global tabs.
- **Global organizations list for platform_bd** — [`panel_org_table_filter()`](utils/auth/admin_scope.py) returns all orgs when `scope.global`; invite tab still uses [`invite_org_filter()`](utils/auth/admin_scope.py) with invited + legacy scope for BD.
- **Post-commit panel RLS** — [`get_admin_scope`](routers/auth/dependencies.py) and [`bind_panel_superadmin_rls`](utils/db/rls_request.py) call `set_rls_context()` so `after_begin` re-applies panel GUCs after `commit`.

### Changed

- **PyPDF2 → pypdf** — PDF text extraction uses [`pypdf`](services/knowledge/document_processor.py) (PyPDF2 is deprecated); `pdfplumber` remains the fallback.
- **Pydantic v3-ready models** — Replaced nested `class Config` with `ConfigDict`, `@validator` → `@field_validator`, `min_items`/`max_items` → `min_length`/`max_length`; `pydantic>=2.13.4,<3.0` until v3 ships on PyPI.
- **pytest `pythonpath`** — [`pyproject.toml`](pyproject.toml) sets `pythonpath = ["."]` so bare `pytest` works from the repo root (WSL or Windows).
- **Alembic `0051`** — `rls_diagram_visible` scopes panel mode via org lookup; `panel_global_read` still sees all user-owned rows ([`rls_functions_sql.py`](alembic/rls_functions_sql.py)).
- **Alembic `0052`** — `rls_lookup_user_organization_id` (`SECURITY DEFINER`) prevents `rls_user_visible` stack overflow when panel policies read `users`.
- **Alembic `0053`** — `rls_lookup_org_invited_by_user_id` fixes `rls_panel_legacy_org_visible` recursion on `organizations`.
- **RLS head revision** — [`scripts/db/migration_urls.py`](scripts/db/migration_urls.py) expects Alembic through `0053`.
- **Global organizations list** — user/manager aggregates on [`GET /admin/organizations`](routers/auth/admin/organizations.py) use [`org_filter()`](utils/auth/admin_scope.py) so platform_bd counts match full org list.
- **Python dependencies (PyPI sweep)** — [`requirements.txt`](requirements.txt) minimum versions raised to current stable (FastAPI, LangChain/LangGraph, OpenAI, redis-py 8.x, numpy 2.x, pylint 4.x, ruff 0.15.x, and related stacks); `qdrant-client>=1.18.0,<1.19` with setup default **1.18.1** ([`update_qdrant_server.py`](scripts/setup/update_qdrant_server.py), [`setup.py`](scripts/setup/setup.py)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.30).

## [5.117.29] - 2026-06-02

> **PostgreSQL row-level security (RLS).** Database-layer tenant isolation replaces bare `AsyncSessionLocal()` across the app. Requires Alembic through `0050`, `mindgraph_app` / `mindgraph_migrate` roles, and `DATABASE_MIGRATION_URL` for DDL. See [`alembic/README.md`](alembic/README.md) and [`env.example`](env.example).

### Added

- **PostgreSQL RLS** — Alembic `0042`–`0050`: `rls_*()` helpers, `mindgraph_app` / `mindgraph_migrate` roles, tenant policies on registry tables, policy indexes; [`utils/db/rls_context.py`](utils/db/rls_context.py) + `SET LOCAL app.*` on every transaction; AdminScope [`to_rls_session_vars()`](utils/auth/admin_scope.py); [`alembic/README.md`](alembic/README.md) operator guide; `pg_dump --no-policies`; tests under [`tests/db/`](tests/db/) and RLS policy regressions ([`tests/test_rls_*.py`](tests/)).
- **Expert invite org scope (Alembic `0050`)** — Experts and platform BD see only orgs they created on the invite tab; legacy NULL `invited_by_user_id` orgs hidden from experts at SQL and RLS layers ([`invite_org_filter`](utils/auth/admin_scope.py), [`rls_panel_legacy_org_visible`](alembic/rls_functions_sql.py)); admin invites list route ([`invites.py`](routers/auth/admin/invites.py)).
- **RLS FastAPI helpers** — [`utils/db/rls_request.py`](utils/db/rls_request.py) binds `request.state.rls_context` (panel superadmin, mindbot callback, public org list, dashboard, system bootstrap); [`utils/db/session_open.py`](utils/db/session_open.py) exposes `user_rls_session`, `actor_rls_session`, `system_rls_session`, and `panel_superadmin_rls_session`.
- **RLS migration CLI** — [`scripts/db/migration_urls.py`](scripts/db/migration_urls.py) resolves runtime vs migrate URLs; [`scripts/db/rls_roles_bootstrap.py`](scripts/db/rls_roles_bootstrap.py) ensures roles exist; [`scripts/db/redis_flush.py`](scripts/db/redis_flush.py) optional `FLUSHDB` after URL cutover; [`scripts/db/postgres_app_startup.py`](scripts/db/postgres_app_startup.py) prepares RLS after PG is listening; Celery workers call `bootstrap_rls_migration_from_env()` on import ([`config/celery.py`](config/celery.py)).
- **RLS session lint** — [`scripts/lint/lint_rls_session.py`](scripts/lint/lint_rls_session.py) flags bare `AsyncSessionLocal()` outside RLS helpers.
- **`RLS_CONTEXT_STRICT`** — optional env flag logs ERROR when transactions start without `RlsContext`.
- **`get_db_sync()`** — uses `rls_sync_session`; Celery sync paths use `rls_sync_session(for_celery_user)`.
- **Admin users — school tier in rows** — List/detail payloads include effective `school_tier` ([`admin_user_list_rows.py`](services/auth/admin_user_list_rows.py)); admin table and edit modal show tier-aware role pills ([`userRoleDisplay.ts`](frontend/src/utils/userRoleDisplay.ts), [`AdminUsersTable.vue`](frontend/src/components/admin/AdminUsersTable.vue), [`AdminUserEditModal.vue`](frontend/src/components/admin/AdminUserEditModal.vue)).
- **Tests** — Phone/email uniqueness RLS ([`test_phone_uniqueness_rls.py`](tests/auth/test_phone_uniqueness_rls.py)), admin scope RLS session vars, expert invite org scope and `load_expert_invited_org_ids`, migration URL / redis flush scripts, and frontend school-tier row spec ([`userRoleDisplaySchoolTierRow.spec.ts`](frontend/tests/userRoleDisplaySchoolTierRow.spec.ts)).

### Fixed

- **`require_admin`** — Passes `Request` into `require_superadmin` so `panel_superadmin` RLS binds on Gewe, library admin, and other `Depends(require_admin)` routes.
- **DebateVerse stream** — Background SSE session uses `user_rls_session(owner_id)` instead of `system_rls_session`.
- **Devices RLS** — Policy uses `student_id` (Alembic `0049`); ESP32 register/status bind system RLS before DB; admin list/assign uses `require_admin`.
- **MindBot callback RLS** — Per-token DingTalk route binds `mindbot_service` RLS before and after tenant resolution ([`mindbot_callback.py`](routers/api/mindbot_callback.py)).
- **Phone/email uniqueness** — Global lookups use `system_rls_session` so registration and profile edits see all users under RLS ([`phone_uniqueness.py`](services/auth/phone_uniqueness.py)).
- **WebSocket auth** — User DB fallback via `system_rls_session`; removed `Depends(get_async_db)` ([`websocket_auth.py`](utils/auth/websocket_auth.py)).
- **Expert invited orgs** — `load_expert_invited_org_ids` uses system RLS; `build_admin_scope_async` no longer requires a caller DB session ([`admin_scope.py`](utils/auth/admin_scope.py)).
- **Update notifier** — All DB paths use `system_rls_session` instead of bare `AsyncSessionLocal`.
- **RLS `after_begin`** — Register listener on `Session` only (`AsyncSession` has no `after_begin` event in SQLAlchemy 2.x).
- **Alembic rev 0042** — Drop invalid ``LEAKPROOF`` on ``rls_*()`` helpers (``current_setting`` is not leakproof in PostgreSQL).
- **`run_migrations.py` RLS** — Auto-resolves `DATABASE_MIGRATION_URL` (never uses `mindgraph_app` for DDL); verifies rev 0050 + roles + policies; optional `.env` patch; pg_restore uses migrate URL; lightweight PG start (no LLM import); rev 0042 runs per-function DDL.
- **`main.py` / `init_db` RLS** — Startup and `_run_alembic_upgrade` auto-resolve migrate URL and load RLS Alembic helpers when `DATABASE_URL` is `mindgraph_app`.
- **Local Postgres subprocess** — Default leave server running after CLI exit; `MINDGRAPH_STOP_POSTGRES_ON_EXIT=1` restores stop-on-exit. Added [`scripts/db/check_migration_status.py`](scripts/db/check_migration_status.py).

### Changed

- **`get_async_db`** — Reads `request.state.rls_context`; auth middleware sets default user/deny context for direct sessions.
- **Auth middleware** — Sets per-request RLS context var (preset from route deps, authenticated user, or deny-default) ([`middleware.py`](services/infrastructure/http/middleware.py)).
- **Admin panel scope** — `get_admin_scope` binds and applies RLS to the session; workshop chat access sets `allow_global_channels` ([`dependencies.py`](routers/auth/dependencies.py)).
- **App-wide session migration** — Auth, API, features, Redis cache loaders, online collab, Celery tasks, and background jobs replace bare `AsyncSessionLocal()` with RLS session helpers.
- **`DATABASE_MIGRATION_URL`** — Alembic and org seed use migrate role when set ([`alembic/env.py`](alembic/env.py), [`env.example`](env.example)); documents `MINDGRAPH_APP_PASSWORD` / `MINDGRAPH_MIGRATE_PASSWORD` and managed-Postgres reuse behavior.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.29).

## [5.117.28] - 2026-06-01

> **Backup checkpoint before database-layer RLS.** This release captures the current application-layer school-tier and admin org-create behavior immediately before introducing PostgreSQL row-level security (RLS) at the database layer. Tag or branch from this commit if you need to roll back or compare pre-RLS behavior.

### Added

- **Tests** — School tier guards when org is missing (`user_has_school_tier_feature` denies; `max_diagrams_for_user` uses trial cap) and superadmin-only explicit tier on org create ([`test_school_tier.py`](tests/test_school_tier.py)).

### Changed

- **School tier — org create tier gate** — Only superadmins may set `school_tier` in the create-org request body; invite and non-superadmin flows always default to trial ([`school_tier.py`](utils/auth/school_tier.py), [`organizations.py`](routers/auth/admin/organizations.py)).
- **School tier — missing org fallbacks** — Users without a resolvable organization are denied tier-gated features and use the trial diagram cap instead of unlimited ([`school_tier.py`](utils/auth/school_tier.py)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.28).

## [5.117.27] - 2026-06-01

### Added

- **Org — subscription expiry downgrade** — When `organizations.expires_at` is in the past, effective school tier resolves to trial and paid tiers are persisted as trial on login and page load ([`org_subscription.py`](utils/auth/org_subscription.py), [`test_org_subscription.py`](tests/test_org_subscription.py)).
- **School tier — trial diagram cap** — Trial schools enforce 20 saved diagrams per teacher; paid tiers and personal accounts use unlimited saves (`diagrams_per_member` / zero cap) ([`school_tier.py`](utils/auth/school_tier.py), [`diagramLimit.ts`](frontend/src/utils/diagramLimit.ts)).
- **Admin — TanStack Query layer** — Typed admin API helpers, query keys, and read/mutation composables centralize admin fetches ([`adminApi.ts`](frontend/src/composables/queries/adminApi.ts), [`adminKeys.ts`](frontend/src/composables/queries/adminKeys.ts), [`useAdminQueries.ts`](frontend/src/composables/queries/useAdminQueries.ts), [`useAdminMutations.ts`](frontend/src/composables/queries/useAdminMutations.ts)).
- **Admin — panel Pinia store** — Shared tab context, org selection, toolbar state, and visibility-aware poll registration ([`adminPanel.ts`](frontend/src/stores/adminPanel.ts), [`useAdminOrgScope.ts`](frontend/src/composables/admin/useAdminOrgScope.ts), [`useAdminRouteSync.ts`](frontend/src/composables/admin/useAdminRouteSync.ts), [`useAdminPolling.ts`](frontend/src/composables/admin/useAdminPolling.ts)).
- **Admin — query error UX** — Scoped abort, ignorable cancel/abort detection, and mounted-only query error toasts ([`useScopedAbort.ts`](frontend/src/composables/core/useScopedAbort.ts), [`queryErrors.ts`](frontend/src/utils/queryErrors.ts), [`useQueryErrorNotification.ts`](frontend/src/composables/admin/useQueryErrorNotification.ts)).
- **Tests** — Org subscription expiry, diagram limit formatting, and query error classification ([`diagramLimit.spec.ts`](frontend/tests/diagramLimit.spec.ts), [`queryErrors.spec.ts`](frontend/tests/queryErrors.spec.ts)).

### Changed

- **Diagrams API — tier-based limits** — Create, list, and duplicate pass per-user caps from school tier (and subscription expiry) into Redis diagram cache; localized 403 detail on cap ([`diagrams.py`](routers/api/diagrams.py), [`redis_diagram_cache.py`](services/redis/cache/redis_diagram_cache.py)).
- **School tier — trial member cap removed** — Trial `member_limit` is unlimited (zero = no cap); manager and storage quotas unchanged ([`school_tier.py`](utils/auth/school_tier.py), [`schoolTier.ts`](frontend/src/constants/schoolTier.ts)).
- **Frontend — saved diagrams store** — `max_diagrams` from API drives unlimited vs capped UI, i18n limit toasts, and 403 handling ([`savedDiagrams.ts`](frontend/src/stores/savedDiagrams.ts), auth locale keys).
- **Admin — data-fetch refactor** — Schools, users, roles, MindBot, performance, teacher usage, and school dashboard tabs migrate to Vue Query + `adminPanel` store; legacy org/list/header composables removed.
- **Auth — login and profile** — Subscription check on login; org profile and token paths use effective tier after expiry ([`login.py`](routers/auth/login.py), [`org_profile.py`](routers/auth/org_profile.py), [`user_tokens.py`](utils/auth/user_tokens.py)).

### Removed

- **Admin — legacy org composables** — [`useAdminOrgContext.ts`](frontend/src/composables/admin/useAdminOrgContext.ts), [`useAdminOrganizationsList.ts`](frontend/src/composables/admin/useAdminOrganizationsList.ts), per-tab header toolbar composables, and school-dashboard org-picker/add-member header composables (logic consolidated into store + queries).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.27).

## [5.117.26] - 2026-05-31

### Added

- **Org — school trial tier (体验版)** — Fourth school subscription tier `trial` (体验版) is the default for new organizations; Alembic `rev_0041` migrates legacy implicit `standard` rows to `trial` and updates the column default. Teachers in trial orgs see a 体验版 sidebar pill; school managers keep 学校管理员; paid tiers (lite/standard/professional) show 学校版 for teachers ([`school_tier.py`](utils/auth/school_tier.py), [`schoolTier.ts`](frontend/src/constants/schoolTier.ts), [`userRoleDisplay.ts`](frontend/src/utils/userRoleDisplay.ts)).
- **Org — MindMate privatization flag** — Admin org and invite lists expose derived `is_privatized` when custom agent name, avatar, and dedicated Dify credentials are all set ([`org_privatization.py`](utils/auth/org_privatization.py), [`orgPrivatization.ts`](frontend/src/utils/orgPrivatization.ts)).
- **Auth — expert invite org scope** — Alembic `rev_0040` adds `organizations.invited_by_user_id` for expert/platform BD B2B org scoping ([`rev_0040_organization_invited_by_user.py`](alembic/versions/rev_0040_organization_invited_by_user.py)).
- **Admin — feature development tab** — Top-level `feature_dev` panel with subtabs for Smart Response, Kitty LLM Ops, and teacher usage; legacy routes redirect into the unified admin panel ([`AdminFeatureDevTab.vue`](frontend/src/components/admin/AdminFeatureDevTab.vue), [`adminFeatureDevNav.ts`](frontend/src/composables/admin/adminFeatureDevNav.ts)).
- **Admin — token overview row** — Extracted [`AdminTokenOverviewRow.vue`](frontend/src/components/admin/AdminTokenOverviewRow.vue) for platform token summary and DingTalk generation API-key card on the data center dashboard.
- **Admin — MindBot token stats helper** — Aggregates successful `mindbot_usage_events` Dify token counts for admin stats APIs ([`mindbot_token_stats.py`](utils/auth/mindbot_token_stats.py)).
- **Admin — role add-member modal** — Swiss stone dialog with `{action}-{role}` title, autofocus search, and stone table styling on the roles tab ([`AdminRoleAddMemberDialog.vue`](frontend/src/components/admin/AdminRoleAddMemberDialog.vue), [`admin-swiss-table.css`](frontend/src/styles/admin-swiss-table.css)).
- **Admin — Swiss pagination** — Shared [`AdminSwissPagination.vue`](frontend/src/components/admin/AdminSwissPagination.vue) for admin and school user tables.
- **Tests** — School trial tier, org privatization, expert invite scope, MindBot token stats, role-control members, admin panel org scope RLS, and frontend capability/sidebar specs ([`test_school_tier.py`](tests/test_school_tier.py), [`test_org_privatization.py`](tests/test_org_privatization.py), [`test_expert_invite_scope.py`](tests/auth/test_expert_invite_scope.py), [`test_mindbot_token_stats.py`](tests/auth/test_mindbot_token_stats.py), [`schoolTier.spec.ts`](frontend/tests/schoolTier.spec.ts)).

### Changed

- **Admin — token overview includes DingTalk MindBot (Dify)** — `Token 使用总览`, MindMate breakdown, dashboard week totals, school org rankings (today), and token trend charts fold in successful `mindbot_usage_events` token counts (same Dify stack as web MindMate). `/api/generate_dingtalk` remains Qwen/MindGraph; the DingTalk API-key card still shows key hit counts only ([`stats.py`](routers/auth/admin/stats.py), [`stats_trends.py`](routers/auth/admin/stats_trends.py)).
- **Auth — role matrix alignment** — Seven-role permission matrix enforced end-to-end: expert and platform BD invites scoped via `invited_by_user_id` and `scope.invited_orgs`; school_admin limited to own-school dashboard and user management; MindBot admin superadmin-only; new `tab.school_dashboard.view` cap for school stats APIs ([`admin_panel_permissions.py`](utils/auth/admin_panel_permissions.py), [`admin_scope.py`](utils/auth/admin_scope.py), [`adminCapabilities.ts`](frontend/src/utils/adminCapabilities.ts)).
- **Admin — unified panel navigation** — Standalone MindBot admin page removed; `/admin/mindbot`, `/school-dashboard`, `/teacher-usage`, `/smart-response`, and `/gewe` redirect into capability-gated admin tabs; settings sidebar uses [`useAdminSettingsNav.ts`](frontend/src/composables/admin/useAdminSettingsNav.ts) ([`AdminPage.vue`](frontend/src/pages/AdminPage.vue), [`router/index.ts`](frontend/src/router/index.ts)).
- **Admin — roles tab refactor** — Role control extracted into composables and header toolbar; schools and invite tables show privatization column ([`AdminRolesTab.vue`](frontend/src/components/admin/AdminRolesTab.vue), [`useAdminRoleControl.ts`](frontend/src/composables/admin/useAdminRoleControl.ts)).

### Removed

- **Admin — standalone tokens tab** — [`AdminTokensTab.vue`](frontend/src/components/admin/AdminTokensTab.vue) removed; token KPIs live on the data center dashboard via [`AdminTokenOverviewRow.vue`](frontend/src/components/admin/AdminTokenOverviewRow.vue).
- **Admin — MindBot admin page** — [`MindbotAdminPage.vue`](frontend/src/pages/MindbotAdminPage.vue) retired in favor of the organizations tab and superadmin-only MindBot access.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.26).

## [5.117.25] - 2026-05-31

### Added

- **Org — school subscription tier** — Alembic `rev_0039` adds `school_tier` (`lite` | `standard` | `professional`) on `organizations`; member/manager caps, premium feature gates (online collab, presentation tools, Chrome extension, API tokens), and school dashboard quota payload ([`school_tier.py`](utils/auth/school_tier.py), [`schoolTier.ts`](frontend/src/constants/schoolTier.ts)).
- **School dashboard — quotas & add members** — [`SchoolDashboardQuotaCard.vue`](frontend/src/components/school/SchoolDashboardQuotaCard.vue) and [`SchoolAddMemberDialog.vue`](frontend/src/components/school/SchoolAddMemberDialog.vue) with Excel-paste batch import ([`parseBatchMemberPaste.ts`](frontend/src/utils/parseBatchMemberPaste.ts), [`school_user_create.py`](services/auth/school_user_create.py)).
- **Admin — personal trial (C2C) invite** — [`AdminPersonalTrialInviteCard.vue`](frontend/src/components/admin/AdminPersonalTrialInviteCard.vue) and `GET /api/auth/admin/invites/personal-trial` when `PERSONAL_TRIAL_ORG_CODE` is set ([`personal_trial_invite.py`](services/auth/personal_trial_invite.py)).
- **Admin — invites organizations API** — Scoped org list with invitation codes for the invite-users tab ([`invites.py`](routers/auth/admin/invites.py)).
- **Admin — Swiss stat cards** — Shared KPI, quota, period, performance, and service card components ([`frontend/src/components/admin/swiss/`](frontend/src/components/admin/swiss/), [`admin-swiss-palette.css`](frontend/src/styles/admin-swiss-palette.css), [`admin-swiss-stat-cards.css`](frontend/src/styles/admin-swiss-stat-cards.css)).
- **Frontend — school tier features** — [`useSchoolTierFeatures.ts`](frontend/src/composables/auth/useSchoolTierFeatures.ts) gates collab, presentation tools, Chrome extension, and API tokens in canvas, account, and MindGraph UI.
- **Utils — org storage estimate** — Diagram storage usage estimate for quota display ([`org_storage_estimate.py`](utils/auth/org_storage_estimate.py), [`formatStorageBytes.ts`](frontend/src/utils/formatStorageBytes.ts)).
- **Tests** — School tier limits, HTTP feature gating, school user batch create, org storage estimate, and MindBot admin RLS ([`test_school_tier.py`](tests/test_school_tier.py), [`test_school_tier_http.py`](tests/test_school_tier_http.py), [`test_school_user_create.py`](tests/auth/test_school_user_create.py), [`test_org_storage_estimate.py`](tests/test_org_storage_estimate.py), [`test_mindbot_admin_rls_http.py`](tests/auth/test_mindbot_admin_rls_http.py)).

### Changed

- **Admin — Swiss stat dashboard refactor** — Data center, performance, tokens, and token-by-service panels use shared Swiss card layout ([`AdminDashboardTab.vue`](frontend/src/components/admin/AdminDashboardTab.vue), [`AdminPerformanceTab.vue`](frontend/src/components/admin/AdminPerformanceTab.vue), [`AdminTokensTab.vue`](frontend/src/components/admin/AdminTokensTab.vue)).
- **Admin — school tier UI** — Tier selector and quota hints in school org modal ([`AdminSchoolOrgGeneralTab.vue`](frontend/src/components/admin/AdminSchoolOrgGeneralTab.vue)); tier downgrade blocked when member or manager counts exceed the selected tier cap.
- **School tier — backend feature gates** — Lite tier blocks workshop collab, presentation generation, personal API tokens, and premium client bundles ([`diagrams_workshop_routes.py`](routers/api/diagrams_workshop_routes.py), [`web_content_generation.py`](routers/api/web_content_generation.py), [`personal_token.py`](routers/auth/personal_token.py)).
- **School dashboard — layout refactor** — Quota cards, embedded add-member from admin header, and slimmer page shell ([`SchoolDashboardPage.vue`](frontend/src/pages/SchoolDashboardPage.vue)).
- **Admin — invite users tab** — Personal trial card and organizations list wired to invites API ([`AdminInviteUsersTab.vue`](frontend/src/components/admin/AdminInviteUsersTab.vue)).
- **Auth — profile payload** — JWT and org profile include `school_tier` and tier feature flags ([`org_profile.py`](routers/auth/org_profile.py), [`auth.ts`](frontend/src/types/auth.ts)).
- **Expert role — admin panel** — Invites tab view/edit capabilities for expert and platform BD ([`admin_panel_permissions.py`](utils/auth/admin_panel_permissions.py)).
- **Frontend — Kitty desktop poll** — Global action poll mounted from [`App.vue`](frontend/src/App.vue) instead of canvas-only layouts.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.25).

## [5.117.24] - 2026-05-30

### Added

- **Org — shared MindBot/MindMate Dify settings** — Alembic `rev_0037` stores timeout, chain-of-thought, and AI-card streaming limits on `organizations`; backfills from the first MindBot config per school when present.
- **MindBot — `use_org_dify_settings`** — Alembic `rev_0038`; each bot can inherit school MindMate Dify credentials or keep custom per-bot Dify keys ([`organization_dify.py`](routers/auth/admin/organization_dify.py), [`mindbot_admin.py`](routers/api/mindbot_admin.py)).
- **Admin — token usage by service** — Token stats and dashboard breakdown for MindGraph vs MindMate; per-org today ranking supports service filter ([`stats.py`](routers/auth/admin/stats.py), [`AdminTokenUsageByServicePanel.vue`](frontend/src/components/admin/AdminTokenUsageByServicePanel.vue)).
- **Admin — user list enrichment** — Shared row builder with diagram counts, paid benefit, and usage fields ([`admin_user_list_rows.py`](services/auth/admin_user_list_rows.py), [`test_admin_user_list_rows.py`](tests/auth/test_admin_user_list_rows.py)).
- **Frontend — MindBot config refactor** — Extracted [`AdminMindBotConfigForm.vue`](frontend/src/components/admin/AdminMindBotConfigForm.vue), [`useAdminMindBotConfig.ts`](frontend/src/composables/admin/useAdminMindBotConfig.ts), and school-modal pane [`AdminSchoolMindBotTab.vue`](frontend/src/components/admin/AdminSchoolMindBotTab.vue).
- **Frontend — admin users refactor** — Split users tab into [`AdminUsersTable.vue`](frontend/src/components/admin/AdminUsersTable.vue), [`AdminUserEditModal.vue`](frontend/src/components/admin/AdminUserEditModal.vue), and header toolbar composables.
- **Frontend — school dashboard org picker** — Admins preview any school dashboard via [`SchoolDashboardOrgPicker.vue`](frontend/src/components/school/SchoolDashboardOrgPicker.vue) and [`useSchoolDashboardOrgPicker.ts`](frontend/src/composables/school/useSchoolDashboardOrgPicker.ts).
- **Frontend — admin Swiss controls** — Shared select poppers and control styles ([`admin-swiss-controls.css`](frontend/src/styles/admin-swiss-controls.css), school/MindBot select popper CSS).
- **Ops — WSL reload guard** — [`_reload_watch_guard.py`](services/infrastructure/process/_reload_watch_guard.py) removes self-referential root symlinks that break uvicorn watchfiles; `.gitignore` ignores accidental `/MindGraph` symlink.
- **Ops — cross-platform native deps** — [`ensure-cross-platform-native-deps.mjs`](frontend/scripts/ensure-cross-platform-native-deps.mjs) installs missing Rolldown/Tailwind bindings when WSL and Windows share `node_modules`.
- **Tests** — Org Dify / MindBot unification coverage ([`test_org_dify_mindbot_unification.py`](tests/test_org_dify_mindbot_unification.py)).

### Changed

- **Admin — org Dify settings UI** — School MindMate Dify tab edits org-level behavior fields and propagates to bots with `use_org_dify_settings` ([`AdminSchoolDifySettings.vue`](frontend/src/components/admin/AdminSchoolDifySettings.vue)).
- **Admin — panel layout** — Breadcrumb composable, settings subtabs, and refactored [`AdminPage.vue`](frontend/src/pages/AdminPage.vue) / [`SchoolDashboardPage.vue`](frontend/src/pages/SchoolDashboardPage.vue).
- **Admin — users & school users APIs** — List endpoints use shared enrichment helper; phone uniqueness checks extended ([`users.py`](routers/auth/admin/users.py), [`school_users.py`](routers/auth/admin/school_users.py)).
- **Frontend — role display** — Extended localized role labels ([`userRoleDisplay.ts`](frontend/src/utils/userRoleDisplay.ts)).
- **Frontend — trend charts** — [`AdminTrendChartModal.vue`](frontend/src/components/admin/AdminTrendChartModal.vue) layout and lazy Chart.js loading improvements.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.24).

## [5.117.23] - 2026-05-29

### Added

- **Admin — unified management panel** — Single `/admin` 管理面板 with six capability-gated tabs (数据中心, 用户管理, 组织管理, 邀请用户, 订单与付费, 系统设置) for roles superadmin, platform_bd, expert, and school_admin; legacy admin URLs redirect into the panel.
- **Admin — row-level security** — `AdminScope`, `ROLE_PANEL_CAPABILITIES`, and `GET /api/auth/admin/capabilities` enforce org-scoped data for school_admin and read-only global access for platform_bd; roles teacher / personal_* are denied panel access.
- **Frontend — `useAdminAccess` / `adminCapabilities.ts`** — Tab visibility and org scope mirror backend capabilities at runtime.
- **Tests** — Admin scope unit tests and RLS HTTP coverage ([`test_admin_scope.py`](tests/auth/test_admin_scope.py), [`test_admin_rls_http.py`](tests/auth/test_admin_rls_http.py)); Vitest [`adminCapabilities.spec.ts`](frontend/tests/adminCapabilities.spec.ts).

### Changed

- **Sidebar** — Removed fixed admin block (Gewe, MindBot, Smart Response, Teacher Usage, school dashboard); one **管理面板** entry in main nav for management roles.
- **Admin APIs** — School stats and school user routes use panel capability checks and `AdminScope` org resolution.
- **Frontend — admin layout** — Removed `AdminLayout.vue`; admin pages use `DefaultLayout` with tabbed panel components ([`AdminPage.vue`](frontend/src/pages/AdminPage.vue), [`AdminDataCenterTab.vue`](frontend/src/components/admin/AdminDataCenterTab.vue), [`AdminUsersPanel.vue`](frontend/src/components/admin/AdminUsersPanel.vue)).
- **Frontend — Vite dev server** — HMR WebSocket defaults to `localhost` when binding `0.0.0.0`; optional WSL `/mnt/c` file polling via `VITE_USE_POLLING` ([`vite.config.ts`](frontend/vite.config.ts)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.23).

## [5.117.22] - 2026-05-29

### Added

- **Frontend — DEP0205 regression gate** — `npm run check:dep0205` traces prebuild, vue-tsc, and Vite build; fails on `module.register()` deprecation ([`check-dep0205.mjs`](frontend/scripts/check-dep0205.mjs), CI frontend job).
- **Frontend — VueUse PURE annotation gate** — `npm run check:vueuse-pure` fails if `@vueuse/core` dist contains Rolldown-invalid `/* #__PURE__ */` forms ([`check-vueuse-pure-annotations.mjs`](frontend/scripts/check-vueuse-pure-annotations.mjs), CI frontend job).
- **Frontend — CLI script smoke test** — `npm run check:scripts` runs `sync-version` and `check-i18n-keys` under Node native type stripping.
- **Ops — Node version pin** — [`frontend/.nvmrc`](frontend/.nvmrc) and `engines.node` ≥ 22.18 in [`package.json`](frontend/package.json).

### Changed

- **Frontend — remove tsx** — All CLI scripts use `node scripts/*.ts` (Node 26 native type stripping); `tsx` removed from devDependencies.
- **Frontend — ESM import suffixes** — Locale bundle `index.ts` files and script imports use explicit `.ts` extensions for Node ESM; [`locales.ts`](frontend/src/i18n/locales.ts) loads prompt registry via relative JSON import with `with { type: 'json' }`.
- **Frontend — Tailwind 4.3.0 floor** — `@tailwindcss/vite` and `tailwindcss` ^4.3.0 (upstream `registerHooks` on Node 26).
- **Frontend — @vueuse/core Rolldown fix** — [`patches/@vueuse+core+14.3.0.patch`](frontend/patches/@vueuse+core+14.3.0.patch) applies upstream [vueuse#5388](https://github.com/vueuse/vueuse/pull/5388) until npm publishes a release after 14.3.0; `postinstall` runs `patch-package`.
- **Ops — WSL node_modules** — [`NODE_NVM_SETUP.md`](docs/NODE_NVM_SETUP.md) documents WSL-only installs and DEP0205 verification.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.22).

## [5.117.21] - 2026-05-29

### Added

- **Frontend — Vite 8 module interop smoke tests** — Vitest project exercises dynamic imports for `vue3-carousel-3d`, `mathlive`, `html-to-image`, and deep Element Plus ESM paths under Rolldown ([`vite8ModuleInterop.spec.ts`](frontend/tests/vite8ModuleInterop.spec.ts)).
- **Ops — LF normalization scripts** — One-off CRLF→LF helpers for WSL/`/mnt/c` working copies ([`normalize-lf.py`](frontend/scripts/normalize-lf.py), [`normalize-lf-repo.py`](frontend/scripts/normalize-lf-repo.py)).

### Changed

- **Frontend — Vite 8 / Vitest 4** — `vite` ^8.0.14 (Rolldown), `vitest` ^4.1.7; Vitest split into `unit` and `vite8-interop` projects with a 60s timeout for cold ESM imports ([`vitest.config.ts`](frontend/vitest.config.ts), [`vite.config.ts`](frontend/vite.config.ts)).
- **Frontend — TypeScript 6 & ESLint 10** — `typescript` ^6.0.3 with `ignoreDeprecations: "6.0"`; `eslint` ^10.4.0 and `@eslint/js` ^10.0.1 ([`tsconfig.json`](frontend/tsconfig.json), [`eslint.config.js`](frontend/eslint.config.js)).
- **Frontend — Lucide icons** — `lucide-vue-next` replaced by `@lucide/vue`; manual chunk renamed to `vendor-lucide` ([`package.json`](frontend/package.json), [`vite.config.ts`](frontend/vite.config.ts)).
- **Frontend — router & charts** — `vue-router` ^5.1.0; `echarts` ^6.1.0; `katex` ^0.17.0; `jsdom` ^29.1.1.
- **Frontend — dependency cleanup** — Removed unused `axios`, `@vue-flow/controls`, `@tanstack/vue-virtual`, `page-flip`, and `vue-danmaku`; dropped `vendor-axios` manual chunk.
- **Frontend — type-only imports** — `import type` / `export type` across Vue SFCs, composables, and stores for `verbatimModuleSyntax` under TypeScript 6.
- **Frontend — npm allowScripts** — Pinned `core-js@3.49.0` and `esbuild@0.28.0` in the install-script allowlist ([`package.json`](frontend/package.json)).
- **Repo — LF line endings** — `.editorconfig` enforces LF on `*.{js,ts,mjs,cjs,vue,css,scss}`; locale bundles and frontend sources normalized to LF.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.21).

## [5.117.20] - 2026-05-29

### Added

- **Auth — seven-role user system** — Canonical roles `superadmin`, `platform_bd`, `expert`, `school_admin`, `teacher`, `personal_trial`, and `personal_paid` with legacy mapping (`admin` → `superadmin`, `manager` → `school_admin`, `user` → `teacher`); shared constants and capability scaffolding in [`role_constants.py`](utils/auth/role_constants.py); Alembic `rev_0036` widens `users.role` and backfills legacy values ([`rev_0036_seven_user_roles.py`](alembic/versions/rev_0036_seven_user_roles.py)).
- **Auth — role assignment UI** — Admin Roles tab lists superadmins and school admins, adds an assignment tab for all seven roles, and shows localized role pills ([`AdminRolesTab.vue`](frontend/src/components/admin/AdminRolesTab.vue), [`userRoleDisplay.ts`](frontend/src/utils/userRoleDisplay.ts)); sidebar account footer displays the user’s role pill ([`AppSidebarNav.vue`](frontend/src/components/sidebar/AppSidebarNav.vue), [`useAppSidebar.ts`](frontend/src/composables/sidebar/useAppSidebar.ts)).
- **Frontend — lazy markdown** — `markdown-it` and KaTeX load on demand; route-aware preload and reactive `useRenderedMarkdown` ([`lazyMarkdown.ts`](frontend/src/composables/core/lazyMarkdown.ts), [`markdownRenderer.ts`](frontend/src/composables/core/markdownRenderer.ts), [`useRenderedMarkdown.ts`](frontend/src/composables/core/useRenderedMarkdown.ts)).
- **Frontend — lazy i18n** — Per-locale dynamic imports with English-copy locale codes ([`lazyLocaleLoaders.ts`](frontend/src/i18n/lazyLocaleLoaders.ts), [`generate-lazy-locale-loaders.js`](frontend/scripts/generate-lazy-locale-loaders.js)); locale label cache invalidation for diagram defaults ([`localeLabelCache.ts`](frontend/src/i18n/localeLabelCache.ts)).
- **Frontend — lazy Chart.js** — Admin trend charts load Chart.js on modal open ([`lazyChartJs.ts`](frontend/src/utils/lazyChartJs.ts), [`AdminTrendChartModal.vue`](frontend/src/components/admin/AdminTrendChartModal.vue)).
- **Ops — admin SMS alert gating** — `admin_sms_alerts_enabled()` disables admin-target SMS when `DEBUG=true`, `ENVIRONMENT` is test/staging/development, or `ADMIN_SMS_ALERTS_ENABLED=false` ([`critical_alert.py`](services/infrastructure/monitoring/critical_alert.py)); documented in [`env.example`](env.example).
- **Tests** — Vitest [`lazyMarkdown.spec.ts`](frontend/tests/lazyMarkdown.spec.ts), [`loadLocaleMessages.spec.ts`](frontend/tests/loadLocaleMessages.spec.ts).

### Changed

- **Auth — dependencies and checks** — `require_superadmin` / `require_school_admin` replace ambiguous admin/manager naming; `normalize_role()` used across routers, scripts, and Redis cache ([`dependencies.py`](routers/auth/dependencies.py), [`roles.py`](utils/auth/roles.py), [`roles.py` admin API](routers/auth/admin/roles.py)).
- **Frontend — bootstrap and bundle** — App bootstraps i18n from the signed-in user’s `uiLanguage`; Element Plus programmatic styles load lazily; diagram layout recalc listener deferred to first canvas mount ([`main.ts`](frontend/src/main.ts), [`notifications.ts`](frontend/src/composables/core/notifications.ts), [`diagramLayoutRecalcBootstrap.ts`](frontend/src/composables/core/diagramLayoutRecalcBootstrap.ts)).
- **Frontend — sidebar** — Nav icons migrated from Element Plus to Lucide; history panels loaded with `defineAsyncComponent` ([`AppSidebarNav.vue`](frontend/src/components/sidebar/AppSidebarNav.vue)).
- **Frontend — Vite build** — Element Plus split into `vendor-ep-core`, `vendor-ep-data`, and `vendor-ep-overlay` manual chunks; production sourcemaps opt-in via `SOURCEMAP=1`; bundle analyzer via `ANALYZE=1` ([`vite.config.ts`](frontend/vite.config.ts)).
- **Diagram — locale-aware labels** — Placeholder and concept-map root label sets build lazily from loaded locales only ([`constants.ts`](frontend/src/stores/diagram/constants.ts), [`diagramDefaultLabels.ts`](frontend/src/stores/diagram/diagramDefaultLabels.ts), [`conceptMapTopicRootEdge.ts`](frontend/src/utils/conceptMapTopicRootEdge.ts)).
- **i18n** — Role pill and admin role strings in [`sidebar.ts`](frontend/src/locales/messages/en/sidebar.ts) / [`admin.ts`](frontend/src/locales/messages/en/admin.ts) and Chinese bundles.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.20).

## [5.117.19] - 2026-05-27

### Fixed

- **MindMate — SSE idle-in-transaction timeout** — `/api/ai_assistant/stream` resolves org Dify credentials in a short-lived `AsyncSessionLocal()` instead of `Depends(get_async_db)`, so PostgreSQL no longer kills the connection during long Dify streams (`idle_in_transaction_session_timeout`, default 30s) and session cleanup no longer raises `IdleInTransactionSessionTimeout` after successful responses ([`sse_streaming.py`](routers/api/sse_streaming.py)).
- **Kitty — mobile hub persist init order** — `useKittyMobileHubPersist` runs after `connected` / `kittyDiagramDisplayTitle` computeds are defined, fixing a temporal-dead-zone ReferenceError on [`MobileKittyPage.vue`](frontend/src/pages/mobile/MobileKittyPage.vue).
- **Kitty — library snapshot ack** — Treat `library_snapshot_saved` as saved only when strictly `true` ([`kittyAgentInbound.ts`](frontend/src/composables/kitty/kittyAgentInbound.ts)).
- **Kitty — desktop voice command log i18n** — Pass vue-i18n params through a wrapper so interpolated labels render correctly ([`useKittyDesktopVoiceCommandLog.ts`](frontend/src/composables/kitty/useKittyDesktopVoiceCommandLog.ts)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.19).

## [5.117.18] - 2026-05-27

### Added

- **Kitty — cross-device diagram sync** — Mobile voice edits fan out `diagram_update` and `selection_update` SSE frames on the desktop wake channel ([`kitty_desktop_wake_fanout.py`](services/kitty/infra/desktop/kitty_desktop_wake_fanout.py)); desktop canvas applies them via [`useKittyDesktopRemoteSync.ts`](frontend/src/composables/kitty/useKittyDesktopRemoteSync.ts), [`useKittyDesktopDiagramUpdateBridge.ts`](frontend/src/composables/kitty/useKittyDesktopDiagramUpdateBridge.ts), [`kittySelectionApply.ts`](frontend/src/composables/kitty/kittySelectionApply.ts), and [`syncDiagramStoreFromVoiceContext.ts`](frontend/src/composables/kitty/syncDiagramStoreFromVoiceContext.ts); content fingerprints in [`kittyDiagramFingerprint.ts`](frontend/src/composables/kitty/kittyDiagramFingerprint.ts).
- **Kitty — desktop voice command log** — Floating panel above the mobile Kitty FAB shows recent phone voice commands over SSE ([`KittyDesktopVoiceCommandLog.vue`](frontend/src/components/kitty/KittyDesktopVoiceCommandLog.vue), [`useKittyDesktopVoiceCommandLog.ts`](frontend/src/composables/kitty/useKittyDesktopVoiceCommandLog.ts), [`kitty_voice_command_fanout.py`](services/kitty/infra/desktop/kitty_voice_command_fanout.py), [`kittyVoiceCommandLabels.ts`](frontend/src/composables/kitty/kittyVoiceCommandLabels.ts)).
- **Kitty — workflow trace** — Structured voice-to-diagram trace logging on backend ([`kitty_workflow_trace.py`](services/kitty/infra/control/kitty_workflow_trace.py), `KITTY_WORKFLOW_TRACE=0` to disable) and frontend ([`kittyWorkflowTrace.ts`](frontend/src/composables/kitty/kittyWorkflowTrace.ts), [`KittyDesktopWorkflowDebugLog.vue`](frontend/src/components/kitty/KittyDesktopWorkflowDebugLog.vue), [`useKittyDesktopWorkflowDebug.ts`](frontend/src/composables/kitty/useKittyDesktopWorkflowDebug.ts)).
- **Kitty — mobile hub library persist** — Debounced Pinia spec → Agent Hub persist after mobile voice edits ([`useKittyMobileHubPersist.ts`](frontend/src/composables/kitty/useKittyMobileHubPersist.ts)); mobile store hydration from library/bootstrap ([`hydrateMobileKittyFromLibrary.ts`](frontend/src/composables/kitty/hydrateMobileKittyFromLibrary.ts), [`hydrateMobileKittyStoreFromBootstrap.ts`](frontend/src/composables/kitty/hydrateMobileKittyStoreFromBootstrap.ts)).
- **Kitty — hub bridge sync** — Voice diagram mutations sync to Agent Hub when live spec is newer than the saved library row ([`hub_bridge.py`](services/kitty/diagram/hub_bridge.py), [`library_refresh.py`](services/kitty/context/library_refresh.py)).
- **Canvas — snapshot recall UX** — Loading animation and keyboard-accessible snapshot badges while a version is being restored ([`CanvasTopBar.vue`](frontend/src/components/canvas/CanvasTopBar.vue), [`useSnapshotHistory.ts`](frontend/src/composables/editor/useSnapshotHistory.ts)).
- **Diagram — brace map parent resolve** — Subparts attach under the correct part group, not under sibling subparts ([`braceMapParentResolve.ts`](frontend/src/stores/diagram/braceMapParentResolve.ts), [`braceMapOps.ts`](frontend/src/stores/diagram/braceMapOps.ts)).
- **Tests** — [`test_kitty_cross_device_sync.py`](tests/test_kitty_cross_device_sync.py), [`test_kitty_library_refresh.py`](tests/test_kitty_library_refresh.py); Vitest [`useKittyDesktopLiveSpecSync.spec.ts`](frontend/tests/useKittyDesktopLiveSpecSync.spec.ts), [`useKittyMobileHubPersist.spec.ts`](frontend/tests/useKittyMobileHubPersist.spec.ts), [`kittyVoiceCommandLabels.spec.ts`](frontend/tests/kittyVoiceCommandLabels.spec.ts), [`resolveKittySelectionNodeId.spec.ts`](frontend/tests/resolveKittySelectionNodeId.spec.ts), [`braceMapParentResolve.spec.ts`](frontend/tests/braceMapParentResolve.spec.ts).

### Changed

- **Kitty — command router** — Routes voice commands through hub sync, library refresh guards, selection fanout, and voice-command SSE labels ([`command_router.py`](services/kitty/routing/command_router.py), [`intent_parser.py`](services/kitty/routing/intent_parser.py), [`inbound.py`](services/kitty/ws/inbound.py)).
- **Kitty — mobile pairing & click wheel** — Improved library diagram pick, scope hydration, and child-node cycling ([`useMobileKittyPairing.ts`](frontend/src/composables/kitty/useMobileKittyPairing.ts), [`MobileKittyPage.vue`](frontend/src/pages/mobile/MobileKittyPage.vue), [`KittyIpodClickWheel.vue`](frontend/src/components/kitty/KittyIpodClickWheel.vue), [`useKittyClickWheel.ts`](frontend/src/composables/kitty/useKittyClickWheel.ts)).
- **Kitty — desktop live spec sync** — Slimmed composable; remote sync extracted to dedicated modules ([`useKittyDesktopLiveSpecSync.ts`](frontend/src/composables/kitty/useKittyDesktopLiveSpecSync.ts)).
- **Kitty — desktop action poll & wake SSE** — Handles `diagram_update`, `selection_update`, and `voice_command` SSE event types ([`useKittyDesktopActionPoll.ts`](frontend/src/composables/kitty/useKittyDesktopActionPoll.ts), [`createKittyDesktopWakeStream.ts`](frontend/src/composables/kitty/createKittyDesktopWakeStream.ts)).
- **Kitty — agent & context** — Expanded inbound message types, context messaging, and Omni refresh hooks ([`kittyAgentInbound.ts`](frontend/src/composables/kitty/kittyAgentInbound.ts), [`messaging.py`](services/kitty/context/messaging.py), [`hub_context.py`](services/kitty/context/hub_context.py)).
- **Canvas — library snapshots** — Snapshot list wiring and node-action snapshot hooks ([`useCanvasPageLibrarySnapshots.ts`](frontend/src/composables/canvasPage/useCanvasPageLibrarySnapshots.ts), [`useNodeActions.ts`](frontend/src/composables/editor/useNodeActions.ts), [`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue)).
- **Event bus** — New Kitty workflow and diagram sync events ([`useEventBus.ts`](frontend/src/composables/core/useEventBus.ts)).
- **i18n** — Voice command log and snapshot recall strings in [`canvas.ts`](frontend/src/locales/messages/en/canvas.ts) / [`common.ts`](frontend/src/locales/messages/en/common.ts) and Chinese bundles.
- **Docs** — [`env.example`](env.example) documents `KITTY_WORKFLOW_TRACE`.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.18).

## [5.117.17] - 2026-05-23

### Added

- **Markets — B2C subscriptions** — Alipay cycle-pay agreement sign/unsign, subscription lifecycle ([`subscription_service.py`](services/markets/subscription_service.py), [`alipay_agreement_sign.py`](services/markets/alipay_agreement_sign.py), [`alipay_agreement_unsign.py`](services/markets/alipay_agreement_unsign.py)); entitlement grants ([`entitlement_service.py`](services/markets/entitlement_service.py), [`access.py`](services/markets/access.py)); unified notify dispatch ([`alipay_notify_dispatch.py`](services/markets/alipay_notify_dispatch.py), [`agreement_notify_process.py`](services/markets/agreement_notify_process.py)); migration `rev_0035` adds `external_agreement_no`, `started_at`, `cancelled_at`, and subscription link columns. New API: `GET /api/markets/entitlements`, `GET /api/markets/subscriptions`, `POST /api/markets/subscriptions/intent`, `POST /api/markets/subscriptions/{id}/sign`, `POST /api/markets/subscriptions/{id}/cancel` ([`routers/features/markets/router.py`](routers/features/markets/router.py)).
- **Kitty — unified backend package** — Single product tree under [`services/kitty/`](services/kitty/) (`ws/`, `omni/`, `session/`, `routing/`, `diagram/`, `context/`, `content/`, `http/`, `infra/redis/`, `infra/desktop/`, `infra/control/`, `infra/scope/`, `infra/bootstrap/`, `infra/guards/`); FastAPI wiring in [`routers/features/kitty/`](routers/features/kitty/).
- **Kitty — mobile iPod click wheel** — [`KittyIpodClickWheel.vue`](frontend/src/components/kitty/KittyIpodClickWheel.vue) and [`useKittyClickWheel.ts`](frontend/src/composables/kitty/useKittyClickWheel.ts) cycle child nodes on mobile Kitty; haptic feedback via [`useDeviceVibration.ts`](frontend/src/composables/core/useDeviceVibration.ts).
- **Kitty — mobile diagram picker** — [`KittyMobileDiagramPickerDropdown.vue`](frontend/src/components/kitty/KittyMobileDiagramPickerDropdown.vue) and [`useKittyMobileLibraryDiagramSelect.ts`](frontend/src/composables/kitty/useKittyMobileLibraryDiagramSelect.ts) pick library diagrams from the mobile hub.
- **Kitty — mobile hub action bridge** — [`useKittyMobileHubActionBridge.ts`](frontend/src/composables/kitty/useKittyMobileHubActionBridge.ts) stashes canvas-only voice actions and routes to `/m/canvas` via [`kittyPendingCanvasAction.ts`](frontend/src/composables/kitty/kittyPendingCanvasAction.ts).
- **Kitty — frontend agent modules** — Split [`useKittyAgent.ts`](frontend/src/composables/kitty/useKittyAgent.ts) into [`kittyAgentActions.ts`](frontend/src/composables/kitty/kittyAgentActions.ts), [`kittyAgentAudioCodec.ts`](frontend/src/composables/kitty/kittyAgentAudioCodec.ts), [`kittyAgentDebug.ts`](frontend/src/composables/kitty/kittyAgentDebug.ts), [`kittyAgentInbound.ts`](frontend/src/composables/kitty/kittyAgentInbound.ts), [`kittyAgentTypes.ts`](frontend/src/composables/kitty/kittyAgentTypes.ts); desktop queue handlers in [`kittyDesktopActionHandlers.ts`](frontend/src/composables/kitty/kittyDesktopActionHandlers.ts); child resolution in [`kittyDiagramChildren.ts`](frontend/src/composables/kitty/kittyDiagramChildren.ts) and [`kittyAddNodeWithRecommendations.ts`](frontend/src/composables/kitty/kittyAddNodeWithRecommendations.ts); voice selection bus in [`useKittyVoiceSelectionBus.ts`](frontend/src/composables/kitty/useKittyVoiceSelectionBus.ts).
- **Kitty — unified desktop focus** — [`useKittyDesktopFocus.ts`](frontend/src/composables/kitty/useKittyDesktopFocus.ts) replaces separate hint/publish composables for mobile poll and desktop PUT.
- **Kitty — LLMOps manifest validation** — [`test_kitty_llmops_manifest.py`](tests/test_kitty_llmops_manifest.py) asserts every path in the admin architecture manifest exists on disk ([`llmops_manifest.py`](services/kitty/http/llmops_manifest.py)).
- **Tests** — [`test_markets_b2c_subscription.py`](tests/test_markets_b2c_subscription.py); Kitty coverage in [`test_kitty_omni_context_refresh.py`](tests/test_kitty_omni_context_refresh.py), [`test_kitty_paragraph_batch_apply.py`](tests/test_kitty_paragraph_batch_apply.py), [`test_kitty_scope_access.py`](tests/test_kitty_scope_access.py), [`test_kitty_session_event_bus.py`](tests/test_kitty_session_event_bus.py), [`test_kitty_voice_command_router.py`](tests/test_kitty_voice_command_router.py), [`test_kitty_voice_node_resolution.py`](tests/test_kitty_voice_node_resolution.py); Vitest [`kittyChildNodeResolution.spec.ts`](frontend/tests/kittyChildNodeResolution.spec.ts).

### Changed

- **Kitty — mobile UX** — [`MobileKittyPage.vue`](frontend/src/pages/mobile/MobileKittyPage.vue) redesigned around the click wheel; context card updates in [`KittyMobileDiagramContextCard.vue`](frontend/src/components/kitty/KittyMobileDiagramContextCard.vue); canvas/mobile pages wire hub bridge, focus, and live spec sync ([`MobileCanvasPage.vue`](frontend/src/pages/mobile/MobileCanvasPage.vue), [`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue)).
- **Kitty — desktop live spec sync** — [`useKittyDesktopLiveSpecSync.ts`](frontend/src/composables/kitty/useKittyDesktopLiveSpecSync.ts) expanded for mobile/desktop parity; desktop action poll refinements in [`useKittyDesktopActionPoll.ts`](frontend/src/composables/kitty/useKittyDesktopActionPoll.ts).
- **Kitty — LLMOps manifest** — Module paths updated for unified layout (`services/kitty/ws/`, `infra/redis/`, `infra/desktop/`, etc.).
- **Kitty — hub wiring** — Scope cleanup hook renamed to `configure_kitty_scope_cleanup` ([`services/agent_hub/scope_lifecycle.py`](services/agent_hub/scope_lifecycle.py)).
- **Kitty — context builders** — `buildKittyContextPreferStore` and `buildKittyChildren` replace `buildKittyVoice*` names ([`buildKittyDiagramContext.ts`](frontend/src/composables/kitty/buildKittyDiagramContext.ts)).
- **Kitty — Omni client** — Realtime context refresh helpers in [`clients/omni_client.py`](clients/omni_client.py).
- **Markets — Alipay notify** — Refactored one-time and agreement notify handling ([`notify_process.py`](services/markets/notify_process.py), [`alipay_client.py`](services/markets/alipay_client.py), [`alipay_common.py`](services/markets/alipay_common.py)).
- **Docs** — [`services/kitty/README.md`](services/kitty/README.md), [`services/agent_hub/README.md`](services/agent_hub/README.md), and [`env.example`](env.example) point at current Kitty module paths and Markets subscription env vars.
- **i18n** — Kitty mobile and MindMate strings in [`common.ts`](frontend/src/locales/messages/en/common.ts) / [`mindmate.ts`](frontend/src/locales/messages/en/mindmate.ts) and Chinese bundles.

### Removed

- **Kitty — Pipecat pipeline** — `FEATURE_KITTY_PIPECAT_PIPELINE`, `pipecat-ai` dependency, and `pipecat_kitty/` package removed; Omni realtime is the sole WS path.
- **Kitty — legacy packages** — `services/kitty_voice/`, `services/kitty_agent/`, `routers/features/voice/`, flat `services/kitty/kitty_*.py` modules, and standalone [`services/features/voice_agent.py`](services/features/voice_agent.py) / [`voice_agent_tools.py`](services/features/voice_agent_tools.py).
- **Kitty — deprecated frontend** — [`KittyAgentPanel.vue`](frontend/src/components/kitty/KittyAgentPanel.vue); composables `useKittyMobileLaneArmed`, `useKittyDesktopFocusHint`, `useKittyDesktopFocusPublish`.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.17).

## [5.117.16] - 2026-05-22

### Added

- **Kitty — mobile_active signal** — User-scoped Redis key `kitty:mobile_active:{user_id}` tracks diagram scopes with mobile-lane Kitty WebSocket sessions ([`kitty_mobile_active.py`](services/kitty/infra/desktop/kitty_mobile_active.py)); atomic mark/clear via `WATCH`/`MULTI`. New `GET /api/kitty/mobile_active` gates desktop action consumption.
- **Kitty — desktop wake SSE** — `GET /api/kitty/desktop_wake/stream` pushes instant `mobile_active` updates over EventSource (cookie auth) via Redis pub/sub on `kitty:desktop_wake:{user_id}` ([`kitty_desktop_wake_stream.py`](services/kitty/infra/desktop/kitty_desktop_wake_stream.py), [`kitty_desktop_wake_fanout.py`](services/kitty/infra/desktop/kitty_desktop_wake_fanout.py)); capped at 2 concurrent streams per user per worker.
- **Kitty — combined desktop pairing poll** — `GET /api/kitty/desktop_pairing` returns `mobile_active` plus optional long-poll action pop (`wait_sec` 0–30); legacy `GET /api/kitty/desktop_action/pop` gains the same `wait_sec` BLPOP support.
- **Kitty — desktop poll leader & wake hub** — [`kittyDesktopPollLeader.ts`](frontend/src/composables/kitty/kittyDesktopPollLeader.ts) elects one tab per browser profile via `BroadcastChannel`; [`createKittyDesktopWakeStream.ts`](frontend/src/composables/kitty/createKittyDesktopWakeStream.ts) and [`kittyDesktopMobileActiveHub.ts`](frontend/src/composables/kitty/kittyDesktopMobileActiveHub.ts) feed canvas pairing hints without per-tab REST churn; [`useKittyUserMobileActive.ts`](frontend/src/composables/kitty/useKittyUserMobileActive.ts) for mobile-side scope tracking.
- **MindMate — animated org avatars** — Admin avatar upload accepts animated GIFs (max 120 frames) alongside PNG/JPEG/WebP; canonical files are `avatar.png` or `avatar.gif` at 256×256 ([`organization_mindmate_branding.py`](routers/auth/admin/organization_mindmate_branding.py)); min input size 64×64, max decode 4096 px; superseded files cleaned up after DB commit.
- **Tests** — [`test_kitty_mobile_active.py`](tests/test_kitty_mobile_active.py) for mobile_active mark/clear, desktop poll gate, and wake fanout; [`test_organization_mindmate_avatar.py`](tests/test_organization_mindmate_avatar.py) for avatar processing (GIF, size, frame limits).

### Changed

- **Kitty — desktop action poll** — [`useKittyDesktopActionPoll.ts`](frontend/src/composables/kitty/useKittyDesktopActionPoll.ts) watches SSE while mobile Kitty is off (12s fallback poll), chains long-poll `desktop_pairing?wait_sec=25` while mobile is active, and only consumes the action queue when `mobile_active` is true.
- **Kitty — canvas & mobile pairing** — [`useCanvasKittyDesktopPairing.ts`](frontend/src/composables/kitty/useCanvasKittyDesktopPairing.ts) reads the shared mobile_active hub instead of per-scope `mobile_lane` polling; [`useMobileKittyPairing.ts`](frontend/src/composables/kitty/useMobileKittyPairing.ts) stops `desktop_focus` polling after WebSocket connect.
- **Kitty — package layout** — Single product tree under [`services/kitty/`](services/kitty/) (realtime subpackages `ws/`, `omni/`, `session/`, …; infra subpackages `redis/`, `desktop/`, `control/`, `scope/`, `bootstrap/`, `guards/`). Removed legacy `services/kitty_voice/`, `services/kitty_agent/`, and `routers/features/voice/` shims; Pipecat pipeline path removed.
- **Kitty — session teardown** — Desktop start clears `client_lane: mobile` and removes scope from `mobile_active`; refcount/sessionmeta drift metric documented in [`services/kitty/README.md`](services/kitty/README.md).
- **Admin — avatar upload UX** — [`AdminSchoolDifySettings.vue`](frontend/src/components/admin/AdminSchoolDifySettings.vue) uses `apiUpload`, `httpErrorDetail`, and new locale strings for too-small and too-many-frames errors.
- **CI** — Pylint scope includes [`organization_mindmate_branding.py`](routers/auth/admin/organization_mindmate_branding.py); pytest runs [`test_organization_mindmate_avatar.py`](tests/test_organization_mindmate_avatar.py); frontend job uses Node `latest`.
- **Docs** — [`README.md`](README.md) prerequisites point to latest Node/npm via [`docs/NODE_NVM_SETUP.md`](docs/NODE_NVM_SETUP.md); [`env.example`](env.example) notes `avatar.gif` path.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.16).

## [5.117.15] - 2026-05-20

### Added

- **Admin — per-school MindMate Dify** — Optional `dify_api_base_url` and `dify_api_key` on organizations (migration `rev_0032`); school detail modal Dify settings can set a school's Dify app or clear the override to use global `DIFY_API_*` env vars. Health probe via [`useSchoolDifyHealthProbe.ts`](frontend/src/composables/admin/useSchoolDifyHealthProbe.ts) and [`organization_dify.py`](routers/auth/admin/organization_dify.py). MindMate routes (`/api/ai_assistant/stream`, `/api/dify/*`) resolve credentials via [`services/dify/org_mindmate_client.py`](services/dify/org_mindmate_client.py). API keys masked in admin responses via [`utils/secrets_mask.py`](utils/secrets_mask.py).
- **MindMate — per-school branding** — Optional agent display name and avatar on organizations (migrations `rev_0033`, `rev_0034`; agent name capped at 10 characters). Admin avatar upload in [`organization_mindmate_branding.py`](routers/auth/admin/organization_mindmate_branding.py). Branding flows through login/session/register via [`org_profile.py`](routers/auth/org_profile.py) and surfaces in sidebar, welcome, messages, and mobile MindMate via [`useMindMateBranding.ts`](frontend/src/composables/mindmate/useMindMateBranding.ts) and [`MindmateAgentAvatar.vue`](frontend/src/components/panels/mindmate/MindmateAgentAvatar.vue).
- **Admin — Schools tab components** — Extracted [`AdminSchoolCreateDialog.vue`](frontend/src/components/admin/AdminSchoolCreateDialog.vue), [`AdminSchoolDifySettings.vue`](frontend/src/components/admin/AdminSchoolDifySettings.vue), [`AdminSchoolOrgGeneralTab.vue`](frontend/src/components/admin/AdminSchoolOrgGeneralTab.vue), [`AdminSchoolShareDialog.vue`](frontend/src/components/admin/AdminSchoolShareDialog.vue), and [`AdminSchoolTokenUsageTab.vue`](frontend/src/components/admin/AdminSchoolTokenUsageTab.vue); shared styling in [`admin-schools-swiss.css`](frontend/src/styles/admin-schools-swiss.css).
- **Invitation codes** — Shared helpers in [`frontend/src/utils/invitationCode.ts`](frontend/src/utils/invitationCode.ts) with Vitest coverage in [`frontend/tests/invitationCode.spec.ts`](frontend/tests/invitationCode.spec.ts).

### Changed

- **Admin — Schools tab** — Simplified create-school dialog to school name and invitation code only (Dify and branding remain in the school detail modal). Removed the tab intro note and list invitation-code column; added agent name and avatar columns. Invitation codes load lazily in the detail modal (skipped when opening via token usage); removed orphaned `admin.schoolsTabNote` locale keys.
- **i18n** — Admin, MindMate, sidebar, and canvas strings updated across locale bundles for school Dify and branding UI.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.15).

## [5.117.14] - 2026-05-18

### Changed

- **Canvas — AI model selector** — Row alignment and button metrics so stacked model chips and the ready-count label stay visually consistent ([`AIModelSelector.vue`](frontend/src/components/canvas/AIModelSelector.vue)).
- **Canvas — bottom controls** — Control strip aligns to the top on medium+ breakpoints ([`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue)).
- **Multi-flow map** — Cause/effect pill label wrap cap is shared via [`MULTI_FLOW_FLOW_NODE_LABEL_MAX_WIDTH`](frontend/src/composables/diagrams/layoutConfig.ts) in [`FlowNode.vue`](frontend/src/components/diagram/nodes/FlowNode.vue) and [`multiFlowMap.ts`](frontend/src/stores/specLoader/multiFlowMap.ts) so layout width matches wrapped labels; left/right topic–column gaps use the same horizontal spacing.
- **Diagram canvas — selection chrome** — Multi-flow selected nodes drop the solid border fallback and rely on glow only ([`diagramCanvas.css`](frontend/src/components/diagram/diagramCanvas.css)).
- **Concept map spec loader** — `isConceptMapSpec` accepts topic + `relationships` when concept lists are absent or empty if those arrays are not populated; safer handling when `concepts` is missing ([`conceptMap.ts`](frontend/src/stores/specLoader/conceptMap.ts)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.14).

## [5.117.13] - 2026-05-14

### Added

- **Canvas — translate diagram labels** — Authenticated streaming API for batch node-label translation via DashScope/Qwen ([`routers/api/canvas_translate.py`](routers/api/canvas_translate.py)), Pydantic models ([`models/requests/requests_canvas_translate.py`](models/requests/requests_canvas_translate.py)), router registration ([`routers/api/__init__.py`](routers/api/__init__.py)). Canvas UI: [`CanvasTranslateProgressBanner.vue`](frontend/src/components/canvas/CanvasTranslateProgressBanner.vue), [`diagramTranslateUi.ts`](frontend/src/stores/diagramTranslateUi.ts), [`diagramTranslateStream.ts`](frontend/src/utils/diagramTranslateStream.ts), [`translateLanguages.ts`](frontend/src/utils/translateLanguages.ts), wiring in [`useCanvasToolbarApps.ts`](frontend/src/composables/canvasToolbar/useCanvasToolbarApps.ts), [`CanvasToolbarMoreAppsDropdown.vue`](frontend/src/components/canvas/CanvasToolbarMoreAppsDropdown.vue), [`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue); i18n strings added across per-locale canvas bundles (English keys in [`frontend/src/locales/messages/en/canvas.ts`](frontend/src/locales/messages/en/canvas.ts)).

### Changed

- **Markdown / KaTeX** — Diagram and panel Markdown pipeline adjustments ([`diagramMarkdownPipeline.ts`](frontend/src/composables/core/diagramMarkdownPipeline.ts), [`markdownKatexSanitize.ts`](frontend/src/composables/core/markdownKatexSanitize.ts), [`useMarkdown.ts`](frontend/src/composables/core/useMarkdown.ts)).
- **Panels & canvas chrome** — MindMate, DebateVerse, Ask Once, Share/Export, and update log surfaces updated for Markdown rendering ([`MindmatePanel.vue`](frontend/src/components/panels/MindmatePanel.vue), [`MessageBubble.vue`](frontend/src/components/panels/mindmate/MessageBubble.vue), [`mindmate.css`](frontend/src/components/panels/mindmate/mindmate.css), [`DebateMessage.vue`](frontend/src/components/debateverse/DebateMessage.vue), [`AskOncePanel.vue`](frontend/src/components/askonce/AskOncePanel.vue), [`ShareExportModal.vue`](frontend/src/components/panels/ShareExportModal.vue), [`UpdateLogModal.vue`](frontend/src/components/auth/UpdateLogModal.vue)); simplified [`CanvasToolbar.vue`](frontend/src/components/canvas/CanvasToolbar.vue).
- **Language settings** — [`LanguageSettingsModal.vue`](frontend/src/components/settings/LanguageSettingsModal.vue) UX updates.
- **Sidebar** — Account footer rework and minor [`AppSidebar.vue`](frontend/src/components/sidebar/AppSidebar.vue) tweaks ([`AppSidebarAccountFooter.vue`](frontend/src/components/sidebar/AppSidebarAccountFooter.vue)).
- **Backend — LLM & infra** — DashScope/client exports ([`clients/llm/dashscope.py`](clients/llm/dashscope.py), [`clients/llm/__init__.py`](clients/llm/__init__.py)), [`config/llm_config.py`](config/llm_config.py), helpers in [`services/llm/llm_utils.py`](services/llm/llm_utils.py); token buffer ([`redis_token_buffer.py`](services/redis/redis_token_buffer.py)), env/load-balancer helpers ([`env_manager.py`](services/infrastructure/utils/env_manager.py), [`load_balancer.py`](services/infrastructure/utils/load_balancer.py), [`client_manager.py`](services/infrastructure/utils/client_manager.py)); [`models/domain/env_settings.py`](models/domain/env_settings.py) and [`env.example`](env.example).
- **Ask Once / DebateVerse** — Small routing and service tweaks ([`routers/features/askonce.py`](routers/features/askonce.py), [`routers/features/debateverse.py`](routers/features/debateverse.py), [`debateverse_service.py`](services/features/debateverse_service.py)).
- **Other** — [`useMindMate.ts`](frontend/src/composables/mindmate/useMindMate.ts); [`agents/mind_maps/web_content_mind_map_agent.py`](agents/mind_maps/web_content_mind_map_agent.py); [`document_processing.py`](services/knowledge/document_processing.py).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.13).

## [5.117.12] - 2026-05-14

### Added

- **Kitty voice — `services/kitty_voice`** — Realtime WebSocket handling, HTTP handlers, hub/diagram bridge, intent catalog, multimodal/Omni helpers, optional Pipecat pipeline path, WS guards, and related tests. Diagram command modules previously under [`routers/features/voice/`](routers/features/voice/) now live under [`services/kitty/voice/diagram/`](services/kitty/voice/diagram/); [`routers/features/voice/kitty_routes.py`](routers/features/voice/kitty_routes.py) is a thin entry layer.
- **Voice agent tools** — [`services/features/voice_agent_tools.py`](services/features/voice_agent_tools.py) alongside refactors in [`services/features/voice_agent.py`](services/features/voice_agent.py).
- **Admin — Kitty LLMOps** — [`GET /admin/kitty-llmops/architecture`](routers/auth/admin/kitty_llmops.py) (admin-only) returns the Kitty module manifest; UI tab [`AdminKittyLlmopsTab.vue`](frontend/src/components/admin/AdminKittyLlmopsTab.vue) on Admin and Canvas pages.
- **Concept map — Cmap import & layout** — Expanded [`cmapImport.ts`](frontend/src/utils/cmapImport.ts), [`cmapLayoutExtract.ts`](frontend/src/utils/cmapLayoutExtract.ts), [`conceptMap.ts`](frontend/src/stores/specLoader/conceptMap.ts) loader, [`javaSerializationParse.ts`](frontend/src/utils/javaSerializationParse.ts); new helpers [`cmapGraphExtract.ts`](frontend/src/utils/cmapGraphExtract.ts), [`cmapLayoutOverlap.ts`](frontend/src/utils/cmapLayoutOverlap.ts), [`cmapConceptPillEstimate.ts`](frontend/src/utils/cmapConceptPillEstimate.ts), [`cmapModifiedUtf8.ts`](frontend/src/utils/cmapModifiedUtf8.ts); composable [`useConceptMapCmapMeasuredLayoutRelax.ts`](frontend/src/composables/diagramCanvas/useConceptMapCmapMeasuredLayoutRelax.ts); Vitest coverage for layout/parse utilities.
- **Dependencies** — `pipecat-ai[websocket]>=1.1.0` in [`requirements.txt`](requirements.txt).
- **Agent hub** — [`services/agent_hub/README.md`](services/agent_hub/README.md).

### Changed

- **Feature flags** — [`FEATURE_KITTY_PIPECAT_PIPELINE`](config/features_config.py) (optional Pipecat `PipelineTask` path for Kitty WS JSON); documented in [`env.example`](env.example).
- **Router registration** — Debug log when Kitty Agent routes load via [`routers/features/voice/routes`](routers/features/voice/routes.py) ([`routers/register.py`](routers/register.py)).
- **Kitty / desktop** — Pairing and live-spec sync composables ([`useCanvasKittyDesktopPairing.ts`](frontend/src/composables/kitty/useCanvasKittyDesktopPairing.ts), [`useKittyDesktopLiveSpecSync.ts`](frontend/src/composables/kitty/useKittyDesktopLiveSpecSync.ts)); session/desktop Redis and action queue touch-ups; [`ws_metrics.py`](services/infrastructure/monitoring/ws_metrics.py) for WebSocket observability.
- **Canvas & import** — [`DiagramCanvas.vue`](frontend/src/components/diagram/DiagramCanvas.vue), [`useDiagramCanvasFit.ts`](frontend/src/composables/diagramCanvas/useDiagramCanvasFit.ts), [`useDiagramImport.ts`](frontend/src/composables/editor/useDiagramImport.ts), [`specIO.ts`](frontend/src/stores/diagram/specIO.ts), [`collabPalette.ts`](frontend/src/shared/collabPalette.ts); Cmap folder analyzer and locale materialization script updates.
- **i18n** — [`frontend/src/i18n/index.ts`](frontend/src/i18n/index.ts) and regenerated per-locale message bundles from English ([`frontend/scripts/materialize-locale-bundles-from-en.ts`](frontend/scripts/materialize-locale-bundles-from-en.ts)).
- **Voice package wiring** — [`routers/features/voice/__init__.py`](routers/features/voice/__init__.py), [`commands.py`](routers/features/voice/commands.py), [`state.py`](routers/features/voice/state.py), paragraph/CQRS helpers; [`routers/auth/admin/__init__.py`](routers/auth/admin/__init__.py) includes the LLMOps router.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.12).

## [5.117.11] - 2026-05-12

### Changed

- **Diagram canvas — typography-aware layout** — Bubble, multi-flow, tree, brace, and flow maps use each node’s `style` (font size, weight, family) in layout measurements instead of only fixed theme defaults. Bubble map topic and attribute radii derive from text and typography rather than stale DOM boxes, avoiding circles that fail to grow with larger fonts.
- **Diagram store** — `loadFromSpec` can merge prior node styles on structural reloads (`mergePreviousNodeStyles`). `updateNode` deep-merges `style` and, for typography-only toolbar edits, clears cached dimensions and bumps the appropriate layout triggers (including multi-flow recalc, bubble/circle/tree, brace, flow, and double-bubble relayout).
- **Double bubble map** — Measurement hints and relayout requests keep capsule sizes aligned with label typography after font changes.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.11).

## [5.117.10] - 2026-05-11

### Added

- **Kitty Agent — access control** — WebSocket connections require `feature_kitty_agent` org/user access; denied clients close with code **4003** ([`routers/features/voice/kitty_routes.py`](routers/features/voice/kitty_routes.py)).

### Changed

- **API — feature flags** — `GET /config/feature-flags` field **`feature_kitty_agent`** follows **`FEATURE_KITTY_AGENT`** and `user_has_feature_access` for signed-in users (anonymous callers see the env flag only) ([`routers/api/config.py`](routers/api/config.py)).
- **Kitty HTTP helpers** — Bootstrap, desktop action pop, desktop focus get/put, mobile lane hint, and session cleanup return empty or no-op payloads when the user lacks Kitty access or the WS feature is off ([`routers/features/voice/kitty_routes.py`](routers/features/voice/kitty_routes.py)).
- **Mobile canvas** — Removed the extra **MindGraph** title bar and Kitty shortcut; adjusted node palette top offset for the slimmer chrome ([`frontend/src/pages/mobile/MobileCanvasPage.vue`](frontend/src/pages/mobile/MobileCanvasPage.vue)).
- **Mobile Kitty** — Diagram context card renders only when the Kitty server/feature path is enabled ([`frontend/src/pages/mobile/MobileKittyPage.vue`](frontend/src/pages/mobile/MobileKittyPage.vue)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.10).

## [5.117.9] - 2026-05-11

### Added

- **MindMate / Bayi — Dify `user` from SSO UUID** — When `AUTH_MODE=bayi` and `users.phone` holds a Bayi vendor `userId` that parses as a UUID (from `/loginByXz` token payload), MindMate uses that canonical UUID string as the Dify API `user` instead of `mg_user_<pk>`. Bayi passkey accounts (`phone` not a UUID) keep `mg_user_<pk>`. Shared helper [`utils/dify_mindmate_user_id.py`](utils/dify_mindmate_user_id.py); frontend mirror [`frontend/src/utils/mindmateDifyUserId.ts`](frontend/src/utils/mindmateDifyUserId.ts); tests [`tests/utils/test_dify_mindmate_user_id.py`](tests/utils/test_dify_mindmate_user_id.py).

### Changed

- **API** — [`routers/api/dify_conversations.py`](routers/api/dify_conversations.py) uses `mindmate_dify_user_id`. [`routers/api/sse_streaming.py`](routers/api/sse_streaming.py) passes the server-computed Dify `user` when the caller is authenticated (aligned with the REST helpers and avoids trusting the client `user_id` alone).
- **Frontend** — [`frontend/src/composables/mindmate/useMindMate.ts`](frontend/src/composables/mindmate/useMindMate.ts) derives MindMate `userId` with the same Bayi UUID rule and watches `mode` / `phone`.
- **Configuration** — [`env.example`](env.example): brief note under MindMate Dify settings.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.9).

## [5.117.8] - 2026-05-11

### Added

- **Auth — registration kill switch** — `REGISTRATION_ENABLED` (default `true`) in [`utils/auth/config.py`](utils/auth/config.py), [`models/domain/env_settings.py`](models/domain/env_settings.py), documented in [`env.example`](env.example). Shared guard [`utils/auth/registration_gate.py`](utils/auth/registration_gate.py) returns HTTP 403 with localized `registration_disabled` when signup is off.
- **Public API** — `GET /api/auth/mode` includes `registration_enabled` ([`routers/auth/public.py`](routers/auth/public.py)).

### Changed

- **Registration & OTP** — Captcha invite, SMS, overseas email, quick-register, and email/SMS flows with `purpose=register` (including peek `/sms/verify` and `/email/verify`) honor the gate ([`routers/auth/registration.py`](routers/auth/registration.py), [`sms.py`](routers/auth/sms.py), [`email.py`](routers/auth/email.py), [`registration_overseas.py`](routers/auth/registration_overseas.py), [`quick_register.py`](routers/auth/quick_register.py)). Per-mode Bayi blocks on those paths are replaced by the unified flag while the env allows turning signup off everywhere.
- **Session** — `/me` includes organization `display_name` only when `AUTH_MODE=bayi` ([`routers/auth/session.py`](routers/auth/session.py)).
- **Frontend** — `registrationEnabled` from the mode endpoint ([`frontend/src/stores/auth.ts`](frontend/src/stores/auth.ts)); login modal hides the register tab when signup is disabled ([`LoginModal.vue`](frontend/src/components/auth/LoginModal.vue), [`useLoginModal.ts`](frontend/src/composables/auth/useLoginModal.ts)); auth page drops quick-register tokens from the URL when disabled ([`AuthPage.vue`](frontend/src/pages/AuthPage.vue)); Bayi session expiry sends users to `/auth` with `redirect` ([`auth.ts`](frontend/src/stores/auth.ts)); navigation guard passes the attempted path into the expired handler ([`frontend/src/router/index.ts`](frontend/src/router/index.ts)); `requireAuth` redirects to the given URL or `/auth`.
- **i18n** — Bundled catalog updates including `registration_disabled` ([`models/domain/message_catalog/bundled_messages.py`](models/domain/message_catalog/bundled_messages.py)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.8).

## [5.117.7] - 2026-05-10

### Added

- **Database — PostgreSQL extensions (Alembic)** — Migration [`alembic/versions/rev_0031_postgresql_extensions.py`](alembic/versions/rev_0031_postgresql_extensions.py): idempotent `CREATE EXTENSION IF NOT EXISTS` for `pg_stat_statements` and `pg_trgm`, each in a savepoint so privilege failures do not abort the migration.

### Changed

- **Voice / Omni realtime — barge-in** — When forwarding user microphone audio, interrupt the assistant before appending PCM ([`clients/omni_client.py`](clients/omni_client.py): `interrupt_assistant_for_user_speech` on `OmniRealtimeClient`).
- **Database — startup extension bootstrap** — [`config/database.py`](config/database.py) `_ensure_pg_extensions` matches revision 0031: one connection with nested transactions; `ProgrammingError` is warned and skipped.
- **Kitty mobile — mic UX** — Tap-to-toggle microphone and Space to toggle when the focused target does not reserve Space; cancel an in-flight start if the user taps again during a slow permission prompt ([`frontend/src/pages/mobile/MobileKittyPage.vue`](frontend/src/pages/mobile/MobileKittyPage.vue)).
- **Kitty agent — duplex audio** — While user voice capture is active, suppress assistant `text_chunk` / `audio_chunk`, clear queued playback, and keep state in **`listening`** where appropriate ([`frontend/src/composables/kitty/useKittyAgent.ts`](frontend/src/composables/kitty/useKittyAgent.ts)).

### Frontend i18n

- **Locales** — Mic accessibility strings renamed to toggle semantics (`mobile.kittyMicToggleTitle`, `mobile.kittyMicToggleAria`) ([`frontend/src/locales/messages/en/common.ts`](frontend/src/locales/messages/en/common.ts), [`zh/common.ts`](frontend/src/locales/messages/zh/common.ts)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.7).

## [5.117.6] - 2026-05-08

### Added

- **Kitty — mobile ↔ desktop canvas** — Redis FIFO queue for **`open_canvas`** actions from mobile Kitty to the desktop SPA ([`services/kitty/kitty_desktop_action_queue.py`](services/kitty/kitty_desktop_action_queue.py), [`services/kitty/kitty_redis_keys.py`](services/kitty/kitty_redis_keys.py)); long-poll client composable ([`frontend/src/composables/kitty/useKittyDesktopActionPoll.ts`](frontend/src/composables/kitty/useKittyDesktopActionPoll.ts)); route seed handoff for canvas loads ([`frontend/src/composables/canvasPage/applyCanvasKittySeedFromRoute.ts`](frontend/src/composables/canvasPage/applyCanvasKittySeedFromRoute.ts)); wiring in [`App.vue`](frontend/src/App.vue), [`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue), [`MobileCanvasPage.vue`](frontend/src/pages/mobile/MobileCanvasPage.vue), [`MobileKittyPage.vue`](frontend/src/pages/mobile/MobileKittyPage.vue), [`useMobileKittyPairing.ts`](frontend/src/composables/kitty/useMobileKittyPairing.ts).
- **Kitty — diagram vocabulary (voice)** — canonical diagram slugs and EN/ZH aliases aligned with the SPA ([`services/kitty/kitty_diagram_vocabulary.py`](services/kitty/kitty_diagram_vocabulary.py)); used when coercing desktop-open payloads.
- **Kitty — diagram review annotations** — LLM-assisted pass to flag nodes that need edits with reasons, resolved to Vue Flow node ids ([`services/kitty/voice/diagram/review_annotate.py`](services/kitty/voice/diagram/review_annotate.py)); client event bridge and mobile context card ([`frontend/src/composables/kitty/useKittyDiagramReviewAnnotationBus.ts`](frontend/src/composables/kitty/useKittyDiagramReviewAnnotationBus.ts), [`frontend/src/components/kitty/KittyMobileDiagramContextCard.vue`](frontend/src/components/kitty/KittyMobileDiagramContextCard.vue)).

### Changed

- **Voice / Kitty messaging** — command handling, websocket messaging, Kitty routes, and voice agent orchestration updates ([`routers/features/voice/commands.py`](routers/features/voice/commands.py), [`routers/features/voice/messaging.py`](routers/features/voice/messaging.py), [`routers/features/voice/kitty_routes.py`](routers/features/voice/kitty_routes.py), [`services/features/voice_agent.py`](services/features/voice_agent.py)).
- **Canvas & diagram store** — voice-driven diagram mutations expanded ([`frontend/src/composables/editor/diagramVoiceMutations.ts`](frontend/src/composables/editor/diagramVoiceMutations.ts)); diagram store/spec/types for Kitty-driven seeding and context ([`frontend/src/stores/diagram.ts`](frontend/src/stores/diagram.ts), [`specIO.ts`](frontend/src/stores/diagram/specIO.ts), [`types.ts`](frontend/src/stores/diagram/types.ts)).
- **Event bus & composables** — [`frontend/src/composables/core/useEventBus.ts`](frontend/src/composables/core/useEventBus.ts), [`useKittyAgent.ts`](frontend/src/composables/kitty/useKittyAgent.ts), [`useKittyMobileDebugBus.ts`](frontend/src/composables/kitty/useKittyMobileDebugBus.ts), [`frontend/src/composables/index.ts`](frontend/src/composables/index.ts).
- **UI & styling** — diagram canvas overlay styles ([`frontend/src/components/diagram/diagramCanvas.css`](frontend/src/components/diagram/diagramCanvas.css)); mascot tweaks ([`KittyBlackCatMascot.vue`](frontend/src/components/kitty/KittyBlackCatMascot.vue), [`frontend/src/utils/mascot/blackCat.ts`](frontend/src/utils/mascot/blackCat.ts)); [`frontend/src/components.d.ts`](frontend/src/components.d.ts).

### Frontend i18n

- **Locales** — new common strings (`en`, `zh`) ([`frontend/src/locales/messages/en/common.ts`](frontend/src/locales/messages/en/common.ts), [`zh/common.ts`](frontend/src/locales/messages/zh/common.ts)).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.6).

## [5.117.5] - 2026-05-08

### Added

- **Bayi passkey** — dedicated route and WebAuthn-oriented helpers ([`frontend/src/pages/BayiPasskeyPage.vue`](frontend/src/pages/BayiPasskeyPage.vue), [`utils/auth/passkey_utils.py`](utils/auth/passkey_utils.py)); router and auth-store wiring ([`frontend/src/router/index.ts`](frontend/src/router/index.ts), [`frontend/src/stores/auth.ts`](frontend/src/stores/auth.ts), [`frontend/src/pages/index.ts`](frontend/src/pages/index.ts)).
- **Database** — Alembic migrations: widen `users.phone` for Bayi SSO user UUIDs ([`alembic/versions/rev_0029_widen_users_phone_bayi_uuid.py`](alembic/versions/rev_0029_widen_users_phone_bayi_uuid.py)); set Beijing Bayi school org `display_name` for org id 5 ([`alembic/versions/rev_0030_bayi_org_id5_display_name.py`](alembic/versions/rev_0030_bayi_org_id5_display_name.py)).
- **Bundled tiktoken** — additional encoding artifact under [`resources/tiktoken_encodings/`](resources/tiktoken_encodings/) alongside `cl100k_base.tiktoken` for offline-friendly tokenizer cache layout.

### Removed

- **Demo / legacy access paths** — demo login UI ([`frontend/src/pages/DemoLoginPage.vue`](frontend/src/pages/DemoLoginPage.vue)), demo mode and generic IP-whitelist utilities ([`utils/auth/demo_mode.py`](utils/auth/demo_mode.py), [`utils/auth/ip_whitelist.py`](utils/auth/ip_whitelist.py)), Redis Bayi whitelist service ([`services/redis/redis_bayi_whitelist.py`](services/redis/redis_bayi_whitelist.py)), admin Bayi router module ([`routers/auth/admin/bayi.py`](routers/auth/admin/bayi.py)).

### Changed

- **Auth & roles** — login, registration, SMS/email flows, helpers, overseas registration, password and quick-register touchpoints ([`routers/auth/`](routers/auth/)); admin role APIs ([`routers/auth/admin/roles.py`](routers/auth/admin/roles.py)); authentication and role utilities ([`utils/auth/`](utils/auth/)); session and Redis keys ([`services/redis/session/redis_session_manager.py`](services/redis/session/redis_session_manager.py), [`services/redis/keys.py`](services/redis/keys.py)); middleware and SPA handling ([`services/infrastructure/http/middleware.py`](services/infrastructure/http/middleware.py), [`services/infrastructure/utils/spa_handler.py`](services/infrastructure/utils/spa_handler.py)); geo/VPN and CN email-login enforcement ([`services/auth/vpn_geo_enforcement.py`](services/auth/vpn_geo_enforcement.py), [`services/auth/email_login_cn_api_geo.py`](services/auth/email_login_cn_api_geo.py)); models and request DTOs ([`models/domain/auth.py`](models/domain/auth.py), [`models/domain/env_settings.py`](models/domain/env_settings.py), [`models/requests/requests_auth.py`](models/requests/requests_auth.py), [`models/__init__.py`](models/__init__.py), [`models/requests/__init__.py`](models/requests/__init__.py)).
- **Core routes** — page registration and Vue SPA integration ([`routers/core/pages.py`](routers/core/pages.py), [`routers/core/vue_spa.py`](routers/core/vue_spa.py)).
- **Admin UI & i18n** — [`AdminRolesTab.vue`](frontend/src/components/admin/AdminRolesTab.vue); admin and common message bundles across locales ([`frontend/src/locales/messages/`](frontend/src/locales/messages/)); [`frontend/scripts/split-locale-bundles.ts`](frontend/scripts/split-locale-bundles.ts).
- **Config & ops** — [`env.example`](env.example), [`config/database.py`](config/database.py), [`docs/QDRANT_SETUP.md`](docs/QDRANT_SETUP.md), [`scripts/setup/update_qdrant_server.py`](scripts/setup/update_qdrant_server.py), [`scripts/setup/setup.py`](scripts/setup/setup.py), [`scripts/setup/mindgraph.service.template`](scripts/setup/mindgraph.service.template), [`scripts/db/check_admin_status.py`](scripts/db/check_admin_status.py), [`services/admin/sqlite_merge_service.py`](services/admin/sqlite_merge_service.py), lifespan DB integration trimming ([`services/infrastructure/lifecycle/lifespan_db_integration.py`](services/infrastructure/lifecycle/lifespan_db_integration.py)); [`pyproject.toml`](pyproject.toml) tidy.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.5).

## [5.117.4] - 2026-05-07

### Changed

- **Locales** — wide refresh of [`frontend/src/locales/messages/`](frontend/src/locales/messages/) bundles (key alignment with English reference); [`frontend/scripts/sync-messages-keys-from-reference.ts`](frontend/scripts/sync-messages-keys-from-reference.ts); server message catalog and locale plumbing ([`models/domain/message_catalog/`](models/domain/message_catalog/), [`models/domain/api_locale.py`](models/domain/api_locale.py)).
- **Online collab / workshop** — coordinated updates across [`services/online_collab/`](services/online_collab/) (Redis locks, scripts, health, live-spec merge/flush, snapshots, WS editor hash/merge/rate limits, join/resume tokens, lifecycle/cleanup); workshop REST and WebSocket layers ([`routers/api/workshop_ws_handlers_update.py`](routers/api/workshop_ws_handlers_update.py), [`workshop_ws_handlers_update_validate.py`](routers/api/workshop_ws_handlers_update_validate.py), [`workshop_ws_update_schema.py`](routers/api/workshop_ws_update_schema.py), [`diagrams_workshop_routes.py`](routers/api/diagrams_workshop_routes.py), [`diagrams.py`](routers/api/diagrams.py)); WebSocket helpers ([`utils/ws_context.py`](utils/ws_context.py), [`ws_session_registry.py`](utils/ws_session_registry.py), [`collab_ws_origin.py`](utils/collab_ws_origin.py)); [`services/features/ws_pg_notify_fanout.py`](services/features/ws_pg_notify_fanout.py), [`services/infrastructure/ws/redis_collab_conn_cap.py`](services/infrastructure/ws/redis_collab_conn_cap.py), lifespan integration; [`config/database.py`](config/database.py); [`loadtests/collab/locustfile.py`](loadtests/collab/locustfile.py) and collab scripts under [`scripts/`](scripts/).
- **Canvas & mobile** — collab UI ([`CanvasCollabOverlay.vue`](frontend/src/components/canvas/CanvasCollabOverlay.vue), [`OnlineCollabModal.vue`](frontend/src/components/canvas/OnlineCollabModal.vue)), diagram diff/zoom/styles ([`diagramDiff.ts`](frontend/src/composables/canvasPage/diagramDiff.ts), [`diagramCanvasZoomPaneStyles.ts`](frontend/src/composables/diagramCanvas/diagramCanvasZoomPaneStyles.ts), [`diagramCanvas.css`](frontend/src/components/diagram/diagramCanvas.css)), workshop composables ([`useCollabSyncVersion.ts`](frontend/src/composables/workshop/useCollabSyncVersion.ts), [`useWorkshop.ts`](frontend/src/composables/workshop/useWorkshop.ts), [`useWorkshopMessageHandlers.ts`](frontend/src/composables/workshop/useWorkshopMessageHandlers.ts), [`useWorkshopPresence.ts`](frontend/src/composables/workshop/useWorkshopPresence.ts)); canvas pages ([`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue), mobile canvas/home/kitty); panels and gallery ([`NodePalettePanel.vue`](frontend/src/components/panels/NodePalettePanel.vue), [`RootConceptModal.vue`](frontend/src/components/panels/RootConceptModal.vue), [`DiscoveryGallery.vue`](frontend/src/components/mindgraph/DiscoveryGallery.vue), [`DiagramHistory.vue`](frontend/src/components/sidebar/DiagramHistory.vue)); editor/diagram operations, labels, voice mutations, toolbar apps, mounted handlers, collab indicators; [`frontend/src/stores/diagram/specIO.ts`](frontend/src/stores/diagram/specIO.ts).
- **Kitty** — UI and composables ([`KittyAgentPanel.vue`](frontend/src/components/kitty/KittyAgentPanel.vue), [`KittyCanvasAnchor.vue`](frontend/src/components/kitty/KittyCanvasAnchor.vue), pairing/focus/mobile helpers under [`frontend/src/composables/kitty/`](frontend/src/composables/kitty/)); [`services/kitty/kitty_session_redis.py`](services/kitty/kitty_session_redis.py).
- **Agents** — inline concept-map recommendations and palette context ([`agents/inline_recommendations/`](agents/inline_recommendations/), [`agents/node_palette/base_palette_generator.py`](agents/node_palette/base_palette_generator.py), [`prompts/node_palette.py`](prompts/node_palette.py)).
- **Live translation & content** — follow-up in [`routers/api/live_translate_ws.py`](routers/api/live_translate_ws.py), [`services/features/live_translate_bridge.py`](services/features/live_translate_bridge.py), [`routers/api/web_content_generation.py`](routers/api/web_content_generation.py).
- **Agent hub** — [`services/agent_hub/scope_lifecycle.py`](services/agent_hub/scope_lifecycle.py), [`services/agent_hub/snapshot.py`](services/agent_hub/snapshot.py).
- **Tooling** — Pylint [`ignore-paths`](pyproject.toml) adds generated [`models/domain/message_catalog/bundled_messages.py`](models/domain/message_catalog/bundled_messages.py); [`services/infrastructure/process/server_launcher.py`](services/infrastructure/process/server_launcher.py) and related lifespan tweaks.

### Tests

- Backend workshop/collab/live-spec/WS fanout tests updated under [`tests/`](tests/) for the above behavior.
- Frontend Vitest: [`useCollabOutboundQueue.spec.ts`](frontend/tests/useCollabOutboundQueue.spec.ts), [`useCollabSyncVersion.spec.ts`](frontend/tests/useCollabSyncVersion.spec.ts), [`useWorkshopHeartbeat.spec.ts`](frontend/tests/useWorkshopHeartbeat.spec.ts), [`useWorkshopReconnect.spec.ts`](frontend/tests/useWorkshopReconnect.spec.ts), [`diagramNodeToVueFlowNode.spec.ts`](frontend/tests/diagramNodeToVueFlowNode.spec.ts).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.4).

## [5.117.3] - 2026-05-07

### Added

- **Concept map — CmapTools `.cmap` import** — client-side ZIP + Java serialization string extraction (`TC_STRING`), IHMC-oriented heuristics for topic / concepts / relationships, optional graphical layout (`_layout_positions_by_label`), dev script `analyze-cmap-folder`; wired through landing import (`.mg,.cmap`), session storage handoff, Vitest coverage ([`frontend/src/utils/cmapImport.ts`](frontend/src/utils/cmapImport.ts), [`cmapLabels.ts`](frontend/src/utils/cmapLabels.ts), [`cmapLayoutExtract.ts`](frontend/src/utils/cmapLayoutExtract.ts), [`javaSerializationParse.ts`](frontend/src/utils/javaSerializationParse.ts), [`useDiagramImport.ts`](frontend/src/composables/editor/useDiagramImport.ts), [`frontend/scripts/analyze-cmap-folder.ts`](frontend/scripts/analyze-cmap-folder.ts), tests under [`frontend/tests/`](frontend/tests)).

### Changed

- **`frontend/src/stores/specLoader/conceptMap.ts`** — honor imported per-label positions; polar fallback ring uses overlap-aware radius; concept-map connections set default `arrowheadDirection` from node centers.
- **Live translation** — default WebSocket target language **English** on server and client; translation target follows the explicit store selection (removed “auto” source-derived flip); realtime model resolves from **`config.QWEN_LIVE_TRANSLATE_MODEL`** ([`live_translate_ws.py`](routers/api/live_translate_ws.py), [`live_translate_bridge.py`](services/features/live_translate_bridge.py), [`liveTranslation.ts`](frontend/src/stores/liveTranslation.ts)).
- **Mobile Kitty hub** — home card and **`MobileKitty`** route respect **`FEATURE_KITTY_AGENT`** after flags fetch ([`MobileHomePage.vue`](frontend/src/pages/mobile/MobileHomePage.vue), [`frontend/src/router/index.ts`](frontend/src/router/index.ts)).
- **Locales** — Sinhala (`si`) bundles refreshed across admin, canvas, common, community, knowledge, mindmate, notification, sidebar, workshop; minor English / Chinese canvas copy ([`frontend/src/locales/messages/si/`](frontend/src/locales/messages/si/), [`zh/canvas.ts`](frontend/src/locales/messages/zh/canvas.ts)).
- **`frontend/scripts/sync-messages-keys-from-reference.ts`**, **`keyboardLayoutForUiLocale.ts`**, **`locales.ts`**, **`translateLanguages.ts`** — small i18n / keyboard plumbing alignment.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.3).

## [5.117.2] - 2026-05-06

### Added

- **Concept map** — remove a relationship curve with **Ctrl+click** (or **⌘+click** on macOS) on the curve segments, the relationship label, or edges routed from a label; cascades removal of child links with `linkedFromConnectionId`, clears relationship-picker state, respects collab foreign-edit locks, and records undo history (`removeConceptMapConnection` in diagram store, [`CurvedEdge.vue`](frontend/src/components/diagram/edges/CurvedEdge.vue), [`connectionManagement.ts`](frontend/src/stores/diagram/connectionManagement.ts)).
- **Workshop collab guests** — host’s announced multi-LLM tab (**`host_llm_model`**) is shown on the canvas AI strip via **`remoteHostDisplayedLlmModel`**; host re-flushes the selection after snapshot and when others join ([`useWorkshop.ts`](frontend/src/composables/workshop/useWorkshop.ts), [`useWorkshopMessageHandlers.ts`](frontend/src/composables/workshop/useWorkshopMessageHandlers.ts), [`AIModelSelector.vue`](frontend/src/components/canvas/AIModelSelector.vue), [`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue)).

### Changed

- **`frontend/src/composables/canvasPage/useCanvasPageCollabDiff.ts`** — optional full-spec fallback when granular node/connection/delete deltas exceed server caps (aligned with `workshop_ws_handlers_update_validate`); diagrams without a `connections` array no longer block diff sends.
- **`frontend/src/composables/workshop/useWorkshopOutboundDispatcher.ts`**, **`useWorkshopTypes.ts`**, **`routers/api/workshop_ws_handlers_core.py`**, **`workshop_ws_handlers_presence.py`**, **`services/features/workshop_ws_connection_state.py`** — wire host LLM announcements and presence plumbing.
- **`frontend/src/components/canvas/`** (`CanvasToolbar`, `CanvasTopBar`, `CanvasToolbarAiSection`), **`useCanvasToolbarApps.ts`**, **`useAutoComplete.ts`**, **`NodePalettePanel.vue`**, **`RootConceptModal.vue`** — toolbar / inline-rec and palette behavior aligned with collab host model UX.
- **Locales** (`en`, `zh`, `zh-tw` canvas / mindmate) — strings for new UX.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.2).

## [5.117.1] - 2026-05-05

### Added

- **`main.py`** — load `.env` before router imports so module-level fanout config (`COLLAB_FANOUT_ORIGIN_SECRET`, etc.) sees the same values as runtime; when `COLLAB_FANOUT_ORIGIN_SECRET` is unset, generate a per-process hex secret at startup (dev/single-worker convenience — **`env.example`** documents setting it explicitly for multi-worker production).

### Changed

- **`routers/api/diagrams_workshop_routes.py`** — `POST .../workshop/stop`: if stopping fails but the authenticated owner still has an active `workshop_code`, return **503** with a retry-oriented message instead of **404**, avoiding a false “not found” when the live-spec flush cannot complete.
- **`services/online_collab/core/online_collab_stop.py`** — bounded retries with backoff when flushing Redis live spec to Postgres on owner stop and idle stop; `destroy_session` / TTL extension use the **normalized** workshop code consistently (same value as flush).
- **`services/online_collab/spec/online_collab_live_spec_ops.py`** — `flush_live_spec_to_db_in_session`: treat missing Redis key as a successful no-op; distinguish unreadable JSON vs absent key; probe `EXISTS` when `read_live_spec` returns `None`.
- **`env.example`** — notes on `ENVIRONMENT=development` vs `COLLAB_STRICT_PROD_GUARDS`, and multi-worker `COLLAB_FANOUT_ORIGIN_SECRET` behavior.
- **`frontend/src/components/mindgraph/MindGraphCollabPanel.vue`** — responsive collab popper and join-code panel (container queries, grid layout, clamped typography) for narrow viewports.
- **`frontend/src/composables/canvasPage/useCanvasPageCollabIndicators.ts`** — remote-edit “ant” color sampling walks visible direct children (strongest border wins), fixes **Concept** nodes where the link handle was first in DOM; supports SVG circle stroke sampling.
- **`frontend/src/components/diagram/nodes/ConceptNode.vue`** — wrapper `border-radius` aligned with inner pill for collab outline shape.
- **`frontend/src/composables/workshop/useWorkshopMessageHandlers.ts`**, **`useWorkshopPresence.ts`**, **`useWorkshopReconnect.ts`** — presence join/leave notifications keyed by **`userId`** (coalescing avoids display-name mismatches on reconnect); skip self-join/self-leave toasts; **`session_closing`** / **`kicked`** handling so only non-owners see the “session ended by host” info toast for `session_ended`.
- **`frontend/src/composables/workshop/useWorkshopOutboundDispatcher.ts`** — guard `node_selected` / `node_editing` / `claim_node_edit` sends when the WebSocket ref is null.

### Tests

- **`frontend/tests/useWorkshopReconnect.spec.ts`** — coverage for `netPresenceAfterCancellingPairsByUserId`.
- **`tests/test_online_collab_hardening.py`** — idle-stop flush failure expects `WORKSHOP_STOP_FLUSH_MAX_ATTEMPTS` flush attempts.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.1).

## [5.117.0] - 2026-05-05

### Added

- **`services/online_collab/core/online_collab_stop.py`** — extracted owner-initiated and idle-stop flows from `online_collab_lifecycle.py` into a dedicated module; `lifecycle.py` now delegates via thin forwarding stubs.
- **`services/online_collab/core/online_collab_join.py`** — extracted join-flow logic into its own module.
- **`routers/api/diagrams_workshop_routes.py`** — workshop-specific diagram REST endpoints separated from the general diagrams router.
- **`routers/api/workshop_ws_handlers_core.py`**, **`workshop_ws_handlers_presence.py`**, **`workshop_ws_handlers_update_validate.py`** — WebSocket handler decomposition; `workshop_ws_handlers.py` now delegates to focused sub-handlers.
- **`frontend/src/composables/canvasPage/useCanvasPageCollabBus.ts`**, **`useCanvasPageCollabDiff.ts`**, **`useCanvasPageCollabIndicators.ts`** — canvas-page collab concerns split from the monolithic `useCanvasPageWorkshopCollab.ts`.
- **`frontend/src/composables/workshop/useWorkshopJoin.ts`**, **`useWorkshopOutboundDispatcher.ts`** — workshop join flow and outbound dispatch extracted from `useWorkshop.ts`.
- **`alembic/versions/rev_0028_unique_active_workshop_code.py`** — migration adding a partial unique index on `diagrams.workshop_code` for active (non-null) sessions, preventing duplicate active codes at the DB level.
- **`tests/test_online_collab_hardening.py`** — new hardening tests covering edge cases in the online collab module.

### Changed

- **`services/online_collab/` — production hardening sweep** (Pylint 10.00/10):
  - All `except Exception` broad-catches replaced with typed exception tuples throughout the module (`online_collab_lifecycle`, `online_collab_manager`, `online_collab_idle_monitor`, `online_collab_stop`, `online_collab_cleanup`, `online_collab_join_helpers`, `online_collab_participant_ops`, `online_collab_snapshots`, `online_collab_redis_health`, `online_collab_redis_keys`, `online_collab_redis_scripts`, `online_collab_live_spec_json`, `online_collab_live_spec_ops`, `online_collab_live_spec_shutdown`, `online_collab_json_offload`).
  - Dead code removed: orphaned `_extend_room_ttl_after_flush_failure` definition and its associated constant `_FAILED_FLUSH_RETRY_TTL_SEC` eliminated from `online_collab_lifecycle.py` (live copy remains in `online_collab_stop.py`).
  - All unused imports removed across the module; `os._exit(1)` replaced with `raise SystemExit(1)` in `online_collab_redis_health.py`.
  - All `pylint: disable` suppression comments removed; `SQLAlchemyError` import added to `online_collab_live_spec_ops.py`.
- **`routers/api/workshop_ws_handlers.py`**, **`workshop_ws_handlers_update.py`** — refactored to delegate to the new focused handler modules; substantially reduced line counts.
- **`routers/api/workshop_ws_auth.py`** — auth flow expanded.
- **`frontend/src/composables/canvasPage/useCanvasPageWorkshopCollab.ts`**, **`useWorkshop.ts`** — refactored to delegate to the new extracted composables; large line-count reduction.
- **`services/features/workshop_ws_role_change.py`** — role-change handling expanded.
- **`services/infrastructure/lifecycle/lifespan_redis_integration.py`** — updated for the new collab lifespan hooks.
- **`services/infrastructure/monitoring/ws_metrics.py`** — added metrics for snapshot oversize, viewer cache hit, and HEXPIRE downgrade events.
- **`models/domain/diagrams.py`** — workshop field adjustments aligned with the new unique-code constraint.
- **`tests/test_online_collab_redis_key_helpers.py`** — fixed `if False: yield` constant-test anti-pattern; expanded purge/key helper coverage.
- **`scripts/collab_synthetic_probe.py`** — probe script updated for new collab API surface.
- **Frontend locale bundles** (`az`, `en`, `zh`, `zh-tw`) — new and updated canvas/workshop/sidebar strings.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.117.0).

## [5.116.0] - 2026-05-04

### Added

- **`services/online_collab/`** — consolidated workshop / online collaboration backend (live spec, participants, Redis scripts and health, org listing, lifecycle, DB helpers); supersedes the legacy **`services/workshop/`** package removed in this release.
- **Canvas collaboration UX**: [`CanvasCollabOverlay.vue`](frontend/src/components/canvas/CanvasCollabOverlay.vue), [`CollabUserRail.vue`](frontend/src/components/canvas/CollabUserRail.vue), [`MindGraphCollabPanel.vue`](frontend/src/components/mindgraph/MindGraphCollabPanel.vue); shared palette constants in [`frontend/src/shared/collabPalette.ts`](frontend/src/shared/collabPalette.ts).
- **Workshop client plumbing**: [`useCollabOutboundQueue.ts`](frontend/src/composables/workshop/useCollabOutboundQueue.ts), [`useCollabSyncVersion.ts`](frontend/src/composables/workshop/useCollabSyncVersion.ts), [`useCanvasPageMountedHandlers.ts`](frontend/src/composables/canvasPage/useCanvasPageMountedHandlers.ts); composable splits [`useWorkshopHeartbeat.ts`](frontend/src/composables/workshop/useWorkshopHeartbeat.ts), [`useWorkshopMessageHandlers.ts`](frontend/src/composables/workshop/useWorkshopMessageHandlers.ts), [`useWorkshopPresence.ts`](frontend/src/composables/workshop/useWorkshopPresence.ts), [`useWorkshopReconnect.ts`](frontend/src/composables/workshop/useWorkshopReconnect.ts), [`useWorkshopTypes.ts`](frontend/src/composables/workshop/useWorkshopTypes.ts).
- **Application lifespan**: collab / DB / Redis integration and shutdown helpers under [`services/infrastructure/lifecycle/`](services/infrastructure/lifecycle/) (`lifespan_collab_integration.py`, `lifespan_db_integration.py`, `lifespan_redis_integration.py`, `lifespan_shutdown.py`) extracted from the main [`lifespan.py`](services/infrastructure/lifecycle/lifespan.py) module.
- **CI and load tooling**: [`.github/workflows/ci.yml`](.github/workflows/ci.yml), [`.github/workflows/nightly-collab.yml`](.github/workflows/nightly-collab.yml); [`loadtests/collab/`](loadtests/collab/); [`scripts/collab_synthetic_probe.py`](scripts/collab_synthetic_probe.py) and related scripts.
- **Frontend tests**: [`frontend/vitest.config.ts`](frontend/vitest.config.ts), [`frontend/tests/`](frontend/tests/).
- **Backend tests**: expanded collab / workshop / fanout / live-spec coverage under [`tests/`](tests/) (palette sync, WS JSON limits, join resume, update schema, integration probes, etc.).

### Changed

- **Workshop WebSocket surface**: [`workshop_ws_handlers.py`](routers/api/workshop_ws_handlers.py), [`workshop_ws_connect.py`](routers/api/workshop_ws_connect.py), [`workshop_ws_disconnect.py`](routers/api/workshop_ws_disconnect.py), [`workshop_ws_broadcast.py`](routers/api/workshop_ws_broadcast.py), [`workshop_ws_auth.py`](routers/api/workshop_ws_auth.py), plus focused helpers [`workshop_ws_handlers_update.py`](routers/api/workshop_ws_handlers_update.py), [`workshop_ws_update_schema.py`](routers/api/workshop_ws_update_schema.py).
- **Connection state, fanout, and metrics**: [`workshop_ws_connection_state.py`](services/features/workshop_ws_connection_state.py), [`workshop_ws_fanout_delivery.py`](services/features/workshop_ws_fanout_delivery.py), [`ws_redis_fanout_listener.py`](services/features/ws_redis_fanout_listener.py), [`ws_redis_fanout_publish.py`](services/features/ws_redis_fanout_publish.py), [`ws_redis_fanout_config.py`](services/features/ws_redis_fanout_config.py), [`ws_pg_notify_fanout.py`](services/features/ws_pg_notify_fanout.py), [`ws_metrics.py`](services/infrastructure/monitoring/ws_metrics.py); supporting utilities [`ws_context.py`](utils/ws_context.py), [`ws_limits.py`](utils/ws_limits.py), [`ws_session_registry.py`](utils/ws_session_registry.py), [`collab_ws_origin.py`](utils/collab_ws_origin.py).
- **Frontend canvas**: [`useCanvasPageWorkshopCollab.ts`](frontend/src/composables/canvasPage/useCanvasPageWorkshopCollab.ts), [`useWorkshop.ts`](frontend/src/composables/workshop/useWorkshop.ts), [`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue), [`MindGraphContainer.vue`](frontend/src/components/mindgraph/MindGraphContainer.vue), [`OnlineCollabModal.vue`](frontend/src/components/canvas/OnlineCollabModal.vue), [`ZoomControls.vue`](frontend/src/components/canvas/ZoomControls.vue), [`DiagramHistory.vue`](frontend/src/components/sidebar/DiagramHistory.vue), [`diagramCanvas.css`](frontend/src/components/diagram/diagramCanvas.css), live subtitle / translation stores and related utilities.
- **Internationalization**: new and updated **canvas** / **workshop** / **sidebar** strings across locale bundles under [`frontend/src/locales/messages/`](frontend/src/locales/messages/).
- **APIs and persistence**: [`routers/api/diagrams.py`](routers/api/diagrams.py), [`redis_diagram_cache.py`](services/redis/cache/redis_diagram_cache.py), [`config/database.py`](config/database.py); domain touch-ups ([`debateverse.py`](models/domain/debateverse.py), [`school_zone.py`](models/domain/school_zone.py)).
- **Environment reference**: [`env.example`](env.example) expanded for collab, Redis, and related deployment options.

### Removed

- **`services/workshop/`** — legacy workshop package; behavior lives under **`services/online_collab/`** and the refactored WebSocket / fanout layers above.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.116.0).

## [5.115.0] - 2026-05-03

### Changed

- **Workshop live spec is RedisJSON-only on Redis 8+** ([`services/online_collab/spec/`](services/online_collab/spec/)): startup asserts `INFO server` → `redis_version >= 8.0.0` when online collab is enabled ([`check_online_collab_redis_version`](services/online_collab/redis/online_collab_redis_health.py)); string `SETEX`/`GET` fallbacks and the optimistic-lock `WATCH`/string merge loop for `workshop:live_spec:{code}` are removed. Each WS merge runs a single pipelines path: `JSON.MERGE` or `JSON.SET`, optional `JSON.NUMINCRBY` on `$.v`, `EXPIRE` (GT), changed-keys `SADD`, `EXPIRE` on the set, and `INCR` on `snapshot_seq` in one `MULTI/EXEC` when `COLLAB_REDIS_HASH_TAGS=1`. The historical `COLLAB_REDIS_JSON_LIVE_SPEC` toggle is obsolete at the code level (live spec always uses `JSON.*`).

### Observability

- **Renamed collab JSON health counter**: `ws_redisjson_fallback_total` / `record_ws_redisjson_fallback` → **`ws_redisjson_failure_total`** / `record_ws_redisjson_failure_total` ([`ws_metrics.py`](services/infrastructure/monitoring/ws_metrics.py)). Log-based collab alerts treat any non-zero failure count as `ws_redisjson_failure_nonzero`.

### Documentation

- **Pre-deploy drain runbook**: [`docs/runbooks/online_collab_redisjson_baseline.md`](docs/runbooks/online_collab_redisjson_baseline.md) (`COLLAB_DISABLED`, flush live specs to Postgres, delete `workshop:live_spec:*`, deploy, re-enable).
- **Cluster ops**: [`docs/operations/redis_cluster_online_collab.md`](docs/operations/redis_cluster_online_collab.md) — Redis 8.0 floor and hash-tag co-location for live spec / snapshot seq / changed keys.

### Tests

- [`tests/test_redis_version_assertion.py`](tests/test_redis_version_assertion.py), [`tests/test_live_spec_pipeline_commands.py`](tests/test_live_spec_pipeline_commands.py), [`tests/test_live_spec_hash_tag_colocation.py`](tests/test_live_spec_hash_tag_colocation.py).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.115.0).

### Load verification

- Before production cutover at 200–500 concurrent editors, run [`loadtests/collab`](loadtests/collab/) against staging and confirm `ws_redisjson_failure_total` stays **0** and broadcast latency is acceptable; attach results to the release notes / PR as needed.

## [5.114.0] - 2026-05-03

### Added

- **GitHub Actions CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): on push and pull request to `main`, `master`, and `develop` — Python 3.13 app import smoke, targeted **Pylint** on collaboration and WebSocket paths, focused **pytest** collab suite, and **Vitest** for the frontend.
- **Manual collab load / soak workflow** ([`.github/workflows/nightly-collab.yml`](.github/workflows/nightly-collab.yml)): `workflow_dispatch` job to run **Locust** against a supplied HTTPS origin, session JWT, and workshop codes; optional Redis churn via `CLIENT PAUSE` when a `redis://` target is provided.
- **Prompt language registry artifact** ([`data/prompt_language_registry.json`](data/prompt_language_registry.json)): checked-in registry used by prompt-output language sync checks and the frontend `build-prompt-registry` prebuild step.

### Changed

- **Workshop client composables** ([`frontend/src/composables/workshop/`](frontend/src/composables/workshop/)): split heartbeat, inbound message dispatch, presence, reconnect/backoff helpers, and shared **TypeScript** types out of [`useWorkshop.ts`](frontend/src/composables/workshop/useWorkshop.ts) into [`useWorkshopHeartbeat.ts`](frontend/src/composables/workshop/useWorkshopHeartbeat.ts), [`useWorkshopMessageHandlers.ts`](frontend/src/composables/workshop/useWorkshopMessageHandlers.ts), [`useWorkshopPresence.ts`](frontend/src/composables/workshop/useWorkshopPresence.ts), [`useWorkshopReconnect.ts`](frontend/src/composables/workshop/useWorkshopReconnect.ts), and [`useWorkshopTypes.ts`](frontend/src/composables/workshop/useWorkshopTypes.ts) for clearer boundaries and testing ([`frontend/tests/useWorkshopReconnect.spec.ts`](frontend/tests/useWorkshopReconnect.spec.ts)).
- **Environment reference** ([`env.example`](env.example)): online collab and related settings documented and aligned with current options.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.114.0).

## [5.113.0] - 2026-05-02

### Online Collab Production Hardening

This release completes a full production-hardening pass of the online collaboration (workshop) module, targeting 200–500 concurrent teachers per session. All changes are native-asyncio with no wrapper layers, fully leveraging Redis 8.6 and PostgreSQL 18.3 features.

#### Fanout Topology (P0 + P1)

- **Per-connection writer tasks with bounded queues**: replaced `ws.send_json` calls with an `asyncio.Queue`-backed `_writer_loop` per handle (`ConnectionHandle`). Slow consumers are evicted without affecting others (`WORKSHOP_SLOW_CONSUMER_EVICT=1`).
- **Pre-serialized sharded fanout** ([`services/features/workshop_ws_fanout_delivery.py`](services/features/workshop_ws_fanout_delivery.py)): payload encoded to bytes **once** per broadcast; room split into shards of `_SHARD_SIZE` peers, each shard processed concurrently via `asyncio.TaskGroup + asyncio.Semaphore(WORKSHOP_FANOUT_SHARD_CONCURRENCY, default 50)`.
- **50 ms time-windowed coalescing**: node-editing frames within a 50 ms window are coalesced per peer before being queued, cutting queue pressure by ~80% in large rooms.
- **Per-message-type backpressure policy**: `update` and `node_editing` frames use `put_nowait` (drop-on-full); `join` / `room_state` / `error` frames always enqueue.
- **Redis Pub/Sub as sole broadcast path** (P1): fixed a critical bug where `XREADGROUP` load-balances to only one consumer group member, breaking broadcast semantics. Streams are now an optional audit log only (`COLLAB_REDIS_STREAMS_AUDIT=1`). Primary delivery uses `SPUBLISH` (sharded, default) → `PUBLISH` → PG LISTEN/NOTIFY fallback.

#### Final sweep — gaps (2026-05-02)

- **Superseded session teardown**: prior tab’s writer/flush tasks are torn down before the new handle replaces it; superseded sockets close with 4003.
- **FCALL node editor merge**: `mg_node_editing_set` / `del` Lua performs read-modify-write so co-editors are not dropped under races.
- **Fan-out force-close**: `_close_one_handle` finalizes writer shutdown and cancels flush tasks to avoid orphaned queues.
- **Client resync**: pending snapshot gaps time out with capped resync retries, `sessionDiagramId` fallback, presence coalescing, and structural lock timer cleanup on canvas leave.
- **DB flush gating**: `schedule_live_spec_db_flush` runs only when live-spec merge succeeds.
- **Metrics / ops**: semaphore wait + hot-path Redis read latencies in JSON snapshot; dead Prometheus formatter removed; log-based `collab_alerts` includes sampled `live_spec_db_flush_lag_detected` when Redis activity leads flush timestamps.
- **Startup / shutdown**: Redis Functions preload after script load; graceful registry drain; shutdown scan flushes all `workshop:live_spec:*` to Postgres before the DB pool closes; debounced flush timers cancelled first.
- **Limits**: Uvicorn `ws_max_size=1MiB`, collab inbound text capped at 1 MiB (configurable), JSON nesting depth capped for inbound messages.
- **Kill switch / hygiene**: `COLLAB_DISABLED` closes new collab handshakes; GDPR purge hook for user deletion; `__seq__` stripped from snapshot/flush payloads.
- **Deliverables**: GitHub Actions CI (targeted pylint + pytest + vitest), Locust skeleton under `loadtests/collab`, synthetic dual-client probe `scripts/collab_synthetic_probe.py`, runbooks under `docs/runbooks/online_collab_*.md`, cluster notes in `docs/operations/redis_cluster_online_collab.md`.

### Wrapper Removal (P2)

- Deleted `online_collab_bg_tasks.py` (`spawn_bg`): replaced with raw `asyncio.create_task` + explicit task reference on owner objects.
- Deleted `workshop_ws_safe_send.py` (`safe_send_json`): per-WS `asyncio.Lock` + `asyncio.timeout(1.5)` inlined at each send site; `WeakKeyDictionary` moved to `workshop_ws_connection_state.py`.
- Deleted `online_collab_asyncio_timeouts.py` (wrapper timeouts): replaced with inline `asyncio.timeout(...)` context managers.
- Removed `LatencyTimer`: replaced with `time.perf_counter()` + `asyncio.create_task(tdigest_record_latency(...))` at each of the four call sites.

#### Redis 8.6 Optimisations (P3)

- **Participants as HASH** ([`services/online_collab/participant/online_collab_participant_ops.py`](services/online_collab/participant/online_collab_participant_ops.py)): `participants:{code}` converted from SET to HASH (field = user_id, value = join-epoch). Per-field TTL via `HEXPIRE` (Redis 7.4+) with whole-key `EXPIRE` fallback; downgrade counted by `record_ws_hexpire_downgrade`.
- **RedisJSON as default live-spec backend** (`COLLAB_REDIS_JSON_LIVE_SPEC=1` default): `JSON.MERGE` for granular patches, `JSON.SET` for full replacements. Falls back to WATCH/MULTI/EXEC loop on failure; fallback counted by `record_ws_redisjson_fallback`.
- **Lua scripts preloaded at startup** ([`services/online_collab/redis/online_collab_redis_scripts.py`](services/online_collab/redis/online_collab_redis_scripts.py)): join-cap and rate-limiter scripts loaded via `SCRIPT LOAD`; hot paths use `EVALSHA` with transparent `NOSCRIPT` reload.
- **Pipelined `CONFIG GET`** ([`services/online_collab/redis/online_collab_redis_health.py`](services/online_collab/redis/online_collab_redis_health.py)): three `CONFIG GET` calls (`appendonly`, `appendfsync`, `maxmemory-policy`) collapsed into one pipeline round-trip.
- **Atomic rate-limiter Lua script** ([`services/online_collab/participant/online_collab_ws_rate_limit.py`](services/online_collab/participant/online_collab_ws_rate_limit.py)): user + IP checks combined into a single `EVALSHA` call, eliminating the race between separate checks.
- **Sharded Pub/Sub default** (`COLLAB_REDIS_SPUBLISH=1`): `SPUBLISH` used by default for Redis Cluster-aware broadcasting with PUBLISH fallback for pre-7.0 servers.
- **CLIENT TRACKING extended**: `CLIENT TRACKING ON BCAST PREFIX` now covers `workshop:registry:` in addition to the session prefix, ensuring session meta-cache invalidation across workers.
- **EXPIRE GT everywhere**: all TTL refresh paths (`json_merge_patch`, `json_set_nodes`, editor hash) use `gt=True` so TTLs are only extended, never shortened, on update paths.
- **Optional `WAIT 1 200` for write durability** (`COLLAB_REDIS_WAIT_DURABILITY=1`): env-gated `WAIT 1 200` after `create_session` and `destroy_session` pipelines ensures commands propagate to at least one replica.
- **Pipelined org session listing** ([`services/online_collab/core/online_collab_org_listing.py`](services/online_collab/core/online_collab_org_listing.py)): N+1 Redis problem fixed — all `HGETALL` and `HLEN` calls for an org's sessions are batched into one pipeline.
- **FIFO OrderedDict eviction**: `_node_editing_dedup_cache` and `session_meta_cache._cache` use `OrderedDict.popitem(last=False)` to evict oldest entries instead of `clear()`, preventing thundering-herd re-fill.
- **Atomic Redis purge for cluster** ([`services/online_collab/redis/online_collab_redis_keys.py`](services/online_collab/redis/online_collab_redis_keys.py)): `purge_online_collab_redis_keys` uses `pipeline(transaction=True)` when hash tags are enabled; per-key `UNLINK`/`DEL` fallback for MOVED errors.

#### PostgreSQL 18.3 Optimisations (P4)

- **MERGE for cleanup** ([`services/online_collab/core/online_collab_lifecycle.py`](services/online_collab/core/online_collab_lifecycle.py)): `cleanup_expired_online_collabs_impl` uses `MERGE INTO ... RETURNING t.id, s.workshop_code` to atomically clear expired sessions and retrieve the pre-update `workshop_code` for Redis purging in one statement (previously `UPDATE ... RETURNING` could not reliably surface the pre-update code).
- **Partial JSONB writes** ([`services/online_collab/spec/online_collab_live_spec_ops.py`](services/online_collab/spec/online_collab_live_spec_ops.py)): `apply_live_update` now returns a `(doc, version, changed_keys)` 3-tuple. `changed_keys` (a `frozenset`) drives `jsonb_set` for only the changed top-level keys, cutting wire traffic 70–90% for large diagrams. Full-replace (`__full__` sentinel) still writes the whole column.
- **PG LISTEN/NOTIFY fallback** ([`services/features/ws_pg_notify_fanout.py`](services/features/ws_pg_notify_fanout.py)): activated via `COLLAB_PG_NOTIFY_FALLBACK=1`; publishes to a per-machine PG channel when Redis Pub/Sub `publish` raises `RedisError`; listener runs as a background `asyncio.Task`.
- **SQLAlchemy compiled-statement cache** ([`services/online_collab/db/online_collab_stmt_cache.py`](services/online_collab/db/online_collab_stmt_cache.py)): `STMT_DIAGRAM_BY_ID`, `STMT_DIAGRAM_SPEC_BY_ID`, `STMT_DIAGRAM_UPDATE_SPEC` pre-compiled with `bindparam` for zero-parse-overhead on hot paths; `create_async_engine(query_cache_size=DATABASE_QUERY_CACHE_SIZE)` (default 1200).
- **Connection pool startup assertion** ([`config/database.py`](config/database.py)): `DATABASE_POOL_HARD_ASSERT=1` aborts startup when `worker_count × pool_size > max_connections`.

#### Concurrency & Safety (P5)

- **`asyncio.Semaphore` on idle-monitor TaskGroup** (`COLLAB_IDLE_MONITOR_CONCURRENCY`, default 20): bounds concurrent stale-code evaluations per cycle.
- **`asyncio.Semaphore` on fanout shard TaskGroup** (`WORKSHOP_FANOUT_SHARD_CONCURRENCY`, default 50): limits concurrent shard processing within `deliver_local_workshop_broadcast`.
- **`destroy_session` lock always released**: refactored to `try...finally` — the per-code `asyncio.Lock` is guaranteed to release even when purge raises.
- **`asyncio.to_thread` for large JSON/deepcopy** ([`services/online_collab/common/online_collab_json_offload.py`](services/online_collab/common/online_collab_json_offload.py)): `dumps_maybe_offload`, `loads_maybe_offload`, `deepcopy_maybe_offload` forward to a thread pool when payload exceeds `COLLAB_JSON_THREAD_OFFLOAD_BYTES` (default 64 KiB), keeping the event loop responsive.
- **Per-room `asyncio.Lock` for `ACTIVE_CONNECTIONS`** ([`services/features/workshop_ws_connection_state.py`](services/features/workshop_ws_connection_state.py)): `register_connection` and `unregister_connection` are guarded by a per-room lock, preventing concurrent mutation races.

#### Module Splits (P6)

| Before | After | Lines |
|--------|-------|-------|
| `online_collab_manager.py` (874 LOC) | `online_collab_session_redis.py`, `online_collab_join.py`, `online_collab_org_listing.py` + thin facade | Each ≤ 700 |
| `online_collab_lifecycle.py` (706 LOC) | `_cleanup`, `_start`, `_stop` submodules | Each ≤ 650 |
| `workshop_ws_handlers.py` (924 LOC) | `workshop_ws_handlers.py` (dispatcher) + `workshop_ws_handlers_update.py` | 507 + 400 |

#### Observability (P7)

New counters added to [`services/infrastructure/monitoring/ws_metrics.py`](services/infrastructure/monitoring/ws_metrics.py):

| Counter | Description |
|---------|-------------|
| `ws_watcherror_retry_total` | WATCH/MULTI/EXEC retries on live-spec contention |
| `ws_hexpire_downgrade_total` | HEXPIRE → EXPIRE downgrades (Redis < 7.4) |
| `ws_redisjson_fallback_total` | RedisJSON path failures, fell back to WATCH loop |
| `ws_fanout_publish_success_total` | Successful Redis pub/sub publish calls |
| `ws_fanout_publish_failure_total` | Failed Redis pub/sub publish calls |
| `ws_idle_monitor_cycle_total` | Idle-monitor loop cycles with stale codes found |
| `ws_cleanup_partition_size_total` | Total expired sessions purged across cleanup runs |
| `ws_broadcast_latency_samples_total` | Broadcast latency samples (p50/p95/p99 via T-Digest when `COLLAB_REDIS_TIMESERIES=1`) |

#### Environment Variable Reference

| Variable | Default | Purpose |
|---|---|---|
| `COLLAB_REDIS_JSON_LIVE_SPEC` | `1` | Use RedisJSON for live-spec storage (0 = WATCH loop only) |
| `COLLAB_REDIS_SPUBLISH` | `1` | Use `SPUBLISH` (sharded pub/sub) for broadcast |
| `COLLAB_REDIS_STREAMS_AUDIT` | `0` | Append `XADD` audit log after each publish |
| `COLLAB_REDIS_WAIT_DURABILITY` | `0` | `WAIT 1 200` after create/destroy session pipeline |
| `COLLAB_REDIS_HASH_TAGS` | `0` | Use Redis hash tags for cluster key co-location |
| `COLLAB_PG_NOTIFY_FALLBACK` | `0` | PG LISTEN/NOTIFY fallback when Redis publish fails |
| `COLLAB_IDLE_MONITOR_CONCURRENCY` | `20` | Max concurrent stale-code evaluations per idle-monitor cycle |
| `COLLAB_JSON_THREAD_OFFLOAD_BYTES` | `65536` | Payload size threshold for offloading JSON ops to thread pool |
| `WORKSHOP_FANOUT_SHARD_CONCURRENCY` | `50` | Max concurrent shard tasks in `deliver_local_workshop_broadcast` |
| `WORKSHOP_SLOW_CONSUMER_EVICT` | `1` | Evict slow consumers on queue full |

### Added
- **Online collab backend package** ([`services/online_collab/`](services/online_collab/)): `services/workshop/` rehomed and split into `core/` (manager, idle monitor, lifecycle, status, room code), `common/` (async helpers, background tasks, collab palette), `redis/`, `participant/`, `spec/`; public exports `OnlineCollabManager`, `get_online_collab_manager`, `start_online_collab_manager`, `generate_online_collab_code`, `start_online_collab_cleanup_scheduler`. **Data plane unchanged**: diagram `workshop_*` columns, existing Redis key prefixes, env vars, and HTTP/WS routes stay as they are.

- **Canvas collab UI** ([`frontend/src/components/canvas/CanvasCollabOverlay.vue`](frontend/src/components/canvas/CanvasCollabOverlay.vue), [`frontend/src/components/canvas/CollabUserRail.vue`](frontend/src/components/canvas/CollabUserRail.vue), [`frontend/src/components/mindgraph/MindGraphCollabPanel.vue`](frontend/src/components/mindgraph/MindGraphCollabPanel.vue), [`frontend/src/shared/collabPalette.ts`](frontend/src/shared/collabPalette.ts)): overlay, participant rail, and mind-graph collab panel wired to shared palette helpers aligned with the server collab palette.

- **Workshop reconnect helper + Vitest** ([`frontend/src/composables/workshop/useWorkshopReconnect.ts`](frontend/src/composables/workshop/useWorkshopReconnect.ts), [`frontend/tests/useWorkshopReconnect.spec.ts`](frontend/tests/useWorkshopReconnect.spec.ts), [`frontend/vitest.config.ts`](frontend/vitest.config.ts)): composable for reconnect behaviour; minimal Vitest config (`tests/**/*.spec.ts`, jsdom) separate from `vite.config.ts`.

### Changed
- **Workshop / collab WebSocket stack** ([`routers/api/workshop_ws.py`](routers/api/workshop_ws.py), [`routers/api/workshop_ws_auth.py`](routers/api/workshop_ws_auth.py), [`routers/api/workshop_ws_broadcast.py`](routers/api/workshop_ws_broadcast.py), [`routers/api/workshop_ws_connect.py`](routers/api/workshop_ws_connect.py), [`routers/api/workshop_ws_disconnect.py`](routers/api/workshop_ws_disconnect.py), [`routers/api/workshop_ws_handlers.py`](routers/api/workshop_ws_handlers.py), [`services/features/workshop_ws_fanout_delivery.py`](services/features/workshop_ws_fanout_delivery.py), [`services/features/ws_redis_fanout_config.py`](services/features/ws_redis_fanout_config.py), [`services/features/ws_redis_fanout_listener.py`](services/features/ws_redis_fanout_listener.py), [`services/features/ws_redis_fanout_publish.py`](services/features/ws_redis_fanout_publish.py)): modular routers and fan-out wiring; metrics and lifespan imports updated for `online_collab` ([`services/infrastructure/lifecycle/lifespan.py`](services/infrastructure/lifecycle/lifespan.py), [`services/infrastructure/monitoring/ws_metrics.py`](services/infrastructure/monitoring/ws_metrics.py)).

- **Diagrams API + models** ([`routers/api/diagrams.py`](routers/api/diagrams.py), [`models/responses.py`](models/responses.py)): responses and collab-related handling aligned with the refactored backend.

- **Canvas / workshop composables & shell** ([`frontend/src/composables/canvasPage/useCanvasPageWorkshopCollab.ts`](frontend/src/composables/canvasPage/useCanvasPageWorkshopCollab.ts), [`frontend/src/composables/canvasPage/useCanvasPageMountedHandlers.ts`](frontend/src/composables/canvasPage/useCanvasPageMountedHandlers.ts), [`frontend/src/composables/canvasPage/useCanvasPageLibrarySnapshots.ts`](frontend/src/composables/canvasPage/useCanvasPageLibrarySnapshots.ts), [`frontend/src/composables/workshop/useWorkshop.ts`](frontend/src/composables/workshop/useWorkshop.ts), [`frontend/src/composables/core/useEventBus.ts`](frontend/src/composables/core/useEventBus.ts), [`frontend/src/pages/CanvasPage.vue`](frontend/src/pages/CanvasPage.vue), [`frontend/src/components/mindgraph/MindGraphContainer.vue`](frontend/src/components/mindgraph/MindGraphContainer.vue)): collab lifecycle, mounts, and event bus typings updated for the new UI and reconnect path.

- **Toolbar, modal, zoom, history, palette** ([`frontend/src/components/canvas/CanvasToolbarAiSection.vue`](frontend/src/components/canvas/CanvasToolbarAiSection.vue), [`frontend/src/components/canvas/CanvasTopBar.vue`](frontend/src/components/canvas/CanvasTopBar.vue), [`frontend/src/components/canvas/OnlineCollabModal.vue`](frontend/src/components/canvas/OnlineCollabModal.vue), [`frontend/src/components/canvas/ZoomControls.vue`](frontend/src/components/canvas/ZoomControls.vue), [`frontend/src/components/sidebar/DiagramHistory.vue`](frontend/src/components/sidebar/DiagramHistory.vue), [`frontend/src/components/panels/NodePalettePanel.vue`](frontend/src/components/panels/NodePalettePanel.vue), [`frontend/src/composables/canvasToolbar/useCanvasToolbarApps.ts`](frontend/src/composables/canvasToolbar/useCanvasToolbarApps.ts)): collab entry points and controls tweaked for the new overlay/rail flow.

- **Diagram store / spec I/O** ([`frontend/src/stores/savedDiagrams.ts`](frontend/src/stores/savedDiagrams.ts), [`frontend/src/stores/diagram/specIO.ts`](frontend/src/stores/diagram/specIO.ts)): persistence paths consistent with collab snapshot behaviour.

- **Landing i18n component** ([`frontend/src/components/mindgraph/InternationalLanding.vue`](frontend/src/components/mindgraph/InternationalLanding.vue), [`frontend/src/components/mindgraph/MindGraphLanguageSwitcher.vue`](frontend/src/components/mindgraph/MindGraphLanguageSwitcher.vue)): small alignment with collab/language UX.

- **Locales** ([`frontend/src/locales/messages/**/canvas.ts`](frontend/src/locales/messages/), [`frontend/src/locales/messages/**/workshop.ts`](frontend/src/locales/messages/), [`frontend/src/locales/messages/en/sidebar.ts`](frontend/src/locales/messages/en/sidebar.ts), [`frontend/src/locales/messages/zh/sidebar.ts`](frontend/src/locales/messages/zh/sidebar.ts), [`frontend/src/locales/messages/zh-tw/sidebar.ts`](frontend/src/locales/messages/zh-tw/sidebar.ts)): canvas, workshop, and sidebar strings for collab UI.

- **Canvas stylesheet** ([`frontend/src/components/diagram/diagramCanvas.css`](frontend/src/components/diagram/diagramCanvas.css)): styles for collab overlay layers.

- **Canvas barrel** ([`frontend/src/components/canvas/index.ts`](frontend/src/components/canvas/index.ts)): exports updated for new components.

### Frontend package version
- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.113.0).

## [5.112.0] - 2026-04-30

### Added
- **Live ASR subtitles — canvas** ([`routers/api/asr_realtime_ws.py`](routers/api/asr_realtime_ws.py), [`services/features/asr_realtime_bridge.py`](services/features/asr_realtime_bridge.py), [`frontend/src/stores/liveSubtitles.ts`](frontend/src/stores/liveSubtitles.ts), [`frontend/src/components/canvas/CanvasLiveSubtitleOverlay.vue`](frontend/src/components/canvas/CanvasLiveSubtitleOverlay.vue)): WebSocket bridge `/api/ws/canvas-asr` relays browser PCM16 audio to **DashScope Qwen3 ASR Flash Realtime**; store captures interim + committed lines at max 100; film-style draggable overlay (`CanvasLiveSubtitleOverlay`) shows at most 2 committed lines + 1 forming line, Teleported to `<body>` so it floats above presentation layers; double-click grip snaps to default bottom-centre.

- **Live translation — canvas (admin-only)** ([`routers/api/live_translate_ws.py`](routers/api/live_translate_ws.py), [`services/features/live_translate_bridge.py`](services/features/live_translate_bridge.py), [`frontend/src/stores/liveTranslation.ts`](frontend/src/stores/liveTranslation.ts), [`frontend/src/utils/translateLanguages.ts`](frontend/src/utils/translateLanguages.ts)): WebSocket bridge `/api/ws/canvas-translate` (403 for non-admins) relays audio to **DashScope Qwen3 LiveTranslate Flash Realtime**; auto-derives target language (zh→en, other→zh); admin Globe dropdown in `MindGraphContainer` and `InternationalLanding` lets admins toggle translation and pick a target from `TRANSLATE_LANGUAGES` (18 languages).

- **WebSocket session registry + managed context** ([`utils/ws_session_registry.py`](utils/ws_session_registry.py), [`utils/ws_context.py`](utils/ws_context.py)): lock-free in-process `WsSessionRegistry` tracks every open WS across all endpoints on a worker; `ws_managed_session` async context manager enforces per-user per-endpoint limits (e.g. `max_per_user_endpoint=1` for ASR/translate), registers/unregisters sessions, and sends a proper close frame with the configured error JSON if the limit is exceeded; bulk `close_all` used on graceful shutdown.

- **Admin endpoint — WS session snapshot** ([`routers/admin/realtime.py`](routers/admin/realtime.py)): `GET /admin/ws-sessions` returns the in-process `_registry.snapshot()` (session_id, user_id, endpoint, remote_addr, age_seconds, per-endpoint counts) merged with the cross-worker Redis gauge from `get_ws_metrics_snapshot()` — for live debugging of stuck sessions or cleanup verification.

- **Graceful WebSocket shutdown** ([`services/infrastructure/lifecycle/lifespan.py`](services/infrastructure/lifecycle/lifespan.py)): on lifespan shutdown the registry `close_all(code=1001, reason="Server shutting down")` is awaited before stopping the fan-out listener and Redis, giving clients a proper `GOING_AWAY` close frame instead of a hard TCP reset.

- **DashScope LLM config** ([`config/llm_config.py`](config/llm_config.py)): new properties `DASHSCOPE_API_KEY` (region key separate from `QWEN_API_KEY`), `QWEN_ASR_REALTIME_MODEL` (default `qwen3-asr-flash-realtime`), `QWEN_LIVE_TRANSLATE_MODEL` (default `qwen3-livetranslate-flash-realtime`), `DASHSCOPE_REALTIME_WS_BASE` (region-aware: `cn` → Beijing endpoint, `intl`/`sg` → international endpoint; or full `wss://` override via env var).

- **`MindGraphLanguageSwitcher`** ([`frontend/src/components/mindgraph/MindGraphLanguageSwitcher.vue`](frontend/src/components/mindgraph/MindGraphLanguageSwitcher.vue)): reusable `header`/`floating` variant component for quick UI + prompt language switching on landing pages; integrated into `MindGraphContainer` (header variant) and `InternationalLanding` (floating variant).

- **`BlackCat` mascot** ([`frontend/src/utils/mascot/blackCat.ts`](frontend/src/utils/mascot/blackCat.ts), [`frontend/src/utils/mascot/catWalk.ts`](frontend/src/utils/mascot/catWalk.ts)): SVG-based voice-agent mascot with states (`idle`, `listening`, `thinking`, `speaking`, `celebrating`, `error`) and walk animation; retained for future VoiceAgent integration.

### Changed
- **`ws_limits.py` — helper functions** ([`utils/ws_limits.py`](utils/ws_limits.py)): added `safe_websocket_send_text`, `receive_websocket_text_frame`, `text_payload_from_websocket_receive`, `inbound_text_exceeds_limit`, and `WebsocketMessageRateLimiter` (token-bucket, default 40 msg/s) shared by ASR, translate, workshop, and voice WebSocket routes.

- **Workshop WebSocket** ([`routers/api/workshop_ws.py`](routers/api/workshop_ws.py), [`services/features/workshop_chat_ws_manager.py`](services/features/workshop_chat_ws_manager.py)): migrated to `ws_managed_session` context and `ws_session_registry` for unified session tracking and per-user limit enforcement.

- **SSE streaming** ([`routers/api/sse_streaming.py`](routers/api/sse_streaming.py)): hardened disconnect handling; consistent use of shared `ws_limits` helpers.

- **Canvas locale strings** ([`frontend/src/locales/messages/en/canvas.ts`](frontend/src/locales/messages/en/canvas.ts), [`frontend/src/locales/messages/zh/canvas.ts`](frontend/src/locales/messages/zh/canvas.ts)): added subtitle (`canvas.subtitles.*`) and translation (`canvas.translation.*`) keys.

- **`translateForUiLocale`** ([`frontend/src/i18n/translateForUiLocale.ts`](frontend/src/i18n/translateForUiLocale.ts)): updated locale resolution to cover new language entries.

- **`App.vue` / stores index** ([`frontend/src/App.vue`](frontend/src/App.vue), [`frontend/src/stores/index.ts`](frontend/src/stores/index.ts)): wired `liveSubtitles` and `liveTranslation` stores into the app lifecycle and barrel exports.

- **`vite.config.ts`** ([`frontend/vite.config.ts`](frontend/vite.config.ts)): build and proxy config updates to support WS endpoints.

- **WS metrics** ([`services/infrastructure/monitoring/ws_metrics.py`](services/infrastructure/monitoring/ws_metrics.py)): added `get_ws_metrics_snapshot()` and `record_ws_connection_delta()` for use by the registry and the admin snapshot endpoint.

- **Auth helpers / phone router** ([`routers/auth/helpers.py`](routers/auth/helpers.py), [`routers/auth/phone.py`](routers/auth/phone.py)): minor improvements aligned with WS auth flow.

- **VPN geo enforcement** ([`services/auth/vpn_geo_enforcement.py`](services/auth/vpn_geo_enforcement.py)): `maybe_close_websocket_for_vpn_cn_geo` used by ASR and translate WebSocket routers.

- **Logging config** ([`services/infrastructure/utils/logging_config.py`](services/infrastructure/utils/logging_config.py)): noise filters for new WS endpoint log names.

### Frontend package version
- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.112.0).

## [5.111.0] - 2026-04-29

### Added
- **Concept map — inline Tab recommendations** ([`frontend/src/utils/conceptMapInlineRec.ts`](frontend/src/utils/conceptMapInlineRec.ts), [`frontend/src/composables/canvasPage/useConceptMapRelationshipTabFromSelection.ts`](frontend/src/composables/canvasPage/useConceptMapRelationshipTabFromSelection.ts), [`frontend/src/composables/editor/useInlineRecommendations.ts`](frontend/src/composables/editor/useInlineRecommendations.ts), [`agents/inline_recommendations/prompts/concept_map.py`](agents/inline_recommendations/prompts/concept_map.py), [`agents/inline_recommendations/`](agents/inline_recommendations/)): relationship-label vs concept-wording stages for linked vs isolated nodes; Tab-from-selection path mirrors select→Tab without opening inline edit; backend prompts and generator wiring for concept-map inline streams.

### Changed
- **Inline recommendations — canvas and nodes** ([`frontend/src/components/canvas/InlineRecommendationsPicker.vue`](frontend/src/components/canvas/InlineRecommendationsPicker.vue), [`frontend/src/components/canvas/AIModelSelector.vue`](frontend/src/components/canvas/AIModelSelector.vue), [`frontend/src/pages/CanvasPage.vue`](frontend/src/pages/CanvasPage.vue), [`frontend/src/pages/mobile/MobileCanvasPage.vue`](frontend/src/pages/mobile/MobileCanvasPage.vue), [`frontend/src/components/diagram/nodes/ConceptNode.vue`](frontend/src/components/diagram/nodes/ConceptNode.vue), [`frontend/src/components/diagram/nodes/InlineEditableText.vue`](frontend/src/components/diagram/nodes/InlineEditableText.vue)): picker, model selector, and diagram wiring for concept-map Tab flows.

- **Locales** ([`frontend/src/locales/messages/**`](frontend/src/locales/messages/)): assorted sidebar, admin, common, and mindmate strings across locales.

- **`useEventBus`** ([`frontend/src/composables/core/useEventBus.ts`](frontend/src/composables/core/useEventBus.ts)): typings aligned with inline recommendation events.

### Fixed
- **`Connection[]` typing in inline recommendations** ([`frontend/src/composables/editor/useInlineRecommendations.ts`](frontend/src/composables/editor/useInlineRecommendations.ts)): `getStageForNode` accepts **`Connection[]`** so **`getConceptMapPrimaryIncidentConnection`** receives edges with required **`id`**, fixing **TS2345** on concept-map stage detection.

### Frontend package version
- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.111.0).

## [5.110.0] - 2026-04-29

### Added
- **User preference `match_prompt_to_ui`** ([`alembic/versions/rev_0026_user_match_prompt_to_ui.py`](alembic/versions/rev_0026_user_match_prompt_to_ui.py), [`models/domain/auth.py`](models/domain/auth.py), [`services/redis/cache/redis_user_cache.py`](services/redis/cache/redis_user_cache.py), [`routers/auth/preferences.py`](routers/auth/preferences.py), [`routers/auth/login.py`](routers/auth/login.py), [`routers/auth/session.py`](routers/auth/session.py), [`frontend/src/stores/auth.ts`](frontend/src/stores/auth.ts), [`frontend/src/stores/ui.ts`](frontend/src/stores/ui.ts), [`frontend/src/types/auth.ts`](frontend/src/types/auth.ts), [`frontend/src/components/settings/LanguageSettingsModal.vue`](frontend/src/components/settings/LanguageSettingsModal.vue)): persisted column **`users.match_prompt_to_ui`** (default **true**) so returning users keep whether UI language and AI prompt language stay tied together; preferences API accepts **`match_prompt_to_ui`** alongside **`ui_language`** / **`prompt_language`** / **`ui_version`**; login/session/register payloads expose the flag.

- **`diagram_snapshots` migration** ([`alembic/versions/rev_0027_diagram_snapshots_table.py`](alembic/versions/rev_0027_diagram_snapshots_table.py)): idempotent **`CREATE TABLE`** when **`diagram_snapshots`** is missing (indexes **`diagram_id`** / **`user_id`**, unique **`(diagram_id, version_number)`**), aligning deployments where baseline **`create_all`** may already have created the table.

- **Canvas virtual keyboard — shared open state** ([`frontend/src/composables/canvasToolbar/useCanvasVirtualKeyboardOpen.ts`](frontend/src/composables/canvasToolbar/useCanvasVirtualKeyboardOpen.ts), [`frontend/src/composables/canvasToolbar/index.ts`](frontend/src/composables/canvasToolbar/index.ts), [`frontend/src/composables/canvasToolbar/useCanvasToolbarApps.ts`](frontend/src/composables/canvasToolbar/useCanvasToolbarApps.ts)): single **`canvasVirtualKeyboardOpen`** ref for toolbar vs presentation shortcuts; **`ensureCanvasVirtualKeyboardUiVersionSync`** closes the panel when **`uiVersion`** is not **international**.

### Changed
- **Chinese regional prompt shells** ([`utils/prompt_locale.py`](utils/prompt_locale.py), [`agents/core/workflow.py`](agents/core/workflow.py), topic extraction, concept map generation, mind map agent, inline recommendations, node palette generators, relationship labels, thinking-map agents): **`is_chinese_prompt_shell_language()`** replaces naive **`language == "zh"`** for knowledge-base shells and similar blocks; **`output_language_instruction`** resolves **Traditional Chinese** (`zh-tw`, **`zh-hant`**, **`zh-hk`**, **`zh-mo`**) **before** the prompt-output-registry guard so footers stay correct instead of falling through to English.

- **Prompt language registry** ([`data/prompt_language_registry.json`](data/prompt_language_registry.json)): regenerated via **`scripts/build_prompt_language_registry.py`** (frontend **`prebuild`**).

- **Canvas / UI i18n (tier 27)** — broad **`frontend/src/locales/messages/**`** updates (canvas keys and related modules across locales); tooling refreshed ([`frontend/scripts/analyze_i18n_en_parity.py`](frontend/scripts/analyze_i18n_en_parity.py), new parity/check/GAP-fill helpers under **`frontend/scripts/`**); legacy tier‑2 canvas **`*.mjs`** / flat JSON artifacts removed in favor of current pipelines.

- **Canvas UX** ([`frontend/src/components/canvas/CanvasVirtualKeyboardPanel.vue`](frontend/src/components/canvas/CanvasVirtualKeyboardPanel.vue), [`frontend/src/pages/CanvasPage.vue`](frontend/src/pages/CanvasPage.vue), [`frontend/src/composables/canvasPage/useCanvasPageLibrarySnapshots.ts`](frontend/src/composables/canvasPage/useCanvasPageLibrarySnapshots.ts), [`frontend/src/composables/editor/useSnapshotHistory.ts`](frontend/src/composables/editor/useSnapshotHistory.ts)): keyboard panel wiring, library snapshots, snapshot history behavior.

- **Keyboard layout ↔ UI locale** ([`frontend/src/i18n/keyboardLayoutForUiLocale.ts`](frontend/src/i18n/keyboardLayoutForUiLocale.ts), [`frontend/scripts/verify-keyboard-layout-map.ts`](frontend/scripts/verify-keyboard-layout-map.ts), [`frontend/src/i18n/index.ts`](frontend/src/i18n/index.ts), [`frontend/src/i18n/locales.ts`](frontend/src/i18n/locales.ts)): mapping and verification updates aligned with locale bundles.

- **Diagram snapshots API** ([`routers/api/diagrams.py`](routers/api/diagrams.py), [`repositories/diagram_repo.py`](repositories/diagram_repo.py)): listing/rest consistency with persisted snapshots.

- **Dependencies** ([`requirements.txt`](requirements.txt)): pins adjusted.

### Frontend package version
- ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.110.0).

## [5.109.0] - 2026-04-28

### Added
- **Public `robots.txt`** ([`frontend/public/robots.txt`](frontend/public/robots.txt)): `User-agent: *` / `Disallow: /` with a short comment that this is a crawler hint, not a security control.

### Changed
- **Admin dashboard — token rankings and user trends** ([`frontend/src/components/admin/AdminDashboardTab.vue`](frontend/src/components/admin/AdminDashboardTab.vue), [`routers/auth/admin/stats.py`](routers/auth/admin/stats.py), [`routers/auth/admin/stats_trends.py`](routers/auth/admin/stats_trends.py), [`frontend/src/locales/messages/en|zh|zh-tw/admin.ts`](frontend/src/locales/messages/en/admin.ts)): `GET /api/auth/admin/stats` now returns **`top_users_by_tokens_today`** (top 10 users by `TokenUsage` for the **current Beijing calendar day**, with 11-digit phones masked) and scopes **`token_stats_by_org`** to that same **today** window (replacing all-time org totals). Removed **`users_by_org`** from the stats payload. The dashboard shows a Beijing-time hint, a two-column layout (**top schools** / **top users**), and opens **per-user** token series from **`GET /api/auth/admin/stats/trends/user`** when a user row is clicked (modal title uses **`admin.trendUserTokens`**).

- **Admin trends — consistent UTC window for charts** ([`routers/auth/admin/stats_trends.py`](routers/auth/admin/stats_trends.py)): main, organization, and user token trend handlers use a single **`trends_filter_start_utc`** lower bound (including **`days=0` / all-time** where the chart window is bounded, e.g. one year for the global tokens metric) so SQL date filters and cumulative series are not left unbounded when **`start_date_utc`** was previously `None`.

- **School dashboard — organization picker** ([`frontend/src/pages/SchoolDashboardPage.vue`](frontend/src/pages/SchoolDashboardPage.vue)): school selector is **filterable**; option labels show **`name (code)`** for easier search and recognition.

- **Frontend package version** ([`frontend/package.json`](frontend/package.json)): aligned with root **`VERSION`** (5.109.0).

## [5.108.0] - 2026-04-27

### Fixed
- **Node palette SSE — `RuntimeError: No response returned.` / critical alert storm** ([`routers/node_palette_streaming.py`](routers/node_palette_streaming.py), [`services/infrastructure/http/exception_handlers.py`](services/infrastructure/http/exception_handlers.py)): when the frontend aborted `POST /thinking_mode/node_palette/start` (AbortController) before the first LLM token arrived, `asyncio.CancelledError` escaped the generator's `except Exception` block, Starlette's `BaseHTTPMiddleware` raised **`RuntimeError("No response returned.")`**, and the general exception handler flagged it **critical**, firing **SMS alerts** that then failed quota. **Defense in depth**: (1) `stream_node_palette` now yields **`": stream_open\n\n"`** (SSE comment, ignored by `EventSource`) as its first statement so the ASGI `http.response.start` is committed before any `await`; (2) explicit **`except asyncio.CancelledError`** branch logs at `INFO` and re-raises, and the `finally` warning is gated by `not cancelled`; (3) `general_exception_handler` short-circuits `RuntimeError("No response returned")` to **HTTP 204** at `DEBUG` level so real client disconnects never hit the critical-alert path.

- **Concept map — duplicate concurrent `NODE_PALETTE_START` requests / concepts flickering and disappearing** ([`frontend/src/pages/CanvasPage.vue`](frontend/src/pages/CanvasPage.vue), [`frontend/src/pages/mobile/MobileCanvasPage.vue`](frontend/src/pages/mobile/MobileCanvasPage.vue)): the `nodePalette:opened` event listener called `startNodePaletteSession({ mode: 'topic' })` in parallel with [`RootConceptModal.vue`](frontend/src/components/panels/RootConceptModal.vue)'s `onMounted → initializeConceptMapRootModal()` (`bootstrap_domains` + per-tab streams), producing **two racing streams on the same session**, double RAG init, and a visible sequence where concepts appeared then disappeared (each stream cleared `panelsStore.suggestions` via `setNodePaletteSuggestions([])`) and intermittent cancellations. Both desktop and mobile listeners now **early-return for `diagram_type === 'concept_map'`**, leaving `RootConceptModal` as the sole initiator.

- **Concept map bootstrap — redundant suggestion clears** ([`frontend/src/composables/nodePalette/useNodePalette.ts`](frontend/src/composables/nodePalette/useNodePalette.ts)): `initializeConceptMapRootModal` and `addConceptMapDomainTab` called `streamBatch(NODE_PALETTE_START, { bootstrap_domains: true })` without `append`, so [`streamNodePaletteBatch`](frontend/src/composables/nodePalette/streamNodePaletteBatch.ts) wiped `panelsStore.suggestions` before reading the body — even though the bootstrap stream only yields `concept_map_domains` and no node suggestions. `append: true` on both call-sites removes a wasted reactivity flush and, for **Add Domain**, prevents existing tabs' concepts from disappearing until the new tab's stream repopulated.

- **Concept map — concepts streamed then cleared up, required manual refresh** ([`frontend/src/composables/nodePalette/useNodePalette.ts`](frontend/src/composables/nodePalette/useNodePalette.ts)): after bootstrap completed and sequential per-tab streaming began, `streamConceptMapConceptsForTabsSequential` called `streamBatch(..., { append: i > 0, ... })` — so the **first** tab (`i === 0`) ran with `append: false`, which makes [`streamNodePaletteBatch`](frontend/src/composables/nodePalette/streamNodePaletteBatch.ts) fire `panelsStore.setNodePaletteSuggestions([])` **after** `authFetch` resolves but **before** the body is read. If the panel was reopened from a dismissed snapshot (`openNodePalette` restores `snapshot.suggestions` into the store before `RootConceptModal` mounts), the user saw: restored concepts → bootstrap spinner → **visible wipe** the instant tab 0's fetch response landed → loader, then new concepts streamed in if nothing else went wrong. When the user reacted by clicking **Refresh** (`refreshConceptMapRootModal`) it worked because refresh explicitly aborted streaming, called `clearNodePaletteSession`, `setNodePaletteSuggestions([])`, `updateNodePalette({ conceptMapTabs: undefined, mode: null })`, reset `sessionId`, and only then re-invoked `initializeConceptMapRootModal` — i.e. it did the cleanup the initial path was missing. **Fix**: (1) `streamConceptMapConceptsForTabsSequential` now passes `append: true` for **every** tab, so no mid-flight clear ever fires during per-tab streaming; (2) `initializeConceptMapRootModal`'s bootstrap branch now wipes stale state **once, up front** via `setNodePaletteSuggestions([])` + `updateNodePalette({ conceptMapTabs: undefined, mode: null })`, matching what refresh does and guaranteeing a clean store before the bootstrap stream opens; (3) a re-entrance guard (`if (isLoading.value) return false`) at the top of `initializeConceptMapRootModal` prevents `RootConceptModal.onMounted` from launching a second racing initialize when the modal re-mounts while a previous run is still streaming.

- **`concept_generation` activity log — orphan and duplicate rows** ([`routers/node_palette.py`](routers/node_palette.py)): the teacher-usage log was written before topic validation and on **every** per-tab stream request, producing orphan rows on HTTP 400 paths and multiple rows per user action. Logging now runs **only** when `diagram_type == "concept_map"` **and** `stage_data.bootstrap_domains == True`, **after** topic validation — one row per "Generate Concepts" / "Add Domain" click.

### Changed
- **Node palette — skip RAG enhancement** ([`agents/node_palette/base_palette_generator.py`](agents/node_palette/base_palette_generator.py), [`agents/node_palette/concept_map_palette.py`](agents/node_palette/concept_map_palette.py)): both node-palette LLM call-sites (`llm_service.stream_progressive` in `BasePaletteGenerator.generate_batch` and `llm_service.chat` in `ConceptMapPaletteGenerator._generate_domain_labels`) now pass **`use_knowledge_base=False`**. Node palette generates concept labels from a topic, not answers against the user's knowledge base, so the prior default of `True` was initializing **Qdrant**, **DashScope embedding/rerank**, **KeywordSearch**, **KBRateLimiter**, and **RAGService** on every palette click and running a per-LLM `has_knowledge_base` DB query on every batch. All diagram-specific palettes (`brace_map`, `bridge_map`, `bubble_map`, `circle_map`, `double_bubble_map`, `flow_map`, `mindmap`, `multi_flow_map`, `tree_map`) inherit the fix via `BasePaletteGenerator`.

### Added
- **Palette session idle-TTL sweep** ([`agents/node_palette/base_palette_generator.py`](agents/node_palette/base_palette_generator.py)): new `session_last_seen` tracking plus `_sweep_stale_sessions` evicts session entries from `generated_nodes`, `seen_texts`, `session_start_times`, `session_last_seen`, and `batch_counts` after **`SESSION_IDLE_TTL_SECONDS = 3600`** (60 min) of inactivity. Sweep is opportunistic — runs at most every **`SESSION_SWEEP_INTERVAL_SECONDS = 300`** (5 min) from `generate_batch` — so the in-memory dicts no longer grow unbounded when users close their browser tab, lose connection, or skip the explicit `/thinking_mode/node_palette/cleanup` endpoint. Safe against mid-stream eviction: the batch that triggers the sweep updates `session_last_seen` first, and the sweep is synchronous within a single asyncio step.

## [5.107.0] - 2026-04-27

### Added
- **Chrome extension (MV3)** ([`chrome-extension/`](chrome-extension/)): shared helpers [`shared-mindgraph.js`](chrome-extension/shared-mindgraph.js) (`importScripts` + popup); default **Base URL** `https://mg.mindspringedu.com`; single **Language** control for **UI** and **mind map** `language` on `POST /api/web_content_mindmap_png` ([`routers/api/web_content_generation.py`](routers/api/web_content_generation.py)); **API token** validity hint via `GET /api/auth/api-token` ([`routers/auth/personal_token.py`](routers/auth/personal_token.py)); optional **PNG width/height**; keyboard command **generate-mindmap**; [`background.js`](chrome-extension/background.js) **service worker** runs page capture, PNG `fetch`, and `chrome.downloads` (toolbar uses **`runtime.connect`** with name **`mindmap-generate-<tabId>`** for live progress; context menu and keyboard use the same worker path); richer page capture (`itemprop=articleBody`, `role=article`, …). Node smoke test [`chrome-extension/test/shared-mindgraph.test.cjs`](chrome-extension/test/shared-mindgraph.test.cjs).

### Fixed
- **Chrome extension popup** ([`chrome-extension/popup.js`](chrome-extension/popup.js)): `setProgressStage` is defined at **module** scope (was only inside `startPopup`); the old **popup-only** generate path called it from a scope where it was not defined, causing **ReferenceError** and a misleading “connection closed” / `errPortDisconnected` string.

- **Chrome extension — Generate vs page focus** ([`chrome-extension/background.js`](chrome-extension/background.js), `popup.js` **manifest 0.3.7**): Focusing the page closes the **popup** (normal browser behavior) and was tearing down the in‑flight **`fetch`** when generation ran in the popup. The **long request and `downloads.download` now run only in the service worker**; the popup **connects** a port for progress/result, and a **notification** is shown on success or failure if the result could not be posted to a closed port. **0.3.7**: encode **active `tabId`** in the connect **`name`** (`mindmap-generate-<id>`) so generation **starts inside `onConnect`**; avoids a race where the worker could sit idle and miss the first **`postMessage`**, which looked like a progress **flash** and no download.

- **Chrome extension — PNG download href (MV3 service worker)** ([`chrome-extension/background.js`](chrome-extension/background.js), [`offscreen.html`](chrome-extension/offscreen.html) / [`offscreen.js`](chrome-extension/offscreen.js), **manifest 0.3.8+**, **`offscreen`** permission): **Root cause** of **TypeError: `URL.createObjectURL` is not a function** is platform policy: **blob `URL`s from `URL.createObjectURL` are not part of the service worker surface** for Blobs in standard Chromium and many docs list **offscreen** reason **`BLOBS`** as the right place. **Root cause** of **`offscreen_unavailable`** was gating on **`chrome.offscreen` only**; some Chromium builds expose **`globalThis.browser.offscreen`** or no offscreen at all. **Fix**: **`prepareDownloadUrlFromPngBlob`** tries **(1)** rare native SW path with **try/catch**, **(2)** `getOffscreenApi()` then offscreen, **(3)** **`FileReader` → data URL** in the worker. Locale key **`errDownloadPrepare`**; manifest **0.3.10** for the sweep (comments + i18n rename + try/catch on step 1).

### Changed
- **Web content mind map — user message locale** ([`utils/prompt_locale.py`](utils/prompt_locale.py) `build_web_page_content_user_block`, [`agents/mind_maps/web_content_mind_map_agent.py`](agents/mind_maps/web_content_mind_map_agent.py)): simplified vs traditional Chinese shells for the LLM user block; non-English, non-Chinese API languages use English placeholders (fixes legacy “Chinese placeholders for all non-`en`” behavior). **Traditional Chinese output** meta-instruction now includes **`zh-hk`** and **`zh-mo`** with **`zh-hant` / `zh-tw`** in [`output_language_instruction`](utils/prompt_locale.py).

- **Extension README** ([`chrome-extension/README.md`](chrome-extension/README.md)): documents language model, default URL, `api-token`, `shared-mindgraph`, and generate flow (service worker for PNG + `mindmap-generate-<tabId>` connect for toolbar progress; notifications when the port is gone).

## [5.106.0] - 2026-04-27

### Changed
- **Lint and formatting (repo-wide)**: Frontend **ESLint** + **Prettier** clean (`npm run lint`, `npm run format:check`); Python **Ruff** (`ruff check`, `ruff format`) and **Pylint** (10.00/10). TypeScript: vue-i18n third-argument `locale` uses `String(...)` instead of `as any`; `AdminMindBotTab` exposes `openManagerMindbot` for school-manager flows; presentation mode keyboard shortcut avoids a non-null assertion; router guard drops unused `useUIStore()`; `MindmateHeader` drops an unused `ElTooltip` import.

## [5.105.0] - 2026-04-27

### Added
- **Admin — DingTalk image generation API keys** (`AdminDingtalkGenerationApiKeysDialog.vue`, `AdminTokensTab.vue`, `components.d.ts`, `admin-mindbot-swiss-api-keys.css`, `admin-mindbot-swiss-dialog-chrome.css`, `admin-mindbot-swiss-messagebox.css`, `locales/messages/en|zh/admin.ts`): dialog to list, create, and delete **X-API-Key** rows (via `GET/POST/DELETE` admin API key routes) for public generation endpoints such as `/api/generate_dingtalk`; shared Swiss-styled styles for the dialog and message boxes. **Tokens** tab adds a **DingTalk image generation** card next to the overall token summary (sums **`usage_count`** from keys; click/focus opens the dialog; refreshes when the dialog closes or token stats reload).

### Changed
- **Admin token stats — DingTalk generation counts** (`routers/auth/admin/stats.py`): `GET /api/auth/admin/token-stats` includes **`dingtalk_generations`** with **today** / **week** / **month** / **total** counts of successful `TokenUsage` rows for **`POST /api/generate_dingtalk`** (PNG + markdown image flow).
- **Admin MindBot config dialog** (`AdminMindBotConfigDialog.vue`): refactored and shortened while keeping the terminal-style MindBot create/edit experience (DingTalk, Dify, usage).
- **Frontend build** (`frontend/vite.config.ts`): broader **`manualChunks`** splits (e.g. **@element-plus/icons-vue**, echarts, Chart.js, **@vue-flow**, katex, highlight.js, mathlive, jspdf, markdown stack, **html-to-image**, simple-keyboard, axios) to improve caching and avoid oversized single vendor chunks; **`chunkSizeWarningLimit`** set to **1000** with updated rationale.

## [5.104.0] - 2026-04-26

### Added
- **School dashboard — org-scoped user management** (`routers/auth/admin/school_users.py`, `routers/auth/admin/school_scope.py`, `SchoolDashboardPage.vue`, `SchoolDashboardUsersTab.vue`, `locales/messages/en|zh/admin.ts`, `components.d.ts`): list/search, detail, update (name/phone with DB-session phone uniqueness), unlock, and delete for users in a single organization. Admins pass **`organization_id`**; **managers** are fixed to their org and cannot cross orgs (403 on mismatch). List responses include per-user **token usage** aggregates when `TokenUsage` is available.
- **Structured school-dashboard logging** (`services/auth/school_dashboard_logger.py`): `LoggerAdapter` and **`school_dashboard_extra`** inject stable **`sd_*`** fields (`sd_event`, `sd_actor_id`, `sd_org_id`, `sd_target_user_id`) for JSON log pipelines.
- **Phone uniqueness in the same DB session** (`services/auth/phone_uniqueness.py`): `any_user_id_with_phone` and `other_user_id_with_phone` for inserts/updates that must race safely with the ORM.
- **User delete — FK cleanup** (`services/auth/user_fk_cleanup.py`, `routers/auth/admin/users.py`, school delete): shared routine to nullify or remove dependent rows (diagrams, community, library, token usage, mindbot links, etc.) before deleting a user row; reused by platform admin and school dashboard delete.
- **HTTP API error text for toasts** (`frontend/src/utils/httpErrorDetail.ts`): normalizes FastAPI **`detail`** (string or Pydantic validation list) for **Element Plus** notifications.

### Changed
- **School statistics & token trends** (`routers/auth/admin/stats.py`, `stats_trends.py`, `organizations.py`): school endpoints use **`resolve_school_dashboard_org_id`** and structured logging; org listing tweaks where needed for the dashboard.
- **Auth and registration** (`routers/auth/helpers.py`, `login.py`, `password.py`, `phone.py`, `quick_register.py`, `registration.py`, `registration_overseas.py`, `sms.py`): refactors and shared handling aligned with the new user-management paths.
- **MindBot admin** (`routers/api/mindbot_admin.py`, `routers/api/mindbot_helpers.py`): helper and routing adjustments.
- **Domain messages** (`models/domain/messages.py`): i18n keys for school dashboard scope and school user errors.

### Fixed
- **Alembic `login_password_set`** (`alembic/versions/rev_0025_user_login_password_set.py`): boolean column **`server_default`** uses PostgreSQL’s **`true`** literal; **downgrade** no longer has an empty body.

## [5.103.0] - 2026-04-26

### Added
- **User `login_password_set` (DB + domain)** (`alembic/versions/rev_0025_user_login_password_set.py`, `models/domain/auth.py`): boolean on **`users`** (defaults **true** for existing rows). Quick registration creates users with **`login_password_set = false`** until the user sets a known login password, so the product can show **set password** instead of **change password** for those accounts.
- **Set login password with SMS while logged in** (`routers/auth/password.py`, `models/requests/requests_auth.py`, `SetPasswordWithSmsModal.vue`, locales): SMS + captcha flow that does **not** revoke the session; success sets **`login_password_set`** to **true** (with cache invalidation consistent with other password writes).
- **Safe post-auth redirect** (`frontend/src/utils/authRedirect.ts`): **`getSafePostAuthPath`** for `/auth?redirect=…` and post quick-registration navigation — only allows same-origin, path-style targets (rejects `//`, `://`, control characters, oversized strings) to avoid open redirects.
- **Auth & account UI** (`AuthPage.vue`, `AccountInfoModal.vue`, `AppSidebarAccountFooter.vue`, `MobileAccountPage.vue`, `AuthQuickRegisterModal.vue`, `components/auth/index.ts`, `auto-imports` / `components.d.ts`): surfaces **`login_password_set`** from the session store and drive **set password** prompts; **`IntlShareSiteModal.vue`** is a back-compat wrapper around **`QuickRegisterModal.vue`**.

### Changed
- **Session and Redis user cache** (`routers/auth/session.py`, `services/redis/cache/redis_user_cache.py`, `frontend/src/stores/auth.ts`, `frontend/src/types/auth.ts`): API session JSON and cached user fields include **`login_password_set`**. Password set/change/reset paths that assign a new hash set the flag to **true** (`routers/auth/password.py` and related success handlers).
- **Quick registration** (`routers/auth/quick_register.py`, `models/domain/messages.py`, `routers/auth/*` wiring): user insert sets **`login_password_set = false`** for room-quick accounts.
- **Typography helper** (`frontend/src/utils/diagramNodeFontStack.ts`): **`APP_REFINED_SANS_STACK`** for compact surfaces (e.g. quick registration) on top of the existing multiscript diagram stack.

## [5.102.0] - 2026-04-25

### Added
- **Quick registration — room code key in Redis (no env HMAC)** (`services/auth/quick_register_redis.py`, `services/auth/quick_register_room_code.py`, `routers/auth/quick_register.py`, `env.example`, `CHANGELOG`): per-mint **`room_code_secret`** in the Redis token JSON drives the 6-digit HMAC; **`QUICK_REG_ROOM_HMAC_KEY` removed**; legacy token keys without the field are **migrated on read** (remaining TTL). **Lifespan** no longer checks that env var.
- **Quick registration — ops, API, and UI polish** (`services/monitoring/registration_metrics.py`, `routers/auth/quick_register.py`, `frontend/.../QuickRegisterModal.vue`, `AuthQuickRegisterPanel.vue`, locales, `env.example`): metrics for **Redis token delete failure after a successful commit** and for **register-quick 429** (ip / phone / room-guess); **GET `/api/auth/quick-register/room-code`** includes **`signups_count`** and optional env **`QUICK_REG_ROOM_GET_*`** for per-IP and per-token rate limits; workshop **`refresh_workshop_channel_ttl`** skips minter `EXPIRE` when `created_by_user_id <= 0`. Facilitator modal is **QR-only** (no visible URL or copy) with a **TOTP-style countdown ring** and **session signup count** in workshop mode; attendee probe distinguishes **429** (rate limit) from **400** (invalid link).
- **PostgreSQL client binaries** (`services/utils/pg_client_binaries.py`): single `find_pg_client_binary` implementation for `pg_dump` and `pg_restore` (honors `PG_BIN_DIR`, searches common Linux versioned paths, falls back to `which` / `where` on PATH).

### Changed
- **Quick registration (breaking API)** (`routers/auth/quick_register.py`, `services/auth/quick_register_redis.py`, `services/auth/quick_register_room_code.py`, `models/requests/requests_auth.py`): `POST /api/auth/register-quick` no longer uses SMS; request body uses **`room_code`** instead of `sms_code`. **`GET /api/auth/quick-register/room-code`** returns the current 6-digit rotating code for a token. **`POST /api/auth/quick-register/open`** accepts optional **`channel_type`** (`single_use` | `workshop`) and optional **`max_uses`** (capped to **`WORKSHOP_MAX_USES_CAP`**, same as the API model). Optional env **`QUICK_REGISTER_IP_MAX`**, **`QUICK_REGISTER_IP_WINDOW`**, **`QUICK_REGISTER_PHONE_MAX`**, **`QUICK_REGISTER_PHONE_WINDOW`** tune rate limits. Success audit / activity tracking uses log method **`room_quick`** (not SMS). [AuthQuickRegisterPanel.vue](frontend/src/components/auth/AuthQuickRegisterPanel.vue) is phone + room code only and optionally **GET**-checks the token on load; [QuickRegisterModal.vue](frontend/src/components/mindgraph/QuickRegisterModal.vue) shows the code and optional workshop options. [env.example](env.example) documents the product tradeoff (room code = in-session presence, not phone verified by SMS) and optional tuning.
- **Admin / database dump & import** (`routers/admin/database.py`, `services/admin/database_export_service.py`, `scripts/db/dump_import_postgres.py`): connection URIs for CLI tools use `libpq_database_url(DATABASE_URL)` from `config.database` (no duplicate env default); backup folder listing and import validation only treat **`mindgraph.postgresql`.*`.dump** files as app exports. CLI import runs **`init_db(seed_organizations=False)`** after `pg_restore` so Alembic brings the schema in line with the current ORM; dump timestamps and manifest `timestamp` use **UTC**; import progress includes an **Alembic upgrade** stage.
- **Scheduled backups** (`services/utils/backup_scheduler.py`): relative `BACKUP_DIR` is resolved from the project root; `pg_dump` uses **`-Fc` with `--no-owner`** to match admin export; `pg_dump` / `pg_restore` resolution delegates to the shared binary helper (including Windows `where`).
- **PG merge** (`services/admin/pg_merge_service.py`): app DB URL uses `DATABASE_URL` from config; `pg_restore` path from `find_pg_client_binary`.
- **CLI dump script** (`scripts/db/dump_import_postgres.py`): `find_pg_binary` aliased to the shared `find_pg_client_binary`.

### Fixed
- **SQLite → PostgreSQL merge** (`services/admin/sqlite_merge_service.py`): safer defaults and fallbacks for NOT NULL / legacy data — user booleans, `ui_version`, `email`, org `is_active`, user API key columns, `failed_login_attempts` / `role` / `created_at`, dashboard activity `action` / `diagram_type` / `created_at`, update-notification `dismissed_at`; boolean column metadata limited to **`public`** schema; rows missing required `user_id`+`version` for update-notification dismissals are skipped.

## [5.101.0] - 2026-04-23

### Added
- **Frontend / `.mg` interchange v1.1** (`frontend/src/utils/mgInterchange.ts`, `useDiagramExport.ts`, `useDiagramImport.ts`): encrypted diagram export uses a typed **`MG` + major/minor** header (v1.1) with AES-256-GCM; import still accepts legacy **`MG1`** payloads and rejects plain JSON masquerading as `.mg`.
- **Frontend / Concept map — link handle hit-testing** (`conceptMapLinkChaseState.ts`, `useDiagramCanvasConceptMapLink.ts`, `CurvedEdge.vue`, `ConceptNode.vue`): shared **`data-mg-concept-link-handle`** attribute and `conceptMapLinkChaseActive` ref for reliable handle detection (including mobile); relationship link-drag logic expanded accordingly.

### Changed
- **Inline recommendations — prompts & context** (`agents/inline_recommendations/context_extractors.py`, `prompts/__init__.py`): richer per-diagram context extraction and prompt wiring aligned with Tab-triggered SSE completion.
- **Frontend / Inline recommendations** (`useInlineRecommendations.ts`, `useInlineRecommendationsCoordinator.ts`, `inlineRecEligibility.ts`, `nodePalette/constants.ts`, `useNodePalette.ts`, `AIModelSelector.vue`, `DiagramCanvas.vue`): coordinator and eligibility rules refined; palette/constants updated; AI model strip integrates inline-rec state; canvas wiring adjusted for Tab sessions and multi-model results.
- **Frontend / Diagram canvas** (`useDiagramCanvasContextMenu.ts`, `useDiagramCanvasEventBus.ts`, `useDiagramCanvasFit.ts`, `useDiagramCanvasMobileTouch.ts`, `useEventBus.ts`): pane/touch and fit behaviour tuned; mobile touch handling extended; event-bus typings/events adjusted.
- **Frontend / Canvas & shell** (`CanvasPage.vue`, `CanvasTopBar.vue`, `MobileCanvasPage.vue`, `MobileHomePage.vue`, `RootConceptModal.vue`, `AppSidebarAccountFooter.vue`, `canvasBackNavigation.ts`, `saveConfig.ts`, `specIO.ts`): desktop and mobile canvas pages updated; root-concept modal and account footer tweaks; back-navigation and save/spec IO small fixes.
- **Frontend / i18n (canvas)** (`locales/messages/*/canvas.ts`): canvas strings refreshed across locale bundles for new UI copy.

## [5.100.0] - 2026-04-23

### Added
- **Frontend / Concept map — drag link from relationship label** (`conceptMapLinkMime.ts`, `CurvedEdge.vue`, `ConceptNode.vue`, `useDiagramCanvasConceptMapLink.ts`, `conceptMapLinkPreviewGeometry.ts`, `connectionManagement.ts`, `types/diagram.ts`, `types/vueflow.ts`): relationship edges now expose a **drag handle icon** (shown when the edge is selected) that lets users drag from the relationship label to create a new connection; dropping on an **existing concept node** links the nearer relationship endpoint to the target; dropping on the **canvas** creates a new concept node and links it automatically. The anchor endpoint (source or target of the original relationship) is chosen by proximity. New connections created this way use `linkedFromConnectionId` to route their bezier path visually from the parent label position (`CurvedEdge` reads the parent label's live midpoint). New `conceptMapLinkMime.ts` module centralises both MIME type constants and the `RelationshipLinkDragPayload` type; `addConnection` accepts an optional `extra` argument carrying `linkedFromConnectionId`, `arrowheadDirection`, and `arrowheadLocked`. Two new geometry helpers `pickAnchorNodeIdForRelationshipToNewConcept` and `pickAnchorNodeIdForRelationshipToExistingNode` compute the optimal anchor by distance.
- **Frontend / Concept map — relationship (edge) selection** (`diagram.ts`, `diagram/selection.ts`, `diagram/types.ts`, `DiagramCanvas.vue`, `CurvedEdge.vue`, `vueFlowIntegration.ts`): clicking a relationship edge or its label now **selects** it (tracked in new `selectedConnectionId` ref, mutually exclusive with node selection); selected edges display a blue outline on their label and surface the relationship-drag handle; `selectConnection` / `clearSelection` / `addToSelection` and all node-move ops clear the connection selection; Vue Flow edges are marked `selectable: true` for concept maps with `selected` synced from store.

### Fixed
- **Frontend / Concept map — focus review skips default focus question** (`conceptMapFocusReview.ts`): `isFocusTopicReady`, `updateFocusTopic`, `triggerFocusTopicReview`, and `loadMoreSuggestions` now guard against the default "Focus question: …" template label via `isDefaultFocusQuestionLabel`, preventing the focus-review tab badge and AI suggestions from firing on untouched template text.

## [5.99.0] - 2026-04-22

### Added
- **Frontend / Canvas — entry-aware back navigation** (`frontend/src/utils/canvasBackNavigation.ts`, `frontend/src/router/index.ts`, `CanvasTopBar.vue`, `MobileLayout.vue`): session storage records the route that opened `/canvas` or `/m/canvas`; **Back** uses browser history when the user came from a MindGraph landing path, otherwise **replace** navigates to the MindGraph hub (desktop `MindGraph` route, mobile `/m/mindgraph`) so the stack does not accumulate duplicate entries.

### Changed
- **Frontend / Concept map — focus question editing** (`InlineEditableText.vue`, `ConceptNode.vue`, `diagramDefaultLabels.ts`): focus-topic labels use a split-edit mode — fixed i18n **prefix**, editable **body**, and language-aware placeholder **suffix**; `stripConceptMapFocusQuestionPrefix` also strips a legacy ASCII-colon Simplified Chinese prefix; `isDefaultFocusQuestionLabel` treats the legacy default string as default; new concept map templates start with **empty** `concepts` / `relationships` arrays (`defaultTemplates.ts`).
- **Frontend / Concept map — viewport & presentation** (`useDiagramCanvasFit.ts`, `CanvasPage.vue`, `MobileCanvasPage.vue`, `useCanvasPagePresentation.ts`): initial **fit-to-view** is off for concept maps (default zoom/center instead); panel open/close, node palette, and presentation-rail toggles **skip refit** on concept maps; closing the presentation rail no longer triggers an extra fit on concept maps.
- **Frontend / Mobile canvas routing** (`useAppSidebar.ts`, `useDiagramAutoSave.ts`, `router/index.ts`): `/m/mindgraph` and `/m/canvas` are treated as MindGraph mode in the sidebar; first successful save **replace**s to the mobile canvas path when already on mobile; authenticated users hitting **guest-only** routes on mobile redirect to **`/m`** instead of MindMate.
- **Frontend / i18n (zh)** (`locales/messages/zh/canvas.ts`): concept map focus question prefix uses a fullwidth colon (**：**).

### Removed
- **Frontend / Admin Performance** (`AdminPerformanceTab.vue`): removed the **LLM** metrics table block (per-model requests / success / circuit columns).

## [5.98.0] - 2026-04-22

### Added
- **Admin / Performance — live metrics** (`routers/auth/admin/performance.py`, `routers/auth/admin/__init__.py`, `services/infrastructure/monitoring/*streaming*.py`, `services/redis/keys.py`): **platform-admin only** `GET /api/auth/admin/performance/live` (`require_admin`, 403 otherwise). Returns host compute/network/disk, merged process CPU/RSS, Redis memory snapshot, WebSocket + activity stats, LLM per-model snapshot, app version/uptime, cross-worker merge from Redis worker snapshots, **`mindbot_ai_card_streaming`** (live DingTalk card / Dify SSE count + 24h concurrent high from UTC hourly keys in Redis), and **`mindmate_streaming`** (live `/api/ai_assistant/stream` count + same 24h pattern). Background worker perf heartbeat republishes per-uvicorn snapshots to Redis; each subsection uses short timeouts. MindMate stream counting hooks in `routers/api/sse_streaming.py` (`mindmate_streaming_begin` / `end` in the SSE generator `finally`).
- **Frontend / Admin Performance** (`AdminPerformanceTab.vue`, `usePerformanceLive.ts`, `AdminPage.vue`, `admin-performance-cards.css`, locale `en`/`zh` `admin.ts` + materialized bundles): **Performance** tab (platform admins) with Swiss-style metric cards, Redis/sessions and **MindBot + MindMate streaming** side-by-side, LLM table when present, ~2s poll, pause on navigate/unmount; i18n under `admin.performance*`.

## [5.96.0] - 2026-04-22

### Added
- **Admin / Schools — managers column** (`AdminSchoolsTab.vue`): schools table shows each organization’s manager display names (comma-separated); the cell remains clickable to open the existing trend/detail modal.

### Changed
- **MindBot admin API — mutating routes platform-admin only** (`routers/api/mindbot_admin.py`): create, update, delete, and rotate public callback token now use `require_admin` instead of `require_mindbot_admin_access`, so only platform administrators can change or remove configs and rotate tokens (list/read/analytics paths unchanged).
- **Frontend / MindBot admin — manager read-only** (`AdminMindBotTab.vue`, `en/admin.ts`, `zh/admin.ts`): organization managers see a read-only summary (bot label, masked robot code, per-bot callback URL with copy, enabled flag) plus empty-state and intro copy; `AdminMindBotConfigDialog` is mounted only for platform admins.
- **Admin organizations API** (`routers/auth/admin/organizations.py`): `GET /admin/organizations` adds a `managers` array (ordered display names) per school alongside `manager_count`; org user and manager listings use safer masking when `phone` is missing and fall back to email for display names where appropriate.
- **Admin roles** (`routers/auth/admin/roles.py`): admin list aligns phone masking with the same missing-phone / email fallback behavior.

## [5.95.0] - 2026-04-21

### Added
- **MindBot admin — move config between orgs** (`routers/api/mindbot_admin.py`, `routers/api/mindbot_models.py`, `services/mindbot/errors.py`): new `POST /admin/configs/{config_id}/move` reassigns a bot configuration row to another organization (platform admins). Validates destination org exists, rejects same-org moves with `MINDBOT_ADMIN_MOVE_SAME_ORGAN`, and enforces the per-org bot cap on the target (excluding the moving row from the destination count). New payload type `MindbotMovePayload`.
- **Presentation mode — keyboard shortcuts** (`frontend/src/composables/canvasPage/useCanvasPagePresentation.ts`, `frontend/src/composables/core/useEventBus.ts`): while the presentation rail is open, **Ctrl/Cmd+1–5** select laser, highlighter, pen, spotlight, and timer in order; **Ctrl/Cmd+6** emits `presentation:toggle_virtual_keyboard_requested` for the virtual keyboard toggle.

### Changed
- **MindBot / DingTalk AI card streaming cap — default 6500** (`models/domain/mindbot_config.py`, `routers/api/mindbot_models.py`, `services/mindbot/platforms/dingtalk/cards/ai_card_create.py`, `alembic/versions/rev_0024_mindbot_ai_card_streaming_default_6500.py`): ORM default, OpenAPI field defaults, and `DEFAULT_DINGTALK_AI_CARD_STREAMING_MAX_CHARS` aligned to **6500** characters (was 6000). Alembic `0024` updates only the **server default** on `organization_mindbot_configs.dingtalk_ai_card_streaming_max_chars`; existing rows keep their stored values.
- **Frontend / MindBot admin** (`AdminMindBotConfigDialog.vue`, `AdminMindBotTab.vue`, `en/admin.ts`, `zh/admin.ts`): admin UI for moving a bot between schools and for the **6500** streaming max-chars default in forms and create payloads.
- **Frontend / canvas & shell** (`PresentationSideToolbar.vue`, `CanvasTopBar.vue`, `MindGraphContainer.vue`, `InternationalLanding.vue`, `MindmatePanel.vue`, `MindmateHeader.vue`, sidebar components, `MainLayout.vue`, `LanguageSettingsModal.vue`, `CanvasPage.vue`, `router/index.ts`, and locale bundles): presentation rail and layout refinements; international landing and Mindmate panel updates; sidebar navigation/account adjustments; i18n string sync across `common` (and related) locale files.

## [5.94.0] - 2026-04-21

### Added
- **MindBot / multi-bot per org** (`models/domain/mindbot_config.py`, `repositories/mindbot_repo.py`, `routers/api/mindbot_admin.py`, `routers/api/mindbot_models.py`, `alembic/versions/rev_0023_mindbot_multi_bot_per_org.py`): each organization can now have up to **5** independent MindBot configurations. The `organization_id` unique constraint on `organization_mindbot_configs` is dropped and replaced with a plain index; a new `bot_label` column (varchar 64, nullable) lets admins distinguish bots for the same school. `MindbotConfigCreatePayload` is split out as a create-only model (carries `organization_id`); `MindbotConfigPayload` (PUT) keeps `dingtalk_app_secret` / `dify_api_key` optional so existing secrets are preserved on update. Repository gains `get_by_id`, `list_by_organization_id`, `count_by_organization_id`, and `_BOT_CAP_PER_ORG = 5`; `list_all` pagination cursor changes from `after_org_id` to `after_id` (config PK). All admin CRUD endpoints are now keyed by config `id` instead of `organization_id`.
- **Frontend / MindBot admin UI — multi-bot support** (`AdminMindBotTab.vue`, `mindbotConfigTypes.ts`, `en/admin.ts`, `zh/admin.ts`): org-select computed switched from `orgsWithoutConfig` to `orgsUnderLimit` (counts per org, permits up to 5); `save()` split into `createConfig()` / `updateConfig()` keyed by `editingConfigId` (config PK); `loadAllConfigs()` cursor-paginates with `after_id`; table gains a **Bot label** column; dialog create header changed from "Add school" to "Add bot"; `bot_label` wired through types, form state, and payload.
- **Frontend / MindBot config dialog — required field indicators** (`AdminMindBotConfigDialog.vue`): required fields now display a red `*` prefix using Element Plus `required` prop: **DingTalk Robot Code** and **Dify Base URL** are always marked; **DingTalk App Secret** and **Dify API Key** are marked on create or when in replace mode; **Organization** select is marked on admin create. Asterisk color overridden to `#fb7185` to match the dialog's dark theme.

### Fixed
- **HTTP exception handlers** (`services/infrastructure/http/exception_handlers.py`): new `client_disconnect_handler` for `starlette.requests.ClientDisconnect` — returns 204 and logs at DEBUG level instead of propagating a 500; common under load tests or when callers time out early.
- **Dify client** (`clients/dify.py`): `AsyncDifyClient` now accepts HTTP 201 alongside 200 as a success response, preventing false-positive errors on Dify create endpoints.
- **Blocklist scheduler / AbuseIPDB service** (`services/infrastructure/security/abuseipdb_scheduler.py`, `abuseipdb_service.py`): `_log_blocklist_scheduled_abuseipdb_summary()` helper emits a single structured INFO line with IP counts for both AbuseIPDB and CrowdSec after each scheduled sync; failed states now log at WARNING instead of DEBUG; a CrowdSec partial-failure that occurs after a successful AbuseIPDB store is propagated as `crowdsec_failed` in the result dict and logged immediately.

## [5.93.0] - 2026-04-20

### Added
- **MindBot / pipeline — send tracker & full-reply fallbacks** (`services/mindbot/pipeline/send_tracker.py`, `dify_paths.py`, `outbound/text.py`, `context.py`, `callback.py`, `redis_keys.py`, `ai_card_state.py`): Redis hash `mindbot:send_track:{msg_id}` with TTL 2 h records `sending` → `error` / `complete` (`status`, `ts`, `err_detail`); `DifyReplyContext.msg_id` wires DingTalk message id from the callback. `send_full_reply()` sends a single final message with `stream_chunk=False` (markdown / `sampleMarkdown`). `CardStreamState.plain_fallback_pending` replaces the earlier `qps_exhausted` flag and covers every AI-card mid-stream error path plus QPS exhaustion: accumulate SSE silently, wait 5 s, then one full markdown reply; cross-org buffer uses `send_full_reply` without delay; AI-card finalize failure retries with full `reply_text` + delay. When `send_full_reply` fails, the tracker records either `{route}_dingtalk_token_failed` or `{route}_send_failed` for `cross_org`, `plain_fallback`, and `finalize_fallback` routes so token outages are distinguishable from generic outbound failures.
- **`requirements.txt`**: `anyio>=4.0.0` added to support async-compatible I/O primitives used by the updated embedding and chunking paths.

### Changed
- **Async / Phase 7 — thread-to-asyncio sweep**: eliminated remaining `threading.Thread`, `threading.Lock`, and `run_coroutine_threadsafe` bridges across the hot path; everything now runs natively on the event loop.
  - **`agents/core/llm_clients.py`**: `LLMTimingStats` migrated from `threading.Lock` to `asyncio.Lock`; `_LegacyLLMStub.invoke`, `add_call_time`, `get_stats`, and `get_llm_timing_stats` are now `async def`; the `asyncio.get_event_loop()` / `run_until_complete` workaround removed.
  - **`agents/concept_maps/concept_map_generation.py`**: parallel key-part fetching converted from `ThreadPoolExecutor` + `as_completed` to `asyncio.gather` with an `asyncio.Semaphore(6)` cap; `_invoke_llm_prompt`, `generate_concept_map_two_stage`, and `fetch_parts` are all `async def`; `concurrent.futures` import removed.
  - **`clients/dashscope_embedding.py`**: `_make_request` converted to `async def`; sync `httpx.Client` replaced with `httpx.AsyncClient` (one client reused across all retry attempts); `time.sleep` replaced with `asyncio.sleep`; `_normalize_embeddings` extracted as a private helper to reduce nesting.
  - **`clients/llm/dashscope.py`**: `QwenClient` non-streaming and streaming paths now obtain a shared pooled `httpx.AsyncClient` from `get_httpx_manager().get_client("qwen", …)` instead of creating a new client per request; connection-setup overhead and OS socket churn eliminated on the LLM hot path.
  - **`services/knowledge/chunking_service.py`**: `MindChunkAdapter` gains a native `chunk_text_async` method that `await`s the LLM chunker directly; the synchronous `chunk_text` entry point delegates via `asyncio.run()` for callers that cannot use async; the previous `asyncio.get_event_loop()` / `loop.run_until_complete()` bridge with its silent new-loop fallback is removed.
  - **`services/llm/qdrant_service.py`**: `QdrantService` migrated from sync `qdrant_client.QdrantClient` to `AsyncQdrantClient`; `create_user_collection`, `get_user_collection`, and all downstream methods are now `async def`.
  - **`services/llm/qdrant_diagnostics.py`**: `QdrantDiagnosticsMixin.get_compression_metrics` and `get_diagnostics` converted to `async def`; all `self.client.*` calls are now `await`ed against `AsyncQdrantClient`.
  - **`services/features/ws_redis_fanout_listener.py`**: daemon thread + `run_coroutine_threadsafe` bridge replaced with a supervised `asyncio.Task` using `redis.asyncio` native pub/sub; push-based delivery eliminates the previous 500 ms polling sleep; automatic reconnection on error with a configurable `_RECONNECT_DELAY` (2 s default); `threading` import removed.
- **Pylint / code quality sweep**: removed all remaining `# pylint: disable=protected-access` inline suppressions from `agents/core/llm_clients.py`; renamed exception variables `e` → `exc` in `services/llm/qdrant_diagnostics.py`, `services/llm/qdrant_service.py`, and related files; stripped redundant inline comments from `chunking_service.py`, `concept_map_generation.py`, and `clients/dashscope_embedding.py` per PEP 8; applied across all 55 changed files.

### Fixed
- **Frontend / diagram canvas event ordering** (`useDiagramCanvasEventBus.ts`): removed the redundant outer `nextTick` wrapper on the `diagram:branch_moved` handler (double-tick was causing a frame skip on fit-to-canvas); concept map `normalizeAllConceptMapTopicRootLabels` + `regenerateForNodeIfNeeded` calls now correctly deferred inside a single `void nextTick(…)` block, preventing stale-DOM reads during the same render cycle.
- **Frontend / node palette streaming** (`streamNodePaletteBatch.ts`): `panelsStore.setNodePaletteSuggestions([])` is now called once before the reader loop begins (non-append mode), then every incoming node is added with `appendNodePaletteSuggestion`; the previous dual-path (append vs. spread-and-replace) that triggered redundant full-array allocations on every chunk is removed.

## [5.92.0] - 2026-04-18

### Added
- **MindBot / concurrency — per-org dynamic cap with burst mode**: replaced the noisy-neighbour *detection-only* approach with an enforcing, burst-aware gate for both streaming and blocking pipelines.
  - `_try_inc_org_stream` / `_try_inc_org_blocking` atomically compute an effective cap inside their respective asyncio locks (no inter-coroutine race) and return `(new_count, effective_cap)` on success or `None` when the org is already at its limit.  Callers receive an immediate `ORG_CONCURRENCY_LIMIT` response rather than blocking in a semaphore queue.
  - **Burst mode**: when ≥ `MINDBOT_ORG_BURST_FREE_THRESHOLD` (default 0.5) of the global active-stream pool is free the org may claim up to `MINDBOT_ORG_BURST_SHARE` (default 0.4) of those free slots, bounded by `MINDBOT_ORG_ABSOLUTE_MAX_STREAMING` (default 40 per worker).  At low load a 50-teacher workshop is served without throttling; under genuine overload the cap contracts to `MINDBOT_ORG_MAX_CONCURRENT_STREAMING` (default 8) to enforce fairness.
  - Equivalent vars for the blocking path: `MINDBOT_ORG_MAX_CONCURRENT_BLOCKING` / `_BURST_FREE_THRESHOLD_BLOCKING` / `_BURST_SHARE_BLOCKING` / `_ABSOLUTE_MAX_BLOCKING`.
  - All config readers use `@functools.cache` so env parsing runs once per process.
  - `MINDBOT_MAX_ACTIVE_STREAMING` (default 128) and `MINDBOT_MAX_ACTIVE_BLOCKING` (default 128) are the global denominators for free-fraction math; documented in `env.example`.
- **MindBot / pipeline — org-active guard**: new `_check_org_active(organization_id)` in `callback_validate.py` — uses the Redis org cache to check `is_active` and `expires_at` before the pipeline runs; returns `ORG_LOCKED` (HTTP 403) for locked or subscription-expired orgs; falls through transparently when the cache is unavailable so a Redis outage never blocks legitimate traffic.
- **MindBot / errors**: two new `MindbotErrorCode` entries — `ORG_CONCURRENCY_LIMIT` (`MINDBOT_ORG_CONCURRENCY_LIMIT`, retryable) and `ORG_LOCKED` (`MINDBOT_ORG_LOCKED`).
- **MindBot / admin — per-org Dify health probe**: new `GET /admin/configs/{organization_id}/dify-health` endpoint that probes the org's own Dify app API (`GET /parameters`) without exposing secrets; requires `mindbot_admin_access` and respects org scope; returns the same `DifyServiceStatusResponse` schema as the global Dify-service status endpoint.
- **MindBot / admin — paginated config list**: `GET /admin/configs` now accepts `limit` (1–200, default 50) and `after_org_id` (exclusive cursor) query parameters; `MindbotConfigRepository.list_all` uses keyset pagination capped at `_LIST_ALL_MAX = 200` to prevent runaway queries on large tenant sets.
- **MindBot / rate limiter — multi-worker guidance**: `services/mindbot/infra/rate_limit.py` module docstring now explains the Redis-authoritative / per-process-fallback split and gives a worked sizing example for `MINDBOT_ORG_RATE_LIMIT` with N workers; new env var `MINDBOT_RATE_LIMIT_MEM_MAX_KEYS` (default 5000) caps the in-process fallback counter map.

### Fixed
- **MindBot / callback routing**: clarified that platform lifecycle events (token verification, OAuth callbacks) use `get_by_organization_id` rather than `get_enabled_by_organization_id` intentionally — DingTalk requires a 200 response even when the bot is disabled so the event-subscription contract remains valid; added inline comments to both `dingtalk_callback_per_org` and `dingtalk_callback_by_token` to prevent accidental regression.
- **MindBot / inbound log**: corrected docstring for `log_dingtalk_callback_failure_details` — the default state of `MINDBOT_LOG_CALLBACK_DEBUG` is *off*, not on.
- **Backup scheduler / COS**: extracted duplicated COS exception attribute introspection into a private `_cos_exc_call(exc, method, default)` helper; applied to both `list_cos_backups` and `cleanup_old_cos_backups`; removed the redundant post-dump size log line from `create_backup` (size was logged redundantly before integrity check).

### Changed
- **Pylint / inline suppression cleanup**: removed all `# pylint: disable=…` inline comments from `services/mindbot/infra/http_client.py`, `services/mindbot/infra/redis_async.py`, `services/mindbot/platforms/dingtalk/cards/stream_client.py`, `services/mindbot/telemetry/usage.py`, and `services/utils/backup_scheduler.py`; the underlying patterns are now clean (broad `except` with a bound variable, `global` statements, and `import-outside-toplevel` in a lazy-import helper are all idiomatic in these contexts and no longer need per-line suppressions).

## [5.91.0] - 2026-04-17

### Added
- **DB / Phase 6h — production-safety & performance sweep** (`db_ops_gaps_fix_11039df5` plan): ten gap-fix items landed across the database and Redis stack. Every default is conservative; every knob is overridable via env. See `docs/db-tuning.md` "Phase 6h tunables" for the full table.
  - **PostgreSQL `connect_args` & LIFO pooling (G1, G5)** — `config/database.py` now passes `statement_timeout`, `idle_in_transaction_session_timeout`, `application_name=mindgraph-w<pid>`, `connect_timeout`, and `pool_use_lifo=True` to both `create_engine` and `create_async_engine`. New env vars: `DATABASE_STATEMENT_TIMEOUT_MS` (default `60000`), `DATABASE_IDLE_IN_TXN_TIMEOUT_MS` (default `30000`), `DATABASE_CONNECT_TIMEOUT_S` (default `10`), `DATABASE_APPLICATION_NAME`, `DATABASE_POOL_USE_LIFO` (default `true`).
  - **Async Redis fail-fast (G3)** — `_with_async_retry` in `services/redis/redis_async_ops.py` now consults the sync-side `is_redis_available()` flag (lazily imported to avoid a cycle) and short-circuits with the operation's `default_return` when Redis is known down, eliminating ~350 ms of pointless exponential backoff per call during outages.
  - **Connection-pool stats in `/health` (G4)** — `routers/core/health.py` exposes `database_stats.pool` (async engine) and `database_stats.sync_pool` (sync engine) with `size`, `checked_in`, `checked_out`, `overflow`, `total` so connection leaks surface before they trigger `QueuePool limit exceeded`.
  - **Cache stampede protection (G6)** — new `services/redis/cache/redis_cache_stampede.py` with `with_stampede_lock(cache_key, loader, cache_reader=None, ...)`: uses Redis `SET NX EX` to ensure only one request per key hits the DB on a cache miss; losers wait briefly (default 2 s, 50 ms poll) then re-read the cache, falling back to the loader if the winner failed. Wired into `RedisUserCache`, `RedisOrgCache`, and `RedisDiagramCache` `_load_from_database` paths. New env: `CACHE_STAMPEDE_LOCK` (default `true`).
  - **`orjson` everywhere (G7)** — `main.py` registers `ORJSONResponse` as FastAPI's `default_response_class`; `services/redis/redis_token_buffer.py` (Redis Streams hot path), `services/redis/cache/redis_diagram_cache.py` (list cache writes + warm-up), and `services/redis/cache/redis_community_cache.py` (list + post cache writes) switched from stdlib `json` to `orjson.dumps`/`orjson.loads`.
  - **Redis circuit breaker (G8)** — new `services/redis/redis_circuit_breaker.py` implements a per-process `CLOSED → OPEN → HALF_OPEN` state machine. Wired into both `services/redis/redis_client.py::_with_retry` and `services/redis/redis_async_ops.py::_with_async_retry`; trips OPEN after `REDIS_CB_FAILURE_THRESHOLD` consecutive `ConnectionError`/`TimeoutError` (default `5`), short-circuits to `default_return` for `REDIS_CB_COOLDOWN_S` seconds (default `10.0`), then allows one probe. New env: `REDIS_CIRCUIT_BREAKER` (default `true`).
  - **Bulk cache loader pipelines (G9)** — `RedisUserCache.bulk_cache_users` and `RedisOrgCache.bulk_cache_orgs` issue **one** Redis pipeline per batch instead of one per row. `services/redis/cache/redis_cache_loader.py::load_all_users_to_cache` / `load_all_orgs_to_cache` use the bulk path with a per-record fallback on pipeline failure.
  - **Drop wasted `lazy="selectin"` (G11)** — `models/domain/auth.py::User.organization` switched from `lazy="selectin"` to `lazy="select"`. No production caller used the relationship attribute (every site uses `user.organization_id` + `org_cache.get_by_id(...)`); the only formatter that does (`routers/features/community.py::_format_post`) already eager-loads via explicit `selectinload(CommunityPost.author).selectinload(User.organization)` / `joinedload(...)`. Baseline file `scripts/lint/lazy_selectin_baseline.txt` decremented accordingly.
  - **Health-endpoint `INFO` memoisation (G12)** — `_cached_redis_info` in `routers/core/health.py` adds a 5-second TTL cache around `INFO server` and `INFO memory` so an aggressive load-balancer poll cadence cannot turn `/health` into a self-DoS against Redis.
- **Docs**: new "Phase 6h tunables" section in `docs/db-tuning.md` documents every new env var, behaviour, and override path.

### Fixed
- **Library / XSS hardening**: `LibraryDanmakuMixin.sanitize_content` and `LibraryBookmarkMixin._sanitize_content` re-ordered their tag-stripping regex chain so the body of `<script>`, `<style>`, `<iframe>`, `<object>`, and `<embed>` tags is dropped **before** the generic `<[^>]+>` strip. Previously the generic strip ran first and reduced `<script>alert('xss')</script>Hello` to `alert('xss')Hello`, leaking the executable text as plain content; the new order also handles unterminated dangerous tags (e.g. truncated `<script>...`).
- **Repo hygiene**: repaired pre-existing UTF-8 mojibake in `routers/features/library/admin.py` (9 mangled multi-byte sequences — left-arrow `\u2190` had its third byte truncated to ASCII `?`, plus two smart quotes), which had been blocking pytest collection of any test that transitively imported the module.

## [5.90.0] - 2026-04-17

### Changed
- **DB / Phase 6 — full async DB & Redis**: every code path reachable from the asyncio event loop now talks to Redis through the shared async client (`get_async_redis()` / `AsyncRedisOps`) and to PostgreSQL through `AsyncSessionLocal` / `async_engine`. `get_redis()`, `RedisOps.*`, `asyncio.to_thread(redis_client.*)` shims, and `SyncSessionLocal()` are forbidden inside `async def` bodies.
- **DB / Phase 6a — auth & verification**: `services/auth/captcha_storage.py`, `services/auth/ip_geolocation.py`, `services/redis/redis_email_storage.py`, `services/redis/redis_sms_storage.py`, `services/redis/redis_bayi_token.py`, `services/redis/redis_bayi_whitelist.py` (+ distributed load-lock), and `utils/auth/jwt_secret.py` migrated to native async; all `routers/auth/*` callers updated; tests switched to `AsyncMock`.
- **DB / Phase 6b — workshop & WS realtime**: `services/workshop/{workshop_service,workshop_live_spec_ops,workshop_live_flush,workshop_ws_editor_redis,workshop_ws_mutation_idle,workshop_cleanup_impl}.py` and `services/features/workshop_chat_presence_store.py` migrated to async; sync `publish_chat_fanout` / `publish_workshop_fanout` and `asyncio.to_thread` shims in `services/features/ws_redis_fanout_publish.py` deleted; native async publishers are now the only API; `routers/api/workshop_ws_handlers.py` (9 sites) and `routers/api/workshop_ws_connect.py` (4 sites) updated to `await`.
- **DB / Phase 6c — LLM & RAG hot path**: `services/llm/embedding_cache.py` (`EmbeddingCache.get`/`set`/`invalidate`), `clients/dashscope_rerank.py`, `services/library/redis_cache.py` (10 sites — documents + danmaku caches), `services/infrastructure/rate_limiting/rate_limiter.py` (`DashscopeRateLimiter`), `services/infrastructure/utils/load_balancer.py`, and `utils/tiktoken_cache.py` async warmup helper migrated to native async; per-prompt local-only path unchanged.
- **DB / Phase 6d — dashboard, monitoring, cleanup**: `routers/public_dashboard.py` (8 sites incl. SSE `stream_activity_updates`), `routers/core/health.py` (Redis health checks + `_async_database_health_check` against `async_engine`, drops `asyncio.to_thread(check_integrity)` and `asyncio.to_thread(RedisOps.ping/info)`), `services/monitoring/{dashboard_session,activity_stream,city_flag_tracker}.py`, and `services/infrastructure/monitoring/ws_metrics.py` (per-WS-frame metrics) migrated to native async.
- **DB / Phase 6e — drop `to_thread(sync_redis)` shims**: `services/infrastructure/monitoring/{process_monitor,health_monitor,critical_alert}.py`, `services/infrastructure/recovery/database_check_state.py`, and `services/utils/temp_image_cleaner.py` (Redis sites only — filesystem `to_thread(list, glob)` left intact) now call the async client directly; distributed locks use `AsyncRedisOps.set` with the same SETNX + EXPIRE semantics.
- **DB / Phase 6f — SQLAlchemy sync API cleanup**: removed dead sync API in `services/teacher_usage_stats.py` (`_get_active_dates_for_user`, `get_classification_config`, `save_classification_config`, `compute_and_upsert_user_usage_stats`); `*_async` variants are now the sole API. `scripts/db/backfill_user_usage_stats.py` rewritten as a fully async CLI (`asyncio.run` at the top level, `AsyncSessionLocal`/`async_engine` throughout).
- **DB / Phase 6g — transitive sync-Redis sweep**: new audit `scripts/lint/audit_transitive_sync_redis.py` walks every `async def` body looking for calls into sync helpers that themselves use `get_redis()`/`RedisOps.*`, catching violations the AST lint guard cannot reach. Driven by that audit, the following hot/loop helpers were converted to native async and their async callers updated:
  - **Security**: `services/infrastructure/security/abuseipdb_service.py` — `is_ip_in_blacklist_set_async`, `_get_cached_check_score_async`, `_set_cached_check_score_async`, `try_acquire_report_dedupe_async`, `_store_blacklist_ips_async`, `log_shared_blacklist_redis_size_async`, `apply_blacklist_baseline_from_file_async` (file I/O still wrapped in `asyncio.to_thread`, Redis fully async); `abuseipdb_middleware.py` (per-request hot path) and `abuseipdb_scheduler.py` (`acquire_abuseipdb_scheduler_lock_async` / `refresh_abuseipdb_scheduler_lock_async`) updated; `crowdsec_blocklist_service.py` (`apply_crowdsec_baseline_from_file_async`, `_get_last_merge_unix_async`, `_set_last_merge_meta_async`, `_should_skip_due_to_min_interval_async`, `_sadd_ips_chunked_async`, `pipeline_sadd_chunks_async`) and `services/infrastructure/lifecycle/lifespan.py` startup wiring switched accordingly.
  - **Recovery**: `services/infrastructure/recovery/recovery_locks.py` — `acquire_integrity_check_lock` / `release_integrity_check_lock` are now `async def` using `get_async_redis()`; `recovery_startup.py::check_database_on_startup` awaits the new API.
  - **Backup scheduler**: `services/utils/backup_scheduler.py` — added `acquire_backup_scheduler_lock_async`, `refresh_backup_scheduler_lock_async`, `release_backup_scheduler_lock_async`, `is_backup_lock_holder_async`; `start_backup_scheduler` and `run_backup_now` use the async lock helpers; the synchronous `create_backup` (which still drives `pg_dump` / COS upload via `asyncio.to_thread`) keeps the sync helpers internally — Bucket B by design.
  - **Gewe DB layer**: `services/gewe/{contact_db,group_member_db,message_db}.py` — dropped `RedisOperations()` instances and replaced every `self._redis.<op>` (cache `get`/`set_with_ttl`/`delete`/`exists`) with `await AsyncRedisOperations.<op>` so the async ORM callers no longer block the loop on a sync Redis round-trip.
  - **Knowledge / chunk test**: replaced the synchronous `detect_and_mark_stuck_tests()` in `routers/api/knowledge_space/chunk_test_background.py` with a single async implementation `detect_and_mark_stuck_tests_async()` (uses `AsyncSessionLocal` + bulk `update`); `routers/api/knowledge_space/chunk_test_execution.py` endpoints `get_chunk_test_progress` and `detect_stuck_tests` now `await` it. The dead sync sibling was removed (it had no callers after the conversion); other `SyncSessionLocal()` use in the same module remains for the atexit cleanup hook and the `threading.Thread`-driven background workers (Bucket B).
- **DB / `config/database.py`**: added `check_integrity_async()` for native async health probes; `/health/database` and `/health/all` no longer trip a thread hop for the SQLAlchemy round-trip.

### Added
- **DB / lint guard**: `scripts/lint/lint_sync_redis_in_async.py` — AST guard that fails CI when an `async def` body contains `get_redis(`, `RedisOps.<name>(`, or `asyncio.to_thread(<expr>, ...)` whose first arg is a sync Redis target. Empty baseline (`scripts/lint/sync_redis_in_async_baseline.txt`) — zero violations after Phase 6.
- **DB / lint guard**: `scripts/lint/lint_sync_session_in_async.py` — AST guard that flags `SyncSessionLocal()` inside any `async def` body. Empty baseline (`scripts/lint/sync_session_in_async_baseline.txt`) — zero violations after Phase 6.
- **DB / audit**: `scripts/lint/audit_transitive_sync_redis.py` — one-shot diagnostic that catches transitive `async → sync helper → sync Redis` chains the AST lint guard cannot reach. Run periodically; today's clean output reports only Bucket B helpers (Celery, dedicated threads, sync startup, sync `create_backup`, CLI/migration helpers) with **zero async callers**.
- **Docs**: `docs/db-tuning.md` documents the async-by-default policy, the Bucket B inventory of legitimate sync consumers (Celery, dedicated threads, subprocess-heavy backups, one-shot startup, CLI scripts), and the lint-guard + audit checklist for new code.

## [5.89.0] - 2026-04-17

### Added
- **MindBot / security**: DNS rebinding SSRF protection — `validate_session_webhook_url` now returns a 3-tuple `(ok, reason, pinned_ip)`; the first resolved IP is pinned at validation time and passed to `post_session_webhook`, which uses `_PinnedIPResolver` (a custom `aiohttp` resolver) to connect to the pre-resolved address without re-resolving DNS on each request; TLS SNI and certificate verification continue to use the original hostname.
- **MindBot / DingTalk**: Per-app-key async sliding-window QPS limiter in `streaming_qps.py` — FIFO waiter queue (O(1) per slot, no spin-sleep); configured via `MINDBOT_DINGTALK_STREAMING_QPS_PER_APP` (default 18/s), `MINDBOT_DINGTALK_STREAMING_QPS_WINDOW_MS`, and `MINDBOT_DINGTALK_STREAMING_QPS_NUM_WORKERS` for multi-worker deployments; LRU eviction when key count exceeds `MINDBOT_QPS_LIMITER_MAX_KEYS` (default 500).
- **MindBot / DingTalk**: QPS throttle detection helper `dingtalk_streaming_body_is_qps_throttle` handles DingTalk `Forbidden.AccessDenied.QpsLimitForAppkeyAndApi`, `Forbidden.AccessDenied.QpsLimitForApi`, legacy numeric codes `90018`/`90002`, and substring patterns.
- **MindBot / DingTalk**: `_card_put_with_retry` in `ai_card_update.py` — unified PUT helper with OAuth 401 single-retry (token refresh + cache invalidation) and QPS 403 sleep-and-retry (up to `MINDBOT_DINGTALK_STREAMING_QPS_MAX_RETRIES`, default 4); callers pass `on_qps_retry` to mutate payload (e.g. rotate `guid`) before each retry.
- **MindBot / pipeline**: `DifyReplyContext` dataclass in `pipeline/context.py` — bundles the parameters shared by `run_streaming_dify_branch` and `run_blocking_send_branch` (`cfg`, `body`, `session_webhook_valid`, `session_webhook_pinned_ip`, `conversation_id_dt`, `conv_key`, `record_usage`, `hdr`, `redis_bind_dify_conversation`, `pipeline_ctx`; `msg_id` added in 5.93.0 for Redis send tracking), reducing each function from 14–18 keyword args to a single context object.
- **MindBot / pipeline**: QPS-exhausted mid-stream fallback in `dify_paths.py` — when a streaming card-update fails with a QPS error, `CardStreamState.plain_fallback_pending` (field was originally named `qps_exhausted`) is set; subsequent SSE chunks accumulate silently and the complete Dify answer is sent as one full markdown robot message after streaming ends (see 5.93.0 for the expanded tracker and `send_full_reply` behaviour).
- **MindBot / pipeline**: Two-level semaphore design in `callback.py` — `_STREAMING_SEMAPHORE` (startup queue, released on first SSE event) paired with `_ACTIVE_STREAMS_SEMAPHORE` (held for full stream lifetime, `MINDBOT_MAX_ACTIVE_STREAMING`, default 128); same pattern for blocking path (`_BLOCKING_SEMAPHORE` + `_ACTIVE_BLOCKING_SEMAPHORE`, `MINDBOT_MAX_ACTIVE_BLOCKING`, default 128).
- **MindBot / pipeline**: Per-org active-stream counter in `callback.py` — logs a WARNING when one org holds ≥ `MINDBOT_ORG_STREAM_WARN_THRESHOLD` (default 10) concurrent streams, enabling noisy-neighbour detection.
- **MindBot / telemetry**: `MindBotLogAdapter` and `get_pipeline_logger` in `pipeline_log.py` — injects structured `extra` fields (`mb_org_id`, `mb_msg_id`, `mb_error_code`, `mb_robot_code`, `mb_streaming`) into every log record for JSON log processors (Datadog, ELK, CloudWatch) without regex-parsing log lines.

### Changed
- **MindBot / pipeline**: `dify_paths.py` — `run_streaming_dify_branch` and `run_blocking_send_branch` signatures replaced 14–18 keyword parameters with a single `ctx: DifyReplyContext`; `new_conv.strip()` normalises Dify conversation IDs before Redis binding; all `send_one_reply_chunk` / `post_session_webhook` calls now forward `pinned_ip`.
- **MindBot / pipeline**: `ai_card_state.py` — `CardStreamState.finalize()` return type simplified from `tuple[bool, Optional[str]]` to `bool`; `plain_fallback_pending: bool` field added (shipped in 5.89.0 as `qps_exhausted`, later renamed); `reset()` clears both new fields.
- **MindBot / infra**: `circuit_breaker.py` — `CircuitBreaker.state()` replaces direct `is_open()` as single source of truth, returning `"closed"` / `"open"` / `"half_open"` literals; `_breakers` dict upgraded to `OrderedDict` with LRU eviction at `MINDBOT_CIRCUIT_BREAKER_MAX_KEYS` (default 2000); uses `redis_incr_fixed_window` (fixed-window, TTL on first increment only) instead of `redis_incr_with_ttl`.
- **MindBot / session**: `validate_session_webhook_url` return type changed from `tuple[bool, str]` to `tuple[bool, str, str]`; DNS timeout cached via `@functools.cache`; empty DNS result set now returns an explicit rejection.
- **MindBot / outbound**: `post_session_webhook` split into `_do_post_session_webhook` (execution) and public wrapper; accepts `pinned_ip` kwarg; `allow_redirects=False` enforced; response body read unconditionally to drain the connection; token/secret redaction in WARNING logs via `_sanitize_webhook_snippet`.
- **MindBot / pipeline**: `callback.py` log calls for `recv` and `pipeline_detail` switched to `_pipeline_log` (`MindBotLogAdapter`) for structured field injection; conv-gate poll timeout log includes `elapsed_ms` and `budget_ms`.
- **Tests**: New test files — `test_mindbot_callback_validate.py`, `test_mindbot_circuit_breaker.py`, `test_mindbot_dify_sse_parse.py`, `test_mindbot_message_files.py`, `test_mindbot_outbound_text.py`, `test_mindbot_pipeline_log.py`, `test_mindbot_rate_limit.py`, `test_mindbot_streaming_qps.py`, `test_mindbot_task_registry.py`, `test_mindbot_usage_parse.py`, `test_mindbot_usage_persistence.py`; expanded coverage for conv gate, AI card, metrics, and session webhook URL.

## [5.88.0] - 2026-04-16

### Added
- **MindBot / DingTalk**: Per-organization cap on AI-card streaming body length — `dingtalk_ai_card_streaming_max_chars` on `organization_mindbot_configs` (default **6000**); Alembic `rev_0021`.
- **MindBot / DingTalk**: `mindbot_ai_card_streaming_max_chars()` helper in `ai_card_create.py` (minimum enforced against platform limits); pipeline and `ai_card_update` use the cap for streamed card text.
- **MindBot / admin**: MindBot admin API and UI expose and persist the new field (`mindbot_models.py`, `mindbot_admin.py`, `mindbot_helpers.py`; `AdminMindBotConfigDialog.vue`, `AdminMindBotTab.vue`, `mindbotConfigTypes.ts`); i18n `en` / `zh` admin strings.

### Changed
- **MindBot / pipeline**: `dify_paths.py` passes per-config `max_chars` into AI-card streaming paths.
- **Tests**: `test_mindbot_ai_card.py`, `test_mindbot_callback.py` cover the new config field and resolver behavior.

## [5.87.0] - 2026-04-16

### Added
- **MindBot / errors**: `RATE_LIMITED` error code (`MindbotErrorCode.RATE_LIMITED`) — rate-limited requests now return HTTP 429 with a dedicated code instead of reusing `DUPLICATE_MESSAGE`.
- **MindBot / errors**: `REDIS_UNAVAILABLE_FOR_DEDUP` error code — deduplication fails closed (HTTP 503) when Redis is unreachable instead of silently dropping messages.
- **MindBot / infra**: `redis_ping()` async health check in `redis_async.py`; replaces the synchronous `is_redis_available()` call in the pipeline.
- **MindBot / infra**: `redis_incr_fixed_window()` Lua-based atomic counter for true fixed-window rate limiting (TTL set only on key creation).
- **MindBot / infra**: In-memory fallback counter in `rate_limit.py` — per-org abuse protection stays active during Redis outages.
- **MindBot / infra**: Redis SETNX probe lock in `circuit_breaker.py` — half-open state allows exactly one probe across all workers, preventing thundering-herd recovery.
- **MindBot / pipeline**: `ai_card_state.py` extracted from `dify_paths.py` — encapsulates the AI-card streaming state machine with `card_chars_confirmed` tracking to prevent duplicate content on card-to-text fallback.
- **MindBot / ops**: Startup pool-vs-`max_connections` health check in `config/database.py` — warns if SQLAlchemy pool size × workers exceeds PostgreSQL limits.
- **MindBot / DB**: Alembic `rev_0020` — three new indexes on `mindbot_usage_events` (`org_id+id`, `dingtalk_conversation_id`, `dify_conversation_id`) for usage query performance.
- **MindBot / logging**: Header redaction (`sign`, `token`, `authorization`, `cookie`) in debug-level inbound and failure dumps (`inbound_log.py`).

### Changed
- **MindBot / router**: `routers/api/mindbot.py` split into `mindbot_callback.py`, `mindbot_admin.py`, `mindbot_helpers.py`, `mindbot_models.py`; aggregator re-exports for backward compatibility.
- **MindBot / pipeline**: Shared callback route (`POST /dingtalk/callback`) now runs the pipeline in the background, matching per-org and per-token routes.
- **MindBot / pipeline**: Conv-gate poll timeout increased from 3 s to 15 s with a warning log when exceeded.
- **MindBot / pipeline**: Usage events persist in isolated DB sessions — telemetry failures cannot roll back pipeline work.
- **MindBot / security**: `public_callback_token` masked (last 8 chars only) and `dingtalk_event_owner_key` masked in admin GET responses.
- **MindBot / infra**: `task_registry.drain()` uses `asyncio.gather(*tasks, return_exceptions=True)` with a bounded timeout for clean shutdown.
- **MindBot / rate limit**: Default org rate limit set to 200 requests per minute (`MINDBOT_ORG_RATE_LIMIT=200`).
- **Tests**: `test_mindbot_callback.py` updated to mock `redis_ping` instead of removed `is_redis_available`.

## [5.86.0] - 2026-04-15

### Added
- **MindBot / Dify**: `services/mindbot/core/dify_user_id.py` — stable Dify `user` id per DingTalk staff; Redis conversation keys and conv-gate scope include `sender_staff_id` in group chats so members do not share one Dify binding.
- **MindBot / reasoning**: Dify SSE `agent_thought` accumulation in `mindbot_consume_dify_stream_batched` (fifth return value `native_reasoning`); `reply_thinking.py` splits tag-embedded `<think>` / loose blocks from answer text (`SplitReasoningResult`, `split_tag_embedded_reasoning`) and reads blocking JSON via `native_reasoning_from_dify_blocking_response`; `dify_paths.py` merges native + tag reasoning in `format_mindbot_reply_for_dingtalk` (dedup when both channels repeat).
- **MindBot / ops**: `GET /api/mindbot/admin/internal/memory-footprint` (platform admins) — OAuth lock LRU size/cap, DingTalk Stream registered clients, callback metrics; school managers see org-scoped `by_organization_id` only (`_callback_metrics_snapshot_for_user`).
- **MindBot / OAuth**: LRU-capped in-process thundering-herd lock map (`MINDBOT_OAUTH_LOCK_MAP_MAX`, default 2048) in `services/mindbot/platforms/dingtalk/auth/oauth.py`.
- **MindBot / telemetry**: `mindbot_long_lived_maps_snapshot` and related metrics; Stream client count hook in `cards/stream_client.py`.
- **Config / security**: `_sanitize_feature_org_access_map` so non-admins do not receive full org/user allowlists for feature flags (`routers/api/config.py`); tests in `tests/routers/test_config_feature_org_access_sanitize.py`.
- **Tests**: `tests/services/test_mindbot_admin_security.py`, `tests/services/test_mindbot_memory_footprint.py`; expanded MindBot callback, Dify stream, and reply-thinking coverage.

### Changed
- **MindBot / capacity**: Separate semaphores — `MINDBOT_MAX_CONCURRENT_STREAMING` and `MINDBOT_MAX_CONCURRENT_BLOCKING` (replace single `MINDBOT_MAX_CONCURRENT`); `env.example` documents per-process caps and ops notes for RSS / memory footprint endpoint.
- **MindBot / Redis**: Configurable async pool size `MINDBOT_REDIS_MAX_CONNECTIONS` (`services/mindbot/infra/redis_async.py`).
- **Database**: Default SQLAlchemy pool raised to **50** base + **100** overflow per worker (`config/database.py`, `env.example`); sizing notes for PostgreSQL `max_connections`.
- **MindBot / pipeline**: `callback.py`, `callback_validate.py`, `chain_of_thought_policy.py` aligned with new user/conv scoping and reasoning merge.
- **Frontend / admin**: `AdminMindBotUsagePanel.vue`, `MindbotUsageEventDetailDialog.vue`, `AdminMindBotConfigDialog.vue`, `AdminMindBotTab.vue`; `mindbotConfigTypes.ts`; sidebar and feature-flag wiring (`AppSidebarNav.vue`, `useAppSidebar.ts`, `useFeatureFlags.ts`, `featureFlags.ts`, `router/index.ts`); i18n `en` / `zh` admin strings.

## [5.85.0] - 2026-04-15

### Added
- **MindBot / Dify**: Shared async HTTP pool for streaming and blocking chat (`clients/dify.py`); tests in `tests/clients/test_dify_shared_http_pool.py`.
- **MindBot / DingTalk**: Package layout under `services/mindbot/platforms/dingtalk/` — `api/`, `auth/`, `cards/` (including `ai_card_create.py`, `ai_card_update.py`), `inbound/`, `media/`, `messaging/`; `services/mindbot/infra/` for `http_client`, `redis_async`, plus `circuit_breaker`, `rate_limit`, `task_registry`.
- **MindBot / pipeline**: Fast callback validation module (`services/mindbot/pipeline/callback_validate.py`) and related pipeline refactors (`callback.py`, `dify_paths.py`).
- **MindBot / chain-of-thought**: Per-chat-scope flags (1:1, internal group, cross-org group) replacing a single `show_chain_of_thought` column; Alembic `rev_0019`; `services/mindbot/core/chain_of_thought_policy.py`.
- **MindBot / admin**: Usage event detail dialog and types (`MindbotUsageEventDetailDialog.vue`, `mindbotUsageTypes.ts`); `frontend/src/utils/mindbotAccess.ts` for route access; MindBot admin API and usage repository extensions.
- **Auth**: MindBot admin access checks (`utils/auth/roles.py`, `routers/auth/dependencies.py`); tests `tests/utils/test_auth_roles_mindbot_access.py`.
- **Tests**: Chain-of-thought policy, updated MindBot callback and AI card tests.

### Changed
- **MindBot**: Conversation gate, streaming (`dify_stream.py`), reply thinking (`reply_thinking.py`), outbound text/media, OAuth and OpenAPI helpers; `conv_gate.py` and `service_health.py` updates; `lifespan.py` for background task registry shutdown.
- **API**: `routers/api/mindbot.py` expanded; `models/domain/mindbot_config.py` and messages for new MindBot fields.
- **Frontend**: `AdminMindBotConfigDialog.vue`, `AdminMindBotTab.vue`, `AdminMindBotUsagePanel.vue`, `MindbotAdminPage.vue`, router and i18n (`en` / `zh` admin).

## [5.84.0] - 2026-04-14

### Added
- **MindBot / DingTalk**: Optional chain-of-thought display for streaming replies (`show_chain_of_thought`, `chain_of_thought_max_chars` on `organization_mindbot_configs`; Alembic `rev_0017`; `services/mindbot/core/reply_thinking.py`).
- **MindBot / DingTalk**: Optional AI card updates for OpenAPI streaming via template id and stream parameter key (`dingtalk_ai_card_template_id`, `dingtalk_ai_card_param_key`; Alembic `rev_0018`; `services/mindbot/platforms/dingtalk/ai_card.py`).
- **MindBot / Dify**: SSE event parsing (`services/mindbot/core/dify_sse_parse.py`), Dify service health checks (`services/mindbot/dify/service_health.py`), and typed HTTP error helpers (`clients/dify_http_errors.py`).
- **MindBot / admin**: Dedicated **`MindbotAdminPage.vue`** at **`/admin/mindbot`** (legacy **`AdminPage?tab=mindbot`** redirects); **`AdminMindBotConfigDialog.vue`**, **`AdminMindBotUsagePanel.vue`**, and usage persistence via **`repositories/mindbot_usage_repo.py`**.
- **Admin / security**: Shared sensitive-value masking for lists and dialogs (`utils/sensitive_mask.py`, `frontend/src/utils/sensitiveMask.ts`).
- **Tests**: Coverage for SSE parsing, service health, reply thinking, AI card paths, admin usage, and related MindBot flows.

### Changed
- **MindBot**: Package layout reorganized under `services/mindbot/` (`core`, `dify`, `education`, `integrations/dingtalk`, `outbound`, `pipeline`, `session`, `telemetry`); former top-level modules moved (for example usage/metrics/callback/outbound).
- **MindBot**: Streaming and reply pipeline updates (`services/mindbot/core/dify_stream.py`, `services/mindbot/core/dify_reply.py`); outbound text/media helpers; pipeline logging (`services/mindbot/telemetry/pipeline_log.py`).
- **API / config**: `routers/api/mindbot.py`, `clients/dify.py`, `config/features_config.py`, `env.example`, `models/domain/mindbot_config.py`; admin user/role/school routers and MindBot tab UI aligned with the new admin page and masking.
- **OpenClaw skill**: **`openclaw/skills/mindgraph/SKILL.md`** and **`README.md`** updated for current MindBot behavior.

## [5.83.0] - 2026-04-14

### Added
- **API / client bundles**: Public zip downloads for the OpenClaw MindGraph skill and the Chrome extension (`GET /api/downloads/mindgraph-openclaw-skill`, `GET /api/downloads/mindgraph-chrome-extension`; `routers/api/client_bundles.py`), built from the repo tree at runtime.
- **Account UI**: Download links for those bundles in **`AccountInfoModal.vue`** with i18n strings in **`en`** / **`zh`** auth message modules.

### Changed
- **Chrome extension**: MV3 service worker for **`PING`**; **180s** PNG `fetch` timeout; manifest **0.2.10** at release. *(That release described long `fetch` in the **popup** and a **`CAPTURE_PAGE_FOR_MINDMAP`** path; current behavior is in **[5.107.0]**: PNG + download in the service worker, toolbar progress via a **`mindmap-generate` connect** port, manifest **0.3.6+**.)*
- **OpenClaw skill**: **`SKILL.md`** and **`README.md`** updated (PNG auth and signed URLs, `diagram_type` alias note, `filename` field, long-timeout guidance for PNG routes, **ClawHub** publish version **1.1.0**, bundle file table).
- **API router**: MindBot lazy import variable renamed to **`MINDBOT_MODULE`** for constant-style naming.
- **Diagram PNG URL**: `GET .../diagrams/{id}/png` JSON includes **`filename`** alongside **`url`** (`routers/api/diagram_node_ops.py`).
- **Temp PNG serving**: Signed temp image responses set **`Content-Disposition`** with a **`.png`** filename (`routers/api/png_export.py`).

## [5.82.0] - 2026-04-13

### Added
- **MindBot / DingTalk**: HTTP event subscription and OA-style callback encryption and decryption (`services/mindbot/`, `routers/api/mindbot.py`).
- **MindBot / DingTalk**: `GET` handlers on the callback route for URL reachability checks; verbose and full inbound logging plus structured debug failure dumps; optional hints listing relevant environment variables when organization config is missing and inbound debug is off.
- **MindBot / DingTalk**: Path-only callback isolation so webhook traffic can be routed separately from the main app.
- **MindBot / DingTalk**: Opaque per-organization callback URLs using `public_callback_token` (shared base URL supported during migration).
- **MindBot / admin**: Default Dify client timeout increased to 300 seconds; secrets masked in admin MindBot views.

### Changed
- **MindBot / DingTalk**: Robot HTTP header verification aligned with the official DingTalk validation flow.
- **MindBot**: `MINDBOT_LOG_CALLBACK_DEBUG` defaults to on; repository hints and tests updated accordingly.
- **Admin**: DingTalk MindBot field labels aligned with Client ID and Client Secret terminology.

### Fixed
- **MindBot / DingTalk**: Accept shared-robot callback URL verification probes that omit `robotCode`.
- **MindBot / security**: Skip AbuseIPDB checks on DingTalk webhook paths; exempt DingTalk client IPs from Fail2ban-style bans and skip CSRF on those webhook paths so legitimate traffic is not blocked.
- **MindBot / DingTalk**: Respond with HTTP 200 on the shared callback URL during token migration so DingTalk does not treat failures as repeated errors and risk blacklisting.

## [5.81.0] - 2026-04-13

### Added
- **Markets (Alipay)**: Alembic `rev_0009_markets_tables`; `models/domain/markets.py`, `repositories/markets_repo.py`, `services/markets/` (Alipay notify, page pay, settings); HTTP feature routers under `routers/features/markets/`; admin **`AdminMarketsTab.vue`** and feature-flag wiring.
- **MindBot platform**: DingTalk HTTP callbacks and per-organization config (`routers/api/mindbot.py`, `models/domain/mindbot_config.py`, `models/domain/mindbot_usage.py`, `repositories/mindbot_repo.py`, `services/mindbot/`); Alembic `rev_0010`–`rev_0013` (org configs, usage events, education metrics, Dify inputs JSON); integration tests under `tests/services/test_mindbot_*.py`. (Streaming and production-hardening details are summarized under 5.79.0 / 5.80.0.)
- **Web content → mind map**: `agents/mind_maps/web_content_mind_map_agent.py`, `routers/api/web_content_generation.py`, request models and prompts for page-text extraction; OpenClaw **`SKILL.md`** updates for the same flow.
- **Changelog in product**: `GET /changelog/recent` (`routers/core/changelog.py`) backed by `services/utils/changelog_recent.py` and tests; **`UpdateLogModal.vue`** on login; `utils/env_helpers.py` for env parsing helpers where used.
- **Chrome extension**: `chrome-extension/` client scaffold for MindGraph web capture and API usage.

### Changed
- **Frontend**: Feature flags and stores (`useFeatureFlags`, `featureFlags`); admin **`AdminPage`** / **`AdminFeaturesTab`**; sidebar, Mindmate header/panel, Workshop personal menu, Template and Workshop chat pages, International landing; i18n (`en` / `zh` / `zh-tw`); auth **`LoginModal`** / **`useLoginModal`**.
- **Backend**: `clients/dify.py`; API registration and config (`routers/register.py`, `routers/api/config.py`, `routers/api/__init__.py`); `feature_gate.py`, Fail2ban startup gate, `redis_client.py`, `utils/auth/roles.py`, SQLite migration table order; `env.example` and **`requirements.txt`** for new dependencies.

## [5.80.0] - 2026-04-13

### Added
- **MindBot production hardening** (`services/mindbot/pipeline/callback.py`, `services/mindbot/core/conv_gate.py`): Optional Redis **conversation gate** serializes first Dify bind per DingTalk chat across workers; optional ``MINDBOT_DEDUP_REQUIRE_REDIS`` returns 503 when Redis is unavailable and ``msgId`` dedup cannot run. Response headers may include ``X-MindBot-Organization-Id`` and ``X-MindBot-Robot-Code``; structured ``callback org_id=…`` log line; ``mindbot_metrics`` snapshots add ``by_organization_id`` and ``by_robot_code`` (per process).
- **Docs** (`docs/MINDBOT_PRODUCTION.md`): DingTalk callback duration expectations, capacity formula, Redis dedup fail-open vs fail-closed, Redis 8.6+ checklist, load-testing note.

### Changed
- **Config** (`env.example`): MindBot capacity, dedup strict mode, and conv gate tuning variables.

## [5.79.0] - 2026-04-13

### Added
- **MindBot / Dify streaming (optional follow-ups)** (`services/mindbot/core/dify_stream.py`, `services/mindbot/pipeline/callback.py`): Chatflow-only replies can use ``workflow_finished.data.outputs`` when there are no ``message`` deltas (optional ``MINDBOT_DIFY_WORKFLOW_OUTPUT_KEY``). ``MINDBOT_STREAM_DEFER_TO_END`` defers all DingTalk sends until ``message_end`` (helps when ``message_replace`` runs after partial text). ``message_replace`` after at least one outbound batch logs a warning (stale partial bubbles). Redis binding for ``mindbot:dify_conv:*`` uses ``SET NX`` plus TTL refresh when the key already exists, so concurrent callbacks do not overwrite each other's Dify conversation id.

### Changed
- **Config** (`env.example`): Documented ``MINDBOT_STREAM_DEFER_TO_END`` and ``MINDBOT_DIFY_WORKFLOW_OUTPUT_KEY``.

## [5.78.0] - 2026-04-11

### Added
- **AbuseIPDB API base override** (`services/infrastructure/security/abuseipdb_service.py`): `get_abuseipdb_api_base()` reads optional `ABUSEIPDB_API_BASE` (trailing slash stripped) for check, report, blacklist, and baseline download; default remains `https://api.abuseipdb.com/api/v2`.
- **CrowdSec integration API base override** (`services/infrastructure/security/crowdsec_blocklist_service.py`): optional `CROWDSEC_BLOCKLIST_API_BASE` when building the integration content URL from `CROWDSEC_BLOCKLIST_INTEGRATION_ID`.
- **Docs / config** (`env.example`): Security notes for AbuseIPDB and CrowdSec credentials; commented examples for `ABUSEIPDB_API_BASE` and `CROWDSEC_BLOCKLIST_API_BASE`.
- **Tests**: `TestAbuseipdbApiBase` and CrowdSec `test_integration_api_base_override` in `tests/services/test_abuseipdb_blacklist.py`, `tests/services/test_crowdsec_blocklist.py`.

### Changed
- **`scripts/setup/download_abuseipdb_baseline.py`**: Blacklist download URL uses `get_abuseipdb_api_base()` instead of a hard-coded host.

## [5.77.0] - 2026-04-11

### Added
- **CrowdSec Console Raw IP List** (`services/infrastructure/security/crowdsec_blocklist_service.py`): Fetches plaintext IPs from the integration endpoint and merges them into the same Redis blacklist set used for AbuseIPDB; optional on-disk baseline `data/crowdsec/blocklist_baseline.txt`; `scripts/setup/download_crowdsec_baseline.py`; `env.example` variables (`CROWDSEC_BLOCKLIST_*`, `CROWDSEC_BASELINE_*`).
- **IP reputation env snapshot** (`services/infrastructure/security/ip_reputation_env_snapshot.py`): Warms configuration snapshots used with blacklist lookups and schedulers.
- **Tests**: `tests/services/test_crowdsec_blocklist.py`, `tests/services/test_abuseipdb_blacklist.py`.

### Changed
- **Lifespan** (`services/infrastructure/lifecycle/lifespan.py`): Applies CrowdSec baseline and optional network merge on startup when enabled.
- **AbuseIPDB stack** (`abuseipdb_service.py`, `abuseipdb_scheduler.py`): Coordinates CrowdSec merge with daily blacklist sync; shared Redis set documents AbuseIPDB + CrowdSec + baselines.
- **Pytest** (`tests/conftest.py`): Autouse fixture resets IP-reputation env snapshots so tests that patch environment variables see consistent behavior.

## [5.76.0] - 2026-04-11

### Added
- **AbuseIPDB + Fail2ban (MindGraph-side)**: `services/infrastructure/security/abuseipdb_service.py` (check, report, Redis blacklist sync), `abuseipdb_middleware.py`, `abuseipdb_scheduler.py` (daily blacklist with Redis lock), `fail2ban_integration/` (deploy helper, `report_ban` CLI); `resources/fail2ban/` templates; `docs/FAIL2BAN_SETUP.md`; `scripts/deploy/fail2ban_sync.sh`, `scripts/fail2ban_report_ban.sh`; `env.example` AbuseIPDB variables; lifespan and login lockout hooks; README / `setup.py` doc hints.
- **AbuseIPDB baseline file**: `data/abuseipdb/blacklist_baseline.txt` (tracked under `.gitignore` exceptions) merged into Redis at startup and after each successful API blacklist sync; `scripts/setup/download_abuseipdb_baseline.py`; `data/abuseipdb/README.md`.
- **Fail2ban**: `resources/fail2ban/jail.d/mindgraph-npm.local.conf` ships with **`enabled = true`**; `scripts/setup/setup.py` Step 9 calls **`verify_fail2ban_hint()`** (`fail2ban-client` on PATH + `fail2ban-client status`) on Linux alongside Redis/Qdrant checks.
- **VPN / CN transition geo enforcement** (`services/auth/vpn_geo_enforcement.py`): Redis-backed login-country baseline and last-IP tracking; optional kick / session invalidation when a session that logged in from a non-CN IP is later seen from a China-mainland IP (configurable via `VPN_CN_KICKOUT_*`); coverage for API routes and WebSockets (`routers/api/workshop_ws.py`, `routers/features/workshop_chat_ws.py`); integrates GeoIP resolution and CN mobile checks (`utils/cn_mobile.py`).
- **Auth resolution** (`utils/auth/auth_resolution.py`): Resolve authenticated `User` once per HTTP request for middleware and dependencies (`request.state.auth_context_user`), reducing duplicate JWT / `mgat_` validation.
- **HTTP auth token helpers** (`services/auth/http_auth_token.py`): Bearer extraction and access-token payload decoding shared by auth paths.
- **CN mainland geo cookie / API** (`services/auth/geo_cn_mainland_cookie.py`, `services/auth/email_login_cn_api_geo.py`): Structured responses and enforcement hooks aligned with email login and mainland policies.
- **Admin GeoLite status** (`routers/auth/admin/geolite.py`): `GET /api/auth/admin/system/geolite` reports whether `GeoLite2-Country.mmdb` is present, expected path, and download URL.
- **Frontend**: `GeoLiteNotification.vue` — admin-only Element Plus notification when the GeoLite country database is missing (dismissible with localStorage); wired from `App.vue`.
- **Redis** (`services/redis/keys.py`): `GEO_VPN_LOGIN_CC`, `GEO_VPN_LAST_IP`, and `TTL_GEO_VPN` for VPN/geo baseline keys.
- **Tests**: `tests/services/test_vpn_geo_enforcement.py`, `tests/services/test_geo_cn_mainland_cookie.py`, `tests/services/test_email_login_cn_api_geo.py`, `tests/utils/test_cn_mobile.py`.

### Changed
- **Auth (backend)**: Session, login, registration, password, email, public routes, helpers, and admin router wiring; `utils/auth/authentication.py`, `utils/auth/websocket_auth.py`, `utils/auth_ws.py`, `utils/auth/config.py`; `models/domain/messages.py` for user-visible copy; GeoIP and SWOT academic services and their tests where aligned with geo flows.
- **Middleware / lifecycle** (`services/infrastructure/http/middleware.py`, `services/infrastructure/lifecycle/lifespan.py`): Auth context and VPN/geo enforcement integration.
- **Notifications**: `routers/core/update_notification.py`; i18n `notification` bundles (`en`/`zh`).
- **Docs / config**: `env.example`, `docs/REDIS_SETUP.md` for Redis and GeoLite-related settings.

## [5.75.0] - 2026-04-11

### Added
- **i18n**: `TIER_27_UI_LOCALE_CODES` in `frontend/src/i18n/locales.ts` — alias of `INTERFACE_LANGUAGE_PICKER_CODES` for scripts, QA scope, and docs (Belt and Road tier-27 alignment).
- **i18n tooling**: `frontend/scripts/check-ui-translation-coverage.ts` for tier-27 UI translation coverage checks.
- **Region helpers**: `frontend/src/composables/auth/useRegisterRegionDetection.ts`, `frontend/src/utils/clientRegion.ts`; `utils/email_mainland_china.py` with `tests/utils/test_email_mainland_china.py`.
- **Validation**: `scripts/check_sms_email_message_languages.py` for SMS/email message language coverage.

### Changed
- **i18n**: Large sweep of message-module translations across locales (`auth`, `canvas`, `admin`, `common`, `community`, `knowledge`, `mindmate`, `notification`, `sidebar`, `workshop`); updates to `frontend/scripts/translate-ui-locales-from-en.ts` and `hi` bundle layout where applicable.
- **Auth (frontend)**: `LoginModal.vue`, `useLoginModal.ts`, and `frontend/src/utils/apiClient.ts` for login flow, region-aware registration, and API error handling.
- **Auth (backend)**: `routers/auth/login.py`, `email.py`, `public.py`, `registration_overseas.py`, `sms.py`; `models/requests/requests_auth.py`; `models/domain/messages.py` for request validation and user-visible strings.
- **Email and GeoIP**: `services/auth/geoip_country.py`, `services/auth/ses_service.py` and related router wiring; tests in `tests/services/test_geoip_country.py`, `tests/models/test_send_email_code_request.py`.
- **Config**: `config/rate_limiting.py` — default `EMAIL_MAX_CONCURRENT_REQUESTS` raised from 10 to 50; `env.example` aligned with current environment variables.

## [5.74.0] - 2026-04-09

### Added
- **Alembic**: `rev_0005_user_api_tokens`, `rev_0006_user_email_overseas_registration`, `rev_0007_user_email_login_cn_whitelist`; baseline revisions renamed to `rev_0001` / `rev_0002` / `rev_0004` naming.
- **Email and registration**: `routers/auth/email.py`, `registration_overseas.py`, `personal_token.py`; AWS SES (`ses_service.py`), email middleware, Redis-backed email storage; GeoIP country helper (`geoip_country.py`); disposable-domain list `data/kikobeats_free_email_domains.json`; `utils/email_validation.py` and `utils/chinese_language_policy.py` for signup/login rules.
- **User API tokens**: `models/domain/user_api_token.py`, `utils/auth/user_tokens.py`, `redis_user_token_cache.py`; token flows aligned with auth routers and preferences.
- **MCP** (`services/mcp/`): scaffolding for MCP-related integration.
- **SWOT academic** (`services/auth/swot_academic.py`, `scripts/swot/`, `scripts/update_swot_upstream.*`): upstream sync helpers and tests (`tests/services/test_swot_academic.py`).
- **Tests**: `tests/services/test_geoip_country.py`, `test_redis_user_cache_whitelist.py`, `tests/models/` additions.

### Changed
- **Auth stack**: Session, login, password, phone, SMS, avatar, preferences, admin org/user/role routes; `models/domain/auth.py`, `messages.py`, `requests_auth.py`; password security, account lockout, authentication and token utilities; HTTP middleware and registration metrics; Redis `keys` and `redis_user_cache` behavior.
- **Frontend auth and account**: `LoginModal.vue`, `AccountInfoModal.vue`, `ApiTokenModal.vue`, `LanguageSettingsModal.vue`, mobile account page, auth store and types, layouts, `components.d.ts`, `locales` (`en`/`zh` auth).
- **Inline AI**: Prompt modules for all diagram types in `agents/inline_recommendations/prompts/` plus `utils/prompt_locale.py`; `inline_recommendations` and `node_palette_streaming` routers; `relationship_labels` generator and router.
- **Config**: `config/features_config.py`, `config/rate_limiting.py`, `env.example`, `.gitignore`.

## [5.73.0] - 2026-04-07

### Added
- **OpenClaw user API token** (`mgat_`): `user_api_tokens` model + Alembic migration; Redis cache keyed by token hash; `validate_user_token` with `Authorization: Bearer` + `X-MG-Account` (phone) binding; `POST/GET/DELETE /api/auth/api-token` (session mints token; rate-limited POST); `ApiTokenModal.vue` + **API Token** entry in `AccountInfoModal.vue`.
- **Diagram node ops API** (`diagram_node_ops.py`): `PATCH /api/diagrams/{id}/nodes` (spec replace or structured add/update/delete) and `GET /api/diagrams/{id}/png` (screenshot + signed URL; rate-limited).
- **OpenClaw skill** (`openclaw/skills/mindgraph/SKILL.md`, `README.md`): env vars, auth headers, generate/save/patch/recommendations flow; publish instructions for ClawHub.
- **Canvas virtual keyboard** (`CanvasVirtualKeyboardPanel.vue`): On-screen keyboard using `simple-keyboard` and `simple-keyboard-layouts`, scoped to focused plain `input`/`textarea` (e.g. node labels, title); respects RTL UI locales; Escape closes; first-open hint via notifications.
- **`keyboardLayoutForUiLocale.ts`**: Maps MindGraph UI locales to keyboard layout presets (Arabic, Chinese, Japanese, Korean, Thai, etc.) with English fallback for unmapped codes.
- **`uiConfig.ts` — `CANVAS_OVERLAY_Z`**: Z-index ladder for Teleported canvas overlays (virtual keyboard below typical Element Plus chrome).
- **`scripts/verify-keyboard-layout-map.ts`**: CI-style check that keyboard layout locale mapping stays aligned with supported UI locales (`npm run i18n:verify-keyboard`).

### Changed
- **Canvas chrome** (`CanvasToolbar*.vue`, `CanvasTopBar.vue`, `PresentationSideToolbar.vue`, `CanvasPage.vue`): Toolbar, dropdowns, AI section, and presentation rail refinements; virtual keyboard wiring and related composable/config updates (`useCanvasToolbarApps.ts`).
- **Diagram nodes** (`BraceNode.vue`, `CircleNode.vue`, `FlowNode.vue`, `FlowSubstepNode.vue`, `TopicNode.vue`): Layout and editing tweaks aligned with recent canvas and measurement behavior.
- **Spec loaders** (`braceMap.ts`, `bubbleMap.ts`, `circleMap.ts`, `flowMap.ts`, `mindMap.ts`) and **`mindMapLayout.ts`**: Loader and layout store adjustments.
- **i18n**: `en`/`zh` canvas and common strings plus broad `common` bundle updates across locales for new UI copy.

## [5.72.0] - 2026-04-05

### Added
- **`InlineEditableText.vue` — `autoWrap` prop**: When enabled, bypasses the JS single-line heuristic (`shouldPreferSingleLineNoWrap`) and delegates line-breaking entirely to the browser via CSS `text-wrap: balance`. `maxWidth` acts as a safety cap only. Adds `.inline-edit-display--auto-wrap` CSS class and sets `line-height: 1.4` on the display element.
- **`utils.ts` — `estimateContextCircleDiameter`**: New DOM-based context-circle sizing that computes a balanced line layout (single-line width vs. `CONTEXT_MAX_TEXT_WIDTH` cap), then derives the required circle diameter from the content diagonal rather than a fixed max. Exports `CONTEXT_MAX_TEXT_WIDTH = 140`.
- **`textMeasurementFallback.ts` — Southeast-Asian script support**: Added `isSoutheastAsianChar` covering Thai (U+0E00–0E7F), Lao (U+0E80–0EFF), Khmer (U+1780–17FF), and Myanmar (U+1000–109F); when ≥ 30 % of glyphs are South-East Asian the `computeScriptAwareMaxWidth` scale floor is raised to 1.3.

### Changed
- **All diagram node components** (`BraceNode.vue`, `BranchNode.vue`, `BubbleNode.vue`, `CircleNode.vue`, `FlowNode.vue`, `FlowSubstepNode.vue`, `TopicNode.vue`): Replaced `computeScriptAwareMaxWidth` with DOM-based `measureTextWidth` for computing the balanced container width. Each node now calculates the number of expected lines and passes a narrowed `maxWidth` to `InlineEditableText`, while setting `auto-wrap` so the browser handles the actual breaking via CSS; no more character-counting CJK/Latin heuristics in node template logic.
- **`circleMap.ts`**: Switched context-node sizing to `estimateContextCircleDiameter` (replaces `computeMinDiameterForNoWrap`); removed hard-coded `noWrap: true` from context node styles; added `estimatedWidth` / `estimatedHeight` fields to topic and context node `data` objects.
- **`braceMap.ts`**: Increased `BRACE_NODE_BASE_MAX_TEXT_WIDTH` 240 → 350 and `BRACE_MAX_NODE_WIDTH` 280 → 400; width estimation now applies a balanced-line approximation (mirrors `text-wrap: balance`) instead of simply clamping to max; removed `computeScriptAwareMaxWidth` dependency.
- **`mindMap.ts`**: Branch and topic width/height estimation refactored to use DOM `measureTextWidth` with balanced-line logic (`computeBalancedMaxWidth`) instead of CJK character-count heuristics; server-side rendering falls back to approximate character widths.
- **`treeMapTopicLayout.ts`**: Switched from `computeScriptAwareMaxWidth` to `computeBalancedMaxWidth` (DOM-based) for topic width in tree maps.
- **`multiFlowMap.ts`**: Simplified cause/effect column width calculation to use `computeFlowNodeWidth` (text measurement only); removed DOM-measured Pinia widths from the width-uniformity pass to prevent stale font-load timing from locking in wrong widths.
- **`treeMap.ts`**: `resolveTreeMapBox` now prefers the computed (text-measurement) width and uses the Pinia-measured height when available, preventing stale or zero-height values from breaking layout.
- **`CircleNode.vue` — diagonal-based markdown sizing**: `measureRenderedMarkdownAndReport` uses `sqrt(w² + h²)` (content diagonal) instead of `max(w, h)` so that rendered markdown/KaTeX correctly fills tall circular containers; ResizeObserver now targets both `.diagram-node-md` and `.inline-edit-display`.
- **`server_launcher.py`**: Removed SQLite-to-PostgreSQL migration import and startup execution block; the legacy `data_migration.migrate_sqlite_to_postgresql` check is no longer performed at launch.

## [5.71.0] - 2026-04-04

### Added
- **Alembic revision `0004`** (`alembic/versions/rev_0004_auth_fk_indexes.py`): Indexes on `users.organization_id` and `api_keys.organization_id`; `ON DELETE SET NULL` on both organization FKs so org deletion does not block; database-level `UNIQUE` on `organizations.invitation_code` (aligned with the ORM).
- **`services/redis/keys.py`**: Single registry for Redis key patterns and TTL constants consumed by cache and session modules.
- **`services/redis/cache/redis_api_key_cache.py`**: Cache-aside Redis layer for API key validation (JSON payload by SHA-256 key fragment, 5-minute TTL) plus Redis `INCR` usage counters to cut Postgres load on authenticated API-key traffic.

### Changed
- **`models/domain/auth.py`**: `invitation_code` unique at the model; `User.organization_id` and `APIKey.organization_id` use `ondelete="SET NULL"` and are indexed to match migration and query patterns.
- **`models/domain/knowledge_space.py`**: Replaced `backref` usage with explicit `back_populates` graphs (knowledge space ↔ queries/templates/evaluation datasets; documents ↔ batch, versions, relationships; chunks ↔ attachments/child chunks; query ↔ feedback/results, etc.) with consistent `lazy="selectin"` / cascade where appropriate.
- **`utils/auth/api_keys.py`**: Redis-first validation path with graceful fallback to Postgres; cache population and invalidation hooks on quota/usage updates; admin router and related paths updated to stay consistent.
- **Redis stack** (`redis_client.py`, `redis_session_manager.py`, `redis_cache_loader.py`, `redis_*` helpers, SMS/token/bayi/distributed-lock/activity modules): Refactored to use shared `keys` constants, clearer connection usage, and streamlined session refresh/invalidation behaviour.
- **Repository and services** (`repositories/base.py`, `services/feature_access/repository.py`, `document_batch_service.py`, `tasks/knowledge_space_tasks.py`, Gewe DB modules, library mixins, workshop chat channel/file services, `workshop_service.py`): Async/typing and Redis-aware paths aligned with the cache and auth changes.
- **Routers** (`routers/core/pages.py`, `community.py`, `debateverse.py`, `library/admin.py`, `school_zone.py`, `workshop_chat_ws.py`, auth login/admin): Adjusted for updated dependencies and behaviour.
- **Auth utilities** (`account_lockout.py`, `authentication.py`, `enterprise_mode.py`): Minor alignment with the session and cache updates.
- **Frontend diagram UX** (`BraceNode.vue`, `BranchNode.vue`, `BubbleNode.vue`, `TopicNode.vue`, `InlineEditableText.vue`, concept-map and recommendation pickers, `NodePalettePanel.vue`, `RootConceptModal.vue`): Small layout/editing and picker refinements.
- **Spec loaders** (`braceMap.ts`, `mindMap.ts`, `treeMap.ts`, `treeMapTopicLayout.ts`, `textMeasurement.ts`, `textMeasurementFallback.ts`) and **`frontend/src/styles/index.css`**: Measurement/layout tweaks for diagram types.

## [5.70.0] - 2026-04-02

### Added
- **Alembic migration infrastructure** (`alembic/`, `alembic.ini`, `alembic/env.py`): Formal schema-migration pipeline replaces ad-hoc inline migration code in `config/database.py`; `alembic upgrade head` is run automatically on startup via `init_db()`.
- **`models/domain/registry.py`**: Central model registry that imports every ORM model to guarantee registration on `Base.metadata` for Alembic autogenerate and startup seeding — eliminates scattered try/except import blocks.
- **Repository layer** (`repositories/`): New `base.py` with generic async CRUD helpers plus domain-specific repositories — `user_repo.py`, `diagram_repo.py`, `knowledge_repo.py`, `community_repo.py`, `library_repo.py`, `workshop_repo.py`.
- **PG-to-PG merge service** (`services/admin/pg_merge_service.py`, `services/admin/pg_merge_tables.py`): Non-destructive PostgreSQL dump analysis and merge via a temporary staging database using `pg_restore`; remaps user/org IDs by phone/org-name, merges every table in FK-safe order, then drops the staging database.
- **`services/admin/sqlite_orphan_service.py`**: SQLite orphan detection and cleanup functions extracted from `sqlite_merge_service.py` into their own module.
- **Admin DB UI — PG dump merge** (`AdminDatabaseTab.vue`): New panel to analyze and execute a PG-dump-to-live merge with table-level row counts (`staging_rows` / `live_rows`), skipped/merge table lists, elapsed-time reporting, and a confirmation dialog.
- **i18n — PG dump merge keys** (`locales/messages/*/admin.ts`): 14 new translation keys (`admin.database.pgAnalyze`, `pgAnalyzeError`, `pgAnalysisResult`, `pgSkippedTables`, `pgStagingRows`, `pgLiveRows`, `pgExecuteMerge`, `pgMergeConfirmTitle`, `pgMergeConfirmMsg`, `pgMergeSuccess`, `pgMergeError`, `pgMergeComplete`) propagated to all locale bundles.

### Changed
- **`config/database.py`**: Major refactor — all inline schema-migration code removed; introduces `AsyncSessionLocal` (async SQLAlchemy 2.0 session factory) alongside the legacy sync `SessionLocal`; model imports consolidated via `models.domain.registry`.
- **`models/domain/auth.py`**: `Base` migrated from `declarative_base()` to the SQLAlchemy 2.0 `class Base(DeclarativeBase)` pattern; all `datetime.utcnow` replaced with timezone-aware `datetime.now(UTC)`; `Organization.users` and `User.organization` relationships set to `lazy="selectin"`; `User.diagrams` gains `cascade="all, delete-orphan"` and `passive_deletes=True`.
- **All `models/domain/*.py`**: `datetime.utcnow` → `datetime.now(UTC)` across all model modules; SQLAlchemy 2.0 / PEP8 alignment (import cleanup, quote styles).
- **`services/llm/rag_service.py`**: `has_knowledge_base`, `retrieve_context`, and `_apply_metadata_post_filter` converted from sync SQLAlchemy `Session` to `AsyncSession` with `select()`-style queries; `ThreadPoolExecutor` removed in favour of `asyncio`.
- **`agents/core/workflow.py`**: RAG lookup updated to use `AsyncSessionLocal` context manager and `await` the async `rag_service` methods.
- **`routers/admin/database.py`**: Added `/analyze-dump` and `/merge-dump` endpoints backed by `pg_merge_service`; orphan helpers moved to `sqlite_orphan_service`; spurious `async` removed from sync router functions.
- **`services/admin/sqlite_merge_service.py`**: Orphan-cleanup functions split out to `sqlite_orphan_service`; org matching switched from phone to org-name; `datetime.utcnow` → `datetime.now(UTC)`.
- **`uvicorn_config.py`**: `SafeStreamHandler` and `_is_stream_usable` inlined directly (removed import dependency on `services.infrastructure.utils.logging_config`); PEP8 / type-annotation cleanup.
- **`prompts/`**: PEP8 alignment across all prompt modules — single quotes replaced with double quotes, trailing commas added, blank-line normalisation (`debateverse.py`, `main_agent.py`, `mind_maps.py`, `node_palette.py`, `prompt_to_diagram_agent.py`, `thinking_maps.py`, `voice_agent.py`).
- **Backend-wide PEP8 / Pylint pass**: All router, service, utility, and script modules — quote-style normalisation, UTC datetime usage, import cleanup, line-length fixes (`routers/**`, `services/**`, `utils/**`, `scripts/**`).
- **`frontend/src/locales/messages/en/canvas.ts`** and **`zh/canvas.ts`**: Canvas locale updates propagated alongside the admin locale additions.

## [5.69.0] - 2026-04-01

### Added
- **Extra UI locales** (`i18n/supportedUiLocalesExtra.ts`): Merged into `SUPPORTED_UI_LOCALES` — Bosnian (`bs`), Dhivehi (`dv`, RTL), Estonian (`et`), Lithuanian (`lt`), Latvian (`lv`), Macedonian (`mk`), Malayalam (`ml`), Pashto (`ps`), Slovak (`sk`), Slovenian (`sl`), Albanian (`sq`), each with full `locales/messages/<code>/` module bundles.
- **Diagram markdown lazy pipeline** (`composables/core/diagramMarkdownPipeline.ts`): Loads the markdown-it + KaTeX stack on demand for diagram label measurement so initial canvas chunks avoid pulling `useMarkdown` until math or markdown is needed; coordinates layout recalc via `diagram:layout_recalc_bump`.
- **Hindi UI modules** (`locales/messages/hi/`): Split from the monolithic `hi.ts` into the standard per-module layout (`admin`, `auth`, `canvas`, etc.) aligned with other locales.
- **i18n tooling**: `check-i18n-picker-stubs.ts` (guard for Settings picker), `translate-ui-locales-from-en.ts`, `analyze_i18n_en_parity.py`, `rewrite-pt-canvas-from-es.ts`, `setup-fetch-proxy.ts`, and `locales/i18n-stub-inventory.json` for translation workflow and parity checks.

### Changed
- **Interface language picker** (`i18n/locales.ts`): Expanded list (e.g. Spanish, Albanian, Persian, Uzbek, Tagalog) with stricter policy — codes appear only after all ten message modules are translated; documents `docs/i18n-belt-and-road-master-plan.md` and `npm run i18n:check-picker-stubs`; exports `INTERFACE_LANGUAGE_PICKER_LOCALE_COUNT`.
- **Tier-2 locale bundles**: Large translation and parity updates across existing `locales/messages/*` bundles (materialize/stub cleanup and copy improvements).
- **Backend UI language allowlist** (`utils/ui_languages.py`): New codes aligned with frontend (`bs`, `dv`, `et`, `lt`, `lv`, `mk`, `ml`, `ps`, `sk`, `sl`, `sq`).
- **Markdown / canvas UX**: `useMarkdown.ts`, `useDiagramNodeMarkdownDisplay.ts`, `useDiagramLabels.ts`, `textMeasurement.ts`, auth modals, `CanvasTopBar`, `ShareExportModal`, `InlineEditableText`, library snapshots, notifications, `MobileLayout` / mobile canvas, `main.ts`, `vite.config.ts`, and global styles — aligned with lazy markdown loading and RTL-capable locales (e.g. Dhivehi).
- **i18n plumbing**: `elementPlusLocale.ts`, `i18n/index.ts`, `check-i18n-keys.ts`, `package.json` / lockfile dependency updates.

## [5.68.0] - 2026-04-01

### Added
- **`sanitizeMarkdownItHtml`** (`composables/core/markdownKatexSanitize.ts`): Central helper that runs DOMPurify with the shared KaTeX/markdown tag allowlist so all markdown-it `v-html` paths use one XSS policy.
- **Startup security posture** (`services/infrastructure/lifecycle/lifespan.py`): Logs `DEBUG`, `LOG_LEVEL`, OpenAPI schema availability, `AUTH_MODE`, and warnings when `AUTH_MODE=enterprise` or `LOG_LEVEL=DEBUG` with `DEBUG=False`.

### Changed
- **Markdown panels**: `AskOncePanel.vue`, `DebateMessage.vue`, `ShareExportModal.vue`, and `mindmate/MessageBubble.vue` now sanitize rendered HTML via `sanitizeMarkdownItHtml` (replacing ad hoc DOMPurify calls where applicable).
- **OpenAPI in production** (`main.py`): `/openapi.json` is served only when `DEBUG=True`, matching `/docs` and `/redoc` (reduces schema and route enumeration when debug is off).
- **PNG export logging** (`routers/api/png_export.py`): Request logs use prompt length and SHA-256 prefix instead of logging raw user prompt text.
- **Image proxy** (`routers/api/image_proxy.py`): HTTP client no longer follows redirects; 3xx responses return a clear error so callers must supply the final image URL.
- **Invalid API key logging** (`utils/auth/api_keys.py`): Logs a SHA-256 fingerprint instead of a key prefix.
- **Enterprise auth documentation**: `env.example`, `utils/auth/config.py`, `utils/auth/enterprise_mode.py`, and `models/domain/env_settings.py` clarify that enterprise mode disables JWT validation and is only for isolated networks; `enterprise_mode` cache globals renamed to `_ORG_CACHE` / `_USER_CACHE` (PEP8).

## [5.67.0] - 2026-03-31

### Changed
- **Python codebase**: PEP8 / Pylint alignment across agents, clients, config, routers, services, utils, and tests—formatting, imports, line length, and string quoting; LF line endings on version-controlled Python sources.
- **Gewe client**: Removed legacy `clients/gewe.py`; the WeChat API client is provided only via the `clients/gewe/` package.
- **Root `VERSION`**: Bumped to match this release (the root file had remained at 5.65.0 while 5.66.0 shipped in the frontend).
- **Tooling**: `pyproject.toml` and related project metadata updates.

## [5.66.0] - 2026-03-31

### Added
- **Tree Map** (`stores/specLoader/treeMap.ts`): New diagram type with center-aligned vertical group layout — topic pill at top, categories spread horizontally, leaves stacked vertically below each category; adaptive column widths via DOM text measurement; post-render re-layout via `recalculateTreeMapLayout` that prefers Pinia DOM dimensions over text estimates (KaTeX-aware).
- **Bridge Map** (`stores/specLoader/bridgeMap.ts`): New diagram type with horizontal analogy-pair layout — left/right branch nodes above/below a centre line, dimension label on the far left; supports both old `pairs` (top/bottom) and new `analogies` (left/right) spec formats; post-render layout correction via `recalculateBridgeMapLayout`.
- **KaTeX / math rendering**: Added `katex`, `@vscode/markdown-it-katex`, and `mathlive` dependencies; `useMarkdown.ts` integrates the KaTeX plugin (same `katex` instance extended by `katex/contrib/mhchem` for `\ce` chemistry notation); exposes `renderMarkdownForDiagramLabelMeasure` used by layout measurement so node width matches actual canvas output. Vite configured with `optimizeDeps`, `dedupe: ['katex']`, and `<math-field>` custom-element support.
- **Text measurement** (`stores/specLoader/textMeasurement.ts`): DOM-based measurement utilities including `measureRenderedDiagramLabelWidth` and `measureRenderedDiagramLabelHeight` that run the full markdown + KaTeX pipeline in a hidden element; used by tree map, multi-flow map, and circle map for accurate initial layout before the canvas renders.
- **Diagram default labels** (`stores/diagram/diagramDefaultLabels.ts`): Centralised default label text definitions for all diagram types (336 lines).

### Changed
- **`TopicNode.vue`**: After editing, flushes DOM dimensions to Pinia and awaits `document.fonts.ready` + RAF before emitting `multi_flow_map:topic_width_changed`, ensuring multi-flow column widths are computed from post-KaTeX rendered sizes rather than the raw element offset.
- **`InlineEditableText.vue`**: Substantial refactor of inline node editing behaviour (87 lines changed).
- **`CircleNode.vue`**: Major rework (143 lines) — circle sizing and text-fit logic updated.
- **`CanvasToolbar.vue` / `CanvasToolbarTextDropdown.vue`**: Canvas toolbar layout and text-style dropdown updates.
- **`useNodeDimensions.ts`**: Now returns `{ reportDimensions }` so callers can manually flush observed dimensions into Pinia after async rendering steps (fonts, KaTeX).
- **`nodeDimensionSlice.ts`**: Extended the diagram node-dimension Pinia slice.
- **`nodeManagement.ts`, `specIO.ts`, `vueFlowIntegration.ts`**: Diagram store updates aligned with new diagram types and dimension tracking.
- **`specLoader` (braceMap, circleMap, conceptMap, mindMap, multiFlowMap, treeMapTopicLayout, utils, index)**: Layout and spec-loading improvements; `index.ts` now exports `recalculateBridgeMapLayout` and `recalculateTreeMapLayout`.
- **`useMarkdown.ts`**: Integrates KaTeX + mhchem into the markdown-it pipeline; DOMPurify config updated for KaTeX output.
- **`useEventBus.ts`**: New event types added for diagram layout coordination.
- **`styles/index.css`**: 105 lines of new CSS for KaTeX display and new diagram node types.
- **`diagramHtmlToImage.ts`**: Minor utility update.
- **i18n**: Canvas and sidebar message updates propagated across all tier-2 locale bundles.

## [5.65.0] - 2026-03-30

### Added
- **CanvasChrome.vue**: Sticky header wrapper that merges the canvas top bar and editing toolbar on one row (`CanvasPage.vue`).
- **presentationPointer store**: Per-tool scale for laser, spotlight, highlighter, and pen in presentation mode; values persist in `localStorage` and adjust via wheel in `useCanvasPagePresentation`.
- **diagramHtmlToImage.ts**: Shared `html-to-image` options for diagram and community export (consistent rasterization, exclude Vue Flow minimap, `waitForNextPaint` after DOM updates).
- **Linux setup — Redis key-memory histograms** (`scripts/setup/setup.py`): When Redis is 8.6+ and `redis.conf` is found, enables `key-memory-histograms yes` and restarts Redis during `install_redis_linux_official_apt()`.

### Changed
- **Canvas & presentation**: `CanvasToolbar`, `CanvasTopBar`, `ZoomControls`, `PresentationSideToolbar`, `PresentationTimerOverlay`, `ExportToCommunityModal`, `DiagramCanvas`, `PresentationHighlightOverlay`, diagram canvas composables (`useDiagramCanvasEventBus`, context menu, fit, Vue Flow UI, export), `useCanvasPagePresentation`, `useViewManager`, `uiConfig`, and `CanvasPage` layout/CSS.
- **Types & stores**: Diagram types and store barrel; `components.d.ts` for new canvas exports.
- **i18n**: Canvas message updates across locale bundles.

## [5.64.0] - 2026-03-29

### Added
- **Password change captcha**: `ChangePasswordModal.vue` now requires captcha verification before submitting; auto-loads on open, refreshes on error, and triggers `authStore.logout()` after success (server revokes all sessions). Backend `ChangePasswordRequest` gains `captcha` / `captcha_id` fields; `change_password` endpoint is now async with captcha verification via `verify_captcha_with_retry` and `_raise_for_captcha_failure`.
- **AccountInfoModal — change-password entry**: "Change password" button added directly next to "Change phone" inside `AccountInfoModal.vue`; `ChangePasswordModal` embedded inline.
- **IntlShareSiteModal**: New `IntlShareSiteModal.vue` component wired to the avatar dropdown on the International landing page (command `share-site`).
- **Password security helpers** (`services/auth/password_security.py`): `invalidate_user_cache_after_password_write` and `revoke_refresh_tokens_and_sessions` extracted as shared utilities; used by `routers/auth/password.py`, `routers/auth/admin/users.py`, and admin user endpoints to eliminate duplicate logic.
- **Redis startup SMS lock** (`services/redis/redis_distributed_lock.py`): `acquire_startup_sms_notification_lock` / `release_startup_sms_notification_lock` using Redis `SET NX` to ensure exactly one worker sends the startup SMS in a multi-worker Uvicorn cluster.
- **Uvicorn `timeout_worker_healthcheck`** (`server_launcher.py`): Configurable via `UVICORN_TIMEOUT_WORKER_HEALTHCHECK` (default 120 s); logged on multi-worker start with guidance on distinguishing healthcheck timeouts from real crashes.

### Changed
- **InternationalLanding.vue**: Teleported the top-right nav (`IntlModuleGrid` + avatar dropdown) to `<body>` via `<Teleport>` to prevent position:fixed interference from ancestor CSS transforms/filters; removed collaboration dialogs (org sessions, shared-code join) and `showPasswordModal` flow; added `IntlShareSiteModal` and `share-site` avatar command.
- **AppSidebarAccountFooter / useAppSidebar**: Removed the "Change password" dropdown item and `openPasswordModal` / `showPasswordModal` state — password change is now accessible from within `AccountInfoModal`.
- **MindGraphContainer header**: Title centered; action buttons absolutely positioned to the right.
- **Startup SMS** (`lifespan.py`): Extracted into `_send_startup_sms_notification_once()` guarded by the Redis startup lock instead of the unreliable `UVICORN_WORKER_ID == '0'` check.
- **Redis client**: `key-memory-histograms` config failure downgraded from `WARNING` to `INFO` with a clearer explanation (optional Redis 8.6+ feature, often blocked by `redis.conf` or ACLs).
- **i18n**: Added `auth.changePhoneButton`, `auth.passwordChangeSuccess`, `auth.passwordChangeFailed`, `auth.captcha`-related keys and `auth.modal.*` keys (en / zh / zh-tw auth bundles); propagated `auth.changePhoneButton` and related common keys across all 50+ tier-2 locale `common.ts` bundles.

## [5.63.0] - 2026-03-29

### Added
- **International landing — saved diagrams**: `IntlDiagramDropdown.vue` — scrollable library under the prompt bar (rename, delete, slot counter, open on select) wired to `useSavedDiagramsStore` and auth.

### Changed
- **International UI**: Updates to `InternationalLanding.vue` and `IntlModuleGrid.vue` for diagram entry and module navigation.
- **Canvas & nodes**: `CanvasToolbar.vue`, `BranchNode`, `BubbleNode`, `FlowSubstepNode`, `InlineEditableText`, `LabelNode` — editing, layout, and interaction polish.
- **Diagram editor**: `useDiagramOperations`, `useDiagramCanvasEventBus`, `applySelection`; diagram store (`diagram.ts`, mind map / brace map ops, node management, constants, default labels); `specLoader` (`flowMap`, `defaultTemplates`, `utils`).
- **Auth & routing**: `AuthLayout`, `AuthPage`, `useLoginModal`, `router/index.ts` alignment with auth flows.
- **Admin**: `AdminTrendChartModal.vue` adjustments.
- **i18n**: Canvas and sidebar message updates across many locale bundles.

## [5.62.0] - 2026-03-28

### Added
- **Tier-2 UI locales**: Materialized `common` and `canvas` bundles for 50+ additional languages; `supportedUiLocales.ts` registry; Traditional Chinese (`zh-tw`) generated from Simplified Chinese via `build-zhtw-from-zh.ts`.
- **i18n / canvas pipeline**: Scripts for canvas key extraction and English JSON export, locale bundle emission, tier-2 build orchestration, and `translate_canvas_tier2.py`; flat JSON assets (e.g. `canvas-*-flat.json`) to support translation workflows.
- **Auth entry pages**: `AuthPage.vue` and `RootHome.vue` for a unified auth and home entry path alongside modal-based login.

### Changed
- **Auth & routing**: Removed standalone `LoginPage.vue`; routing uses `AuthPage`, `AuthLayout`, and updated guards in `router/index.ts` and `pages/index.ts`; `useLoginModal`, `LoginModal`, `DemoLoginPage`, and mobile account flows aligned.
- **Backend**: `models/requests/requests_auth.py` and `utils/ui_languages.py` updated for UI language lists and preference validation consistent with the expanded frontend locales.
- **i18n integration**: `locales.ts`, `i18n/index.ts`, `elementPlusLocale.ts`, and `scripts/check-i18n-keys.ts`; widespread `$t` key and Element Plus API updates across canvas, diagram, admin, MindMate, knowledge space, and settings components.
- **Tooling**: ESLint config and frontend dependencies refreshed (`package.json` / lockfile).

## [5.61.0] - 2026-03-27

### Added
- **International UI version**: Google-style landing page (`InternationalLanding.vue`) with centered hero (logo + title side-by-side), pill-shaped prompt bar for AI diagram generation, and large diagram-type card grid with staggered pulse hover animations.
- **UI version persistence**: `ui_version` column on `users` table (PostgreSQL + custom migration), `PATCH /api/auth/language-preferences` and `GET /api/auth/me` support, localStorage sync, and browser-language auto-detection (`zh` → Chinese, else International) for first-time visitors.
- **Module grid menu**: `IntlModuleGrid.vue` — feature-gated 3×3 popover grid replacing sidebar navigation in International mode; shown in InternationalLanding top-right and as floating button on non-landing pages.
- **UI version selector**: Radio group in `LanguageSettingsModal` to switch between Chinese and International versions; navigates to the correct default page after switching.

### Changed
- **MainLayout**: Sidebar conditionally hidden when International version is active; ICP footer shown only in Chinese version.
- **Router**: Added guard redirecting `/mindmate` → `/mindgraph` when `uiVersion === 'international'`; `'/'` follows the same redirect chain.
- **LanguageSettingsModal**: Uses `value` prop instead of deprecated `label` for `el-radio` (Element Plus 2.13 compatibility).
- **DiagramPreviewSvg**: Fixed circle-map outer ring and long connector paths (tree map, brace map, bridge map) broken by `stroke-dasharray: 100` — changed to `anim-connector`/`anim-ring` classes; removed `max-height: 80px` constraint.
- **Diagram card animations**: Replaced fade-in/fade-out (`intlAddNode`) with staggered per-node pulse animation using `:nth-child(n of .anim-node)` matching old gallery style.
- **i18n**: Updated slogan to "宇宙中最强大的AI思维图示生成软件"; renamed "语言与提示词" → "语言设置"; added module grid and version setting keys across zh/en/az.

## [5.60.0] - 2026-03-27

### Added
- **Composable domains**: New groupings and helpers — `canvasPage/` (presentation, workshop collab, library snapshots, editor shortcuts, diagram event bus), `canvasToolbar/` (apps, formatting), `diagramCanvas/` (Vue Flow handlers, viewport/zoom, mobile touch, export, fit, concept-map link preview), `auth/useLoginModal`, `sidebar/useAppSidebar`, `teacherUsage/`, and node-palette streaming/errors/session keys; `workshop/`, `knowledge/`, `mindmate/` moves from flat composables.
- **Split UI components**: `CanvasToolbar` subcomponents (add/delete, AI, style/text/border/background/more-apps dropdowns, undo/redo), `PresentationSideToolbar`, `PresentationTimerOverlay`, `DiagramCanvasZoomPaneOverlays`, `AppSidebarNav`, `AppSidebarAccountFooter`, `TeacherUsageDialogs`; `diagramCanvas.css`, `diagramCanvasVueFlowTypes.ts`, `CanvasPage.scoped.css`, `imageViewer.css`.
- **Utilities**: `colorFormat.ts`; diagram diff/type maps and related canvas-page utilities.

### Changed
- **Composable layout**: Shared code under `composables/core/`; editor and diagram editing under `composables/editor/` and `composables/diagrams/`; barrel `composables/index.ts` and imports updated across pages, stores, and components.
- **Stores & API**: Diagram store/spec-loader/vue-flow integration updates; `routers/api/diagrams.py` aligned with frontend diagram handling.
- **i18n**: Locale messages (en/zh/az) and tooling (`check-i18n-keys.ts`, `split-locale-bundles.ts`) updated for new structure and strings.

## [5.59.0] - 2026-03-26

### Added
- **Per-feature organization/user access**: SQLAlchemy models (`FeatureAccessRule`, `FeatureAccessOrgGrant`, `FeatureAccessUserGrant`), `FeatureOrgAccessEntry` DTO, `services/feature_access/repository.py` with Postgres load/replace and Redis cache (`redis_feature_org_access_cache`), admin GET/PUT `/api/auth/admin/feature-org-access`, and `feature_org_access` on `/config/features` for authenticated clients.
- **Admin Features tab**: `AdminFeaturesTab.vue` for toggling `FEATURE_*` flags (env + runtime reload) and editing DB-backed org/user allowlists; i18n (en/zh/az).
- **HTTP feature-flag gate**: `feature_gate.py` middleware returns 404 JSON for feature API URL prefixes when the corresponding `FEATURE_*` env flag is off (covers workshop chat, library, community, knowledge space, school zone, DebateVerse, AskOnce, devices, gewe, and related admin paths).
- **Presentation mode highlighter**: `PresentationHighlightOverlay.vue`, `presentationHighlighter.ts` stroke palette, types on `PresentationHighlightStroke`, wired through `DiagramCanvas`, `CanvasPage`, toolbar, and context menu.

### Changed
- **Workshop Chat access**: `can_access_workshop_chat` / `user_has_feature_access` in `utils/auth/roles.py` respect DB rules and global flags; WebSocket and REST paths aligned; `workshopAccess.ts` mirrors server logic using `feature_org_access.feature_workshop_chat` with legacy preview-org fallback.
- **Feature flags & routing**: `useFeatureFlags`, `featureFlags` store, and `router/index.ts` consume `feature_org_access` for gating; `auth` dependencies and workshop chat router updated accordingly.
- **Infrastructure**: `middleware`, lifecycle/startup, server launcher, logging, and admin env wiring updated to register the feature gate and new admin routes.

## [5.58.0] - 2026-03-26

### Added
- **Flow map — post-render layout correction**: `recalculateFlowMapLayout` in `specLoader/flowMap.ts` uses DOM-measured node dimensions to center-align the topic node with step nodes after the first render (horizontal: corrects Y; vertical: corrects X). Wired into `vueFlowIntegrationSlice` via a reactive `flowMapLayoutNodes` computed.
- **Flow map — dimension preservation across spec reloads**: `specIO.ts` captures existing `nodeDimensions` before clearing on same-type reloads (add/delete step). Previously measured sizes are restored for reused nodes so layout correction fires immediately without waiting for `ResizeObserver` to re-fire.
- **Qdrant service split — `qdrant_diagnostics.py` and `qdrant_startup.py`**: Extracted compression-metrics helpers (`QdrantDiagnosticsMixin`) and startup/error utilities (`parse_qdrant_host_port`, `QdrantStartupError`, `_log_qdrant_error`) into two new modules; `QdrantService` now imports from them, reducing its size and improving separation of concerns.
- **Backup manifest co-deletion**: `backup_scheduler.py` now deletes companion `.manifest.json` files alongside their pg_dump archives during both COS cleanup (`cleanup_old_cos_backups`) and local backup rotation (`cleanup_old_backups`). `_write_backup_manifest` helper writes table row counts and summary statistics alongside pg_dump files.
- **`database_export_service.py` — shared manifest builder**: Extracted `_build_manifest` helper (filename, size, table row counts, column totals) used by `export_postgres_dump`; aligns manifest structure with `backup_scheduler` and `dump_import_postgres`.
- **`dashboard_install.py`**: Consolidated IP geolocation and dashboard asset installer (ECharts bundle, China GeoJSON, ip2region xdb databases, patch cache) extracted from the old setup script into its own standalone script with interactive prompts and `MINDGRAPH_NON_INTERACTIVE=1` CI support.
- **`setup.py` — monolithic unified installer**: Absorbed Redis ≥ 8.6, PostgreSQL ≥ 18.3, Qdrant, Tesseract OCR, Playwright (with `--with-deps` on Linux), system-package, and interactive-prompt logic. Privilege check on Linux; `MINDGRAPH_NON_INTERACTIVE=1` for CI. Old split helper scripts (`install_dependencies.sh`, `install_qdrant.sh`, `install_qdrant.py`, `download_dashboard_dependencies.py`, `download_ip2region_db.py`, `apply_ip2region_patches.py`, `embed_china_geo.py`) removed.
- **`recovery_startup.py` — inline kill-9 cleanup helper**: `_cleanup_user_documents` extracted to isolate per-user document cleanup, removing the `DatabaseRecovery` class import dependency.

### Changed
- **Flow map nodes — adaptive height**: `FlowNode.vue`, `FlowSubstepNode.vue`, and `TopicNode.vue` switch fixed `height` to `min-height` in both inline styles and scoped CSS, allowing multi-line text to expand node height. `TopicNode` also removes fixed `py-4` padding in flow-map context (`py-3`) and lifts `max-width` cap (`none`) for the topic node.
- **Flow map substep add — substep-aware parent lookup**: `CanvasToolbar.vue` and `useNodeActions.ts` handle `flowSubstep` selection when "Add Node" / "Add Child" is triggered, parsing the parent step index from the substep ID (`flow-substep-{stepIndex}-*`) and routing the add to the correct step. Previously, only step-type selection triggered substep creation.
- **`pyproject.toml` — Pylint module-line limit raised**: `max-module-lines` increased from 800 to 3500 to accommodate the intentionally monolithic `scripts/setup/setup.py`. `extraPaths` updated to local Python 3.13 site-packages path.
- **`requirements.txt` / `env.example`**: Updated install references from old shell scripts to `sudo python3 scripts/setup/setup.py` and `dashboard_install.py`; updated `DB_QUICK_CHECK_ENABLED` note to `SKIP_INTEGRITY_CHECK`.

### Removed
- **`scripts/setup/install_dependencies.sh`**, **`install_qdrant.sh`**, **`install_qdrant.py`**, **`download_dashboard_dependencies.py`**, **`download_ip2region_db.py`**, **`apply_ip2region_patches.py`**, **`embed_china_geo.py`**: Superseded by `setup.py` and `dashboard_install.py`.
- **`services/infrastructure/recovery/database_recovery.py`**: `DatabaseRecovery` class removed; startup recovery logic consolidated in `recovery_startup.py`.

## [5.57.0] - 2026-03-26

### Added
- **Bundled tiktoken encoding (offline-safe startup)**: Shipped `resources/tiktoken_encodings/cl100k_base.tiktoken` (~1.7 MB) with the repo. When present, `ensure_tiktoken_cache()` sets `TIKTOKEN_CACHE_DIR` to that directory and skips HTTP/Redis cache coordination — no outbound fetch to `openaipublic.blob.core.windows.net` on startup. If the bundled file is absent, behavior falls back to `storage/tiktoken_cache/` with the previous download-and-update logic.

### Changed
- **`utils/tiktoken_cache.py`**: Refactored cache helpers (`_default_cache_dir_path`, `_set_tiktoken_cache_dir_env`, `_encoding_requires_download`, `_sync_one_encoding_if_needed`) for clarity and Pylint compliance.

## [5.56.0] - 2026-03-26

### Added
- **Unified node dimensions**: `useNodeDimensions` composable (ResizeObserver, debounced reporting) and `nodeDimensionSlice` in the diagram store — batch vs live `layoutRecalcTrigger` modes; diagram node components report measured width/height for layout.
- **Public site URL for admin links**: `EXTERNAL_BASE_URL` exposed via `/config/features` as `external_base_url`; `usePublicSiteUrl` composable; admin Schools tab and trend chart modals use it for invitation/share `siteUrl` text. Documented in `env.example`.
- **Canvas toolbar — text alignment**: Left/center/right alignment controls in the text format panel; `textAlign` applied to selected nodes with i18n (`canvas.toolbar.alignLabel`, en/zh/az).

### Changed
- **Brace map layout**: Removed Dagre dependency (`useDagreLayout.ts` deleted); `useBraceMap` and `specLoader/braceMap` refactored to use measured node dimensions and updated positioning logic.
- **Other diagram loaders & store**: Bubble map, circle map, and multi-flow map spec loaders; `vueFlowIntegration`, `specIO`, `mindMapOps`, `nodeManagement`, `nodeSwapOps`, and `braceMapOps` aligned with dimension-driven layout and recalculation.

### Removed
- **`frontend/src/composables/diagrams/useDagreLayout.ts`**: Replaced by DOM-measured layout paths.

## [5.55.0] - 2026-03-25

### Added
- **Mobile web shell (`/m/*`)**: `MobileLayout.vue` and pages (`MobileHomePage`, `MobileMindMatePage`, `MobileMindGraphPage`, `MobileCanvasPage`, `MobileAccountPage`); `useMobileDetect` composable; router guard auto-redirects mobile clients from desktop paths to `/m/*` (skips login, auth, demo, `/export-render`, dashboard, and routes already under `/m`).
- **`useNodeActions`**: Centralized event-bus handlers for add/delete node, branch, and child actions shared by the desktop toolbar and mobile canvas.
- **Diagram canvas — mobile touch**: `DiagramCanvas` custom pinch-zoom and single-finger pane pan (capture-phase, before d3-drag/d3-zoom); optional `panOnDragButtons` prop; `useBranchMoveDrag` touch integration; diagram node components and `InlineEditableText` updates for consistent mobile interaction.

### Changed
- **Vue Flow PNG export (Playwright)**: Pre-seed `sessionStorage` via `page.add_init_script` before `goto` `/export-render`; remove Element Plus message/notification overlays before capturing the screenshot.
- **Sidebar i18n**: Mobile-related sidebar strings (en, zh, az).

### Removed
- **`docs/ENDPOINTS_SUMMARY.md`**: Removed outdated endpoint summary.

## [5.54.0] - 2026-03-25

### Added
- **Diagram Snapshots — point-in-time restore**: New `DiagramSnapshot` model (`models/domain/diagram_snapshots.py`) stores up to 10 immutable JSONB copies of a diagram spec (LLM results excluded). Backend CRUD endpoints (`POST/GET/DELETE /api/diagrams/{id}/snapshots`, `POST .../recall`) with rate limiting, ownership checks, and automatic gap-free renumbering on delete/eviction. Frontend `useSnapshotHistory` composable, toolbar "Snapshot" button in More Apps, and numbered version badges in `CanvasTopBar` with click-to-recall and Ctrl+click-to-delete.
- **Admin Database Management tab**: New admin-only panel tab (`AdminDatabaseTab.vue`) backed by `routers/admin/database.py` and `services/admin/` (SQLite merge service, PG export/import service). Features: PostgreSQL table stats, backup-folder SQLite file scanning/analysis/merge with ID remapping, PG dump export/restore, and orphaned-record detection/cleanup. Full i18n coverage (en/zh/az).
- **Auto-save UX — dirty/saving indicators & relative timestamps**: `useDiagramAutoSave` now exposes `isDirty` and `isSaving` reactive flags with a typed `SaveFlushResult` return. Periodic 30-second interval save catches position/style-only edits via a new `getFullFingerprint` (includes node positions and styles). Save status badge shows color-coded state (blue = saving, amber = unsaved, gray = saved) with relative time labels ("Saved just now", "Saved Xs ago", "Saved Nmin ago"). Manual Ctrl+S shows success/failure notifications.
- **Element Plus programmatic-API styles**: Explicit CSS imports for `ElMessage`, `ElMessageBox`, `ElNotification`, and `ElLoading` in `main.ts` so programmatic calls render correctly with `unplugin-vue-components`.

### Changed
- **Security — authentication required on health endpoints**: `/health/websocket`, `/health/redis`, `/health/database`, `/health/all`, and `/health/processes` now require a valid JWT via `get_current_user`.
- **Security — DebateVerse hardening**: All endpoints migrated from `get_current_user_optional` to mandatory `get_current_user`; session ownership checks (403) added to coin-toss, advance-stage, stream-debater, and position-generation; request models use Pydantic `Field` validators with allow-listed formats, stages, models, roles, sides, and message length caps; rate limiting on LLM-streaming endpoints (30–60 req/min).
- **Security — AskOnce hardening**: `/askonce/stream/{model}` now requires authentication (was optional) with per-user rate limiting (60 req/min); model listing no longer exposes internal `model_name`.
- **Security — multi-LLM generation rate limiting**: `generate_multi_parallel` and `generate_multi_progressive` rate-limited to 20 req/min per user; error responses replaced with generic "Internal server error" (no stack traces).
- **Security — SSE & frontend logging**: SSE error payloads no longer expose `error_type` or raw exception text. Frontend log endpoint strips all control characters including `\n\r\t` (prevents log-line forging) and prefixes entries with `[FRONTEND]`.
- **Security — SSRF prevention**: Removed `localhost` and `127.0.0.1` from the image-proxy allowed-domain whitelist.
- **Security — health stats**: Database URL no longer included in health-check response payloads.
- **Health Monitor — direct function calls**: Replaced `httpx`-based localhost HTTP polling with direct calls to internal health-check functions (`_check_application_health`, `_check_redis_health`, `_check_database_health`, `_check_processes_health`), eliminating HTTP/auth overhead, the `httpx` dependency, and CLOSE_WAIT socket accumulation.
- **Router registration ordering**: Vue SPA catch-all route moved to the very last position; admin and feature API routers now register before it, fixing potential route shadowing.
- **Brand rename**: Page title changed from "MindGraph Pro" to "Mind Platform"; `app.brandName` and several `meta.pageTitle.*` i18n keys updated (en/zh/az).
- **CanvasTopBar filename display**: Long filenames truncated to 15 characters with an ellipsis; full name shown on tooltip hover.

## [5.53.0] - 2026-03-24

### Added
- **Redis Diagram Cache helpers module**: Extracted constants (`CACHE_TTL`, `SYNC_INTERVAL`, `SYNC_BATCH_SIZE`, `MAX_PER_USER`, `MAX_SPEC_SIZE_KB`), key templates, `_redis_json_get`, `_redis_json_set_paths`, and `count_diagrams_from_db` into new `services/redis/cache/_redis_diagram_cache_helpers.py`. `RedisDiagramCache` now requires PostgreSQL and uses `pg_insert` with `RETURNING` and JSONB spec column.
- **Redis Token Buffer → Streams**: Migrated token usage buffering from a Redis List (`tokens:buffer`) to Redis Streams (`tokens:stream`) with a consumer group (`token_flush_workers`) and per-worker consumer name, enabling at-least-once processing guarantees and no data loss on worker restart.
- **Embedding Cache — VSET semantic deduplication**: New `_vset_lookup` / `_vset_key` helpers in `EmbeddingCache` use the `VSIM` command (Redis >= 8.0) to find semantically similar cached query embeddings above a configurable cosine threshold (`VSET_SIMILARITY_THRESHOLD`, default 0.95), avoiding redundant embedding API calls for near-duplicate queries.
- **Redis startup configuration**: `_apply_redis_startup_config` and `_parse_redis_version` in `redis_client.py` apply version-gated `CONFIG SET` at startup — `volatile-lrm` eviction policy and `key-memory-histograms` enabled automatically for Redis >= 8.6 (overridable via `REDIS_EVICTION_POLICY`).
- **Health — enhanced Redis endpoint**: `GET /health/redis` now returns memory stats (`used_memory_human`, `used_memory_peak_human`, `mem_fragmentation_ratio`) and hot keys (`HOTKEYS`, Redis >= 8.6). All sync Redis calls wrapped in `asyncio.to_thread` with 2-second timeouts to keep the event loop non-blocking.
- **PostgreSQL JSONB column migration**: `_ensure_jsonb_columns` + `_JSONB_MIGRATIONS` list in `schema_migration.py` idempotently convert 30+ `Text`/`JSON` columns to `JSONB` (with GIN indexes) across `diagrams`, `community_posts`, `shared_diagrams`, `gewe_contacts`, `gewe_group_members`, all knowledge-space tables, `debate_judgments`, `library_danmaku`, `teacher_usage_config`, and `workshop_chat` message tables.

### Changed
- **Redis Activity Tracker — pipelined session reuse**: `_redis_start_session` now batch-checks all candidate sessions with a single pipelined `EXISTS` and updates the first live one in one pipeline, replacing the previous per-session sequential `EXISTS` + `HSET` calls for lower latency under concurrent users.
- **Diagram Cache quota fix**: `count_user_diagrams` now checks `redis.exists(meta_key)` before calling `zcard`, preventing an evicted/expired sorted-set key from reporting 0 and falsely bypassing the per-user quota.
- **`useDiagramAutoSave` suppress timer**: Replaced `suppressUntil` (`Date.now()` computed ref) with a `setTimeout`-based `isSuppressed` flag and `setSuppressWindow(ms)` helper; `suppressTimer` is cleared on `teardown()` to avoid memory leaks.
- **Redis Org / User / Community caches**: PEP8 compliance pass — renamed exception variables, fixed line lengths, improved type hints.
- **Workshop chat WS, community router, public dashboard, debateverse router**: Pylint/PEP8 compliance — consistent exception variable names, f-string/format cleanup, line length fixes.
- **Gewe contact / group member DB services**: Code quality improvements with consistent exception handling and type annotations.
- **Infrastructure process managers** (`_port_utils`, `_postgresql_manager`, `_postgresql_paths`, `_qdrant_manager`, `_redis_manager`): PEP8 compliance and minor refactoring.

## [5.52.0] - 2026-03-24

### Removed
- **Mind map backend layout endpoint**: Deleted `routers/api/layout.py` and the `POST /api/recalculate_mindmap_layout` endpoint; removed `RecalculateLayoutRequest` model from `models/requests/requests_diagram.py` and its export from `models/requests/__init__.py` and `models/__init__.py`. The backend `MindMapAgent` no longer participates in layout recalculation.
- **`useMindMap` composable**: Deleted `frontend/src/composables/diagrams/useMindMap.ts` (hybrid backend/Dagre layout orchestration, 631 lines) and removed its export from `composables/diagrams/index.ts` and the renderer reference in `frontend/src/renderers/index.ts`.
- **Frontend API layout helpers**: Removed `recalculateMindMapLayout`, `diagramDataToMindMapSpec`, and `MindMapSpec`/`MindMapBranchSpec`/`MindMapLayout`/`MindMapNodePosition` interfaces from `frontend/src/utils/api.ts`; updated `frontend/src/utils/index.ts` exports accordingly.

### Changed
- **Mind map layout — DOM-measured branch heights**: `estimateBranchNodeHeight` (CJK character counting heuristic) replaced by `measureBranchNodeHeight` in `frontend/src/stores/specLoader/mindMap.ts`, which delegates to `measureTextDimensions` (font 16px, `maxWidth` 150px) and adds `BRANCH_PADDING_Y` (16px) + `BRANCH_BORDER_Y` (6px), enforcing `BRANCH_NODE_HEIGHT` minimum. Dagre imports and all Dagre-based subtree/node flattening helpers (`getSubtreeHeight`, `flattenMindMapBranches`, `layoutMindMapSideWithClockwiseHandles`, etc.) removed from the spec loader; the mind map store is substantially simplified (~480 lines removed).
- **New layout spacing constants**: `MINDMAP_SIBLING_GAP` (20 px, vertical gap between sibling branch bottom/top edges) and `DEFAULT_MINDMAP_BRANCH_GAP` (70 px, vertical gap between top-level branches) added to `frontend/src/composables/diagrams/layoutConfig.ts`.
- **`mindMapLayout` store**: `useMindMapLayoutSlice` updated to use the new gap constants for column position recalculation (`frontend/src/stores/diagram/mindMapLayout.ts`).
- **`BranchNode.vue` / `TopicNode.vue`**: Minor updates aligned with the new DOM-measurement-driven layout flow.
- **`mind_map_agent.py`**: Layout-related server-side computation removed; agent retains generation responsibilities only.

## [5.51.0] - 2026-03-24

### Changed
- **Mind map layout — column-based stacking**: Replaced Dagre-based `layoutMindMapSideWithClockwiseHandles` with `layoutMindMapSideSimple`, a simpler column-stacking layout that assigns Y positions by vertical stacking with bottom-up centering and X positions by a column system keyed on depth. Adds `estimateTopicNodeWidth` and `estimateBranchNodeHeight` for text-aware sizing; removes `normalizeMindMapHorizontalSymmetry` and `normalizeBranchToChildSpans` normalize passes and associated debug logging.
- **Mind map reactive dimension tracking**: New `mindMapLayout.ts` store slice (`useMindMapLayoutSlice`, `recalculateMindMapColumnPositions`) enables DOM-measured node dimensions to feed back into layout. `BranchNode.vue` reports `offsetWidth`/`offsetHeight` on mount and text save; `TopicNode.vue` reports actual topic width on mount. Diagram store carries `mindMapNodeWidths`, `mindMapNodeHeights`, `mindMapRecalcTrigger`, `mindMapTopicActualWidth`, and `mindMapTopicBranchGaps` state refs; `vueFlowIntegration` uses the column recalculation in its computed node list.
- **Tree map topic node measured sizing**: New `treeMapTopicLayout.ts` (`measureTreeMapTopicDimensions`, `treeMapTopicPositionFromLayout`, `ensureTreeMapTopicLayout`, `applyTreeMapTopicLayoutToNodes`) replaces fixed `DEFAULT_NODE_WIDTH`/`DEFAULT_NODE_HEIGHT` for tree map topic nodes with text-measured pill dimensions. `TopicNode.vue` renders constrained `width`/`height` style for tree maps; `diagramNodeToVueFlowNode` forwards measured dimensions; `nodeManagement` applies layout on topic text update; `useTreeMap` composable and `treeMap` spec loader use the new helpers.
- **CanvasPage setup ordering**: Moved `getPanelCoordinator()` and `getNodePalette()` singleton creation from `onMounted` to the `<script setup>` top level so composables that use `useI18n` / `onUnmounted` run within the component setup context.
- **Minor cleanup**: Sorted imports (`DiagramCanvas.vue`, `CanvasPage.vue`, `DefaultLayout.vue`); removed redundant inline comments; formatted multi-line ternaries for consistency.

## [5.50.0] - 2026-03-24

### Added
- **Concept map — root concept**: Generate and stream root-concept suggestions over SSE (`routers/concept_map_focus.py`); registry prompts `concept_map_root_concept` / `concept_map_root_concept_suggestions`; frontend `conceptMapRootConceptApi.ts`, `ConceptMapRootConceptPicker.vue`, `RootConceptModal.vue`, `conceptMapRootConceptReview` store. Diagram and node-palette payloads include `root_concept` in educational context (`routers/node_palette_streaming.py`, `agents/node_palette/concept_map_palette.py`, diagram request types).
- **Concept map — focus question review UX**: Shared `conceptMapFocusQuestionApi.ts` for parallel validation and suggestions; `ConceptMapFocusReviewPicker.vue`, `conceptMapFocusReview` store, `conceptMapTopicRootEdge.ts` helper for topic–root edges on canvas.
- **User language preferences (server-backed)**: `users.ui_language` and `users.prompt_language` with migration [`utils/migration/user_language_preferences_columns.py`](utils/migration/user_language_preferences_columns.py); `PATCH` [`routers/auth/preferences.py`](routers/auth/preferences.py); request model updates; Redis user cache refresh after save. Frontend language settings and auth flows load and persist preferences.
- **Frontend i18n bundles**: [`frontend/src/i18n/`](frontend/src/i18n/) bootstrap and lazy [`frontend/src/locales/`](frontend/src/locales/) message loading; font pipeline under [`frontend/src/fonts/`](frontend/src/fonts/); maintenance scripts [`frontend/scripts/check-i18n-keys.ts`](frontend/scripts/check-i18n-keys.ts), [`frontend/scripts/split-locale-bundles.ts`](frontend/scripts/split-locale-bundles.ts).
- **Display & measurement helpers**: [`frontend/src/utils/intlDisplay.ts`](frontend/src/utils/intlDisplay.ts); diagram default labels and text-measurement fallbacks (`diagramDefaultLabels.ts`, `textMeasurementFallback.ts`) aligned with multi-script canvas text.

### Changed
- **Workshop Chat — presence display**: Last-seen plumbing [`services/features/workshop_chat/presence_last_seen.py`](services/features/workshop_chat/presence_last_seen.py); client formatting and storage [`frontend/src/utils/formatContactLastOnline.ts`](frontend/src/utils/formatContactLastOnline.ts), [`frontend/src/utils/workshopContactLastSeenStorage.ts`](frontend/src/utils/workshopContactLastSeenStorage.ts); related workshop-chat UI.
- **Agents, prompts, and API**: Concept map / mind map / flow map agents, topic extraction, Dashscope client, PNG export, LLM routers, and prompt-locale utilities updated for the above flows and language handling.
- **UI pass**: Broad i18n and layout consistency across canvas, panels, debate, knowledge space, login, and sidebar components.

## [5.49.0] - 2026-03-22

### Changed
- **Prompt output languages (expanded registry)**: Single source [`data/prompt_language_registry.json`](data/prompt_language_registry.json) (generated by [`scripts/build_prompt_language_registry.py`](scripts/build_prompt_language_registry.py)) drives [`utils/prompt_output_languages.py`](utils/prompt_output_languages.py) and the frontend via `@data` alias (`vite.config.ts`, `tsconfig.json`). Language settings prompt dropdown lists ~149 ISO/BCP-47 codes with native + English labels, Chinese search keywords, **filterable** placeholder ([`LanguageSettingsModal.vue`](frontend/src/components/settings/LanguageSettingsModal.vue)); i18n keys `settings.language.promptSelectPlaceholder` (zh/en/az).
- **i18n follow-up**: Backend `agents/core` accepts `az` with `template_lang_for_registry`; PNG export validates `zh`/`en`/`az`; activity topic labels treat non-`zh` (including `az`) like English. Frontend: concept-map focus modal and online collab modal use `t()` + `focusQuestion.*` / `collab.*` keys (incl. Azerbaijani); language settings add **match prompt to interface** checkbox; `frontend/src/i18n/messageSchema.ts` exports `MessageSchema` for typed keys documentation.
- **Node palette & generation language**: Validated `req.language` is merged into palette `educational_context` (`routers/node_palette_streaming.py`); `_detect_language` prefers that code before Chinese-topic heuristics (`agents/node_palette/base_palette_generator.py`). Thinking-mode requests validate generation codes (`models/requests/requests_thinking.py`). Client palette uses reactive `promptLanguage` from the UI store (`useNodePalette.ts`). **QA**: With prompt language **fr** / **ja** and a **Chinese** center topic, palette output should follow the selected code, not `zh`.
- **Diagram labels**: Default node `font-family` stack widened for multi-script LLM output (`frontend/src/utils/diagramNodeFontStack.ts` and diagram node components).

### Notes
- **Online canvas collaboration (diagram workshop / MindGraph)**: Still **under development** and not treated as production-complete. Further backend and client work should align with the high-concurrency collaboration review plan: [`.cursor/plans/high-concurrency_collab_review_01b89726.plan.md`](.cursor/plans/high-concurrency_collab_review_01b89726.plan.md) — including atomic Redis live-spec merge, multi-worker debounce/flush coordination, participant caps and connection safeguards, and load testing with extended metrics and observability.

## [5.48.0] - 2026-03-21

### Added
- **Workshop Phase 2 — authoritative live spec**: Redis `workshop:live_spec:{code}` merges each WS `update` (full or granular); **`snapshot`** message after **`joined`** seeds from DB when needed; debounced (**45s**) + max-interval (**60s**) flush to **`Diagram.spec`** (`workshop_live_flush.py`, `workshop_live_spec_ops.py`); flush on **stop**, when **last participant** leaves, and existing cleanup paths; new keys purged in `purge_workshop_redis_keys`. Frontend: **`snapshot`** applies via **`loadFromSpec`**, **`diagram:workshop_snapshot_applied`** suppresses autosave **5s** (`SAVE.SUPPRESS_AFTER_WORKSHOP_SNAPSHOT_MS`).
- **Workshop Chat — channel ordering & teaching groups**: `display_order` on `ChatChannel` (`models/domain/workshop_chat.py`); SQLite bootstrap adds missing column (`_ensure_chat_channels_display_order` in `config/database.py`); `channel_service` create/reorder APIs; `TeachingGroupsManageDialog.vue` for ordering teaching-group channels; sidebar and browser respect order (`ChannelSidebarItem`, `ChannelBrowser`, `WorkshopChatHistory`, store types).
- **Workshop Chat — preview org access**: Config `WORKSHOP_CHAT_PREVIEW_ORG_IDS` (`config/features_config.py`); gate in `utils/auth/roles.py` and auth dependencies; client config exposure (`routers/api/config.py`); non-admin orgs in the allowlist can use Workshop Chat for staged rollouts.
- **WebSocket production hardening**: Diagram collaboration WS (`routers/api/workshop_ws.py`) — shared JWT/cookie auth (`authenticate_websocket_user`), max text payload + per-connection rate limits (`utils/ws_limits.py`), connect/auth metrics (`ws_metrics`), Redis-backed editor persistence (`workshop_ws_editor_redis`) and optional Redis fanout hooks; chat WS (`workshop_chat_ws.py`, `workshop_chat_ws_manager.py`) aligned with limits and channel subscribe caps.
- **Diagram workshop join policy**: `workshop_service` enforces who may join a diagram session (owner, elevated roles, or same organization as diagram owner) consistent with REST workshop APIs.
- **Lifespan**: Workshop-related startup wiring updates (`services/infrastructure/lifecycle/lifespan.py`).

### Changed
- **Canvas online collaboration**: WebSocket endpoint **`GET /api/ws/canvas-collab/{code}`** replaces `/api/ws/workshop/{code}`; server broadcasts **`node_selected`**, filters granular **`update`** (nodes + **connections**) when another user holds an edit lock (`services/workshop/canvas_collab_locks.py`), and includes **`owner_id`** in **`joined`**; REST `POST /api/generate_graph` blocks non-owner **LLM** use when the diagram has an active workshop (`routers/api/diagram_generation.py`, `models/requests/requests_diagram.py`). Frontend: **`useWorkshop.ts`** (owner id unknown during collab ⇒ not owner for AI), **`CanvasTopBar`** (在线协作 entry + participant names; sync **`workshop:code-changed`**), **`CanvasPage`** (remote-merge echo guard for outbound **`sendUpdate`**; selection sync; redo invalidation; undo/redo lock guard; **`applyJoinWorkshopFromQuery`**; presentation-mode collab strip; **`provide('collabCanvas')`**), **`DiagramCanvas`**, **`InlineEditableText`**, **`CanvasToolbar`** / **`useAutoComplete`**, diagram store **`collabForeignLockedNodeIds`** + delete guards (`collabHelpers.ts`, diagram ops slices), **`MindGraphContainer`** (navigate with **`join_workshop`** query).
- **Voice**: `routers/features/voice/routes.py` — WebSocket handling aligned with shared auth and WS limits where applicable.
- **Health**: `routers/core/health.py` adjustments.
- **Workshop Chat REST**: `channels`, `topics`, `messages`, `dependencies`, `schemas` under `routers/features/workshop_chat/`; `default_channels` seed data refresh.
- **Frontend**: ESLint flat config (`eslint.config.js`), Vite (`vite.config.ts`), and dependency refresh (`package.json` / lockfile); broad UX and layout polish across `WorkshopChatPage.vue`, workshop-chat components, canvas/diagram/admin/school/teacher flows, `useLanguage`, `workshopChat` store, and diagram `specLoader` / operations.

## [5.47.0] - 2026-03-20

### Added
- **Concept map focus question**: Multi-model validation and SSE suggestion streams (`routers/concept_map_focus.py`); `ConceptMapFocusQuestionModal.vue` on canvas; diagram request types and `prompts/concept_maps.py` updates.
- **Workshop Chat search & efficiency**: Full-text message search with normalized query text (`message_search_normalize`, `message_fts`); `@` mention resolution (`mention_resolution`); conditional list responses with `ETag` (`conditional_list_response`, `workshop_list_etag`); PostgreSQL FTS index migration (`workshop_fts_indexes`).
- **Workshop Chat UX**: `WorkshopInboxWelcome.vue`; `workshopChatRoute.ts`, `workshopChatLocalCache.ts`, `workshopAvatar.ts`, `lessonStudyDeadline.ts` helpers.
- **Voice API layout**: `routers/features/voice.py` replaced by a `routers/features/voice/` package; `scripts/generate_voice_package.py`.
- **Tests**: `tests/services/test_mention_resolution.py`, `tests/services/test_workshop_list_etag.py`.

### Changed
- **Workshop Chat**: Store, WebSocket, and UI updates across sidebar, compose, messages, channel settings, notifications, and DMs (`useWorkshopChat`, `useChatNotifications`, `useLanguage`, related Vue components and CSS).
- **Canvas**: Toolbar, top bar, and `CanvasPage.vue` wiring for concept map focus flow; diagram store/spec I/O updates for new diagram fields.
- **Admin & API**: Library admin tab and router tweaks; `clients/omni_client.py`; `vite.config.ts` dev settings; HTTP middleware updates.

### Removed
- **Monolithic voice router**: `routers/features/voice.py` (superseded by `routers/features/voice/` package).

## [5.46.0] - 2026-03-20

### Added
- **Workshop Chat (教研坊)**: Complete school-scoped real-time communication system for teacher collaboration, gated by `FEATURE_WORKSHOP_CHAT` feature flag.
  - **Channels**: Create, browse, join, and manage topic-based channels with settings (name, description, member management).
  - **Topics**: Threaded topic cards within channels; create, edit, star, and delete topics.
  - **Messages**: Rich message composition with Markdown rendering, file/image attachments, emoji reactions, edit/delete, and inline image lightbox.
  - **Direct Messages**: One-to-one DM support with conversation history.
  - **WebSocket**: Real-time message delivery via WebSocket manager (`workshop_chat_ws_manager.py`); dedicated WS router (`workshop_chat_ws.py`).
  - **Presence & Activity**: `usePresenceActivity` composable tracks user online/away status in real time.
  - **Chat Notifications**: `useChatNotifications` composable and `chatToastQueue` deliver in-app toast notifications (`ChatMessageToast.vue`) for new messages while browsing other pages.
  - **Seed Data**: Default channel definitions (`default_channels.py`) and rich seed data sets (`seed_channel_data.py`, `seed_data_stem_math.py`) for onboarding.
  - **Backend services**: `channel_service`, `topic_service`, `message_service`, `dm_service`, `reaction_service`, `file_service`, `star_service` under `services/features/workshop_chat/`.
  - **REST API routers**: `channels`, `topics`, `messages`, `direct_messages`, `reactions`, `files` under `routers/features/workshop_chat/`.
  - **Domain model**: `models/domain/workshop_chat.py` with SQLAlchemy models for channels, topics, messages, reactions, files, stars, and DMs.
  - **Database migrations**: SQLite migration tables and PostgreSQL data migration extended for all workshop chat entities.
- **Workshop Chat Frontend**: Full Vue 3 frontend with 20+ components and dedicated page.
  - **WorkshopChatPage.vue** and `workshop-chat-page.css`: Main chat layout page with sidebar + content panels.
  - **Components**: `ChannelBrowser`, `ChannelMemberList`, `ChannelSettingsDialog`, `ChannelActionsPopover`, `ChannelSidebarItem`, `WorkshopChatHistory`, `TopicCard`, `TopicEditDialog`, `TopicActionsPopover`, `ChatMessageList`, `ChatMessageItem`, `ChatComposeBox`, `MessageActionBar`, `MessageReactions`, `RecipientBar`, `EmojiPicker`, `FilePreview`, `ImageLightbox`, `UserCardPopover`, `WorkshopGearMenu`, `WorkshopPersonalMenu`.
  - **workshopChat store** (`stores/workshopChat.ts`): Pinia store managing channels, topics, messages, DMs, and WebSocket connection lifecycle.
  - **useWorkshopChat composable**: High-level composable wiring store actions to UI interactions.
  - **useMarkdown composable**: Markdown-to-HTML rendering with syntax highlighting for chat messages.
- **Admin page refactoring**: `AdminPage.vue` split into `AdminLibraryTab.vue` and `AdminTokensTab.vue` for clearer separation of concerns.
- **Library admin router** (`routers/features/library/admin.py`): Dedicated admin endpoints for library document management.
- **useLanguage composable** (`composables/useLanguage.ts`): Centralised language detection and switching logic extracted from inline code.
- **AppSidebar**: Workshop Chat navigation entry (`ChannelSidebarItem`) and `WorkshopChatHistory` panel integrated into sidebar.
- **PostgreSQL support**: `config/database.py` extended; SQLite-to-PostgreSQL data migration updated to include workshop chat tables.

### Changed
- **Feature flags**: `FEATURE_WORKSHOP_CHAT` flag added to `features_config.py`, `featureFlags` store, and `useFeatureFlags` composable.
- **Router**: Workshop Chat page route registered; library admin routes added.
- **Lifespan**: Workshop chat WebSocket manager initialised during app startup.

## [5.45.0] - 2026-03-18

### Changed
- **Diagram store modularization**: Diagram store split from single file into `stores/diagram/` module: `index`, `types`, `constants`, `events`, `history`, `selection`, `customPositions`, `nodeStyles`, `copyPaste`, `titleManagement`, `learningSheet`, `mindMapOps`, `bubbleMapOps`, `braceMapOps`, `doubleBubbleMapOps`, `flowMapOps`, `treeMapOps`, `multiFlowLayout`, `connectionManagement`, `nodeManagement`, `vueFlowIntegration`, `specIO`, `nodeSwapOps`. Main `diagram.ts` composes slices from the new module.
- **ContextMenu.vue**: Minor cleanup.
- **specLoader/treeMap.ts**: Updates for diagram module imports.

## [5.44.0] - 2026-03-18

### Added
- **Concept Map Handle Splitting**: When connections sharing the same handle have mixed arrow states (some with arrows, some without), they are automatically split into separate offset handles to prevent visual overlap and confusion.
- **Smart Bidirectional Offset**: Split handles use spatially-aware offset direction — the group whose connected nodes are above/left gets the upper/left offset, the other gets the lower/right offset, so curves lean toward their endpoints and don't cross.
- **Secondary/Tertiary Handles**: ConceptNode now has three handle positions per side (center, -2 at `50%-8px`, -3 at `50%+8px`) for split connection routing.
- **Source Arrow Sharing**: `drawSourceArrowhead` flag added to edge data; when multiple edges share a source handle and all have source arrows, only one draws the arrowhead (mirrors existing target arrow sharing).
- **arrowheadLocked**: Connection flag that preserves manually toggled arrowhead directions during node moves. `updateConnectionArrowheadsForNode` skips locked connections.

### Changed
- **toggleConnectionArrowhead**: Now sets `arrowheadLocked: true` on the connection so manual arrow changes persist when nodes are dragged.
- **updateConnectionArrowheadsForNode**: Skips connections with `arrowheadLocked` flag, preventing auto-recalculation from overwriting user choices.
- **CurvedEdge**: `showSourceArrow` now respects `drawSourceArrowhead` flag for shared source handle arrowhead deduplication.
- **vueFlowEdges computed**: Runs `splitMixedArrowHandleGroups` before arrowhead sharing logic; adds source-side grouping and `drawSourceArrowhead` assignment parallel to existing target-side logic.

## [5.43.0] - 2026-03-18

### Added
- **Branch Move (Drag-and-Drop)**: Long-press (1.5s) any node to enter drag mode across all thinking map types. Circle follows cursor with drop preview overlay. Mind map and tree map use hierarchical move (reparent as child, sibling, or top-level); all other types use position swap. Bridge map and double bubble map diff nodes move as pairs.
- **useBranchMoveDrag**: New composable for long-press drag-and-drop with shrink animation, cursor tracking, drop target detection, and diagram-type-aware move/swap logic.
- **Mind Map moveMindMapBranch**: Reparent branches to topic (left/right based on cursor), as child of another branch, or swap as sibling. Rebuilds spec and reloads layout.
- **Tree Map moveTreeMapBranch**: Move categories and leaves between groups or reorder within the same group. Spec-based rebuild.
- **Generic moveNodeBySwap**: Position swap for bubble map, circle map, double bubble map, flow map, multi-flow map, brace map, and bridge map nodes. Diagram-type-specific swap functions (swapBraceMapNodes, swapBridgeMapPairs, swapDoubleBubbleMapNodes, swapFlowMapNodes, swapMultiFlowMapNodes).
- **Brace Map moveBraceMapNode**: Reparent (subpart→part) or swap based on depth comparison.
- **Flow Map moveFlowMapNode**: Reparent substep to another step group or swap steps/substeps.
- **MindMapCurveExtents**: Curve extent tracking (left/right) with baseline capture for drift monitoring after branch operations.
- **MINDMAP_TARGET_EXTENT**: Layout constant (450px) for minimum horizontal curve extent; scales both sides up when layout produces smaller extent after branch moves.
- **estimateNodeWidth**: Text-adaptive node width estimation for mind map branches (CJK ~16px, Latin ~9px at 16px font, capped at 150px text width + 38px padding).
- **normalizeBranchToChildSpans**: Equalizes branch-to-child curve spans so left and right sides match after layout.
- **diagram:branch_moved event**: New event bus event to trigger fit-to-canvas after programmatic node replacement.
- **diagram:operation_completed event**: Auto-save integration for branch move operations.

### Changed
- **Nodes non-draggable in layout-controlled diagrams**: Mind map, tree map, brace map, flow map, multi-flow map, bubble map, circle map, double bubble map, and bridge map nodes are now non-draggable (only concept map retains free-form drag). Long-press drag replaces direct dragging.
- **Mind Map horizontal symmetry**: normalizeMindMapHorizontalSymmetry now expands the shorter side to match the longer (instead of shrinking), and scales both sides up when below MINDMAP_TARGET_EXTENT. Uses per-node estimatedWidth for accurate center calculations.
- **Mind Map layout**: Dagre nodes use estimateNodeWidth for text-adaptive widths; estimatedWidth stored in node data for accurate left-side mirroring.
- **BranchNode, CircleNode, FlowNode, FlowSubstepNode, BraceNode**: All inject branchMove composable and wire mousedown/mouseup handlers for long-press drag-and-drop.
- **DiagramCanvas**: Integrates useBranchMoveDrag; filters hidden nodes/edges during drag; renders branch-move-circle and drop-preview overlays in zoom-pane; disables nodes-draggable for mindmap/tree_map.
- **LLM Model Switching**: contentChangeIsFromModelSwitch flag prevents auto-save from overwriting user edits when switching models. updateCurrentModelSpec syncs user edits to LLM results cache so model switching loads edited spec.
- **saveCurrentDiagramBeforeReplace**: Now persists LLM results alongside spec before model switch.
- **savedDiagrams**: updateCurrentModelSpec called on save/update/delete-and-replace to keep LLM cache in sync.
- **Bridge Map dimension label**: Always create dimension-label node (even when empty); LabelNode shows placeholder text.
- **BraceOverlay**: Single-child brace renders as straight horizontal line instead of curly brace.
- **Inline Recommendations cleanup**: Skip cleanup API call when user is not authenticated (avoids 401 errors).
- **useDiagramAutoSave**: Triggers save on diagram:operation_completed (move_branch); skips save when content change is from model switch.
- **CanvasPage**: Increments sessionEditCount on move_branch operation.
- **Code quality**: Removed non-null assertions throughout diagram store; formatting cleanup; debug logging for curve diagnostics in CurvedEdge, mindMap spec loader, and mind_map_agent.py.

### Removed
- Verbose node-click debug logging in DiagramCanvas (getTimestamp helper and detailed click logs).
- Obsolete plan files from .cursor/plans/.

## [5.42.0] - 2026-03-17

### Added
- **Inline Recommendations (Diagram Auto-Completion)**: Extends concept map's auto label generation pattern to mindmap, flow_map, tree_map, brace_map, circle_map, bubble_map, double_bubble_map, multi_flow_map, bridge_map. When user fixes the topic, a green badge indicates readiness; double-clicking step/substep or branch nodes triggers context-aware AI recommendations in an inline picker.
- **Inline Recommendations Backend**: New `agents/inline_recommendations/` (context extractors, diagram-specific prompts, generator, cleanup scheduler). Catapult-style 3-LLM concurrent streaming.
- **Inline Recommendations Router**: New `routers/inline_recommendations.py` with `POST /thinking_mode/inline_recommendations/start`, `next_batch`, `cleanup` endpoints.
- **InlineRecommendationsPicker**: New bottom bar picker component—keys 1–5 select, `-`/`=` for prev/next page.
- **useInlineRecommendations**: New composable for streaming recommendations, selection, pagination.
- **useInlineRecommendationsCoordinator**: Central event handler for topic updates, diagram changes, pane click, dismiss.
- **inlineRecommendations Store**: New Pinia store for options, activeNodeId, isReady, generatingNodeIds, fetchingNextBatchNodeIds.
- **INLINE_RECOMMENDATIONS_SUPPORTED_TYPES**: Shared constant in `nodePalette/constants.ts`.

### Changed
- **CanvasToolbar**: Green badge when `isReady` for supported diagram types.
- **DiagramCanvas, FlowNode, InlineEditableText**: Double-click integration for inline recommendations.
- **CanvasPage**: Coordinator setup for inline recommendations events.
- **useEventBus**: Added `node_editor:tab_pressed` event type.
- **useDiagramAutoSave, useConceptMapRelationship, useAutoComplete**: Integration updates.
- **conceptMapRelationship Store, diagram Store**: Minor updates.
- **requests_thinking**: InlineRecommendationsStartRequest, InlineRecommendationsNextRequest, InlineRecommendationsCleanupRequest.
- **Lifespan**: Start inline recommendations cleanup scheduler (30 min interval, 30 min TTL).
- **Routers Register**: Registered inline_recommendations router.

## [5.41.0] - 2026-03-17

### Added
- **Community Feature**: Global community sharing for MindGraph diagrams. Users can share diagrams to a public BBS-like community with thumbnails, likes, and comments.
- **Community Models**: New `CommunityPost`, `CommunityPostComment`, `CommunityPostLike` models in `models/domain/community.py`.
- **Community Router**: New `routers/features/community.py` with endpoints for listing, creating, updating, deleting posts; like/unlike; comments; spec JSON and thumbnail serving.
- **Community Helpers**: New `community_helpers.py` for thumbnail/spec file handling, validation, and post CRUD utilities.
- **Redis Community Cache**: New `redis_community_cache.py` for post invalidation on updates/deletes.
- **CommunityPage**: New community page with filters (type, category, sort), infinite scroll, search, "Me" tab for own posts, like/comment/edit/delete.
- **ExportToCommunityModal**: New modal in CanvasTopBar for sharing diagrams to community—create (title, description, category, auto thumbnail) or edit existing posts.
- **CommunityPostDetailModal**: New modal for viewing post details, spec import, and engagement (like, comment).
- **useDiagramImport**: New composable for importing community post specs into the canvas.
- **Migration Table Order & Verification**: New `migration_table_order.py` and `migration_verification.py` for SQLite migration sequencing and validation.

### Changed
- **CanvasTopBar**: Added Export to Community button and ExportToCommunityModal integration.
- **CommunityPage Route**: Added `/community` route and sidebar navigation.
- **API Client**: Added community endpoints (`getCommunityPosts`, `createCommunityPost`, `updateCommunityPost`, `deleteCommunityPost`, `toggleCommunityPostLike`, `getCommunityPost`, etc.).
- **Database Config**: Registered Community models for migrations.
- **SPA Handler**: Added static paths for community thumbnails and spec JSON.
- **Routers Register**: Registered community feature router.
- **Diagram/Canvas Components**: Integration updates for community export flow.
- **Migration Scripts**: Updates to `dump_import_postgres.py`, `migrate_sqlite_to_postgresql.py`, `migration_tables.py`, `data_migration.py`, `table_creation.py` for community tables and migration flow.

## [5.40.1] - 2026-03-16

### Added
- **Redis User Cache Role**: User cache now stores and restores `role` field for role-aware lookups.

### Changed
- **Stats Trends Router**: Removed redundant comments and unused `_current_user` dependency from `get_user_token_trends_admin`.
- **Users Router**: Removed redundant comments from `list_users_admin`.
- **Redis User Cache**: Safer `organization_id` parsing when deserializing from cache.

## [5.40.0] - 2026-03-16

### Added
- **Flow Map Add/Delete**: Add step or substep via CanvasToolbar (Add Node, Add Branch, Add Child). Add Node: select step → add substep; no selection → add step with 2 default substeps. Add Branch adds step; Add Child adds substep to selected step. Delete step cascades to substeps; spec rebuilt on add/delete.
- **Flow Map Orientation Persistence**: Vertical/horizontal orientation persisted in spec and restored on save/load.
- **measureTextDimensions**: New text measurement utility for multi-line width/height (used by flow map substeps and tree map leaves).
- **Tree Map groupIndex & nodeType**: Preserved in vueflow sync for branch/leaf distinction and mindmapColors.

### Changed
- **Flow Map Layout**: Unified pill dimensions (FLOW_MAP_PILL_WIDTH/HEIGHT); text-adaptive topic and substep widths; vertical layout: steps on left, substeps on right with curved (mindmap-style) branches; step-to-substep edges use curved instead of horizontalStep; mindmapColors for step/group edges.
- **FlowSubstepNode**: Pill shape for flow maps; mindmapColors by groupIndex; center handles for step-to-substep; additional top/bottom handles for layout flexibility.
- **Flow Map Nodes**: Non-draggable (layout controlled by spec).
- **Tree Map Layout**: measureTextDimensions for adaptive category/leaf widths and heights; TREE_MAP_LEAF_SPACING 24→10, TREE_MAP_CATEGORY_TO_LEAF_GAP 32→24; TREE_MAP_CATEGORY_SPACING 60; mindmapColors for edges; per-leaf width/height for multi-line text.
- **layoutConfig**: FLOW_MAP_PILL_WIDTH/HEIGHT, FLOW_SUBSTEP_SPACING 10→12.
- **Diagram Store**: addFlowMapStep accepts defaultSubsteps; addFlowMapSubstep; removeNode for flow_map with spec rebuild; orientation in flow map spec.
- **CanvasToolbar**: Flow map handlers for handleAddNode, handleAddBranch, handleAddChild.
- **Diagram Nodes**: BranchNode, FlowNode, TopicNode—updates for flow/tree map integration.
- **useTreeMap, flowMap, textMeasurement**: Layout and measurement refinements.
- **AdminSchoolsTab, applySelection, useLanguage, uiConfig, llmResults**: Minor updates.

## [5.39.3] - 2026-03-16

### Added
- **Delete Organization with Users**: Admin can delete an organization and all its user accounts via `delete_users=true`; cascades to diagrams, activity logs, usage stats, and token usage.
- **List All Managers API**: New `GET /admin/managers` endpoint for role control panel—returns managers with organization info.
- **Admin Translations**: New i18n keys for school code, invitation code, lock/unlock org, delete org confirmations, danger zone, expiration date, and school managers tab.

### Changed
- **AdminRolesTab**: Refactored with school managers sub-tab, role control UI improvements.
- **AdminSchoolsTab**: School code, invitation code, lock/unlock, expiration date, and delete org with users support.
- **AdminTrendChartModal**: Layout and integration updates.
- **APIKey Model**: Migrated to SQLAlchemy 2.0 style (Mapped[], mapped_column).
- **Organizations Router**: Type-safe cast() for org cache comparisons; delete org now supports optional user cascade.
- **Users Router**: Type-safe cast() for org_cache.invalidate and organizations_by_id.

## [5.39.2] - 2026-03-16

### Added
- **useDiagramAutoSave**: New composable for event-driven diagram auto-save—config-driven timing, event-based coordination (diagram:loaded_from_library, llm:generation_completed), and state-driven guards.
- **useDiagramSpecForSave**: New composable to get diagram spec for save with optional LLM results persistence (when 2+ results, under size limit).
- **saveConfig**: Centralized save constants (debounce, suppression-after-load window, max spec size) in `config/saveConfig.ts`.

### Changed
- **Auto-save flow**: Refactored from inline logic into useDiagramAutoSave composable for cleaner separation and maintainability.

## [5.39.1] - 2026-03-16

### Fixed
- **Auto-complete diagram history bug**: Fixed issue where 3 diagrams were saved in diagram history for a single auto-complete. Now uses event + state-driven flow: user edits save immediately (debounced); LLM generation skips auto-save; single save on `llm:generation_completed`.

## [5.39.0] - 2026-03-16

### Added
- **Brace Map Helper Modules**: New `brace_map_helpers.py`, `brace_map_models.py`, `brace_map_positioning.py`—extracted from brace_map_agent for reduced complexity and improved maintainability.
- **Tree Map Helper Module**: New `tree_map_helpers.py`—extracted from tree_map_agent for cleaner separation of concerns.

### Changed
- **Thinking Map Agents**: Major refactor across brace_map, bridge_map, bubble_map, circle_map, double_bubble_map, flow_map, multi_flow_map, tree_map agents—reduced duplication, improved PEP8 compliance, and modular structure.
- **Admin Components**: AdminSchoolsTab, AdminTrendChartModal—layout and integration updates.
- **Canvas Components**: AIModelSelector, CanvasToolbar—minor updates.
- **AppSidebar**: Navigation and layout updates.
- **Composables**: useAutoComplete, useLanguage—enhancements.
- **Auth Store & Types**: auth.ts, auth types, auth domain model—updates.
- **llmResults Store**: State handling improvements.
- **Prompts**: concept_maps.py, thinking_maps.py—refinements.
- **Config**: features_config, rate_limiting—cleanup and simplification.
- **Routers**: diagram_generation, organizations, session—updates.
- **Redis Org Cache**: Improved caching logic.
- **env.example, pyproject.toml, tsconfig.json**: Config cleanup.

## [5.38.0] - 2026-03-16

### Changed
- **Double Bubble Map Curved Edges**: Switched double bubble map from radial (straight) to curved (bezier) edges for smoother connections between topic and similarity/difference nodes.
- **CircleNode Handles**: Added left/right/top/bottom handles for double bubble map nodes so curved edges connect at node boundaries; handles are invisible (connection points only).
- **Double Bubble Spec Loader**: Connection specs now include `edgeType: 'curved'`, `sourcePosition`, `targetPosition`, `sourceHandle`, `targetHandle` for proper curved edge routing.
- **ConceptMapLabelPicker**: Skip key handling when target is contentEditable; added `stopPropagation` for `-`, `=`, and 1–5 keys; use capture-phase keydown listener to prevent shortcut conflicts.
- **CurvedEdge Label Display**: Reordered label logic—show existing label first when trimmed, then "AI..." when generating, then placeholder for concept maps.

## [5.37.0] - 2026-03-15

### Added
- **Admin Page Tabs**: Refactored Admin page into tabbed layout—AdminDashboardTab, AdminRolesTab, AdminSchoolsTab, AdminUsersTab, AdminTrendChartModal for better organization.
- **School Dashboard Page**: New SchoolDashboardPage.vue with route `/school-dashboard` and sidebar integration.
- **Admin Roles Router**: New `routers/auth/admin/roles.py` for role management endpoints.
- **Activity API**: New `routers/api/activity.py` for activity tracking.
- **Node Palette Streaming**: New `routers/node_palette_streaming.py` for streaming node palette generation.
- **Backfill Teacher Activity Logs**: New `scripts/db/backfill_teacher_activity_logs.py` for one-time backfill of teacher activity data.

### Changed
- **Admin Backend**: Enhanced stats, stats_trends, teacher_usage, and organizations routers with additional functionality.
- **TeacherUsagePage**: Major refactor with improved layout and integration.
- **useLanguage Composable**: Extended with additional language utilities and translations.
- **AppSidebar**: Added school-dashboard navigation item.
- **Feature Flags**: Updates to features_config, useFeatureFlags, and featureFlags store.
- **Diagram Export, EventBus, Diagram Store, SavedDiagrams**: Integration and state handling updates.
- **Node Palette Router**: Refactored with streaming support; simplified implementation.
- **CanvasPage, Config, Models, Auth Utils**: Minor updates and improvements.

## [5.36.0] - 2026-03-14

### Changed
- **ConceptMapLabelPicker**: Always prevent default for `-` and `=` keys so they don't trigger other shortcuts when label picker is active; only invoke prev/next when applicable.
- **CanvasPage**: Skip add-node, add-branch, add-child shortcuts for concept maps (use different flow). Skip clear-node-text when relationship label picker is active.

## [5.35.0] - 2026-03-14

### Changed
- **Canvas Reset Button**: Added label text (重置/Reset); now fully resets canvas—LLM results store, all panels (Mindmate, Property, Node Palette), and closes modals (slot full, workshop).
- **Canvas Top Bar**: Even spacing between 教学设计, Reset, and Export buttons (grouped with consistent gap).

## [5.34.0] - 2026-03-14

### Added
- **ConceptMapLabelPicker**: Bottom bar label picker for concept map relationship options. When user drags concepts to create a link, AI generates 3–5 labels; user presses 1–5 to select; clicking canvas clears.
- **conceptMapRelationship Store**: New Pinia store for transient state of AI-generated relationship label options (connectionId → labels), kept separate from diagram store for concept-map-specific UI.

### Changed
- **Concept Map Agent**: Updates for label generation and direction-aware handling.
- **useConceptMapRelationship**: Integration with ConceptMapLabelPicker and relationship store.
- **CurvedEdge**: Enhanced label display and picker integration.
- **Diagram Nodes**: BraceNode, BranchNode, BubbleNode, CircleNode, ConceptNode, FlowNode, FlowSubstepNode, InlineEditableText, LabelNode, TopicNode—cleanup and consistency.
- **CanvasToolbar, AIModelSelector, DiagramCanvas, CanvasPage**: UI and integration updates.
- **prompts/concept_maps.py**: Refined relationship generation prompts.
- **Config, models, routers**: Tab mode removal and feature flag updates.
- **useEventBus, useLanguage, diagram store**: Concept map event handling and store updates.

### Removed
- **Tab Mode Feature**: Removed agents/tab_mode (tab_agent), prompts/tab_mode (autocomplete, colors, expansion), routers/features/tab_mode. Feature no longer in use.
- **IME Autocomplete**: Removed IMEAutocompleteDropdown.vue and useIMEAutocomplete.ts.

## [5.33.0] - 2026-03-13

### Added
- **Concept Map Arrowhead-Aware Relationship Labels**: When generating relationship labels via AI, the API now considers link direction (`arrowheadDirection`). Direction-specific prompts for source_to_target, target_to_source, both, and none—with STEM and literature examples.
- **Concept Map Node Palette Sub-Concept Generation**: Node palette for concept maps supports generating sub-concepts from a selected node. Selecting a concept node opens a tab; AI generates concepts related to that node instead of the main topic.
- **Concept Map Node Palette Tabs**: `conceptMapTabs` in panels store—tabs for main topic and per-node sub-concept tabs. Each tab displays suggestions filtered by its center topic.
- **Canvas Reset Button**: CanvasTopBar reset button to clear diagram, node palette, and saved state. Loads default template with confirmation modal.
- **link_direction in GenerateRequest**: New `link_direction` field for concept map relationship API (source_to_target, target_to_source, both, none).

### Changed
- **Concept Map Agent**: `_generate_relationship_only` now accepts `link_direction`; added `_get_direction_instruction()` for direction-aware relationship labels.
- **ConceptMapPaletteGenerator**: `generate_batch` override adds `parent_id` to nodes for sub-concept tab routing.
- **useNodePalette**: Concept map support—`conceptMapCenterTopic`, `switchConceptMapTab`, concept_map-specific filtering and payload for sub-concept generation.
- **NodePalettePanel**: Concept map tabs UI; click node to open palette with that node as center.
- **Panels Store**: `openNodePalette` accepts `conceptMapNodeId`/`conceptMapNodeText`; `conceptMapTabs` persisted in session.
- **DiagramCanvas, ConceptNode**: Concept map node palette integration.
- **Routers node_palette, diagram_generation**: Concept map sub-concept and link_direction support.
- **prompts/concept_maps.py**: Updated for direction-aware relationship generation.
- **useConceptMapRelationship, conceptMapHandles, useEventBus**: Pass link_direction and concept map events.
- **Diagram Store, types/panels**: Concept map node palette and ConceptMapTab type updates.

## [5.32.0] - 2026-03-08

### Added
- **nodePalette Composable Modules**: New `composables/nodePalette/` with `applySelection.ts`, `constants.ts`, `diagramDataBuilder.ts`, `placeholderHelpers.ts`, `stageHelpers.ts`—extracted from useNodePalette for better maintainability and separation of concerns.

### Changed
- **useNodePalette**: Major refactor—logic split into nodePalette submodules. Reduced main composable size; stage helpers, diagram data building, and selection application now in dedicated modules.
- **Node Palette Agents**: Enhanced palette generators (base, brace_map, bridge_map, double_bubble, flow_map, mindmap, multi_flow, tree_map) with improved prompts and PEP8 compliance.
- **NodePalettePanel**: Refactored with useNodePalette integration and panel coordination updates.
- **Panel Coordination**: usePanelCoordination, panels store, types/panels—improved node palette coordination and state handling.
- **Diagram Store**: Added node palette assembly methods and state handling.
- **CanvasPage, DiagramCanvas, CanvasToolbar**: Node palette integration and layout updates.
- **DiagramTemplateInput, ContextMenu**: Minor updates for node palette flow.
- **useAutoComplete, useEventBus**: Placeholder detection and event handling for node palette.
- **prompts/node_palette.py, routers/node_palette.py**: Simplified and improved PEP8 compliance.
- **utils/placeholder.py, models/requests/requests_thinking.py**: Placeholder detection and request handling updates.
- **multiFlowMap spec loader, savedDiagrams store**: Spec loading and persistence updates.

## [5.31.0] - 2026-03-07

### Added
- **Node Palette Prompts**: New `prompts/node_palette.py` with centralized prompt templates for node palette incremental generation. Content requirements aligned with thinking_maps.py for consistent generation across auto-complete and node palette flows.
- **useNodePalette Composable**: New composable for Node Palette (瀑布流) AI-suggested nodes—SSE streaming, session management, multi-select and assembly to diagram. Migrated from archive node-palette-manager.js.
- **llmModelColors Config**: New `llmModelColors.ts` with shared color palette for Qwen, DeepSeek, Doubao. Used by AIModelSelector and NodePalettePanel for consistent visual identity.
- **utils/placeholder**: New `utils/placeholder.py` for placeholder text detection in Node Palette and diagram generation. Aligned with frontend useAutoComplete.ts patterns.

### Changed
- **Node Palette Agents**: Refactored all palette generators (base, brace_map, bridge_map, bubble_map, circle_map, double_bubble, flow_map, mindmap, multi_flow, tree_map) to use centralized prompts from prompts/node_palette.py. Reduced duplication and improved maintainability.
- **NodePalettePanel**: Major refactor with useNodePalette integration, LLM model colors, and improved layout.
- **Diagram Store**: Added node palette assembly methods and state handling.
- **Canvas Bottom Controls**: Removed background from AI selector and zoom/pan controls. AIModelSelector glass-container and ZoomControls wrapper now use transparent backgrounds for a cleaner overlay on the canvas.
- **Routers node_palette**: Simplified to use prompts module; improved PEP8 compliance.
- **uiConfig, usePanelCoordination, panels store, types/panels**: Minor updates for node palette coordination.
- **CanvasPage, DiagramCanvas, LabelNode, ImageViewer, CanvasToolbar, CanvasTopBar, vite.config**: Updates and improvements.

## [5.30.0] - 2026-03-06

### Added
- **TreeMapOverlay**: New overlay component for tree maps displaying alternative dimensions at bottom (like BridgeOverlay/BraceOverlay). Shows "本主题的其他可能分类维度" / "Other possible dimensions for this topic" with dimension chips.
- **Border Style System**: New `borderStyleUtils.ts` with `getBorderStyleProps()` and `resolveBorderStyle()` for diagram nodes. Supports solid, dashed, dotted, double, dash-dot, dash-dot-dot. Uses background-clip for dash-dot patterns so they respect border-radius (pill shapes).
- **CanvasToolbar Border Style**: Border style dropdown in CanvasToolbar—apply solid, dashed, dotted, double, dash-dot, dash-dot-dot to selected nodes.
- **NodeStyle borderStyle**: Added `borderStyle` to NodeStyle type and diagram store for persistence.

### Changed
- **Diagram Nodes**: BraceNode, BranchNode, BubbleNode, CircleNode, ConceptNode, FlowNode, FlowSubstepNode, LabelNode, TopicNode now use `getBorderStyleProps()` for consistent border styling.
- **Brace Map Spec Loader**: Enhanced with alternative_dimensions support; refactored layout and metadata handling.
- **Tree Map Spec Loader**: Refactored useTreeMap and treeMap.ts; added alternative_dimensions to metadata.
- **BridgeOverlay**: Refactored and simplified.
- **Diagram Store**: Added border style handling in `applyBorderToSelected`, style preset application, and sync.
- **DiagramHistory, useAutoComplete, useLanguage, useTheme**: Updates and improvements.
- **RadialEdge**: Enhanced edge rendering.
- **layoutConfig**: Added layout constants.

## [5.29.1] - 2026-03-05

### Added
- **Double Bubble Map Add/Delete**: Add and delete nodes for double bubble maps. Add node: select a similarity or difference node first, then add (similarity adds one node; difference adds a pair). Delete: select similarity/difference nodes (topic nodes protected). Context menu "在此组添加节点" / "Add to this group" on right-click; CanvasToolbar add/delete with validation.
- **Diagram Store Double Bubble**: `addDoubleBubbleMapNode()` and `removeDoubleBubbleMapNodes()` for programmatic add/delete with spec rebuild.

### Changed
- **Canvas Bottom Controls Layout**: AI model selector and zoom controls in adaptive flex layout—AI selector centered, zoom on right; responsive for mobile/desktop.
- **AIModelSelector, ZoomControls**: Removed absolute positioning; now positioned by parent `canvas-bottom-controls` container.
- **CanvasTopBar**: Export button label "导出" → "图示导出".
- **Mindmate Panel Mode**: Input area pinned to bottom in panel mode via `mindmate-input-section` wrapper and `panel-mode` CSS.
- **Circle Map Theme**: Topic stroke color changed from dark blue (#0d47a1) to black (#000000) for better contrast.

## [5.29.0] - 2026-03-05

### Added
- **半成品图示 (Learning Sheet)**: Full implementation of learning sheet mode. CanvasToolbar "半成品图示" button toggles mode on existing diagrams. Randomly knocks out child nodes (placeholder `___`), displays answer chips below diagram via LearningSheetOverlay. Press `-` on a node to empty it and add to answer key. State preserved on save/load.
- **LearningSheetOverlay**: New component rendering dashed separator line and answer chips below diagram (bridge-map style).
- **Spec Loader Learning Sheet**: `applyLearningSheetHiddenNodes()` in specLoader/utils.ts—seeded shuffle for deterministic hidden set, hideable node filtering, metadata `hiddenAnswers` and `isLearningSheet`.
- **Diagram Store Learning Sheet**: `emptyNodeForLearningSheet()`, `setLearningSheetMode()`, `restoreFromLearningSheetMode()`, `applyLearningSheetView()`, `hasPreservedLearningSheet()` for mode toggle and answer tracking.

### Changed
- **Circle Map, Bubble Map, Double Bubble Map**: Huangyi fixes—(1) multi-line theme nodes with wrap support, (2) refit after text edit so diagram stays fully visible, (3) fixed canvas center (no bottom-right shift after edit), (4) text-adaptive topic radius via `getTopicCircleDiameter()` and `computeTopicRadiusForCircleMap`, (5) long English text stays within bubble (dynamic textMaxWidth), (6) `noWrap` for mixed-character nodes to prevent unwanted wrapping, (7) double bubble text-adaptive radii and reload-on-edit for consistent sizes.
- **CircleNode**: Extended to bubble_map and double_bubble_map; capsule nodes for double-bubble similarity/diff; `noWrap`, `centerBlockInCircle`, `textMaxWidth` from circle size.
- **InlineEditableText**: New props `noWrap`, `fullWidth`, `centerBlockInCircle`; `disabled` for learning sheet knocked-out nodes.
- **bubbleMap.ts / doubleBubbleMap.ts**: Fixed center (DEFAULT_CENTER_X/Y), text-adaptive topic radius, double bubble capsule layout.
- **textMeasurement.ts**: `computeTopicRadiusForCircleMap` now includes BORDER_TOPIC in radius; exported `measureTextWidth` for overlays.
- **DiagramCanvas**: Refit on `node:text_updated` for circle_map, bubble_map, double_bubble_map; integrated LearningSheetOverlay.
- **CanvasToolbar**: 半成品图示 handler—append " 半成品" for new generation, or toggle mode on existing diagram.
- **Mindmate Panel, useAutoComplete, savedDiagrams, llmResults**: Learning sheet state preservation in save/load and auto-complete flows.

## [5.28.4] - 2026-03-02

### Added
- **Mind Map Branch Colors**: New `mindmapColors.ts` config with 20-color palette for branch nodes (fill + border pairs). Each branch gets a distinct color for visual hierarchy.
- **Mind Map Add Branch/Child**: Context menu and CanvasToolbar support for adding first-level branches and child nodes. Add branch uses smart clockwise distribution (right/left). Add child inserts under selected branch.
- **Mind Map Spec Helpers**: `loadMindMapSpec`, `nodesAndConnectionsToMindMapSpec`, `distributeBranchesClockwise`, `findBranchByNodeId`, `normalizeMindMapHorizontalSymmetry` in mindMap store for programmatic branch/child management.

### Changed
- **Mind Map Edges**: Switched from straight to curved (bezier) edges, matching concept map style.
- **Mind Map Nodes**: Nodes are non-draggable; layout controlled by spec.
- **Mind Map Agent**: Canonical node field is `text` (fallback to `label` for backward compatibility). Updated docstrings and logging.
- **Diagram Store**: Added `addMindMapBranch()`, `addMindMapChild()`; mind map sync sets `totalBranchCount` on topic for handle generation.
- **Context Menu**: Mind map node right-click shows "Add child" and pane right-click shows "Add branch".
- **CanvasToolbar**: Mind map add-branch and add-child actions with keyboard shortcuts (Tab/Enter).
- **Flow Map & Mind Map Spec Loaders**: Enhanced spec loading and layout handling.

## [5.28.3] - 2026-03-01

### Added
- **Concept Map Arrowheads**: Click connection lines to toggle directional arrowheads. Each connection cycles through: none → arrow on clicked side → arrow on other side → both sides → none. Both segments (source→midpoint, midpoint→target) are clickable.
- **Bidirectional Markers**: Forward (right-pointing) and backward (left-pointing) arrow markers for concept map edges.
- **Shared-Handle Merge**: When multiple connections share the same target handle and all have arrowheads, they combine into one shared arrowhead.
- **bezierSplit Utility**: New `utils/bezierSplit.ts` for splitting cubic bezier paths at midpoint (De Casteljau) for segment rendering.
- **Larger Hit Area**: Concept map connection lines use a 16px invisible stroke for easier clicking while keeping the 2px visual line.

### Changed
- **CurvedEdge**: Concept maps now render two path segments per edge with click handlers, conditional markers, and hit-area paths.
- **Connection Data Model**: Added `arrowheadDirection?: 'none' | 'source' | 'target' | 'both'` to Connection for unified arrowhead state.
- **Diagram Store**: Added `toggleConnectionArrowhead()`, merge logic for shared target handles, and `arrowheadDirection` persistence in syncFromVueFlow.

## [5.28.2] - 2026-02-28

### Changed
- **Pylint Integration**: Added pylint to requirements.txt for static analysis and PEP8 linting. Updated pyproject.toml to exclude esp32/ and archive/ from pylint checks.
- **Library Service**: Refactored library_document_mixin with top-level redis_cache import, improved type hints (cast, Tuple), and PEP8 compliance. Similar cleanup in library_bookmark_mixin, library_danmaku_mixin, library_page_mixin.
- **Library Model**: Refactored models/domain/library.py for improved code organization and PEP8 compliance.
- **Frontend Components**: Code quality and styling updates across debateverse, diagram, knowledge-space, library, mindgraph, and workshop components. TeacherUsagePage and ChunkTestResultsPage layout improvements.
- **Composables & Stores**: Updates to useWorkshop, useConceptMapRelationship, useDiagramExport, useKnowledgeSpace, diagram store, and spec loaders for consistency and maintainability.
- **Tests**: PEP8 compliance and formatting fixes in test_ip_geolocation.py and test_library.py.

## [5.28.1] - 2026-02-28

### Changed
- **Concept Map Fit View**: Fit view now only triggers when user enters the canvas, not when creating links via the menu icon. Prevents unwanted view re-fit when adding connections between concepts.

## [5.28.0] - 2026-02-28

### Added
- **Concept Map Relationship Generation**: When user creates a link between two concepts or clears the label, the API generates the relationship label using the selected LLM. New `concept_map_relationship_only` mode with `concept_a`, `concept_b`, `concept_map_topic` request fields and `relationship_label` response.
- **useConceptMapRelationship Composable**: New composable for AI-generated relationship labels. Label agent: when a concept node's text changes, only regenerates edges with empty labels—avoids overwriting user-edited or AI-generated labels.
- **concept_map:label_cleared Event**: New EventBus event emitted when user clears a relationship label, triggering AI regeneration.

### Changed
- **CurvedEdge**: Shows "AI..." loading state when generating relationship label; emits `concept_map:label_cleared` when label cleared; injects `generatingConnectionIds` for per-edge loading feedback.
- **Concept Map Topic Node**: Topic node is now draggable in concept maps (vueflow.ts).
- **prompts/concept_maps.py**: Major simplification (~1769 lines removed).
- **Concept Map Agent & Workflow**: Refactored for relationship-only mode; workflow passes `concept_map_relationship_only`, `concept_a`, `concept_b`, `concept_map_topic` to agent.
- **useNotifications**: Unified notification options—`NOTIFICATION_OPTIONS` spread first for consistent defaults.
- **Pylint**: Added init-hook for project root path (fixes E1123 on `agent_graph_workflow_with_styles`).
- **AIModelSelector, CanvasToolbar, ImagePreviewModal, DiagramCanvas**: Minor updates and improvements.

### Removed
- **Plan File**: Removed `.cursor/plans/free-form_prompt_ux_enhancements_23e97284.plan.md`.

## [5.27.0] - 2026-02-27

### Added
- **Free-form Prompt UX**: Unified generation flow—both free-form and specific diagram modes now generate on the landing page, then navigate to canvas when complete. No more immediate navigation with canvas loading.
- **Rainbow Glowing Animation**: When free-form mode ("选择具体图示") is generating, prompt box shows rainbow glowing border animation for visual feedback.
- **ElButton Loading State**: Replaced send button with Element Plus `ElButton` with loading spinner during generation for both modes.
- **useRadialLayout Composable**: New `useRadialLayout.ts` for shared radial/circular layout calculation (polar positions, no-overlap formula) used by bubble map, circle map, and similar diagrams.
- **Parallel LLM Generation**: Landing page uses first-success-wins parallel calls across multiple LLMs (qwen, deepseek, kimi, doubao) for faster free-form generation.
- **Abort on Unmount**: DiagramTemplateInput aborts in-flight generation on unmount to avoid leaks.

### Changed
- **DiagramTemplateInput**: Major refactor—unified `generateFromLanding()` for both modes, `authFetch` API call, `loadFromSpec` then `router.push('/canvas')`. Free-form passes `diagram_type: null`; specific diagram passes fixed type for backend enforcement. Renamed "选择图示" → "选择具体图示".
- **CanvasPage**: Removed `canvas:generate_with_prompt` listener, `autoGenerateDiagram`, and `customPrompt`—all generation now happens on landing.
- **CanvasTopBar**: Simplified (232 lines removed); generation logic moved to DiagramTemplateInput.
- **DiagramHistory**: Simplified (207 lines removed).
- **Backend Workflow**: Removed early return for free-form mode; flow now continues to full spec generation so API returns `spec` instead of `use_default_template`. Refactored agent kwargs to explicit parameters for bridge/tree/brace maps.
- **prompt_to_diagram_agent**: Consolidated and simplified (578 lines removed).
- **Bubble/Double Bubble Map Stores**: Enhanced spec loading and layout; integrated useRadialLayout.
- **Diagram Store**: Added `loadFromSpec` and related state for pre-loaded diagrams from landing.
- **UI Store**: Added `hasValidSlots()`, template slot validation.
- **LoginModal, ChangePhoneModal**: UI improvements.
- **Context Menu**: Enhanced with additional actions.
- **WorkshopModal, DiagramCanvas, RadialEdge**: Minor updates.
- **Logging Config**: Improved log levels/formatting.

### Removed
- **Canvas Generation Flow**: Removed generation-from-canvas flow; all diagram generation now originates from landing page.

## [5.26.0] - 2026-02-26

### Added
- **Diagram Export**: New `useDiagramExport.ts` composable for exporting diagrams as PNG, SVG, PDF (via html-to-image + jspdf), and JSON. Integrated into CanvasTopBar.
- **DiagramPreviewSvg**: New `DiagramPreviewSvg.vue` component with SVG previews for each diagram type in gallery and diagram type grid.
- **Color Palette Config**: New `colorPalette.ts` with WCAG AA contrast-compliant style presets (Simple, Creative, Business, Vibrant) from ColorHunt.
- **Style Presets Apply**: CanvasToolbar style presets now apply to all nodes via `applyStylePreset()`.

### Changed
- **CanvasToolbar**: Enhanced text formatting (B/I/U/S), font family/size dropdowns, text color palette, background/border color pickers. Style presets now apply to diagram nodes. EventBus integration for delete/add node.
- **Diagram Store**: Added `applyStylePreset()` for applying style presets to all nodes.
- **DiagramTypeGrid & DiscoveryGallery**: Use DiagramPreviewSvg for diagram type previews.
- **ImagePreviewModal**: Enhanced image preview modal.
- **Scripts Reorganization**: Moved DB scripts from `scripts/` to `scripts/db/` (check_admin_status, backfill_user_usage_stats, check_diagram_counts, clear_library_tables). Moved setup scripts to `scripts/setup/` (find_esp_idf.ps1, mindgraph.service.template). Moved library scripts to `scripts/library/` (register_image_folders, rename_library_pages).
- **Admin Scripts Paths**: Updated CHANGELOG v5.23.0 to reflect correct script paths (`scripts/db/`).

### Removed
- **Scripts Root**: Removed scripts from root `scripts/` in favor of organized subdirs (`scripts/db/`, `scripts/setup/`, `scripts/library/`).

## [5.25.0] - 2026-02-25

### Added
- **useDiagramLabels Composable**: New `useDiagramLabels.ts` with `getDiagramTypeDisplayName()` and `getDefaultDiagramName()` for consistent diagram type labels (zh/en) and default names like "新圆圈图" / "New Circle Map" across CanvasTopBar, CanvasPage, WorkshopModal, and diagram templates.

### Changed
- **Diagram Default Names**: Replaced ad-hoc `新${chartType}` logic with `getDefaultDiagramName()` for proper display names (e.g. "新桥形图" instead of raw type). Diagram type now sourced from store when loaded or route query for new diagrams.
- **Bridge Map Label**: Corrected "桥型图" → "桥形图" in CanvasPage, uiConfig templates, and stores.
- **Zoom Controls**: ZoomControls now emits `zoom-in` and `zoom-out` events; CanvasPage handles zoom logic via eventBus. Removed inline zoom math from ZoomControls.
- **DiagramCanvas Fit & Controls**: Removed Vue Flow Controls from DiagramCanvas; zoom/fit moved to ZoomControls overlay. Fit padding top updated to 108px to clear CanvasTopBar (48px) + CanvasToolbar (48px). Canvas area no longer uses pt-16/pt-20; fit excludes toolbar via FIT_PADDING.
- **Context Menu Edit**: InlineEditableText context-menu edit now reuses double-click handler with 50ms defer so menu closes and selection animation shows correctly.

### Removed
- **DiagramCanvas showControls**: Removed Vue Flow Controls component and `show-controls` prop; zoom/fit handled by ZoomControls.

## [5.24.0] - 2026-02-25

### Added
- **Context Menu Copy/Paste**: Implemented copy and paste for diagram nodes. Copy stores selected nodes to clipboard; paste creates duplicates at right-click position. Supports all diagram types.
- **Context Menu Add Node**: Pane right-click "添加节点" now works for circle_map (adds context node), bridge_map (adds analogy pair), and multi_flow_map (add cause/effect). Other types show "coming soon" message.
- **Edit from Context Menu**: Right-click → 编辑 now enters edit mode with text focused and selected. InlineEditableText listens for `node:edit_requested` and triggers startEditing with selection highlight.

### Changed
- **Context Menu Click-Outside**: Fixed menu not closing when clicking elsewhere. Listeners now added/removed via watch on visibility (not just onMount). Uses mousedown capture phase so clicks on Vue Flow canvas close the menu.
- **InlineEditableText Selection**: Added `user-select: text` to override parent nodes' `select-none`, and `::selection` styles for visible text highlight when editing.
- **Diagram Store Clipboard**: Added `copiedNodes`, `copySelectedNodes()`, `pasteNodesAt()`, and `canPaste` computed for clipboard support.

## [5.23.0] - 2026-02-25

### Added
- **Teacher Usage Analytics Dashboard**: Admin-only analytics page for teacher engagement classification. 2-tier classification: unused, continuous, non-continuous (rejection, stopped, intermittent). Includes `TeacherUsagePage.vue` with ECharts visualizations, group stats, configurable thresholds, and recompute support.
- **Teacher Usage Backend**: New `routers/auth/admin/teacher_usage.py` with endpoints: `GET /admin/teacher-usage`, `GET/PUT /admin/teacher-usage/config`, `POST /admin/teacher-usage/recompute`. Reads from pre-computed `user_usage_stats`.
- **Teacher Usage Config Model**: New `TeacherUsageConfig` model for storing classification thresholds (continuous, rejection, stopped, intermittent). Scholars can tweak via UI.
- **Teacher Usage Data Models**: New `UserActivityLog` and `UserUsageStats` models; `services/teacher_usage_stats.py` for computing and upserting stats.
- **Teacher Usage Feature Flag**: `FEATURE_TEACHER_USAGE` in `config/features_config.py` (disabled by default). Frontend feature flags in `useFeatureFlags.ts` and `featureFlags.ts`.
- **Admin Scripts**: `scripts/db/check_admin_status.py` for verifying admin access; `scripts/db/backfill_user_usage_stats.py` for one-time backfill of `user_usage_stats`; `scripts/db/dump_import_postgres.py` for PostgreSQL dump/import.

### Changed
- **App Sidebar & Main Layout**: Added Teacher Usage nav item (admin-only, behind feature flag). Updated `AppSidebar.vue`, `MainLayout.vue`, router.
- **Database Config**: Registered `TeacherUsageConfig` in `config/database.py`.
- **API Config Router**: Updated `routers/api/config.py` for feature flags.
- **Infrastructure**: Updates to lifespan, startup, server launcher, recovery startup, browser, logging config.
- **Schema Migration**: Enhanced `utils/migration/postgresql/schema_migration.py`.
- **TikToken Cache**: Updated `utils/tiktoken_cache.py`.
- **Auth Admin Init**: Registered teacher usage router in `routers/auth/admin/__init__.py`.
- **Env Example**: Added `FEATURE_TEACHER_USAGE` and related env vars.

## [5.22.0] - 2026-02-09

### Changed
- **ESP32 Firmware Architecture**: Major refactoring of ESP32 firmware codebase from monolithic structure to modular component-based architecture using Brookesia framework. Replaced single-file implementations with organized component modules for better maintainability and code organization.
- **ESP32 Build System**: Updated CMakeLists.txt configuration to use standard ESP-IDF project structure with improved component management and build configuration.
- **ESP32 Main Application**: Refactored main.cpp to use Brookesia framework with component-based initialization and improved system architecture.

### Removed
- **ESP32 Legacy Code**: Removed old monolithic firmware implementation files including:
  - Application modules: `dify_app`, `smart_response_app`
  - Manager modules: `asset_manager`, `audio_handler`, `battery_manager`, `button_handler`, `config_manager`, `echo_cancellation`, `font_manager`, `i2c_bus_manager`, `rtc_manager`, `sd_storage`, `ui_manager`, `wallpaper_manager`, `wifi_manager`
  - UI modules: `launcher`, `loading_screen`, `standby_screen`, `ui_icons`
  - Utility modules: `motion_sensor`, `qrcode_generator`, `websocket_client`
- **ESP32 Legacy Configuration**: Removed `.clangd` configuration file and old build configurations.

### Added
- **ESP32 Component Architecture**: New modular component structure with separate components for:
  - Core services: `brookesia_core`, `brookesia_service_manager`, `brookesia_service_audio`, `brookesia_service_wifi`, `brookesia_service_nvs`, `brookesia_service_helper`
  - Agent integrations: `brookesia_agent_coze`, `brookesia_agent_helper`, `brookesia_agent_manager`, `brookesia_agent_openai`, `brookesia_agent_xiaozhi`
  - Application modules: `brookesia_app_ai_profile`, `brookesia_app_calculator`, `brookesia_app_game_2048`, `brookesia_app_pos`, `brookesia_app_settings`, `brookesia_app_squareline_demo`, `brookesia_app_timer`, `brookesia_app_usbd_ncm`
  - Utilities: `brookesia_lib_utils`, `av_processor`
  - Hardware components: `waveshare__esp_lcd_sh8601`
- **ESP32 Gitignore Updates**: Added gitignore entries for ESP32 reference folders (`brookesia-esp/`, `brookesia-waveshare/`).

## [5.21.0] - 2026-02-02

### Added
- **Workshop Collaborative Editing System**: Complete real-time collaborative diagram editing system allowing multiple users to edit diagrams simultaneously. Includes workshop code generation (xxx-xxx format), participant tracking, and real-time synchronization via WebSocket.
- **Workshop Service**: New `services/workshop/workshop_service.py` module for managing workshop sessions with Redis-backed session management, participant tracking with TTL-based expiration, and automatic cleanup of inactive sessions. Supports workshop code generation, session validation, and participant management.
- **Workshop WebSocket Router**: New `routers/api/workshop_ws.py` WebSocket endpoint (`/api/ws/workshop/{code}`) for real-time collaboration with features including:
  - Real-time diagram updates broadcast to all participants
  - User presence tracking and notifications
  - Node-level editing indicators with color-coded visual feedback
  - Granular update support (nodes/connections only) for efficient synchronization
  - Conflict resolution using last-write-wins with timestamps
  - Authentication and session validation via Redis
  - Heartbeat/ping-pong mechanism for connection health monitoring
- **Workshop API Endpoints**: New REST endpoints in `routers/api/diagrams.py`:
  - `POST /api/diagrams/{diagram_id}/workshop/start` - Start a workshop session
  - `POST /api/diagrams/{diagram_id}/workshop/stop` - Stop a workshop session
  - `GET /api/diagrams/{diagram_id}/workshop/status` - Get workshop status
  - `POST /api/workshop/join` - Join a workshop using a code
- **Workshop Frontend Components**: New Vue components and composables:
  - `frontend/src/components/workshop/WorkshopModal.vue` - Modal for managing workshop sessions with QR code generation, code sharing, and participant display
  - `frontend/src/composables/useWorkshop.ts` - Composable for WebSocket connection management, participant tracking, active editor indicators, and automatic reconnection with exponential backoff
- **Workshop Cleanup Service**: New `services/workshop/workshop_cleanup.py` module for background cleanup of expired workshop sessions and inactive participants.
- **Canvas Workshop Integration**: Enhanced `frontend/src/components/canvas/CanvasTopBar.vue` with workshop button, participant bar displaying active collaborators with usernames, and real-time editing indicators showing which users are editing specific nodes.

### Changed
- **Diagram Canvas**: Enhanced `frontend/src/components/diagram/DiagramCanvas.vue` with workshop integration for real-time collaborative updates and node editing notifications.
- **Diagram Store**: Updated `frontend/src/stores/diagram.ts` to support workshop code management and collaborative state synchronization.
- **Event Bus**: Enhanced `frontend/src/composables/useEventBus.ts` with workshop-related events for code changes and participant updates.
- **Diagram Router**: Enhanced `routers/api/diagrams.py` with workshop endpoints and improved rate limiting for workshop operations.

## [5.20.0] - 2026-02-02

### Added
- **Gewe Collection/Favorites Module**: Added collection/favorites management with sync, get content, and delete operations. Includes client mixin (`clients/gewe/collection.py`) and service mixin (`services/gewe/collection.py`) for managing WeChat favorites/collections with pagination support via syncKey.
- **Gewe Tag Management Module**: Added friend tag management system with add, delete, list, and modify friend tags operations. Includes client mixin (`clients/gewe/tag.py`) and service mixin (`services/gewe/tag.py`) for comprehensive tag management including batch operations and friend tag assignment.
- **Gewe Video Channel Module**: Comprehensive video channel (视频号) integration with 30+ operations including follow, comment, browse, publish, like, favorite, search, QR code operations, private messaging, CDN upload, and channel management. Includes client mixin (`clients/gewe/video_channel.py`) and service mixin (`services/gewe/video_channel.py`) for full video channel functionality.
- **Gewe SNS/Moments Service**: Added Moments (朋友圈) service module (`services/gewe/sns.py`) with operations for liking, deleting, sending (text/image/video/link), forwarding, uploading media, and managing privacy settings. Supports visibility controls, tag-based filtering, and contact-based access control.
- **Gewe Response Models**: Added comprehensive Pydantic response models (`models/domain/gewe_responses.py`) for type-safe API responses including login, messages, contacts, groups, webhooks, and all new module responses with proper field aliasing and validation.

### Changed
- **Gewe Client Modules**: Enhanced existing Gewe client modules (`account.py`, `base.py`, `contact.py`, `download.py`, `enterprise.py`, `group.py`, `message.py`, `personal.py`, `sns.py`) with improved error handling, type safety, and code organization.
- **Gewe Service Modules**: Updated Gewe service modules (`base.py`, `contact.py`, `message.py`, `personal.py`, `protocols.py`) with better integration patterns and consistent error handling.
- **Gewe Router**: Enhanced Gewe router (`routers/features/gewe.py`) with improved endpoint organization and response handling.
- **Infrastructure Middleware**: Updated HTTP middleware (`services/infrastructure/http/middleware.py`) with improved request handling and logging.
- **Application Lifecycle**: Enhanced application lifespan (`services/infrastructure/lifecycle/lifespan.py`) and startup (`services/infrastructure/lifecycle/startup.py`) with better initialization and error handling.
- **Logging Configuration**: Improved logging configuration (`services/infrastructure/utils/logging_config.py`) with better log levels and formatting.
- **Database Migration**: Enhanced PostgreSQL schema migration utilities (`utils/migration/postgresql/schema_migration.py`) with improved error handling and validation.
- **TikToken Cache**: Updated tiktoken cache utility (`utils/tiktoken_cache.py`) with improved caching strategies.
- **Frontend Package**: Updated frontend dependencies (`frontend/package.json`) with latest package versions.
- **Ask Once Page**: Enhanced AskOncePage component (`frontend/src/pages/AskOncePage.vue`) with improved UI and functionality.

## [5.19.0] - 2026-02-02

### Added
- **Gewe WeChat Integration**: Complete WeChat integration system with message handling, contact management, and group member tracking. Includes backend services (`services/gewe/`), API client (`clients/gewe/`), database models (`GeweMessage`, `GeweContact`, `GeweGroupMember`), router endpoints (`/api/gewe/webhook`), and admin frontend page (`GewePage.vue`). Supports webhook callbacks for receiving WeChat messages and events.
- **Gewe Configuration**: Added Gewe integration configuration options in `env.example` including `GEWE_TOKEN`, `GEWE_BASE_URL`, and `GEWE_TIMEOUT` settings with documentation for webhook callback URLs.
- **Multi-Flow Map Node Deletion**: Added node deletion functionality for multi-flow maps in Canvas Toolbar, allowing users to delete selected cause/effect nodes.
- **Migration Table Helpers**: New `migration_table_helpers.py` utility module for SQLite migration table operations.

### Changed
- **Bridge Map Agent**: Improved code formatting and PEP8 compliance. Enhanced docstring formatting, fixed line length issues, and improved string formatting using f-strings. Added `**kwargs` parameter for better compatibility with base class.
- **AI Model Selector UI**: Major visual improvements with glassmorphism design, model-specific color themes (Qwen: indigo, DeepSeek: green, Doubao: orange), improved hover effects, and enhanced dark mode support. Removed checkmark icon in favor of color-coded idle states.
- **Canvas Toolbar**: Enhanced with multi-flow map node deletion functionality, allowing users to delete selected cause/effect nodes with proper validation and user feedback.
- **Diagram Components**: Improved FlowNode, TopicNode, LabelNode, and InlineEditableText components with better event handling and user interaction.
- **Multi-Flow Map Store**: Enhanced multi-flow map store with improved node deletion logic and better state management.
- **Bridge Map Store**: Improved bridge map store with better spec loading and error handling.
- **Library Router**: Significant code refactoring and reduction (1254 lines removed) with improved code organization and maintainability.
- **Migration Utilities**: Improved SQLite migration utilities (`migration_backup.py`, `migration_tables.py`, `migration_utils.py`) with better error handling and code organization. Enhanced PostgreSQL data migration utilities.
- **Database Model Registration**: Added Gewe model registration in `config/database.py` for automatic database migration support.
- **Dify API Configuration**: Updated default Dify API URL from custom server (`http://101.42.231.179/v1`) to official API (`https://api.dify.ai/v1`) in `env.example`.
- **SSE Streaming**: Improved Server-Sent Events streaming implementation with better error handling.
- **Admin Page**: Enhanced admin page with Gewe integration access and improved navigation.
- **Router Registration**: Updated router registration to include Gewe feature routes.
- **Clear Library Tables Script**: Improved script with better error handling and user feedback.

### Fixed
- **Code Formatting**: Fixed PEP8 compliance issues throughout codebase, including line length, string formatting, and import organization.
- **Bridge Map Agent**: Fixed variable name inconsistency (`prompt` vs `user_prompt`) in full generation mode.
- **Diagram Canvas**: Improved edge rendering and node interaction handling.
- **Straight Edge Component**: Enhanced edge visualization and interaction.
- **Event Bus**: Improved event handling and type safety.


## [5.18.0] - 2026-01-31

### Added
- **Library Exception Handling**: New `exceptions.py` module with specific exception types (`DocumentNotFoundError`, `PageNotFoundError`, `PageImageNotFoundError`, etc.) for better error handling and clearer error messages.
- **Library Redis Caching**: New `redis_cache.py` module providing Redis-backed caching for library operations (document metadata, danmaku lists) to reduce database load and improve performance in multi-server deployments. Uses cache-aside pattern with configurable TTLs.
- **Endpoint Authentication Audit Scripts**: New `audit_endpoints_auth.py` and `audit_endpoints_simple.py` scripts for auditing API endpoints to identify authentication requirements and potential security issues.
- **Library Page Renaming Script**: New `rename_library_pages.py` script for renaming library page image files to sequential numbering patterns while preserving book names. Includes preview mode (dry-run) support.
- **Library Test Suite**: New `test_library.py` test file for library service testing.
- **Optional Authentication Support**: Added `get_optional_user()` dependency function in library router to allow public access to certain endpoints (document listings, cover images) while maintaining authenticated features.
- **Document Serialization Helper**: Added `serialize_document()` helper function to reduce code duplication across library endpoints.

### Changed
- **Library Router**: Major refactoring with improved error handling using specific exception types, optional authentication support for public endpoints, and better code organization. Added rate limiting support and improved response serialization.
- **Library Service Mixins**: Refactored library service mixins (`library_document_mixin.py`, `library_danmaku_mixin.py`, `library_bookmark_mixin.py`, `library_page_mixin.py`) with improved error handling, Redis caching integration, and better exception handling.
- **Image Viewer Component**: Simplified page navigation logic by removing complex missing page detection and skipping mechanisms. Now relies on standard error handling for missing pages.
- **Library Viewer Page**: Added authentication checks throughout the component. Bookmark operations now require authentication and show login modal for unauthenticated users. Improved error handling for bookmark status checks.
- **Login Modal Component**: Improved UI with better z-index handling (changed from z-[9999] to z-[1000]), removed backdrop blur, and improved close button positioning with better z-index.
- **Diagram Template Input**: Added authentication check to prevent submission when user is not authenticated. Submit button is disabled for unauthenticated users.
- **Mindmate Input Component**: Added authentication check to disable send button when user is not authenticated. Improved disabled state handling with computed property.
- **API Client**: Updated with improved error handling and type definitions for library operations.
- **Server Launcher**: Enhanced server launcher with improved process management and error handling.

### Fixed
- **Library Authentication**: Fixed issue where library features were accessible without authentication. Now properly checks authentication status before allowing bookmark operations and other user-specific features.
- **Login Modal Z-Index**: Fixed z-index conflict by reducing from z-[9999] to z-[1000] and improving close button positioning.
- **Image Viewer Complexity**: Simplified image viewer by removing overly complex page skipping logic that could cause navigation issues. Now uses standard error handling.
- **Error Logging**: Improved error logging throughout library services to use appropriate log levels and provide better context.

## [5.17.0] - 2026-01-30

### Added
- **Image Viewer Component**: New `ImageViewer.vue` component for displaying pre-rendered page images with zoom, navigation, rotation, and pin-based comment overlay support. Supports lazy loading and preloading of adjacent pages.
- **Image Path Resolution Service**: New `image_path_resolver.py` module for resolving page image paths from folder paths and page numbers. Supports multiple naming patterns (page_001.jpg, 001.jpg, page1.jpg, etc.).
- **Library Path Utilities**: New `library_path_utils.py` module for path normalization and cross-platform compatibility utilities.
- **Image Folder Registration Script**: New `register_image_folders.py` script for scanning and registering existing image folders as library documents with preview mode (dry-run) support.
- **Library Table Management Script**: New `clear_library_tables.py` script for clearing library tables in PostgreSQL development environment.
- **PostgreSQL Configuration Modules**: New PostgreSQL management modules (`_postgresql_config.py`, `_postgresql_helpers.py`, `_postgresql_init.py`, `_postgresql_paths.py`) for improved database lifecycle management.
- **Library Bookmark Page**: New `LibraryBookmarkPage.vue` page component for bookmark management.
- **Image-Based Document Support**: Added support for image-based documents in library system with `use_images`, `pages_dir_path`, and `total_pages` fields in `LibraryDocument` model.
- **Page Image API Endpoint**: New `GET /api/library/documents/{id}/pages/{page}` endpoint for serving page images.

### Changed
- **Library Viewer Page**: Updated `LibraryViewerPage.vue` to support both PDF and image viewing modes with automatic mode detection based on document `use_images` flag.
- **Library Service**: Refactored `library_service.py` to support image-based document management, including image folder registration and page counting. Added in-memory page caching with LRU eviction to optimize directory scans and next available page detection.
- **Library Router**: Updated library router endpoints to support image-based documents, including page image serving and document metadata updates. Added `X-Next-Available-Page` header in 404 responses to help frontend automatically skip missing pages.
- **Library Store**: Enhanced `library.ts` store with image-related functionality and improved document management.
- **API Client**: Updated `apiClient.ts` with image URL helpers (`getLibraryDocumentPageImageUrl`) and updated type definitions for image-based documents.
- **Comment Panel**: Updated `CommentPanel.vue` component to work seamlessly with both PDF and image viewers.
- **Danmaku Overlay**: Updated `DanmakuOverlay.vue` component to support image viewer coordinate system.
- **PostgreSQL Manager**: Refactored `_postgresql_manager.py` into modular components for better maintainability and separation of concerns.
- **Application Lifespan**: Updated application lifecycle management to remove PDF auto-import scheduler dependencies.
- **Library Module**: Updated `services/library/__init__.py` to export new image-related services and utilities.
- **Image Viewer Component**: Enhanced `ImageViewer.vue` with automatic page skipping when pages don't exist (404 handling). Automatically detects and navigates to next available page using `X-Next-Available-Page` header from backend.
- **Vite Configuration**: Simplified `vite.config.ts` by removing PDF.js worker and cmaps copying plugins (no longer needed for image-based system).
- **SPA Handler**: Removed PDF.js related static file mounts (`/pdfjs/` and `/cmaps/`) from SPA handler.
- **Exception Handlers**: Improved HTTP exception handling to log expected 404s (missing pages, bookmark checks) at DEBUG level instead of WARNING to reduce log noise.

### Removed
- **PDF Viewer Component**: Removed `PdfViewer.vue` component in favor of image-based viewing system.
- **PDF Import Services**: Removed PDF-related services including `pdf_importer.py`, `pdf_optimizer.py`, `pdf_cover_extractor.py`, and `pdf_utils.py`.
- **PDF Analysis Scripts**: Removed PDF analysis and testing scripts (`analyze_pdf_structure.py`, `analyze_pdf_structure_simple.py`, `compare_pdf_environments.py`, `diagnose_pdf_xref.py`, `fix_pdf_xref_issues.py`, `test_pdf_js_behavior.py`, `test_pdf_optimizer.py`, `test_pdf_text_extraction.py`, `test_range_requests.py`).
- **PDF Import Scripts**: Removed `library_import.py` and `linearize_pdfs.py` scripts.
- **Auto Import Scheduler**: Removed `auto_import_scheduler.py` service for automatic PDF import.
- **Sync Validator**: Removed `sync_validator.py` service for PDF sync validation.
- **WSL Documentation**: Removed `README_WSL.md` documentation file.
- **PDF Toolbar**: Removed `PdfToolbar.vue` component (functionality integrated into viewer components).
- **PDF.js Dependencies**: Removed `pdfjs-dist` npm package and `verify-pdf-worker.js` script from frontend build process.
- **PDF.js Build Plugins**: Removed PDF.js worker and cmaps copying plugins from Vite configuration.

### Fixed
- **Library Comments History**: Fixed and improved `LibraryCommentsHistory.vue` component functionality.
- **Cross-Platform Path Handling**: Improved path normalization for better cross-platform compatibility.
- **Image Viewer Page Navigation**: Fixed issue where image viewer would fail when encountering missing pages. Now automatically skips to next available page using backend-provided `X-Next-Available-Page` header.
- **Library Service Performance**: Optimized page availability checks with in-memory caching (5-minute TTL, LRU eviction) to avoid repeated directory scans when checking for missing pages.
- **Error Logging**: Fixed excessive warning logs for expected 404 errors (missing pages, bookmark checks) by logging them at DEBUG level instead.

## [5.16.0] - 2026-01-30

### Added
- **Library Feature**: Complete library management system with PDF viewer, danmaku (comment overlay), and document management capabilities. Includes full frontend and backend implementation with Vue components, Pinia stores, and FastAPI endpoints.
- **PDF Viewer Component**: Interactive PDF viewer with zoom, navigation, page rendering, and pin/comment overlay support using PDF.js.
- **Danmaku/Comment System**: Real-time comment overlay system for PDF documents with pin-based annotations and comment panels.
- **Library Sync Validation**: Comprehensive sync validation system (`sync_validator.py`) to maintain consistency between PDF files in storage, cover images, and database records. Includes validation functions and sync reporting capabilities.
- **PDF Analysis Scripts**: Added analysis scripts (`analyze_pdf_files.py` and `analyze_pdf_lazy_loading.py`) for analyzing PDF structure and verifying lazy loading feasibility.
- **PDF Utilities Module**: New `pdf_utils.py` module with PDF validation (magic bytes check) and path normalization utilities for cross-platform compatibility.
- **Auto Import Scheduler**: Background automatic PDF import system with startup initialization and periodic background scheduler (`auto_import_scheduler.py`).
- **Library Service**: Complete library service implementation with document management, PDF import, cover extraction, and database operations.
- **Feature Flags System**: Frontend feature flag system for enabling/disabling library features via configuration.
- **API Client Utilities**: Comprehensive API client utilities for frontend-backend communication with error handling and type safety.
- **PDF Cover Extraction**: Automatic cover image extraction from PDF documents with standardized naming (`{document_id}_cover.png`).
- **Diagnostic Endpoints**: Added `/._diagnostic/static-files` endpoint for verifying static file serving configuration.

### Changed
- **PDF Viewer Component**: Significant improvements to PDF viewer component with enhanced functionality (260+ lines added in latest update, 300+ lines in initial implementation).
- **PDF Worker Loading**: Refactored PDF.js worker loading to use `/pdfjs/` directory with StaticFiles mount, consistent with other static file serving patterns.
- **Library Router**: Enhanced library router with comprehensive endpoints for document management, PDF serving, cover images, and library operations.
- **Path Normalization**: Implemented path normalization across all library modules for cross-platform compatibility (WSL/Ubuntu/Windows).
- **Cover Image Handling**: Improved cover image loading with fallback to placeholder icons when images fail to load, removed strict v-if checks.
- **PDF Path Resolution**: Enhanced PDF path resolution with fallback logic (absolute path → storage_dir → CWD) for cross-platform compatibility.
- **Error Handling**: Improved error handling throughout library modules with specific exception types and detailed logging.
- **Duplicate Detection**: Enhanced duplicate detection with normalized path comparison.
- **Auto Import Scheduler**: Updated auto import scheduler with improved error handling and validation logic.
- **Application Lifespan**: Updated application lifecycle management to integrate library auto-import and sync validation features.
- **Static File Serving**: Enhanced static file serving with improved logging and diagnostic capabilities.

### Fixed
- **PDF Viewer Pin Interaction**: Fixed critical issue where PDF library pins were rendered correctly but not clickable or draggable. Root cause was pin elements inheriting `pointer-events: none` from parent layer. Fixed by explicitly setting `pointer-events: auto` inline at multiple lifecycle points.
- **PDF Viewer Worker Loading**: Fixed 404 errors when loading PDF.js worker in production by serving root-level static files from dist/ and adding proper StaticFiles mounts.
- **PDF Viewer Ref Safety**: Added comprehensive null checks for `pinsLayerRef` and `canvasRef` throughout component to prevent errors when refs are not yet available.
- **Library Cover Images**: Fixed issue where cover images didn't show even when files existed by removing strict v-if checks and adding proper error handling.
- **PDF Path Resolution**: Fixed PDF loading issues due to path differences between WSL and Ubuntu environments with improved fallback logic.
- **TypeScript Errors**: Fixed TypeScript errors in PDF viewer components.
- **Linter Errors**: Removed unused `library_auto_import_task` variable from application lifespan module to resolve linter warnings.
- **Danmaku Pin Rendering**: Fixed danmaku pin rendering and click handling in PDF viewer.
- **Library Page Linting**: Fixed linting errors in LibraryPage.vue component.

## [5.15.1] - 2026-01-29

### Fixed
- **PDF Viewer Pin Interaction**: Fixed critical issue where PDF library pins were rendered correctly but not clickable or draggable. The root cause was that pin elements inherited `pointer-events: none` from the parent `.pdf-pins-layer`. Fixed by explicitly setting `pointer-events: auto` inline on pin elements at multiple points in the lifecycle (creation, Vue mounting, DOM appending) and adding `!important` to the CSS rule as a safeguard.
- **PDF Viewer Ref Safety**: Added comprehensive null checks for `pinsLayerRef` and `canvasRef` throughout the component to prevent errors when refs are not yet available, improving stability during component lifecycle transitions.

## [5.15.0] - Previous Release

Initial version tracking.
