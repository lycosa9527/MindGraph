"""IP reputation env flag readers (leaf module — no service imports).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os


def env_bool(name: str, default: bool = False) -> bool:
    """Env bool."""
    val = os.getenv(name, "").lower().strip()
    if not val:
        return default
    return val in ("1", "true", "yes", "on")


def env_int(name: str, default: int) -> int:
    """Env int."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def abuseipdb_master_enabled() -> bool:
    """True when AbuseIPDB features may run (requires API key)."""
    return env_bool("ABUSEIPDB_ENABLED", False) and bool(os.getenv("ABUSEIPDB_API_KEY", "").strip())


def abuseipdb_check_enabled() -> bool:
    """GET /check per IP (quota). Default off: use daily blacklist sync + Redis only."""
    return abuseipdb_master_enabled() and env_bool("ABUSEIPDB_CHECK_ENABLED", False)


def abuseipdb_blacklist_lookup_enabled() -> bool:
    """Abuseipdb blacklist lookup enabled."""
    return abuseipdb_master_enabled() and env_bool("ABUSEIPDB_BLACKLIST_LOOKUP_ENABLED", True)


def abuseipdb_report_enabled() -> bool:
    """Abuseipdb report enabled."""
    return abuseipdb_master_enabled() and env_bool("ABUSEIPDB_REPORT_ENABLED", True)


def abuseipdb_blacklist_sync_enabled() -> bool:
    """Abuseipdb blacklist sync enabled."""
    return abuseipdb_master_enabled() and env_bool("ABUSEIPDB_BLACKLIST_SYNC_ENABLED", True)


def get_check_min_score() -> int:
    """Get check min score."""
    return max(0, min(100, env_int("ABUSEIPDB_CHECK_MIN_SCORE", 80)))


def crowdsec_blocklist_credentials_configured() -> bool:
    """True when username and password are set (Console integration credentials)."""
    user = os.getenv("CROWDSEC_BLOCKLIST_USERNAME", "").strip()
    password = os.getenv("CROWDSEC_BLOCKLIST_PASSWORD", "").strip()
    return bool(user and password)


def crowdsec_blocklist_endpoint_configured() -> bool:
    """True when URL or integration id is set."""
    url = os.getenv("CROWDSEC_BLOCKLIST_URL", "").strip()
    if url:
        return True
    integration_id = os.getenv("CROWDSEC_BLOCKLIST_INTEGRATION_ID", "").strip()
    return bool(integration_id)


def crowdsec_blocklist_master_enabled() -> bool:
    """True when CrowdSec blocklist merge may run (operator opted in and configured)."""
    if not env_bool("CROWDSEC_BLOCKLIST_ENABLED", False):
        return False
    if not crowdsec_blocklist_credentials_configured():
        return False
    return crowdsec_blocklist_endpoint_configured()


def crowdsec_blocklist_sync_enabled() -> bool:
    """Crowdsec blocklist sync enabled."""
    return crowdsec_blocklist_master_enabled() and env_bool("CROWDSEC_BLOCKLIST_SYNC_ENABLED", True)


def crowdsec_blocklist_lookup_enabled() -> bool:
    """Use shared Redis blacklist for blocking (CrowdSec-only or with AbuseIPDB)."""
    return crowdsec_blocklist_master_enabled() and env_bool("CROWDSEC_BLOCKLIST_LOOKUP_ENABLED", True)
