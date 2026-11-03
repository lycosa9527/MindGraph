"""OSS backup mirror uploads beside COS and keeps its own retention."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.utils import aliyun_oss_client, backup_scheduler, oss_backup_store


def test_oss_object_key_uses_prefix(monkeypatch) -> None:
    """Local dumps land under the dev_roy/backups prefix."""
    monkeypatch.setenv("OSS_KEY_PREFIX", "dev_roy/backups")
    assert aliyun_oss_client.oss_object_key("mindgraph.postgresql.1.dump") == (
        "dev_roy/backups/mindgraph.postgresql.1.dump"
    )


def test_publish_backup_copies_runs_cos_and_oss(monkeypatch, tmp_path: Path) -> None:
    """One backup run publishes to COS and OSS independently."""
    calls: list[str] = []
    monkeypatch.setattr(
        backup_scheduler,
        "_upload_to_cos_if_enabled",
        lambda *_args, **_kwargs: calls.append("cos"),
    )
    monkeypatch.setattr(
        backup_scheduler,
        "upload_oss_backup_if_enabled",
        lambda *_args, **_kwargs: calls.append("oss"),
    )
    dump = tmp_path / "mindgraph.postgresql.1.dump"
    backup_scheduler.publish_backup_copies(dump, None)
    assert calls == ["cos", "oss"]


def test_oss_upload_skipped_when_disabled(monkeypatch, tmp_path: Path) -> None:
    """OSS_BACKUP_ENABLED=false does not upload."""
    monkeypatch.setenv("OSS_BACKUP_ENABLED", "false")
    uploaded: list[str] = []
    monkeypatch.setattr(
        oss_backup_store.aliyun_oss_client,
        "upload_file",
        lambda *_args, **_kwargs: uploaded.append("upload") or True,
    )
    dump = tmp_path / "mindgraph.postgresql.1.dump"
    dump.write_bytes(b"dump")
    oss_backup_store.upload_oss_backup_if_enabled(dump, None)
    assert not uploaded


def test_oss_upload_sends_dump_and_manifest(monkeypatch, tmp_path: Path) -> None:
    """The dump and its manifest are both stored under the OSS prefix."""
    monkeypatch.setenv("OSS_BACKUP_ENABLED", "true")
    monkeypatch.setenv("OSS_KEY_PREFIX", "dev_roy/backups")
    monkeypatch.setattr(oss_backup_store.aliyun_oss_client, "oss_credentials_configured", lambda: True)
    monkeypatch.setattr(oss_backup_store.aliyun_oss_client, "oss_bucket_name", lambda: "mindgraph")
    monkeypatch.setattr(oss_backup_store.aliyun_oss_client, "oss_region", lambda: "cn-beijing")
    uploaded: list[str] = []

    def _upload(_path: Path, key: str, **_kwargs: object) -> bool:
        uploaded.append(key)
        return True

    monkeypatch.setattr(oss_backup_store.aliyun_oss_client, "upload_file", _upload)
    monkeypatch.setattr(oss_backup_store, "cleanup_old_oss_backups", lambda retention_days=2: 0)
    dump = tmp_path / "mindgraph.postgresql.1.dump"
    dump.write_bytes(b"dump")
    manifest = tmp_path / "mindgraph.postgresql.1.dump.manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    oss_backup_store.upload_oss_backup_if_enabled(dump, manifest)
    assert uploaded == [
        "dev_roy/backups/mindgraph.postgresql.1.dump",
        "dev_roy/backups/mindgraph.postgresql.1.dump.manifest.json",
    ]


def test_oss_cleanup_deletes_old_dump_and_manifest(monkeypatch) -> None:
    """Dumps older than two days are removed with their manifest."""
    monkeypatch.setenv("OSS_BACKUP_ENABLED", "true")
    monkeypatch.setattr(oss_backup_store.aliyun_oss_client, "oss_credentials_configured", lambda: True)
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5)
    monkeypatch.setattr(
        oss_backup_store,
        "list_oss_backups",
        lambda: [
            {
                "key": "dev_roy/backups/mindgraph.postgresql.old.dump",
                "last_modified": old,
                "size": 10,
                "filename": "mindgraph.postgresql.old.dump",
            }
        ],
    )
    deleted: list[str] = []
    monkeypatch.setattr(
        oss_backup_store.aliyun_oss_client,
        "delete_object",
        lambda key, log_prefix="[OSS]": deleted.append(key) or True,
    )
    assert oss_backup_store.cleanup_old_oss_backups(2) == 1
    assert deleted == [
        "dev_roy/backups/mindgraph.postgresql.old.dump",
        "dev_roy/backups/mindgraph.postgresql.old.dump.manifest.json",
    ]
