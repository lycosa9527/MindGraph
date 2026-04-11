"""
Copy Fail2ban templates from the repo into /etc/fail2ban (requires appropriate permissions).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from services.infrastructure.security.fail2ban_integration.paths import fail2ban_resources_dir

logger = logging.getLogger(__name__)


def deploy_fail2ban_templates(
    target_root: Path,
    source_root: Optional[Path] = None,
) -> None:
    """
    Copy resources/fail2ban/{filter.d,jail.d,action.d} into target_root.

    Typical target_root: Path("/etc/fail2ban")
    """
    src = source_root or fail2ban_resources_dir()
    if not src.is_dir():
        raise FileNotFoundError(f"Missing Fail2ban templates: {src}")

    for sub in ("filter.d", "jail.d", "action.d"):
        src_sub = src / sub
        if not src_sub.is_dir():
            continue
        dst_sub = target_root / sub
        dst_sub.mkdir(parents=True, exist_ok=True)
        for item in src_sub.iterdir():
            if item.is_file():
                shutil.copy2(item, dst_sub / item.name)
                logger.info("Installed %s -> %s", item, dst_sub / item.name)
