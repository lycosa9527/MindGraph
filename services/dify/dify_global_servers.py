"""
Global Dify main and backup credentials from the environment.

Slot 1 (school 主服务器) is Dify main: ``DIFY_API_URL`` / ``DIFY_API_KEY``.
Slot 2 (school 备用服务器) is Dify backup: ``DIFY_BACKUP_API_URL`` / ``DIFY_BACKUP_API_KEY``.
Both servers run the same workflow; the app sends the school name.

A school override replaces that slot. A blank slot uses the matching env pair
only when the backup pair is set. A school that already has its own two servers
keeps that pair.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
from typing import List, Optional

from models.domain.auth import Organization
from services.dify.dify_servers import (
    DifyServerCreds,
    FAILOVER_CONFIGURED_SERVER_COUNT,
    configured_dify_servers,
    partner_for_configured_slots,
    primary_server_no,
)

_MAIN_URL_ENV = "DIFY_API_URL"
_MAIN_KEY_ENV = "DIFY_API_KEY"
_BACKUP_URL_ENV = "DIFY_BACKUP_API_URL"
_BACKUP_KEY_ENV = "DIFY_BACKUP_API_KEY"
_DEFAULT_MAIN_URL = "https://api.dify.ai/v1"
_SCHOOL_ENV_SLOTS = (1, 2)


def global_dify_main_url() -> str:
    """Dify main base URL, or the public default when ``DIFY_API_URL`` is unset."""
    return (os.getenv(_MAIN_URL_ENV) or _DEFAULT_MAIN_URL).strip()


def _env_pair(url_name: str, key_name: str, *, default_url: str = "") -> Optional[tuple[str, str]]:
    """Return ``(api_key, api_url)`` when both are set."""
    api_key = (os.getenv(key_name) or "").strip()
    api_url = (os.getenv(url_name) or default_url).strip()
    if api_key and api_url:
        return api_key, api_url
    return None


def global_dify_slot_credentials(server: int) -> Optional[tuple[str, str]]:
    """
    Env credentials for one school slot.

    Slot 1 is 主服务器 (Dify main). Slot 2 is 备用服务器 (Dify backup). Other slots have no env pair.
    """
    if server == 1:
        return _env_pair(_MAIN_URL_ENV, _MAIN_KEY_ENV, default_url=global_dify_main_url())
    if server == 2:
        return _env_pair(_BACKUP_URL_ENV, _BACKUP_KEY_ENV)
    return None


def global_dify_backup_configured() -> bool:
    """True when the Dify backup URL and key are both set."""
    return global_dify_slot_credentials(2) is not None


def global_dify_pair_ready() -> bool:
    """True when both Dify main and Dify backup env pairs are set."""
    return global_dify_slot_credentials(1) is not None and global_dify_backup_configured()


def global_dify_servers() -> List[DifyServerCreds]:
    """Configured global servers, main as slot 1 and backup as slot 2."""
    out: List[DifyServerCreds] = []
    for server in _SCHOOL_ENV_SLOTS:
        creds = global_dify_slot_credentials(server)
        if creds is None:
            continue
        api_key, api_url = creds
        out.append(DifyServerCreds(server=server, api_key=api_key, api_url=api_url))
    return out


def effective_configured_dify_servers(org: Organization) -> List[DifyServerCreds]:
    """
    School servers, with a blank 主服务器 / 备用服务器 filled from the env pair.

    Filling runs only when Dify backup is configured. A school that already has
    two servers keeps those credentials.
    """
    own = configured_dify_servers(org)
    if not global_dify_backup_configured():
        return own
    if len(own) >= FAILOVER_CONFIGURED_SERVER_COUNT:
        return own
    if len(own) == 1 and own[0].server not in _SCHOOL_ENV_SLOTS:
        return own

    present = {entry.server for entry in own}
    filled = list(own)
    for server in _SCHOOL_ENV_SLOTS:
        if server in present:
            continue
        creds = global_dify_slot_credentials(server)
        if creds is None:
            continue
        api_key, api_url = creds
        filled.append(DifyServerCreds(server=server, api_key=api_key, api_url=api_url))
    filled.sort(key=lambda entry: entry.server)
    return filled


def effective_server_credentials(org: Organization, server: int) -> Optional[tuple[str, str]]:
    """``(api_key, api_url)`` for *server* after school override and env fill-in."""
    for entry in effective_configured_dify_servers(org):
        if entry.server == server:
            return entry.api_key, entry.api_url
    return None


def effective_failover_partner_server(org: Organization) -> Optional[int]:
    """Failover partner after env fill-in for a blank 主服务器 or 备用服务器."""
    primary = primary_server_no(org)
    slots = [entry.server for entry in effective_configured_dify_servers(org)]
    return partner_for_configured_slots(primary, slots)
