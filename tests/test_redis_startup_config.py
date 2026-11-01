"""Redis startup CONFIG SET must not touch immutable io-threads."""

from unittest.mock import MagicMock

from services.redis.redis_client import _apply_redis_startup_config


def test_runtime_tuning_does_not_config_set_io_threads():
    """io-threads is immutable; startup must leave it out of CONFIG SET."""
    client = MagicMock()
    client.config_get.return_value = {"appendonly": "yes", "appendfsync": "everysec"}

    _apply_redis_startup_config(client, "7.2.0")

    keys = [call.args[0] for call in client.config_set.call_args_list]
    assert "io-threads" not in keys
    assert "io-threads-do-reads" not in keys
    assert "lazyfree-lazy-eviction" in keys
