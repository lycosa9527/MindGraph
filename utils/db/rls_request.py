"""
FastAPI helpers to set request.state.rls_context before get_async_db runs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from fastapi import Path, Request

from utils.db.rls_context import RlsContext, set_rls_context


def bind_public_org_list_rls(request: Request) -> None:
    """Bind public org list rls."""
    request.state.rls_context = RlsContext.for_public_org_list()


def bind_dashboard_rls(request: Request) -> None:
    """Bind dashboard rls."""
    request.state.rls_context = RlsContext.for_dashboard()


def bind_authenticated_rls(
    request: Request,
    *,
    allow_global_channels: bool = False,
) -> None:
    """Bind authenticated rls."""
    user = getattr(request.state, "auth_context_user", None)
    if user is not None:
        request.state.rls_context = RlsContext.from_user(
            user,
            allow_global_channels=allow_global_channels,
        )


def bind_panel_superadmin_rls(request: Request, user) -> None:
    """Bind panel superadmin rls."""
    ctx = RlsContext.panel_superadmin(user)
    request.state.rls_context = ctx
    set_rls_context(ctx)


def bind_mindbot_callback_rls(request: Request, *, organization_id: int, callback_token: str) -> None:
    """Bind mindbot callback rls."""
    request.state.rls_context = RlsContext.for_mindbot_service(
        organization_id=organization_id,
        callback_token=callback_token,
    )


def bind_system_bootstrap_rls(request: Request) -> None:
    """Celery-style maintenance, device register/status, and other system paths."""
    request.state.rls_context = RlsContext.system_bootstrap()


def bind_system_bootstrap_rls_dependency(request: Request) -> None:
    """FastAPI dependency — declare before ``Depends(get_async_db)``."""
    bind_system_bootstrap_rls(request)


def bind_public_org_list_rls_dependency(request: Request) -> None:
    """Registration org dropdown — declare before ``Depends(get_async_db)``."""
    bind_public_org_list_rls(request)


def bind_dashboard_rls_dependency(request: Request) -> None:
    """Public dashboard passkey stats — declare before ``Depends(get_async_db)``."""
    bind_dashboard_rls(request)


def bind_mindbot_callback_rls_from_path_dependency(
    request: Request,
    public_callback_token: str = Path(..., min_length=8, max_length=64),
) -> None:
    """MindBot token route — set mindbot_service RLS before ``Depends(get_async_db)``."""
    token = public_callback_token.strip()
    bind_mindbot_callback_rls(
        request,
        organization_id=0,
        callback_token=token,
    )
