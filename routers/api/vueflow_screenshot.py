"""
Vue Flow Screenshot Module
===========================

Captures diagram PNGs by loading the Vue Flow frontend in Playwright.
Replaces the old D3-based png_export_core.py rendering pipeline.

Flow:
1. Open headless Chromium via BrowserContextManager
2. Navigate to the same backend origin (which serves the SPA)
3. Set the diagram spec in sessionStorage
4. Navigate to /export-render (minimal page that renders DiagramCanvas only)
5. Wait for window.__MINDGRAPH_RENDER_COMPLETE flag
6. Screenshot the .vue-flow-wrapper element
7. Return PNG bytes

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict, List
import asyncio
import json
import logging
import os

from services.infrastructure.utils.browser import BrowserContextManager

logger = logging.getLogger(__name__)

EXPORT_SPEC_SESSION_KEY = "mindgraph_export_spec"
RENDER_TIMEOUT_SECONDS = 20
RENDER_POLL_INTERVAL_MS = 500
POST_RENDER_SETTLE_MS = 500


def _get_base_url() -> str:
    """
    Get the URL where the Vue SPA is accessible.

    Priority:
    1. FRONTEND_URL env var (e.g. http://localhost:5173 for Vite dev server)
    2. Backend origin at http://localhost:{PORT} (production: backend serves dist/)
    """
    frontend_url = os.getenv("FRONTEND_URL", "").rstrip("/")
    if frontend_url:
        return frontend_url
    port = os.getenv("PORT", "9527")
    return f"http://localhost:{port}"


def _build_export_spec(diagram_data: Dict[str, Any], diagram_type: str) -> str:
    """
    Merge diagram_data with type field for ExportRenderPage.

    ExportRenderPage expects: { type: "bubble_map", topic: "...", ... }
    """
    export_spec = {**diagram_data, "type": diagram_type}
    return json.dumps(export_spec, ensure_ascii=False)


def _log_debug_info(
    console_messages: List[str],
    page_errors: List[str],
) -> None:
    """Log browser console messages and errors for debugging."""
    if console_messages:
        logger.error(
            "[VueFlowScreenshot] Browser console (%d messages):",
            len(console_messages),
        )
        for msg in console_messages[-20:]:
            logger.error("[VueFlowScreenshot]   %s", msg)
    if page_errors:
        logger.error(
            "[VueFlowScreenshot] Page errors (%d):",
            len(page_errors),
        )
        for err in page_errors:
            logger.error("[VueFlowScreenshot]   %s", err)


async def _inject_spec_and_navigate(page, base_url: str, spec_json: str):
    """Inject spec via init script and navigate directly to /export-render."""
    escaped_spec = json.dumps(spec_json)
    await page.add_init_script(f"sessionStorage.setItem('{EXPORT_SPEC_SESSION_KEY}', {escaped_spec});")
    logger.debug("[VueFlowScreenshot] Spec will be injected via init script")

    export_url = f"{base_url}/export-render"
    logger.debug("[VueFlowScreenshot] Navigating directly to: %s", export_url)
    await page.goto(export_url, wait_until="domcontentloaded")


async def _wait_for_render(
    page,
    console_messages: List[str],
    page_errors: List[str],
) -> None:
    """Poll window.__MINDGRAPH_RENDER_COMPLETE and check for errors."""
    logger.debug("[VueFlowScreenshot] Waiting for render completion")
    waited = 0.0
    while waited < RENDER_TIMEOUT_SECONDS:
        complete = await page.evaluate(
            "window.__MINDGRAPH_RENDER_COMPLETE === true",
        )
        if complete:
            break
        await asyncio.sleep(RENDER_POLL_INTERVAL_MS / 1000)
        waited += RENDER_POLL_INTERVAL_MS / 1000

    if waited >= RENDER_TIMEOUT_SECONDS:
        _log_debug_info(console_messages, page_errors)
        raise RuntimeError(
            f"Vue Flow render timed out after {RENDER_TIMEOUT_SECONDS}s",
        )

    render_error = await page.evaluate("window.__MINDGRAPH_RENDER_ERROR")
    if render_error:
        _log_debug_info(console_messages, page_errors)
        raise RuntimeError(f"Vue Flow render error: {render_error}")


async def _screenshot_canvas(
    page,
    console_messages: List[str],
    page_errors: List[str],
) -> bytes:
    """Wait for Vue Flow nodes, then screenshot the canvas wrapper."""
    logger.debug("[VueFlowScreenshot] Render complete, waiting for nodes")

    try:
        await page.wait_for_selector(".vue-flow__node", timeout=5000)
        logger.debug("[VueFlowScreenshot] Vue Flow nodes found in DOM")
    except Exception as exc:
        _log_debug_info(console_messages, page_errors)
        raise RuntimeError(
            "No .vue-flow__node elements found after render",
        ) from exc

    await asyncio.sleep(POST_RENDER_SETTLE_MS / 1000)

    await page.evaluate("document.querySelectorAll('.el-notification, .el-message').forEach(el => el.remove())")

    wrapper = await page.query_selector(".vue-flow-wrapper")
    if not wrapper:
        wrapper = await page.query_selector(".vue-flow")
    if not wrapper:
        _log_debug_info(console_messages, page_errors)
        raise RuntimeError(
            "Could not find .vue-flow-wrapper or .vue-flow element",
        )

    await wrapper.scroll_into_view_if_needed()
    return await wrapper.screenshot(omit_background=False, timeout=30000)


async def capture_diagram_screenshot(
    diagram_data: Dict[str, Any],
    diagram_type: str,
    width: int = 1200,
    height: int = 800,
) -> bytes:
    """
    Capture a PNG screenshot of a diagram by rendering it in the Vue Flow frontend.

    Args:
        diagram_data: The diagram spec from the LLM (topic, attributes, etc.)
        diagram_type: Diagram type string (e.g. 'bubble_map', 'tree_map')
        width: Viewport width in pixels
        height: Viewport height in pixels

    Returns:
        Raw PNG bytes of the rendered diagram

    Raises:
        RuntimeError: If rendering fails or times out
    """
    base_url = _get_base_url()
    spec_json = _build_export_spec(diagram_data, diagram_type)
    console_messages: List[str] = []
    page_errors: List[str] = []

    logger.debug(
        "[VueFlowScreenshot] Starting capture: type=%s, viewport=%dx%d",
        diagram_type,
        width,
        height,
    )

    async with BrowserContextManager() as context:
        page = await context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(30000)

        page.on(
            "console",
            lambda msg: (
                console_messages.append(f"{msg.type}: {msg.text}"),
                logger.debug("[VueFlowScreenshot] CONSOLE: %s: %s", msg.type, msg.text),
            ),
        )
        page.on(
            "pageerror",
            lambda err: (
                page_errors.append(str(err)),
                logger.error("[VueFlowScreenshot] PAGE ERROR: %s", err),
            ),
        )

        try:
            await _inject_spec_and_navigate(page, base_url, spec_json)
            await _wait_for_render(page, console_messages, page_errors)
            screenshot_bytes = await _screenshot_canvas(
                page,
                console_messages,
                page_errors,
            )

            logger.info(
                "[VueFlowScreenshot] Screenshot captured: %d bytes, type=%s",
                len(screenshot_bytes),
                diagram_type,
            )
            return screenshot_bytes

        except RuntimeError:
            raise
        except Exception as exc:
            _log_debug_info(console_messages, page_errors)
            logger.error(
                "[VueFlowScreenshot] Unexpected error: %s",
                exc,
                exc_info=True,
            )
            raise RuntimeError(f"Vue Flow screenshot failed: {exc}") from exc
