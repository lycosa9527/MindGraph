"""Debug logging for the platform browser tab."""

from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

_LOCK = threading.Lock()


def _log_targets() -> tuple[Path, ...]:
    """Return log file paths (exe dir first when frozen, then TEMP)."""
    targets: list[Path] = []
    if getattr(sys, "frozen", False):
        targets.append(Path(sys.executable).resolve().parent / "smartedu-browser.log")
    temp_root = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))) / "mindgraph-file-reader"
    targets.append(temp_root / "smartedu-browser.log")
    unique: list[Path] = []
    seen: set[str] = set()
    for path in targets:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return tuple(unique)


def debug_log_path() -> Path:
    """Primary path to the append-only platform browser debug log."""
    return _log_targets()[0]


def debug_log_path_display() -> str:
    """Human-readable log path(s) for UI error messages."""
    paths = _log_targets()
    if getattr(sys, "frozen", False):
        return "\n".join(str(path) for path in paths)
    temp = os.environ.get("TEMP") or os.environ.get("TMP") or "TEMP"
    name = temp.rstrip("\\/").split("\\")[-1].split("/")[-1]
    if name.upper() == "TEMP":
        return f"%TEMP%\\mindgraph-file-reader\\{paths[-1].name}"
    return str(paths[-1])


def _stamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def redact_url_for_log(raw_url: str, *, max_path_len: int = 120) -> str:
    """Return a log-safe URL without query tokens or fragments."""
    text = (raw_url or "").strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    parsed = urlparse(text)
    path = parsed.path or "/"
    if len(path) > max_path_len:
        path = f"{path[:max_path_len]}…"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def log_platform_browser(message: str, *, level: str = "INFO") -> None:
    """Append one line to all platform browser debug log targets."""
    line = f"[{_stamp()}] [{level}] {message}\n"
    with _LOCK:
        for path in _log_targets():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line)
                    handle.flush()
            except OSError:
                continue


def log_platform_browser_section(title: str) -> None:
    """Start a visually separated log section."""
    log_platform_browser(f"--- {title} ---")
