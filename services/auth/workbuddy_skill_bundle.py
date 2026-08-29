"""Build the WorkBuddy / OpenClaw skill zip with filled account.json and .env."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

ACCOUNT_JSON_NAME = "account.json"
DOTENV_NAME = ".env"
_SKIP_ACCOUNT_NAMES = frozenset({ACCOUNT_JSON_NAME, "demo.json", DOTENV_NAME})


def _origin(base_url: str) -> str:
    """Strip trailing slash from the public origin."""
    return base_url.rstrip("/")


def build_account_json_text(base_url: str, account: str, token: str) -> str:
    """Skill-folder credentials. Flat keys plus skills.entries.env."""
    origin = _origin(base_url)
    env = {
        "MINDGRAPH_BASE_URL": origin,
        "MINDGRAPH_ACCOUNT": account,
        "MINDGRAPH_TOKEN": token,
    }
    payload = {
        **env,
        "skills": {
            "entries": {
                "mindgraph": {
                    "enabled": True,
                    "env": env,
                }
            }
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def build_skill_dotenv_text(base_url: str, account: str, token: str) -> str:
    """Per-skill .env for hosts that load env from the skill folder."""
    origin = _origin(base_url)
    return f"MINDGRAPH_BASE_URL={origin}\nMINDGRAPH_ACCOUNT={account}\nMINDGRAPH_TOKEN={token}\n"


def _should_skip_path(relative: Path) -> bool:
    """True when the path must not enter the skill zip."""
    parts = relative.parts
    if "__pycache__" in parts:
        return True
    if relative.name in _SKIP_ACCOUNT_NAMES:
        return True
    return any(part.startswith(".") for part in parts)


def zip_skill_directory(
    source_dir: Path,
    arc_root_name: str,
    base_url: str,
    account: str,
    token: str,
) -> bytes:
    """Zip the skill tree and add generated account.json plus .env."""
    if not source_dir.is_dir():
        raise FileNotFoundError(str(source_dir))
    account_json_text = build_account_json_text(base_url, account, token)
    dotenv_text = build_skill_dotenv_text(base_url, account, token)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(source_dir)
            except ValueError:
                continue
            if _should_skip_path(rel):
                continue
            zf.write(path, arcname=f"{arc_root_name}/{rel.as_posix()}")
        zf.writestr(
            f"{arc_root_name}/{ACCOUNT_JSON_NAME}",
            account_json_text.encode("utf-8"),
        )
        zf.writestr(
            f"{arc_root_name}/{DOTENV_NAME}",
            dotenv_text.encode("utf-8"),
        )
    return buffer.getvalue()
