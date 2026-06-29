"""WeChat cache image key extraction and .dat decoding (v4).

Ported from https://github.com/ycccccccy/wx_key image_key_service.dart
and github.com/svcvit/chatlog pkg/util/dat2img.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from Crypto.Cipher import AES

from file_reader.wechat.scan_common import enum_readable_regions, read_process_memory

_V2_HEADER = bytes([0x07, 0x08, 0x56, 0x32, 0x08, 0x07])
_TEMPLATE_SUFFIX = "_t.dat"
_MAX_TEMPLATE_FILES = 16
_SCAN_CHUNK = 4 * 1024 * 1024
_SCAN_OVERLAP = 65
_AES_CIPHERTEXT_SLICE = slice(0x0F, 0x1F)
_JPEG_MAGIC = b"\xff\xd8\xff"


class WeChatImageKeyError(RuntimeError):
    """Raised when image XOR/AES keys cannot be extracted."""


@dataclass(frozen=True)
class ImageKeys:
    """XOR byte and 16-byte AES key for WeChat v4 image cache files."""

    xor_key: int
    aes_key: bytes


def _is_alnum(byte: int) -> bool:
    return (0x61 <= byte <= 0x7A) or (0x41 <= byte <= 0x5A) or (0x30 <= byte <= 0x39)


def _find_template_files(account_dir: Path) -> List[Path]:
    files: List[Path] = []
    for root, _dirs, names in os.walk(account_dir):
        for name in names:
            if name.endswith(_TEMPLATE_SUFFIX):
                files.append(Path(root) / name)
                if len(files) >= _MAX_TEMPLATE_FILES * 2:
                    break
        if len(files) >= _MAX_TEMPLATE_FILES * 2:
            break
    files.sort(key=lambda path: path.as_posix(), reverse=True)
    return files[:_MAX_TEMPLATE_FILES]


def _xor_key_from_templates(templates: List[Path]) -> Optional[int]:
    counts: dict[str, int] = {}
    for path in templates:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) < 2:
            continue
        last_two = data[-2:]
        key = f"{last_two[0]}_{last_two[1]}"
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None
    most_common = max(counts.items(), key=lambda item: item[1])[0]
    parts = most_common.split("_")
    if len(parts) != 2:
        return None
    first = int(parts[0])
    second = int(parts[1])
    xor_key = first ^ 0xFF
    if xor_key == (second ^ 0xD9):
        return xor_key
    return None


def _ciphertext_from_templates(templates: List[Path]) -> Optional[bytes]:
    for path in templates:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) < 0x1F:
            continue
        if data[:6] == _V2_HEADER:
            return data[_AES_CIPHERTEXT_SLICE]
    return None


def _verify_aes_key(ciphertext: bytes, key_material: bytes) -> bool:
    if len(key_material) < 16 or len(ciphertext) < 16:
        return False
    aes_key = key_material[:16]
    cipher = AES.new(aes_key, AES.MODE_ECB)
    decrypted = cipher.decrypt(ciphertext[:16])
    return decrypted.startswith(_JPEG_MAGIC)


def _weixin_pids() -> List[int]:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Weixin.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=8,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    pids: List[int] = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.strip('"').split('","')
        if len(parts) >= 2:
            try:
                pids.append(int(parts[1]))
            except ValueError:
                continue
    return pids


def _scan_chunk_for_aes(data: bytes, ciphertext: bytes) -> Optional[bytes]:
    limit = len(data) - 34
    for index in range(limit):
        if _is_alnum(data[index]):
            continue
        valid = True
        for offset in range(1, 33):
            if not _is_alnum(data[index + offset]):
                valid = False
                break
        if not valid:
            continue
        if index + 33 < len(data) and _is_alnum(data[index + 33]):
            continue
        key_bytes = data[index + 1 : index + 33]
        if _verify_aes_key(ciphertext, key_bytes):
            return key_bytes[:16]
    utf_limit = len(data) - 65
    for index in range(utf_limit):
        key_bytes = bytearray(32)
        ok = True
        for char_index in range(32):
            char_byte = data[index + char_index * 2]
            null_byte = data[index + char_index * 2 + 1]
            if null_byte != 0 or not _is_alnum(char_byte):
                ok = False
                break
            key_bytes[char_index] = char_byte
        if ok and _verify_aes_key(ciphertext, bytes(key_bytes)):
            return bytes(key_bytes[:16])
    return None


def _aes_key_from_memory(pid: int, ciphertext: bytes) -> Optional[bytes]:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
    if not handle:
        return None
    try:
        for base, region_size in enum_readable_regions(handle):
            offset = 0
            trailing: Optional[bytes] = None
            while offset < region_size:
                chunk_size = min(_SCAN_CHUNK, region_size - offset)
                chunk = read_process_memory(handle, base + offset, chunk_size)
                offset += chunk_size
                if not chunk:
                    trailing = None
                    continue
                if trailing:
                    data = trailing + chunk
                else:
                    data = chunk
                found = _scan_chunk_for_aes(data, ciphertext)
                if found is not None:
                    return found
                trailing = data[-_SCAN_OVERLAP:] if len(data) >= _SCAN_OVERLAP else data
    finally:
        kernel32.CloseHandle(handle)
    return None


def extract_image_keys(account_dir: Path) -> ImageKeys:
    """Extract XOR and AES keys for WeChat 4.x cached images under account_dir."""
    if sys.platform != "win32":
        raise WeChatImageKeyError("Image key extraction is supported on Windows only")
    templates = _find_template_files(account_dir)
    if not templates:
        raise WeChatImageKeyError("No image template files (*_t.dat) found under account folder")
    xor_key = _xor_key_from_templates(templates)
    if xor_key is None:
        raise WeChatImageKeyError("Could not derive XOR key from template files")
    ciphertext = _ciphertext_from_templates(templates)
    if ciphertext is None:
        raise WeChatImageKeyError("Could not read encrypted AES sample from template files")
    pids = _weixin_pids()
    if not pids:
        raise WeChatImageKeyError("Weixin.exe is not running — open WeChat and view a few images first")
    for pid in pids:
        aes_key = _aes_key_from_memory(pid, ciphertext)
        if aes_key is not None:
            return ImageKeys(xor_key=xor_key, aes_key=aes_key)
    raise WeChatImageKeyError(
        "Could not read image AES key from memory. Restart WeChat, open Moments images full-size "
        "2–3 times, then try again."
    )


def decode_v2_dat(data: bytes, keys: ImageKeys) -> bytes:
    """Decode a WeChat v4 V2 .dat cache file to raw image bytes."""
    if len(data) < 0x1F:
        raise ValueError("dat file too small")
    if data[:6] != _V2_HEADER:
        raise ValueError("unsupported dat header")
    body = bytearray(data[0x1F:])
    for index, byte in enumerate(body):
        body[index] = byte ^ keys.xor_key
    aes_len = (len(body) // 16) * 16
    if aes_len >= 16:
        cipher = AES.new(keys.aes_key, AES.MODE_ECB)
        body[:aes_len] = cipher.decrypt(bytes(body[:aes_len]))
    return bytes(body)


def decode_legacy_dat(data: bytes, xor_key: int) -> bytes:
    """Decode legacy v3-style XOR-only .dat files."""
    return bytes(byte ^ xor_key for byte in data)


def guess_image_path(account_dir: Path, md5_hint: str) -> Optional[Path]:
    """Best-effort lookup for a cached image file by MD5 fragment in path."""
    pattern = re.compile(re.escape(md5_hint), re.IGNORECASE)
    image_root = account_dir / "FileStorage" / "Image"
    if not image_root.is_dir():
        return None
    for root, _dirs, files in os.walk(image_root):
        for name in files:
            if name.endswith(".dat") and pattern.search(name):
                return Path(root) / name
    return None
