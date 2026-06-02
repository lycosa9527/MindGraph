"""FastAPI helpers to set request.state.rls_context before get_async_db runs."""

from __future__ import annotations

from fastapi import Path, Request

from utils.db.rls_context import RlsContext


def bind_public_org_list_rls(request: Request) -> None:
    request.state.rls_context = RlsContext.for_public_org_list()


def bind_dashboard_rls(request: Request) -> None:
    request.state.rls_context = RlsContext.for_dashboard()


def bind_authenticated_rls(
    request: Request,
    *,
    allow_global_channels: bool = False,
) -> None:
    user = getattr(request.state, "auth_context_user", None)
    if user is not None:
        request.state.rls_context = RlsContext.from_user(
            user,
            allow_global_channels=allow_global_channels,
        )


def bind_panel_superadmin_rls(request: Request, user) -> None:
    request.state.rls_context = RlsContext.panel_superadmin(user)


def bind_mindbot_callback_rls(request: Request, *, organization_id: int, callback_token: str) -> None:
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
