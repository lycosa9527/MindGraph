"""Phone and token in the OS keychain. Other preferences stay in a plain file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import keyring
from keyring.errors import KeyringError

SERVICE = "mindgraph-desktop-pet"
USER = "account"


def _config_dir() -> Path:
    if sys.platform == "win32":
        root = Path.home() / "AppData" / "Local" / "MindGraph Pet"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "MindGraph Pet"
    else:
        root = Path.home() / ".mindgraph-pet"
    root.mkdir(parents=True, exist_ok=True)
    return root


def preferences_path() -> Path:
    """Non-secret settings: server, mascot, window position, open at login."""
    return _config_dir() / "preferences.json"


def load_preferences() -> dict[str, str]:
    """Return saved preferences. Missing file yields an empty dict."""
    path = preferences_path()
    if not path.is_file():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


def save_preferences(values: dict[str, str]) -> None:
    """Write non-secret preferences."""
    preferences_path().write_text(json.dumps(values, indent=2), encoding="utf-8")


def load_secrets() -> tuple[str, str]:
    """Return phone and token, or two empty strings."""
    try:
        raw = keyring.get_password(SERVICE, USER)
    except KeyringError:
        return "", ""
    if not raw:
        return "", ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return "", ""
    if not isinstance(parsed, dict):
        return "", ""
    return str(parsed.get("phone") or ""), str(parsed.get("token") or "")


def save_secrets(phone: str, token: str) -> None:
    """Store the phone and token together in the OS keychain."""
    payload = json.dumps({"phone": phone.strip(), "token": token.strip()})
    keyring.set_password(SERVICE, USER, payload)
