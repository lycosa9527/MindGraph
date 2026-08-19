# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.180.16] - 2026-08-20

> **Tencent T-Sec is the default captcha. The login form has no image code; the Tencent popup runs when you click sign in. The old SVG captcha stays behind `CAPTCHA_PROVIDER=legacy`.**

### Added

- **T-Sec captcha** — Default `CAPTCHA_PROVIDER=tsec`. On 同意协议并登录 (and register / send code / change password or phone), Tencent Captcha 2.0 pops up. After a pass, the server checks the ticket with `DescribeCaptchaResult` and the existing auth APIs still receive `captcha` + `captcha_id`. Set `CAPTCHA_PROVIDER=legacy` to restore the SVG image and 4-character field. The old captcha generate/verify code is unchanged.
- **T-Sec AppId auth** — Each popup mints a one-time server-side `aidEncrypted` (AES-256-CBC, unique IV) so console **CaptchaAppId 强制校验** and **一次一密** both work. `AppSecretKey` never goes to the browser.
- **Local SVG captcha** — On WSL/dev, set `CAPTCHA_PROVIDER=legacy` to keep the image + 4-character field. Production stays on T-Sec. SMS/email still use the 6-digit code.

### Tests

- `tests/test_tsec_captcha.py` / `tests/test_tsec_aid_encrypted.py` / `frontend/tests/tsecCaptcha.spec.ts`

## [5.180.15] - 2026-08-19

> **Adding a mind-map main branch always starts silent auto-complete; Kitty waits for generate before saying it is done.**

### Fixed

- **Kitty branch complete** — Adding a mind-map main branch always starts silent auto-complete (typed loop + one-sentence router). The done-ack may say “正在补完整” because that work is running. Explicit `auto_complete_branch` is the same fill path. The loop does not say “补全好了” until generate finishes. Delete acks fall back to the spoken label when the UUID is missing from session context (`「」已删除`).

### Tests

- `tests/test_kitty_agent_loop.py` / `_five_maps.py` / `_five_maps_live.py` / `test_kitty_ack_library.py` / `test_pending_branch_autocomplete.py`

## [5.180.14] - 2026-08-19

> **Kitty typed text uses a tool loop; mind-map string children keep a UUID; PNG export stays on html-to-image 1.11.11.**

### Added

- **Typed agent loop** — Keyboard and Fun-ASR `{type:"text"}` run an OpenAI-compatible ReAct loop (`qwen3.6-flash`, cap 5). Identity resolve runs first (durable UUID). Structural `diagram.*` go through the verified DiagramCommandBus; `auto_complete` / `clarify_options` target by `node_id` but are not ExpectedEffect verifies. Omni `function_call` stays one-shot.

### Changed

- **Typed mindmap edits** — All typed mindmap structural ops use the verified Bus (not only the one-sentence panel). Heuristics run only after LLM timeout, empty tools, or the step cap. Unrecognized clarify replies no longer drop the pending options.

### Fixed

- **Identity** — Leftover `branch-*` live ids migrate to `mindMapUid` before snapshot/dispatch. Successful `auto_complete` counts as progress so heuristics do not fire after a good UI tool. Insufficient thinking coins fail the turn instead of a fake heuristic success.
- **LLM spec coerce** — Bare string children and mind-map `left` / `right` / `children` trees stay trees (some models emit a label string). Canvas hydrate no longer assigns `uid` onto a string.
- **PNG/SVG/PDF export** — Pin `html-to-image` at 1.11.11. 1.11.12+ deep-clones SVG without inlining styles, so Vue Flow curves export with black ghost strokes.

### Tests

- `tests/test_kitty_agent_loop.py` / `_messages.py` / `_five_maps.py` / `_sams_club.py` (live optional: `LIVE_LLM=1`)
- `frontend/tests/mindMapNodeUid.spec.ts` / `mindMapSubgraphMerge.spec.ts` / `mindMapStringChildrenAudit.spec.ts`
- `tests/test_prompt_to_diagram_result.py`

## [5.180.13] - 2026-08-19

> **思维讲堂 does not start a job or TTS until the mascot modal opens.**

### Fixed

- **Classroom launch gate** — Opening a diagram no longer restores the 思维讲堂 job or prefetches first-slide TTS. The by-diagram GET, job watch, and CosyVoice warmup start when the user opens the mascot modal (or clicks Start). Closing the modal does not cancel an in-flight script; a late GET after close is dropped.

### Tests

- `frontend/tests/useMindClassroomLecture.spec.ts` — diagram / settings stay silent; modal open restores
- `frontend/tests/useMindClassroomLectureQueue.spec.ts` — restore gated; Start still reuses; late GET after close is dropped
- `frontend/tests/warmupLectureTts.spec.ts` — `isLaunchActive`

## [5.180.12] - 2026-08-19


> **Mind-map branches keep a stable UUID; new main branches balance clockwise; v2 drag shows the dashed drop target.**

### Changed

- **Stable node identity** — Live mind-map `node.id` is a UUID (topic stays `topic`). Location is connections plus `mindMapSide` / `mindMapDepth`. Leftover `branch-*` / invented ids stay aliases only (`mindMapLegacyId`). Agents target UUID and chain on `created_node_ids`; `add_node` does not invent ids. See [`docs/architecture/mindmap_node_identity.md`](docs/architecture/mindmap_node_identity.md).
- **L1 add / delete** — `addMindMapBranch()` with no side clockwise-balances; an explicit `left` / `right` stays on that side. Deleting an L1 on a two-sided map redistributes the rest the same way. Kitty, toolbar, outline, paste, and brainstorm share that rule.
- **Kitty spoken target** — Acks use the branch label, never a UUID or leftover id.
- **Removed `FEATURE_DRAG_AND_DROP`** — Unused stub. Canvas / palette drag is always on.

### Fixed

- **v2 branch drag** — Hide the four `+` handles and the connector `−` while dragging. Hovering another node shows the dashed drop box (UUID hit-test; leftover `branch-*` prefix matching is gone). Underline children use the same box, not a thin baseline bar.

### Tests

- `tests/test_mindmap_identity.py` / `test_mindmap_identity_kitty_e2e.py`
- `frontend/tests/mindMapIdentityMigrate.spec.ts` / `branchMoveHitTest.spec.ts` / `mindMapSeparation.spec.ts` / `mindMapLoadPreserveSides.spec.ts`
- `tests/test_diagram_edit.py` — leftover delete still uses label; live UUID is the verify key
- `tests/test_diagram_agent_context.py` / `test_kitty_ack_library.py`
- CI (`ci.yml` / `ci-local.sh`) now runs the identity, ack, and v2 drag/add-balance specs

## [5.180.11] - 2026-08-18

> **思维讲堂 Start keeps the job that just finished; multi-LLM auto-complete no longer drops peers on save or library switch.**

### Fixed

- **Ready attach vs enqueue snapshot** — When the first branch is already playable, finishing the job no longer clears Start just because the enqueue-time node ids drifted (LLM switch / layout settle). The script stays attached if its focus ids are still on the canvas. A Kitty full rewrite still goes back to blue Start.
- **Second Start reuse** — Reuse matches launch settings (mode, tone, LLM, …) and ignores localized `audience_title`. A ready job whose steps still hit the live map is reused instead of paying for another Celery run.
- **SSE close at ready** — If the watch drops when the stream ends, Start re-reads the Postgres row (or keeps the mid-job warmup) instead of toasting empty and resetting.
- **Multi-LLM persist** — A 3-model spec that exceeds the size cap no longer strips all `llm_results` (that overwrote a good 2-model save). Pack selected + as many peers as fit. Persist even when `selectedModel` was never painted; clone the blob so a later store write cannot mutate a queued PUT.
- **Library switch during auto-complete** — Drain in-flight PUTs before teardown. Flush again while dirty or still generating (`llm:model_completed` marks dirty because later models do not change the canvas fingerprint). Desktop, mobile, and Kitty library reload restore `llm_results` the same way.

### Tests

- `tests/test_mind_classroom_job_match.py` — settings match; steps bind live
- `frontend/tests/mindClassroomRemoteSteps.spec.ts` — drifted snapshot, live focus
- `frontend/tests/useMindClassroomLectureQueue.spec.ts` — ready attach + SSE drop
- `frontend/tests/llmResultsPersist.spec.ts` / `llmResultsPersistAudit.spec.ts` / `llmResultsTeardown.spec.ts`
- `frontend/tests/shouldFlushBeforeLibrarySwitch.spec.ts`

## [5.180.10] - 2026-08-18

> **思维讲堂 Start follows the Postgres manifesto — Redis pushes live, a rewritten map goes back to blue Start.**

### Changed

- **Classroom Start status** — The Start button follows the job row in Postgres (Redis live push, Postgres on SSE idle/drop). In-flight Start reattaches; a rewritten map goes back to blue Start; a 429 from another in-flight job no longer paints this map red. Stuck jobs fail after 15 minutes so they cannot hold the per-user cap.

### Tests

- `frontend/tests/mindClassroomLaunchState.spec.ts` — Start-button chrome from job status
- `frontend/tests/useMindClassroomLectureQueue.spec.ts` — reattach, Kitty rewrite, 429
- `scripts/audit_mind_classroom_status_e2e.py` — live Celery + Redis/PG + button cases

## [5.180.9] - 2026-08-18

> **节点解释 is a short bubble beside the node; 思维讲堂 prep stays per map and LLM.**

### Changed

- **Node explain bubble** — 节点解释 now streams one everyday gloss (~25–30 words) into a speech bubble anchored around the selected node. Click empty canvas, press Esc, or use the close button to dismiss. The old three-panel modal is gone.
- **Classroom prep slots** — Switching maps or the canvas LLM parks the in-flight 思维讲堂 job (progress, prepared steps, voice warmup) and restores it when you come back. Jobs and transcripts are keyed by diagram + LLM so a reuse lookup cannot attach another model's script.
- **Ready toast** — When first-slide voice is playable, a global toast opens the 思维讲堂 modal (skipped if a lecture is already running).
- **Autoplay prefetch** — Playing slide N warms only N+1; a manual jump TTS the landed caption instead of the old three-slide bank.
- **Showcase cover lease** — A later Celery run no longer overwrites a cover job it does not own. The feed spinner follows `converting_preview` / `generating_cover` and attaches SSE; auto-enqueue stays off while a job is in flight. Unknown fail reasons are not retried.

### Tests

- `test_meaning_prompt_asks_for_short_everyday_gloss` / `test_english_meaning_prompt_asks_for_twenty_five_words`
- `frontend/tests/useNodeExplainBubblePosition.spec.ts` — right / left / below placement
- `frontend/tests/mindClassroomPrepSlot.spec.ts` — park/restore per diagram+LLM
- `tests/test_mind_classroom_job_match.py` — spec/LLM/live-node match
- `tests/test_lecture_autoplay_prefetch.py` — next-slide only
- `tests/test_showcase_cover_job_manifest.py` — lease lost / in-flight block

## [5.180.8] - 2026-08-18

> **Repo root cleanup: MindChunk lives under knowledge, Locust loadtests are gone, and `storage/` is runtime-only.**

### Changed

- **MindChunk package** — Moved `llm_chunking/` to [`services/knowledge/llm_chunking/`](services/knowledge/llm_chunking/). Imports and logger lists follow the knowledge package; CI pylint now covers the chunker.
- **RLS SQL package** — Moved `db_rls/` to [`utils/db_rls/`](utils/db_rls/) so it sits with runtime RLS helpers in `utils/db/` without colliding with PyPI `alembic`. Migrations and dump scripts import `utils.db_rls`.
- **Load tests** — Removed unused `loadtests/collab` Locust harness, [`.github/workflows/nightly-collab.yml`](.github/workflows/nightly-collab.yml), and `typings/locust`. Collab soaks stay on [`scripts/collab_synthetic_probe.py`](scripts/collab_synthetic_probe.py) and the online-collab runbook.
- **Runtime storage** — Stopped tracking leftover `storage/qdrant` lock files. `.gitignore` now ignores the whole `storage/` tree (library pages, knowledge docs, tiktoken cache). Library covers were never migrated to COS because the public library module is unused.

## [5.180.7] - 2026-08-18

> **思维讲堂 job progress is Redis/SSE — the Start button no longer polls every 1.5s.**

### Changed

- **Event-driven job watch** — Workers publish each manifesto write to `mind_classroom:job:{id}`. The client opens `GET /api/mind-classroom/jobs/{id}/stream` and updates the button from those events. There is no HTTP poll loop and no 20s voice-ready timer; first-slide TTS unlocks only when Kitty reports prefetch ready/failed.
- **Concurrent classroom jobs** — `MIND_CLASSROOM_MAX_ACTIVE_JOBS` can raise the per-user in-flight cap (default remains 1) so a 4-worker load run can enqueue several maps at once.
- **Celery loop-bound Redis** — Prefork workers that run a second `asyncio.run` no longer reuse a Redis client from the closed first loop (`Event loop is closed`).

### Tests

- `tests/test_mind_classroom_job_events.py` — channel, payload, snapshot without a request.
- `tests/test_redis_async_loop_reuse.py` — second `asyncio.run` gets a new Redis client.
- `frontend/tests/mindClassroomJobApi.spec.ts` — SSE watch resolves on the first playable snapshot.

## [5.180.6] - 2026-08-18

> **Start stays on writing the lesson plan until every branch script is done; voice-wait is only after that.**

### Fixed

- **Start label vs TTS** — First-slide voice ready (or still loading) while other families are in flight no longer shows 正在加载语音. That copy is only when `in_flight === 0` and Kitty is still warming. Mid-job the button stays on 正在写其余教案 / 正在为分支…写教案.

## [5.180.5] - 2026-08-18

> **思维讲堂 TTS catches up as each finished branch lands, without dropping the opening slide.**

### Changed

- **Script prefix persist** — As soon as family 0…N is a contiguous finished prefix, those steps are written while the job is still `generating`. A later family finishing first does not jump the queue.
- **TTS catch-up** — The client updates prepared steps on each poll and prefetches up to three slides. Kitty keeps ready PCM in a small bank; warmup `prefetch` queues behind the opening slide instead of replacing it.

### Tests

- `contiguous_raw_prefix` — hole at family 0 writes nothing; 0 then 1 writes both.
- `warmupLectureTts` — later family on the job prefetches slide 2 once.
- `test_catchup_prefetch_does_not_drop_ready_first_slide`.

## [5.180.4] - 2026-08-18

> **思维讲堂 Start fill tracks finished branches while the traveling ring keeps moving.**

### Changed

- **Start progress fill** — Busy Start keeps the blue traveling ring and adds a left-to-right fill in stacked blues. Width is `done / total` families (1/6 → 17%, 3/6 → 50%). No ledger yet stays navy; the ring still spins.

### Tests

- `mindClassroomStartFillPercent` — 0/6, 1/6, 3/6, 6/6.

## [5.180.3] - 2026-08-18

> **思维讲堂 parallel branches share one sticky progress ledger; Start follows writing → voice → remaining.**

### Fixed

- **Progress last-write-wins** — Parallel streams no longer replace the whole manifesto `progress` blob. Each family is a slot (`pending` / `streaming` / `done`); `tts_ready` stays true after the opening family lands. The Start name is the lowest-index still-writing branch, not whoever emitted the latest first token.
- **Start label while generating** — After the first family is stored, the button shows 正在加载语音, then 正在写其余教案（done/total） once opening TTS is ready. It no longer stays on 正在为分支…写教案 through voice warmup.
- **按主分支 fan-out** — Same one-DashScope-call-per-L1-family path as 逐个节点. A map with several main branches no longer waits on a single full-tour call.

### Changed

- Sibling family LLM tasks are cancelled if one family fails mid-job.
- Poll INFO includes `done=N/M` and `tts_ready` so uvicorn tracks the ledger, not only the last phase string.

### Tests

- `tests/test_mind_classroom_tour_progress.py` — sticky `tts_ready`, stable display branch, no done→streaming regress.
- `test_main_branch_families_call_llm_in_parallel` — 按主分支 starts all L1 calls before any finishes.
- `mindClassroomLaunchState.spec.ts` — loading-voice and remaining labels while `generating`.

## [5.180.2] - 2026-08-17

> **思维讲堂 Start stays in motion while writing the lesson plan; poll logs name the stage.**

### Changed

- **Start button busy** — Same blue traveling ring as auto-complete / avatar while queued, writing 讲稿／教案, or loading voice.
- **重写教案** — Restart control is no longer “重新开始”; zh / zh-tw / en match rewrite-lesson-plan.
- **Job stage logs** — Worker INFO: reading diagram spec, generating script for branch N, DashScope request sent, LLM waiting / received. GET `/api/mind-classroom/jobs/{id}` logs `poll … phase=…` on change or every 15s (uvicorn no longer looks like a silent 200).
- **Script timeout** — Canvas-tour Celery soft/hard limit 120s/150s → 600s/660s so a slow DashScope wave is not killed mid-write.
- **each_node scripts** — One DashScope call per trunk family, all at once (7 branches = 7 concurrent calls). The previous sequential loop is what made rewrite look like a 120s timeout.
- **Early TTS** — When the first trunk family returns, those steps are written while the job is still `generating`. The client prefetches opening-slide voice immediately; Start stays locked until the rest of the script is ready.
- **Script LLM stream** — Canvas-tour uses DashScope `chat_stream`. Worker INFO: `LLM result streaming for branch N/M` on first token, every 800 chars, and every 15s.
- **Start label** — While writing a canvas-tour script, the button shows 正在为分支{name}写教案 using the live `progress.branch_label`.

### Tests

- `tests/test_mind_classroom_progress_log.py` — poll line, heartbeat dedupe, branch label.
- `test_each_node_families_call_llm_in_parallel` — all trunk families start before any finishes.
- `test_first_family_persists_before_other_branches_finish` — opening family is stored before the rest return.
- `tests/test_mind_classroom_tour_stream.py` — stream chunk parse, heartbeat cadence, token join.
- Script-task limit assertion updated.

## [5.180.1] - 2026-08-17

> **WeChat / older WebViews no longer crash on `Iterator`; node-explain i18n works outside setup.**

### Fixed

- **`Iterator is not defined`** — Oxc does not lower ES2025 Iterator helpers, so a `Iterator.from` polyfill is installed at startup. Vite JS target is also pinned to ES2020 + Chrome 87 / Safari 14 (not 2026 baseline `chrome111`); CSS target is `chrome61` for WeChat `#RGBA`.
- **vue-i18n `SyntaxError: 26`** — That code is `MUST_BE_CALL_SETUP_TOP` (`useI18n()` with no component instance). `useLanguage()` now uses the `i18n.global` singleton (same pattern as ZhiHui handoff) so node-explain / dialog remounts do not throw.

### Tests

- `iteratorHelpersPolyfill.spec.ts` — install when missing, map/filter, raw iterator, reject non-iterables.
- `useLanguage.spec.ts` — translate without a Vue setup instance.
- `safeI18nTranslate.spec.ts` — fallback when the translator throws.

## [5.180.0] - 2026-08-17

> **Mind-map 编号 is chrome on the new canvas; 按主分支 lecture lights the whole branch.**

### Added

- **思维导图 编号** — 主题风格 panel: enable/hide plus prefix and nested styles. Prefixes are painted chrome (not stored in `node.text`). L1 uses 前缀风格; L2+ uses 下级编号 (outline path or restarting glyphs, including 章/节/段 and 条/款/项). Topic/center is never numbered. New / regenerated diagrams stay off unless the spec enables it. Box width and wrap use this node’s glyphs (`1.` vs `①` vs `第一章` vs `1.1.1`). PDF/SVG draws the same chrome; body wraps beside it.

### Fixed

- **思维讲堂 highlight** — In 按主分支 (and slide-deck canvas), the current branch and its descendants stay fully visible; only the head is selected / blue-outlined. Incoming stem from the topic stays lit. Overview and closing no longer outline the topic. Empty focus no longer dims the whole map. Tour scope is snapshotted for the session.
- **Mind-map PDF text Y** — Export baseline matches canvas `line-height` (half-leading + ascent) so branch labels sit in the box instead of a few pixels high.
- **Celery Redis pools** — Result-backend pools get the same RESP2 / no-SCH defaults as the broker, so OSS Redis is not probed for `CLIENT MAINT_NOTIFICATIONS`.

### Tests

- Numbering glyphs, clockwise L1, per-prefix width/height, outline cache fingerprint, vector prefix chrome, PDF baseline.
- `expandLectureFocusNodeIds` — main-branch / slide-deck expand the subtree; each-node stays on one node.
- Celery Redis result-backend pool options.

## [5.179.0] - 2026-08-17

> **思维讲堂 is event-bus + Pinia; CosyVoice prefetches the next slide; lecture scripts stay on a stable COS key.**

### Added

- **Lecture command bus** — Start, restart, stop, pause, next/prev, and voice go through `classroom:*` events. Pinia holds job, session, generations, and `startInFlight`. Closing the launch modal does not cancel the server job; restore reattaches when it is ready.
- **TTS lookahead** — While slide N plays, a second CosyVoice socket synthesizes N+1 and the next narrate plays from cache. Skip/pause still interrupt.

### Changed

- **Lecture scripts** — Stable COS key `mind_classroom/transcripts/{user}/{diagram}/{mode}.md`; regenerate overwrites that key and then deletes leftover `{job_id}.md`. `.md` assets use `Cache-Control: private, no-store`.
- **Celery banners** — Process monitor replaces a worker whose `[tasks]` list is stale after an API recycle. Manual WSL restart is documented in `docs/CELERY_SETUP.md`.

### Tests

- Frontend: event-bus start, queue attach/abandon, launch lock, lecture TTS prefetch generation.
- Backend: Kitty narrate + prefetch cache, transcript key replace, enqueue/reuse, Celery stale-banner health.

## [5.178.1] - 2026-08-16

> **思维讲堂 stays on the current canvas; Celery job status is visible in backend logs.**

### Fixed

- **Lecture session isolation** — Switching library diagrams or unloading the canvas tears down the lecture overlay and abandons in-flight polls so they cannot stamp the next canvas. Server jobs stay queued (reusable when returning). First persist does not kill a live tour.

### Changed

- **Kitty idle** — CosyVoice lecture TTS holds the 300s idle close so the socket does not drop mid-caption.
- **Celery status logs** — Uvicorn logs enqueue / reuse / revoke; workers log start / status / finish / error when manifesto `status` or `stage` actually moves. GET polls and planning heartbeats stay quiet.

### Tests

- `tests/test_kitty_idle.py`, `tests/test_mind_classroom_celery_log.py`
- Frontend: diagram-switch teardown, queue-abandon, unloadCanvas closeModal.

## [5.178.0] - 2026-08-16

> **思维讲堂 runs as a server job (script / slide deck); Kitty narrates captions; 专业程度 persists.**

### Added

- **思维讲堂 jobs** — Signed-in start enqueues canvas-tour or slide-deck work (`POST /api/mind-classroom/jobs`, Celery `mind_classroom.*`, migration `0103` + owner RLS). Launch modal shows queue / planning / generating; reuse same spec+settings; cancel or restart. Guests keep local template scripts.
- **Kitty lecture narrate** — Canvas-owner Kitty TTS speaks captions via WS `narrate` (no command router / one-sentence persist). Overlay waits for PCM `lecture_tts_done`; interrupt stops playback.
- **Mind-map 专业程度** — Picker value is stored on `users.ai_content_level` (migration `0102`) with other personal prefs. Login / `/me` restore it; `PATCH /api/auth/diagram-preferences` saves it. Guests still use localStorage. Classroom jobs send the same audience level.

### Changed

- **ZhiHui planner share** — Lesson planner, outline, and Wan image shell live in `services/mind_classroom/`; ZhiHui re-exports the same helpers so diagram studio and 思维讲堂 share one planner path.
- **Slide lecture** — Dual-pane player maps classroom slides (or legacy ZhiHui generations) onto the existing deck chrome; transcript markdown is persisted with the job.

### Tests

- Classroom prompts (tone / audience / mastery), steps, slide adapter, transcript, temp cleanup, RLS; Kitty narrate; `test_ai_content_level_pref.py`.
- Frontend: launch/queue state, remote steps, lecture runner, classroom→ZhiHui slide map, audience hydrate/persist.

## [5.177.1] - 2026-08-15

> **Canvas multi-LLM regenerate keeps the current session spec (no stale first-finisher).**

### Fixed

- **Canvas multi-LLM regenerate** — First success of the current generate session always paints; persist cannot stamp the previous canvas over a fresh spec; late results from a prior session are dropped. Background Kitty `live_context` cannot reclaim the model slot or recover Redis over a smaller regenerate. Also stop sending 专业程度 twice (prompt + `generation_instructions`), which duplicated `【用户要求】`.

### Tests

- `frontend/tests/llmResultsTeardown.spec.ts` / `kittyLlmModelSync.spec.ts` / `useKittyDesktopRemoteSyncHubPersist.spec.ts` — session-owned paint; no canvas stamp or live_context recover while generating.

## [5.177.0] - 2026-08-15

> **Mind-map 专业程度 drives new-canvas AI; classic autocomplete stays on 学段.**

### Added

- **Copy to clipboard** — Export menu copies the canvas PNG as shown; if clipboard write is blocked, downloads a PNG instead.

### Changed

- **Mind-map toolbar** — 「专业内容」picker extracted to its own control; 「AI生成图示」is a single button (no 学段 caret). Audience copy is native zh/en templates (用语/句子/前提/深度 · Voice/Length/Assume/Depth), not 学段 “生成图示”.
- **New-canvas AI** — Generate, one-sentence create, branch expand, brainstorm, document/image/package summarize, node explain, and Kitty paragraph (mind-map only) send the picker level.
- **Classic thinking-maps** — Autocomplete keeps the 学段 caret and `education_stage` path. Inline rec, relationship labels, concept-map helpers, and thinking-map palette are unchanged.

### Tests

- `frontend/tests/mindMapAudience.spec.ts` — all six constrained levels share the four slots and stay distinct; general unconstrained; payload injection.
- `frontend/tests/copyPngBlobToClipboard.spec.ts` — clipboard write plus download fallback.
- `tests/test_ai_content_level.py` — audience instruction append helper.

## [5.176.0] - 2026-08-12

> **Mind-map v2 classroom lecture and toolbar audience UX.**

### Added

- **思维讲堂** — Mint blob IP entry (bottom-right) opens launch prefs: mastery, **画布语音巡讲** / **幻灯片讲解**, tour scope, lecture tone; canvas-tour runner with captions/TTS controls; slide-deck dual-pane fullscreen player.
- **幻灯片风格** — Presets: 通用幻灯片 / 黑板报风 / 漫画风 / 手绘风 (legacy styles migrate automatically).
- **专业内容（受众难度）** — Toolbar picker (学段/场景) beside AI generate; first-run coach tip; after the first pick the control collapses to icon + level tag.

### Changed

- **思维讲堂入口** — Side-toolbar item removed; only the bottom-right mascot remains.
- **Mind-map top bar** — Structure and theme controls are icon-only (tooltip for labels); audience control sits **before** AI generate.

## [5.175.1] - 2026-08-12

> **Word add-in: production packaging/CSP framing, Voice same-origin WS, Windows install catalogs.**

### Fixed

- **Office task-pane framing** — `/word-addin/*` CSP uses `frame-ancestors *` and omits `X-Frame-Options` so Word can host the shell (DENY/`frame-ancestors 'none'` blocked the runtime).
- **Production AppDomains** — Manifest rewrite keeps origin-only AppDomains (never `…/word-addin` paths); path AppDomains installed but hid the CustomTab.
- **Dev vs production add-in Id** — Repo/Vite sideload uses **MindGraph Dev**; production zip rewrites a distinct Id/labels so `npm start` cannot overwrite Install.cmd registration.
- **Voice CSWSH / mixed content** — Ribbon Voice opens `{Settings baseUrl}/word-addin/.../voice.html` (same Origin as Fun-ASR WS); clearer WS close / mixed-content errors.

### Changed

- **Windows installer** — Closes/relaunches Word; validates AppDomains; registers trusted shared-folder catalog; strips Dev/localhost registry leftovers; prompts to open a document (not blank start screen).
- **Sign-in / prefs** — Hosted shell pins Settings baseUrl; async OfficeRuntime.storage save; SPA handoff waits for prefs hydrate.
- **Docs / README** — Voice same-origin note; production vs Dev install guidance; `Reset-DevSideload.ps1` for clearing stale WEF cache.

### Tests

- Word add-in CSP framing; production packaging Id / AppDomain / display-name assertions.

## [5.175.0] - 2026-08-12

> **Word add-in: dedicated Voice dialog, embed probe, packaging; WS mgat_ auth hardening.**

### Added

- **Embed probe** — `POST /api/auth/embed/probe` validates phone + `mgat_` without minting a Redis handoff code (Settings Sign-in).
- **Word Voice dialog** — Ribbon Voice opens a dedicated Office.js recorder (Start/Pause/Stop/Copy) over `WS /api/ws/voice-notes` with saved `mgat_`; 60m cap, silence auto-stop, started timeout.
- **Word add-in packaging** — Deploy zip helpers (`utils/word_addin_packaging.py`), Windows/Mac install scripts, download API wiring; static `/word-addin/` hosting helpers.
- **Bearer extract leaf** — `services/auth/bearer_token.py` breaks `http_auth_token` ↔ `utils.auth` import cycles.

### Changed

- **Sign-in UX** — Compact Settings dialog; server presets (Test / MG / Local); probe failures distinguish credentials vs network vs unsupported server.
- **MindMate / Voice / Sign-in** — Office dialogs; MindGraph / Showcase / Manual remain task panes.
- **WS mgat_ auth** — `authenticate_websocket_user` accepts `mgat_` + account (header or query); TokenAudit + `?client=` bind for Word Voice.
- **Office embed chrome** — Desktop layout for embed; sidebar collapse defaults; Showcase expand control; Manual iframes Kingsoft guide.

### Fixed

- **False “invalid token” on undeployed probe** — Client no longer maps HTTP 404/405 to credential failure.
- **CSP / shell** — `/word-addin/*` allows Office.js CDN + Manual frame-src; shell JS no-store.

### Tests

- Embed probe/handoff sanitize; WS mgat_ auth; Word add-in packaging; SPA cache-control / security hardening coverage.

## [5.174.0] - 2026-08-12

> **Word add-in embed auth; semantic diagram spec validation; floating toolbar fit-aware placement.**

### Added

- **Word add-in** — Office.js host in [`word-addin/`](word-addin/) (MindGraph / MindMate / Voice / Showcase / Settings task panes); `X-MG-Client: word-addin`.
- **Embed session handoff** — `POST /api/auth/embed/handoff` + `GET /api/auth/embed/complete` exchanges a short-lived Redis code for SPA cookies on the MindGraph origin (no `mgat_` in the query string). Docs: [`docs/architecture/word_addin_embed_auth.md`](docs/architecture/word_addin_embed_auth.md).
- **Semantic spec validation** — Create / patch / PNG export reject invalid agent-authored specs with structured `400 invalid_diagram_spec` (canvas `{nodes, connections}` persist specs pass through).
- **OpenClaw skill 1.4.0** — Slimmer `SKILL.md`: agent-authored semantic `spec` vs `generate_graph`, intent→type table, cookbook; README covers install/env.

### Changed

- **Office embed layout** — `?embed=word-addin` / Office host always treated as desktop (never `/m/*`).
- **CORS** — Allow `localhost` / `127.0.0.1` (any port) for the Word add-in HTTPS shell calling API hosts; private-LAN regex remains debug-only.
- **Mind map fit-after-load** — Always fit-to-full-canvas (drops center-at-default-zoom path).

### Fixed

- **Floating toolbar clipping** — Anchor stays inside the canvas container; flips below when fit-to-screen leaves no room above; measures bar size via `ResizeObserver`.

### Tests

- Embed handoff sanitize/consume; semantic spec validation; floating toolbar placement; mobile detect Office embed.

## [5.173.2] - 2026-08-09

> **Node explain: hide floating toolbar and directional + handles.**

### Fixed

- **Canvas chrome over explain modal** — Gate floating toolbar and four-direction `+` overlays with `nodeExplainOpen` in v2 canvas overlays (same `v-if` pattern as presentation/export); directional-add position clears handles on the same tick when disabled.

## [5.173.1] - 2026-08-09

> **Node explain: hide floating toolbar; sharper 节点含义 prompt.**

### Fixed

- **Floating toolbar over explain modal** — Suppress toolbar while the modal is open (no flash above ElDialog).

### Changed

- **节点含义 prompt** — Asks for a clean, direct definition from the topic’s perspective (glossary-style essence first), not hierarchy/coaching filler.

## [5.173.0] - 2026-08-09

> **Mind map node explain: three parallel facet panels.**

### Changed

- **Node explain UX** — Replaces the Kitty chat follow-up flow with a Swiss-style modal: meaning, cognitive conflict, and inquiry questions stream in parallel; Kitty mascot with rotating speech bubbles while loading.
- **Entry point** — Explain moves from the context menu to the node floating toolbar (lightbulb); Kitty click-wheel / Mobile Kitty re-tap opens the same three-panel flow.
- **API / prompts** — `POST` explain accepts `session_id` + `facet` (`meaning` | `conflict` | `questions`); each facet has a focused prompt (no chat history). Bills as canvas-assist (`mindmap_node_explain`, 4 coins).

### Tests

- Facet normalization and prompt focus; canvas-assist / live-activity registration for `mindmap_node_explain`.

## [5.172.0] - 2026-08-08

> **Voice Notes realtime transcription and canvas AI 学段 preference.**

### Added

- **Voice Notes** — Authenticated Fun-ASR WebSocket bridge (`/api/ws/voice-notes`); draggable FAB + transcript modal; sidebar entry; PCM streaming with pause/resume, 60m cap, 2m silence auto-stop; mindmap bootstrap/save and Document Summary handoff; daily-cap / thinking-coin settle via audio-duration proxy.
- **AI generate 学段** — User `education_stage` column (migration `0101`); split「AI生成图示」toolbar control (primary generate + caret 学段 picker); `PATCH /diagram-preferences`; stage-aware `generation_instructions` for auto-complete (guest session value until login).

### Changed

- **Dify health poll default** — `DIFY_HEALTH_POLL_INTERVAL_SECONDS` default 30s → 120s (documented in `env.example`); stale-health max age follows the new interval.

### Tests

- Voice Notes ASR bridge relay, token estimate, budget errors, Fun-ASR semantic punctuation; WS metrics endpoint mapping.

## [5.171.2] - 2026-08-08

> **ZhiHui diagram progress UX and Wan/planner observability.**

### Added

- **Finer diagram phase labels** — Banner copy follows planning stages (topics / branch N of M / close) and distinguishes waiting for first slides vs drawing (`zhihuiDiagramProgress`).
- **Milestone toasts** — Session-scoped status announcements for planning → drawing → complete / partial / cancelled / failed (no re-toast on hydrate).

### Changed

- **Wan image client logs** — Conversation/batch `log_context`, 30s poll heartbeats, and clear success/timeout/failure lines.
- **Lesson planner / ZhiHui routes** — Phase timing + token usage logs; clearer queued/resume/cancel/delete audit lines.

### Tests

- Wan poll heartbeat + timeout logging; frontend phase label / toast milestone helpers.

## [5.171.1] - 2026-08-08

> **Bump transitive `nanoid` for npm high audit.**

### Fixed

- **`nanoid` < 3.3.17** — Lockfile bump to 3.3.18 (via PostCSS/Vite) for [GHSA-2v37-7h3g-55p8](https://github.com/advisories/GHSA-2v37-7h3g-55p8); `npm audit --audit-level=high` clean.

## [5.171.0] - 2026-08-08

> **ZhiHui teacher narration (Kitty TTS), phased lesson planning, and long-job session hardening.**

### Added

- **Teacher script + Kitty caption** — Deck slides store `teacher_script`; perched Kitty caption auto-plays DashScope TTS via `POST /api/zhihui/teacher-tts` (migrations `0099` / `0100` unique conversation+slide).
- **Phased lesson planner** — Open / per-branch / close planner calls with progress callbacks, truncation-aware JSON repair, and `ZHIHUI_LESSON_PLANNER_MAX_TOKENS` (default 2500 per phase).
- **Celery run lease** — Diagram lesson tasks stop cleanly when cancelled, failed, or superseded (`lesson_lease`).
- **`.mg` decode CLI** — `python scripts/decode_mg_file.py path.mg` documented in `AGENTS.md` / `MG_FILE_FORMAT.md`.
- **Shared LLM→HTTP mapping** — `llm_http_errors` for stable status codes across generation routes.

### Changed

- **Wan prompt shell / deck pipeline** — Richer focus framing and batch persistence aligned with outline order.
- **DebateVerse stream** — Streaming/TTS path extracted to `routers/features/debateverse/stream.py`.
- **Postgres setup** — Pointer to orphan-cluster recovery when 5432 is refused / service masked.

### Fixed

- **Frontend error noise** — Drop ResizeObserver, opaque `Script error`, WeChat bridge, and stale-chunk reports from error collection (client + server).
- **Long LLM jobs holding DB** — DingTalk PNG, web-content, and doc-summary package flows open short RLS sessions instead of keeping a txn across LLM/browser work.
- **Prompt-to-diagram labels** — Coerce null/non-string LLM label fields so PNG/DingTalk generation does not blow up on type mismatches.
- **Generation library claim** — Cover additional claim/skip paths in tests.

### Tests

- Teacher TTS route; ZhiHui lease; frontend noise; LLM HTTP mapping; DingTalk/doc-summary session scoping; DebateVerse stream session; planner phase/outline fixtures.

## [5.170.6] - 2026-08-07

> **Canvas → 智绘 图示生图 handoff, conversation resume, and admin-only ZhiHui access.**

### Added

- **Mind-map export → 图示生图** — Export menu jumps to ZhiHui with the current map selected; resumes the latest diagram conversation when one exists (`GET /api/zhihui/conversations/by-diagram/{id}`), otherwise opens a blank create surface.
- **Handoff deep-link** — Query params `conversationId` / `diagramId` / `diagramTitle`; page hydrates mode, dropdown, slides, and polling; strips query after apply.
- **Admin-only ZhiHui** — `feature.zhihui` / `canAccessZhihui` gated to superadmin; JWT text-to-image requires the same capability.

### Fixed

- **Handoff outside setup** — Event-handler path uses the i18n singleton (not `useLanguage` / `useI18n`) so toolbar click no longer throws.
- **Stale Pinia session** — Immediate `currentId` hydrate + handoff pending guard; remount diagram studio; force-refresh library when the selected map is missing from the dropdown cache.

### Tests

- Handoff query parse (incl. `conversationId`); `canAccessZhihui`; ZhiHui capability + T2I teacher 403.

## [5.170.5] - 2026-08-07

> **Fix AutoComplete UI freeze from save-spec stamping.**

### Fixed

- **AutoComplete freeze** — `getDiagramSpec()` must stay pure; stamping the live canvas into `llm_results` now lives only in `useDiagramSpecForPersist()` (save/flush paths). Template evaluation in `CanvasTopBar` no longer mutates Pinia and cannot re-enter an infinite render loop.
- **Multi-model autosave 409s** — SPA PUTs no longer send `if_updated_at` on routine autosave (queued per-model saves shared one cached timestamp). Server optional CAS remains for future callers.

### Changed

- **Diagram spec helpers** — Split pure `useDiagramSpecForSave` vs persist `useDiagramSpecForPersist`; slot-full modal snapshots pending spec once on open.

### Tests

- Pure-vs-persist stamp regression; detail-cache PUT no longer expects client CAS headers.

## [5.170.4] - 2026-08-07

> **Library save durability + ZhiHui lesson decks that follow the mind-map order.**

### Fixed

- **Diagram reopen lost edits** — Canvas library open force-fetches (`getDiagram({ force })`); detail cache is write-through / `updated_at`-guarded so stale SPA snapshots cannot hydrate and autosave over a good PUT.
- **Library switch wipe** — Dirty switch uses leave-style flush and fails closed (except live collab, which owns durability via `live_spec`); manual save bypasses suppress and surfaces skipped guards.
- **Autosave `llm_results`** — Live canvas is stamped into the current model slot before persist so multi-model reopen keeps user deletes/edits.
- **Backend cache poison** — Title-only PUT never rewrites `spec` from Redis; Redis write-fail deletes the diagram key; collab flush/stop invalidate per-diagram cache; soft CAS via `if_updated_at`.
- **Mobile canvas** — Watches `?diagramId=` so in-app library switches flush/load like desktop.

### Changed

- **ZhiHui lesson planner** — Outline is the sole knowledge skeleton (clockwise branch order, focus fields); stronger anti-reorder / anti-invent prompts; hookier topic open + analogy-heavy branch intros.
- **ZhiHui deck pipeline** — Normalize/reorder develop batches to outline after plan; richer batch logging; deck UI shows batch bar + planned slide progress.
- **Outline helpers** — Clockwise branch ordering coverage expanded for lesson decks and focus hints.

### Tests

- Detail-cache force/write-through/409; save flush feedback; diagram cache durability (CAS helpers + Redis invalidate); ZhiHui outline/order/batch fixtures (incl. Sam’s Club L1).

## [5.170.3] - 2026-08-07

> **ZhiHui: idle 图示生图 deck no longer says “generating”.**

### Fixed

- **Empty deck copy** — Blank 图示生图 (no map / no job) shows “选择思维导图后，点击生成” instead of “课件生成中，请稍候…”.

## [5.170.2] - 2026-08-07

> **ZhiHui: blank 图示生图 create, bundled landing seeds, clockwise outline + focus polish.**

### Fixed

- **图示生图 blank create** — Segmented control re-click opens a fresh create surface (clear map selection, remount studio); sticky “generating” chrome cleared on hydrate.
- **Image studio race** — Leaving mid-generate no longer `selectItem`s back into the new conversation after unmount.
- **Delete open conversation** — Returns to landing with mode preserved (`startLanding('preserve')`).

### Changed

- **图片生成 landing gallery** — Always shows bundled `frontend/public/zhihui/seeds/*.jpg` (no recent covers, no COS redirect).
- **Outline order** — Mind-map branches ordered clockwise for lesson decks; planner prompted to keep that order.
- **Canvas focus** — Child-detail slides prefer `focus_child`; browsing dims non-focused nodes.

### Removed

- `GET /api/zhihui/seeds`, seed key helpers, and `scripts/db/seed_zhihui_landing_images.py` (gallery is frontend-static only).

### Tests

- Clockwise outline cases; focus hint coverage for child slides.

## [5.170.1] - 2026-08-07

> **ZhiHui polish: landing/conversation UX, canvas focus sync, lesson prompts, stale-job hardening.**

### Fixed

- **Stale / incomplete jobs** — Worker stops on `cancelled`/`failed`/`partial`; incomplete Wan batches mark `partial` (not `complete`); stale sweep revokes Celery task ids; `partial` resumes via `claim_for_run`.
- **Studio navigation** — Sidebar 智绘 always opens landing; mode switch image↔diagram no longer sticks; history select syncs dropdown + canvas; optimistic image/diagram mode; canvas load race guard.
- **Image thrash** — Stable same-origin asset URLs for admin poll; stabilize only rotating `sig`/`exp`; deck retry preserves query params.
- **Seeds gate** — `/api/zhihui/seeds` requires `CAP_FEATURE_ZHIHUI`.

### Changed

- **Lesson planner prompts** — Topic overview → branch intro → child detail + 认知冲突 highlights for critical thinking; richer Wan shell fields (`learning_point`, `manifestation`, `think_prompt`).
- **Focus restore** — Flatten `lesson_plan.batches[].frames` for canvas pan fallback; first slide fits whole map.

### Removed

- Temporary COS seed copy script; unused `zhihui:focus_slide` bus event / dead helpers.

### Tests

- Planner pedagogy + Wan conflict shell; focus hint flatten; stabilize signed vs stable URLs.

## [5.170.0] - 2026-08-07

> **ZhiHui (智绘): Qwen image studio + Wan mind-map → lesson PPT decks.**

### Added

- **ZhiHui studio (admin)** — `/zhihui` image mode (Qwen) and 图示生图 diagram-lesson decks from mind maps; sidebar history, live poll + event bus, resume on failed/partial, mode lock while busy (`ZhiHuiPage.vue`, `ZhiHuiStudio.vue`, `zhihuiHistory.ts`).
- **Diagram lesson pipeline** — Celery `zhihui.run_diagram_lesson`: planner (`qwen3.7-plus`) → Wan `wan2.7-image` async 组图 → COS; concurrent cap, stale sweeper, cancel/revoke, resume (`services/zhihui/`, `tasks/zhihui_lesson_tasks.py`).
- **API** — `POST /api/zhihui/diagram-lesson`, conversation list/detail/delete/resume, signed assets, landing seeds; image generations wrapped in conversations (`routers/features/zhihui/`, `routers/api/image_generation.py`).
- **Schema & config** — Migrations `0097`/`0098` (`zhihui_generations` / `zhihui_conversations`); `FEATURE_ZHIHUI`, `COS_ZHIHUI_*`, `ZHIHUI_LESSON_PLANNER_MODEL`, `CAP_FEATURE_ZHIHUI` panel gate; admin activity / token counters for ZhiHui.

### Tests

- **Backend** — Wan helpers, outline/shell/planner parse, T2I generate, ZhiHui keys.
- **Frontend** — ZhiHui modes; admin activity summary / feature-flag coverage for ZhiHui.

## [5.169.6] - 2026-08-06

> **Kitty WS auth close codes + ownership serialization; stop speculative refresh → 429 / forced re-login.**

### Fixed

- **Kitty WS auth signaling** — Reject paths `accept()` then `close(4001|4003|4400|4403)` so browsers receive real close codes instead of HTTP 403 → opaque 1006 (`reject_kitty_websocket` in `lifecycle.py`).
- **Kitty refresh only on 4001** — Client classifies close codes; cookie refresh runs only for `auth_failed`. Access/scope denials hard-stop without login modal; transport failures backoff-reconnect without rotating cookies (`kittyConnectFailure.ts`, `kittyWsAuthReconnect.ts`, `useKittyAgent.ts`).
- **Canvas owner scope churn** — Serialize stop→start on scope change; ignore stale `voice:ws_closed` (wrong scope / 1001 / clean / policy codes); skip Redis cleanup when old scope equals next SoT; auth-store 401 paths use epoch helper; 429 ≠ logout (`useKittyCanvasOwnerAgent.ts`, `useMobileKittyPageLifecycle.ts`, `CanvasPage.vue`, `auth.ts`, `apiClient.ts`).
- **HTTP 401 stampede grace** — Keep 20s success grace for apiClient/auth peers only (not Kitty speculative refresh).

### Tests

- **Backend** — Accept-then-close reject helper codes (`test_kitty_ws_reject_close.py`).
- **Frontend** — Close-code helpers; refresh only on `auth_failed`; budget / 429 / post-refresh policy-deny (`kittyConnectFailure.spec.ts`, `kittyWsAuthReconnect.spec.ts`, `sessionRefresh.spec.ts`).

## [5.169.5] - 2026-08-06

> **Auth refresh 401 stampede coordination (Kitty + apiClient); autoWrap inline edit grows with draft / IME-safe.**

### Fixed

- **Auth refresh 401 stampede (Kitty + apiClient)** — Sequential `/api/auth/refresh` after cookie rotation deleted the new Redis access session while in-flight `desktop_focus` / Kitty WS still carried the old cookie (401 + WS 403 storm). Root fix: shared refresh **epoch** in `sessionRefresh.ts` (`ensureFreshSessionAfterAuthFailure`) so peers retry without re-rotating; wire `apiClient` 401 paths and slim Kitty recovery; keep single-flight canvas-owner connect, aborted/supersede skip, and focus idle await (`sessionRefresh.ts`, `apiClient.ts`, `kittyWsAuthReconnect.ts`, `useKittyCanvasOwnerAgent.ts`, `useKittyDesktopFocus.ts`, `MobileKittyPage.vue`).
- **Inline edit autoWrap grow / IME** — autoWrap editors start as a centered single-line `<input>`, grow width with the live draft (including IME composition) up to `maxWidth`, then promote to `<textarea>` without swapping mid-composition (`InlineEditableText.vue`).

### Tests

- **Frontend** — Session refresh coalesce / epoch skip / await-idle; Kitty WS auth reconnect aborted vs failed; canvas-owner ownership coverage (`sessionRefresh.spec.ts`, `kittyWsAuthReconnect.spec.ts`, `useKittyCanvasOwnerAgentOwnership.spec.ts`).

## [5.169.4] - 2026-08-06

> **Restore Material-20 for thinking maps / classic mind map; isolate classic vs v2 canvas style buckets.**

### Fixed

- **Thinking-map / classic branch palette** — Default `MINDMAP_BRANCH_COLORS` is Material-20 again (baseline `7c7df0d3`); Radix-12 is `V2_MINDMAP_BRANCH_COLORS` only via `getMindmapBranchColor(i, 'v2')`. Bubble, flow, double-bubble, tree, brace, circle, multi-flow, and classic mind map share Material fills/borders (`mindmapColors.ts`, `mindMapLegacyColors.ts`, `useBranchMoveDrag.ts`).
- **Classic vs v2 mind-map style isolation** — Persist `diagram_style` in `_mindmap_canvas.v2`; clear/restore live `_mindmap_theme` and `_mindmap_diagram_style` on mode switch like theme. Classic apply/reload/spec hydrate never seeds v2 theme defaults; `sanitizeLegacyNodeStyle` also strips `fontFamily` / `borderWidth` (`mindMapCanvasModeSwitch.ts`, `mindMapStylePreservation.ts`, `mindMapOps.ts`, `specIO.ts`, `diagram.ts`).
- **Template label contrast** — Seeded defaults (主题, 联想1, …) no longer render as muted placeholders; only whitespace and editable “Enter text” / “输入文本” stay muted (`diagramDefaultLabels.ts`).
- **Auth locale** — Shorten Chinese platform quick-guide label to “快速指南” (`zh/auth.ts`).

### Tests

- **Frontend** — Palette Material default vs Radix-on-v2; separation sanitize / empty-bucket v2→legacy / diagram_style clear-restore; placeholder mute vs template contrast (`mindMapColorPalettes.spec.ts`, `mindMapSeparation.spec.ts`, `diagramDefaultLabels.spec.ts`).

## [5.169.3] - 2026-08-06

> **Deduplicate auth/bootstrap and diagram-list fetches (in-flight coalesce + guarded TTL).**

### Fixed

- **Auth / bootstrap duplicate GETs** — Stamp profile refresh time on successful `/me`; session-monitor immediate kick uses throttled profile refresh (keeps `session-status`); drop MindMate/mobile mount `checkAuth(true)`; admin capabilities use a 60s cache with router `{ force: true }` on admin entry while AdminPage/sidebar reuse TTL (`auth.ts`, `MindMatePage.vue`, `MindmatePanel.vue`, `useAdminAccess.ts`, `router/index.ts`).
- **Feature flags race** — Concurrent `fetchFlags()` share one in-flight request; `markStale()` bumps an epoch so in-flight completions cannot re-mark a stale cache as fresh, with one follow-up fetch when invalidated (`featureFlags.ts`).
- **Diagram list fan-out** — `fetchDiagrams()` coalesces in-flight calls, applies a 15s TTL keyed by user id (clears across account switch), and supports `{ force: true }` for pickers/modals/kitty follow; remove redundant CanvasTopBar mount fetch (`savedDiagrams.ts`, `CanvasTopBar.vue`).
- **Playwright COS version mismatch** — Block Chromium install when pip `playwright` ≠ COS meta version; Check/Update print package vs COS and a clear hint (`package_newer_than_cos` / `cos_newer_than_package`) instead of opaque `install_failed` (`playwright_cos_sync.py`, `update_stack_from_cos.py`).

### Tests

- **Frontend** — Feature-flags coalesce/TTL/`markStale` mid-flight; auth no double-`/me` after monitor start + capabilities TTL/force; diagram list coalesce/TTL/force/user-switch/force-after-failed-share.
- **Backend** — Playwright package↔COS mismatch plan/install errors; stack COS check exit code for mismatch.

## [5.169.2] - 2026-08-06

> **Session-owned mind-map canvas mode for Showcase/export; sole new-canvas blank-load owners with dedupe.**

### Fixed

- **Showcase / export mind-map canvas mode** — Each `DiagramSession` owns `mindMapCanvasMode`; Showcase and headless VueFlow screenshots use gallery policy (v2 when the feature flag is on, Classic when off) instead of the viewer UI preference. Theme, mind-map ops, style reload, and vector export read the session mode (`mindMapCanvasMode.ts`, `createDiagramSession.ts`, `vueflow_screenshot.py`).
- **New-canvas blank load ownership** — `?type=` without `diagramId` loads only via route bootstrap, in-place type-query watch, switch/reset, and Kitty helpers (`newCanvasBootstrap.ts`, `useNewCanvasTypeQueryBootstrap.ts`). `selectedChartType` watch syncs type only (no template load / double paint). Same-turn dedupe avoids remount/helper double measure-batch; Priority 3 keeps landing-generated Pinia specs when `data.type` matches.
- **Layout recalc across sessions** — `diagram:layout_recalc_bump` increments every mounted diagram session (and pending bumps apply on late mount) so Showcase previews are not skipped / do not only poke the editor store (`diagramLayoutRecalcBootstrap.ts`).

### Tests

- **Frontend** — New-canvas bootstrap ownership/dedupe/Priority 3; mind-map canvas visuals session mode; Kitty mobile library select; diagram session isolation coverage.

## [5.169.1] - 2026-08-06

> **Injectable DiagramSession: Showcase vector preview isolated from the editor Pinia store.**

### Fixed

- **Showcase preview vs editor isolation** — Live Showcase vector previews use an injectable readonly `DiagramSession` (private VueFlow id + view bus, quiet emits) instead of the editor Pinia store; removes backup/restore and reader-lock hijacks. Opening `?type=` without `diagramId` always blanks via `clearActiveDiagram` + `loadDefaultTemplate` so leftover preview content cannot appear as a new mind map (desktop + mobile). Preview UX: session-scoped VueFlow, context-menu/inline-edit/drag blocked when `isReadonly`. Quiet sessions gate slice `emitCtxEvent` / history-restore and node-delete concept-map picker clears, and route view events through `ctx.viewBus`. Also: drop dead showcase reader-lock API; `ExportRenderPage` provides the editor session; editor keyboard/canvas helpers bind VueFlow by session id (`createDiagramSession.ts`, `DiagramSessionProvider.vue`, `ShowcaseDiagramPreview.vue`, `CanvasPage.vue`, `MobileCanvasPage.vue`).

### Tests

- **Frontend** — Diagram session isolation (preview vs editor Pinia, dual viewBus, new-canvas mindmap-after-showcase, quiet `diagram:loaded`).

## [5.169.0] - 2026-08-06

> **Showcase media-status phases (cover vs preview); cover-job manifesto under system RLS; mind-map Enter/reload style SoT; frontend + Python dependency bump.**

### Added

- **Showcase media-status phases** — Teaching-design pipeline reports `generating_cover`, `preview_failed`, and `cover_failed` (in addition to convert/preview/cover-ready); admin chips and locales updated (`media_status.py`, `showcaseMediaStatus.ts`).

### Fixed

- **Cover-job manifesto under RLS** — Celery cover workers write job stages/fail/success via system bootstrap so manifesto persistence does not depend on author-scoped post SELECT (`generate.py`, `job_manifest.py`).
- **Mind-map sibling style identity** — Single SoT for in-place Enter insert and path-keyed reload: mint `_node_styles`, match nearest same-parent sibling colors/typography, keep rainbow/theme rules aligned (`mindMapStylePreservation.ts`, `mindMapSiblingInsert.ts`, `mindMapOps.ts`).

### Changed

- **Frontend deps** — `mathlive` 0.110 (XSS fix for `\text{}`/`\mbox{}`); `@vueuse/core` 14.4 (drop local Rolldown PURE patch); `pinia` 4 + `@vue/devtools-api`; `pdfjs-dist` 6.2.108 with re-vendored `public/pdf.worker.min.mjs` and preview render API updates (`canvas` + `cleanup`); `katex` 0.18; `markdown-it` 15 (bundled types, keep fuzzy linkify); `jsdom` 30; Element Plus table slot rows cast to concrete types (Vue SFC templates cannot host `ElTable<Row>` generics); plus routine Vue/Vite/ESLint/fontsource minors. Patch sweep: `dompurify` 3.4.13, `jspdf`/`fflate`/`html-to-image`/`undici`/`@vue-flow/core`/`@element-plus/icons-vue`/`unplugin-vue-components`, chrome-extension `vitest` 4.1.10. **TypeScript stays on 6.x** — TS 7 is stable but lacks the public compiler API Vue tooling (`vue-tsc` / typescript-eslint) needs until 7.1.
- **Python deps (`requirements.txt`)** — Raise PyPI floors (FastAPI/uvicorn/LangChain/LangGraph/openai/playwright/redis/tooling, etc.); `datasets` ≥5.0.1. Keep `websockets` on 15.x (`<16`) until `langgraph-sdk` allows 17+; keep `pydantic` `<3` and `qdrant-client` `<1.19` (paired with server 1.18.x).

### Tests

- **Backend** — Media-status phase/fail derivation; cover-job manifesto system-RLS paths.
- **Frontend** — Showcase media-status resolve/chip/tooltip; mind-map reload style identity, sibling insert in-place style, undo/redo coverage.

## [5.168.2] - 2026-08-05

> **Showcase approve / engagement under RLS; recommend-only experts stay out of admin panel; mind-map outline clockwise order; SelectiveGZip Starlette compat.**

### Fixed

- **Showcase approve + community engagement under RLS** — Credit case rewards as the author (owner/system coin policies); bump community like/comment counters via system sessions; widen community write policies for moderation cascades (rev `0095`/`0096`, `case_earn.py`, `counters.py`).
- **Recommend-only Showcase grants** — Recommend is a gallery action only; experts with recommend-only perms no longer get admin panel access or moderation subtabs (`staff_permissions.py`, `AdminShowcaseTab.vue`, `stats.py`).
- **Mind-map outline / presentation order** — Topic-level children follow clockwise reading order (right top→bottom, then left bottom→top), matching layout `mindMapBranchesClockwiseOrder` (`mindMapOutlineTree.ts`).
- **SelectiveGZipMiddleware** — Use public `GZipMiddleware` API so gzip works across Starlette versions that disagree on `GZipResponder.thread_minimum_size`.

### Changed

- **Mind map New canvas default** — One-time localStorage migration puts all browsers on New canvas; Classic is opt-in in Language settings. Feature-flag-off Classic is runtime-only so it cannot sticky-overwrite the New default (`ui.ts`, `featureFlags.ts`, `LanguageSettingsModal.vue`).
- **Docs** — README version badge, Showcase / Maite routes and links, thinking-coins daily bucket note, mind-map v2 / presentation spotlight wording.

### Tests

- **Backend** — Showcase staff→panel capability mapping; community panel / thinking-coins system RLS migrations; public static gzip middleware.
- **Frontend** — Outline tree matches layout clockwise order after `loadMindMapSpec`; slides deep traversal left bottom→top; mind-map v2-default migration + persist-flag coverage; separation fixture includes selection/preserve/bulk refs for reload paths.

## [5.168.1] - 2026-08-05

> **MindMate / generate_dingtalk library-save notices use end-user wording; strip stale preview-only lines after claim.**

### Fixed

- **MindMate diagram preview notices** — `generate_dingtalk` embeds MindMate / guest / DingTalk skip wording instead of ops `X-MG-Dify-User` text; after library claim, web MindMate hides the stale preview-only line (`library_save_user_notices.py`, `mindmateDiagramMeta.ts`).

### Changed

- **Docs** — Clarify `generate_dingtalk` identity order and Dify header ops note (`identity_unification.md`).

### Tests

- **Backend** — Audience mapping + guest/MindMate skip notices (`test_library_save_user_notices.py`, `test_generate_dingtalk_identity.py`).
- **Frontend** — `stripLibrarySaveSkipNotices` after claim recovery (`mindmateDiagramMeta.spec.ts`).

## [5.168.0] - 2026-08-05

> **Thinking-coin daily login bucket (Beijing midnight expire); Showcase cover job manifesto + admin refresh; diagram AI copy structure outline; field-options community read + admin panel RLS pin.**

### Added

- **Daily login coins (no rollover)** — Check-in credits go to `thinking_coin_wallets.daily_balance`; unused daily coins expire at Beijing midnight (lazy on read/credit/debit); spend daily bucket first then persistent balance (`wallet_service.py`, rev `0093`).
- **Showcase cover job manifesto** — Cold Postgres `case_square_cover_jobs` (queued/running/succeeded/failed + attempts); admin media status without per-row COS HEAD; Celery retries with exponential backoff (`job_manifest.py`, rev `0092`).
- **Admin cover refresh** — `POST …/admin/showcase/posts/{id}/refresh-cover` force-requeues teaching-design cover/PDF; Refresh status button on moderation + published lists.
- **Diagram structure outline for AI copy** — Hierarchical outline from library/native specs (and image OCR prompt) so publish AI fills intro/classroom use from real diagram structure (`diagram_structure_outline.py`, `routes_ai.py`).
- **Admin panel RLS pin** — `resolve_admin_scope_rls` builds AdminScope and pins panel `request.state.rls_context` before the request DB session opens (`dependencies.py`).
- **Platform quick start guide** — Account menu link to the platform guide (`AppSidebarAccountFooter.vue`).

### Fixed

- **Showcase field options meta** — Authenticated community SELECT on `case_square_field_options` so publish/filter meta is not empty (rev `0094`; greenfield policy also corrected in rev `0085`).

### Changed

- **Showcase publish AI / gallery** — Stronger diagram-copy orchestration (image / library / `.mg`); case vs template gallery hints; OCR accepts custom prompts for diagram vision.
- **Cover pipeline** — Enqueue/generate/tasks honor manifesto cold status; backfill skips cold-`succeeded`; media_status prefers job row.
- **Locale** — Daily-expire / remaining balance, admin refresh-status, platform guide, showcase publish hints across locale bundles.
- **Docs** — Thinking-coins daily bucket; admin-scope RLS Q1 done; Showcase README manifesto/retry/refresh.
- **CrowdSec** — Refresh committed blocklist baseline.

### Tests

- **Backend** — Cover job manifesto, daily expire, field-options wiring, admin-scope RLS resolve, diagram AI copy / media status / enqueue / covers updates.
- **Frontend** — Showcase diagram action + copy AI specs; thinking-coin sync payload field.

## [5.167.0] - 2026-08-05

> **Showcase moderation media pipeline status; fix Showcase .mg reader fit (init + fullscreen).**

### Added

- **Showcase media status** — API `media_status` on formatted posts (upload → Office PDF convert → preview/cover ready / failed); pending-queue column with status chips in admin moderation (`media_status.py`, `showcaseMediaStatus.ts`, `AdminShowcaseModeration.vue`).

### Fixed

- **Showcase diagram reader fit** — Mind-map / locked reader always zoom-fits (including v1); allow auto fit-on-init under showcase reader lock; re-fit after fullscreen enter (`useDiagramCanvasFit.ts`, `useDiagramCanvasEventBus.ts`, `ShowcaseDiagramPreview.vue`).

### Changed

- **Locale** — Admin showcase media-status keys across locale bundles.

### Tests

- **Backend** — Media status derivation + cover_fail mapping (`test_showcase_media_status.py`).
- **Frontend** — Media status resolve/label/chip helpers (`showcaseMediaStatus.spec.ts`).

## [5.166.0] - 2026-08-05

> **Shape-aware mind-map gaps + e-blackboard chrome; presentation spotlight sizes; Showcase Office→pdf.js with COS CJK fonts and cover SSE replay.**

### Added

- **Adaptive mind-map gaps (v2)** — Sibling/branch vertical gaps follow adjacent node shapes (underline / mixed / box) instead of fixed legacy constants (`mindMapAdaptiveGaps.ts`, `mindMapSideStacking.ts`, `mindMapV2Layout.ts`).
- **E-blackboard optimization** — Settings toggle enlarges mind-map +/- and collapse controls for classroom boards (`mindMapEBlackboard.ts`, `LanguageSettingsModal.vue`, `ui.ts`).
- **Presentation spotlight sizes** — Small / medium / large spotlight presets on the presentation rail (`presentationSpotlight.ts`, `MindMapPresentationSideToolbar.vue`).
- **Office preview CJK fonts (COS)** — Optional Windows font pack (宋体/楷体/仿宋/黑体/微软雅黑) under `sync/fonts/office-preview/`; cover workers warm/pull into `data/office_preview_fonts/` (`office_preview_fonts_cos.py`, `publish_office_preview_fonts_to_cos.py`, Celery worker init).

### Changed

- **Mind-map layout** — Stronger side stacking, outline-tree mirror, shape-aware measurements/typography, left-only rebalance identity, and chrome positioning for collapse/directional-add overlays.
- **Showcase teaching docs** — Detail reader is **pdf.js only** (drop browser `docx-preview`); LibreOffice export uses lossless PDF filters; HiDPI natural-width pages; remove client HTML thumbnail capture path.
- **Cover SSE** — Replay last cover event for late subscribers; stream/backfill hardening (`covers/events.py`, `covers/stream.py`, `routes_feed.py`).
- **Locale** — Canvas/common keys for spotlight sizes + e-blackboard; showcase copy refresh (en/zh); fa thinkingCoins refresh.

### Fixed

- **Mobile canvas touch / Vue Flow UI** — Touch and chrome interaction coverage for presentation and overlays.
- **Mind-map side identity** — Load/preserve sides and sibling Y anchors under adaptive stacking.

### Tests

- **Frontend** — Adaptive gaps, e-blackboard scale, outline tree, shape-aware estimates, left-only rebalance, PG layout audits, mobile touch / Vue Flow UI.
- **Backend** — Office preview fonts COS, cover SSE replay, Office PDF export (`test_office_preview_fonts_cos.py`, `test_showcase_cover_sse_replay.py`, `test_showcase_office_pdf_export.py`).

## [5.165.1] - 2026-08-04

> **Harden DEBUG logs against Cookie/COS secret dumps; stop Showcase Office cover enqueue storm.**

### Fixed

- **Secret logging** — Pin `uvicorn.error` to INFO so WebSocket handshake DEBUG no longer dumps `Cookie`/JWT; set `qcloud_cos*` / `urllib3` to WARNING unless `COS_DEBUG=1` or `HTTP_DEBUG=1` (`logging_config.py`).
- **Office cover enqueue storm** — Persist `preview_path` with `flag_modified`; Redis NX dedupe on Celery enqueue; stop detail-modal `loadPost` loop on thumb-only `cover_ready`; keep existing cover SSE when already pending (`generate.py`, `enqueue.py`, `locks.py`, `ShowcaseDetailModal.vue`, `showcase.ts`).
- **COS client churn** — Reuse one `CosS3Client` per process instead of reconstructing on every asset request (`tencent_cos_client.py`).

### Changed

- **Locale** — Refresh fa showcase message bundle.
- **CrowdSec** — Refresh committed blocklist baseline.

### Tests

- **Backend** — Enqueue dedupe unit coverage (`test_showcase_office_preview_enqueue.py`).

## [5.165.0] - 2026-08-04

> **Showcase diagram AI copy + 15-item gallery publish; MindMate case attachments; COS asset proxy for pdf.js; Office preview.pdf backfill.**

### Added

- **Diagram AI copy (publish step 2)** — Extract node text from canvas / personal library / `.mg` / gallery specs, then draft `description` + `classroom_application` via `qwen3.7-flash` (`POST /api/showcase/ai/diagram-copy` + SSE; `diagram_ai_copy.py`, `usePublishShowcaseAiOrchestration.ts`, `generateShowcaseDiagramCopy.ts`, `useShowcaseDiagramCopyAi.ts`).
- **MindMate Showcase attachments** — Detail “Ask MindMate” builds a Dify-uploadable file from teaching doc, LibreOffice `preview.pdf`, or synthesized markdown brief; `/mindmate?showcase_post=` deep-link auto-attaches (`buildShowcaseMindMateAttachment.ts`, `MindmatePanel.vue`, `MindMatePage.vue`).
- **Gallery image prep pipeline** — Abortable pick pipeline resizes to 1600px long edge, strips EXIF/GPS, preserves PNG/JPEG/WebP (`processShowcaseGalleryImagePick.ts`, `resizeImageFileForShowcaseGallery.ts`).
- **Showcase asset proxy fetch** — `fetchShowcaseAsset()` appends `proxy=1` so credentialed pdf.js/docx readers get same-origin bytes on COS (`fetchShowcaseAsset.ts`, `routes_feed.py`).
- **Office preview backfill** — On post read, enqueue LibreOffice cover regen when `.doc`/`.docx`/`.pptx` lacks `preview_path` (`covers/enqueue.py`).

### Changed

- **Diagram-case / template gallery** — Multi-item gallery (up to **15** images + saved diagrams) for both case types; personal-library picker with folder labels; Swiss remove-pill UI; publish validates gallery diagram specs before submit (`PublishShowcaseModal.vue`, `ShowcaseHistoryDiagramPicker.vue`, `showcaseGallery.ts`).
- **Teaching-design AI copy** — Teaching reflection stays teacher-authored; AI fills intro + design highlights only (~400 字); diagram cases get separate AI orchestration (`usePublishShowcaseModal.ts`, `services/showcase/README.md`).
- **Showcase detail previews** — Multi-diagram carousel resolves specs from gallery items / `.mg` URLs via proxied fetch; teaching docs use LO `preview.pdf` for `.doc`/`.docx` full-page pdf.js when available (`ShowcaseDiagramPreview.vue`, `ShowcaseTeachingDocPreview.vue`).
- **Diagram actions** — Import/open resolves gallery-embedded diagram specs and defers canvas `setActiveDiagram` until preview unmount (`useShowcaseDiagramAction.ts`, `ShowcaseDetailModal.vue`).
- **MindMate uploads** — Composer stays image-only; programmatic Showcase handoffs may upload documents via existing Dify extension list (`useMindMate.ts`).
- **PDF worker** — Bump pinned worker to **pdfjs-dist@4.10.38**; version check validates `pdf.worker.min.mjs` against `package.json` (`pdf.worker.version`, `check-pdf-worker-version.ts`).
- **Showcase spec limits** — Diagram/gallery JSON cap raised to **2 MB**; gallery path resolution uses COS `head_object` not just local disk.
- **Locale bundles** — Showcase keys for diagram AI, gallery, personal library, doc preview (en/zh/zh-tw); broad **ar** refresh; **fa** partial refresh; **tr/admin** refresh.

### Fixed

- **Gallery JSONB persistence** — Deep-copy + `flag_modified` on nested gallery slot updates so COS complete/approve no longer leaves `pending` forever (`uploads/pipeline.py`, `routes_posts.py`).
- **COS pdf.js CORS** — Showcase PDF/doc previews no longer fail when assets API returns 302 to presigned COS URLs.
- **Legacy Office posts** — `.doc`/`.docx` with missing inline preview enqueue server-side LO→PDF instead of a permanent dead-end.
- **Gallery upload gate** — Diagram-template posts can use the dedicated gallery upload endpoint (was diagram-case only).

### Tests

- **Frontend** — MindMate attachment builder, asset proxy fetch, gallery resize/pick, gallery upload, carousel slides, diagram copy AI, diagram actions (8 new Vitest specs).
- **Backend** — Diagram AI copy extraction/normalization, gallery JSONB deep-copy, office preview enqueue, upload gallery spec, cover stream/proxy behavior (`test_showcase_diagram_ai_copy.py`, `test_showcase_upload_gallery_spec.py`, `test_showcase_office_preview_enqueue.py`, plus lifecycle/covers/COS extensions).

## [5.164.0] - 2026-08-03

> **Mind-map vector SVG/PDF export (model→SVG + svg2pdf); shared canvas/export text wrap; COS-backed CJK fonts; topic stem flush fix.**

### Added

- **Mind-map vector export** — Mind maps build diagram SVG from the layout model (nodes/edges/text), then PDF via `svg2pdf.js`; DOCX embeds a high-DPI raster of that SVG. PNG menu stays html-to-image (`diagramMindMapVector*.ts`, `useDiagramExport.ts`, `svg2pdf.js`).
- **Shared text-wrap contract** — Canvas topic/branch hosts and vector export share column widths and break rules (`mindMapTextWrap.ts`, mind-map node components).
- **Export fonts API** — Same-origin `GET /api/mindmap_export_fonts/{filename}` serves Noto Sans SC TrueType from local cache or Tencent COS (`mindmap_export_fonts.py`, `mindmap_export_fonts_cos.py`).
- **Font vendor/publish tooling** — `npm run vendor:mindmap-export-fonts` (WOFF2→TTF) and `scripts/db/publish_mindmap_export_fonts_to_cos.py` for shared COS mirror (`frontend/public/fonts/README.md`, `env.example`).

### Changed

- **Thinking Coins subscription UI** — Temporarily hide personal plan tab; school edition only (`SHOW_PERSONAL_SUBSCRIPTION_TAB`, Thinking Coins modal/section).
- **Topic connector geometry** — Layout column width (`resolveMindMapTopicLayoutWidth`) stays estimate-floored; stem endpoints use painted width (`resolveMindMapTopicStemWidth`) so topic→L1 edges meet the blue box edge (`mindMapGeometry.ts`, `MindMapOrthogonalEdge.vue`).
- **Locale sync** — Refresh ru message bundles (knowledge, maite, mindmate, notification, showcase, sidebar, thinkingCoins, workshop).

### Fixed

- **Topic→L1 stem gap** — Right-side connector no longer stops short when layout width is inflated above the painted topic box.

### Tests

- **Frontend** — Vector export unit/E2E audit specs; text-wrap unit coverage; underline-anchor coverage for stem width (`diagramMindMapVectorExport.spec.ts`, `diagramMindMapVectorE2E.audit.spec.ts`, `mindMapTextWrap.spec.ts`, `mindMapUnderlineAnchorY.spec.ts`).
- **Backend** — COS font cache/status helpers (`tests/test_mindmap_export_fonts_cos.py`); MCP unit tests typed for basedpyright (`test_mcp_mindgraph_tool.py`, `test_mcp_session_lifespan.py`).

## [5.163.0] - 2026-08-03

> **MCP Streamable HTTP production hardening; DEBUG `/assets` mount for Playwright export.**

### Added

- **MCP HTTP ops** — Secure Streamable HTTP at `/api/mcp`: host `session_manager` lifespan, trailing-slash rewrite, `mgat_` + `X-MG-Account` auth before protocol, per-user rate limit, feature-flag gate, loopback-only internal URL, `mcp` client label ([`services/mcp/`](services/mcp/), [`docs/operations/mcp_http.md`](docs/operations/mcp_http.md)).

### Changed

- **Feature gate** — `/api/mcp` gated by `FEATURE_MCP_HTTP` with always-on mount (hot off without restart) ([`feature_gate.py`](services/infrastructure/http/feature_gate.py), [`register.py`](routers/register.py)).
- **SPA dist static** — Mount `/assets` (and `/gallery`) from `frontend/dist` even in DEBUG so Playwright `/export-render` can load hashed CSS/JS ([`spa_handler.py`](services/infrastructure/utils/spa_handler.py)).
- **Deploy notes** — MCP proxy timeout ≥180s and env comments ([`production_security_deploy.md`](docs/architecture/production_security_deploy.md), [`env.example`](env.example)).

### Fixed

- **MCP mount lifespan** — Enter `session_manager.run()` from the host FastAPI lifespan (fixes `Task group is not initialized` when mounted).
- **MCP POST without slash** — Rewrite `/api/mcp` → `/api/mcp/` so POST is not 405.
- **Local DingTalk/MCP PNG in DEBUG** — Stale “missing Playwright” symptom was unmounted `/assets` returning JSON 404s.

### Tests

- **Backend** — MCP auth/lifespan/tool URL guards, feature-gate `/api/mcp`, SPA assets mount in DEBUG (`tests/test_mcp_*.py`, `tests/test_feature_flag_hot_reload.py`, `tests/test_vue_spa_static_mime.py`).

## [5.162.0] - 2026-08-03

> **Mind-map v2 delete/layout flash fixes; DOCX/PDF export modal polish; one-sentence node-action guide.**

### Added

- **One-sentence node-action guide** — Kitty conversational edit panel shows a collapsible node-action library with rotating suggestion prompts (`OneSentenceNodeActionGuide.vue`, `oneSentenceNodeActionGuide.ts`, `oneSentenceNodeActionSuggestions.ts`, canvas i18n).

### Changed

- **Export as DOCX/PDF** — Toolbar/modal copy renamed from “Print learning sheet”; mind-map v2 top-bar export drops standalone PDF (DOCX/PDF + paper orientation live in the worksheet modal) (`canvasExportMenu.ts`, `CanvasWorksheetTextModal.vue`, `MindMapExportOptionsPanel.vue`, `canvasExport.ts`).
- **Locale bundles** — Canvas keys for DOCX/PDF rename + one-sentence suggestions across locales; broader pt/ru/pl/tr message refresh.

### Fixed

- **Mind-map v2 side layout after delete/reload** — Incremental delete layout, sole-root fan moves with the topic anchor, and pre-show v2 layout sync so the first paint matches post-recalc (no off-then-correct flash) (`mindMapSideStacking.ts`, `mindMapOps.ts`, `mindMapLayout.ts`).
- **Diagram-edit delete verify labels** — Prefer unique human node text over recycled `branch-*` structural ids when building `node_absent` expectations (`services/diagram_edit/effects.py`).

### Tests

- **Frontend** — Side-stacking / sibling-anchor-Y / diagram-edit apply coverage; export menu no longer expects top-level PDF.
- **Backend** — Delete-verify label resolution cases in `tests/test_diagram_edit.py`.

## [5.161.0] - 2026-08-02

> **Interface language picker: real UI copy for all 28 locales; canvas library switch flash hardening.**

### Changed

- **Interface language picker translations** — All 28 Settings → Interface language locales now ship dedicated message bundles (~90–98% differs-from-en UI copy across 13 modules; brands/formulas/shortcuts intentionally English). Completes former English stubs and partial fr/az/th/af; regenerates zh-tw including showcase/maite/thinkingCoins; lazy loaders leave EN-copy for picker codes (`lazyLocaleLoaders.ts`, `messages/<code>/*.ts`).
- **zh-tw OpenCC pipeline** — `i18n:build-zhtw` also converts showcase, maite, and thinkingCoins from zh.
- **i18n key sync namespaces** — `sync-messages-keys-from-reference.ts` includes showcase and maite.

### Fixed

- **Canvas switch flash (follow-up)** — Library diagram select: generation-gated in-flight loads and collab flag preserved across unload (`useCanvasPageLibrarySnapshots.ts`, `useMobileCanvasRouteLoader.ts`).

## [5.160.0] - 2026-08-02

> **Document Summary lite production hardening; AI brainstorm 3-LLM waterfall polish; learning-sheet DOCX export.**

### Added

- **Print learning sheet → Export document (DOCX)** — Editable name/class/date/task fields with the diagram embedded as an image (`POST /api/export_worksheet_docx`, `worksheet_docx.py`, modal split PDF/document actions).
- **Document Summary web Chrome-extension nudge** — Soft notice under paste-URL that server fetch has no login cookies; tier-gated download link (`MindMapDocumentSummaryPanel.vue`, i18n).
- **AI brainstorm canvas glow** — Topic / branch nodes use the same `LlmPhaseRing` waiting glow as auto-complete while brainstorm streams (`useAiBrainstorm.ts`, mind-map topic/branch nodes).
- **AI brainstorm selected-card polish** — Swiss checkbox + ink/stone selected state, thin LLM accent bar, source label; dropped heavy ring stack (`AiBrainstormPanel.vue`).

### Changed

- **AI brainstorm uses all 3 LLMs** — Same default as node palette (`qwen` / `deepseek` / `doubao` in parallel); still 6 ideas per model per batch.
- **Document Summary upload body limit** — Middleware allows ~22 MB for doc-summary / knowledge-space `.../documents/upload` (matches advertised 20 MB file cap).

### Fixed

- **Canvas switch flash** — On library diagram select, flush dirty autosave then unload the previous canvas (reset + chrome type from list metadata) before fetch, so old toolbar/nodes never paint during the load gap.
- **Worksheet DOCX body limit** — Middleware now allows ~22 MB for `/api/export_worksheet_docx` so large diagram PNGs are not rejected by the default 5 MB cap.
- **Worksheet DOCX image fit / invalid upload** — Tall diagrams shrink to the page box; corrupt images return 400 instead of 500.
- **Worksheet modal hint (af/az/fr/th)** — Copy mentions both PDF and document export.
- **URL page fetch SSRF / DoS** — Resolve-once IP pin + SNI/`Host`, streamed 2 MiB abort, no redirects; HTML/plain content-type gate; title slug when page title missing (`url_page_fetch.py`).
- **`ingest-web-url` rate limit** — 20 requests / 600s before fetch/ingest.
- **Document Summary lite generate package miss** — Returns 422 instead of falling through to Knowledge Space 403 (`web_content_generation.py`).
- **Vision-before-upload** — Hand-drawn rebuild runs before file upload so orphan async extracts are not left behind.
- **Generate-owned extract toasts** — Suppress success/error watcher toasts while save-and-generate owns the wait; delete disabled during add/generate/processing.
- **Structured 413 toasts** — Object `detail` / `doc_summary_content_too_long` mapped via `parseApiErrorDetail` + i18n in file-center mutations.
- **Web URL draft validation** — Require `http(s)` and max 2000 chars before Generate enables.
- **AI brainstorm stage-2 Finish** — Applies selections across all parent tabs (palette parity), not only the active tab.
- **AI brainstorm Load more session id** — Matches `${session}_${parentId}` after multi-parent stage-2 start.
- **AI brainstorm undo / panel parity** — History navigation aborts brainstorm streams; `anyPanelOpen` / close-all / `state:panel_*` + fit include brainstorm; selection watcher no longer wipes stage-2.
- **AI brainstorm dismiss → Load more** — Restored sessions remint a client session id so Load more stays available.

### Tests

- **Backend** — Doc-summary upload body-limit paths; URL fetch pin/redirect/oversize/content-type; ingest-web-url rate-limit source assert; worksheet DOCX export coverage.
- **Frontend** — Lite draft URL validation + wait-helper empty/fail/timeout; `parseApiErrorDetail` object codes; multi-tab brainstorm Finish apply.

## [5.159.0] - 2026-08-01

> **Admin error Copy all; showcase cross-org author 500; quieter Celery/WS/abort logs; ClientDisconnect and RLS session hardening.**

### Added

- **Admin error collection Copy all** — One-click clipboard dump of filtered errors with path/message/stacktrace/tags (batched detail fetch, clipboard fallback, truncate/partial toasts) (`AdminErrorsTab.vue`, `adminErrorCollectionCopy.ts`).

### Fixed

- **Showcase list 500 (cross-org authors)** — `users` RLS is same-org, so `joinedload(author)` was `None` for other schools’ cases and author formatting crashed; resolve public name/avatar/org under system bootstrap and tolerate missing authors (`author_payload.py`, `routes_posts.py`).
- **`ClientDisconnect` on `/api/generate_graph/stream`** — Stop peeking the POST body in `log_requests` (logging no longer buffers JSON just for slow-threshold splitting); streamed-body limit and the general exception handler treat early client abort as 204 instead of an unhandled 500 (`middleware.py`, `exception_handlers.py`).
- **HTTPException as unhandled 500** — Middleware-raised `HTTPException` (e.g. expired token) re-routes through `http_exception_handler` instead of the catch-all (`exception_handlers.py`).
- **RLS strict deny_default noise** — Admin error APIs and coin side-sessions use pinned RLS sessions (`get_async_db_with_request_rls` / `actor_rls_session`); chunk-test background binds session RLS; lint flags bare `open_async_session` (`admin/errors.py`, diagrams/workshop/canvas_translate, `lint_rls_session.py`).
- **Celery log flood** — Managed worker defaults to `--loglevel=info`; process monitor skips broker inspect when the subprocess PID is alive; file formatters drop ANSI (`_celery_manager.py`, `process_monitor.py`, `logging_config.py`, `config/celery.py`).
- **WebSocket client-gone noise** — `safe_websocket_send_text` also swallows `websockets.ConnectionClosed*` (`ws_limits.py`).
- **Frontend abort / teaching-copy noise** — Skip `AbortError` in frontend error reporting; teaching-copy stream catch no longer rethrows (`frontendLog.ts`, `useShowcaseTeachingCopyAi.ts`).

### Tests

- **Backend** — Showcase author payload when author row is missing; `log_requests` does not buffer bodies; `ClientDisconnect` → 204 in streamed-body limit and general handler; Celery health-check skip when worker PID is alive.
- **Frontend** — Error-collection copy dump / clipboard helpers; teaching-copy stream abort coverage; `AbortError` skipped in frontend error reporting.

## [5.158.0] - 2026-08-01

> **Mind map v2 canvas default; pan-only keep-new-child in view; inline-edit hardening; admin capabilities after verified session; OpenClaw skill 1.3.0 (90-day tokens).**

### Changed

- **Mind map v2 default** — `FEATURE_MINDMAP_V2_CANVAS` defaults to `True`; UI defaults to the new canvas (classic still selectable in Language settings; flag off forces classic-only) (`features_config.py`, `env.example`, `featureFlags.ts`, `ui.ts`).
- **OpenClaw skill** — Auth / response / web-content / shortcut docs; API token validity **90 days**; ClawHub publish target **1.3.0** (`openclaw/skills/mindgraph/`).
- **API Token modal** — Copy updated to 90-day validity (`ApiTokenModal.vue`).

### Fixed

- **Admin capabilities race** — Wait for verified auth session (and retry once after refresh on 401) before `/api/auth/admin/capabilities`, so restored panel roles do not paint console 401s (`auth.ts`, `useAppSidebar.ts`).
- **Mind-map child add viewport** — Pan-only keep-in-view so a newly added child lands in the central safe fraction of the usable canvas without changing zoom (`mindMapEnsureNodeVisible.ts`, `useDiagramCanvasFit.ts`, `mindMapOps.ts`).
- **Inline edit / Enter on mind maps** — Stronger pending-edit handoff, Enter guard, and v2 branch node edit wiring so focus and commit stay reliable (`InlineEditableText.vue`, `MindMapV2BranchNode.vue`, `mindMapCanvasEnterGuard.ts`).

### Added

- **Mind-map keep-visible helpers** — Pure pan math + canvas fit hook; optional inline-edit debug util for local diagnosis.
- **Tests** — Admin capabilities load gating; keep-visible pan math; inline-edit debug; Enter-guard / pending-inline-edit coverage.

## [5.157.0] - 2026-08-01

> **Playwright Chromium (+ apt deps) via COS stack sync; showcase AI copy leaves teaching reflection to teachers; slim env.example.**

### Added

- **Playwright COS mirror** — Publisher packs Chromium (and Ubuntu apt `.deb` deps) to COS; consumers install from the shared sync prefix alongside Qdrant/Celery (`services/infrastructure/sync/playwright_*.py`, `scripts/db/update_stack_from_cos.py`).
- **Admin COS Playwright** — Overview health row plus status / publish / install API routes (`routers/admin/cos.py`, `AdminCosOverviewPanel.vue`).
- **`PLAYWRIGHT_TARGET_VERSION`** — Optional pin for the Playwright package version recorded in COS meta (`env.example`).

### Changed

- **Showcase teaching-copy AI** — Streams only description + design highlights; teaching reflection is teacher-authored and never cleared/overwritten by AI generate (`services/showcase/ai_copy.py`, `useShowcaseTeachingCopyAi.ts`).
- **`env.example`** — Trimmed to deployment essentials; advanced knobs documented in `docs/ops/env-advanced.md`.
- **Fail2ban / COS docs** — Shared sync prefix layout notes Playwright under `sync/playwright/`.

### Tests

- **Backend** — Playwright COS plan/sync + apt-deps helpers; updated stack COS / showcase AI copy tests.
- **Frontend** — Showcase teaching-copy generate coverage for the two AI fields.

## [5.156.1] - 2026-07-31

> **迈特学习法: persist practice on OCR, stream mentor results live, and commit Maite DB writes.**

### Fixed

- **Practice list empty after OCR** — Maite domain services only flushed and never committed, so create-problem/session responses looked successful then rolled back on request end; all Maite write paths now commit (`services/maite/domain/transaction.py`).
- **Mentor stream stall** — Streaming decompose/follow-up no longer uses `response_format: json_object` (DashScope buffered the full JSON ~45–70s); cumulative SSE preview + longer stall timeout; UI shows live tokens in chat and stream panel.
- **最近练习 on upload** — OCR success immediately creates problem + session and optimistically prepends sidebar **最近练习** (demo/inquiry), before mentor decompose starts.

### Added

- **Maite toasts / notifications** — Upload, OCR, decompose start/complete, practice-saved, and stream-fallback feedback; `useMaiteNotifications` bridges `maite:error`.
- **Sidebar practice history** — `MaitePracticeHistory` accordion (MindMate-style); open respects `demo` vs `inquiry` mode.

### Changed

- **Demo OCR → auto decompose** — After OCR, demo auto-starts streamed mentor decompose and reuses the session created at upload.

### Tests

- **Frontend** — Inquiry complete gate (`frontend/tests/maite/inquiryCompleteGate.spec.ts`).
- **Backend** — Module activity + public serializers (`tests/test_maite_module_activity.py`, `tests/test_maite_public_serializers.py`).

## [5.156.0] - 2026-07-31

> **迈特学习法 (Mate Learning): native MindGraph module with async LLM, PG+RLS, Redis, and event-bus UI.**

### Added

- **迈特学习法 module** — Sidebar + Intl module grid entry (`/maite`) for demo / inquiry / learning-map modes, gated by `FEATURE_MATE_LEARNING` (default off).
- **Backend `/api/maite`** — Authenticated async routers for problems/OCR, mentor SSE, inquiry stages (decompose → diagnose → remedy → variants → complete), reports, and user graph progress; private uploads; Redis recent-practice cache.
- **Shared LLM path** — Maite prompts call MindGraph `llm_service` (`request_type=maite_learning`) with token-cap / thinking-coin tracking; YAML prompts under `services/maite/prompts/`.
- **PostgreSQL models + RLS** — `maite_*` tables (Alembic `0089`/`0090`/`0091`) with `user_id` ownership + child/task-reference RLS; server-only `MaiteTaskReference` answer keys.
- **Event-bus UI** — Typed `maite:*` events on the frontend event bus; session asyncio bus for stage/stream coordination.

### Changed

- **Maite production hardening** — Completed sessions return 409 on mutations; strip `expected_strategy` from client payloads; LLM rate limits on diagnosis/remedy/variants/reports; OCR 8MB cap; authenticated `/health`; module activity tagged `maite` (not coerced to canvas); practice list Redis populate + `/practice/recent`; inquiry UI requires real variant answers (no placeholder complete).

### Tests

- **Backend** — Maite LLM adapter tracking kwargs, feature-gate hot-off, session bus, completion gate, secret stripping, module activity (`tests/test_maite_*.py`).
- **Frontend** — Maite math text + SSE frame parser (`frontend/tests/maite/`).

## [5.155.4] - 2026-07-30

> **Mind-map load: supersede rapid model-switch debug sessions; fit after settle on rAF.**

### Fixed

- **Overlapping load sessions** — Rapid LLM switches restart the `[MindMapLoad]` session when a prior `spec:load` is still open, instead of nesting stages ([`mindMapLoadDebug.ts`](frontend/src/utils/mindMapLoadDebug.ts), [`specIO.ts`](frontend/src/stores/diagram/specIO.ts)).
- **Fit-after-load jank** — Post measure-batch zoom-fit uses double-`rAF` instead of a 350ms `setTimeout` (avoids long timer-handler violations) ([`useDiagramCanvasFit.ts`](frontend/src/composables/diagramCanvas/useDiagramCanvasFit.ts)).

### Tests

- **Frontend** — Load-debug session supersede on rapid `spec:load` ([`mindMapSoftLoadAndMeasureBatch.spec.ts`](frontend/tests/mindMapSoftLoadAndMeasureBatch.spec.ts)).

## [5.155.3] - 2026-07-30

> **Mind-map load audit: freeze layout during measure-batch; LLM model switch zoom-fits after settle.**

### Fixed

- **V2 layout crawl during measure-batch** — While `mindMapBulkLoading`, v2 layout holds stamped node XY so live width/height updates cannot reshape Vue Flow node-by-node before flush ([`vueFlowIntegration.ts`](frontend/src/stores/diagram/vueFlowIntegration.ts)).
- **LLM model-switch zoom-fit** — Switching models always fits the diagram; mind-map v2 fits after measure-batch settle (soft reloads often skip `nodes-initialized`) ([`llmResults.ts`](frontend/src/stores/llmResults.ts), [`useDiagramCanvasFit.ts`](frontend/src/composables/diagramCanvas/useDiagramCanvasFit.ts)).
- **Soft hydrate coverage** — Snapshot recall, Kitty desktop/mobile library hydrate, and mobile import use `mindMapLibraryLoadOptions`; library `diagram:loaded_from_library` emits after Pinia replace ([`useCanvasPageLibrarySnapshots.ts`](frontend/src/composables/canvasPage/useCanvasPageLibrarySnapshots.ts), [`kittyDesktopActionHandlers.ts`](frontend/src/composables/kitty/kittyDesktopActionHandlers.ts), [`hydrateMobileKittyFromLibrary.ts`](frontend/src/composables/kitty/hydrateMobileKittyFromLibrary.ts), [`useMobileCanvasRouteLoader.ts`](frontend/src/composables/mobile/useMobileCanvasRouteLoader.ts)).
- **Measure-batch progress safety** — Progress timeout resets on each unique report so it cannot beat quiet while mounts are still streaming ([`mindMapLayout.ts`](frontend/src/stores/diagram/mindMapLayout.ts)).

## [5.155.2] - 2026-07-30

> **Mind-map load: measure-batch quiet flush wins after long stalls; Kitty reconnect deferred off first paint.**

### Fixed

- **Measure-batch timeout race** — First unique measure report cancels the arm-time 1.5s safety and starts a 750ms progress safety, so a long main-thread stall cannot leave an overdue timer beating the 64ms quiet flush ([`mindMapLayout.ts`](frontend/src/stores/diagram/mindMapLayout.ts)).
- **Kitty canvas-owner connect** — Scope/enabled watch uses the existing 400ms reconnect debounce instead of immediate `ensureConnected`, so `loadFromSpec` first paint is not competing with WS start + full diagram context JSON ([`useKittyCanvasOwnerAgent.ts`](frontend/src/composables/kitty/useKittyCanvasOwnerAgent.ts)).

### Tests

- **Frontend** — Arm-safety cancel vs quiet; Kitty ownership waits for reconnect debounce ([`mindMapSoftLoadAndMeasureBatch.spec.ts`](frontend/tests/mindMapSoftLoadAndMeasureBatch.spec.ts), [`useKittyCanvasOwnerAgentOwnership.spec.ts`](frontend/tests/useKittyCanvasOwnerAgentOwnership.spec.ts)).

## [5.155.1] - 2026-07-30

> **Mind-map library open paints labels with layout; measure-batch no longer crawls node-by-node.**

### Fixed

- **Mind-map load paint** — Eager-import v2 canvas + topic/branch shells (async canvas was ~1–2s to first mount); library/mobile soft-loads stamped `nodes[]`/`connections[]` (without copying prior-diagram session measures) and seeds v2 measure maps from estimates; measure-batch settles on unique reports + 64ms quiet flush (reused Vue Flow nodes often skip ResizeObserver) with 1.5s safety timeout — removed double-rAF early flush; suppress Vue Flow node `transform` while bulk-loading ([`MindMapCanvasRouter.vue`](frontend/src/components/diagram/MindMapCanvasRouter.vue), [`TopicNode.vue`](frontend/src/components/diagram/nodes/TopicNode.vue), [`BranchNode.vue`](frontend/src/components/diagram/nodes/BranchNode.vue), [`mindMapLayout.ts`](frontend/src/stores/diagram/mindMapLayout.ts), [`mindMapLibraryLoadOptions.ts`](frontend/src/utils/mindMapLibraryLoadOptions.ts), [`specIO.ts`](frontend/src/stores/diagram/specIO.ts), [`diagramCanvas.css`](frontend/src/components/diagram/diagramCanvas.css)).

### Added

- **Mind-map load timers** — Opt-in `localStorage.setItem('mindmap_load_debug', '1')` logs `[MindMapLoad]` `performance.now()` stages (fetch → spec → shell → measure batch → recalcs → settle) ([`mindMapLoadDebug.ts`](frontend/src/utils/mindMapLoadDebug.ts)).

### Tests

- **Frontend** — Measure-batch late-mount / no early-flush / safety-timeout cases; library soft-load options helper ([`mindMapSoftLoadAndMeasureBatch.spec.ts`](frontend/tests/mindMapSoftLoadAndMeasureBatch.spec.ts)).

## [5.155.0] - 2026-07-30

> **Showcase teaching-copy AI streams live; mind-map auto-complete locks the canvas topic and soft-loads model switches.**

### Added

- **Streaming teaching-copy AI** — `POST /api/showcase/ai/teaching-copy/stream` SSE fills `description` / `design_highlights` / `teaching_reflection` token-by-token in the publish modal; sync JSON route kept as fallback ([`routes_ai.py`](routers/features/showcase/routes_ai.py), [`ai_copy.py`](services/showcase/ai_copy.py), [`useShowcaseTeachingCopyAi.ts`](frontend/src/composables/showcase/useShowcaseTeachingCopyAi.ts)).
- **Autocomplete topic lock** — Client sends `locked_topic`; backend overwrites central topic fields after generation so auto-complete never rewrites the canvas topic ([`autocomplete_topic_lock.py`](agents/core/autocomplete_topic_lock.py), [`workflow.py`](agents/core/workflow.py), [`useAutoComplete.ts`](frontend/src/composables/editor/useAutoComplete.ts), [`llmResults.ts`](frontend/src/stores/llmResults.ts)).
- **Mind-map measure batch** — After `loadFromSpec`, ResizeObserver updates accumulate until the pending count hits 0 (or a short safety flush) before one recalc ([`mindMapLayout.ts`](frontend/src/stores/diagram/mindMapLayout.ts), [`specIO.ts`](frontend/src/stores/diagram/specIO.ts)).
- **Orthogonal sibling map** — Precompute parent→sibling edge groups so each orthogonal edge does not filter the full edge list ([`mindMapOrthogonalSiblings.ts`](frontend/src/utils/mindMapOrthogonalSiblings.ts), [`vueFlowIntegration.ts`](frontend/src/stores/diagram/vueFlowIntegration.ts)).

### Changed

- **AI生成 UX** — Step 2 auto-streams into empty fields with start/success/error toasts; button shows **停止** while in-flight (abort, keep partial text); idle click clears and regenerates ([`PublishShowcaseModal.vue`](frontend/src/components/showcase/PublishShowcaseModal.vue), [`useShowcaseTeachingCopyAi.ts`](frontend/src/composables/showcase/useShowcaseTeachingCopyAi.ts)).
- **Mind-map auto-complete quality** — Enforce 4/6/8 main branches with nested children; raise `max_tokens` and lower temperature; prompt locks exact `topic` ([`mind_map_agent.py`](agents/mind_maps/mind_map_agent.py), [`prompts/mind_maps.py`](prompts/mind_maps.py)).
- **Soft model switch** — Laid-out mind maps reuse stamped `nodes[]`/`connections[]`, preserve measured widths/heights, skip fit on user switch, and defer cache stamp so first paint stays smooth ([`llmResults.ts`](frontend/src/stores/llmResults.ts), [`specLoader/index.ts`](frontend/src/stores/specLoader/index.ts)).
- **Volcengine / DashScope JSON mode** — Forward `response_format`; Volcengine retries without structured output when the model rejects it ([`volcengine.py`](clients/llm/volcengine.py), [`dashscope.py`](clients/llm/dashscope.py)).
- **Cover host-deps** — Require Writer + Impress markers; clearer apt install/verify hints in startup and [`env.example`](env.example) ([`host_deps.py`](services/showcase/covers/host_deps.py)).

### Tests

- **Backend / frontend** — Partial JSON field extraction; SSE client field callbacks; topic-lock unit tests; mind-map soft-load / measure-batch vitest; autocomplete audit helpers ([`test_showcase_ai_copy.py`](tests/test_showcase_ai_copy.py), [`test_autocomplete_topic_lock.py`](tests/test_autocomplete_topic_lock.py), [`generateShowcaseTeachingCopy.spec.ts`](frontend/tests/generateShowcaseTeachingCopy.spec.ts), [`mindMapSoftLoadAndMeasureBatch.spec.ts`](frontend/tests/mindMapSoftLoadAndMeasureBatch.spec.ts)).

## [5.154.0] - 2026-07-30

> **Showcase teaching-design accepts PPTX (cover + PDF preview); stale Celery workers restart safely; document preview fits width with denser watermarks.**

### Added

- **PPTX teaching-design uploads** — `.pptx` joins the teaching-design allowlist (FE accept, upload roles, magic bytes requiring `ppt/presentation.xml`, AI teaching-copy extract via `python-pptx`) ([`helpers.py`](routers/features/showcase/helpers.py), [`showcaseShared.ts`](frontend/src/components/showcase/showcaseShared.ts), [`roles.py`](services/showcase/uploads/roles.py)).
- **PPTX cover + slide preview** — LibreOffice converts PPTX→PDF for the cover thumbnail and persists `preview.pdf`; detail reader uses pdf.js with a pending state until conversion finishes ([`generate.py`](services/showcase/covers/generate.py), [`ShowcaseTeachingDocPreview.vue`](frontend/src/components/showcase/ShowcaseTeachingDocPreview.vue), [`office_to_pdf.py`](services/showcase/covers/office_to_pdf.py)).
- **Host deps gate for covers** — Startup checks LibreOffice + Noto CJK when server covers are enabled; install hints include `libreoffice-impress` ([`host_deps.py`](services/showcase/covers/host_deps.py), [`server_launcher.py`](services/infrastructure/process/server_launcher.py)).

### Changed

- **Stale Celery reuse** — Before skipping worker startup, verify registered tasks; missing app tasks shut down **only** those workers (`destination=…`), then reuse healthy peers or relaunch ([`_celery_manager.py`](services/infrastructure/process/_celery_manager.py)).
- **Attachment replace invalidates cover/preview** — New attachment clears `thumbnail_path` and `preview_path` so cover-stream waits for the new job instead of early `cover_ready` ([`pipeline.py`](services/showcase/uploads/pipeline.py)).
- **Teaching-doc preview UX** — Fit-to-width zoom (CSS `zoom`), no horizontal scroll, denser watermarks; locales use “Fit width” / “适应宽度” ([`ShowcaseTeachingDocPreview.vue`](frontend/src/components/showcase/ShowcaseTeachingDocPreview.vue), [`renderDocxPreview.ts`](frontend/src/utils/renderDocxPreview.ts), [`showcaseWatermark.ts`](frontend/src/utils/showcaseWatermark.ts)).
- **Content-Type hardening** — FE remaps empty/`octet-stream` from extension; BE allows `application/octet-stream` for pdf/doc/docx/pptx ([`uploadShowcaseFile.ts`](frontend/src/composables/showcase/uploadShowcaseFile.ts), [`roles.py`](services/showcase/uploads/roles.py)).
- **Honest teaching-doc hints** — Copy lists `.docx` / `.pdf` / `.pptx` and notes limited `.doc` preview; removed unused cover-skip locales ([en/zh showcase locales](frontend/src/locales/messages/)).

### Fixed

- **AI teaching-copy magic validation** — `POST /api/showcase/ai/teaching-copy` rejects mismatched file content ([`routes_ai.py`](routers/features/showcase/routes_ai.py)).
- **PPTX COS complete magic** — Full object is loaded for OOXML member checks (ZIP central directory is at EOF) ([`routes_uploads.py`](routers/features/showcase/routes_uploads.py)).
- **covers package import cycle** — Package `__init__` stays light so `host_deps` can load from launch paths without pulling Redis via `generate` ([`covers/__init__.py`](services/showcase/covers/__init__.py)).

### Tests

- **Backend** — PPTX magic accept/reject; octet-stream content-types; Celery stale-worker targeted shutdown; cover host-deps; `preview_path` key collection ([`test_showcase_helpers.py`](tests/test_showcase_helpers.py), [`test_celery_manager_stale.py`](tests/test_celery_manager_stale.py), [`test_showcase_cover_host_deps.py`](tests/test_showcase_cover_host_deps.py)).

## [5.153.0] - 2026-07-29

> **Showcase teaching-design covers render server-side (LibreOffice + Celery + SSE); AI drafts intro, highlights, and reflection from uploaded documents; MCP HTTP mounts on mcp 2.x.**

### Added

- **Server-side teaching-design covers** — After attachment `uploads/complete`, Celery job `showcase.generate_cover` downloads the file, converts `.doc`/`.docx` via LibreOffice, rasterizes page 1 with PyMuPDF, shrinks to the 2MB / 960px budget, and uploads `thumbnail.png` ([`services/showcase/covers/`](services/showcase/covers/), [`tasks/showcase_cover_tasks.py`](tasks/showcase_cover_tasks.py)).
- **Cover SSE stream** — `GET /api/showcase/posts/{id}/cover-stream` pushes `cover_ready` / `cover_fail` over Redis pub/sub with heartbeats and a 210s hard stop ([`routes_covers.py`](routers/features/showcase/routes_covers.py), [`createShowcaseCoverStream.ts`](frontend/src/composables/showcase/createShowcaseCoverStream.ts)).
- **Cover pending UX** — Publish marks the post as cover-pending, opens an EventSource, shows a spinner on feed cards until the thumbnail arrives, and warns on timeout/failure without blocking submit ([`showcase.ts`](frontend/src/stores/showcase.ts), [`ShowcasePage.vue`](frontend/src/pages/ShowcasePage.vue)).
- **Teaching-design AI copy API** — `POST /api/showcase/ai/teaching-copy` accepts `.pdf`/`.doc`/`.docx` plus title/subject/grade, extracts text, and returns `description`, `design_highlights`, and `teaching_reflection` via `qwen3.7-flash` (~200 字 × 3; rate limit 12/min) ([`ai_copy.py`](services/showcase/ai_copy.py), [`routes_ai.py`](routers/features/showcase/routes_ai.py)).
- **Publish modal AI generate** — Real LLM-backed “AI生成” with prefetch on step-2 entry, fingerprint cache, abort on file/title change, and phase styling ([`useShowcaseTeachingCopyAi.ts`](frontend/src/composables/showcase/useShowcaseTeachingCopyAi.ts), [`PublishShowcaseModal.vue`](frontend/src/components/showcase/PublishShowcaseModal.vue)).
- **Showcase storage download helpers** — `download_to_path` / `download_to_path_sync` stream attachments to temp files during cover generation ([`backend.py`](services/showcase/storage/backend.py)).
- **Celery cover task registration** — `tasks.showcase_cover_tasks` on the `default` queue with `showcase.*` routing ([`config/celery.py`](config/celery.py)).
- **`SHOWCASE_SERVER_COVERS` env** — Default on when `COS_SHOWCASE_ENABLED`; set `false` to disable; `true` forces on for local/dev ([`env.example`](env.example)).

### Changed

- **Teaching-design publish flow** — Client no longer captures/uploads a cover thumbnail on submit; only the attachment is uploaded and the cover is generated asynchronously server-side ([`submitPublishShowcasePost.ts`](frontend/src/composables/showcase/submitPublishShowcasePost.ts)).
- **Celery startup/monitoring** — Worker soft-starts when server covers are on (even if Knowledge Space is off); missing Celery warns and covers soft-fail instead of blocking boot ([`server_launcher.py`](services/infrastructure/process/server_launcher.py), [`process_monitor.py`](services/infrastructure/monitoring/process_monitor.py)).
- **AI generate replaces stub** — Step-2 “AI生成” calls the new API and fills all three teaching-design text fields ([`usePublishShowcaseModal.ts`](frontend/src/composables/showcase/usePublishShowcaseModal.ts)).
- **COS thumbnail upload** — `put_bytes` / `upload_bytes` accept optional `ContentType` so cover PNGs store as `image/png` ([`tencent_cos_client.py`](services/utils/tencent_cos_client.py)).
- **Token accounting for qwen3.7-flash** — Pricing alias and 120s timeout for the new model ([`redis_token_buffer.py`](services/redis/redis_token_buffer.py), [`llm_utils.py`](services/llm/llm_utils.py)).
- **MCP package 2.x** — Pin `mcp[cli]>=2,<3`; mount via `MCPServer` / `mindgraph_mcp_asgi_app()` ([`requirements.txt`](requirements.txt), [`mindgraph_mcp.py`](services/mcp/mindgraph_mcp.py), [`mount.py`](services/mcp/mount.py)).

### Fixed

- **Legacy `.doc` covers** — Server-side LibreOffice conversion covers `.doc` attachments (5.152.0 skipped them client-side); publish still succeeds if generation fails.
- **DOCX DOM capture robustness** — `sanitizeDocxDomForHtmlCapture` strips empty/broken SVG `<image>` hrefs that broke html-to-image ([`captureTeachingDocThumbnail.ts`](frontend/src/utils/captureTeachingDocThumbnail.ts)).

### Tests

- **Backend** — AI copy JSON parse/normalize ([`test_showcase_ai_copy.py`](tests/test_showcase_ai_copy.py)); server cover scope/stale-key guards, PNG shrink, PDF render ([`test_showcase_server_covers.py`](tests/test_showcase_server_covers.py)).
- **Frontend** — Teaching-copy fingerprint cache key ([`generateShowcaseTeachingCopy.spec.ts`](frontend/tests/generateShowcaseTeachingCopy.spec.ts)); DOCX DOM sanitizer ([`sanitizeDocxDomForHtmlCapture.spec.ts`](frontend/tests/sanitizeDocxDomForHtmlCapture.spec.ts)).
- **Smoke** — Live LLM smoke for teaching-copy extraction + generation ([`scripts/smoke_showcase_ai_copy.py`](scripts/smoke_showcase_ai_copy.py)).

## [5.152.0] - 2026-07-28

> **Showcase covers stay under 2MB and soft-fail without discarding the case; Kitty WS/SSE recover auth once then hard-stop; Dify failover health probes once per host and treats bad app keys as reachable.**

### Added

- **Dify host-level health probe** — Probe each unique base URL once with candidate app keys; retry on 401/403; auth-only answers still count as host online ([`dify_health_host_probe.py`](services/dify/dify_health_host_probe.py), [`dify_health_probe_plan.py`](services/dify/dify_health_probe_plan.py), [`dify_health_poller.py`](services/dify/dify_health_poller.py)).
- **Showcase cover size helpers** — Client shrinks cover PNGs to the 2MB / 960px budget before upload ([`showcaseShared.ts`](frontend/src/components/showcase/showcaseShared.ts), [`captureTeachingDocThumbnail.ts`](frontend/src/utils/captureTeachingDocThumbnail.ts)).
- **Kitty WS auth reconnect gate** — Shared refresh-once-then-hard-stop helper for canvas-owner and mobile Kitty connect paths ([`kittyWsAuthReconnect.ts`](frontend/src/composables/kitty/kittyWsAuthReconnect.ts)).

### Changed

- **Showcase cover is best-effort** — Attachment/gallery uploads still roll back on failure; cover capture/upload failures warn and leave the case submitted ([`submitPublishShowcasePost.ts`](frontend/src/composables/showcase/submitPublishShowcasePost.ts)).
- **Showcase size-error UX** — Distinct messages for cover 2MB vs attachment/video limits, including rollback wording ([`mapShowcaseSubmitError.ts`](frontend/src/composables/showcase/mapShowcaseSubmitError.ts), en/zh showcase locales).
- **Kitty desktop polls use `apiRequest`** — Focus/session/live-context/mobile-active/pairing GETs refresh on 401 instead of raw `fetch`, so idle heartbeats stop after session expiry ([`useKittyDesktopFocus.ts`](frontend/src/composables/kitty/useKittyDesktopFocus.ts), [`useKittyDesktopActionPoll.ts`](frontend/src/composables/kitty/useKittyDesktopActionPoll.ts), and related Kitty pollers).
- **Desktop wake SSE reconnect gate** — Skip backoff reconnect when logged out or polling is disallowed ([`createKittyDesktopWakeStream.ts`](frontend/src/composables/kitty/createKittyDesktopWakeStream.ts)).
- **Dify health poller lock loss** — Finish Redis fan-out with in-memory probe results instead of aborting mid-cycle ([`dify_health_poller.py`](services/dify/dify_health_poller.py)).
- **Dify health env docs** — Clarify host-level dedupe and auth-retry behavior ([`env.example`](env.example)).

### Fixed

- **Teaching-design / diagram covers over 2MB** — Lower capture pixelRatio and downscale until within `CASE_THUMBNAIL_MAX_BYTES` so COS/presigned PUTs stop returning 413.
- **Legacy `.doc` cover path** — Skip unsupported preview generation and submit without a cover instead of failing the publish flow.
- **Kitty WS reconnect storm after expired JWT** — Canvas-owner and mobile Kitty refresh once via `/api/auth/refresh`, then hard-stop and surface session-expired instead of looping on 403/1006 ([`useKittyCanvasOwnerAgent.ts`](frontend/src/composables/kitty/useKittyCanvasOwnerAgent.ts), [`MobileKittyPage.vue`](frontend/src/pages/mobile/MobileKittyPage.vue), [`useMobileKittyPageLifecycle.ts`](frontend/src/composables/mobile/useMobileKittyPageLifecycle.ts)).

### Tests

- **Backend** — Host probe auth-retry / online classification; probe plan collapses same URL across keys and slots ([`test_dify_health_host_probe.py`](tests/test_dify_health_host_probe.py), [`test_dify_health_probe_plan.py`](tests/test_dify_health_probe_plan.py)).
- **Frontend** — Cover vs attachment 413 mapping; Kitty WS auth recover/hard-stop; wake-stream `shouldReconnect` skip ([`mapShowcaseSubmitError.spec.ts`](frontend/tests/mapShowcaseSubmitError.spec.ts), [`kittyWsAuthReconnect.spec.ts`](frontend/tests/kittyWsAuthReconnect.spec.ts), [`createKittyDesktopWakeStream.spec.ts`](frontend/tests/createKittyDesktopWakeStream.spec.ts)).
- **Optional e2e** — Real DOCX teaching-design create → attach → thumb gates → withdraw when `SHOWCASE_REAL_DOCX` / Desktop fixture is present ([`test_showcase_real_docx_e2e.py`](tests/test_showcase_real_docx_e2e.py)).

## [5.151.1] - 2026-07-28

> **Mind map post-Enter/Tab selection no longer fights sticky inline edit; Kitty desktop action drain loads handlers before LPOP; Vite Rolldown codeSplitting groups.**

### Fixed

- **Mind map sticky post-add edit steals branch clicks** — After Enter/Tab add, `mindMapPendingEditNodeId` + `tryFocus` re-selected the new node and ignored outside canvas pointers, so older branches needed multiple clicks. Pending edit now yields on intentional canvas/selection changes (toast/overlay stickiness kept), clears on save/cancel and the stuck max-attempt path, and no longer force-selects over a user-moved selection ([`mindMapOps.ts`](frontend/src/stores/diagram/mindMapOps.ts), [`selection.ts`](frontend/src/stores/diagram/selection.ts), [`InlineEditableText.vue`](frontend/src/components/diagram/nodes/InlineEditableText.vue)).
- **Kitty desktop queued-action drop on chunk load failure** — Heavy handlers/`savedDiagrams` load before Redis LPOP so a failed dynamic import cannot dequeue an action ([`useKittyDesktopActionPoll.ts`](frontend/src/composables/kitty/useKittyDesktopActionPoll.ts)).

### Changed

- **`adoptOpenCanvasSessionScope` module** — Extracted from desktop action handlers so canvas seed/route paths avoid pulling the full Kitty handler graph ([`adoptOpenCanvasSessionScope.ts`](frontend/src/composables/kitty/adoptOpenCanvasSessionScope.ts)).
- **Vite vendor splits** — `rollupOptions.manualChunks` → Rolldown `codeSplitting.groups`; keep vue-flow/echarts/jspdf/EP out of forced entry-shared chunks ([`vite.config.ts`](frontend/vite.config.ts)).
- **Mobile canvas Tailwind** — Prefer spacing utilities (`min-h-11`, `inset-e-3`, …) over arbitrary pixel classes ([`MobileCanvasPage.vue`](frontend/src/pages/mobile/MobileCanvasPage.vue)).

### Tests

- **Frontend** — Pending post-add inline-edit release on grace selection / other-node pointer / ephemeral toast ([`mindMapPendingInlineEdit.spec.ts`](frontend/tests/mindMapPendingInlineEdit.spec.ts)); Kitty surface import guard for the extracted scope helper.

## [5.151.0] - 2026-07-28

> **Mind map v2/legacy lazy canvas split, in-place sibling insert with sticky Enter Y, collab connection-order SoT, and longer API tokens with safer geo/pg-restore startup.**

### Added

- **Mind map canvas host/router** — `DiagramCanvasHost` routes mind maps through `MindMapCanvasRouter`, which lazy-loads exactly one shell (`MindMapLegacyCanvas` / `MindMapV2Canvas`) with separate edge registries and v2-only overlays ([`DiagramCanvasHost.vue`](frontend/src/components/diagram/DiagramCanvasHost.vue), [`MindMapCanvasRouter.vue`](frontend/src/components/diagram/MindMapCanvasRouter.vue)).
- **Mind map node routers** — `TopicNode` / `BranchNode` are thin lazy routers to `MindMapLegacy*` / `MindMapV2*` variant chunks; other diagram types use `TopicNodeDiagram` / `BranchNodeDiagram` ([`TopicNode.vue`](frontend/src/components/diagram/nodes/TopicNode.vue), [`BranchNode.vue`](frontend/src/components/diagram/nodes/BranchNode.vue), [`nodes/mindMap/`](frontend/src/components/diagram/nodes/mindMap/)).
- **Locked canvas variant injection** — `MIND_MAP_CANVAS_VARIANT_KEY` + `useMindMapCanvasVisuals()` so nodes resolve legacy vs v2 from the active shell ([`mindMapCanvasVariantKey.ts`](frontend/src/composables/mindMap/mindMapCanvasVariantKey.ts), [`useMindMapCanvasVisuals.ts`](frontend/src/composables/mindMap/useMindMapCanvasVisuals.ts)).
- **V2 in-place sibling insert** — `insertMindMapSiblingInPlace` mints one id/edge, splices connection order, places Y, and shifts siblings without full-tree reload ([`mindMapSiblingInsert.ts`](frontend/src/stores/diagram/mindMapSiblingInsert.ts)).
- **`mindMapPreserveIncomingY` policy** — Sticky L1 Enter Y across measure/edit-end; settle-only layout; cleared on collapse, shape switch, and full reload ([`mindMapLayout.ts`](frontend/src/stores/diagram/mindMapLayout.ts), [`mindMapSideStacking.ts`](frontend/src/utils/mindMapSideStacking.ts)).
- **Sibling insert API fields** — `after_node_id` / `insert_index` on diagram-edit tools and Kitty/voice paths ([`schema.py`](services/diagram_edit/schema.py), [`convert.py`](services/diagram_edit/convert.py), [`diagram_add.py`](services/kitty/diagram/diagram_add.py)).
- **Collab sibling-order hint** — `insert_after_target` on new connection patches with Redis `JSON.ARRINSERT` ([`online_collab_live_spec.py`](services/online_collab/spec/online_collab_live_spec.py)).
- **pg_restore migrate-role TOC filter** — Skip superuser extension/default-ACL entries; pre-install extensions; re-apply RLS grants ([`pg_restore_prep.py`](services/utils/pg_restore_prep.py), [`reset_local_pg_and_import_dump.py`](scripts/db/reset_local_pg_and_import_dump.py)).
- **COS consumer startup pull** — Sync blocklists, GeoLite, Qdrant, and Celery from COS before serving ([`cos_mirror_scheduler.py`](services/infrastructure/sync/cos_mirror_scheduler.py)).
- **Architecture / nvm docs** — Canvas/node split and preserve-Y lifecycle; China-friendly nvm install notes ([`mindmap_v2_separation.md`](docs/architecture/mindmap_v2_separation.md), [`NODE_NVM_SETUP.md`](docs/NODE_NVM_SETUP.md)).

### Changed

- **Sibling order SoT** — Connection list order replaces global branch-index sorting in geometry, side stacking, voice, and Kitty paths.
- **V2 L1 column / orthogonal paths** — Shared inner-edge column layout; rounded multi-sibling bus tees; topic width SoT for anchors ([`mindMapOrthogonalPath.ts`](frontend/src/utils/mindMapOrthogonalPath.ts)).
- **Canvas pages use host** — Desktop/mobile mount `DiagramCanvasHost` ([`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue), [`MobileCanvasPage.vue`](frontend/src/pages/mobile/MobileCanvasPage.vue)).
- **Library reload guard** — Skip reload when `?diagramId=` matches the already-active diagram ([`skipLibraryReloadDuringGeneration.ts`](frontend/src/composables/canvasPage/skipLibraryReloadDuringGeneration.ts)).
- **API token lifetime** — Personal API tokens and Redis cache TTL **7 → 90 days** ([`personal_token.py`](routers/auth/personal_token.py)).
- **Startup ordering** — COS consumer artifact pull before CrowdSec merge; geo middleware after `auth_context` ([`lifespan.py`](services/infrastructure/lifecycle/lifespan.py), [`middleware.py`](services/infrastructure/http/middleware.py)).
- **Ruff 0.16 compatibility** — Pin pre-0.16 lint `select` and exclude Markdown from format gate ([`pyproject.toml`](pyproject.toml)).
- **Local lint parity with CI** — Inline-suppression and four-rule audits scan git-tracked Python only; basedpyright/pylint/ruff exclude gitignored `esp32/` / `archive/` trees ([`lint_no_inline_disables.py`](scripts/lint/lint_no_inline_disables.py), [`audit_pylint_four_rules.py`](scripts/lint/audit_pylint_four_rules.py), [`pyproject.toml`](pyproject.toml)).
- **Frontend npm audit cleanup** — `vite-plugin-pwa@^1.3.0`, `sharp@^0.35.3`, overrides for `brace-expansion` / `minimatch` ([`package.json`](frontend/package.json)).

### Fixed

- **V2 Enter sibling flash** — In-place insert keeps new branch at insert Y and selects it for inline edit.
- **Post-edit Enter anchor theft** — User selection wins over stale post-edit sibling anchor ([`mindMapCanvasEnterGuard.ts`](frontend/src/composables/mindMap/mindMapCanvasEnterGuard.ts)).
- **Collab sibling mis-order** — Remote inserts land between siblings, not at connection list end.
- **Geo middleware ASGI crash** — Invalid/expired `mgat_` tokens soft-resolve to `None` ([`email_login_cn_api_geo.py`](services/auth/email_login_cn_api_geo.py), [`vpn_geo_enforcement.py`](services/auth/vpn_geo_enforcement.py)).
- **Local pg_restore on `mindgraph_migrate`** — TOC skips postgres-owned extension/ACL DDL; grants re-applied post-restore.

### Tests

- **Frontend** — In-place sibling insert, preserve-Y policy, side stacking, v2 Enter selection, orthogonal bus paths ([`mindMapSiblingInsertInPlace.spec.ts`](frontend/tests/mindMapSiblingInsertInPlace.spec.ts), [`mindMapPreserveIncomingY.spec.ts`](frontend/tests/mindMapPreserveIncomingY.spec.ts)).
- **Backend** — Geo `mgat_` soft-resolve, pg_restore TOC skip rules, COS consumer startup pull, collab `insert_after_target` ([`test_email_login_cn_api_geo_mgat.py`](tests/auth/test_email_login_cn_api_geo_mgat.py), [`test_pg_restore_prep.py`](tests/services/test_pg_restore_prep.py), [`test_cos_mirror_scheduler.py`](tests/services/test_cos_mirror_scheduler.py), [`test_workshop_collab_backend.py`](tests/test_workshop_collab_backend.py)).

## [5.150.0] - 2026-07-21

> **Showcase COS upload reliability: Content-Type signed via headers, clearer CORS/storage failure UX, and upload-rollback withdraw reasons.**

### Added

- **Showcase submit error mapper** — Dedicated mapping for CORS/network vs storage-rejected vs generic rollback messages ([`mapShowcaseSubmitError.ts`](frontend/src/composables/showcase/mapShowcaseSubmitError.ts)).
- **Withdraw reason on upload rollback** — Optional `reason` on `POST /api/showcase/posts/{id}/withdraw`; upload failures log as `upload_rollback` for greppable workflow traces ([`routes_posts.py`](routers/features/showcase/routes_posts.py), [`lifecycle.py`](services/showcase/posts/lifecycle.py)).
- **COS CORS guidance** — `env.example` documents required browser origins / methods / headers for Showcase presigned PUTs.

### Changed

- **Presigned PUT Content-Type** — Sign `Content-Type` via `Headers` (not query `Params`) so browser PUTs match the signature ([`tencent_cos_client.py`](services/utils/tencent_cos_client.py)).
- **Upload failure UX** — Detect browser→COS CORS/network failures; longer toast duration; i18n keys for CORS and storage rejection across locale bundles.

### Fixed

- **Silent Showcase upload failure** — Browser CORS/network PUT failures no longer look like opaque rollbacks; drafts still withdraw, with a reason the server can log.

### Tests

- **Backend** — Presigned PUT signs Content-Type via Headers; withdraw reason normalization and `upload_rollback` stage.
- **Frontend** — Showcase submit error mapping (`mapShowcaseSubmitError.spec.ts`).

## [5.149.0] - 2026-07-21

> **Stable mind-map node identity, underline connector layout/performance, unified module activity with `X-MG-Client`, and Kitty live-spec extras hydrate.**

### Added

- **Stable mind-map branch UIDs** — `data.mindMapUid` survives tree rebuilds/reparent so styles, selection, and measured sizes follow content identity instead of positional ids ([`mindMapNodeUid.ts`](frontend/src/utils/mindMapNodeUid.ts), [`mindMapCollapse.ts`](frontend/src/stores/diagram/mindMapCollapse.ts)).
- **Mind-map live-spec extras helpers** — Persist/restore diagram style, theme, node styles, and collapse paths across Kitty/live-spec round-trips ([`mindMapLiveSpecExtras.ts`](frontend/src/utils/mindMapLiveSpecExtras.ts)).
- **Unified module activity** — Shared Redis + usage-timeline + greppable log helper for canvas/Kitty/knowledge/doc-summary and feature routers ([`module_activity.py`](services/monitoring/module_activity.py)).
- **`X-MG-Client` attribution** — Sanitize/bind client labels (`web`, chrome/edge extension, OpenClaw, file-reader) for activity details ([`mg_client.py`](utils/auth/mg_client.py)).
- **Underline drop-preview shapes** — V2 branch-move previews use rectangular/baseline highlights for underline nodes ([`diagramCanvasZoomPaneStyles.ts`](frontend/src/composables/diagramCanvas/diagramCanvasZoomPaneStyles.ts)).

### Changed

- **Style merge on reload** — Mind-map reload styles remap by UID/content identity and refresh `nodeShape` when depth changes after drag-reparent ([`mindMapStylePreservation.ts`](frontend/src/stores/diagram/mindMapStylePreservation.ts)).
- **V2 layout height estimates** — Underline-shaped depths use underline box metrics at build time ([`mindMapV2Layout.ts`](frontend/src/stores/specLoader/mindMapV2Layout.ts)).
- **Activity tracking wiring** — Routers/services call the unified module activity helper with client-source details.
- **Kitty context hydrate** — Library/saved-spec hydrate keeps mind-map live-spec extras for `loadFromSpec` visuals ([`kitty_context_hydrate.py`](services/kitty/infra/bootstrap/kitty_context_hydrate.py)).

### Fixed

- **Underline connector Y misalignment** — Pack underline content to the top (`justify-start` + `height: fit-content`) so SVG bars/tees meet the text baseline instead of floating below ([`BranchNode.vue`](frontend/src/components/diagram/nodes/BranchNode.vue), [`TopicNode.vue`](frontend/src/components/diagram/nodes/TopicNode.vue)).
- **Connector lag after branch edits** — Stop sync DOM measuring inside Y restack; seed underline-aware estimates on text edit; sync edit width only; cache subtree spans; seed sizes on history restore ([`mindMapLayout.ts`](frontend/src/stores/diagram/mindMapLayout.ts), [`nodeManagement.ts`](frontend/src/stores/diagram/nodeManagement.ts), [`InlineEditableText.vue`](frontend/src/components/diagram/nodes/InlineEditableText.vue), [`historyRestore.ts`](frontend/src/stores/diagram/historyRestore.ts)).
- **Plain-text underline measure cost** — Prefer cheap canvas measure unless markdown/KaTeX is needed ([`mindMapMeasurements.ts`](frontend/src/stores/specLoader/mindMapMeasurements.ts)).

### Tests

- **Backend** — Module activity, `X-MG-Client` tracker source, mg_client sanitize/bind, Kitty hydrate mind-map extras.
- **Frontend** — Mind-map UID remap, live-spec extras, load preserve sides, reload style identity, underline drop-preview shapes.

## [5.148.0] - 2026-07-20

> **Document Summary `/api/doc-summary` surface, vision mind-map from conversation images, AI Brainstorm panel, Kitty structural edit chains, and Chrome extension v0.4.22 doc-summary persist.**

### Added

- **Document Summary API package** — Short-path router at `/api/doc-summary` (session, packages, documents) so canvas/clients use product URLs while persistence stays shared ([`routers/api/doc_summary/`](routers/api/doc_summary/), [`docSummaryApi.ts`](frontend/src/config/docSummaryApi.ts)).
- **Vision mind-map rebuild** — DashScope multimodal detect + structure rebuild for hand-drawn/photographed maps; applies to library and wakes desktop Kitty ([`vision_mindmap.py`](services/knowledge/vision_mindmap.py), [`vision_mindmap_apply.py`](services/knowledge/vision_mindmap_apply.py)).
- **Kitty conversation image REST** — `POST /api/kitty/conversation_image`: hand-drawn → canvas rebuild + outline extract; otherwise OCR → Document Summary ([`conversation_image.py`](services/knowledge/conversation_image.py), [`conversation_image_handler.py`](services/kitty/http/conversation_image_handler.py)).
- **Conversation image FE pipeline** — Capture/resize/upload shared by desktop Kitty and mobile ([`prepareConversationImageCapture.ts`](frontend/src/composables/kitty/prepareConversationImageCapture.ts), [`processConversationImageUpload.ts`](frontend/src/composables/kitty/processConversationImageUpload.ts)).
- **AI Brainstorm panel** — Side tool for staged AI suggestions on canvas, replacing Concept Parking Lot ([`AiBrainstormPanel.vue`](frontend/src/components/canvas/AiBrainstormPanel.vue), [`composables/aiBrainstorm/`](frontend/src/composables/aiBrainstorm/)).
- **Kitty structural mutation chain** — Sequential multi-edit one-sentence turns with safe command ordering ([`structural_chain.py`](services/kitty/routing/structural_chain.py), [`node_action_order.py`](services/kitty/routing/node_action_order.py)).
- **Quiet branch-complete batching** — Coalesce multi-branch auto-complete into one short chat reply ([`kittyQuietBranchCompleteBatch.ts`](frontend/src/composables/kitty/kittyQuietBranchCompleteBatch.ts)).
- **Subgraph apply queue** — Serial paste/persist + bounded parallel LLM fetches for multi-branch auto-complete ([`mindMapSubgraphApplyQueue.ts`](frontend/src/composables/editor/mindMapSubgraphApplyQueue.ts)).
- **Office / table extraction** — OOXML/CSV → markdown tables; LibreOffice path for legacy `.doc`/`.ppt`/`.xls` ([`document_office_extract.py`](services/knowledge/document_office_extract.py), [`markdown_tables.py`](services/knowledge/markdown_tables.py), [`legacy_office_convert.py`](services/knowledge/legacy_office_convert.py)).
- **Mind-map outline markdown** — Vision rebuild specs → Document Summary `extract.md` outline ([`mindmap_outline_md.py`](services/knowledge/mindmap_outline_md.py)).
- **Doc Summary limits & temp files** — Upload/input caps and short-lived binary temp under `doc_summary_tmp/` ([`doc_summary_limits.py`](services/knowledge/doc_summary_limits.py), [`doc_summary_temp.py`](services/knowledge/doc_summary_temp.py)).
- **Chat handoff cancel/revoke** — Cancel waiting codes; one waiting code per package; revoke on session end ([`chat_handoff_service.py`](services/knowledge/chat_handoff_service.py), [`useChatHandoff.ts`](frontend/src/composables/mindMap/useChatHandoff.ts)).
- **Canvas library open helper** — Shared confirm/navigate when opening another library diagram ([`canvasLibraryDiagramOpen.ts`](frontend/src/composables/canvasPage/canvasLibraryDiagramOpen.ts)).
- **Ephemeral session clear** — Shared Pinia/UI teardown for reset and leave-canvas ([`clearCanvasEphemeralSession.ts`](frontend/src/composables/canvasPage/clearCanvasEphemeralSession.ts)).
- **Document-content mind-map prompts** — Dedicated EN/ZH prompts for extracted docs vs web pages ([`prompts/mind_maps.py`](prompts/mind_maps.py)).
- **Chrome extension v0.4.22** — Persist captures into Document Summary via `/api/doc-summary` with package or new-session flow ([`background.js`](chrome-extension/background.js), [`popup.js`](chrome-extension/popup.js)).

### Changed

- **Clients → `/api/doc-summary`** — Canvas Document Summary UI, file-reader, and Chrome extension call the new prefix ([`useMindMapDocumentSummary.ts`](frontend/src/composables/mindMap/useMindMapDocumentSummary.ts), [`api_client.py`](clients/file-reader/file_reader/api_client.py)).
- **Default vision model** — `DASHSCOPE_VISION_MODEL` default `qwen3.7-plus` → `qwen3.6-flash` ([`knowledge_config.py`](config/knowledge_config.py), [`env.example`](env.example)).
- **COS Document Summary keys** — UUID-keyed objects under `documents/mindgraph/{uuid}.md`; access only via ownership-checked APIs ([`doc_summary_storage.py`](services/knowledge/doc_summary_storage.py)).
- **Doc Summary ingest/storage** — Harder session binding, storage-conflict codes, extracted-access probe, clearer package lifecycle.
- **Kitty WS `append_image` retired** — Inbound errors point clients to REST conversation image; WS module removed.
- **Canvas session reset** — Reset/leave paths use ephemeral clear + library-open decisions.
- **Waterfall tool shell** — Legacy waterfall panel mounts AI Brainstorm ([`MindMapWaterfallPanel.vue`](frontend/src/components/canvas/MindMapWaterfallPanel.vue)).
- **One-sentence / node-action routing** — Stronger heuristics and ordered structural vs auto-complete execution.

### Fixed

- **Chat handoff lifecycle** — Waiting codes revoked when cancelled or when minting a new code for the same package; oversized ingest returns 413.
- **Multi-branch Kitty UX** — Quiet batched completion and subgraph apply queue reduce chat spam and racey canvas applies.
- **Library diagram switch** — Confirm before replacing an already-open different diagram.
- **i18n key parity** — Synced Document Summary / Kitty photo / canvas-switch keys across all UI locale bundles (and rebuilt zh-TW from zh).
- **Kitty live-context typing** — Narrow `updated_at` before assigning into `lastAppliedUpdatedAt` so vue-tsc stays green ([`useKittyDesktopRemoteSync.ts`](frontend/src/composables/kitty/useKittyDesktopRemoteSync.ts)).

### Removed

- **Concept parking lot** — Composable and panel logic removed; replaced by AI Brainstorm.
- **Kitty WS image append path** — `services/kitty/ws/append_image.py` and FE `compressImageForKitty.ts` removed in favor of HTTP vision upload.

### Tests

- **Backend** — Vision mindmap, conversation image, doc-summary session/binding/clear/sync/limits/temp/storage-conflict/packages/extracted-access, office extract, markdown tables, outline md, structural chain, node-action order, chat-handoff revoke, Chrome doc-summary persist, content mindmap prompts.
- **Frontend** — Canvas library open, Kitty quiet branch batch, subgraph apply queue, conversation image upload, Document Summary accept, chat handoff, and related canvas/Kitty specs.

## [5.147.0] - 2026-07-15

> **Public dashboard embedded in admin, feature-flag hot reload, COS mirrors for GeoLite/AbuseIPDB, and Showcase router package layout.**

### Added

- **Public dashboard in admin** — China-map analytics live under Admin → Settings → 全国数据中心; super-admin capability `tab.settings.public_dashboard`; legacy `/dashboard`, `/dashboard/login`, and `/pub-dash` redirect to the admin URL; separate dashboard login/session flow removed ([`AdminPublicDashboardTab.vue`](frontend/src/components/admin/AdminPublicDashboardTab.vue), [`usePublicDashboard.ts`](frontend/src/composables/dashboard/usePublicDashboard.ts)).
- **Feature-flag hot reload** — HTTP `feature_flag_gate` middleware returns 404 when admin toggles features off without restart; routers stay mounted at startup; cross-worker `.env` reload via Redis pub/sub on admin `reload-runtime` ([`feature_gate.py`](services/infrastructure/http/feature_gate.py), [`env_reload_fanout.py`](services/infrastructure/sync/env_reload_fanout.py)).
- **COS security asset mirrors** — GeoLite2-Country MMDB and AbuseIPDB blocklist publisher/consumer sync via Tencent COS; one-shot CLI [`scripts/db/publish_blocklists_to_cos.py`](scripts/db/publish_blocklists_to_cos.py).
- **Showcase approval gates** — Teaching designs require an attachment; diagram cases require resolved gallery uploads before approve ([`test_showcase_lifecycle_gates.py`](tests/test_showcase_lifecycle_gates.py)).
- **Showcase pg-merge remap** — `case_square_*` tables registered for phone-based user FK remap in stack merge ([`test_pg_merge_showcase_remap.py`](tests/test_pg_merge_showcase_remap.py)).

### Changed

- **Showcase router package** — Feature routers reorganized into package folders (`routers/features/showcase/`, `community/`, etc.); admin showcase routes colocated under [`routers/features/showcase/admin.py`](routers/features/showcase/admin.py).
- **Public dashboard auth** — Short-lived admin capability dependency replaces dashboard session manager; [`dashboard_session.py`](services/monitoring/dashboard_session.py) removed.
- **Vite 8 HMR** — `server.hmr.host` set to `localhost` when binding `0.0.0.0` for WSL/LAN dev ([`vite.config.ts`](frontend/vite.config.ts)).

### Tests

- **CI** — [`test_public_dashboard_e2e.py`](tests/test_public_dashboard_e2e.py), [`test_feature_flag_hot_reload.py`](tests/test_feature_flag_hot_reload.py), [`test_showcase_cos_live_matrix.py`](tests/test_showcase_cos_live_matrix.py), [`test_abuseipdb_cos_sync.py`](tests/services/test_abuseipdb_cos_sync.py), [`test_geolite_cos_sync.py`](tests/services/test_geolite_cos_sync.py); smoke [`scripts/smoke_public_dashboard_live.py`](scripts/smoke_public_dashboard_live.py).

## [5.146.1] - 2026-07-14

> **Showcase pylint docstring fix so GitHub CI treats convention score as green.**

### Fixed

- **Pylint C0116** — Added missing function docstrings in Showcase audit, field options, post delete, and staff permissions modules so CI exits 0 (score 10.00 alone was not enough on Actions).

## [5.146.0] - 2026-07-14

> **Showcase private COS uploads, Kitty-style control plane, workflow logging, and COS↔DB reconcile.**

### Added

- **Showcase COS media** — Private bucket with short-TTL browser PUT/GET; Postgres stores keys only under `showcase/posts/{id}/…`; create is metadata-only when COS is on, then `uploads/init` → PUT → `uploads/complete` with Redis anti-swap grants ([`services/showcase/storage/`](services/showcase/storage/), [`routers/features/showcase_routes_uploads.py`](routers/features/showcase_routes_uploads.py)).
- **Showcase package layout** — Kitty-style domain modules: `storage/`, `uploads/`, `posts/`, `sync/`, `infra/` plus package README ([`services/showcase/README.md`](services/showcase/README.md)).
- **Workflow logging** — `SHOWCASE_WF` stages via `showcase_wf_log` / `showcase_extra` (create, upload, download, withdraw/delete, sync); disable with `SHOWCASE_WORKFLOW_TRACE=0` ([`services/showcase/infra/observability.py`](services/showcase/infra/observability.py)).
- **COS ↔ DB sync** — Inventory/reconcile report (`matched`, `orphan_cos`, `missing_in_cos`, `unscoped`); admin status/reconcile/purge-orphans APIs (purge dry-run by default); CLI [`scripts/showcase_cos_reconcile.py`](scripts/showcase_cos_reconcile.py).
- **Publish progress UX** — Loading toast + submit-button phase labels through create/upload; clearer upload-failure messages with draft rollback ([`submitPublishShowcasePost.ts`](frontend/src/composables/showcase/submitPublishShowcasePost.ts)).
- **Detail action busy state** — Approve/reject/withdraw/delist/like/favorite/recommend disable while in flight with success/error toasts.

### Changed

- **Download AuthZ** — Asset membership uses collected post keys only (no prefix leak); COS downloads 302 to short GET.
- **Partial-publish safety** — Failed post-create uploads withdraw the draft and delete assets.
- **Env** — Shared Tencent secrets document COS Showcase flags in [`env.example`](env.example); `COS_SHOWCASE_ENABLED` defaults on when credentials exist.

### Tests

- **CI** — [`test_showcase_storage_cos.py`](tests/test_showcase_storage_cos.py), [`test_showcase_e2e_smoke.py`](tests/test_showcase_e2e_smoke.py) (local E2E always; live COS when `COS_SHOWCASE_SMOKE=1`).

## [5.145.0] - 2026-07-14

> **Showcase gallery and diagram archive folders, with Alembic 0084–0088 and security hardening.**

### Added

- **Showcase** — Moderated public gallery for teaching designs, diagram cases, and diagram templates (`FEATURE_SHOWCASE`, migrations `0084`–`0087`, `/api/showcase`). Browse with filters, likes, favorites, expert recommendations; authors publish via modal; admin moderation, field options, and staff grants. Default **on** via feature flag.
- **Diagram archive folders** — Always-on sidebar folders (`0088`, `/api/diagram-folders`) with create/rename/delete and diagram move.
- **Authenticated Showcase assets** — Files served via `/api/showcase/assets/...` (author/staff for non-approved; any auth user for approved). Direct `/static/case_square/` access is blocked.

### Security

- **Multipart body-limit bypass** — Streaming body limit now applies to multipart when `Content-Length` is absent (path-scoped 105MB only for Showcase publish routes).
- **Admin feature gate** — `/api/auth/admin/showcase` requires `FEATURE_SHOWCASE`.
- **Staff edit policy** — Staff may edit pending/rejected posts only (approved posts are immutable via the edit API).
- **Upload magic-byte checks** — Docs, images, videos, and `.mg` sources validated beyond extension/size.

### Changed

- **CSP** — `frame-src` includes Office Online viewer for teaching-doc preview; `worker-src` / `media-src` retained from main.
- **Router size** — Showcase backend split into feed/posts/actions/common modules; publish modal script extracted to composables.
- **Rename** — Case Square → Showcase across modules, routes, and UI (`FEATURE_SHOWCASE`); School Zone (学校专区) removed.

### Tests

- **CI** — [`test_showcase_create_response.py`](tests/test_showcase_create_response.py), [`test_diagram_folders_api.py`](tests/test_diagram_folders_api.py) (incl. folder IDOR negative); extended security hardening tests.

## [5.144.0] - 2026-07-14

> **Mind map slide show with traversal modes and focus dimming, B&W export wireframe wired to nodes and edges, inline-edit Enter sibling guard, and presentation toolbar polish.**

### Added

- **Mind map slide traversal modes** — Overview plus **first-level branches** or **deep traversal** slides; breadcrumb path per slide ([`mindMapSlides.ts`](frontend/src/utils/mindMapSlides.ts), [`useMindMapSlidePresentation.ts`](frontend/src/composables/mindMap/useMindMapSlidePresentation.ts)).
- **Slide show HUD** — Compact bottom dock with progress bar (click to jump), prev/next/first/last, auto-play with fill progress, traversal toggle, collapsible handle, and icon-only exit back to presentation mode ([`MindMapSlideOverlay.vue`](frontend/src/components/canvas/MindMapSlideOverlay.vue)).
- **Slide focus visuals** — Blue outline on the active slide node; non-focus nodes and branch edges dimmed during branch slides ([`useDiagramCanvasNodesEdges.ts`](frontend/src/composables/diagramCanvas/useDiagramCanvasNodesEdges.ts), [`diagramCanvas.css`](frontend/src/components/diagram/diagramCanvas.css)).
- **Slide navigation** — Keyboard (Space, arrows, Home/End), click canvas to advance, and auto-play countdown ([`useMindMapSlidePresentation.ts`](frontend/src/composables/mindMap/useMindMapSlidePresentation.ts)).
- **Inline-edit Enter guard** — Post-commit sibling anchor and frame guard so Enter after double-click edit adds a sibling on the edited branch instead of re-opening edit or mis-selecting ([`mindMapCanvasEnterGuard.ts`](frontend/src/composables/mindMap/mindMapCanvasEnterGuard.ts)).

### Changed

- **Slide show state restore** — Snapshot viewport and collapsed-branch paths on enter; restore on exit slides (stay in presentation mode) ([`useMindMapSlidePresentation.ts`](frontend/src/composables/mindMap/useMindMapSlidePresentation.ts), [`useDiagramCanvasEventBus.ts`](frontend/src/composables/diagramCanvas/useDiagramCanvasEventBus.ts)).
- **Presentation side toolbar** — Right toolbar slides out while slide show is active and returns when slides end ([`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue)).
- **Mind map export B&W** — Wireframe outline styles now apply to topic/branch nodes, underline bars, and orthogonal edges during raster export ([`BranchNode.vue`](frontend/src/components/diagram/nodes/BranchNode.vue), [`TopicNode.vue`](frontend/src/components/diagram/nodes/TopicNode.vue), [`MindMapOrthogonalEdge.vue`](frontend/src/components/diagram/edges/MindMapOrthogonalEdge.vue)).

### Fixed

- **Slide exit edge dimming** — `mind-map-slide-edge-dimmed` is stripped from every edge when leaving slide show so connectors no longer stay faded ([`useDiagramCanvasNodesEdges.ts`](frontend/src/composables/diagramCanvas/useDiagramCanvasNodesEdges.ts)).
- **Mind map B&W export** — Color/wireframe toggle in the export dropdown now affects PNG, SVG, and PDF output (styles were implemented but not connected to renderers).

### Tests

- **Frontend** — [`mindMapSlides.spec.ts`](frontend/tests/mindMapSlides.spec.ts), [`mindMapCanvasEnterGuard.spec.ts`](frontend/tests/mindMapCanvasEnterGuard.spec.ts), [`mindMapCollapseOverlayTarget.spec.ts`](frontend/tests/mindMapCollapseOverlayTarget.spec.ts), [`mindMapEditSiblingSelection.spec.ts`](frontend/tests/mindMapEditSiblingSelection.spec.ts), [`mindMapUndoRedo.spec.ts`](frontend/tests/mindMapUndoRedo.spec.ts), [`canvasExportVisualMode.spec.ts`](frontend/tests/canvasExportVisualMode.spec.ts); extended [`mindMapNodeIdRemap.spec.ts`](frontend/tests/mindMapNodeIdRemap.spec.ts).

## [5.143.1] - 2026-07-14

> **CI hygiene on main: Ruff format, Kitty ephemeral-scope i18n parity, and document review-annotation removal.**

### Removed

- **Kitty diagram review annotations** — Dropped review-annotation messaging, routing, and canvas bus wiring from the tip of 5.143.0 ([`services/kitty/diagram/`](services/kitty/diagram/), canvas Kitty composables).

### Fixed

- **Ruff format drift** — Reformatted Kitty session/messaging modules and open-canvas owner tests that failed `ruff format --check` on CI.
- **i18n key parity** — Propagated `mobile.kittyEphemeralScopePinned` / `mobile.kittyEphemeralScopeDegraded` plus remaining Kitty scope/create keys and canvas one-sentence strings to all UI locale bundles.

### Changed

- **Kitty README socket model** — Document mobile + desktop canvas-owner coexistence on the same scope (same-lane replace only).
- **Kitty diagram package docstring** — Removed stale “review annotations” wording.

## [5.143.0] - 2026-07-13

> **Kitty open_canvas session scope: desktop adopts mobile ephemeral SoT, Redis canvas-owner presence lease, and fail-closed `no_owner` when verified edits have no desktop owner.**

### Added

- **open_canvas `session_scope`** — Mobile voice `open_canvas` and desktop action queue carry the ephemeral Kitty scope so desktop adopts the same SoT ([`command_router.py`](services/kitty/routing/command_router.py), [`kitty_desktop_action_queue.py`](services/kitty/infra/desktop/kitty_desktop_action_queue.py), [`kittyDesktopActionHandlers.ts`](frontend/src/composables/kitty/kittyDesktopActionHandlers.ts)).
- **Desktop scope adoption** — `adoptOpenCanvasSessionScope` + `kitty_scope` route query bind one-sentence ephemeral scope; dirty-canvas confirm before jump ([`applyCanvasKittySeedFromRoute.ts`](frontend/src/composables/canvasPage/applyCanvasKittySeedFromRoute.ts), [`oneSentence.ts`](frontend/src/stores/oneSentence.ts)).
- **Canvas-owner presence lease** — Redis `kitty:canvas_owner_presence:{user_id}:{scope}` marks live desktop owner WS; cleared on session end ([`kitty_canvas_owner_presence.py`](services/kitty/infra/desktop/kitty_canvas_owner_presence.py), [`lifecycle.py`](services/kitty/ws/lifecycle.py), [`ops.py`](services/kitty/session/ops.py)).
- **Canvas-owner reconnect** — Debounced WS reconnect on `voice:ws_closed` and tab visibility return ([`useKittyCanvasOwnerAgent.ts`](frontend/src/composables/kitty/useKittyCanvasOwnerAgent.ts)).
- **Clearer connect-failure copy** — `kittyConnectFailed` when canvas-owner WS cannot connect ([`en/canvas.ts`](frontend/src/locales/messages/en/canvas.ts), [`zh/canvas.ts`](frontend/src/locales/messages/zh/canvas.ts)).

### Changed

- **Desktop pairing scope SoT** — Ephemeral scope comes from `oneSentence.diagramScope` instead of a per-tab random UUID ([`useCanvasKittyDesktopPairing.ts`](frontend/src/composables/kitty/useCanvasKittyDesktopPairing.ts)).
- **Canvas Kitty remote sync scope** — `kittyOwnerScope` uses library id or shared ephemeral scope for voice phase, selection, LLM model, live_spec, and canvas-owner agent ([`CanvasPage.vue`](frontend/src/pages/CanvasPage.vue)).

### Fixed

- **Verified edit `ack_timeout` / scope mismatch** — `canvas_owner_available` checks process-local owner WS plus Redis presence; mobile verified edits fail closed with `no_owner` instead of waiting when no desktop owner exists ([`canvas_owner.py`](services/kitty/session/canvas_owner.py), [`messaging.py`](services/kitty/context/messaging.py)).

### Tests

- **Backend** — [`test_kitty_open_canvas_owner_e2e.py`](tests/test_kitty_open_canvas_owner_e2e.py); extended [`test_kitty_cross_worker_canvas_owner.py`](tests/test_kitty_cross_worker_canvas_owner.py), [`test_kitty_voice_command_router.py`](tests/test_kitty_voice_command_router.py).
- **Frontend** — [`kittyDesktopOpenCanvasScope.spec.ts`](frontend/tests/kittyDesktopOpenCanvasScope.spec.ts).

## [5.142.0] - 2026-07-12

> **Kitty mobile ↔ desktop cross-device sync: bidirectional selection and LLM model, live-context poll, voice-phase FAB, one-sentence desktop lock while phone Kitty is active, and mobile chat transcript.**

### Added

- **Cross-device sync contract** — Documented mobile ↔ desktop pairing domains (scope, selection, LLM model, live_spec, voice phase, chat turns) in [`services/kitty/README.md`](services/kitty/README.md).
- **Bidirectional selection sync** — Desktop `PUT /api/kitty/selection/{scope}` pushes chips to mobile WS; mobile `context_update` fans out to desktop SSE ([`kitty_selection_push.py`](services/kitty/infra/desktop/kitty_selection_push.py), [`useKittyDesktopSelectionPublish.ts`](frontend/src/composables/kitty/useKittyDesktopSelectionPublish.ts)).
- **Bidirectional LLM model sync** — `PUT /api/kitty/llm_model/{scope}` + WS/SSE so canvas and phone pills stay aligned ([`kitty_llm_model_push.py`](services/kitty/infra/desktop/kitty_llm_model_push.py), [`useKittyDesktopLlmModelPublish.ts`](frontend/src/composables/kitty/useKittyDesktopLlmModelPublish.ts), [`applyKittyRemoteLlmModel.ts`](frontend/src/composables/kitty/applyKittyRemoteLlmModel.ts), [`KittyMobileLlmModelRow.vue`](frontend/src/components/kitty/KittyMobileLlmModelRow.vue)).
- **Live-context snapshot / put** — `GET`/`PUT /api/kitty/live_context/{scope}` plus mobile poll so phone chips stay honest after desktop canvas edits ([`handlers.py`](services/kitty/http/handlers.py), [`useMobileKittyLiveContextPoll.ts`](frontend/src/composables/kitty/useMobileKittyLiveContextPoll.ts), [`useKittyDesktopLiveSpecPublish.ts`](frontend/src/composables/kitty/useKittyDesktopLiveSpecPublish.ts)).
- **Voice-phase FAB fanout** — Mobile listening/speaking phase publishes to desktop SSE ([`kitty_voice_phase_fanout.py`](services/kitty/infra/desktop/kitty_voice_phase_fanout.py), [`useKittyDesktopVoicePhase.ts`](frontend/src/composables/kitty/useKittyDesktopVoicePhase.ts)).
- **Desktop one-sentence lock** — When Mobile Kitty holds the same library scope, desktop one-sentence *edit* input yields to the phone (create/generate stays on desktop) ([`desktopOneSentenceMobileKittyLock.ts`](frontend/src/composables/canvasToolbar/desktopOneSentenceMobileKittyLock.ts)).
- **Mobile Kitty chat transcript** — Shared one-sentence turns UI on `/m/kitty` with hydrate on scope change ([`KittyMobileChatTranscript.vue`](frontend/src/components/kitty/KittyMobileChatTranscript.vue), [`useMobileKittyChat.ts`](frontend/src/composables/mobile/useMobileKittyChat.ts)).
- **Mobile photo capture prep** — Shared helper for Kitty photo capture flow ([`prepareMobileKittyPhotoCapture.ts`](frontend/src/composables/mobile/prepareMobileKittyPhotoCapture.ts)).

### Changed

- **Mobile Kitty page** — Pairing, library pick, LLM row, chat transcript, and mic PTT refactored onto focused composables ([`MobileKittyPage.vue`](frontend/src/pages/mobile/MobileKittyPage.vue), [`useMobileKittyPairing.ts`](frontend/src/composables/kitty/useMobileKittyPairing.ts)).
- **Desktop Kitty remote sync** — Canvas anchor / remote sync publish selection, live_spec, LLM model, and consume wake/selection/voice-phase SSE ([`KittyCanvasAnchor.vue`](frontend/src/components/kitty/KittyCanvasAnchor.vue), [`useKittyDesktopRemoteSync.ts`](frontend/src/composables/kitty/useKittyDesktopRemoteSync.ts)).
- **Click wheel / diagram children** — Cleaner iPod wheel wiring and richer child-node resolution for selection chips ([`KittyIpodClickWheel.vue`](frontend/src/components/kitty/KittyIpodClickWheel.vue), [`kittyDiagramChildren.ts`](frontend/src/composables/kitty/kittyDiagramChildren.ts)).
- **Desktop wake fanout** — Extended Redis pub/sub payloads for diagram_update, selection, and LLM model ([`kitty_desktop_wake_fanout.py`](services/kitty/infra/desktop/kitty_desktop_wake_fanout.py)).
- **Fun-ASR / session bridge** — Hardening around realtime ASR and audio session lifecycle ([`fun_asr_realtime.py`](services/kitty/asr/fun_asr_realtime.py), [`session_bridge.py`](services/kitty/audio/session_bridge.py)).

### Removed

- **Kitty desktop workflow debug UI** — Dropped debug log panel and composable ([`KittyDesktopWorkflowDebugLog.vue`](frontend/src/components/kitty/KittyDesktopWorkflowDebugLog.vue), [`useKittyDesktopWorkflowDebug.ts`](frontend/src/composables/kitty/useKittyDesktopWorkflowDebug.ts)).

### Tests

- **Backend** — Extended [`test_kitty_cross_device_sync.py`](tests/test_kitty_cross_device_sync.py), [`test_kitty_hub_contract.py`](tests/test_kitty_hub_contract.py), [`test_kitty_fun_asr_cosyvoice.py`](tests/test_kitty_fun_asr_cosyvoice.py).
- **Frontend** — [`desktopOneSentenceMobileKittyLock.spec.ts`](frontend/tests/desktopOneSentenceMobileKittyLock.spec.ts), [`kittyLlmModelSync.spec.ts`](frontend/tests/kittyLlmModelSync.spec.ts), [`useKittyDesktopSelectionPublish.spec.ts`](frontend/tests/useKittyDesktopSelectionPublish.spec.ts), [`useMobileKittyChat.spec.ts`](frontend/tests/useMobileKittyChat.spec.ts), [`useMobileKittyLiveContextPoll.spec.ts`](frontend/tests/useMobileKittyLiveContextPoll.spec.ts), [`useMobileKittyMicPtt.spec.ts`](frontend/tests/useMobileKittyMicPtt.spec.ts), [`useMobileKittyPairingContext.spec.ts`](frontend/tests/useMobileKittyPairingContext.spec.ts), [`prepareMobileKittyPhotoCapture.spec.ts`](frontend/tests/prepareMobileKittyPhotoCapture.spec.ts); extended [`kittyChildNodeResolution.spec.ts`](frontend/tests/kittyChildNodeResolution.spec.ts).

## [5.141.0] - 2026-07-11


> **Verified diagram-edit tool + Command Bus, Kitty Fun-ASR/CosyVoice voice I/O, one-sentence node-action edits, admin expert org scope and role filter, post-deploy stale-chunk reload, and LLM timeout preservation.**

### Added

- **Diagram Edit Tool** — Agent-driven mindmap mutations with verified canvas ack (`applied` only after owning tab proves the effect): schema, executor, pending futures, postcondition verify, mindmap handlers, and `CanvasTransport` / `KittyWsTransport` ([`services/diagram_edit/`](services/diagram_edit/), [`docs/architecture/diagram_edit_tool.md`](docs/architecture/diagram_edit_tool.md)).
- **Diagram Command Bus spine** — Single front door in `services/agent_hub/diagram_spine/` (policy, Bus, origins); Kitty adapter routes verified edits; FE apply via `registerKittyDiagramMutationBus` + Hub persist ack (`hub_persist_ok` + `hub_revision`) ([`diagramEditApply.ts`](frontend/src/composables/kitty/diagramEditApply.ts), [`diagramEditHubPersist.ts`](frontend/src/composables/kitty/diagramEditHubPersist.ts)).
- **Kitty Fun-ASR + CosyVoice** — Text-first voice I/O on shared DashScope MaaS realtime WebSocket (mic PCM processor + CosyVoice TTS); Omni duplex not used for Kitty commands ([`services/kitty/asr/`](services/kitty/asr/), [`services/kitty/tts/`](services/kitty/tts/), [`useKittyFunAsrMic.ts`](frontend/src/composables/kitty/useKittyFunAsrMic.ts)).
- **One-sentence node-action agent** — Structural edit parse (`update_center` / `add_node` / `update_node` / `delete_node`) with library tools, pending branch autocomplete / clarify options, and edit heuristics ([`node_action_agent.py`](services/kitty/routing/node_action_agent.py), [`node_action_library.py`](services/kitty/routing/node_action_library.py)).
- **One-sentence session depth** — Command-detail + turn `request_id` migrations; memory hydrate; richer turn/activity tracking ([`rev_0082`](alembic/versions/rev_0082_kitty_one_sentence_turn_request_id.py), [`rev_0083`](alembic/versions/rev_0083_kitty_one_sentence_command_detail.py), [`one_sentence_memory_hydrate.py`](services/kitty/session/one_sentence_memory_hydrate.py)).
- **DashScope workspace URLs** — Central endpoint builders for legacy vs workspace MaaS domains when `DASHSCOPE_WORKSPACE_ID` is set ([`dashscope_urls.py`](config/dashscope_urls.py), [`dashscope_endpoint_config.py`](config/dashscope_endpoint_config.py)).
- **Expert organizations tab (invite scope)** — Experts with `scope.invited_orgs` can view organizations they created, open insights-mode school dialogs, and create schools when invite/org edit caps allow ([`admin_panel_permissions.py`](utils/auth/admin_panel_permissions.py), [`adminCapabilities.ts`](frontend/src/utils/adminCapabilities.ts), [`AdminSchoolsTab.vue`](frontend/src/components/admin/AdminSchoolsTab.vue)).
- **Admin user role filter** — Canonical role query param (with legacy slug matching) plus toolbar role select on the Users tab ([`users.py`](routers/auth/admin/users.py), [`db_roles_for_canonical_filter`](utils/auth/role_constants.py), [`AdminUsersHeaderToolbar.vue`](frontend/src/components/admin/AdminUsersHeaderToolbar.vue)).
- **Org member role sort** — School/org member lists order by 超级管理员 → 学校管理员 → 专家 → 教研员 → 学校版, then newest ([`admin_user_role_sort.py`](services/auth/admin_user_role_sort.py)).
- **Stale chunk / PWA reload** — Detect Vite dynamic-import and CSS preload failures after deploy; one-shot hard reload with cooldown; PWA `onNeedRefresh` reloads ([`staleChunkReload.ts`](frontend/src/utils/staleChunkReload.ts)).
- **BrowserUnavailableError** — Playwright missing-binary / launch failures map to a typed error; PNG/DingTalk generation returns 503 with `browser_unavailable` ([`browser.py`](services/infrastructure/utils/browser.py), [`png_export.py`](routers/api/png_export.py)).
- **Safe UUID + focus helpers** — `safeRandomUUID` for older WebViews / non-secure contexts; guarded `focusHtmlControl` / `selectHtmlControl` ([`safeRandomUUID.ts`](frontend/src/utils/safeRandomUUID.ts), [`focusHtmlControl.ts`](frontend/src/utils/focusHtmlControl.ts)).
- **App QueryClient holder** — Pinia auth and other non-setup code resolve Vue Query via [`appQueryClient.ts`](frontend/src/utils/appQueryClient.ts) instead of `useQueryClient()` outside injection context.
- **Test-server watermark** — Optional banner/watermark for non-production frontends ([`TestServerWatermark.vue`](frontend/src/components/common/TestServerWatermark.vue), [`testServerBanner.ts`](frontend/src/utils/testServerBanner.ts)).

### Changed

- **Kitty command router** — Richer routing into verified diagram-edit / node-action paths, ack phrase pools, and write-lock vs LLM generate ([`command_router.py`](services/kitty/routing/command_router.py)).
- **Org trends auth** — Token-trend reads allow data-center global readers or organizations-tab readers with global/invited scope ([`require_organization_trends_read`](routers/auth/dependencies.py)).
- **Kitty desktop poll leader** — Elect a poll leader only when the surface is eligible to poll (auth + feature + non-mobile / non-headless); tear down when ineligible ([`useKittyDesktopActionPoll.ts`](frontend/src/composables/kitty/useKittyDesktopActionPoll.ts)).
- **Error monitoring DB sessions** — Alert dispatch, error collector, and retention purge use `system_rls_session` ([`alert_dispatcher.py`](services/monitoring/alert_dispatcher.py), [`error_collector.py`](services/monitoring/error_collector.py), [`error_retention_scheduler.py`](services/monitoring/error_retention_scheduler.py)).
- **Chromium diagnostics** — Startup launch probe logs clear install guidance when Playwright Chromium cannot start.
- **LLM / DashScope clients** — Shared HTTP client manager and workspace-aware endpoint resolution across chat, embedding, rerank, Omni, and realtime TTS ([`http_client_manager.py`](clients/llm/http_client_manager.py), [`dashscope.py`](clients/llm/dashscope.py)).

### Fixed

- **LLM timeouts** — Chat / stream pipeline re-raises `LLMTimeoutError` instead of wrapping as generic `LLMServiceError` ([`services/llm/__init__.py`](services/llm/__init__.py)); diagram generation surfaces timeout distinctly ([`diagram_generation.py`](routers/api/diagram_generation.py)).
- **Frontend error noise** — Skip reporting ResizeObserver loops, opaque `Script error.`, and stale-chunk load failures ([`frontendLog.ts`](frontend/src/utils/frontendLog.ts)).
- **Kitty event handlers** — Session event bus catches database errors from handlers without aborting the bus ([`events.py`](services/kitty/session/events.py)).
- **Canvas / MindMate robustness** — Safer focus/select and UUID usage across inline edit, edges, outline, MindMate input/bubbles, live subtitle/translation, and collab outbound queue.

### Tests

- **Backend** — [`test_diagram_edit.py`](tests/test_diagram_edit.py), [`test_diagram_command_bus.py`](tests/test_diagram_command_bus.py), [`test_one_sentence_verified_edit_flow.py`](tests/test_one_sentence_verified_edit_flow.py), [`test_kitty_fun_asr_cosyvoice.py`](tests/test_kitty_fun_asr_cosyvoice.py), [`test_node_action_*.py`](tests/), [`test_role_filter_slugs.py`](tests/auth/test_role_filter_slugs.py), [`test_browser_unavailable.py`](tests/test_browser_unavailable.py), [`test_llm_timeout_raise.py`](tests/test_llm_timeout_raise.py), [`test_dashscope_urls.py`](tests/test_dashscope_urls.py); extended admin org-scope and one-sentence session tests.
- **Frontend** — [`diagramEditApply.spec.ts`](frontend/tests/diagramEditApply.spec.ts), [`diagramEditHubPersist.spec.ts`](frontend/tests/diagramEditHubPersist.spec.ts), [`focusAndChunkReload.spec.ts`](frontend/tests/focusAndChunkReload.spec.ts), [`safeRandomUUID.spec.ts`](frontend/tests/safeRandomUUID.spec.ts), [`oneSentence*.spec.ts`](frontend/tests/); extended [`adminCapabilities.spec.ts`](frontend/tests/adminCapabilities.spec.ts), [`frontendLog.spec.ts`](frontend/tests/frontendLog.spec.ts).

## [5.140.0] - 2026-07-09

> **Mind map one-sentence Kitty chat with persisted turns, node learning notes, hierarchical clipboard, Document Summary lite ingest, branch-expand AI subgraphs, and canvas diagram-type switching.**

### Added

- **One-sentence generate → Kitty chat panel** — Text-only chat UI with Kitty avatar; first message generates the diagram, follow-ups route to Kitty for edits ([`MindMapOneSentencePanel.vue`](frontend/src/components/canvas/MindMapOneSentencePanel.vue), [`OneSentenceKittyAvatar.vue`](frontend/src/components/canvas/OneSentenceKittyAvatar.vue), [`useMindMapOneSentenceChat.ts`](frontend/src/composables/canvasToolbar/useMindMapOneSentenceChat.ts), [`one_sentence_text_reply.py`](services/kitty/session/one_sentence_text_reply.py)).
- **One-sentence session persistence** — Chat turns stored in Redis + PostgreSQL with REST list/get/append and scope migration ([`one_sentence_turns.py`](services/kitty/session/one_sentence_turns.py), [`one_sentence_session_pg.py`](services/kitty/session/one_sentence_session_pg.py), Alembic [`rev_0078`](alembic/versions/rev_0078_kitty_one_sentence_turns.py)–[`0081`](alembic/versions/rev_0081_rls_kitty_one_sentence_sessions.py), [`kitty_routes.py`](routers/features/kitty/kitty_routes.py)).
- **Mind map node learning note** — Context-menu action opens explain modal; Kitty streams educational reflection on a selected node via SSE ([`MindMapNodeExplainModal.vue`](frontend/src/components/canvas/MindMapNodeExplainModal.vue), [`node_explain.py`](agents/mind_maps/node_explain.py), [`mindmap_node_explain.py`](routers/mindmap_node_explain.py), [`useMindMapNodeExplain.ts`](frontend/src/composables/mindMap/useMindMapNodeExplain.ts)).
- **Hierarchical clipboard** — Structure-aware copy/cut/paste for mind map branches, tree map, brace map, and flow map; paste anchors onto a target node ([`hierarchicalClipboardExtract.ts`](frontend/src/stores/diagram/hierarchicalClipboardExtract.ts), [`hierarchicalClipboardPaste.ts`](frontend/src/stores/diagram/hierarchicalClipboardPaste.ts), [`copyPaste.ts`](frontend/src/stores/diagram/copyPaste.ts)).
- **Document Summary lite** — Extract-only ingest: upload Word/PDF/PPT/images/audio, store extracted markdown to COS, skip RAG/wiki indexing ([`doc_summary_ingest.py`](services/knowledge/doc_summary_ingest.py), [`doc_summary_storage.py`](services/knowledge/doc_summary_storage.py), [`docSummaryLite.ts`](frontend/src/config/docSummaryLite.ts)).
- **Mind map branch-expand API** — Dedicated LLM path for expanding one branch with 4–6 direct children using topic/reference/sibling context ([`mind_map_agent.py`](agents/mind_maps/mind_map_agent.py), [`workflow.py`](agents/core/workflow.py), [`prompts/mind_maps.py`](prompts/mind_maps.py)).
- **AI subgraph generation (canvas)** — Floating toolbar / context menu generates child nodes for a branch; accept/discard preview flow ([`useMindMapSubgraphSuggest.ts`](frontend/src/composables/editor/useMindMapSubgraphSuggest.ts), [`mindMapSubgraphContext.ts`](frontend/src/utils/mindMapSubgraphContext.ts), [`BranchNode.vue`](frontend/src/components/diagram/nodes/BranchNode.vue)).
- **Diagram type switching from natural language** — Detect diagram type aliases in one-sentence prompts and switch pristine canvas while preserving topic seed ([`diagramTypeFromPrompt.ts`](frontend/src/composables/canvasPage/diagramTypeFromPrompt.ts), [`switchCanvasDiagramType.ts`](frontend/src/composables/canvasPage/switchCanvasDiagramType.ts)).
- **Kitty acknowledgment library** — Centralized zh/en ack templates for diagram commands, low-confidence, and unsupported types ([`services/kitty/ack/`](services/kitty/ack/), [`kitty_unsupported_diagram_types.py`](services/kitty/infra/bootstrap/kitty_unsupported_diagram_types.py)).
- **Canvas LLM model resolution** — Subgraph and related flows honor the user's selected model via [`resolveDiagramLlmModel.ts`](frontend/src/utils/resolveDiagramLlmModel.ts).
- **Node palette multi-model batches** — Callers can pass `llm_models` to limit which LLMs run in palette generation ([`base_palette_generator.py`](agents/node_palette/base_palette_generator.py)).

### Changed

- **One-sentence panel UX** — Chat-style message list with streaming Kitty replies, collab-aware input blocking, and automatic scope migration when the diagram is saved to the library.
- **Document Summary panel** — Lite mode defaults to file upload; simplified status copy; sidebar hides Knowledge Space nav while lite mode is on ([`MindMapDocumentSummaryPanel.vue`](frontend/src/components/canvas/MindMapDocumentSummaryPanel.vue), [`useAppSidebar.ts`](frontend/src/composables/sidebar/useAppSidebar.ts)).
- **Knowledge package API** — `doc_summary` packages report wiki/RAG as disabled; ingest uses extract-only pipeline ([`packages.py`](routers/api/knowledge_space/packages.py)).
- **Kitty command router** — Richer routing, ack emission, unsupported-diagram handling, and text-only one-sentence conversational path ([`command_router.py`](services/kitty/routing/command_router.py)).
- **Subgraph merge pipeline** — Direct-children-only merge, debug logging, and context collection refactored ([`mindMapSubgraphMerge.ts`](frontend/src/utils/mindMapSubgraphMerge.ts), [`mindMapOps.ts`](frontend/src/stores/diagram/mindMapOps.ts)).
- **Save / keyboard guards** — Save blocked while AI subgraph is generating; subgraph preview must be accepted or discarded before save ([`diagramSaveFeedback.ts`](frontend/src/composables/editor/diagramSaveFeedback.ts)).

### Fixed

- **Clipboard paste semantics** — Paste attaches hierarchical content to the context node instead of dropping flat copies at canvas coordinates.
- **Subgraph generation quality** — Branch expand sends explicit branch context to avoid duplicate children and deep nesting.
- **Collab + AI** — Node explain and one-sentence flows respect live-collaboration AI blocks.
- **Kitty unsupported diagram requests** — Clear fallback when users ask for unsupported types (e.g. fishbone) instead of failing silently.

### Tests

- **Backend** — [`test_kitty_one_sentence_*.py`](tests/), [`test_one_sentence_text_reply.py`](tests/test_one_sentence_text_reply.py), [`test_doc_summary_ingest.py`](tests/test_doc_summary_ingest.py), [`test_doc_summary_storage.py`](tests/test_doc_summary_storage.py), [`test_mind_map_branch_expand.py`](tests/test_mind_map_branch_expand.py), [`test_kitty_ack_library.py`](tests/test_kitty_ack_library.py), [`test_kitty_unsupported_diagram_types.py`](tests/test_kitty_unsupported_diagram_types.py); extended [`test_kitty_voice_command_router.py`](tests/test_kitty_voice_command_router.py).
- **Frontend** — [`oneSentenceSessionTurns.spec.ts`](frontend/tests/oneSentenceSessionTurns.spec.ts), [`hierarchicalClipboard.spec.ts`](frontend/tests/hierarchicalClipboard.spec.ts), [`diagramTypeFromPrompt.spec.ts`](frontend/tests/diagramTypeFromPrompt.spec.ts), [`mindMapSubgraphContext.spec.ts`](frontend/tests/mindMapSubgraphContext.spec.ts), [`mindMapSubgraphMerge.spec.ts`](frontend/tests/mindMapSubgraphMerge.spec.ts), [`resolveDiagramLlmModel.spec.ts`](frontend/tests/resolveDiagramLlmModel.spec.ts); extended [`branchAutoExpandGuard.spec.ts`](frontend/tests/branchAutoExpandGuard.spec.ts), [`diagramSaveFlow.spec.ts`](frontend/tests/diagramSaveFlow.spec.ts).

## [5.139.0] - 2026-07-08

> **Chrome extension v0.4.20 store packaging and page capture refactor, public Terms/Privacy page with browser extension appendix, and Edge Add-ons publish tooling.**

### Added

- **Store-ready extension zip** — Manifest-at-root zip builder for Chrome, Edge, and Partner Center upload ([`extension_store_packaging.py`](utils/extension_store_packaging.py), [`client_bundles.py`](routers/api/client_bundles.py)).
- **Edge Add-ons publish tooling** — `publish_edge_addon.py`, `package_extension.py`, manual push script, and certification notes example ([`scripts/publish_edge_addon.py`](scripts/publish_edge_addon.py), [`chrome-extension/scripts/manual_push_edge.sh`](chrome-extension/scripts/manual_push_edge.sh)).
- **Chrome extension v0.4.20 — page content capture pipeline** — Shared file-first + DOM text capture for MindMate, mind map, and File Center ingest ([`page-content-capture.js`](chrome-extension/doc-extract/page-content-capture.js), [`page-content.js`](chrome-extension/doc-extract/text/page-content.js)).
- **Extension per-tab job locks** — MV3 service worker rejects overlapping capture/download work on the same tab ([`extension-jobs.js`](chrome-extension/extension-jobs.js)).
- **Public Terms + Privacy page** — `/privacy` with shared agreement renderer and browser-extension privacy appendix ([`PrivacyPage.vue`](frontend/src/pages/PrivacyPage.vue), [`SoftwareAgreementDocument.vue`](frontend/src/components/auth/SoftwareAgreementDocument.vue), [`authSoftwareAgreement.ts`](frontend/src/content/authSoftwareAgreement.ts)).
- **Chrome extension icon300** — 300×300 store logo asset ([`icons/icon300.png`](chrome-extension/icons/icon300.png)).

### Changed

- **Client bundle download** — `GET /api/downloads/mindgraph-chrome-extension` serves the store-ready zip from [`build_store_zip_bytes()`](utils/extension_store_packaging.py) (alias `/mindgraph-extension`).
- **Software agreement UI** — Modal and `/privacy` share [`SoftwareAgreementDocument.vue`](frontend/src/components/auth/SoftwareAgreementDocument.vue); auth footer links to the public page ([`SoftwareAgreementModal.vue`](frontend/src/components/auth/SoftwareAgreementModal.vue), [`AuthLayout.vue`](frontend/src/layouts/AuthLayout.vue)).
- **Chrome extension capture** — Removed [`mindmate-page-markdown.js`](chrome-extension/mindmate-page-markdown.js); MindMate and background flows delegate to the shared page-content pipeline ([`mindmate-capture.js`](chrome-extension/mindmate-capture.js), [`background.js`](chrome-extension/background.js)).
- **SmartEdu extract helpers** — Metadata block dedup keys and token/page capture alignment ([`metadata.js`](chrome-extension/doc-extract/smartedu/metadata.js), [`token.js`](chrome-extension/doc-extract/smartedu/token.js)).
- **Chrome extension branding** — Regenerated icon sizes and manifest metadata for Edge listing ([`manifest.json`](chrome-extension/manifest.json), [`generate_icons.py`](chrome-extension/scripts/generate_icons.py)).
- **CI** — Chrome extension vitest job in GitHub Actions and [`ci-local.sh`](scripts/ci-local.sh) ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

### Fixed

- **Overlapping extension jobs** — Same-tab capture/download returns `errJobAlreadyRunning` instead of racing the service worker ([`extension-jobs.js`](chrome-extension/extension-jobs.js), locale strings in [`_locales/`](chrome-extension/_locales/)).
- **Extension API errors** — User-facing `errApi` / job-busy messages in popup and compose flows ([`popup.js`](chrome-extension/popup.js), [`mindmate-compose.js`](chrome-extension/mindmate-compose.js)).

### Tests

- **Backend** — [`test_extension_store_packaging.py`](tests/test_extension_store_packaging.py) (manifest at zip root, runtime scripts included).
- **Chrome extension** — Extended [`test/doc-extract.spec.js`](chrome-extension/test/doc-extract.spec.js) and [`test/mindmate.spec.js`](chrome-extension/test/mindmate.spec.js) for page-content capture, job locks, and shared helpers.

## [5.138.0] - 2026-07-07

> **MindMate collab WebSocket reliability, thinking-coins school subscription and WeCom consult, mind map underline connectors, and extension page-context display.**

### Added

- **WeCom outbound notifications** — Profile-based webhook + optional app-message client under [`services/integrations/wecom/`](services/integrations/wecom/); env vars in [`env.example`](env.example).
- **School consultation API** — `POST /api/thinking-coins/school-consultation` validates the form, rate-limits, and forwards leads via WeCom ([`thinking_coins.py`](routers/auth/thinking_coins.py), [`school_consult_notify.py`](services/auth/thinking_coin/school_consult_notify.py), [`school_consult_validation.py`](services/auth/thinking_coin/school_consult_validation.py)).
- **Thinking-coins school subscription UI** — School consult form in upgrade modal ([`ThinkingCoinsSchoolSubscriptionPanel.vue`](frontend/src/components/auth/ThinkingCoinsSchoolSubscriptionPanel.vue), [`ThinkingCoinsSubscriptionSection.vue`](frontend/src/components/auth/ThinkingCoinsSubscriptionSection.vue)); deep-link `?tab=school` on `/thinking-coins/upgrade`.
- **Ledger enrichment** — Wallet ledger rows include `task_title` / `task_title_en` from earn-task refs ([`ledger_enrichment.py`](services/auth/thinking_coin/ledger_enrichment.py), [`thinkingCoinsLedgerLabel.ts`](frontend/src/composables/auth/thinkingCoinsLedgerLabel.ts)).
- **Collab reconnect helpers** — Permanent close-code denylist, exponential backoff, and resume-token refresh ([`mindmateCollabReconnect.ts`](frontend/src/utils/mindmateCollabReconnect.ts)).
- **Extension page-context display** — Strip embedded page markdown for MindMate bubbles, collab seed, and history ([`mindmateExtensionPageContext.ts`](frontend/src/utils/mindmateExtensionPageContext.ts)).
- **WS disconnect cleanup module** — Superseded-socket teardown without evicting the active Redis/registry connection ([`ws_disconnect_cleanup.py`](services/features/mindmate_collab/ws_disconnect_cleanup.py)).

### Changed

- **MindMate collab WebSocket join flow** — `add_participant` runs only after `ws_managed_session` accepts; REST join validates permissions without incrementing counts until WS connect ([`mindmate_collab_ws.py`](routers/api/mindmate_collab_ws.py), [`manager.py`](services/features/mindmate_collab/manager.py)).
- **Collab room UX** — Connection status banner, retry control, mobile members drawer, and embed layout polish ([`MindmateCollabRoom.vue`](frontend/src/components/mindmate/MindmateCollabRoom.vue), [`MindmateCollabEmbed.vue`](frontend/src/components/mindmate/MindmateCollabEmbed.vue), [`MindmateCollabPage.vue`](frontend/src/pages/MindmateCollabPage.vue)).
- **Thinking-coins upgrade panel** — Ledger preview row, expandable earn-task cards, and school subscription section ([`ThinkingCoinsUpgradePanel.vue`](frontend/src/components/auth/ThinkingCoinsUpgradePanel.vue)).
- **Mind map underline connectors** — Underline-bar anchor Y aligned with branch node geometry; orthogonal edge path uses shared endpoint resolver ([`BranchNode.vue`](frontend/src/components/diagram/nodes/BranchNode.vue), [`MindMapOrthogonalEdge.vue`](frontend/src/components/diagram/edges/MindMapOrthogonalEdge.vue), [`mindMapEdgeEndpoints.ts`](frontend/src/utils/mindMapEdgeEndpoints.ts)).
- **Chrome extension compose** — Panel bubbles and history show the teacher question only when page context is embedded ([`mindmate-compose.js`](chrome-extension/mindmate-compose.js), [`mindmate-api.js`](chrome-extension/mindmate-api.js)).
- **MindMate collab architecture doc** — WebSocket frame and participant-registration notes ([`mindmate_collab.md`](docs/architecture/mindmate_collab.md)).

### Fixed

- **Duplicate-tab WebSocket cleanup** — Second connection for the same user no longer evicts the active socket from Redis/registry ([`ws_disconnect_cleanup.py`](services/features/mindmate_collab/ws_disconnect_cleanup.py)).
- **Connection-cap ghost participants** — Failed WS joins roll back; counts update only on successful connect.
- **REST join ghost participants** — Participant counts no longer increment on permission-only REST join.
- **Collab reconnect policy** — Denylist permanent close codes (1008, 4029); `session_closing` and auth-failure UX ([`useMindmateCollab.ts`](frontend/src/composables/mindmate/useMindmateCollab.ts)).
- **Extension page context in collab seed** — Seed messages display the extracted question, not raw page markdown ([`MindmatePanel.vue`](frontend/src/components/panels/MindmatePanel.vue)).
- **Mobile collab members panel** — Drawer toggle on narrow viewports.

### Tests

- **Backend** — `test_mindmate_collab_ws_disconnect.py`, `test_school_consult_route.py`, `test_school_consult_validation.py`, `test_thinking_coin_ledger_enrichment.py`, `test_wecom_*.py`; extended `test_mindmate_collab_backend.py`, `test_mindmate_collab_hardening.py`, `test_mindmate_collab_resume_tokens.py`.
- **Frontend** — `mindmateCollabReconnect.spec.ts`, `mindmateExtensionPageContext.spec.ts`, `thinkingCoinsLedgerLabel.spec.ts`; extended `mindMapUnderlineAnchorY.spec.ts`, `useMindmateCollab.spec.ts`.
- **Chrome extension** — Extended [`test/mindmate.spec.js`](chrome-extension/test/mindmate.spec.js) for page-context display helpers.

## [5.137.0] - 2026-07-05

> **MindMate collab hardening, unified org roster, seed-message handoff, and sidebar quote vendor refresh.**

### Added

- **MindMate collab seed messages** — Starting a room copies the host's MindMate thread into the shared room (`seed_messages` on `POST /start`; [`message_history.py`](services/features/mindmate_collab/message_history.py), [`MindmatePanel.vue`](frontend/src/components/panels/MindmatePanel.vue)).
- **Org concurrent session cap** — `MINDMATE_COLLAB_MAX_ORG_CONCURRENT_SESSIONS` (default 10) limits live organization-visible rooms per org ([`manager.py`](services/features/mindmate_collab/manager.py), [`config.py`](services/features/mindmate_collab/config.py)).
- **Network room session members** — `GET /session-members` lists teachers who joined a public collab room ([`mindmate_collab_routes.py`](routers/api/mindmate_collab_routes.py), [`org_member_roster.py`](services/features/org_member_roster.py)).
- **Unified org roster composables** — Shared `useOrgRosterPanel`, `useOrgPresenceCore`, and backend adapters for Workshop Chat and MindMate collab ([`frontend/src/composables/social/`](frontend/src/composables/social/)).
- **MindMate collab breadcrumb** — In-room navigation back to personal MindMate thread ([`MindmateCollabBreadcrumb.vue`](frontend/src/components/mindmate/MindmateCollabBreadcrumb.vue)).
- **Collab teardown helpers** — Shared stop/confirm/WS error utilities ([`mindmateCollabTeardown.ts`](frontend/src/utils/mindmateCollabTeardown.ts), [`mindmateCollabConfirm.ts`](frontend/src/utils/mindmateCollabConfirm.ts), [`mindmateCollabWsErrors.ts`](frontend/src/utils/mindmateCollabWsErrors.ts)).
- **MindGrowth sidebar quotes** — Chinese vendor bucket via `normalize-mindgrowth.ts`; shipped in `sidebar-quotes-zh.json` ([`frontend/scripts/vendor/sidebar-quotes/mindgraph/`](frontend/scripts/vendor/sidebar-quotes/mindgraph/)).
- **Local CI script** — [`scripts/ci-local.sh`](scripts/ci-local.sh) mirrors GitHub Actions workflow.

### Changed

- **MindMate collab defaults** — Default room duration 10h (was end-of-day); idle warning after 43m silence + 2m grace ([`config.py`](services/features/mindmate_collab/config.py)).
- **Collab room UX** — Embed panel, members panel, and history refactored; Swiss-style confirm dialogs ([`mindmate-swiss-messagebox.css`](frontend/src/styles/mindmate-swiss-messagebox.css)); host stop from toolbar.
- **Org contacts panel** — Sectioned roster via `useOrgContactSections`; `UserCardPopover` shared across Workshop and collab ([`OrgContactsPanel.vue`](frontend/src/components/social/OrgContactsPanel.vue)).
- **Dify stream control** — Cooperative abort signal, chat guard while closing, system-stop path ([`dify_stream_control.py`](services/features/mindmate_collab/dify_stream_control.py), [`dify_stream.py`](services/features/mindmate_collab/dify_stream.py)).
- **Idle monitor** — Configurable concurrency; fan-out publish core alignment ([`idle_monitor.py`](services/features/mindmate_collab/idle_monitor.py), [`ws_redis_fanout_publish_core.py`](services/features/ws_redis_fanout_publish_core.py)).
- **Resume tokens** — Tighter binding and one-time consume ([`resume_tokens.py`](services/features/mindmate_collab/resume_tokens.py)).
- **AGENTS.md** — Canonical pointers to Cursor rules and `ci-local.sh`; lint policy consolidated.

### Fixed

- **Collab join while closing** — Reject joins and chat when session is shutting down ([`manager.py`](services/features/mindmate_collab/manager.py)).
- **Participant registration** — Enforce max participants on join ([`manager.py`](services/features/mindmate_collab/manager.py)).
- **Visibility validation** — Reject invalid `visibility` on room start ([`mindmate_collab_routes.py`](routers/api/mindmate_collab_routes.py)).

### Tests

- **Backend** — `test_mindmate_collab_dify_stream.py`, `test_mindmate_collab_message_history.py`, `test_mindmate_collab_org_limits.py`, `test_mindmate_collab_resume_tokens.py`, `test_mindmate_collab_session_chat_guard.py`, `test_mindmate_collab_system_stop.py`; extended `test_mindmate_collab_backend.py`, `test_mindmate_collab_hardening.py`, `test_ws_fanout.py`.
- **Frontend** — `mindmateCollabWsErrors.spec.ts`, `orgContactSections.spec.ts`; extended `useMindmateCollab.spec.ts`, `import-sidebar-quotes.spec.ts`.

## [5.136.0] - 2026-07-05

> **Learning sheet persistence, classroom worksheet headers, mind map connector geometry, canvas export polish, and thinking-coins fixes.**

### Added

- **Canvas worksheet text** — Classroom header fields (topic, name, class, date, instructions) via `CanvasWorksheetTextModal.vue`; session-persisted options ([`canvasWorksheetText.ts`](frontend/src/config/canvasWorksheetText.ts), [`useCanvasWorksheetText.ts`](frontend/src/composables/canvas/useCanvasWorksheetText.ts)); rasterized into A4 PDF export ([`diagramWorksheetHeader.ts`](frontend/src/utils/diagramWorksheetHeader.ts)).
- **Canvas export options panel** — Wireframe/outline, color mode, layout, and answer visibility in `MindMapExportOptionsPanel.vue`; preferences in [`canvasExportOptions.ts`](frontend/src/config/canvasExportOptions.ts).
- **Concept parking lot** — Mind map side panel for staging ideas before placement ([`useConceptParkingLot.ts`](frontend/src/composables/conceptParkingLot/useConceptParkingLot.ts)).
- **MindMate diagram preview cache** — Eagerly persist generate_dingtalk PNGs to IndexedDB when a stream completes and when conversation history loads ([`mindmateDiagramPreviewPersist.ts`](frontend/src/utils/mindmateDiagramPreviewPersist.ts), [`useMindMate.ts`](frontend/src/composables/mindmate/useMindMate.ts)).
- **MindMate stale preview toast** — Clickable warning when server temp PNG is gone but the diagram can still open in canvas ([`mindmateDiagramPreviewExpiredNotify.ts`](frontend/src/utils/mindmateDiagramPreviewExpiredNotify.ts), [`MessageBubble.vue`](frontend/src/components/panels/mindmate/MessageBubble.vue)).
- **Thinking-coins wallet fetch helper** — Shared deduped refetch in [`fetchThinkingCoinsWallet.ts`](frontend/src/composables/auth/fetchThinkingCoinsWallet.ts).

### Changed

- **Learning sheet answer visibility** — Show/hide reference answers from the side panel (segmented control + `Ctrl+Shift+H`); preference and `hiddenAnswers` round-trip in spec save/load and auto-save ([`learningSheet.ts`](frontend/src/stores/diagram/learningSheet.ts), [`MindMapSidePanel.vue`](frontend/src/components/canvas/MindMapSidePanel.vue)).
- **Learning sheet undo** — Blank/restore node picks push history entries; undo after reload restores full diagram text ([`useLearningSheetCustomMode.ts`](frontend/src/composables/mindMap/useLearningSheetCustomMode.ts)).
- **Mind map connectors** — Orthogonal bracket paths with flat horizontal segments near parent Y; underline handle anchor Y aligned with Vue Flow DOM probe ([`mindMapOrthogonalPath.ts`](frontend/src/utils/mindMapOrthogonalPath.ts), [`mindMapGeometry.ts`](frontend/src/config/mindMapGeometry.ts), [`mindMapEdgeEndpoints.ts`](frontend/src/utils/mindMapEdgeEndpoints.ts)).
- **Canvas PDF export** — Worksheet header page prepended when active; learning-sheet show-answers preference applied before rasterize ([`useDiagramExport.ts`](frontend/src/composables/editor/useDiagramExport.ts), [`diagramPdfExport.ts`](frontend/src/utils/diagramPdfExport.ts)).
- **Mind map shortcut guide** — Learning-sheet answer toggle row pinned while mode is active ([`mindMapShortcutGuide.ts`](frontend/src/config/mindMapShortcutGuide.ts), [`CanvasMindMapShortcutGuide.vue`](frontend/src/components/canvas/CanvasMindMapShortcutGuide.vue)).
- **Trial-org thinking coins** — All org members on trial tier earn coins, not only teacher/school_admin roles ([`eligibility.py`](services/auth/thinking_coin/eligibility.py)).

### Fixed

- **Thinking-coins wallet refetch loop** — Sidebar auth sync no longer hammers `/api/thinking-coins/wallet` on every navigation ([`useAppSidebar.ts`](frontend/src/composables/sidebar/useAppSidebar.ts), [`fetchThinkingCoinsWallet.ts`](frontend/src/composables/auth/fetchThinkingCoinsWallet.ts)).
- **MindMate collab notify WS** — Real-time poke/mention socket connects only when `FEATURE_MINDMATE_COLLAB` is enabled ([`useMindmateCollabNotify.ts`](frontend/src/composables/social/useMindmateCollabNotify.ts)).
- **Learning sheet layout** — Preserve pre-blank node dimensions so restored text does not shrink branches ([`learningSheet.ts`](frontend/src/stores/diagram/learningSheet.ts)).

### Tests

- **Frontend** — `canvasWorksheetText.spec.ts`, `learningSheetPersist.spec.ts`, `mindMapOrthogonalPath.spec.ts`, `mindMapUnderlineAnchorY.spec.ts`; extended `learningSheetUndo.spec.ts`, `mindMapShortcutGuide.spec.ts`, `canvasExportMenu.spec.ts`, `diagramExportLearningSheet.spec.ts`, `fetchThinkingCoinsWallet.spec.ts`, `mindmateDiagramPreviewPersist.spec.ts`, `mindmateDiagramPreviewExpiredNotify.spec.ts`.
- **Backend** — `test_thinking_coin_eligibility.py`, `test_thinking_coin_task_wiring_audit.py`, [`thinking_coin_wiring_manifest.py`](tests/thinking_coin_wiring_manifest.py).

## [5.135.0] - 2026-07-03

> **MindMate online collab, diagram provenance, canvas PDF export, and identity unification.**

### Added

- **MindMate online collab** — Shared AI chatroom for teachers: one room, one Dify conversation, streaming assistant replies fan-out to all participants. REST at `/api/mindmate/collab/*`, WebSocket at `/api/ws/mindmate-collab/{code}`, feature flag `FEATURE_MINDMATE_COLLAB` (default off). See [`docs/architecture/mindmate_collab.md`](docs/architecture/mindmate_collab.md).
- **MindMate collab UI** — `MindmateCollabPage.vue`, toolbar panel on `/mindmate`, sidebar history (`MindmateCollabHistory.vue`), org contacts + DM drawer (shared social layer with Workshop Chat).
- **MindMate collab backend** — Session manager, idle monitor, Dify stream lock, resume tokens, Redis fan-out (`mmc:` prefix), Alembic `rev_0076` + RLS `rev_0077`.
- **Diagram provenance** — Optional `source_channel`, `conversation_id`, `dify_user_key` columns on `diagrams` (Alembic `rev_0074`); populated on library save from MindMate/MindBot flows.
- **Pinned conversation routing** — `dify_user`, `server`, `mindbot_config_id` on pinned rows (Alembic `rev_0075`) for unified inbox message/delete/rename routing.
- **Canvas PDF export** — A4 landscape/portrait PDF via `diagramPdfExport.ts`; multi-page learning-sheet PDF; export menu entries in all locale buckets.
- **Identity unification docs** — [`docs/architecture/identity_unification.md`](docs/architecture/identity_unification.md) for MindGraph ↔ Dify ↔ DingTalk identity, generation session registry, and diagram provenance.
- **Mind map connector debug** — Optional verbose connector logging (`useMindMapConnectorDebugLog.ts`, `mindMapConnectorDebug*.ts`).
- **Chrome extension v0.4.20 — unified conversation list** — `fetchConversations`, routed message/history/delete/rename via `dify_user` + `server` + `mindbot_config_id` query params ([`mindmate-api.js`](chrome-extension/mindmate-api.js), [`mindmate-panel.js`](chrome-extension/mindmate-panel.js)).

### Changed

- **Unified conversations** — Web MindMate and bound MindBot threads merged in sidebar; cross-org group threads supplemented from usage telemetry ([`unified_conversations.py`](services/dify/unified_conversations.py)).
- **Workshop Chat social layer** — Org contacts, presence, and DM drawer extracted to shared `frontend/src/components/social/` composables; `WorkshopChatPage.vue` slimmed down.
- **Mind map layout** — Improved typography measurement, connector geometry, and learning-sheet blank-node handling ([`mindMapMeasurements.ts`](frontend/src/stores/specLoader/mindMapMeasurements.ts), [`learningSheet.ts`](frontend/src/stores/diagram/learningSheet.ts)).
- **Canvas toolbar** — Mind map side toolbar refactor; PNG export prep waits for paint/fonts before rasterize.
- **Generation session registry** — DingTalk identity resolution and library-save provenance wiring ([`generation_session_registry.py`](services/diagram/generation_session_registry.py), [`generation_library_save.py`](services/diagram/generation_library_save.py)).
- **DingTalk bind** — Usage-event backfill on successful staff bind ([`dingtalk_bind_service.py`](services/auth/dingtalk_bind_service.py)).
- **Admin features tab** — Toggle for `FEATURE_MINDMATE_COLLAB`.

### Fixed

- **Learning sheet blanks** — Placeholder nodes no longer leak into export or palette data ([`placeholderHelpers.ts`](frontend/src/composables/nodePalette/placeholderHelpers.ts)).
- **Dify export targets** — Pinned conversation routing alignment for multi-server MindBot configs.

### Tests

- **Backend** — `tests/test_mindmate_collab_*.py` (backend, hardening, lifecycle, visibility, WS broadcast); extended `test_unified_conversations.py`, `test_dingtalk_bind_service.py`, `test_generation_session_registry.py`.
- **Frontend** — `useMindmateCollab.spec.ts`, `MindmateCollabPanel.spec.ts`, `MindmateCollabHistory.spec.ts`, `learningSheetBlank.spec.ts`, `mindmateCollabMention.spec.ts`, `mindmateCollabPokeNotify.spec.ts`, extended `canvasExportMenu.spec.ts`.
- **Chrome extension** — Extended [`test/mindmate.spec.js`](chrome-extension/test/mindmate.spec.js) for conversation routing helpers.

## [5.134.1] - 2026-07-01

> **Chrome extension v0.4.19 — MindMate page capture UX, SmartEdu PDF text extraction, and CNKI flowpdf fixes.**

### Added

- **Chrome extension v0.4.19 — MindMate capture progress** — Live status line under「包含当前网页内容」for prefetch and send: generic web text, SmartEdu asset detect/download/extract phases, and ready/error summaries via [`mindmate-capture-progress.js`](chrome-extension/mindmate-capture-progress.js) and session storage ([`mindmate-panel.js`](chrome-extension/mindmate-panel.js)).
- **Chrome extension — CNKI reader surfaces** — Shared wait/capture helpers for canvas, `<img>`, and iframe reader content ([`doc-extract/cnki/reader-surfaces.js`](chrome-extension/doc-extract/cnki/reader-surfaces.js)); reader plain-text collection for MindMate ([`doc-extract/cnki/reader-text.js`](chrome-extension/doc-extract/cnki/reader-text.js)).
- **Chrome extension — CNKI download URL builder** — `buildCnkiReaderDownloadCandidates()` supports invoice-only flowpdf URLs and classic `kns/download?…&dflag=pdfdown` ([`doc-extract/cnki/url-parser.js`](chrome-extension/doc-extract/cnki/url-parser.js)).

### Changed

- **Backend — CSRF for mgat_ API clients** — Skip double-submit CSRF only when `Authorization: Bearer mgat_…` is present, so Chrome extension / file-reader calls are not blocked by incidental session cookies ([`middleware.py`](services/infrastructure/http/middleware.py), [`http_auth_token.py`](services/auth/http_auth_token.py)); deploy note in [`production_security_deploy.md`](docs/architecture/production_security_deploy.md).
- **Chrome extension — MindMate Dify prompt** — Question-first layout with routing hints for 思维发展型课堂 / 认知冲突; SmartEdu/Wenku/CNKI file-first capture without silent DOM fallback when extraction fails ([`mindmate-compose.js`](chrome-extension/mindmate-compose.js), [`doc-extract/extract-to-markdown.js`](chrome-extension/doc-extract/extract-to-markdown.js)).
- **Chrome extension — MindMate assistant markdown** — Safe subset renderer for streamed replies ([`mindmate-markdown.js`](chrome-extension/mindmate-markdown.js)).
- **Chrome extension — CNKI engine** — PDF fetch runs in tab context (session cookies); merges DOM-resolved and URL-built download candidates ([`doc-extract/engines/cnki.js`](chrome-extension/doc-extract/engines/cnki.js)).

### Fixed

- **Chrome extension — SmartEdu MindMate capture** — PDF text extraction uses offscreen pdf.js with base64 fallback instead of passing `ArrayBuffer`/`Blob` through `chrome.scripting.executeScript` (fixes「Unserializable argument passed.」) ([`doc-extract/text/pdf-extract-offscreen.js`](chrome-extension/doc-extract/text/pdf-extract-offscreen.js), [`offscreen.js`](chrome-extension/offscreen.js)).
- **Chrome extension — CNKI flowpdf** — Removed infinite recursion in [`page-resolve.js`](chrome-extension/doc-extract/cnki/page-resolve.js) that broke URL resolution; invoice-only reader URLs no longer return `CNKI_PDF_URL_MISS`; canvas/img capture waits for reader content; MindMate no longer maps all CNKI failures to「需要登录」.
- **Chrome extension — MindMate auth** — Extension API fetches omit cookies; CSRF skip narrowed to `mgat_` Bearer tokens (server + extension alignment from prior session).

### Tests

- **Backend** — `test_csrf_skips_when_mgat_bearer_present_despite_session_cookies` and JWT Bearer still enforces CSRF ([`test_csrf_protection.py`](tests/test_csrf_protection.py)).
- **Chrome extension** — Capture progress formatting, CNKI invoice URL candidates, offscreen base64 helper; extended [`test/mindmate.spec.js`](chrome-extension/test/mindmate.spec.js) and [`test/doc-extract.spec.js`](chrome-extension/test/doc-extract.spec.js).

## [5.134.0] - 2026-07-01

> **Chrome extension MindMate + security hardening, Tencent COS admin/sync, and file-reader scope trim.**

### Added

- **Chrome extension — MindMate panel** — In-page chat panel with SSE streaming, session history, and page-context capture via [`mindmate-panel.js`](chrome-extension/mindmate-panel.js), [`mindmate-api.js`](chrome-extension/mindmate-api.js), [`mindmate-sse.js`](chrome-extension/mindmate-sse.js), [`mindmate-capture.js`](chrome-extension/mindmate-capture.js).
- **Chrome extension — Document Summary save** — Save active page or SmartEdu assets to a Knowledge Space package from the popup; library link reads `X-MG-Diagram-Id` after mind-map PNG generation ([`popup.js`](chrome-extension/popup.js), [`shared-mindgraph.js`](chrome-extension/shared-mindgraph.js)).
- **Chrome extension — Baidu Wenku tier** — Direct PDF fetch engine for `wkretype.bdimg.com` ([`doc-extract/wenku/`](chrome-extension/doc-extract/wenku/)).
- **Chrome extension — security helpers** — Sender validation, positive-int package checks, and shared storage utilities ([`extension-security.js`](chrome-extension/extension-security.js), [`extension-storage.js`](chrome-extension/extension-storage.js)).
- **Chrome extension — Edge offscreen blobs** — Shared offscreen document for large downloads without service-worker blob races ([`offscreen-blobs.js`](chrome-extension/offscreen-blobs.js)).
- **Admin — Tencent COS tab** — Overview, PostgreSQL backups, CrowdSec blocklist mirror, and Qdrant release status with manual trigger actions ([`AdminCosTab.vue`](frontend/src/components/admin/AdminCosTab.vue), [`cos_admin_service.py`](services/admin/cos_admin_service.py), [`routers/admin/cos.py`](routers/admin/cos.py)).
- **Infrastructure — COS sync pipeline** — Publisher/consumer roles for CrowdSec blocklist, Qdrant, Celery, and stack artifacts via Tencent COS ([`services/infrastructure/sync/`](services/infrastructure/sync/), [`tencent_cos_client.py`](services/utils/tencent_cos_client.py)).
- **Setup scripts — COS stack update** — `update_stack_from_cos.py`, `update_qdrant_from_cos.py`, `update_celery_from_cos.py` for consumer nodes ([`scripts/setup/`](scripts/setup/), [`scripts/db/update_stack_from_cos.py`](scripts/db/update_stack_from_cos.py)).

### Changed

- **Chrome extension v0.4.18** — Split MindGraph API host permissions from doc-extract wildcards; localhost HTTP warning in Settings; MindMate SSE errors return `ok: false` instead of false success ([`HOST_PERMISSIONS.md`](chrome-extension/HOST_PERMISSIONS.md), [`DEPLOY_VERIFICATION.md`](chrome-extension/DEPLOY_VERIFICATION.md)).
- **Chrome extension — SmartEdu token** — Page-injected token reader, improved metadata/downloader flow, and user-facing error messages ([`doc-extract/smartedu/token.js`](chrome-extension/doc-extract/smartedu/token.js), [`user-messages.js`](chrome-extension/doc-extract/user-messages.js)).
- **File reader — scope trim** — Removed Playwright platform browser, SmartEdu tab, and multi-platform download modules; desktop helper focuses on WeChat/DingTalk/WeCom chat handoff only ([`clients/file-reader/README.md`](clients/file-reader/README.md)).
- **Backup scheduler — COS integration** — PostgreSQL dumps upload to COS with manifest metadata; admin status and manual backup trigger ([`backup_scheduler.py`](services/utils/backup_scheduler.py)).
- **HTTP middleware — CORS expose headers** — `X-MG-Diagram-Id`, `X-MG-Save-Error`, and `Content-Disposition` exposed for extension cross-origin fetch ([`middleware.py`](services/infrastructure/http/middleware.py)).
- **Docs** — COS env vars in [`env.example`](env.example); Celery/Qdrant/Fail2ban setup notes for COS consumer role ([`docs/CELERY_SETUP.md`](docs/CELERY_SETUP.md), [`docs/QDRANT_SETUP.md`](docs/QDRANT_SETUP.md), [`docs/FAIL2BAN_SETUP.md`](docs/FAIL2BAN_SETUP.md)).

### Removed

- **File reader — platform browser stack** — Playwright host, SmartEdu panel, YouTube/WeChat Channels/Tencent Meeting extractors, and related tests (superseded by Chrome extension doc-extract).

### Fixed

- **Chrome extension — MindMate SSE errors** — Panel clears status only on successful stream; quota/coin error types mapped to readable messages ([`test/mindmate.spec.js`](chrome-extension/test/mindmate.spec.js)).
- **Chrome extension — background message validation** — `sender.id` and payload shape checks on save/token handlers ([`background.js`](chrome-extension/background.js), [`offscreen.js`](chrome-extension/offscreen.js)).

### Tests

- **COS sync** — `test_tencent_cos_client.py`, `test_cos_admin_service.py`, `test_qdrant_cos_sync.py`, `test_celery_cos_sync.py`, `test_crowdsec_cos_sync.py`, `test_stack_cos_plan.py`, `test_release_version.py`, `test_update_stack_from_cos.py`.
- **Chrome extension** — `test/mindmate.spec.js`, extended `test/doc-extract.spec.js` (29 vitest tests).

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): syncs with root **`VERSION`** (5.134.0) on next `npm run build` (`prebuild` → `sync-version`).

## [5.133.0] - 2026-06-30

> **Knowledge Space wiki spine, section-aware chunking, pipeline badges, and file-reader Playwright platform browser.**

### Added

- **Knowledge Space — wiki spine (v2b)** — Curriculum documents (课标 / 课程方案) map OCR/extracted headings onto canonical wiki slugs (`san-kecheng-mubiao`, etc.) for TOC-driven compile; other sources fall back to LLM structure pass ([`wiki_spine.py`](services/knowledge/wiki_spine.py), [`package_wiki_compiler.py`](services/knowledge/package_wiki_compiler.py)).
- **Knowledge Space — section-aware chunking** — Hierarchical semchunk splits on heading boundaries; chunks carry `section_title` and `section_key` for scoped RAG ([`section_parser.py`](services/knowledge/section_parser.py), [`section_keys.py`](services/knowledge/section_keys.py), [`chunking_service.py`](services/knowledge/chunking_service.py)).
- **Knowledge Space — user settings API** — `GET/PUT /api/knowledge-space/settings` for retrieval method, top-k, score threshold, chunk size/overlap; mirrors into `processing_rules` ([`knowledge_settings.py`](services/knowledge/knowledge_settings.py), [`settings.py`](routers/api/knowledge_space/settings.py)).
- **Knowledge Space — pipeline status badges** — Per-document RAG and wiki compile states on library table, package groups, and sidebar history ([`package_pipeline_status.py`](services/knowledge/package_pipeline_status.py), [`usePipelineStatusBadge.ts`](frontend/src/composables/knowledge/usePipelineStatusBadge.ts)).
- **Knowledge Space — section-scoped RAG** — Wiki spine sections and section hints route retrieval to chapter-scoped context ([`section_query.py`](services/knowledge/section_query.py), [`section_resolver.py`](services/knowledge/section_resolver.py), [`package_rag_context.py`](services/knowledge/package_rag_context.py)).
- **File reader — Playwright platform browser** — Default backend launches **bundled Chromium** via Playwright Python driver; persistent profile at `platform-browser/playwright-edge/`; network capture for Tencent Meeting, YouTube PO tokens, and WeChat Channels ([`playwright_host.py`](clients/file-reader/file_reader/platform_browser/playwright_host.py), [`chromium_launcher.py`](clients/file-reader/file_reader/platform_browser/chromium_launcher.py), [`browser_factory.py`](clients/file-reader/file_reader/platform_browser/browser_factory.py)).
- **File reader — multi-platform downloads** — SmartEdu, Bilibili, YouTube, Douyin, TikTok, WeChat Channels, and Tencent Meeting probe/download pipeline in the platform browser tab ([`platform_browser/`](clients/file-reader/file_reader/platform_browser/)).

### Changed

- **Knowledge Space — wiki compile default** — `FILE_CENTER_WIKI_COMPILE` defaults to `true` (was opt-in `false`) ([`knowledge_config.py`](config/knowledge_config.py), [`env.example`](env.example)).
- **Knowledge Space — settings UI** — Retrieval/chunking preferences panel with reindex-required feedback; package page composable and per-tier package limits ([`KnowledgeSpaceSettings.vue`](frontend/src/components/knowledge-space/KnowledgeSpaceSettings.vue), [`useKnowledgeSpacePackagePage.ts`](frontend/src/composables/knowledge/useKnowledgeSpacePackagePage.ts)).
- **Document Summary — mind map panel** — Package pipeline status and wiki-aware summary context in canvas panel ([`MindMapDocumentSummaryPanel.vue`](frontend/src/components/canvas/MindMapDocumentSummaryPanel.vue)).
- **File reader — platform browser UX** — Browsing moves to an external Chromium window; the panel toolbar controls navigation and download detection. Set `MINDGRAPH_BROWSER=webview2` to restore embedded WebView2 (legacy).
- **File reader — build** — PyInstaller bundles Playwright driver + Chromium (`PLAYWRIGHT_BROWSERS_PATH=0 playwright install chromium`); onefile exe is larger (~300 MB+) but needs no system browser ([`mindgraph-file-reader.spec`](clients/file-reader/mindgraph-file-reader.spec), [`build_windows.ps1`](clients/file-reader/build_windows.ps1)).
- **File reader — browser profiles** — Separate storage dirs for Playwright (`playwright-edge/`) and WebView2 (`webview2/`) to avoid profile collisions ([`smartedu_browser.py`](clients/file-reader/file_reader/smartedu_browser.py)).

### Fixed

- **File reader — browser init hang** — Lazy tab init, UI-thread callbacks, and Playwright command queue avoid tkwebview2 hidden-tab / main-thread deadlocks ([`smartedu_panel.py`](clients/file-reader/file_reader/smartedu_panel.py)).
- **File reader — yt-dlp cookies** — Netscape export preserves path/secure flags; session cookies export as expiry `0` ([`cookie_view.py`](clients/file-reader/file_reader/platform_browser/cookie_view.py), [`cookie_jar.py`](clients/file-reader/file_reader/platform_browser/cookie_jar.py)).

### Tests

- **Knowledge Space** — `test_wiki_spine.py`, `test_section_parser.py`, `test_section_query.py`, `test_section_resolver.py`, `test_hierarchical_semchunk.py`, `test_knowledge_settings.py`, `test_knowledge_settings_api.py`, `test_package_pipeline_status.py`, `test_package_rag_wiki_context.py`.
- **File reader browser** — `test_browser_factory.py`, `test_webview_init_errors.py`, platform registry/download/cookie tests.

### Frontend package version

- ([`frontend/package.json`](frontend/package.json)): syncs with root **`VERSION`** (5.133.0) on next `npm run build` (`prebuild` → `sync-version`).

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
