"""Consume bind token and upsert dingtalk_staff_links."""

from __future__ import annotations

from services.auth.dingtalk_bind_service import claim_dingtalk_qr_bind

__all__ = ["claim_bind_token_for_staff"]


async def claim_bind_token_for_staff(
    *,
    token: str,
    bind_code: str,
    organization_id: int,
    dingtalk_staff_id: str,
) -> tuple[bool, str]:
    """Backward-compatible alias; prefer :func:`claim_dingtalk_qr_bind`."""
    return await claim_dingtalk_qr_bind(
        token=token,
        bind_code=bind_code,
        organization_id=organization_id,
        dingtalk_staff_id=dingtalk_staff_id,
        linked_via="qr_bind",
    )
