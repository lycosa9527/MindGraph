"""Redis flush helper for migration CLI."""

from scripts.db.redis_flush import flush_redis_cache, redis_flush_summary_label


def test_redis_flush_summary_uses_db_from_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/2")
    label = redis_flush_summary_label()
    assert "redis DB 2" in label


def test_flush_redis_cache_missing_package(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, message = flush_redis_cache()
    assert not ok
    assert "redis package" in message
