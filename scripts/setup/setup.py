#!/usr/bin/env python3
"""
MindGraph Complete Setup Script

This script handles the complete installation and setup of MindGraph, including:
- Privilege check (Linux: run with sudo so system packages and Playwright deps install)
- System packages: Tesseract OCR (required by pytesseract / Knowledge Space)
- Python dependency installation (FastAPI stack)
- Playwright Chromium and OS-level browser dependencies (--with-deps on Linux/macOS)
- Logging and data directories
- Comprehensive verification
- On Linux with sudo: Redis >= 8.6 and PostgreSQL >= 18.3 via official apt repos
  (docs/REDIS_SETUP.md, docs/POSTGRES_SETUP.md). When Redis is 8.6+ and
  /etc/redis/redis.conf exists, enables key-memory-histograms (startup-only Redis
  setting) and restarts the service. Prompts let you skip apt installs.
- Qdrant vector server (Knowledge Space): on Linux with sudo, downloads the official
  release from GitHub, installs systemd (docs/QDRANT_SETUP.md). Optional skip via prompt.

Requirements:
- Python 3.8+
- pip package manager
- Internet connection for package downloads
- Linux: sudo/root for full setup (or answer the prompt to continue without sudo)

Usage:
    sudo python3 scripts/setup/setup.py

Interactive prompts ask about optional skips on Linux. For CI or pipes, set
MINDGRAPH_NON_INTERACTIVE=1 (full install, no questions).

Author: MindGraph Development Team
Version: See VERSION file (centralized version management)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import argparse
import ctypes
import importlib
import importlib.metadata
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple

try:
    import pkg_resources
except ImportError:
    pkg_resources = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


def _stdin_is_tty() -> bool:
    """True if stdin is an interactive terminal."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _non_interactive_env() -> bool:
    """MINDGRAPH_NON_INTERACTIVE=1 skips prompts (CI / pipes)."""
    value = os.environ.get("MINDGRAPH_NON_INTERACTIVE", "").strip().lower()
    return value in ("1", "true", "yes")


def prompt_yes_no(message: str, default: bool = False) -> bool:
    """
    Ask a yes/no question. Empty input uses default.

    Args:
        message: Question text (no trailing punctuation required).
        default: Default when user presses Enter.

    Returns:
        True for yes, False for no.
    """
    tag = "Y/n" if default else "y/N"
    try:
        line = input(f"{message} [{tag}]: ").strip().lower()
    except EOFError:
        return default
    if not line:
        return default
    return line in ("y", "yes", "1", "true")


def resolve_setup_interactive_options() -> Tuple[bool, bool, bool]:
    """
    Ask which optional parts to skip (Linux). Non-interactive: all False.

    Returns:
        (allow_non_root, skip_redis_postgres, skip_qdrant)
    """
    if not _stdin_is_tty() or _non_interactive_env():
        print(
            "[INFO] Non-interactive mode (pipe or MINDGRAPH_NON_INTERACTIVE=1): "
            "full system setup; use sudo on Linux for apt installs."
        )
        return False, False, False

    allow_non_root = False
    skip_redis = False
    skip_qdrant = False

    if platform.system().lower() == "linux":
        print("\n--- Setup options (Linux) ---")
        if not is_elevated_privileges():
            allow_non_root = prompt_yes_no(
                "Continue without sudo? This skips apt installs (Tesseract, Playwright "
                "system deps, Redis, PostgreSQL, Qdrant server)",
                default=False,
            )
        else:
            skip_redis = prompt_yes_no(
                "Skip installing Redis and PostgreSQL via apt (you will use your own)?",
                default=False,
            )
            skip_qdrant = prompt_yes_no(
                "Skip installing the Qdrant vector server (you will use your own)?",
                default=False,
            )

    return allow_non_root, skip_redis, skip_qdrant


# Constants
CORE_DEPENDENCIES = {
    # Web framework (FastAPI)
    'fastapi': 'FastAPI',
    'uvicorn': 'Uvicorn',
    'starlette': 'starlette',
    'pydantic': 'pydantic',
    'pydantic_settings': 'pydantic-settings',
    'email_validator': 'email-validator',
    'jinja2': 'jinja2',

    # HTTP and networking (async)
    'aiohttp': 'aiohttp',
    'httpx': 'httpx',
    'requests': 'requests',
    'openai': 'openai',
    'multipart': 'python-multipart',
    'websockets': 'websockets',

    # AI and language processing
    'langchain': 'langchain',
    'langchain_community': 'langchain-community',
    'langchain_core': 'langchain-core',
    'langchain_openai': 'langchain-openai',
    'langgraph': 'langgraph',
    'langgraph_checkpoint': 'langgraph-checkpoint',
    'dashscope': 'dashscope',

    # Configuration and environment
    'yaml': 'PyYAML',
    'dotenv': 'python-dotenv',

    # Async and concurrency
    'nest_asyncio': 'nest-asyncio',
    'aiofiles': 'aiofiles',

    # Browser automation and image processing
    'playwright': 'playwright',
    'PIL': 'Pillow',

    # Database and authentication
    'sqlalchemy': 'SQLAlchemy',
    'alembic': 'alembic',
    'jose': 'python-jose',
    'bcrypt': 'bcrypt',  # passlib removed in v4.12.0, using bcrypt directly
    'captcha': 'captcha',
    'Crypto': 'pycryptodome',

    # System utilities
    'psutil': 'psutil',
    'watchfiles': 'watchfiles',

    # JSON serialization
    'orjson': 'orjson'
}

PROGRESS_BAR_LENGTH = 30
MAX_LINE_LENGTH = 100
SETUP_STEPS = 8

REQUIRED_LOG_FILES = [
    "uvicorn_access.log",
    "uvicorn_error.log",
    "app.log",
    "agent.log"
]

ESSENTIAL_FILES = [
    "VERSION",
    "main.py",
    "requirements.txt",
    "uvicorn_config.py"
]

ESSENTIAL_DIRECTORIES = [
    "logs",
    "data",
    "static",
    "templates",
    "routers",
    "models",
    "clients",
    "services",
    "config"
]

# Packages where check_dependencies_already_installed skips import test (legacy behavior)
_SKIP_IMPORT_CHECK_MODULES = frozenset({
    "PIL", "multipart", "yaml", "dotenv", "nest_asyncio", "Crypto", "jose",
    "pydantic_settings", "email_validator",
})

# Offline Chromium installation directory
BROWSERS_DIR = "browsers"
CHROMIUM_DIR = os.path.join(BROWSERS_DIR, "chromium")

# Project docs (relative to repo root) for Redis / PostgreSQL
DOC_REDIS = "docs/REDIS_SETUP.md"
DOC_POSTGRES = "docs/POSTGRES_SETUP.md"
DOC_QDRANT = "docs/QDRANT_SETUP.md"

# MindGraph requires recent Redis / PostgreSQL; setup targets latest apt packages
# that meet these minimums (see docs/REDIS_SETUP.md, docs/POSTGRES_SETUP.md).
MIN_REDIS_VERSION = (8, 6, 0)
MIN_POSTGRESQL_VERSION = (18, 3, 0)

# Qdrant server binary from GitHub Releases (see docs/QDRANT_SETUP.md)
QDRANT_GITHUB_VERSION = "1.15.5"
QDRANT_LOCAL_BIN = "/usr/local/bin/qdrant"
QDRANT_CONFIG_PATH = "/etc/qdrant/config.yaml"
QDRANT_SYSTEMD_PATH = "/etc/systemd/system/qdrant.service"
QDRANT_CONFIG_YAML = """storage:
  storage_path: "/var/lib/qdrant/storage"
  snapshots_path: "/var/lib/qdrant/snapshots"
service:
  host: "0.0.0.0"
  api_port: 6333
  grpc_port: 6334
log_level: INFO
"""
QDRANT_SYSTEMD_UNIT = """[Unit]
Description=Qdrant Vector Database
Documentation=https://qdrant.tech/documentation/
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/qdrant --config-path /etc/qdrant/config.yaml
Restart=always
RestartSec=5
User=root
WorkingDirectory=/var/lib/qdrant
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""


class SetupError(Exception):
    """Custom exception for setup failures"""


def resolve_project_root(start_dir: str) -> str:
    """
    Directory containing requirements.txt / VERSION (repo root).

    Works when this file lives under scripts/, scripts/setup/, etc.
    """
    current = os.path.abspath(start_dir)
    for _ in range(8):
        if os.path.isfile(os.path.join(current, "requirements.txt")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.abspath(start_dir)


def get_playwright_cli_prefix() -> str:
    """Shell-safe prefix: ``<python> -m playwright`` (quoted if needed)."""
    exe = sys.executable
    if " " in exe or platform.system().lower() == "windows":
        return f'"{exe}" -m playwright'
    return f"{exe} -m playwright"


def is_elevated_privileges() -> bool:
    """True if running as root (Unix) or Windows administrator."""
    if platform.system().lower() == "windows":
        try:
            win_dll = getattr(ctypes, "WinDLL")
            shell32 = win_dll("shell32")
            is_admin = getattr(shell32, "IsUserAnAdmin")
            return bool(is_admin())
        except (AttributeError, OSError, ImportError, TypeError):
            return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def print_infrastructure_docs_hint(project_root: str) -> None:
    """Point operators at Redis/PostgreSQL/Qdrant documentation."""
    print("\n[INFO] Redis, PostgreSQL, and Qdrant:")
    for rel, title in (
        (DOC_REDIS, "Redis"),
        (DOC_POSTGRES, "PostgreSQL"),
        (DOC_QDRANT, "Qdrant"),
    ):
        path = os.path.join(project_root, rel)
        if os.path.isfile(path):
            print(f"    - {title}: {rel}")
        else:
            print(f"    - {title}: ({rel} not found in tree; see README.md)")


def ensure_linux_elevation_or_allow(
    allow_non_root: bool,
) -> None:
    """
    On Linux, full setup expects root/sudo so apt can install Tesseract and
    Playwright system dependencies. The interactive prompt can allow non-root.
    """
    if platform.system().lower() != "linux":
        return
    if is_elevated_privileges():
        print("[SUCCESS] Running with elevated privileges (sudo/root) — OK for system packages")
        return
    if allow_non_root:
        print(
            "[WARNING] Linux: not running as root. "
            "Skipping apt-based installs (Tesseract, Playwright --with-deps). "
            "Run: sudo python3 scripts/setup/setup.py"
        )
        return
    print("\n[ERROR] On Linux this script must be run with sudo for system packages.")
    print("    Example: sudo python3 scripts/setup/setup.py")
    print("    Or run again and answer yes when asked to continue without sudo.")
    raise SetupError("Re-run with sudo, or re-run and choose continue without sudo")


def _tesseract_print_if_already_installed() -> bool:
    """If tesseract is on PATH, print version and return True."""
    if not shutil.which("tesseract"):
        return False
    try:
        ver = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        first = (ver.stdout or ver.stderr or "").splitlines()
        line0 = first[0] if first else "present"
        print(f"[SUCCESS] Tesseract already available: {line0.strip()}")
        return True
    except (subprocess.SubprocessError, OSError):
        print("[INFO] tesseract in PATH but version check failed; continuing")
        return False


def _install_tesseract_linux_apt() -> bool:
    """Install Tesseract via apt on Debian/Ubuntu."""
    if not is_elevated_privileges():
        print(
            "[WARNING] Cannot install Tesseract via apt without sudo. "
            "Install: sudo apt-get install -y tesseract-ocr tesseract-ocr-chi-sim"
        )
        return False
    if not shutil.which("apt-get"):
        print("[WARNING] apt-get not found")
        return False
    run_command_with_progress(
        "apt-get update -qq",
        "apt-get update (for Tesseract)",
        check=False,
    )
    ok = run_command_with_progress(
        "DEBIAN_FRONTEND=noninteractive apt-get install -y "
        "tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim",
        "Installing Tesseract OCR packages",
        check=False,
    )
    if ok and shutil.which("tesseract"):
        print("[SUCCESS] Tesseract OCR installed via apt")
        return True
    print("[WARNING] apt-get install for Tesseract failed or unavailable")
    return False


def _install_tesseract_macos_brew() -> bool:
    """Install Tesseract via Homebrew on macOS."""
    if not shutil.which("brew"):
        print(
            "[WARNING] Install Tesseract manually: "
            "brew install tesseract tesseract-lang"
        )
        return False
    if run_command_with_progress(
        "brew install tesseract tesseract-lang",
        "Installing Tesseract via Homebrew",
        check=False,
    ) and shutil.which("tesseract"):
        print("[SUCCESS] Tesseract OCR installed via brew")
        return True
    print(
        "[WARNING] Install Tesseract manually: brew install tesseract tesseract-lang"
    )
    return False


def _install_tesseract_windows() -> bool:
    """Best-effort Tesseract on Windows (winget or manual)."""
    print(
        "[INFO] Windows: install Tesseract from "
        "https://github.com/UB-Mannheim/tesseract/wiki "
        "or: winget install UB-Mannheim.TesseractOCR"
    )
    if shutil.which("winget"):
        run_command_with_progress(
            "winget install --id UB-Mannheim.TesseractOCR -e "
            "--accept-package-agreements --accept-source-agreements",
            "Installing Tesseract via winget (if available)",
            check=False,
        )
    if shutil.which("tesseract"):
        print("[SUCCESS] Tesseract OCR is available in PATH")
        return True
    print("[WARNING] Tesseract not in PATH after setup; add install dir to PATH")
    return False


def install_tesseract_ocr_system() -> bool:
    """
    Install Tesseract OCR binary where supported (best-effort).

    Returns:
        True if installed or already present, False if skipped/failed non-fatally
    """
    print("\n[INFO] Tesseract OCR (system binary for pytesseract)...")

    if _tesseract_print_if_already_installed():
        return True

    system = platform.system().lower()
    if system == "linux":
        return _install_tesseract_linux_apt()

    if system == "darwin":
        return _install_tesseract_macos_brew()

    if system == "windows":
        return _install_tesseract_windows()

    print("[WARNING] Unsupported OS for automatic Tesseract install")
    return False


def verify_tesseract_ocr() -> None:
    """Warn if Tesseract binary is missing (pytesseract needs it)."""
    if shutil.which("tesseract"):
        print("    [SUCCESS] tesseract binary found in PATH")
        return
    print("    [WARNING] tesseract binary not in PATH — OCR features may fail")
    print("    [INFO] See requirements.txt notes and docs in repository README")


def redis_server_responding() -> bool:
    """True if redis-cli ping returns PONG."""
    if not shutil.which("redis-cli"):
        return False
    try:
        result = subprocess.run(
            ["redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        out = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0 and "PONG" in out.upper()
    except (OSError, subprocess.SubprocessError):
        return False


def postgresql_client_available() -> bool:
    """True if psql is installed."""
    return shutil.which("psql") is not None


def get_redis_server_version() -> Optional[Tuple[int, int, int]]:
    """Parse redis_version from INFO server (authoritative for running server)."""
    if not shutil.which("redis-cli") or not redis_server_responding():
        return None
    try:
        result = subprocess.run(
            ["redis-cli", "INFO", "server"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        match = re.search(r"redis_version:(\d+)\.(\d+)\.(\d+)", result.stdout or "")
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def get_redis_cli_version() -> Optional[Tuple[int, int, int]]:
    """Parse redis-cli --version when server INFO is unavailable."""
    if not shutil.which("redis-cli"):
        return None
    try:
        result = subprocess.run(
            ["redis-cli", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", result.stdout or "")
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def redis_version_reported() -> Optional[Tuple[int, int, int]]:
    """Best-effort Redis version tuple for requirement checks."""
    ver = get_redis_server_version()
    if ver is not None:
        return ver
    return get_redis_cli_version()


def redis_meets_mindgraph_minimum() -> bool:
    """True if Redis is at least MIN_REDIS_VERSION (8.6.x)."""
    ver = redis_version_reported()
    if ver is None:
        return False
    return ver >= MIN_REDIS_VERSION


_REDIS_CONF_CANDIDATE_PATHS = (
    "/etc/redis/redis.conf",
    "/etc/redis.conf",
)


def _find_redis_conf_path_linux() -> Optional[str]:
    """Return first existing redis.conf path for typical Debian/Ubuntu Redis.io packages."""
    for path in _REDIS_CONF_CANDIDATE_PATHS:
        if Path(path).is_file():
            return path
    return None


def _apply_key_memory_histograms_to_conf_text(content: str) -> Tuple[str, bool]:
    """
    Ensure key-memory-histograms yes in redis.conf text.

    Returns:
        (new_content, changed) — changed is False if already enabled.
    """
    pattern = re.compile(
        r"^\s*#?\s*key-memory-histograms\s+(yes|no)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    if pattern.search(content):
        new_content, _ = pattern.subn("key-memory-histograms yes", content)
        return new_content, new_content != content
    trailing = "" if content.endswith("\n") else "\n"
    addition = (
        f"{trailing}"
        "# MindGraph: INFO keysizes memory histograms (Redis 8.6+)\n"
        "key-memory-histograms yes\n"
    )
    return content + addition, True


def ensure_redis_key_memory_histograms_linux() -> None:
    """
    Enable key-memory-histograms in redis.conf (must be set at startup; Redis 8.6+).

    No-op when not Linux, not root, Redis unavailable, or version < 8.6.
    """
    if platform.system() != "Linux":
        return
    try:
        if os.geteuid() != 0:
            return
    except AttributeError:
        return
    if not redis_server_responding() or not redis_meets_mindgraph_minimum():
        return
    conf_path = _find_redis_conf_path_linux()
    if not conf_path:
        print(
            "[INFO] key-memory-histograms: redis.conf not found; "
            "set manually in Redis config (Redis 8.6+)",
        )
        return
    try:
        current = Path(conf_path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"[WARNING] key-memory-histograms: could not read {conf_path}: {exc}")
        return
    new_text, changed = _apply_key_memory_histograms_to_conf_text(current)
    if not changed:
        return
    try:
        Path(conf_path).write_text(new_text, encoding="utf-8")
    except OSError as exc:
        print(f"[WARNING] key-memory-histograms: could not write {conf_path}: {exc}")
        return
    print(f"[INFO] key-memory-histograms: updated {conf_path}; restarting Redis...")
    for svc in ("redis-server", "redis"):
        run_command(
            f"systemctl restart {svc} 2>/dev/null",
            f"Restart {svc} after redis.conf update",
            check=False,
        )
    time.sleep(1.0)
    if redis_server_responding():
        print("[SUCCESS] key-memory-histograms: Redis restarted and responds to PING")
    else:
        print(
            "[WARNING] key-memory-histograms: Redis did not respond after restart; "
            "check systemd logs",
        )


def get_postgresql_version() -> Optional[Tuple[int, int, int]]:
    """Parse psql --version (e.g. PostgreSQL 18.3)."""
    if not shutil.which("psql"):
        return None
    try:
        result = subprocess.run(
            ["psql", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        line = result.stdout or ""
        match = re.search(
            r"PostgreSQL\)\s+(\d+)\.(\d+)(?:\.(\d+))?",
            line,
        )
        if match:
            patch = int(match.group(3)) if match.group(3) else 0
            return (int(match.group(1)), int(match.group(2)), patch)
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def postgresql_meets_mindgraph_minimum() -> bool:
    """True if PostgreSQL is at least MIN_POSTGRESQL_VERSION (18.3+)."""
    ver = get_postgresql_version()
    if ver is None:
        return False
    return ver >= MIN_POSTGRESQL_VERSION


def _add_redis_io_apt_repository() -> bool:
    """
    Add official Redis apt source (docs/REDIS_SETUP.md: GPG key + redis.list).

    Same commands as the doc: curl gpg pipe to keyring, chmod 644, deb line to
    /etc/apt/sources.list.d/redis.list. Runs as root (sudo), so no sudo prefix.
    """
    repo_cmd = (
        "curl -fsSL https://packages.redis.io/gpg | "
        "gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg && "
        "chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg && "
        'echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] '
        'https://packages.redis.io/deb $(lsb_release -cs) main" | '
        "tee /etc/apt/sources.list.d/redis.list"
    )
    return run_command_with_progress(
        repo_cmd,
        "Adding Redis official apt repository (packages.redis.io)",
        check=False,
    )


def install_redis_linux_official_apt() -> bool:
    """
    Install or upgrade Redis from packages.redis.io to the latest >= 8.6.x.

    See docs/REDIS_SETUP.md. Does not install legacy distro redis-server < 8.6.
    """
    if not shutil.which("apt-get"):
        print("[WARNING] apt-get not found; install Redis manually (docs/REDIS_SETUP.md)")
        return False

    if redis_server_responding() and redis_meets_mindgraph_minimum():
        ver = redis_version_reported()
        if ver:
            print(
                f"[SUCCESS] Redis {ver[0]}.{ver[1]}.{ver[2]} meets minimum "
                f"{MIN_REDIS_VERSION[0]}.{MIN_REDIS_VERSION[1]}.{MIN_REDIS_VERSION[2]}"
            )
        else:
            print("[SUCCESS] Redis meets minimum version requirement")
        ensure_redis_key_memory_histograms_linux()
        return True

    if redis_server_responding():
        ver = redis_version_reported()
        print(
            f"[INFO] Redis {ver} is below required "
            f"{MIN_REDIS_VERSION[0]}.{MIN_REDIS_VERSION[1]}.{MIN_REDIS_VERSION[2]}; "
            "upgrading from redis.io packages..."
        )

    print("[INFO] Installing Redis via official Redis apt repository (latest 8.x)...")
    run_command_with_progress(
        "DEBIAN_FRONTEND=noninteractive apt-get install -y "
        "lsb-release curl gpg",
        "Installing prerequisites (lsb-release, curl, gpg) for Redis repo",
        check=False,
    )
    if not _add_redis_io_apt_repository():
        print(
            "[ERROR] Could not add Redis.io apt repository. "
            "MindGraph requires Redis 8.6+; see docs/REDIS_SETUP.md"
        )
        return False

    run_command_with_progress(
        "DEBIAN_FRONTEND=noninteractive apt-get update -qq",
        "apt-get update after Redis repo",
        check=False,
    )
    run_command_with_progress(
        "DEBIAN_FRONTEND=noninteractive apt-get install -y redis",
        "Installing latest Redis package from redis.io",
        check=False,
    )
    run_command_with_progress(
        "DEBIAN_FRONTEND=noninteractive apt-get install --only-upgrade -y redis",
        "Upgrading Redis to newest patch in repo",
        check=False,
    )
    for svc in ("redis-server", "redis"):
        run_command(
            f"systemctl enable {svc} 2>/dev/null; systemctl start {svc} 2>/dev/null",
            f"Enable/start {svc}",
            check=False,
        )
    if redis_server_responding() and redis_meets_mindgraph_minimum():
        ver = redis_version_reported()
        if ver:
            print(
                f"[SUCCESS] Redis {ver[0]}.{ver[1]}.{ver[2]} installed and meets minimum "
                f"{MIN_REDIS_VERSION[0]}.{MIN_REDIS_VERSION[1]}.{MIN_REDIS_VERSION[2]}"
            )
        else:
            print("[SUCCESS] Redis installed and meets minimum version requirement")
        ensure_redis_key_memory_histograms_linux()
        return True
    if redis_server_responding():
        ver = redis_version_reported()
        print(
            f"[WARNING] Redis version {ver} still below "
            f"{MIN_REDIS_VERSION[0]}.{MIN_REDIS_VERSION[1]}.{MIN_REDIS_VERSION[2]}; "
            "run: sudo apt-get update && sudo apt-get install --only-upgrade -y redis"
        )
        return False
    print("[WARNING] Redis install did not respond to ping; see docs/REDIS_SETUP.md")
    return False


def install_postgresql_linux_pgdg() -> bool:
    """
    Install PostgreSQL 18 from PGDG (latest 18.x in repo, >= 18.3 when available).

    See docs/POSTGRES_SETUP.md. Does not fall back to generic postgresql < 18.
    """
    if not shutil.which("apt-get"):
        print("[WARNING] apt-get not found; install PostgreSQL manually (docs/POSTGRES_SETUP.md)")
        return False

    if postgresql_client_available() and postgresql_meets_mindgraph_minimum():
        ver = get_postgresql_version()
        if ver:
            print(
                f"[SUCCESS] PostgreSQL {ver[0]}.{ver[1]}.{ver[2]} meets minimum "
                f"{MIN_POSTGRESQL_VERSION[0]}.{MIN_POSTGRESQL_VERSION[1]}."
                f"{MIN_POSTGRESQL_VERSION[2]}"
            )
        else:
            print("[SUCCESS] PostgreSQL meets minimum version requirement")
        run_command(
            "systemctl enable postgresql 2>/dev/null; "
            "systemctl start postgresql 2>/dev/null",
            "Ensure PostgreSQL service is running",
            check=False,
        )
        return True

    if postgresql_client_available():
        ver = get_postgresql_version()
        print(
            f"[INFO] PostgreSQL {ver} is below required "
            f"{MIN_POSTGRESQL_VERSION[0]}.{MIN_POSTGRESQL_VERSION[1]}.{MIN_POSTGRESQL_VERSION[2]}; "
            "installing from PGDG..."
        )

    print("[INFO] Installing PostgreSQL 18 from PGDG (latest 18.x in repo)...")
    run_command_with_progress(
        "DEBIAN_FRONTEND=noninteractive apt-get install -y "
        "lsb-release curl ca-certificates",
        "Installing prerequisites for PostgreSQL PGDG repo",
        check=False,
    )
    # docs/POSTGRES_SETUP.md: pgdg dir, ACCC4CF8.asc key, pgdg.list repository
    run_command(
        "install -d /usr/share/postgresql-common/pgdg",
        "Creating PGDG key directory (docs/POSTGRES_SETUP.md)",
        check=False,
    )
    key_cmd = (
        "curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc "
        "--fail https://www.postgresql.org/media/keys/ACCC4CF8.asc"
    )
    if not run_command_with_progress(
        key_cmd,
        "Downloading PostgreSQL PGDG GPG key (apt.postgresql.org.asc)",
        check=False,
    ):
        print(
            "[ERROR] Could not download PGDG key. "
            "MindGraph requires PostgreSQL 18.3+; see docs/POSTGRES_SETUP.md"
        )
        return False

    pgdg_line = (
        'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] '
        'https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | '
        "tee /etc/apt/sources.list.d/pgdg.list"
    )
    run_command_with_progress(
        pgdg_line,
        "Adding PostgreSQL PGDG apt repository (/etc/apt/sources.list.d/pgdg.list)",
        check=False,
    )
    run_command_with_progress(
        "DEBIAN_FRONTEND=noninteractive apt-get update -qq",
        "apt-get update after PGDG",
        check=False,
    )
    run_command_with_progress(
        "DEBIAN_FRONTEND=noninteractive apt-get install -y "
        "postgresql-18 postgresql-client-18",
        "Installing latest PostgreSQL 18 from PGDG",
        check=False,
    )
    run_command_with_progress(
        "DEBIAN_FRONTEND=noninteractive apt-get install --only-upgrade -y "
        "postgresql-18 postgresql-client-18",
        "Upgrading PostgreSQL 18 to newest patch in repo",
        check=False,
    )
    run_command(
        "systemctl enable postgresql 2>/dev/null; systemctl start postgresql 2>/dev/null",
        "Enable/start PostgreSQL",
        check=False,
    )
    if postgresql_client_available() and postgresql_meets_mindgraph_minimum():
        ver = get_postgresql_version()
        if ver:
            print(
                f"[SUCCESS] PostgreSQL {ver[0]}.{ver[1]}.{ver[2]} meets minimum "
                f"{MIN_POSTGRESQL_VERSION[0]}.{MIN_POSTGRESQL_VERSION[1]}."
                f"{MIN_POSTGRESQL_VERSION[2]}"
            )
        else:
            print("[SUCCESS] PostgreSQL meets minimum version requirement")
        print("[INFO] Create DB/user per docs/POSTGRES_SETUP.md, then set DATABASE_URL in .env")
        return True
    ver = get_postgresql_version()
    print(
        f"[WARNING] PostgreSQL version {ver} still below "
        f"{MIN_POSTGRESQL_VERSION[0]}.{MIN_POSTGRESQL_VERSION[1]}.{MIN_POSTGRESQL_VERSION[2]}; "
        "run: sudo apt-get update && sudo apt-get install --only-upgrade -y "
        "postgresql-18 postgresql-client-18"
    )
    return False


def install_redis_and_postgresql_linux(skip: bool) -> Tuple[bool, bool]:
    """
    Install Redis and PostgreSQL on Debian/Ubuntu when root.

    Returns:
        (redis_ok, postgres_ok) best-effort status flags
    """
    if skip:
        print("\n[INFO] Skipping Redis/PostgreSQL apt install (you chose to skip)")
        return redis_server_responding(), postgresql_client_available()
    if platform.system().lower() != "linux":
        print("\n[INFO] Redis/PostgreSQL: install manually on this OS (see docs/)")
        return redis_server_responding(), postgresql_client_available()
    if not is_elevated_privileges():
        print(
            "\n[INFO] Redis/PostgreSQL apt install requires sudo; "
            "skipping (use sudo or docs/REDIS_SETUP.md, docs/POSTGRES_SETUP.md)"
        )
        return redis_server_responding(), postgresql_client_available()
    print("\n[INFO] Linux + root: installing Redis and PostgreSQL (apt)...")
    redis_ok = install_redis_linux_official_apt()
    pg_ok = install_postgresql_linux_pgdg()
    return redis_ok, pg_ok


def verify_redis_postgres_hints() -> None:
    """Print quick status for Redis and PostgreSQL (MindGraph minimum versions)."""
    min_r = f"{MIN_REDIS_VERSION[0]}.{MIN_REDIS_VERSION[1]}.{MIN_REDIS_VERSION[2]}"
    min_p = (
        f"{MIN_POSTGRESQL_VERSION[0]}.{MIN_POSTGRESQL_VERSION[1]}."
        f"{MIN_POSTGRESQL_VERSION[2]}"
    )
    if redis_server_responding():
        if redis_meets_mindgraph_minimum():
            ver = redis_version_reported()
            if ver:
                print(
                    f"    [SUCCESS] Redis {ver[0]}.{ver[1]}.{ver[2]} "
                    f"(MindGraph requires >= {min_r})"
                )
            else:
                print("    [SUCCESS] Redis: redis-cli ping -> PONG")
        else:
            ver = redis_version_reported()
            vtxt = f"{ver[0]}.{ver[1]}.{ver[2]}" if ver else "unknown"
            print(
                f"    [WARNING] Redis {vtxt} is below required {min_r}; upgrade via apt "
                "(docs/REDIS_SETUP.md)"
            )
    else:
        print(
            f"    [WARNING] Redis: not responding; install Redis >= {min_r} "
            "(docs/REDIS_SETUP.md)"
        )
    if postgresql_client_available():
        if postgresql_meets_mindgraph_minimum():
            ver = get_postgresql_version()
            if ver:
                print(
                    f"    [SUCCESS] PostgreSQL {ver[0]}.{ver[1]}.{ver[2]} "
                    f"(MindGraph requires >= {min_p})"
                )
            else:
                print("    [SUCCESS] PostgreSQL: psql client found")
        else:
            ver = get_postgresql_version()
            vtxt = f"{ver[0]}.{ver[1]}.{ver[2]}" if ver else "unknown"
            print(
                f"    [WARNING] PostgreSQL {vtxt} is below required {min_p}; "
                "upgrade via PGDG (docs/POSTGRES_SETUP.md)"
            )
    else:
        print(
            f"    [WARNING] PostgreSQL: psql not in PATH; install {min_p}+ if using DATABASE_URL"
        )


def qdrant_api_responding() -> bool:
    """True if Qdrant HTTP API answers on port 6333 (docs/QDRANT_SETUP.md)."""
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:6333/collections",
            timeout=3,
        ) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


def _qdrant_linux_arch_suffix() -> Optional[str]:
    """Prebuilt tarball suffix for Qdrant GitHub Releases (arch -> filename)."""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64-unknown-linux-gnu"
    if machine in ("aarch64", "arm64"):
        return "aarch64-unknown-linux-gnu"
    return None


def _qdrant_find_binary() -> Optional[str]:
    """Return path to an executable qdrant binary if found."""
    for path in (
        QDRANT_LOCAL_BIN,
        "/usr/bin/qdrant",
        os.path.expanduser("~/qdrant/qdrant"),
    ):
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def _qdrant_client_importable() -> bool:
    try:
        importlib.import_module("qdrant_client")
        return True
    except ImportError:
        return False


def _ensure_qdrant_client_pip() -> bool:
    """Ensure qdrant-client is installed (requirements.txt should already have done this)."""
    if _qdrant_client_importable():
        return True
    print("[INFO] Installing qdrant-client via pip...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "qdrant-client"],
        check=False,
    )
    return result.returncode == 0 and _qdrant_client_importable()


def _qdrant_download_to_file(url: str, dest: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            with open(dest, "wb") as outfile:
                shutil.copyfileobj(response, outfile)
        return True
    except OSError:
        return False


def install_qdrant_linux_server() -> bool:
    """
    Install Qdrant from GitHub Releases + systemd (Ubuntu/Linux production).

    Single entry point with MindGraph setup (no separate install_qdrant scripts).
    """
    print("\n============================================================")
    print("  Qdrant vector database (GitHub release + systemd)")
    print("============================================================\n")

    if qdrant_api_responding():
        print("[INFO] Qdrant API already responding on port 6333")
        return _ensure_qdrant_client_pip()

    binary_path = _qdrant_find_binary()
    binary_exists = binary_path is not None
    systemd_unit = os.path.isfile(QDRANT_SYSTEMD_PATH)
    needs_setup = False

    if binary_exists and systemd_unit:
        run_command("systemctl start qdrant", "Starting Qdrant service", check=False)
        time.sleep(3)
        if qdrant_api_responding():
            return _ensure_qdrant_client_pip()
        needs_setup = True
        print("[WARNING] Qdrant systemd unit present but API not responding; reconfiguring...")
    elif binary_exists and not systemd_unit:
        needs_setup = True
        print("[INFO] Qdrant binary found without systemd unit; configuring service...")

    if not binary_exists:
        arch = _qdrant_linux_arch_suffix()
        if arch is None:
            print(
                "[ERROR] Unsupported CPU for Qdrant prebuilt binary; "
                "see https://github.com/qdrant/qdrant/releases"
            )
            return False
        url = (
            f"https://github.com/qdrant/qdrant/releases/download/"
            f"v{QDRANT_GITHUB_VERSION}/qdrant-{arch}.tar.gz"
        )
        print(
            f"[INFO] Downloading Qdrant v{QDRANT_GITHUB_VERSION} from GitHub "
            f"({arch})..."
        )
        tmp_dir = tempfile.mkdtemp(prefix="mg_qdrant_")
        tar_path = os.path.join(tmp_dir, "qdrant.tgz")
        if not _qdrant_download_to_file(url, tar_path):
            print("[ERROR] Failed to download Qdrant tarball")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False
        try:
            with tarfile.open(tar_path, "r:gz") as archive:
                if sys.version_info >= (3, 12):
                    archive.extractall(tmp_dir, filter="data")
                else:
                    archive.extractall(tmp_dir)
        except (OSError, tarfile.TarError) as err:
            print(f"[ERROR] Failed to extract Qdrant: {err}")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False
        inner_bin = os.path.join(tmp_dir, "qdrant")
        if not os.path.isfile(inner_bin):
            print("[ERROR] qdrant binary missing inside release archive")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False
        shutil.move(inner_bin, QDRANT_LOCAL_BIN)
        os.chmod(QDRANT_LOCAL_BIN, 0o755)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"[SUCCESS] Installed Qdrant binary -> {QDRANT_LOCAL_BIN}")

    if not binary_exists or needs_setup:
        os.makedirs("/var/lib/qdrant/storage", mode=0o755, exist_ok=True)
        os.makedirs("/var/lib/qdrant/snapshots", mode=0o755, exist_ok=True)
        os.makedirs("/etc/qdrant", mode=0o755, exist_ok=True)
        with open(QDRANT_CONFIG_PATH, "w", encoding="utf-8") as cfg:
            cfg.write(QDRANT_CONFIG_YAML)
        with open(QDRANT_SYSTEMD_PATH, "w", encoding="utf-8") as unit:
            unit.write(QDRANT_SYSTEMD_UNIT)
        run_command("systemctl daemon-reload", "systemctl daemon-reload", check=False)
        run_command("systemctl enable qdrant", "systemctl enable qdrant", check=False)
        run_command("systemctl start qdrant", "systemctl start qdrant", check=False)

    print("[INFO] Waiting for Qdrant to listen on 6333...")
    time.sleep(5)

    if not _ensure_qdrant_client_pip():
        print("[ERROR] Could not install qdrant-client; check pip / requirements.txt")
        return False

    if qdrant_api_responding():
        print("[SUCCESS] Qdrant is running — API http://127.0.0.1:6333  gRPC 127.0.0.1:6334")
        print("[INFO] sudo systemctl status qdrant  |  sudo journalctl -u qdrant -f")
        return True

    print(
        "[WARNING] Qdrant did not respond; check: sudo journalctl -u qdrant -n 50 "
        "(docs/QDRANT_SETUP.md)"
    )
    return False


def install_qdrant_via_documented_flow(
    project_root: str,
    skip: bool,
    allow_non_root: bool,
) -> bool:
    """
    Install Qdrant server per docs/QDRANT_SETUP.md (GitHub binary + systemd, Ubuntu).

    project_root is unused (kept for API compatibility with main()).
    """
    del project_root
    if skip:
        print("\n[INFO] Skipping Qdrant server install (you chose to skip)")
        return qdrant_api_responding()

    if platform.system().lower() != "linux":
        print(
            "\n[INFO] Qdrant server auto-install targets Linux (systemd). "
            "On other OSes use Docker, WSL, or follow docs/QDRANT_SETUP.md manually."
        )
        return qdrant_api_responding()

    if allow_non_root or not is_elevated_privileges():
        print(
            "\n[INFO] Qdrant server install needs root (systemd, /usr/local/bin). "
            "Skipping. Run: sudo python3 scripts/setup/setup.py "
            "(see docs/QDRANT_SETUP.md)"
        )
        return qdrant_api_responding()

    if qdrant_api_responding():
        print("\n[INFO] Qdrant server already responding on http://127.0.0.1:6333")
        return True

    ok = install_qdrant_linux_server()
    if ok:
        print("[INFO] Set QDRANT_HOST=localhost:6333 in .env for Knowledge Space (see env.example)")
    return ok


def verify_qdrant_hint() -> None:
    """Print Qdrant server and Python client status (Knowledge Space)."""
    if qdrant_api_responding():
        print(
            "    [SUCCESS] Qdrant API http://127.0.0.1:6333/collections "
            "(docs/QDRANT_SETUP.md)"
        )
    else:
        print(
            "    [WARNING] Qdrant not listening on port 6333; "
            "configure QDRANT_HOST or run install (docs/QDRANT_SETUP.md)"
        )
    try:
        importlib.import_module("qdrant_client")
        print("    [SUCCESS] Python package qdrant-client is importable")
    except ImportError:
        print(
            "    [WARNING] qdrant-client not importable; "
            "ensure Step 4 (pip install -r requirements.txt) completed"
        )


def run_command(command: str, description: str, check: bool = True) -> bool:
    """
    Execute a shell command with proper error handling.

    Args:
        command: The shell command to execute
        description: Human-readable description of what the command does
        check: Whether to raise an exception on non-zero return code

    Returns:
        True if command succeeded, False otherwise

    Raises:
        SetupError: If check=True and command fails
    """
    print(f"[INFO] {description}...")

    try:
        result = subprocess.run(
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"[SUCCESS] {description} completed")
            return True
        else:
            print(f"[WARNING] {description} completed with warnings")
            if result.stderr:
                print(f"    Warning: {result.stderr.strip()}")
            return True

    except subprocess.SubprocessError as e:
        print(f"[ERROR] {description} failed: {e}")
        if check:
            raise SetupError(f"Command failed: {description}") from e
        return False


def run_command_with_progress(command: str, description: str, check: bool = True) -> bool:
    """
    Execute a shell command with real-time progress tracking and download speed.

    Args:
        command: The shell command to execute
        description: Human-readable description of what the command does
        check: Whether to raise an exception on non-zero return code

    Returns:
        True if command succeeded, False otherwise

    Raises:
        SetupError: If check=True and command fails
    """
    print(f"[INFO] {description}...")

    try:
        # Start the process with real-time output
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Track progress and download speed
        start_time = time.time()
        total_bytes = 0

        print("    [INFO] Downloading and installing packages...")

        proc_stdout = process.stdout
        while True:
            if proc_stdout is None:
                break
            output = proc_stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                line = output.strip()

                # Parse pip progress output
                if "Downloading" in line and "%" in line:
                    # Extract percentage and speed info
                    print(f"\r    [INFO] {line}", end='', flush=True)
                elif "Installing collected packages" in line:
                    print(f"\n    [INFO] {line}")
                elif "Successfully installed" in line:
                    print(f"    [SUCCESS] {line}")
                elif "Requirement already satisfied" in line:
                    print(f"    [INFO] {line}")
                elif "Collecting" in line:
                    package_name = line.split("Collecting ")[-1].split()[0]
                    print(f"    [INFO] Collecting {package_name}...")
                elif "Downloading" in line and "MB" in line:
                    # Extract download size and speed
                    if "MB" in line:
                        size_match = line.split("MB")[0].split()[-1]
                        try:
                            size_mb = float(size_match)
                            total_bytes += size_mb * 1024 * 1024
                        except ValueError:
                            pass
                    print(f"\r    [INFO] {line}", end='', flush=True)
                elif "Installing" in line and "..." in line:
                    print(f"\n    [INFO] {line}")
                elif "Successfully" in line:
                    print(f"    [SUCCESS] {line}")
                elif "ERROR:" in line or "FAILED" in line:
                    print(f"\n    [ERROR] {line}")
                elif line and not line.startswith("WARNING:"):
                    # Show other relevant output
                    if len(line) < MAX_LINE_LENGTH:  # Avoid very long lines
                        print(f"    [INFO] {line}")

        # Wait for process to complete
        return_code = process.poll()

        if return_code == 0:
            elapsed_time = time.time() - start_time
            if total_bytes > 0:
                avg_speed = total_bytes / elapsed_time / (1024 * 1024)  # MB/s
                print(f"\n    [SUCCESS] {description} completed in {elapsed_time:.1f}s (avg: {avg_speed:.1f} MB/s)")
            else:
                print(f"\n    [SUCCESS] {description} completed in {elapsed_time:.1f}s")
            return True
        else:
            print(f"\n    [ERROR] {description} failed with return code {return_code}")
            if check:
                raise SetupError(f"Command failed: {description}")
            return False

    except subprocess.SubprocessError as e:
        print(f"\n[ERROR] {description} failed: {e}")
        if check:
            raise SetupError(f"Command failed: {description}") from e
        return False


def check_python_version() -> bool:
    """
    Verify Python version compatibility.

    Returns:
        True if Python version is compatible

    Raises:
        SetupError: If Python version is incompatible
    """
    print("[INFO] Checking Python version...")

    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        raise SetupError(
            f"Python {version.major}.{version.minor} detected. "
            "MindGraph requires Python 3.8+"
        )

    print(f"[SUCCESS] Python {version.major}.{version.minor}.{version.micro} - Compatible")
    return True


def print_system_info() -> None:
    """Print system information for diagnostics"""
    print("[INFO] System Information:")
    print(f"    Platform: {platform.system()} {platform.release()}")
    print(f"    Architecture: {platform.machine()}")
    print(f"    Python: {sys.version}")
    print(f"    Python Executable: {sys.executable}")
    print(f"    Working Directory: {os.getcwd()}")
    print(f"    Available Memory: {get_available_memory():.1f} GB")
    print()


def get_available_memory() -> float:
    """Get available system memory in GB"""
    if psutil is None:
        return 0.0
    try:
        memory = psutil.virtual_memory()
        return memory.available / (1024**3)  # Convert to GB
    except Exception:
        return 0.0


def get_package_version(package_name: str) -> str:
    """
    Get package version using modern importlib.metadata approach.

    Args:
        package_name: The package name to get version for

    Returns:
        Package version string or 'unknown' if not available
    """
    try:
        return importlib.metadata.version(package_name)
    except Exception:
        if pkg_resources is None:
            return 'unknown'
        try:
            return pkg_resources.get_distribution(package_name).version
        except Exception:
            return 'unknown'


def check_pip() -> bool:
    """
    Verify pip package manager availability.

    Returns:
        True if pip is available

    Raises:
        SetupError: If pip is not available
    """
    print("[INFO] Checking pip availability...")

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            check=True,
            capture_output=True
        )
        print("[SUCCESS] pip is available")
        return True

    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SetupError("pip not found. Please install pip first") from exc


def check_dependencies_already_installed() -> bool:
    """
    Check if all required dependencies are already installed.

    Returns:
        True if all dependencies are already installed, False otherwise
    """
    print("[INFO] Checking if dependencies are already installed...")

    # Core dependencies to check (production only)
    core_dependencies = CORE_DEPENDENCIES

    missing_dependencies = []

    for module_name, package_name in core_dependencies.items():
        if module_name in _SKIP_IMPORT_CHECK_MODULES:
            continue
        try:
            if module_name == "langchain_openai":
                importlib.import_module("langchain_openai")
            elif module_name == "langgraph_checkpoint":
                importlib.import_module("langgraph_checkpoint")
            else:
                importlib.import_module(module_name)

        except ImportError:
            missing_dependencies.append(package_name)

    if not missing_dependencies:
        print("[SUCCESS] All Python dependencies are already installed!")
        return True
    print(f"[INFO] Missing dependencies: {', '.join(missing_dependencies)}")
    return False


def install_python_dependencies() -> bool:
    """
    Install Python dependencies from requirements.txt.

    Always runs ``pip install -r requirements.txt``. Core-import checks alone are
    not enough: requirements.txt adds Celery, py-ip2region, DB drivers, etc.

    Returns:
        True if installation succeeded

    Raises:
        SetupError: If requirements.txt not found or installation fails
    """
    if not os.path.exists("requirements.txt"):
        raise SetupError("requirements.txt not found")

    if check_dependencies_already_installed():
        print(
            "\n[INFO] Core Python imports OK; syncing full requirements.txt "
            "(celery, ip2region, qdrant-client, DB clients, etc.)..."
        )
    else:
        print("\n[INFO] Installing Python dependencies...")

    print("[INFO] Installing packages with progress tracking...")

    # Use pip with progress bar and verbose output
    if not run_command_with_progress(
        f"{sys.executable} -m pip install -r requirements.txt --progress-bar on",
        "Installing Python packages"
    ):
        raise SetupError("Failed to install Python dependencies")

    print("[SUCCESS] Python dependencies installed successfully")
    return True


def check_playwright_already_installed() -> bool:
    """
    Check if Playwright and Chromium browser are already installed.

    Returns:
        True if Playwright is fully installed, False otherwise
    """
    print("[INFO] Checking if Playwright is already installed...")

    try:
        if sync_playwright is None:
            print("[INFO] Playwright Python module not found")
            return False

        # Try to launch Chromium to verify browser installation
        with sync_playwright() as p:
            try:
                # Try to launch with minimal options to avoid issues
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )

                # If browser launches successfully, consider it working regardless of version check
                print("[SUCCESS] Playwright Chromium already installed and working")
                browser.close()
                return True

            except Exception as e:
                error_msg = str(e).lower()
                if "chromium" in error_msg and "not found" in error_msg:
                    print("[INFO] Playwright module found but Chromium browser not installed")
                elif "font" in error_msg or "library" in error_msg:
                    print("[INFO] Playwright module found but system dependencies may be missing")
                else:
                    print(f"[INFO] Playwright module found but browser launch failed: {e}")
                return False

    except ImportError:
        print("[INFO] Playwright Python module not found")
        return False
    except Exception as e:
        print(f"[INFO] Playwright check failed: {e}")
        return False


def install_playwright() -> bool:
    """
    Install Playwright with Chromium browser only.

    Returns:
        True if installation succeeded

    Raises:
        SetupError: If Playwright installation fails
    """
    print("\n[INFO] Installing Playwright (Chromium only)...")

    # Check if Playwright is already installed
    if check_playwright_already_installed():
        print("[INFO] Skipping Playwright installation - already complete")
        return True

    os_name = platform.system().lower()
    print(f"[INFO] Platform: {platform.system()} {platform.release()}")

    # Show installation details
    print("[INFO] Installation includes:")
    print("    - Playwright Python package (already installed via pip)")
    print("    - Chromium browser binary (~150MB)")

    if os_name != "windows":
        print("    - System dependencies (fonts, libraries, etc.)")
        print("      - Font packages (libwoff1, libwebp7, etc.)")
        print("      - Graphics libraries (libgdk-pixbuf2.0-0, libegl1)")
        print("      - Audio libraries (libopus0, libvpx7)")
        print("      - Other system packages (~50-100MB)")

    # Use --with-deps flag for automatic system dependency installation
    print("\n[INFO] Installing Chromium browser with system dependencies...")
    pw = get_playwright_cli_prefix()

    if os_name == "windows":
        print("[INFO] Windows detected - using python -m playwright")

        # On Windows, --with-deps is less critical but still useful
        if not run_command_with_progress(
            f"{pw} install chromium --with-deps",
            "Installing Chromium with dependencies",
        ):
            print("[WARNING] Installation with --with-deps failed, trying without...")
            if not run_command_with_progress(
                f"{pw} install chromium",
                "Installing Chromium",
            ):
                raise SetupError(
                    "Playwright installation failed. "
                    f"Try manually: {pw} install chromium"
                )
    else:
        print("[INFO] Unix-like system detected - installing with system dependencies")
        print("[INFO] This will install fonts, libraries, and other system packages")
        print("[INFO] May require sudo/administrator privileges")

        # Use --with-deps to install everything in one command
        if not run_command_with_progress(
            f"{pw} install chromium --with-deps",
            "Installing Chromium with system dependencies",
        ):
            print("[WARNING] Installation with --with-deps failed")
            print("[INFO] Trying two-step installation (install-deps + install chromium)...")

            # Fallback to two-step process
            if not run_command_with_progress(
                f"{pw} install-deps",
                "Installing Playwright system dependencies",
            ):
                raise SetupError(
                    "Failed to install system dependencies. "
                    "This may require sudo/administrator privileges. "
                    f"Try: sudo {pw} install chromium --with-deps"
                )

            if not run_command_with_progress(
                f"{pw} install chromium",
                "Installing Chromium browser",
            ):
                raise SetupError("Failed to install Chromium browser")

    print("[SUCCESS] Playwright Chromium installed successfully")
    return True


def get_local_chromium_executable() -> Optional[str]:
    """
    Get the path to local Chromium executable if available.

    Returns:
        str or None: Path to Chromium executable, or None if not found
    """
    system = platform.system().lower()
    chromium_path = Path(CHROMIUM_DIR)

    if not chromium_path.exists():
        return None

    if system == "windows":
        exe_path = chromium_path / "chrome.exe"
        return str(exe_path) if exe_path.exists() else None
    elif system == "darwin":  # macOS
        possible_paths = [
            chromium_path / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
            chromium_path / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
            chromium_path / "chrome"
        ]
        for path in possible_paths:
            if path.exists():
                return str(path)
        return None
    else:  # Linux
        possible_paths = [
            chromium_path / "chrome-linux" / "chrome",
            chromium_path / "chrome"
        ]
        for path in possible_paths:
            if path.exists():
                return str(path)
        return None


def check_offline_chromium_installed() -> bool:
    """
    Check if offline Chromium is already installed in browsers/chromium/.

    Returns:
        True if offline Chromium is installed and working, False otherwise
    """
    local_chromium = get_local_chromium_executable()

    if not local_chromium or not os.path.exists(local_chromium):
        return False

    # Try to verify the executable works
    try:
        result = subprocess.run(
            [local_chromium, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"[INFO] Found offline Chromium: {version}")
            return True
    except Exception:
        pass

    return False


def get_platform_name():
    """Get platform name for zip extraction"""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "mac"
    elif system == "linux":
        return "linux"
    else:
        return system

def extract_chromium_zip() -> bool:
    """
    Extract Chromium from multi-platform zip file if it exists.
    Extracts only the platform-specific folder from chromium.zip.

    Returns:
        True if extraction succeeded or zip doesn't exist, False on error
    """
    zip_path = Path(BROWSERS_DIR) / "chromium.zip"
    chromium_dest_dir = Path(CHROMIUM_DIR)
    platform_name = get_platform_name()

    # Check if zip exists
    if not zip_path.exists():
        return False

    print(f"\n[INFO] Found Chromium zip file: {zip_path.name}")
    print(f"[INFO] Extracting {platform_name} platform for: {platform.system()}")

    # Check if already extracted
    if check_offline_chromium_installed():
        print("[INFO] Chromium already extracted - skipping")
        return True

    try:
        # Create browsers directory if it doesn't exist
        browsers_path = Path(BROWSERS_DIR)
        browsers_path.mkdir(exist_ok=True)

        # Remove existing chromium directory if it exists
        if chromium_dest_dir.exists():
            print("[INFO] Removing existing Chromium installation...")
            shutil.rmtree(chromium_dest_dir)

        # Check what platforms are available in zip
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            available_platforms = set()
            for name in zipf.namelist():
                if '/' in name:
                    platform_in_zip = name.split('/')[0]
                    if platform_in_zip in ['windows', 'linux', 'mac']:
                        available_platforms.add(platform_in_zip)

            if available_platforms:
                print(f"[INFO] Zip contains platforms: {', '.join(sorted(available_platforms))}")

            if platform_name not in available_platforms:
                print(f"[ERROR] {platform_name} platform not found in zip file")
                print(f"[INFO] Available platforms in zip: {', '.join(sorted(available_platforms))}")
                print(f"[INFO] Your platform ({platform.system()}) requires: {platform_name}")
                print("[INFO] Falling back to Playwright download...")
                return False

        # Extract zip file (only platform-specific folder)
        print(f"[INFO] Extracting {platform_name} platform from zip...")
        print("    This may take a few minutes (~150MB)...")

        with zipfile.ZipFile(zip_path, 'r') as zipf:
            # Get files for current platform
            platform_files = [f for f in zipf.namelist() if f.startswith(f'{platform_name}/')]
            total_files = len(platform_files)
            extracted = 0

            # Extract only platform-specific files
            for member in platform_files:
                # Remove platform prefix from path
                target_path = member[len(f'{platform_name}/'):]
                if target_path:  # Skip empty paths
                    # Extract to chromium directory
                    full_path = chromium_dest_dir / target_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)

                    # Extract file (use copyfileobj for better memory efficiency)
                    with zipf.open(member) as source:
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(full_path, 'wb') as target:
                            shutil.copyfileobj(source, target)

                    extracted += 1
                    if extracted % 100 == 0:
                        print(f"    Progress: {extracted}/{total_files} files...", end='\r')

        # Clear progress line and print completion
        print(f"    Progress: {extracted}/{total_files} files...")
        print("\n[SUCCESS] Chromium extracted successfully!")

        # Verify installation
        if check_offline_chromium_installed():
            print(f"[INFO] Chromium is now available at: {CHROMIUM_DIR}")
            return True
        else:
            print("[WARNING] Chromium extracted but verification failed")
            return False

    except Exception as e:
        print(f"[ERROR] Failed to extract Chromium zip: {e}")
        return False


def copy_playwright_chromium_to_offline() -> bool:
    """
    Copy Playwright's installed Chromium to browsers/chromium/ for offline use.
    This is a fallback if zip extraction is not available.

    Returns:
        True if copy succeeded, False otherwise
    """
    print("\n[INFO] Setting up offline Chromium installation...")

    # Check if already installed
    if check_offline_chromium_installed():
        print("[INFO] Offline Chromium already installed - skipping")
        return True

    # Get Playwright's Chromium path
    try:
        if sync_playwright is None:
            print("[WARNING] Playwright not available - cannot copy Chromium")
            return False

        with sync_playwright() as p:
            playwright_chromium_path = p.chromium.executable_path
            if not playwright_chromium_path or not os.path.exists(playwright_chromium_path):
                print("[WARNING] Playwright Chromium not found - skipping offline copy")
                return False

            print(f"[INFO] Found Playwright Chromium at: {playwright_chromium_path}")

            # Find the Chromium directory (parent of executable)
            chromium_source_dir = os.path.dirname(playwright_chromium_path)

            # On macOS, Chromium.app is a bundle
            if platform.system().lower() == "darwin" and chromium_source_dir.endswith(".app"):
                chromium_source_dir = os.path.dirname(chromium_source_dir)

            # Create browsers directory if it doesn't exist
            browsers_path = Path(BROWSERS_DIR)
            browsers_path.mkdir(exist_ok=True)

            # Remove existing chromium directory if it exists
            chromium_dest_dir = Path(CHROMIUM_DIR)
            if chromium_dest_dir.exists():
                print("[INFO] Removing existing Chromium installation...")
                shutil.rmtree(chromium_dest_dir)

            # Copy Chromium directory
            print(f"[INFO] Copying Chromium to {CHROMIUM_DIR}...")
            print("    This may take a few minutes (~150MB)...")

            shutil.copytree(chromium_source_dir, chromium_dest_dir)

            # Verify installation
            if check_offline_chromium_installed():
                print("[SUCCESS] Offline Chromium installation complete!")
                print(f"[INFO] Chromium is now available at: {CHROMIUM_DIR}")
                return True
            else:
                print("[WARNING] Chromium copied but verification failed")
                return False

    except ImportError:
        print("[WARNING] Playwright not available - cannot copy Chromium")
        return False
    except Exception as e:
        print(f"[WARNING] Failed to copy Chromium for offline use: {e}")
        return False





def verify_dependencies() -> bool:
    """
    Verify all key dependencies are properly installed.

    Returns:
        True if all dependencies are verified

    Raises:
        SetupError: If dependency verification fails
    """
    print("\n[INFO] Verifying all dependencies...")

    # Core dependencies to check (production only)
    core_dependencies = CORE_DEPENDENCIES

    print("[INFO] Checking core dependencies...")
    failed_imports: List[str] = []
    successful_imports: List[str] = []

    total_deps = len(core_dependencies)
    for idx, (module_name, package_name) in enumerate(core_dependencies.items(), 1):
        print_progress(idx, total_deps, f"Checking {package_name}")

        try:
            # Handle special cases for packages with different import names
            if module_name == 'PIL':
                importlib.import_module('PIL')
                version = get_package_version('Pillow')
            elif module_name == 'multipart':
                importlib.import_module('multipart')
                version = get_package_version('python-multipart')
            elif module_name == 'yaml':
                importlib.import_module('yaml')
                version = get_package_version('PyYAML')
            elif module_name == 'dotenv':
                importlib.import_module('dotenv')
                version = get_package_version('python-dotenv')
            elif module_name == 'nest_asyncio':
                importlib.import_module('nest_asyncio')
                version = get_package_version('nest-asyncio')
            elif module_name == 'Crypto':
                importlib.import_module('Crypto.Cipher')
                version = get_package_version('pycryptodome')
            elif module_name == 'jose':
                importlib.import_module('jose.jwt')
                version = get_package_version('python-jose')
            elif module_name == 'pydantic_settings':
                importlib.import_module('pydantic_settings')
                version = get_package_version('pydantic-settings')
            elif module_name == 'email_validator':
                importlib.import_module('email_validator')
                version = get_package_version('email-validator')
            elif module_name == 'langchain_openai':
                importlib.import_module('langchain_openai')
                version = get_package_version('langchain-openai')
            elif module_name == 'langgraph_checkpoint':
                importlib.import_module('langgraph_checkpoint')
                version = get_package_version('langgraph-checkpoint')
            else:
                importlib.import_module(module_name)
                version = get_package_version(package_name)

            print(f"    [SUCCESS] {package_name:<20} - {version}")
            successful_imports.append(package_name)

        except ImportError as e:
            print(f"    [ERROR] {package_name:<20} - Import failed: {e}")
            failed_imports.append(package_name)
        except Exception as e:
            print(f"    [WARNING] {package_name:<20} - Version check failed: {e}")
            successful_imports.append(package_name)

    # Summary
    print("\n[INFO] Dependency Check Summary:")
    print(f"    [SUCCESS] Successful: {len(successful_imports)}/{len(core_dependencies)}")
    print(f"    [ERROR] Failed: {len(failed_imports)}/{len(core_dependencies)}")

    if failed_imports:
        raise SetupError(
            f"Failed dependencies: {', '.join(failed_imports)}. "
            "Please reinstall: pip install -r requirements.txt"
        )

    print("[SUCCESS] All core dependencies verified successfully!")
    return True


def verify_playwright_browsers() -> bool:
    """
    Verify Playwright browsers are properly installed.

    Returns:
        True if browsers are verified

    Raises:
        SetupError: If browser verification failed
    """
    print("\n[INFO] Verifying Playwright browsers...")

    if sync_playwright is None:
        raise SetupError("Playwright module not importable")

    try:
        with sync_playwright() as p:
            # Check if Chromium is available
            try:
                browser = p.chromium.launch(headless=True)

                # Try to get version, but don't worry if it fails
                try:
                    if hasattr(browser, 'version') and callable(browser.version):
                        version = browser.version()
                        print(f"    [SUCCESS] Chromium browser - {version}")
                    elif hasattr(browser, 'version'):
                        version = browser.version
                        print(f"    [SUCCESS] Chromium browser - {version}")
                    else:
                        print("    [SUCCESS] Chromium browser - Working")
                except Exception:
                    print("    [SUCCESS] Chromium browser - Working")

                browser.close()

                # Additional verification for system dependencies
                if platform.system().lower() != "windows":
                    print("    [INFO] Verifying system dependencies...")
                    try:
                        # Test browser launch with system dependency flags
                        browser = p.chromium.launch(
                            headless=True,
                            args=['--no-sandbox', '--disable-dev-shm-usage']
                        )
                        browser.close()
                        print("    [SUCCESS] System dependencies verified (fonts, libraries)")
                    except Exception as e:
                        print(f"    [WARNING] System dependency warning: {e}")
                        print("    [INFO] This may affect rendering quality but browser should work")

                return True

            except Exception as e:
                print(f"    [ERROR] Chromium browser - Failed to launch: {e}")
                if "font" in str(e).lower() or "library" in str(e).lower():
                    print("    [INFO] This may be a system dependency issue")
                    pfx = get_playwright_cli_prefix()
                    print(f"    [INFO] Try: sudo {pfx} install chromium --with-deps")
                raise SetupError("Chromium browser verification failed") from e

    except SetupError:
        raise
    except ImportError as exc:
        raise SetupError("Playwright module not importable") from exc
    except Exception as exc:
        raise SetupError(f"Browser verification failed: {exc}") from exc


def verify_file_structure() -> bool:
    """
    Verify essential files and directories exist.

    Returns:
        True if file structure is verified

    Raises:
        SetupError: If file structure verification fails
    """
    print("\n[INFO] Verifying file structure...")

    # Check files (we're already in project root from main())
    for file_path in ESSENTIAL_FILES:
        if os.path.exists(file_path):
            print(f"    [SUCCESS] {file_path}")
        else:
            raise SetupError(f"Essential file missing: {file_path}")

    # Check directories
    for dir_path in ESSENTIAL_DIRECTORIES:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            print(f"    [SUCCESS] {dir_path}/")
        else:
            raise SetupError(f"Essential directory missing: {dir_path}/")

    # Check log files
    for log_file in REQUIRED_LOG_FILES:
        log_path = os.path.join("logs", log_file)
        if os.path.exists(log_path):
            print(f"    [SUCCESS] logs/{log_file}")
        else:
            raise SetupError(f"Log file missing: logs/{log_file}")

    print("[SUCCESS] File structure verified successfully!")
    return True


def print_banner() -> None:
    """Display the MindGraph ASCII banner"""
    banner = """
    ███╗   ███╗██╗███╗   ██╗██████╗ ███╗   ███╗ █████╗ ████████╗███████╗
    ████╗ ████║██║████╗  ██║██╔══██╗████╗ ████║██╔══██╗╚══██╔══╝██╔════╝
    ██╔████╔██║██║██╔██╗ ██║██║  ██║██╔████╔██║███████║   ██║   █████╗
    ██║╚██╔╝██║██║██║╚██╗██║██║  ██║██║╚██╔╝██║██╔══██║   ██║   ██╔══╝
    ██║ ╚═╝ ██║██║██║ ╚████║██████╔╝██║ ╚═╝ ██║██║  ██║   ██║   ███████╗
    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝
================================================================================
    MindGraph - AI-Powered Graph Generation Application
    ==================================================
    """
    print(banner)


def print_progress(current: int, total: int, description: str = "") -> None:
    """Print a simple progress indicator"""
    percentage = (current / total) * 100
    bar_length = PROGRESS_BAR_LENGTH
    filled_length = int(bar_length * current // total)
    progress_bar = '█' * filled_length + '░' * (bar_length - filled_length)

    if description:
        print(f"\r[INFO] {description} [{progress_bar}] {percentage:.1f}% ({current}/{total})", end='', flush=True)
    else:
        print(f"\r[INFO] Progress [{progress_bar}] {percentage:.1f}% ({current}/{total})", end='', flush=True)

    if current == total:
        print()  # New line when complete


def check_logs_already_configured() -> bool:
    """
    Check if the logging system is already properly configured.

    Returns:
        True if logs are already configured, False otherwise
    """
    print("[INFO] Checking if logging system is already configured...")

    try:
        # We're already in project root from main()
        logs_dir = "logs"

        # Check if logs directory exists
        if not os.path.exists(logs_dir):
            print("[INFO] Logs directory not found")
            return False

        # Check if all required log files exist
        log_files = REQUIRED_LOG_FILES

        missing_files = []
        for log_file in log_files:
            log_path = os.path.join(logs_dir, log_file)
            if not os.path.exists(log_path):
                missing_files.append(log_file)

        if not missing_files:
            print("[SUCCESS] Logging system already configured - all files present")
            return True
        else:
            print(f"[INFO] Missing log files: {', '.join(missing_files)}")
            return False

    except Exception as e:
        print(f"[INFO] Logs check failed: {e}")
        return False


def setup_logs_directory() -> bool:
    """
    Create logs directory and set proper permissions.

    Returns:
        True if setup succeeded

    Raises:
        SetupError: If logs setup fails
    """
    print("[INFO] Setting up logging system...")

    # Check if logs are already configured
    if check_logs_already_configured():
        print("[INFO] Skipping logs setup - already configured")
        return True

    try:
        # We're already in project root from main()
        logs_dir = "logs"

        # Create logs directory if it doesn't exist
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, mode=0o755)
            print("    [SUCCESS] Created logs directory")
        else:
            print("    [INFO] Logs directory already exists")

        # Create log files if they don't exist
        log_files = REQUIRED_LOG_FILES

        for log_file in log_files:
            log_path = os.path.join(logs_dir, log_file)
            if not os.path.exists(log_path):
                # Create empty log file
                with open(log_path, 'w', encoding='utf-8'):
                    pass
                print(f"    [SUCCESS] Created log file: {log_file}")
            else:
                print(f"    [INFO] Log file exists: {log_file}")

        # Set proper permissions (755 for directory, 644 for files)
        os.chmod(logs_dir, 0o755)

        # Set file permissions
        for log_file in log_files:
            log_path = os.path.join(logs_dir, log_file)
            if os.path.isfile(log_path):
                os.chmod(log_path, 0o644)

        print("[SUCCESS] Logging system configured")
        return True

    except Exception as exc:
        raise SetupError(f"Failed to setup logging system: {exc}") from exc


def setup_data_directory() -> bool:
    """
    Create data directory for database files.

    Returns:
        True if setup succeeded

    Raises:
        SetupError: If data directory setup fails
    """
    print("[INFO] Setting up data directory...")

    try:
        # We're already in project root from main()
        data_dir = "data"

        # Create data directory if it doesn't exist
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, mode=0o755)
            print("    [SUCCESS] Created data directory")
        else:
            print("    [INFO] Data directory already exists")

        # Set proper permissions (755 for directory)
        os.chmod(data_dir, 0o755)

        print("[SUCCESS] Data directory configured")
        return True

    except Exception as exc:
        raise SetupError(f"Failed to setup data directory: {exc}") from exc


def setup_application_directories() -> bool:
    """
    Create application-specific directories needed at runtime.

    Creates:
    - static/images/ - for uploaded images
    - tests/images/ - for test images
    - temp_images/ - for temporary PNG files

    Returns:
        True if setup succeeded

    Raises:
        SetupError: If directory setup fails
    """
    print("[INFO] Setting up application directories...")

    try:
        # We're already in project root from main()
        directories_to_create = [
            ("static/images", "Static images"),
            ("static/community", "Community thumbnails"),
            ("tests/images", "Test images"),
            ("temp_images", "Temporary images")
        ]

        for dir_path, description in directories_to_create:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, mode=0o755)
                print(f"    [SUCCESS] Created {description} directory: {dir_path}/")
            else:
                print(f"    [INFO] {description} directory already exists: {dir_path}/")

            # Set proper permissions (755 for directory)
            os.chmod(dir_path, 0o755)

        print("[SUCCESS] Application directories configured")
        return True

    except Exception as exc:
        raise SetupError(f"Failed to setup application directories: {exc}") from exc


def cleanup_temp_files() -> None:
    """Clean up any temporary files created during setup"""
    try:
        # We're already in project root from main()
        debug_script = "debug_playwright.py"
        if os.path.exists(debug_script):
            os.remove(debug_script)
            print("[INFO] Cleaned up temporary debug script")
    except Exception as e:
        print(f"[WARNING] Could not clean up temporary files: {e}")


def print_setup_summary(setup_summary: Dict[str, bool]) -> None:
    """Print a formatted setup summary"""
    print("\n[INFO] Setup Summary:")

    if setup_summary.get('tesseract'):
        print("    ✅ Tesseract OCR - Installed or verified")
    else:
        print("    ⏭️  Tesseract OCR - Skipped or verify PATH manually")

    if setup_summary.get("redis"):
        print("    ✅ Redis - Responding or installed")
    else:
        print("    ⏭️  Redis - Not verified (install or set REDIS_URL)")

    if setup_summary.get("postgres"):
        print("    ✅ PostgreSQL - Client/service present or installed")
    else:
        print("    ⏭️  PostgreSQL - Not verified (install or use SQLite)")

    if setup_summary['python_deps']:
        print("    ✅ Python dependencies - Installed/Updated")
    else:
        print("    ⏭️  Python dependencies - Already installed (skipped)")

    if setup_summary.get("qdrant"):
        print("    ✅ Qdrant server - Installed or API responding")
    else:
        print("    ⏭️  Qdrant - Skipped or verify QDRANT_HOST (docs/QDRANT_SETUP.md)")

    if setup_summary['playwright']:
        print("    ✅ Playwright browser - Installed/Updated")
    else:
        print("    ⏭️  Playwright browser - Already installed (skipped)")

    if setup_summary.get('offline_chromium', False):
        print("    ✅ Offline Chromium - Installed in browsers/chromium/")
    elif check_offline_chromium_installed():
        print("    ⏭️  Offline Chromium - Already installed (skipped)")
    else:
        print("    ⏭️  Offline Chromium - Not installed (optional)")

    if setup_summary['logs']:
        print("    ✅ Logging system - Configured")
    else:
        print("    ⏭️  Logging system - Already configured (skipped)")


def print_next_steps() -> None:
    """Print next steps for the user"""
    print("\n[INFO] Next steps:")
    print("    1. Copy env.example to .env and configure your API keys")
    print(
        "    2. Set REDIS_URL and (if used) DATABASE_URL / PostgreSQL vars — "
        "see docs/REDIS_SETUP.md, docs/POSTGRES_SETUP.md"
    )
    print(
        "    3. Knowledge Space: set QDRANT_HOST (e.g. localhost:6333) if using RAG; "
        "full setup runs Qdrant on Linux+sudo (docs/QDRANT_SETUP.md)"
    )
    print(
        "    4. Optional: python scripts/setup/dashboard_install.py — ip2region xdb, "
        "map/static assets (scripts/setup/setup_ip2region.md)"
    )
    print("    5. Run: python main.py")
    print("    6. Open http://localhost:9527 in your browser")

    # Show platform-specific hints
    os_name = platform.system().lower()
    if os_name == "linux":
        print("\n[INFO] For Linux deployment:")
        print(
            "    - Celery/Redis: install OS Redis (docs/REDIS_SETUP.md); "
            "requirements.txt already lists celery and redis Python packages"
        )
        print("    - Production deployment: ./scripts/setup_systemd.sh (if present)")
        print("    - Then use: sudo systemctl start/stop/restart mindgraph")
        print("    - See docs/ and README.md for detailed instructions")

    print("\n[INFO] For more information, see README.md")


def parse_setup_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI for setup.py (--help only; options are chosen via prompts)."""
    parser = argparse.ArgumentParser(
        description=(
            "MindGraph complete setup: Tesseract, Redis, PostgreSQL, Qdrant (Linux), "
            "Python deps, Playwright Chromium + OS dependencies."
        ),
        epilog=(
            "On Linux, the script asks optional yes/no questions. "
            "Set MINDGRAPH_NON_INTERACTIVE=1 to skip prompts (full install)."
        ),
    )
    return parser.parse_args(argv)


def main() -> None:
    """
    Main setup function that orchestrates the entire installation process.

    Raises:
        SetupError: If any step fails
        SystemExit: On successful completion or user interruption
    """
    start_time = time.time()
    parse_setup_args(sys.argv[1:])

    script_path = os.path.abspath(__file__)
    project_root = resolve_project_root(os.path.dirname(script_path))

    # Change to project root directory for all operations
    original_cwd = os.getcwd()
    os.chdir(project_root)

    # Display the MindGraph banner
    print_banner()
    print("[INFO] Starting MindGraph Complete Setup")
    print("=" * 60)
    print("[INFO] Smart Setup: Will skip steps that are already complete")
    print("=" * 60)

    allow_non_root, skip_redis_postgres, skip_qdrant = resolve_setup_interactive_options()

    try:
        ensure_linux_elevation_or_allow(allow_non_root)
    except SetupError as e:
        print(f"\n[ERROR] {e}")
        os.chdir(original_cwd)
        sys.exit(1)

    print_infrastructure_docs_hint(project_root)

    # Show platform-specific notes
    os_name = platform.system().lower()
    if os_name != "windows":
        print("\n[INFO] Note: On Linux/macOS, Playwright may install system libraries")
        print("    (fonts, codecs). Run this script with sudo on Linux for full installs.")
        print()

    # Track what was actually performed vs skipped
    setup_summary = {
        'python_deps': False,
        'playwright': False,
        'logs': False,
        'offline_chromium': False,
        'tesseract': False,
        'redis': False,
        'postgres': False,
        'qdrant': False,
    }

    try:
        # Step 1: Environment checks
        print(f"[STEP 1/{SETUP_STEPS}] Environment validation...")
        print_system_info()
        check_python_version()
        check_pip()
        print("[SUCCESS] Environment validation completed")

        # Step 2: Tesseract OCR (system binary)
        print(f"\n[STEP 2/{SETUP_STEPS}] Tesseract OCR (system)...")
        if install_tesseract_ocr_system():
            setup_summary['tesseract'] = True

        # Step 3: Redis and PostgreSQL (Linux + sudo, unless skipped)
        print(f"\n[STEP 3/{SETUP_STEPS}] Redis and PostgreSQL (systemd services)...")
        redis_ok, pg_ok = install_redis_and_postgresql_linux(skip=skip_redis_postgres)
        setup_summary['redis'] = redis_ok
        setup_summary['postgres'] = pg_ok

        # Step 4: Install Python dependencies
        print(f"\n[STEP 4/{SETUP_STEPS}] Python dependencies...")
        if install_python_dependencies():
            setup_summary['python_deps'] = True

        # Step 5: Qdrant vector server (Linux + sudo; docs/QDRANT_SETUP.md)
        print(f"\n[STEP 5/{SETUP_STEPS}] Qdrant vector database (Knowledge Space)...")
        if install_qdrant_via_documented_flow(
            project_root,
            skip=skip_qdrant,
            allow_non_root=allow_non_root,
        ):
            setup_summary["qdrant"] = True

        # Step 6: Install Playwright
        print(f"\n[STEP 6/{SETUP_STEPS}] Playwright browser...")

        # First, try to extract from zip if available (fastest option)
        chromium_from_zip = False
        zip_path = Path(BROWSERS_DIR) / "chromium.zip"

        if zip_path.exists():
            print("[INFO] Found chromium.zip - attempting extraction...")
            try:
                if extract_chromium_zip():
                    chromium_from_zip = True
                    setup_summary['offline_chromium'] = True
                    print("[SUCCESS] Using Chromium from zip file - skipping Playwright download")
                else:
                    print("[WARNING] Zip extraction failed, falling back to Playwright download")
            except Exception as e:
                print(f"[WARNING] Error extracting zip: {e}")
                print("[INFO] Falling back to Playwright download...")
        else:
            print("[INFO] No chromium.zip found - will download via Playwright")

        # If zip extraction didn't work, install via Playwright
        if not chromium_from_zip:
            if install_playwright():
                setup_summary['playwright'] = True

                # Copy Chromium for offline use (optional, non-blocking)
                try:
                    if copy_playwright_chromium_to_offline():
                        setup_summary['offline_chromium'] = True
                except Exception as e:
                    print(f"[WARNING] Offline Chromium setup skipped: {e}")
                    print("[INFO] You can run this manually later if needed")

        # Step 7: Setup logging and data directories
        print(f"\n[STEP 7/{SETUP_STEPS}] Directory setup...")
        if setup_logs_directory():
            setup_summary['logs'] = True
        setup_data_directory()
        setup_application_directories()

        # Step 8: Comprehensive verification
        print(f"\n[STEP 8/{SETUP_STEPS}] System verification...")
        verify_dependencies()
        verify_tesseract_ocr()
        verify_redis_postgres_hints()
        verify_qdrant_hint()
        verify_playwright_browsers()
        verify_file_structure()

        # Cleanup temporary files
        cleanup_temp_files()

        # Calculate execution time
        execution_time = time.time() - start_time

        # Show setup summary
        print("\n" + "=" * 60)
        print("[SUCCESS] MindGraph setup completed successfully!")
        print(f"[INFO] Total execution time: {execution_time:.1f} seconds")

        print_setup_summary(setup_summary)
        print_next_steps()
        print("=" * 60)

        # Restore original working directory
        os.chdir(original_cwd)
        sys.exit(0)

    except SetupError as e:
        print(f"\n[ERROR] Setup failed: {e}")
        print(f"[INFO] Execution time: {time.time() - start_time:.1f} seconds")
        print("\n[INFO] Troubleshooting:")
        print("    - Check your internet connection")
        print("    - Ensure you have sufficient disk space")
        print("    - Try running with administrator privileges if needed")
        os.chdir(original_cwd)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n[WARNING] Setup interrupted by user")
        print(f"[INFO] Execution time: {time.time() - start_time:.1f} seconds")
        os.chdir(original_cwd)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        print(f"[INFO] Execution time: {time.time() - start_time:.1f} seconds")
        print("\n[INFO] This may be a bug. Please report the issue with:")
        print("    - Python version:", sys.version)
        print("    - Platform:", platform.system(), platform.release())
        print("    - Error details:", str(e))
        os.chdir(original_cwd)
        sys.exit(1)


if __name__ == "__main__":
    main()
