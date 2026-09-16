"""Siamese tester-cat still kit stays smaller, bespectacled, and separate."""

from __future__ import annotations

from scripts.cat_emoji.paths import MASCOTS_DIR, SIAMESE_DESKTOP_DIR
from scripts.siamese_cat_emoji.catalog import NEGATIVE, SHELL, STILL_SHOTS, shot_by_id
from scripts.siamese_cat_emoji.paths import (
    EXPORT_DIR,
    STILL_SIZE,
    export_still_path,
    still_filename,
)


def test_two_still_shots_and_lookup() -> None:
    """Front idle then 3/4, same filenames as the other cats."""
    assert [shot["id"] for shot in STILL_SHOTS] == ["2", "1"]
    assert shot_by_id("2")["slug"] == "front"
    assert shot_by_id("1-three-quarter")["name"] == "四分之三侧站"
    assert still_filename("2") == "fullbody-still-noptr-2.png"
    assert still_filename("1") == "fullbody-still-noptr-1.png"


def test_identity_is_small_siamese_tester() -> None:
    """Glasses, seal-point Siamese, smaller than the black/white lock."""
    assert "暹罗" in SHELL
    assert "奶油色" in SHELL
    assert "巧克力" in SHELL
    assert "斜杏仁形" in SHELL
    assert "楔形头" in SHELL
    assert "黑色小圆框眼镜" in SHELL
    assert "再小一圈" in SHELL
    assert "#00FF00" in SHELL
    assert "测试员" in SHELL
    assert "雌性" not in SHELL
    assert "白猫脸" in NEGATIVE
    assert "圆苹果脸" in NEGATIVE
    assert "草莓粉" in NEGATIVE
    assert STILL_SIZE == "1280*1920"


def test_exports_land_under_pictures_mascots() -> None:
    """Siamese kit lives with the other mascots, not on the desktop."""
    assert EXPORT_DIR == SIAMESE_DESKTOP_DIR
    assert SIAMESE_DESKTOP_DIR == MASCOTS_DIR / "siamese-cat-mascot"
    assert export_still_path("2") == EXPORT_DIR / "fullbody-still-noptr-2.png"
    assert "Pictures/mascots" in EXPORT_DIR.as_posix()
