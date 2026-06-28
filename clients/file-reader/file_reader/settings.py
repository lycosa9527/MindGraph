"""Persist file-reader preferences and DPAPI-protected credentials."""

from __future__ import annotations

import json
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from file_reader.dpapi_store import DpapiError, dpapi_available, protect_credentials, unprotect_credentials
from file_reader.server_url import ServerUrlError, normalize_server_url

DEFAULT_SERVER_URL = "https://test.mindspringedu.com"

SETTINGS_DIR = Path(tempfile.gettempdir()) / "mindgraph-file-reader"
PREFS_PATH = SETTINGS_DIR / "settings.json"
CREDENTIALS_PATH = SETTINGS_DIR / "credentials.dpapi"

# Backward-compatible alias used by the UI status line.
SETTINGS_PATH = PREFS_PATH

LEGACY_SETTINGS_PATH = Path.home() / ".mindgraph" / "file-reader-settings.json"
LEGACY_CHAT_READER_PATH = Path.home() / ".mindgraph" / "chat-reader-settings.json"
LEGACY_COMBINED_PATHS = (PREFS_PATH, LEGACY_SETTINGS_PATH, LEGACY_CHAT_READER_PATH)


@dataclass
class FileReaderSettings:
    """User settings for the Windows file reader."""

    server_url: str = DEFAULT_SERVER_URL
    api_token: str = ""
    account_phone: str = ""
    platform: str = "wechat"

    @classmethod
    def load(cls) -> "FileReaderSettings":
        """Load settings, migrating legacy plaintext stores when needed."""
        if PREFS_PATH.is_file() and cls._combined_file_has_secrets(PREFS_PATH) and not CREDENTIALS_PATH.is_file():
            loaded = cls._load_combined_file(PREFS_PATH)
            if loaded is not None:
                loaded.save()
                cls._remove_legacy_credential_files()
                return loaded

        if CREDENTIALS_PATH.is_file() or PREFS_PATH.is_file():
            return cls._load_split_store()

        for path in (LEGACY_SETTINGS_PATH, LEGACY_CHAT_READER_PATH):
            if not path.is_file():
                continue
            loaded = cls._load_combined_file(path)
            if loaded is not None:
                loaded.save()
                cls._remove_legacy_credential_files()
                return loaded
        return cls()

    @staticmethod
    def _combined_file_has_secrets(path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(data, dict):
            return False
        return bool(data.get("api_token") or data.get("account_phone"))

    @classmethod
    def _load_split_store(cls) -> "FileReaderSettings":
        prefs = cls._read_json(PREFS_PATH) if PREFS_PATH.is_file() else {}
        settings = cls(
            server_url=str(prefs.get("server_url") or DEFAULT_SERVER_URL),
            platform=str(prefs.get("platform") or "wechat"),
        )
        if CREDENTIALS_PATH.is_file():
            try:
                blob = CREDENTIALS_PATH.read_bytes()
                secrets = unprotect_credentials(blob)
                settings.api_token = secrets.get("api_token", "")
                settings.account_phone = secrets.get("account_phone", "")
            except (OSError, DpapiError, json.JSONDecodeError, ValueError):
                pass
        try:
            settings.server_url = normalize_server_url(settings.server_url)
        except ServerUrlError:
            settings.server_url = DEFAULT_SERVER_URL
        return settings

    @classmethod
    def _load_combined_file(cls, path: Path) -> Optional["FileReaderSettings"]:
        data = cls._read_json(path)
        if not data:
            return None
        server_url = str(data.get("server_url") or DEFAULT_SERVER_URL)
        try:
            server_url = normalize_server_url(server_url)
        except ServerUrlError:
            server_url = DEFAULT_SERVER_URL
        return cls(
            server_url=server_url,
            api_token=str(data.get("api_token") or ""),
            account_phone=str(data.get("account_phone") or ""),
            platform=str(data.get("platform") or "wechat"),
        )

    @staticmethod
    def _read_json(path: Path) -> Dict[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def save(self) -> None:
        """Write non-secret prefs and DPAPI-protected credentials."""
        normalized = normalize_server_url(self.server_url)
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        prefs = {
            "server_url": normalized,
            "platform": self.platform,
        }
        PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
        _restrict_to_current_user(PREFS_PATH)

        token = self.api_token.strip()
        phone = self.account_phone.strip()
        if token and phone:
            if not dpapi_available():
                raise DpapiError("Credential encryption requires Windows DPAPI")
            CREDENTIALS_PATH.write_bytes(protect_credentials(token, phone))
            _restrict_to_current_user(CREDENTIALS_PATH)
        elif CREDENTIALS_PATH.is_file():
            CREDENTIALS_PATH.unlink()

        self.server_url = normalized

    def clear(self) -> None:
        """Remove saved credentials and legacy plaintext copies."""
        for path in (PREFS_PATH, CREDENTIALS_PATH, LEGACY_SETTINGS_PATH, LEGACY_CHAT_READER_PATH):
            if path.is_file():
                path.unlink()
        if SETTINGS_DIR.is_dir() and not any(SETTINGS_DIR.iterdir()):
            SETTINGS_DIR.rmdir()
        self.api_token = ""
        self.account_phone = ""
        self.server_url = DEFAULT_SERVER_URL

    @classmethod
    def _remove_legacy_credential_files(cls) -> None:
        """Delete plaintext credential files after migration."""
        for path in LEGACY_COMBINED_PATHS:
            if path.is_file() and cls._combined_file_has_secrets(path):
                path.unlink()


def _restrict_to_current_user(path: Path) -> None:
    """Best-effort POSIX mode; Windows relies on DPAPI for the secrets file."""
    if sys.platform == "win32":
        return
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        return
