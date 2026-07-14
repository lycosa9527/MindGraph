"""Compatibility shim — prefer ``services.showcase.uploads.roles``."""

from services.showcase.uploads.roles import (
    CONTENT_TYPES,
    UploadRoleSpec,
    assert_content_type_allowed,
    resolve_upload_role,
    suffix_from_filename,
)

__all__ = [
    "CONTENT_TYPES",
    "UploadRoleSpec",
    "assert_content_type_allowed",
    "resolve_upload_role",
    "suffix_from_filename",
]
