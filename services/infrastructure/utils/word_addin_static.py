"""Mount MindGraph for Word static shell at ``/word-addin/*`` (production)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_WORD_ADDIN = _PROJECT_ROOT / "word-addin"


def setup_word_addin_static(app: FastAPI) -> bool:
    """
    Serve Office.js add-in HTML/JS/icons from the repo ``word-addin/`` tree.

    Mounts only ``src/`` and ``assets/`` (never ``node_modules``).
    Returns True when mounts were registered.
    """
    src_dir = _WORD_ADDIN / "src"
    assets_dir = _WORD_ADDIN / "assets"
    mounted = False
    if src_dir.is_dir():
        app.mount(
            "/word-addin/src",
            StaticFiles(directory=str(src_dir), html=False),
            name="word-addin-src",
        )
        mounted = True
    if assets_dir.is_dir():
        app.mount(
            "/word-addin/assets",
            StaticFiles(directory=str(assets_dir), html=False),
            name="word-addin-assets",
        )
        mounted = True
    if mounted:
        logger.info("[WordAddin] Static shell mounted at /word-addin/src and /word-addin/assets")
    else:
        logger.warning("[WordAddin] word-addin/src or assets missing; shell not mounted")
    return mounted
