"""Showcase media storage: private COS (presigned) or local disk fallback.

Public API re-exports for ``from services.showcase.storage import …``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from services.showcase.storage.backend import (
    STORAGE_COS,
    STORAGE_LOCAL,
    cos_showcase_enabled,
    create_presigned_get,
    create_presigned_put,
    delete_key,
    delete_key_sync,
    delete_keys,
    delete_keys_sync,
    delete_post_assets,
    delete_post_prefix,
    delete_post_prefix_sync,
    get_bytes,
    get_bytes_sync,
    head_object_async,
    head_object_sync,
    put_bytes,
    put_bytes_sync,
    storage_backend,
)
from services.showcase.storage.keys import (
    LEGACY_LOGICAL_PREFIX,
    LOGICAL_PREFIX,
    build_object_key,
    collect_keys_from_post,
    full_cos_key,
    is_scoped_post_object_key,
    is_showcase_logical_key,
    local_path_for_key,
    logical_key_from_full_cos_key,
    resolve_local_safe,
    showcase_local_root,
    showcase_public_asset_url,
)

__all__ = [
    "LEGACY_LOGICAL_PREFIX",
    "LOGICAL_PREFIX",
    "STORAGE_COS",
    "STORAGE_LOCAL",
    "build_object_key",
    "collect_keys_from_post",
    "cos_showcase_enabled",
    "create_presigned_get",
    "create_presigned_put",
    "delete_key",
    "delete_key_sync",
    "delete_keys",
    "delete_keys_sync",
    "delete_post_assets",
    "delete_post_prefix",
    "delete_post_prefix_sync",
    "full_cos_key",
    "get_bytes",
    "get_bytes_sync",
    "head_object_async",
    "head_object_sync",
    "is_scoped_post_object_key",
    "is_showcase_logical_key",
    "local_path_for_key",
    "logical_key_from_full_cos_key",
    "put_bytes",
    "put_bytes_sync",
    "resolve_local_safe",
    "showcase_local_root",
    "showcase_public_asset_url",
    "storage_backend",
]
