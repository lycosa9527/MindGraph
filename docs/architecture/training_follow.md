# Org training follow

Visiting instructors (superadmin, `platform_bd`, expert with invited orgs) steer every teacher in a school org to the same canvas page. Teachers generate independently. Redis holds the session; SSE only whispers `{seq}`; clients `GET /api/training/command` for the snapshot.

## Flag

`FEATURE_TRAINING` (default off). Admin → Features. Routes under `/api/training` are 404 when the flag is off.

## Session

Many schools may train at once: Redis keys and SSE channels are per `org_id`. One live-or-paused session per org and at most one hosted session per instructor. A new session always starts at `seq` 1; clients key follow state by `session_id`, not a process-wide seq. States: `live`, `paused`, `ended`. Hard TTL 4 hours. Instructor heartbeat every 15s; 3 minutes silent → lazy auto-pause on `GET /command`.

**Start then play.** Selecting a school and clicking Start arms the room: refresh teacher / online counts, drop stale follow ETags, and open a live Redis session with `pull_users: false` (no force-nav, no teacher banner). A toast says the module is ready. Clicking a course is what pulls every online teacher and starts the slideshow (`pull_users: true`). Start alone stays on the catalog.

## Transport

- `GET /api/training/events` — SSE (`X-Accel-Buffering: no`, comment keepalive ~20s). Cookie auth, same-origin EventSource.
- `GET /api/training/command` — snapshot + ETag (`"{session_id}:{seq}"` so a new session at seq 1 is not a 304).
- Poll fallback (2s) if EventSource fails.

Do not put tokens on the SSE query string. Recreate EventSource after access-token refresh.

## Frontend engine

The live console is Pinia + event bus, same shape as 思维讲堂. UI emits `training:*_requested` (`frontend/src/composables/training/trainingCommands.ts`). `useTrainingSessionEngine` in `App.vue` maps those to `useTrainingStore` actions (start/play/step/free, catalog, roster). Follow stays SSE + ETag GET (`useTrainingFollow`). Topic apply and catalog modals are bus events (`training:topic_apply_requested`, `training:modal_open_requested`), not module-level registries. Course Builder drafts live in `useTrainingBuilderStore`; system seed courses are read-only. COS I/O on the API is `asyncio.to_thread`.

## Courses and COS

Authored lessons live in Postgres (`training_courses`, `training_course_steps`, `training_course_assets`). Each course owns a COS folder `{COS_TRAINING_PREFIX}/courses/{course_id}/` (cover, slides, videos, media). Packed Course Builder role WebPs stay in `frontend/public/training/roles/` in git. Source stills and the Wan I2V toolkit live in `scripts/training_roles/` (`stills/fullbody-still-noptr-1.png` / `-2.png`, `python -m scripts.training_roles.generate --ids 08`). Live playback uses `/api/training/assets/roles/{id}.webp` (first request publishes the catalog to `{COS_TRAINING_PREFIX}/roles/`, then 302 to a short-TTL COS GET). The prefix defaults from `ENVIRONMENT` (`training/mindgraph`, `training/mindgraph-Test`, `training/mindgraph-Dev`) so local / test / production do not collide in one bucket. JSON never stores durable COS hosts — only `/api/training/assets/...`. Each step may set `page_key` (MindGraph landing, canvas, MindMate, …) and `pull_users`. The seeded 双气泡图教程 is the first system course.

Course Builder is `/training/builder`. Each slide picks a teacher-facing app page from the closed catalog (`/auth` login/register, MindGraph landing, canvas with the real top bar + editing toolbar + zoom, MindMate, 多应, 迈特学习法, 论境, 智绘, 图书馆, 模板, 课程, 知识库, 案例广场, 社区, 语音笔记, 思维币升级). The **弹窗** list is scoped to that page: landing (`mindgraph`) owns 账户 / 语言设置 / 思维币 / 更新日志; canvas owns 协同 / 分享到社区; library, template, course, 多应, 社区, and 案例广场 own the login modal; `/auth` has no extra modal (login/register are page buttons). Changing the page clears a modal that does not belong. The selected stage mounts that page at full size (a `scale(1)` containing block plus disabled `Teleport` keeps login/register inside the stage). Overlay text/emoji/arrows paint above that modal. Canvas is a live isolated editor that uses the author’s current V1/V2/V3 canvas chrome (V3 ribbon when that preference is on). The header **预览** button covers the editor with the teacher view of the current slide (media overlay or live page, topic chips, no speaker notes). The builder toolbar is three rows: follow (page / modal / button / pull), canvas (diagram / V1–V3 / 主题备选), and marks (text bubble / arrow / emoji / roles / image). Text bubbles store optional `w` / `h` / `size` / `bold` / `italic` / `align` / `ink` / `stroke` on the overlay JSON. **主题备选** authors `topic_options` for that slide (two fields on 双气泡图, one field on every other diagram). Play copies them onto the Redis snapshot so teachers can tap a chip and generate immediately. A notes strip under the stage stores `notes` on the step for the instructor only. Teachers never receive `notes` on the command snapshot; the live notes bar is hidden unless the viewer is the session instructor. The filmstrip **添加图片** button inserts one or more PPT images at the current filmstrip index (`type: slide`, `pull_users` on) and shifts later slides down. Teachers see that image as a full-screen overlay when the session is live on that step. Filmstrip thumbs are still images only (stage snapshot or uploaded slide), never a live animated page. Snapshots upload through the API into the course COS folder (`thumbs/{id}.png`) and persist as `thumb_id` on the step; uploaded PPT slides reuse that file as the preview. After a slide has a snapshot, leaving it hibernates the live page so switching back shows the still image until the author clicks the stage or changes page/modal/focus/canvas. Clicking a landing diagram card switches that slide to the matching canvas. Other catalogued controls bind `focus_key` without leaving the builder; auth login/register clicks also switch the live tab. Text bubbles, emoji, roles, and arrows on the builder stage are draggable. Text bubbles are inline-editable speech bubbles (no modal) with resize and a floating bold / size / align bar. Follow to `/auth` uses `?training=1` so signed-in teachers are not bounced by `guestOnly`. Start + play on `/training` binds `course_id` / `step` onto the Redis snapshot; when `pull_users` is set, teachers are routed to that page, the modal opens if `modal_key` is set, and a red ring highlights `[data-training-target=…]`. Slide/video steps always use the full-screen overlay instead of a page route. Page and canvas steps keep teachers on the real app page and paint the same marks (text bubbles, roles from COS, arrows, emoji, spotlight, topics) as a transparent viewport overlay so they see what the author placed.

**主题备选** chips can be dragged onto the builder stage as a single `topics` overlay (drop replaces any existing topics card). Clicking an option writes the label into the isolated builder canvas (`left-topic` / `right-topic` on 双气泡图, otherwise the `topic` node).

## Live instructor pad

`TrainingInstructorPad` mounts in `App.vue` (hidden on `/training/builder`). After Start+play, the instructor is routed to the same page teachers see. When they host and a course is playing, a bottom-right pad (above the lesson overlay) shows 上一页 / 下一页 / 停止 / 自由.

- Prev/next walk remaining mark clicks on the current slide, then change slides. The next slide starts at mark 1; the previous slide ends at its last mark (`services/features/training/play_advance.py`).
- 停止 ends the Redis session.
- 自由 keeps the session **live** but sets snapshot `pull_users: false` so teachers stay on the page they are on and may work. Next, or 自由 again, pulls them back (`pull_users: true`).
- Builder preview uses the same pad locally (`advancePlayCursor`) without hitting Redis. The notes bar shifts left (`training-notes--pad`) so it does not sit under the pad.

## Proxy

Existing `/api` `proxy_read_timeout 300s` and `proxy_buffering off` in [production_security_deploy.md](production_security_deploy.md) cover this stream as long as keepalives continue.
