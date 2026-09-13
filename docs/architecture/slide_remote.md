# 演讲模式 watch remote

Desktop 放映 → **演讲模式** walks the mind map (一级分支 or 深度遍历). The 1.85C Super tile **演讲模式** (`com.mindgraph.slides`) is a clicker for that HUD. Auth is the same flash-time `mgat_` + `X-MG-Account` as Kitty. There is no feature flag.

## Session

One Redis room per account. Desktop canvas opens it when 演讲模式 starts and heartbeats the snapshot every 2s (TTL 120s). Leaving slides or leaving the canvas `POST`s `/end`. The watch never hosts the room; swipe-home does not quit the desktop show.

The watch can start the show: pick a diagram from the account 图库 (same `GET /api/diagrams` list as Kitty), then green **开始**. Desktop always drains commands. `start` opens that diagram on `/canvas` and enters 演讲模式. Red **退出** closes the 放映 rail.

## Transport

The watch does not use SSE.

- `PUT /api/slides/remote/sessions` — desktop snapshot (`slide_index`, `slide_count`, `traversal`, `autoplay`, `can_prev`, `can_next`)
- `GET /api/slides/remote/sessions/active` — watch poll (2s). Idle when the desktop is not in 演讲模式
- `POST /api/slides/remote/command` — watch click (`next` / `prev` / `autoplay` / `traversal` / `quit` / `start` with `diagram_id`)
- `GET /api/slides/remote/commands` — desktop drain (400ms), including `start` before a room exists
- `POST /api/slides/remote/end` — desktop leaves slides

`start` can be enqueued while idle. Other actions still need a live room.

## 360 face

Inset pad: sliding **一级分支 / 深度遍历** pill, **上一页 | 下一页**, full-width **自动轮播**. Bottom row matches Kitty / 校本培训: slate **图库** (`54,260`, `136×44`) and a host pill (`206,260`, `100×44`) that is green **开始** (enabled after a pick) or red **退出** while live. Status uses the same green / orange disk as Kitty: **请选图库** / **点开始放映** / `n / m`. Preview: [`esp32/firmware/1.85c/round_ui/preview/slides_lvgl_face.html`](../../esp32/firmware/1.85c/round_ui/preview/slides_lvgl_face.html).
