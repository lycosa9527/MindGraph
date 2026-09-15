"""Disk locations for MindMate teaching-design Word templates."""

from pathlib import Path

BUNDLED_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2] / "assets" / "templates" / "bnu_thinking_classroom_design.docx"
)
OVERRIDE_FILENAME = "teaching_design.docx"
OVERRIDE_META_FILENAME = "teaching_design.meta.json"
CATALOG_FILENAME = "teaching_design_catalog.json"
CATALOG_FILES_DIRNAME = "teaching_design_files"
TEMPLATE_KEY_SYSTEM = "system"
TEMPLATE_KEY_BUNDLED = "bundled"
TEMPLATE_KEY_UPLOADED = "uploaded"
TEMPLATE_ID_PREFIX = "td_"
MAX_TEMPLATE_BYTES = 10 * 1024 * 1024
MAX_TEMPLATE_NAME_LEN = 80
MAX_CATALOG_TEMPLATES = 50
DOCX_MAGIC = b"PK"


def project_root() -> Path:
    """Repository root (services/mindmate → repo)."""
    return Path(__file__).resolve().parents[2]


def override_dir() -> Path:
    """Runtime directory for uploaded templates (gitignored)."""
    return project_root() / "storage" / "templates"


def override_docx_path() -> Path:
    """Legacy single-file override from the first template admin."""
    return override_dir() / OVERRIDE_FILENAME


def override_meta_path() -> Path:
    """Sidecar JSON for the legacy single-file override."""
    return override_dir() / OVERRIDE_META_FILENAME


def catalog_path() -> Path:
    """JSON catalog of named uploaded templates."""
    return override_dir() / CATALOG_FILENAME


def catalog_files_dir() -> Path:
    """Directory that holds one .docx per uploaded catalog row."""
    return override_dir() / CATALOG_FILES_DIRNAME
