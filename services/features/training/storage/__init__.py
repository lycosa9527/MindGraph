"""Per-course COS folder for 校本培训 media."""

from services.features.training.storage.backend import (
    cos_training_enabled,
    create_presigned_get,
    create_presigned_put,
    delete_course_prefix,
    get_bytes_sync,
    head_object_sync,
    put_bytes_sync,
    storage_backend,
)
from services.features.training.storage.keys import (
    ASSET_ROLES,
    build_object_key,
    course_folder,
    course_id_from_key,
    is_scoped_course_object_key,
    is_training_logical_key,
    training_public_asset_url,
)

__all__ = [
    "ASSET_ROLES",
    "build_object_key",
    "cos_training_enabled",
    "course_folder",
    "course_id_from_key",
    "create_presigned_get",
    "create_presigned_put",
    "delete_course_prefix",
    "get_bytes_sync",
    "head_object_sync",
    "is_scoped_course_object_key",
    "is_training_logical_key",
    "put_bytes_sync",
    "storage_backend",
    "training_public_asset_url",
]
