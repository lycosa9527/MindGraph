"""WorkBuddy skill zip embeds filled account.json and .env."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

from services.auth.workbuddy_skill_bundle import (
    ACCOUNT_JSON_NAME,
    DOTENV_NAME,
    build_account_json_text,
    build_skill_dotenv_text,
    zip_skill_directory,
)

_REPO_ACCOUNT = Path(__file__).resolve().parents[1] / "openclaw" / "skills" / "mindgraph" / "account.json"


def test_repo_account_json_is_placeholder() -> None:
    """Git copy must not ship a real mgat_ secret."""
    payload = json.loads(_REPO_ACCOUNT.read_text(encoding="utf-8"))
    token = payload["MINDGRAPH_TOKEN"]
    assert token.startswith("mgat_")
    assert "paste_token" in token


def test_build_account_json_has_flat_and_env_keys() -> None:
    """Agent can read top-level keys or skills.entries.env."""
    text = build_account_json_text(
        "https://test.mindspringedu.com/",
        "17801353751",
        "mgat_unit_test_token",
    )
    payload = json.loads(text)
    assert payload["MINDGRAPH_BASE_URL"] == "https://test.mindspringedu.com"
    assert payload["MINDGRAPH_ACCOUNT"] == "17801353751"
    assert payload["MINDGRAPH_TOKEN"] == "mgat_unit_test_token"
    env = payload["skills"]["entries"]["mindgraph"]["env"]
    assert env["MINDGRAPH_TOKEN"] == "mgat_unit_test_token"


def test_build_skill_dotenv_has_three_keys() -> None:
    """Skill-folder .env uses the same three keys."""
    text = build_skill_dotenv_text("https://example.test/", "13800000000", "mgat_filled")
    assert "MINDGRAPH_BASE_URL=https://example.test\n" in text
    assert "MINDGRAPH_ACCOUNT=13800000000\n" in text
    assert "MINDGRAPH_TOKEN=mgat_filled\n" in text


def test_zip_skill_writes_account_json_and_dotenv(tmp_path: Path) -> None:
    """Zip keeps SKILL.md and writes generated account.json plus .env."""
    (tmp_path / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (tmp_path / ACCOUNT_JSON_NAME).write_text('{"MINDGRAPH_TOKEN":"mgat_placeholder"}\n')
    (tmp_path / "demo.json").write_text("{}\n", encoding="utf-8")
    raw = zip_skill_directory(
        tmp_path,
        "mindgraph",
        "https://example.test",
        "13800000000",
        "mgat_filled",
    )
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "mindgraph/SKILL.md" in names
        assert f"mindgraph/{ACCOUNT_JSON_NAME}" in names
        assert f"mindgraph/{DOTENV_NAME}" in names
        assert "mindgraph/demo.json" not in names
        payload = json.loads(zf.read("mindgraph/account.json"))
        dotenv = zf.read("mindgraph/.env").decode("utf-8")
    assert payload["MINDGRAPH_TOKEN"] == "mgat_filled"
    assert payload["MINDGRAPH_ACCOUNT"] == "13800000000"
    assert "MINDGRAPH_TOKEN=mgat_filled" in dotenv
