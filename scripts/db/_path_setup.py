"""Add project root to sys.path and load project ``.env`` for scripts in ``scripts/db/``."""

import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

_DEFAULT_ENV_PATH = project_root / ".env"

# Always prefer repo ``.env`` for COS mirror credentials (ignore stale shell exports).
_COS_ENV_OVERRIDE_KEYS = frozenset(
    {
        "TENCENT_SMS_SECRET_ID",
        "TENCENT_SMS_SECRET_KEY",
        "COS_BUCKET",
        "COS_REGION",
        "COS_KEY_PREFIX",
        "COS_SYNC_ENABLED",
        "COS_SYNC_ROLE",
        "CELERY_TARGET_VERSION",
        "QDRANT_TARGET_VERSION",
        "QDRANT_DOWNLOAD_SOURCE",
        "QDRANT_COS_AUTO_INSTALL",
    }
)


def _resolve_env_path() -> Path:
    """Project ``.env``, or ``MINDGRAPH_ENV_FILE`` when set."""
    env_override = os.getenv("MINDGRAPH_ENV_FILE")
    if env_override:
        path = Path(env_override).expanduser()
        return path if path.is_absolute() else (project_root / path).resolve()
    return _DEFAULT_ENV_PATH


def _apply_env_file(path: Path) -> None:
    """Load ``.env``; COS keys always win over stale shell exports."""
    if not path.is_file():
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"').split("#", 1)[0].strip()
        if not key:
            continue
        if key in _COS_ENV_OVERRIDE_KEYS or key not in os.environ:
            os.environ[key] = val


_apply_env_file(_resolve_env_path())
