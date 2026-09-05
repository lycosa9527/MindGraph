"""Read DashScope keys from the repo .env without printing secrets."""

from __future__ import annotations

from scripts.training_roles.paths import ENV_PATH


def load_env_value(name: str) -> str:
    """Return one KEY=value from .env, or empty string."""
    if not ENV_PATH.is_file():
        return ""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def dashscope_api_key() -> str:
    """Prefer DASHSCOPE_API_KEY, then QWEN_API_KEY."""
    key = load_env_value("DASHSCOPE_API_KEY") or load_env_value("QWEN_API_KEY")
    if not key:
        raise RuntimeError("DashScope API key missing in .env")
    return key


def dashscope_workspace() -> str:
    """Beijing MaaS workspace id used for Wan I2V."""
    workspace = load_env_value("DASHSCOPE_WORKSPACE_ID")
    if not workspace:
        raise RuntimeError("DASHSCOPE_WORKSPACE_ID missing in .env")
    return workspace
