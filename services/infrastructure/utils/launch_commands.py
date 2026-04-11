"""
Copy-paste commands for MindGraph launch dependencies.

Single source of truth for operator hints (ports, Redis, Qdrant, Celery, Fail2ban,
Tesseract OCR, Playwright, etc.).

Run:
  python -m services.infrastructure.utils.launch_commands
"""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

_MODULE_INVOKE = "python -m services.infrastructure.utils.launch_commands"

FAIL2BAN_CHECK_CMD = "python3 -m services.infrastructure.security.fail2ban_integration check"
FAIL2BAN_SETUP_CMD = (
    'sudo PYTHONPATH="$PWD" python3 -m services.infrastructure.security.fail2ban_integration '
    "setup --npm-home /root/npm --proxy-host 1"
)

CELERY_WORKER_CMD = "celery -A config.celery worker --loglevel=info"

# Same URL as services.auth.geoip_country.GEOIP_GEOLITE_DOWNLOAD_URL (keep in sync).
GEOLITE_MAXMIND_INFO_URL = (
    "https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/?lang=en"
)

LIFESPAN_ORDER_TEXT = """
  1. Fail2ban gate (Linux only; FAIL2BAN_STARTUP_CHECK=false to skip)
  2. Redis (required)
  3. AbuseIPDB/CrowdSec baselines (warnings only if merge fails)
  4. Qdrant (if FEATURE_KNOWLEDGE_SPACE)
  5. Celery worker check (if FEATURE_KNOWLEDGE_SPACE)
  6. System deps / Tesseract (if Knowledge Space)
  7. Database integrity + init_db
  8. Remaining services (LLM, schedulers, etc.)
""".strip()


def redis_port_from_url(redis_url: str) -> int:
    try:
        parsed = urlparse(redis_url)
        if parsed.port is not None:
            return int(parsed.port)
    except (ValueError, TypeError, OSError):
        pass
    return 6379


def lines_tcp_port_kill(port: int) -> list[str]:
    lines = [f"If something else holds port {port}, free it:"]
    if sys.platform == "win32":
        lines.extend(
            [
                f"  netstat -ano | findstr :{port}",
                "  taskkill /PID <PID> /F",
            ]
        )
    else:
        lines.extend(
            [
                f"  lsof -ti:{port} | xargs kill -9",
                f"  sudo fuser -k {port}/tcp",
            ]
        )
    return lines


def error_footer_launch_reference() -> list[str]:
    return [
        "",
        "Full launch dependency cheatsheet (all copy-paste commands):",
        f"  {_MODULE_INVOKE}",
    ]


def lines_redis_connection_failed(
    redis_url: str,
    exc: str,
    *,
    include_footer: bool = True,
) -> list[str]:
    """Log body for Redis connection failure (includes port-kill; optional cheatsheet footer)."""
    port = redis_port_from_url(redis_url)
    lines = [
        f"Failed to connect to Redis at: {redis_url}",
        f"Error: {exc}",
        "",
        "MindGraph requires Redis. Ensure the server is running:",
        "",
        "  Ubuntu:  sudo apt install redis-server",
        "           sudo systemctl start redis-server",
        "",
        "  macOS:   brew install redis && brew services start redis",
        "",
        f"Set REDIS_URL in .env (default uses port {port}).",
        "",
        *lines_tcp_port_kill(port),
    ]
    if include_footer:
        lines.extend(error_footer_launch_reference())
    return lines


def lines_http_port_in_use(port: int, pid: int | None, *, include_footer: bool = True) -> list[str]:
    out = [f"Port {port} is already in use."]
    if pid is not None:
        out.append(f"Detected process ID: {pid}")
    out.extend(
        [
            "",
            "Solutions:",
            "  1. Stop the process using this port:",
        ]
    )
    for line in lines_tcp_port_kill(port):
        out.append(f"     {line}")
    out.extend(
        [
            "  2. Use a different port: set PORT=<port> in .env",
            "  3. Check if another MindGraph instance is running",
        ]
    )
    if include_footer:
        out.extend(error_footer_launch_reference())
    return out


def lines_qdrant_connection_failed(
    connection_info: str,
    exc: str,
    port: int,
    *,
    include_footer: bool = True,
) -> list[str]:
    lines = [
        f"Failed to connect to Qdrant at: {connection_info}",
        f"Error: {exc}",
        "",
        "MindGraph requires Qdrant when Knowledge Space is enabled.",
        "",
        "  Install (Linux):  sudo python3 scripts/setup/setup.py",
        "  Ubuntu service:   sudo systemctl start qdrant",
        "  Foreground:       qdrant",
        "",
        "Set QDRANT_HOST or QDRANT_URL in .env (see docs/QDRANT_SETUP.md).",
        "",
        *lines_tcp_port_kill(port),
    ]
    if include_footer:
        lines.extend(error_footer_launch_reference())
    return lines


def lines_fail2ban_host_install() -> list[str]:
    """When fail2ban-client is missing on the host (check.py / startup_gate)."""
    return [
        "Install Fail2ban on the host (Debian/Ubuntu example):",
        "  sudo apt install fail2ban",
        "  sudo systemctl enable --now fail2ban",
    ]


def lines_fail2ban_deploy() -> list[str]:
    return [FAIL2BAN_CHECK_CMD, FAIL2BAN_SETUP_CMD]


def lines_celery_recovery() -> list[str]:
    return [
        "Start a worker from the MindGraph repo (venv active):",
        f"  {CELERY_WORKER_CMD}",
        "",
        'Or run "python main.py" so the server launcher can start stack components.',
        "Redis must be running (Celery broker).",
    ]


def lines_postgresql_hint() -> list[str]:
    return [
        "PostgreSQL: ensure DATABASE_URL is reachable.",
        "  pip install psycopg2-binary",
        "  Ubuntu: sudo systemctl start postgresql",
        "  Install server: sudo apt-get install postgresql postgresql-contrib  (or brew install postgresql)",
        "",
        "If port 5432 is stuck:",
        *[f"  {line}" for line in lines_tcp_port_kill(5432)],
    ]


def lines_requirements_quickstart() -> list[str]:
    """Mirrors comments at top of requirements.txt."""
    return [
        "Recommended first-time setup (requirements.txt header):",
        "  pip install -r requirements.txt",
        "  python -m playwright install chromium",
        "  cp env.example .env   # then edit .env",
    ]


def lines_core_python_clients() -> list[str]:
    """Explicit pip lines (also covered by requirements.txt). Matches dependency_checker / redis_client."""
    return [
        "Core Python packages (if something is missing in isolation):",
        "  pip install redis>=5.0.0",
        "  pip install celery",
        "  pip install qdrant-client",
        '  pip install "psycopg[binary]"',
        "  pip install uvicorn[standard]>=0.24.0",
        "  Some scripts still mention psycopg2-binary; app standard is psycopg3 above.",
    ]


def lines_optional_feature_packages() -> list[str]:
    """
    Copy-paste for packages, data files, and scripts whose hints live in individual modules.

    Sweep: dependency_checker, ip_geolocation, geoip_country, bayi_mode, backup_scheduler,
    chunk_comparator, rag_service, swot_academic, download_datasets, prompt_output_languages,
    dashboard_install, provision_infra, etc.
    """
    return [
        "Optional / feature-specific (module log strings):",
        "",
        *lines_requirements_quickstart(),
        "",
        *lines_core_python_clients(),
        "",
        "IP / Geo:",
        "  pip install py-ip2region",
        "  pip install geoip2",
        "  python scripts/setup/dashboard_install.py   # ip2region xdb + dashboard assets",
        "GeoLite2-Country.mmdb (overseas email / GeoIP):",
        f"  Info: {GEOLITE_MAXMIND_INFO_URL}",
        "  Copy GeoLite2-Country.mmdb to data/ or set GEOIP_MAXMIND_COUNTRY_PATH",
        "",
        "Integrations:",
        "  pip install pycryptodome",
        "  pip install cos-python-sdk-v5",
        "Academic email (pyswot): install via requirements.txt (GitHub rse-pyswot; see requirements header)",
        "",
        "RAG / knowledge / chunking:",
        "  pip install numpy",
        "  pip install semchunk jieba3 tiktoken langdetect opencc-python-reimplemented",
        "  pip install spacy && python -m spacy download en_core_web_sm",
        "  pip install chonkie langchain-text-splitters llm-chunking",
        "  pip install datasets>=2.14.0",
        "",
        "Repo / DB maintenance scripts:",
        "  python scripts/build_prompt_language_registry.py",
        "  python scripts/db/run_migrations.py",
        "  python scripts/swot/sync_kikobeats_domains.py   # optional: refresh free-email list",
        "",
        "Frontend (production SPA):",
        "  cd frontend && npm ci && npm run build",
    ]


def lines_tesseract_hint() -> list[str]:
    """Binary + Python bindings (matches dependency_checker / document_processor)."""
    return [
        "Tesseract OCR (Knowledge Space document OCR):",
        "  pip install pytesseract Pillow",
        "  Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim",
        "  macOS: brew install tesseract",
        "  Windows: https://github.com/UB-Mannheim/tesseract/wiki",
    ]


def lines_playwright_hint() -> list[str]:
    """Chromium for PNG generation (matches browser.py / setup.py patterns)."""
    return [
        "Playwright (PNG generation: /api/generate_png, /api/generate_dingtalk):",
        "  pip install playwright",
        "  python -m playwright install chromium",
        "  Linux system libraries (if Chromium fails to start):",
        "    sudo python -m playwright install-deps chromium",
        "  Optional (all browsers): python -m playwright install",
        "  Conda env example: conda activate python3.13 && python -m playwright install chromium",
    ]


def lines_playwright_startup_critical() -> list[str]:
    """Banner + hints when lifespan detects missing Playwright browsers."""
    return [
        "=" * 80,
        "CRITICAL: Playwright browsers are not installed!",
        "PNG generation endpoints (/api/generate_png, /api/generate_dingtalk) will fail.",
        "",
        *lines_playwright_hint(),
        *error_footer_launch_reference(),
        "=" * 80,
    ]


def build_cheatsheet_text() -> str:
    sections: list[str] = [
        "=" * 80,
        "MindGraph - launch dependency reference (copy-paste)",
        "=" * 80,
        "",
        "FastAPI lifespan order (main worker):",
        LIFESPAN_ORDER_TEXT,
        "",
        "--- Redis ---",
        *lines_redis_connection_failed("redis://localhost:6379/0", "<example>", include_footer=False),
        "",
        "--- HTTP listen port (python main.py / uvicorn) ---",
        *lines_http_port_in_use(8000, None, include_footer=False),
        "",
        "--- Qdrant (FEATURE_KNOWLEDGE_SPACE=true) ---",
        *lines_qdrant_connection_failed("localhost:6333", "<example>", 6333, include_footer=False),
        "",
        "--- Celery ---",
        *lines_celery_recovery(),
        "",
        "--- Fail2ban (Linux) ---",
        "Skip gate: FAIL2BAN_STARTUP_CHECK=false",
        *lines_fail2ban_host_install(),
        *lines_fail2ban_deploy(),
        "",
        "--- PostgreSQL ---",
        *lines_postgresql_hint(),
        "",
        "--- Tesseract ---",
        *lines_tesseract_hint(),
        "",
        "--- Playwright ---",
        *lines_playwright_hint(),
        "",
        "--- Full sweep (pip, Geo data, scripts, frontend) ---",
        *lines_optional_feature_packages(),
        "",
        *error_footer_launch_reference(),
        "",
        "=" * 80,
        "Re-print this sheet:",
        f"  {_MODULE_INVOKE}",
        "=" * 80,
        "",
    ]
    return "\n".join(sections)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=_MODULE_INVOKE,
        description="Print copy-paste commands for MindGraph launch dependencies.",
    )
    parser.parse_args(argv)
    print(build_cheatsheet_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
