"""Wan 3.0 settings for desktop-pet clips. Scenes live in actions/."""

from __future__ import annotations

from scripts.desktop_pet.actions import ACTIONS_BY_SLUG, actions_for
from scripts.desktop_pet.actions.pack import PetAction, clip_id
from scripts.desktop_pet.interactions import PAIRS
from scripts.training_roles.wan_client import WAN3_VIDEO

VIDEO_MODEL = WAN3_VIDEO
VIDEO_RESOLUTION = "1080P"
VIDEO_DURATION = 5
VIDEO_RATIO = "9:16"
SCENES_PER_MASCOT = 50

__all__ = [
    "ACTIONS_BY_SLUG",
    "PAIRS",
    "SCENES_PER_MASCOT",
    "VIDEO_DURATION",
    "VIDEO_MODEL",
    "VIDEO_RATIO",
    "VIDEO_RESOLUTION",
    "PetAction",
    "actions_for",
    "clip_id",
]
