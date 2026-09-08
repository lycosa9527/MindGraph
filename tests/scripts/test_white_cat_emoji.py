"""White-cat emoji catalog stays separate from Course Builder roles."""

from __future__ import annotations

from scripts.training_roles.catalog import SHELL as ROLE_SHELL
from scripts.training_roles.catalog import catalog_ids as role_catalog_ids
from scripts.white_cat_emoji.catalog import (
    EMOJI_ACTIONS,
    SHELL,
    action_by_id,
    catalog_ids,
    clip_name,
)
from scripts.white_cat_emoji.paths import DESKTOP_DIR, OUT_DIR, STILL_FRONT, STILL_THREE_QUARTER


def test_white_cat_ids_are_twenty_and_unique() -> None:
    """Twenty separate emoji jobs, one id each."""
    ids = catalog_ids()
    assert len(ids) == 20
    assert len(set(ids)) == 20
    assert ids[0] == "01-look-here"
    assert ids[-1] == "20-dismiss"
    assert clip_name(EMOJI_ACTIONS[10]) == "11-clap_鼓掌欢呼"


def test_action_by_id_accepts_short_and_slug() -> None:
    """Look up by 01 or 01-look-here."""
    assert action_by_id("01")["slug"] == "look-here"
    assert action_by_id("11-clap")["name"] == "鼓掌欢呼"


def test_white_cat_ids_align_but_shell_stays_grumpy() -> None:
    """Same action ids as Course Builder, different locked face and output dir."""
    assert catalog_ids() == role_catalog_ids()
    assert "臭脸" in SHELL
    assert "黑色小猫" not in SHELL
    assert "黑色小猫" in ROLE_SHELL
    assert STILL_FRONT.name == "fullbody-still-noptr-2.png"
    assert STILL_FRONT.is_file()
    assert STILL_THREE_QUARTER.is_file()
    assert STILL_FRONT.stat().st_size > 100_000
    assert "scripts/cat_emoji/stills/white" in STILL_FRONT.as_posix()
    assert OUT_DIR == DESKTOP_DIR / "actions"
