"""Inbound mutation ack completion (no Kitty imports).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict

from services.diagram_edit.pending import MutationAckPayload, complete_pending


def complete_mutation_ack_from_client(payload: Dict[str, Any]) -> bool:
    """Complete pending future from inbound WS ``diagram_mutation_ack``."""
    mutation_id = payload.get("mutation_id")
    if not isinstance(mutation_id, str) or not mutation_id.strip():
        return False

    verified = payload.get("verified") is True or payload.get("ok") is True
    rev_raw = payload.get("revision")
    revision = rev_raw if isinstance(rev_raw, int) else None
    hub_rev_raw = payload.get("hub_revision")
    hub_revision = hub_rev_raw if isinstance(hub_rev_raw, int) else None
    hub_persist_raw = payload.get("hub_persist_ok")
    hub_persist_ok = hub_persist_raw if isinstance(hub_persist_raw, bool) else None
    evidence = payload.get("evidence")
    evidence_dict = evidence if isinstance(evidence, dict) else None
    created_raw = payload.get("created_node_ids")
    created_node_ids: list[str] | None = None
    if isinstance(created_raw, list):
        parsed = [item.strip() for item in created_raw if isinstance(item, str) and item.strip()]
        if parsed:
            created_node_ids = parsed

    ack = MutationAckPayload(
        mutation_id=mutation_id.strip(),
        verified=verified,
        revision=revision,
        hub_revision=hub_revision,
        hub_persist_ok=hub_persist_ok,
        error_code=str(payload.get("error_code") or "") or None,
        message=str(payload.get("message") or payload.get("error") or "") or None,
        evidence=evidence_dict,
        created_node_ids=created_node_ids,
    )
    return complete_pending(ack)
