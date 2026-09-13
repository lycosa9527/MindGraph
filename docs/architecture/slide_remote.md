# 演讲模式 watch remote

Desktop 放映 → **演讲模式** walks the mind map (一级分支 or 深度遍历). The 1.85C Super tile **演讲模式** (`com.mindgraph.slides`) is a clicker for that HUD. Auth is the same flash-time `mgat_` + `X-MG-Account` as Kitty. There is no feature flag.

## Session

One Redis room per account. Desktop canvas opens it when 演讲模式 starts and `PUT`s only when the HUD changes. TTL (120s) is refreshed by the desktop WebSocket (`EXPIRE` while that socket is up). Leaving slides or leaving the canvas `POST`s `/end`. The watch never hosts the room and does not refresh TTL; swipe-home does not quit the desktop show.

The watch can start the show: pick a diagram from the account 图库 (same `GET /api/diagrams` list as Kitty), then green **开始**. Desktop always drains commands. `start` opens that diagram on `/canvas` and enters 演讲模式. Red **退出** closes the 放映 rail.

## Transport

Same push path as Kitty on the watch: one WebSocket while the 演讲模式 face is open (`kitty_ws` + `/api/ws/slides-remote`). The face closes the socket when hidden so Kitty can reuse the client. No 2s `sessions/active` poll.

1. Watch `POST /command` writes Redis and `PUBLISH`es `slides_command_pending`
2. Desktop applies, then `PUT /sessions` when the HUD changes
3. Each app worker has **one** pattern-subscribe (`slide_remote:user:*:wake`) — O(workers), not O(users)
4. Local sockets get one frame: `slides_command_pending` (desktop LPOP) or `slides_snapshot` (watch HUD)
5. Connect also pushes the current snapshot so the watch hydrates without GET

- `PUT /api/slides/remote/sessions` — desktop snapshot on HUD change only; snapshot fanout only when HUD fields change
- `GET /api/slides/remote/sessions/active` — fallback hydrate if the watch socket is down
- `POST /api/slides/remote/command` — watch click (`next` / `prev` / `autoplay` / `traversal` / `quit` / `start` with `diagram_id`)
- `WS /api/ws/slides-remote` — desktop + 1.85C watch (cookie or `mgat_`). Event frames only. Desktop sockets `EXPIRE` the Redis room; watch sockets do not
- `GET /api/slides/remote/commands` — desktop drain (instant LPOP after WS wake or on socket open)
- `POST /api/slides/remote/end` — desktop leaves slides; idle snapshot is pushed to the watch

`start` can be enqueued while idle. Other actions still need a live room.

## 360 face

Inset pad: sliding **一级分支 / 深度遍历** pill, **上一页 | 下一页**, full-width **自动轮播**. Bottom row matches Kitty / 校本培训: slate **图库** (`54,260`, `136×44`) and a host pill (`206,260`, `100×44`) that is green **开始** (enabled after a pick) or red **退出** while live. Status uses the same green / orange disk as Kitty: **请选图库** / **点开始放映** / `n / m`. Preview: [`esp32/firmware/1.85c/round_ui/preview/slides_lvgl_face.html`](../../esp32/firmware/1.85c/round_ui/preview/slides_lvgl_face.html).
