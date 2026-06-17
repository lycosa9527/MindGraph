"""Resolve paths to bundled Fail2ban templates under resources/fail2ban/.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from pathlib import Path


def project_root_from_here() -> Path:
    """MindGraph repo root (parent of services/)."""
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def fail2ban_resources_dir() -> Path:
    """Directory containing jail.d, filter.d, action.d templates."""
    return project_root_from_here() / "resources" / "fail2ban"
