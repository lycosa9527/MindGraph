"""Render real diagrams in headless Chromium and check the painted boxes.

Uses the same ``/export-render`` page as server PNG export, against an app you
already started (this script never starts one). For each fixture in
``tmp/real_diagrams/fixtures`` it follows every node frame by frame, from the
first frame it is painted until the layout holds still. It then reports

* nodes that moved or resized after first paint (a visible jump),
* overlapping node boxes,
* with ``--compare``: box drift and screenshot pixel change against an earlier run.

Usage::

    python -m scripts.render_check.headless_render_check --base-url http://localhost:3000 --label before
    # change code, then
    python -m scripts.render_check.headless_render_check --base-url http://localhost:3000 \\
        --label after --compare before

Output: ``tmp/real_diagrams/headless/<label>/`` (one JSON + PNG per fixture,
plus ``summary.txt``). Exit status 1 when ``--compare`` finds a regression.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, cast

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from scripts.render_check.render_compare import (
    TimelineRow,
    compare_runs,
    count_overlaps,
    describe_jumps,
    settled_rows,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tmp" / "real_diagrams" / "fixtures"
OUTPUT_ROOT = REPO_ROOT / "tmp" / "real_diagrams" / "headless"
# Keep in sync with routers/api/vueflow_screenshot.py and ExportRenderPage.vue.
EXPORT_SPEC_SESSION_KEY = "mindgraph_export_spec"
HEADLESS_EXPORT_SESSION_KEY = "mindgraph_headless_export"
MINDMAP_CANVAS_MODE_KEY = "mindgraph_mindmap_canvas_mode"
MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY = "mindgraph_mindmap_canvas_v2_default_migrated"
READY_TIMEOUT_MS = 20_000
SETTLE_MS = 1_500
STILL_STYLE = "*, *::before, *::after { animation: none !important; transition: none !important; }"

STABLE_FRAMES = 45
MAX_FRAMES = 900
# Runs before the app. Follows every node by Vue Flow id from the first frame it
# is painted (sized and not hidden) until the layout holds still.
TIMELINE_JS = f"""(() => {{
  const nodes = new Map()
  let frames = 0
  let stable = 0
  const read = (el) => {{
    const match = /translate\\(\\s*(-?[\\d.]+)px,\\s*(-?[\\d.]+)px/.exec(el.style.transform)
    if (!match || el.offsetWidth <= 0 || el.offsetHeight <= 0) return null
    if (getComputedStyle(el).visibility === 'hidden') return null
    return {{ x: Number(match[1]), y: Number(match[2]), w: el.offsetWidth, h: el.offsetHeight }}
  }}
  const moved = (a, b) =>
    Math.abs(a.x - b.x) > 1 || Math.abs(a.y - b.y) > 1 || Math.abs(a.w - b.w) > 1 || Math.abs(a.h - b.h) > 1
  const tick = () => {{
    let changed = false
    for (const el of document.querySelectorAll('.vue-flow__node')) {{
      const id = el.dataset.id
      const box = id ? read(el) : null
      if (!box) continue
      const row = nodes.get(id)
      if (!row) {{
        const typeClass = [...el.classList].find((c) => c.startsWith('vue-flow__node-')) || ''
        nodes.set(id, {{
          el,
          type: typeClass.replace('vue-flow__node-', ''),
          first: box,
          last: box,
          moves: 0,
          fonts_at_first: document.fonts.status,
        }})
        changed = true
      }} else if (moved(row.last, box)) {{
        row.last = box
        row.moves += 1
        changed = true
      }}
    }}
    if (nodes.size > 0) frames += 1
    stable = changed ? 0 : stable + 1
    const ready = window.__MINDGRAPH_EXPORT_HEADLESS_CLICK_PENDING === true
    if ((ready && stable >= {STABLE_FRAMES}) || frames >= {MAX_FRAMES}) {{
      window.__mgTimelineDone = true
      return
    }}
    requestAnimationFrame(tick)
  }}
  requestAnimationFrame(tick)
  window.__mgReadTimeline = () => {{
    const seen = new Map()
    return [...nodes.entries()].map(([id, row]) => {{
      const text = (row.el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 40)
      const label = row.type + ':' + text
      const n = seen.get(label) || 0
      seen.set(label, n + 1)
      return {{
        id,
        key: label + '#' + n,
        type: row.type,
        first: row.first,
        last: row.last,
        moves: row.moves,
        fonts_at_first: row.fonts_at_first,
      }}
    }})
  }}
}})()"""


def _init_script(spec: dict[str, Any], diagram_type: str) -> str:
    payload = json.dumps(json.dumps({**spec, "type": diagram_type}, ensure_ascii=False))
    return (
        f"sessionStorage.setItem('{HEADLESS_EXPORT_SESSION_KEY}', '1');"
        f"sessionStorage.setItem('{EXPORT_SPEC_SESSION_KEY}', {payload});"
        f"localStorage.setItem('{MINDMAP_CANVAS_MODE_KEY}', 'v2');"
        f"localStorage.setItem('{MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY}', '1');"
    )


def _render_one(page: Page, base_url: str, fixture: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    name = str(fixture["name"])
    page.add_init_script(_init_script(cast(dict[str, Any], fixture["spec"]), str(fixture["diagram_type"])))
    page.add_init_script(TIMELINE_JS)
    page.goto(f"{base_url}/export-render", wait_until="domcontentloaded")
    page.wait_for_function(
        "() => window.__MINDGRAPH_EXPORT_HEADLESS_CLICK_PENDING === true || !!window.__MINDGRAPH_RENDER_ERROR",
        timeout=READY_TIMEOUT_MS,
    )
    error = page.evaluate("window.__MINDGRAPH_RENDER_ERROR")
    if error:
        return {"name": name, "error": str(error)}
    page.wait_for_function("() => window.__mgTimelineDone === true", timeout=READY_TIMEOUT_MS)
    timeline = cast(list[TimelineRow], page.evaluate("window.__mgReadTimeline()"))
    pane = page.locator(".vue-flow__pane").first
    box = pane.bounding_box(timeout=5_000)
    if box:
        page.mouse.click(box["x"] + 12, box["y"] + 12)
    page.evaluate("async () => { await window.__MINDGRAPH_EXPORT_finalize() }")
    page.wait_for_timeout(SETTLE_MS)
    page.add_style_tag(content=STILL_STYLE)
    wrapper = page.query_selector(".vue-flow-wrapper") or page.query_selector(".vue-flow")
    if wrapper:
        wrapper.screenshot(path=str(out_dir / f"{name}.png"))
    settled = settled_rows(timeline)
    return {
        "name": name,
        "diagram_type": fixture["diagram_type"],
        "timeline": timeline,
        "settled": settled,
        "jumps": describe_jumps(timeline),
        "overlaps": count_overlaps(settled),
    }


def run(base_url: str, label: str, only: str | None, viewport: tuple[int, int]) -> list[dict[str, Any]]:
    """Render every fixture; returns one result per fixture."""
    out_dir = OUTPUT_ROOT / label
    out_dir.mkdir(parents=True, exist_ok=True)
    fixtures = sorted(FIXTURE_DIR.glob("*.json"))
    if only:
        fixtures = [path for path in fixtures if only in path.stem]
    if not fixtures:
        raise SystemExit(f"no fixtures in {FIXTURE_DIR}; run scripts.render_check.export_real_diagrams first")
    results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for path in fixtures:
                fixture = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
                context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
                page = context.new_page()
                page_errors: list[str] = []
                page.on("pageerror", lambda err, sink=page_errors: sink.append(str(err)))
                started = time.monotonic()
                result: dict[str, Any]
                try:
                    result = _render_one(page, base_url, fixture, out_dir)
                except PlaywrightError as exc:
                    result = {"name": path.stem, "error": str(exc).splitlines()[0]}
                finally:
                    context.close()
                result["page_errors"] = page_errors
                result["ms"] = round((time.monotonic() - started) * 1000)
                (out_dir / f"{path.stem}.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                results.append(result)
                print(_line(result), flush=True)
        finally:
            browser.close()
    return results


def _line(result: dict[str, Any]) -> str:
    if result.get("error"):
        return f"{result['name']:24} ERROR {result['error']}"
    jumps = cast(list[str], result.get("jumps", []))
    errors = cast(list[str], result.get("page_errors", []))
    return (
        f"{result['name']:24} nodes={len(cast(list[Any], result['settled'])):3} "
        f"jumps={len(jumps):3} overlaps={result['overlaps']:3} pageErrors={len(errors)} {result['ms']}ms"
    )


def main() -> None:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="Render real diagrams in headless Chromium and check painted boxes.")
    parser.add_argument("--base-url", default=os.getenv("FRONTEND_URL") or "http://localhost:9527")
    parser.add_argument("--label", required=True, help="run name; output under tmp/real_diagrams/headless/")
    parser.add_argument("--compare", help="earlier run label to compare against")
    parser.add_argument("--only", help="only fixtures whose name contains this text")
    parser.add_argument("--viewport", default="1600x1000", help="WIDTHxHEIGHT")
    args = parser.parse_args()
    width, height = (int(part) for part in str(args.viewport).lower().split("x"))
    base_url = str(args.base_url).rstrip("/")
    label = str(args.label)
    results = run(base_url, label, args.only, (width, height))
    lines = [_line(result) for result in results]
    regressions: list[str] = []
    if args.compare:
        regressions = compare_runs(OUTPUT_ROOT / str(args.compare), OUTPUT_ROOT / label)
        lines += ["", f"compare {args.compare} -> {label}:", *(regressions or ["no regressions"])]
    summary = "\n".join(lines)
    (OUTPUT_ROOT / label / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    print(summary)
    if regressions:
        sys.exit(1)


if __name__ == "__main__":
    main()
