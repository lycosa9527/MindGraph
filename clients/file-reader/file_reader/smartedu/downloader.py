# Mirrors chrome-extension/doc-extract/smartedu/downloader.js — keep auth headers in sync.

"""Download SmartEdu assets (PDF stream or m3u8 via ffmpeg)."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from file_reader.smartedu.models import SmartEduAsset
from file_reader.smartedu.token_store import append_access_token, nd_auth_header

ProgressCallback = Callable[[str, float], None]
CHUNK_SIZE = 1024 * 256
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    """Return a Windows-safe filename stem."""
    cleaned = INVALID_FILENAME.sub("_", name.strip())
    cleaned = cleaned.strip(". ")
    return cleaned or "smartedu"


def resolve_ffmpeg_path() -> Optional[Path]:
    """Locate bundled, beside-exe, dev tools/, or PATH ffmpeg executable."""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str):
        candidates.append(Path(meipass) / "tools" / "ffmpeg.exe")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "ffmpeg.exe")
    candidates.append(Path(__file__).resolve().parent.parent.parent / "tools" / "ffmpeg.exe")
    which = shutil.which("ffmpeg")
    if which:
        candidates.append(Path(which))
    for path in candidates:
        if path.is_file():
            return path
    return None


def _download_headers(access_token: str) -> dict[str, str]:
    headers = {
        "User-Agent": "MindGraph-FileReader/1.0",
        "Accept": "*/*",
    }
    auth = nd_auth_header(access_token)
    if auth:
        headers["X-ND-AUTH"] = auth
    return headers


def _notify(progress: Optional[ProgressCallback], message: str, fraction: float) -> None:
    if progress is not None:
        progress(message, max(0.0, min(1.0, fraction)))


def download_binary_file(
    url: str,
    dest: Path,
    access_token: str,
    *,
    progress: Optional[ProgressCallback] = None,
    timeout: int = 120,
) -> None:
    """Stream a PDF (or other binary) to disk."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    download_url = append_access_token(url, access_token)
    request = Request(download_url, headers=_download_headers(access_token), method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            total_raw = response.headers.get("Content-Length")
            total = int(total_raw) if total_raw and total_raw.isdigit() else 0
            read = 0
            with dest.open("wb") as handle:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    read += len(chunk)
                    if total > 0:
                        _notify(progress, dest.name, read / total)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"HTTP {exc.code}: {body[:200]}") from exc
    except URLError as exc:
        raise ValueError(f"Network error: {exc.reason}") from exc


def download_m3u8_to_mp4(
    url: str,
    dest: Path,
    access_token: str,
    *,
    ffmpeg_path: Optional[Path] = None,
    progress: Optional[ProgressCallback] = None,
    timeout: int = 3600,
) -> None:
    """Merge DRM m3u8 to MP4 using ffmpeg."""
    ffmpeg = ffmpeg_path or resolve_ffmpeg_path()
    if ffmpeg is None:
        raise ValueError("ffmpeg not found — place ffmpeg.exe next to the app or on PATH")

    dest.parent.mkdir(parents=True, exist_ok=True)
    download_url = append_access_token(url, access_token)
    auth = nd_auth_header(access_token)
    header_lines = [f"X-ND-AUTH: {auth}"] if auth else []
    header_lines.append("User-Agent: MindGraph-FileReader/1.0")
    headers_arg = "\r\n".join(header_lines) + "\r\n"

    command = [
        str(ffmpeg),
        "-y",
        "-headers",
        headers_arg,
        "-i",
        download_url,
        "-c",
        "copy",
        str(dest),
    ]
    _notify(progress, dest.name, 0.05)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("ffmpeg timed out while merging video") from exc
    except OSError as exc:
        raise ValueError(f"ffmpeg failed to start: {exc}") from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        tail = stderr[-500:] if len(stderr) > 500 else stderr
        raise ValueError(tail or "ffmpeg merge failed (DRM video may require a fresh login token)")
    _notify(progress, dest.name, 1.0)


def asset_output_path(folder: Path, asset: SmartEduAsset, lesson_title: str) -> Path:
    """Build output path for an asset."""
    stem = sanitize_filename(f"{lesson_title}_{asset.alias}")
    suffix = f".{asset.format}"
    return folder / f"{stem}{suffix}"


def download_asset(
    asset: SmartEduAsset,
    folder: Path,
    lesson_title: str,
    access_token: str,
    *,
    progress: Optional[ProgressCallback] = None,
    ffmpeg_path: Optional[Path] = None,
) -> Path:
    """Download one asset and return the local path."""
    dest = asset_output_path(folder, asset, lesson_title)
    if asset.format == "mp4":
        download_m3u8_to_mp4(
            asset.download_url,
            dest,
            access_token,
            ffmpeg_path=ffmpeg_path,
            progress=progress,
        )
    else:
        download_binary_file(asset.download_url, dest, access_token, progress=progress)
    return dest
