"""Headless PNG clicks empty pane chrome, not the fitted diagram."""

from __future__ import annotations

from routers.api.vueflow_screenshot import pane_empty_click_point


def test_pane_empty_click_is_inset_not_center() -> None:
    """Fit-view parks nodes in the middle; the click must stay in the corner."""
    box = {"x": 100.0, "y": 40.0, "width": 1200.0, "height": 800.0}
    click_x, click_y = pane_empty_click_point(box)
    assert click_x == 112.0
    assert click_y == 52.0
    assert click_x < box["x"] + box["width"] / 2
    assert click_y < box["y"] + box["height"] / 2
