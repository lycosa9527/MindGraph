"""Green-screen key follows the outer edge and keeps green trapped inside props."""

from __future__ import annotations

import numpy as np
from PIL import Image

from scripts.training_roles.export import key_green


def _alpha(image: Image.Image) -> np.ndarray:
    return np.asarray(image)[:, :, 3]


def test_green_button_inside_a_machine_stays_opaque() -> None:
    """A lamp or button enclosed by the prop is not part of the screen."""
    canvas = np.zeros((100, 100, 3), dtype=np.uint8)
    canvas[:, :] = (0, 255, 0)
    canvas[25:75, 25:75] = (70, 70, 74)
    canvas[42:54, 42:54] = (0, 255, 0)
    keyed = key_green(Image.fromarray(canvas, "RGB"))
    alpha = _alpha(keyed)
    color = np.asarray(keyed)
    assert alpha[0, 0] == 0
    assert alpha[50, 30] == 255
    assert alpha[48, 48] == 255
    assert color[48, 48, 1] > 200


def test_dark_floor_goes_and_cloth_spill_stays_grey() -> None:
    """A dim green floor touching the rim is screen; a grey hoodie keeps its cloth."""
    canvas = np.zeros((100, 100, 3), dtype=np.uint8)
    canvas[:, :] = (0, 255, 0)
    canvas[20:80, 20:80] = (40, 58, 42)
    canvas[80:100, :] = (13, 66, 18)
    keyed = key_green(Image.fromarray(canvas, "RGB"))
    alpha = _alpha(keyed)
    color = np.asarray(keyed)
    assert alpha[90, 50] == 0
    assert alpha[50, 50] == 255
    assert int(color[50, 50, 1]) == max(int(color[50, 50, 0]), int(color[50, 50, 2]))


def test_large_enclosed_screen_goes_and_a_button_stays() -> None:
    """A backdrop trapped behind a prop is removed. A small green button stays."""
    canvas = np.zeros((160, 160, 3), dtype=np.uint8)
    canvas[:, :] = (0, 255, 0)
    canvas[15:145, 15:145] = (70, 70, 74)
    canvas[40:80, 40:80] = (20, 90, 24)
    canvas[100:112, 100:112] = (0, 220, 0)
    keyed = key_green(Image.fromarray(canvas, "RGB"))
    alpha = _alpha(keyed)
    color = np.asarray(keyed)
    assert alpha[0, 0] == 0
    assert alpha[60, 60] == 0
    assert alpha[106, 106] == 255
    assert color[106, 106, 1] > 200


def test_green_gap_that_opens_to_the_screen_is_removed() -> None:
    """Space between legs stays clear when it reaches the backdrop."""
    canvas = np.zeros((80, 80, 3), dtype=np.uint8)
    canvas[:, :] = (0, 255, 0)
    canvas[10:70, 15:28] = (40, 40, 40)
    canvas[10:70, 52:65] = (40, 40, 40)
    alpha = _alpha(key_green(Image.fromarray(canvas, "RGB")))
    assert alpha[40, 20] == 255
    assert alpha[40, 40] == 0
