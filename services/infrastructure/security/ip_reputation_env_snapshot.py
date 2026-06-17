"""
Process-lifetime snapshot of IP reputation env flags (read once after Redis init).

Avoids repeated os.getenv / branching on the hot middleware path. Tests should reset
via invalidate_ip_reputation_env_snapshot() when monkeypatching related env vars.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from services.infrastructure.security import ip_reputation_env_flags

logger = logging.getLogger(__name__)


class _IpReputationSnapshotState:
    """Process-lifetime IP reputation env snapshot holder."""

    value: Optional[Tuple[bool, bool, bool, bool, int]] = None


def _read_snapshot_tuple() -> Tuple[bool, bool, bool, bool, int]:
    """Read snapshot tuple."""
    abuse_master = ip_reputation_env_flags.abuseipdb_master_enabled()
    crowd_lu = ip_reputation_env_flags.crowdsec_blocklist_lookup_enabled()
    lookup_active = (abuse_master and ip_reputation_env_flags.abuseipdb_blacklist_lookup_enabled()) or crowd_lu
    check_enabled = ip_reputation_env_flags.abuseipdb_check_enabled()
    check_min = ip_reputation_env_flags.get_check_min_score()
    return abuse_master, crowd_lu, lookup_active, check_enabled, check_min


def warm_ip_reputation_env_snapshot() -> None:
    """Read AbuseIPDB/CrowdSec flags once; call from application lifespan after Redis init."""
    _IpReputationSnapshotState.value = _read_snapshot_tuple()


def log_ip_reputation_startup_summary() -> None:
    """
    Log once after warm_ip_reputation_env_snapshot() so operators see how vetting is configured.
    """
    if _IpReputationSnapshotState.value is None:
        warm_ip_reputation_env_snapshot()
    abuse_master, crowd_lu, lookup_active, check_enabled, check_min = _IpReputationSnapshotState.value or (
        False,
        False,
        False,
        False,
        80,
    )

    abuse_bl = bool(abuse_master) and ip_reputation_env_flags.abuseipdb_blacklist_lookup_enabled()
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
    if ip_reputation_env_flags.abuseipdb_master_enabled():
        sync_bits.append("abuseipdb_sync=" + str(ip_reputation_env_flags.abuseipdb_blacklist_sync_enabled()))
    if ip_reputation_env_flags.crowdsec_blocklist_master_enabled():
        sync_bits.append("crowdsec_sync=" + str(ip_reputation_env_flags.crowdsec_blocklist_sync_enabled()))
    if sync_bits:
        logger.info("[IP reputation] Scheduled blocklist refresh: %s", ", ".join(sync_bits))


def invalidate_ip_reputation_env_snapshot() -> None:
    """Clear snapshot (e.g. pytest monkeypatch or reload). Next access re-reads env."""
    _IpReputationSnapshotState.value = None


def should_skip_ip_reputation_middleware() -> bool:
    """
    True when neither AbuseIPDB nor CrowdSec blacklist path applies (skip middleware work).

    Mirrors: not abuseipdb_master and not crowdsec_blocklist_lookup_enabled.
    """
    if _IpReputationSnapshotState.value is not None:
        abuse_master, crowd_lu, _, _, _ = _IpReputationSnapshotState.value
        return not abuse_master and not crowd_lu
    return (
        not ip_reputation_env_flags.abuseipdb_master_enabled()
        and not ip_reputation_env_flags.crowdsec_blocklist_lookup_enabled()
    )


def blacklist_lookup_active() -> bool:
    """True if shared Redis blacklist lookup should run."""
    if _IpReputationSnapshotState.value is not None:
        return _IpReputationSnapshotState.value[2]
    abuse = (
        ip_reputation_env_flags.abuseipdb_master_enabled()
        and ip_reputation_env_flags.abuseipdb_blacklist_lookup_enabled()
    )
    crowd = ip_reputation_env_flags.crowdsec_blocklist_lookup_enabled()
    return abuse or crowd


def abuseipdb_check_enabled_cached() -> bool:
    """Abuseipdb check enabled cached."""
    if _IpReputationSnapshotState.value is not None:
        return _IpReputationSnapshotState.value[3]
    return ip_reputation_env_flags.abuseipdb_check_enabled()


def get_check_min_score_cached() -> int:
    """Get check min score cached."""
    if _IpReputationSnapshotState.value is not None:
        return _IpReputationSnapshotState.value[4]
    return ip_reputation_env_flags.get_check_min_score()
