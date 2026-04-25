"""Structured logging helpers for the school dashboard (admin + manager).

Mirrors :mod:`services.mindbot.telemetry.pipeline_log`: a :class:`logging.LoggerAdapter`
injects stable ``sd_*`` keys into every record's ``extra`` so JSON log formatters can
index and alert without regex-parsing the message.

Fields (on ``LogRecord`` when using the adapter or ``school_dashboard_extra``):

- ``sd_event`` – stable event name (required on each call via ``extra=``)
- ``sd_actor_id`` – authenticated user performing the action
- ``sd_org_id`` – organization scope for the request
- ``sd_target_user_id`` – subject user when applicable

Additional keys may be passed per log line via ``extra=`` (e.g. ``sd_page``,
``sd_error_type``). All custom keys should use the ``sd_`` prefix to avoid
clashing with :class:`logging.LogRecord` attributes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, MutableMapping


class SchoolDashboardLogAdapter(logging.LoggerAdapter):
    """Inject school-dashboard scope into log records for structured backends."""

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        extra = dict(self.extra or {})
        existing = kwargs.get("extra") or {}
        extra.update(existing)
        kwargs["extra"] = extra
        return msg, kwargs


def get_school_dashboard_logger(
    base_logger: logging.Logger,
    *,
    actor_id: int | str = "",
    org_id: int | str = "",
    target_user_id: int | str = "",
) -> SchoolDashboardLogAdapter:
    """Return an adapter with default ``sd_actor_id``, ``sd_org_id``, ``sd_target_user_id``."""
    return SchoolDashboardLogAdapter(
        base_logger,
        {
            "sd_actor_id": actor_id if actor_id != "" else "",
            "sd_org_id": org_id if org_id != "" else "",
            "sd_target_user_id": target_user_id if target_user_id != "" else "",
        },
    )


def school_dashboard_extra(
    *,
    event: str,
    actor_id: int | str = "",
    org_id: int | str = "",
    target_user_id: int | str = "",
    **more: Any,
) -> dict[str, Any]:
    """Build a single ``extra`` dict for one-off logs (no adapter)."""
    payload: dict[str, Any] = {
        "sd_event": event,
        "sd_actor_id": actor_id if actor_id != "" else "",
        "sd_org_id": org_id if org_id != "" else "",
        "sd_target_user_id": target_user_id if target_user_id != "" else "",
    }
    for key, val in more.items():
        payload[key] = val
    return payload
