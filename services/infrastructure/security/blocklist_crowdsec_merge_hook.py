"""Post-AbuseIPDB-sync CrowdSec merge hook (breaks abuseipdb↔crowdsec lazy import).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict

from services.infrastructure.security.crowdsec_blocklist_service import (
    apply_crowdsec_baseline_from_file_async,
    merge_crowdsec_blocklist_from_network,
)


async def merge_crowdsec_after_abuseipdb_sync(*, force: bool = False) -> Dict[str, Any]:
    """Merge CrowdSec blocklist into shared Redis set after AbuseIPDB sync."""
    result = await merge_crowdsec_blocklist_from_network(force=force)
    crowdsec_baseline = await apply_crowdsec_baseline_from_file_async()
    if crowdsec_baseline:
        result["baseline_merged"] = crowdsec_baseline
    return result
