"""Log resolved COS write prefixes once at startup."""

from __future__ import annotations

import logging

from config.cos_env_prefix import (
    cos_env_root,
    cos_production_tree_enabled,
    uses_live_production_prefixes,
)
from config.settings import config
from services.infrastructure.sync.cos_sync_env import normalized_cos_sync_prefix
from services.utils.tencent_cos_client import COS_KEY_PREFIX

logger = logging.getLogger(__name__)


def log_cos_prefix_posture() -> None:
    """Print the env root and every feature prefix operators must verify."""
    if uses_live_production_prefixes():
        layout = "live-production"
    elif cos_production_tree_enabled():
        layout = "production-tree"
    else:
        layout = f"env-root:{cos_env_root()}"
    logger.info(
        "[COS] layout=%s documents=%s showcase=%s zhihui=%s temp_images=%s "
        "training=%s workshop=%s backups=%s sync=%s load_from_cos=%s",
        layout,
        config.COS_DOCUMENTS_PREFIX,
        config.COS_SHOWCASE_PREFIX,
        config.COS_ZHIHUI_PREFIX,
        config.COS_TEMP_IMAGES_PREFIX,
        config.COS_TRAINING_PREFIX,
        config.COS_WORKSHOP_PREFIX,
        COS_KEY_PREFIX,
        normalized_cos_sync_prefix(),
        config.COURSE_BUILDER_LOAD_FROM_COS,
    )
    if cos_production_tree_enabled():
        logger.warning(
            "[COS] COS_ENV_PREFIX=production writes under production/; "
            "confirm the bucket was migrated before serving traffic"
        )
