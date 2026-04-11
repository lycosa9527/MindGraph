"""
Process-lifetime snapshot of IP reputation env flags (read once after Redis init).

Avoids repeated os.getenv / branching on the hot middleware path. Tests should reset
via invalidate_ip_reputation_env_snapshot() when monkeypatching related env vars.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_IP_REPUTATION_SNAPSHOT: Optional[Tuple[bool, bool, bool, bool, int]] = None
# abuse_master, crowd_lookup_enabled, blacklist_lookup_active, check_enabled, check_min_score


def warm_ip_reputation_env_snapshot() -> None:
    """Read AbuseIPDB/CrowdSec flags once; call from application lifespan after Redis init."""
    global _IP_REPUTATION_SNAPSHOT
    from services.infrastructure.security import abuseipdb_service
    from services.infrastructure.security import crowdsec_blocklist_service

    abuse_master = abuseipdb_service.abuseipdb_master_enabled()
    crowd_lu = crowdsec_blocklist_service.crowdsec_blocklist_lookup_enabled()
    lookup_active = (
        abuse_master and abuseipdb_service.abuseipdb_blacklist_lookup_enabled()
    ) or crowd_lu
    check_enabled = abuseipdb_service.abuseipdb_check_enabled()
    check_min = abuseipdb_service.get_check_min_score()
    _IP_REPUTATION_SNAPSHOT = (abuse_master, crowd_lu, lookup_active, check_enabled, check_min)


def log_ip_reputation_startup_summary() -> None:
    """
    Log once after warm_ip_reputation_env_snapshot() so operators see how vetting is configured.
    """
    if _IP_REPUTATION_SNAPSHOT is None:
        warm_ip_reputation_env_snapshot()
    abuse_master, crowd_lu, lookup_active, check_enabled, check_min = (
        _IP_REPUTATION_SNAPSHOT
        or (False, False, False, False, 80)
    )
    from services.infrastructure.security import abuseipdb_service
    from services.infrastructure.security import crowdsec_blocklist_service

    abuse_bl = (
        bool(abuse_master) and abuseipdb_service.abuseipdb_blacklist_lookup_enabled()
    )
    if should_skip_ip_reputation_middleware():
        logger.info(
            "[IP reputation] Middleware inactive (enable ABUSEIPDB_* and/or "
            "CROWDSEC_BLOCKLIST_* for shared Redis blacklist vetting)."
        )
        return

    logger.info(
        "[IP reputation] Middleware active: shared_blacklist=%s "
        "(abuseipdb_blacklist=%s, crowdsec_blacklist=%s); "
        "abuseipdb_live_check=%s (min_score=%s)",
        lookup_active,
        abuse_bl,
        crowd_lu,
        check_enabled,
        check_min,
    )
    sync_bits = []
    if abuseipdb_service.abuseipdb_master_enabled():
        sync_bits.append(
            "abuseipdb_sync="
            + str(abuseipdb_service.abuseipdb_blacklist_sync_enabled())
        )
    if crowdsec_blocklist_service.crowdsec_blocklist_master_enabled():
        sync_bits.append(
            "crowdsec_sync="
            + str(crowdsec_blocklist_service.crowdsec_blocklist_sync_enabled())
        )
    if sync_bits:
        logger.info("[IP reputation] Scheduled blocklist refresh: %s", ", ".join(sync_bits))


def invalidate_ip_reputation_env_snapshot() -> None:
    """Clear snapshot (e.g. pytest monkeypatch or reload). Next access re-reads env."""
    global _IP_REPUTATION_SNAPSHOT
    _IP_REPUTATION_SNAPSHOT = None


def should_skip_ip_reputation_middleware() -> bool:
    """
    True when neither AbuseIPDB nor CrowdSec blacklist path applies (skip middleware work).

    Mirrors: not abuseipdb_master and not crowdsec_blocklist_lookup_enabled.
    """
    if _IP_REPUTATION_SNAPSHOT is not None:
        abuse_master, crowd_lu, _, _, _ = _IP_REPUTATION_SNAPSHOT
        return not abuse_master and not crowd_lu
    from services.infrastructure.security import abuseipdb_service
    from services.infrastructure.security import crowdsec_blocklist_service

    return (
        not abuseipdb_service.abuseipdb_master_enabled()
        and not crowdsec_blocklist_service.crowdsec_blocklist_lookup_enabled()
    )


def blacklist_lookup_active() -> bool:
    """True if shared Redis blacklist lookup should run."""
    if _IP_REPUTATION_SNAPSHOT is not None:
        return _IP_REPUTATION_SNAPSHOT[2]
    from services.infrastructure.security import abuseipdb_service
    from services.infrastructure.security import crowdsec_blocklist_service

    abuse = (
        abuseipdb_service.abuseipdb_master_enabled()
        and abuseipdb_service.abuseipdb_blacklist_lookup_enabled()
    )
    crowd = crowdsec_blocklist_service.crowdsec_blocklist_lookup_enabled()
    return abuse or crowd


def abuseipdb_check_enabled_cached() -> bool:
    if _IP_REPUTATION_SNAPSHOT is not None:
        return _IP_REPUTATION_SNAPSHOT[3]
    from services.infrastructure.security import abuseipdb_service

    return abuseipdb_service.abuseipdb_check_enabled()


def get_check_min_score_cached() -> int:
    if _IP_REPUTATION_SNAPSHOT is not None:
        return _IP_REPUTATION_SNAPSHOT[4]
    from services.infrastructure.security import abuseipdb_service

    return abuseipdb_service.get_check_min_score()
