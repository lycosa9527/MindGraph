"""Unit tests for the offline Wan image studio client."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PIL import Image

from services.t2i import wan_image_env, wan_image_studio
from services.t2i.wan_image_client import extract_image_urls_from_task_output


def test_load_env_value_reads_key(tmp_path: Path) -> None:
    """Parse a KEY=value line and ignore comments."""
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nDASHSCOPE_API_KEY=abc123\n", encoding="utf-8")
    with patch.object(wan_image_env, "ENV_PATH", env_file):
        assert wan_image_env.load_env_value("DASHSCOPE_API_KEY") == "abc123"
        assert wan_image_env.load_env_value("MISSING") == ""


def test_jpeg_data_url_resizes_wide_still(tmp_path: Path) -> None:
    """Wide stills shrink to max_w and return a JPEG data URL."""
    src = tmp_path / "cat.png"
    Image.new("RGB", (2048, 512), (10, 20, 30)).save(src)
    work = tmp_path / "work"
    payload = wan_image_studio.jpeg_data_url(src, max_w=1024, work_dir=work)
    assert payload.startswith("data:image/jpeg;base64,")
    ref = work / "ref-cat.jpg"
    assert ref.is_file()
    with Image.open(ref) as saved:
        assert saved.size == (1024, 256)


def test_extract_image_urls_from_task_output() -> None:
    """Reuse the service helper for studio poll results."""
    output = {
        "choices": [
            {"message": {"content": [{"type": "image", "image": "https://ex/a.png"}]}},
            {"message": {"content": [{"image": "https://ex/b.png"}]}},
        ]
    }
    assert extract_image_urls_from_task_output(output) == [
        "https://ex/a.png",
        "https://ex/b.png",
    ]
