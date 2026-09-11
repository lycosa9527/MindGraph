"""Dify Service API file-type rules used by MindMate upload and chat-messages.

Mirrors langgenius/dify ``api/factories/file_factory.py``:
``_standardize_file_type`` (extension first, then MIME) and default size limits
from ``POST /files/upload``. Chat-messages ``files[].type`` must match this
detected type or Dify returns ``invalid_param``.

``DOCUMENT_EXTENSIONS`` includes Dify's default set plus the Unstructured ETL
set (``.doc`` / ``.ppt`` / ``.pptx``) so MindMate analysis payloads stay
``document``.
"""

from pathlib import Path

_MB = 1024 * 1024

DIFY_IMAGE_MAX_BYTES = 10 * _MB
DIFY_DOCUMENT_MAX_BYTES = 15 * _MB
DIFY_AUDIO_MAX_BYTES = 50 * _MB
DIFY_VIDEO_MAX_BYTES = 100 * _MB

DIFY_IMAGE_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp", "gif", "svg"})
DIFY_VIDEO_EXTENSIONS = frozenset({"mp4", "mov", "mpeg", "webm"})
DIFY_AUDIO_EXTENSIONS = frozenset({"mp3", "m4a", "wav", "amr", "mpga"})
DIFY_DOCUMENT_EXTENSIONS = frozenset(
    {
        "txt",
        "markdown",
        "md",
        "mdx",
        "pdf",
        "html",
        "htm",
        "xlsx",
        "xls",
        "vtt",
        "properties",
        "doc",
        "docx",
        "csv",
        "eml",
        "msg",
        "ppt",
        "pptx",
        "xml",
        "epub",
        "odt",
    }
)

_GENERIC_MIME_TYPES = frozenset(
    {
        "",
        "application/octet-stream",
        "binary/octet-stream",
    }
)

_MIME_BY_EXTENSION = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "txt": "text/plain",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "mdx": "text/markdown",
    "pdf": "application/pdf",
    "html": "text/html",
    "htm": "text/html",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "csv": "text/csv",
    "xml": "application/xml",
    "epub": "application/epub+zip",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odt": "application/vnd.oasis.opendocument.text",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
    "amr": "audio/amr",
    "mpga": "audio/mpeg",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "mpeg": "video/mpeg",
    "mpg": "video/mpeg",
    "webm": "video/webm",
    "aac": "audio/aac",
}

DIFY_CHAT_FILE_TYPES = frozenset({"image", "document", "audio", "video", "custom"})

# Gateway allowlist: Dify category sets plus MIME-fallback extras we already accept.
DIFY_GATEWAY_UPLOAD_EXTENSIONS = frozenset(
    DIFY_IMAGE_EXTENSIONS | DIFY_VIDEO_EXTENSIONS | DIFY_AUDIO_EXTENSIONS | DIFY_DOCUMENT_EXTENSIONS | {"aac", "mpg"}
)

_TYPE_BY_EXTENSION_GROUP = (
    (DIFY_IMAGE_EXTENSIONS, "image"),
    (DIFY_VIDEO_EXTENSIONS, "video"),
    (DIFY_AUDIO_EXTENSIONS, "audio"),
    (DIFY_DOCUMENT_EXTENSIONS, "document"),
)

_MAX_BYTES_BY_EXTENSION_GROUP = (
    (DIFY_IMAGE_EXTENSIONS, DIFY_IMAGE_MAX_BYTES),
    (DIFY_VIDEO_EXTENSIONS, DIFY_VIDEO_MAX_BYTES),
    (DIFY_AUDIO_EXTENSIONS, DIFY_AUDIO_MAX_BYTES),
)


def file_extension(filename: str) -> str:
    """Return the lowercase extension without a leading dot."""
    return Path(filename).suffix.lower().lstrip(".")


def dify_upload_content_type(filename: str, declared_mime: str | None) -> str:
    """MIME type to send on ``POST /files/upload``.

    Dify stores the multipart part's Content-Type and later uses it as the MIME
    fallback for chat-messages type detection. Empty or generic types become
    the extension's canonical MIME.
    """
    declared = (declared_mime or "").strip().lower()
    if declared not in _GENERIC_MIME_TYPES:
        return declared
    inferred = _MIME_BY_EXTENSION.get(file_extension(filename))
    if inferred:
        return inferred
    return declared or "application/octet-stream"


def _dify_file_type_from_mime(mime_type: str) -> str:
    """Dify MIME fallback used when the extension is not in a known set."""
    mime = mime_type.lower()
    if "image" in mime:
        return "image"
    if "video" in mime:
        return "video"
    if "audio" in mime:
        return "audio"
    if "text" in mime or "pdf" in mime:
        return "document"
    return "custom"


def dify_chat_file_type(filename: str, mime_type: str = "") -> str:
    """Return Dify ``files[].type``: image, document, audio, video, or custom.

    Extension wins, then MIME (image / video / audio / text|pdf → document).
    """
    ext = file_extension(filename)
    for extensions, file_type in _TYPE_BY_EXTENSION_GROUP:
        if ext in extensions:
            return file_type
    return _dify_file_type_from_mime(mime_type)


def dify_upload_max_bytes(filename: str) -> int:
    """Dify default size cap for the file's category."""
    ext = file_extension(filename)
    for extensions, limit in _MAX_BYTES_BY_EXTENSION_GROUP:
        if ext in extensions:
            return limit
    return DIFY_DOCUMENT_MAX_BYTES
