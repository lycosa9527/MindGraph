"""ZhiHui media storage: private COS or local disk fallback."""

from services.zhihui.storage.backend import (
    STORAGE_COS,
    STORAGE_LOCAL,
    aiter_bytes,
    cos_zhihui_enabled,
    create_presigned_get,
    delete_key,
    get_bytes,
    put_bytes,
    storage_backend,
)
from services.zhihui.storage.keys import (
    LANDING_SEED_FILENAMES,
    LOGICAL_PREFIX,
    SEEDS_PREFIX,
    build_generation_key,
    build_seed_key,
    full_cos_key,
    is_zhihui_generation_key,
    is_zhihui_logical_key,
    is_zhihui_seed_key,
    resolve_local_safe,
    zhihui_public_asset_url,
)

__all__ = [
    "LANDING_SEED_FILENAMES",
    "LOGICAL_PREFIX",
    "SEEDS_PREFIX",
    "STORAGE_COS",
    "STORAGE_LOCAL",
    "aiter_bytes",
    "build_generation_key",
    "build_seed_key",
    "cos_zhihui_enabled",
    "create_presigned_get",
    "delete_key",
    "full_cos_key",
    "get_bytes",
    "is_zhihui_generation_key",
    "is_zhihui_logical_key",
    "is_zhihui_seed_key",
    "put_bytes",
    "resolve_local_safe",
    "storage_backend",
    "zhihui_public_asset_url",
]
