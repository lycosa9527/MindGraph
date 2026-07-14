"""
Router Registration Module

Centralized router registration for all FastAPI routes.
Feature routers are always mounted when importable; ``feature_flag_gate`` and
per-route checks enforce ``FEATURE_*`` at runtime (supports hot on/off).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import importlib
import logging

from fastapi import FastAPI

from config.settings import config
from routers import (
    api,
    auth,
    concept_map_focus,
    inline_recommendations,
    mindmap_node_explain,
    node_palette,
    public_dashboard,
    relationship_labels,
)
from routers.admin import cos_router as admin_cos
from routers.admin import database_router as admin_database
from routers.admin import env_router as admin_env
from routers.admin import logs_router as admin_logs
from routers.admin import realtime_router as admin_realtime
from routers.core import changelog, pages, update_notification
from routers.core.health import router as health_router
from routers.core.vue_spa import router as vue_spa
from routers.features.askonce import router as askonce
from routers.features.kitty import router as kitty
from services.mcp.mount import mount_mindgraph_mcp
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


def _try_import_module(module_path: str, label: str):
    """Import a feature module; return None on failure."""
    try:
        return importlib.import_module(module_path)
    except (ImportError, ModuleNotFoundError, AttributeError, TypeError) as exc:
        logger.debug(
            "[RouterRegistration] Failed to import %s (%s): %s",
            label,
            module_path,
            exc,
            exc_info=True,
        )
        return None


LIBRARY_MODULE = _try_import_module("routers.features.library", "library")
DEBATEVERSE_MODULE = _try_import_module("routers.features.debateverse", "debateverse")

_community_mod = _try_import_module("routers.features.community", "community")
COMMUNITY_MODULE = getattr(_community_mod, "router", None) if _community_mod else None

_showcase_mod = _try_import_module("routers.features.showcase", "showcase")
SHOWCASE_MODULE = getattr(_showcase_mod, "router", None) if _showcase_mod else None

_gewe_mod = _try_import_module("routers.features.gewe", "gewe")
GEWE_MODULE = getattr(_gewe_mod, "router", None) if _gewe_mod else None

_wc_mod = _try_import_module("routers.features.workshop_chat", "workshop_chat")
_wc_ws_mod = _try_import_module("routers.features.workshop_chat.ws", "workshop_chat_ws")
WORKSHOP_CHAT_MODULE = getattr(_wc_mod, "router", None) if _wc_mod else None
WORKSHOP_CHAT_WS_MODULE = getattr(_wc_ws_mod, "router", None) if _wc_ws_mod else None
if _wc_mod is None or _wc_ws_mod is None:
    logger.warning(
        "[RouterRegistration] Workshop Chat routers incomplete — "
        "/api/chat/* or /api/ws/chat may be unavailable until import errors are fixed."
    )

MARKETS_MODULE = _try_import_module("routers.features.markets", "markets")


def _mount_feature(app: FastAPI, router_obj, path_label: str, registered: list[str]) -> None:
    """Include a feature router when present and record its API prefix."""
    if router_obj is None:
        logger.warning(
            "[RouterRegistration] %s router NOT registered - import failed or router is None.",
            path_label,
        )
        return
    app.include_router(router_obj)
    registered.append(path_label)


def register_routers(app: FastAPI) -> None:
    """
    Register all FastAPI routers in the correct order.

    Router registration order is critical:
    1. Health check endpoints (no prefix)
    2. Core API routes (must be before vue_spa catch-all)
    3. Feature routers (must be before vue_spa)
    4. Admin routers (must be before vue_spa)
    5. Remaining feature routers with API endpoints (before vue_spa)
    6. Vue SPA catch-all route (MUST be last)

    Args:
        app: FastAPI application instance
    """
    app.include_router(health_router)

    app.include_router(changelog.router, prefix="/api")

    app.include_router(pages)
    app.include_router(api.router)

    if config.FEATURE_MCP_HTTP:
        try:
            mount_mindgraph_mcp(app)
            logger.info("[RouterRegistration] MCP Streamable HTTP mounted at /api/mcp")
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning(
                "[RouterRegistration] MCP mount failed (FEATURE_MCP_HTTP=True): %s",
                exc,
                exc_info=True,
            )

    app.include_router(node_palette.router)
    app.include_router(relationship_labels.router)
    app.include_router(inline_recommendations.router)
    app.include_router(mindmap_node_explain.router)
    app.include_router(
        concept_map_focus.router,
        prefix="/api",
    )
    app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])

    registered_feature_paths: list[str] = []

    if LIBRARY_MODULE is not None:
        _mount_feature(app, LIBRARY_MODULE.router, "/api/library", registered_feature_paths)
    else:
        logger.warning(
            "[RouterRegistration] Library router NOT registered - import failed or router is None."
        )

    _mount_feature(app, COMMUNITY_MODULE, "/api/community", registered_feature_paths)
    _mount_feature(app, SHOWCASE_MODULE, "/api/showcase", registered_feature_paths)

    if MARKETS_MODULE is not None:
        _mount_feature(app, MARKETS_MODULE.router, "/api/markets", registered_feature_paths)
    else:
        logger.warning(
            "[RouterRegistration] Markets router NOT registered - import failed or router is None."
        )

    _mount_feature(app, GEWE_MODULE, "/api/gewe", registered_feature_paths)
    _mount_feature(app, WORKSHOP_CHAT_MODULE, "/api/chat", registered_feature_paths)

    app.include_router(admin_env)
    app.include_router(admin_logs)
    app.include_router(admin_realtime)
    app.include_router(admin_database)
    app.include_router(admin_cos)

    kitty_routes = importlib.import_module("routers.features.kitty.routes")
    logger.debug(
        "[RouterRegistration] Kitty Agent routes registered via %s",
        kitty_routes.__name__,
    )
    app.include_router(kitty)
    app.include_router(update_notification)
    app.include_router(public_dashboard.router, prefix="/api/public", tags=["Public Dashboard"])
    app.include_router(askonce)

    _mount_feature(app, WORKSHOP_CHAT_WS_MODULE, "/api/ws/chat", registered_feature_paths)

    if DEBATEVERSE_MODULE is not None:
        _mount_feature(app, DEBATEVERSE_MODULE.router, "/api/debateverse", registered_feature_paths)
    else:
        logger.warning(
            "[RouterRegistration] DebateVerse router NOT registered - import failed or router is None."
        )

    if registered_feature_paths:
        logger.info(
            "[RouterRegistration] Feature API prefixes: %s",
            ", ".join(registered_feature_paths),
        )

    app.include_router(vue_spa)
