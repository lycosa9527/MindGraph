"""Performance samples share app.log clock format and 72h dated files."""

from __future__ import annotations

import asyncio
import logging
import os
from unittest.mock import AsyncMock, patch

import pytest

from services.infrastructure.monitoring.perf_sample_log import (
    BACKUP_COUNT,
    ROTATE_INTERVAL_HOURS,
    PerfSample,
    claim_perf_sample_lock,
    configured_uvicorn_workers,
    format_perf_sample_line,
    get_performance_logger,
    performance_log_base_path,
    perf_sample_enabled,
    perf_sample_interval_seconds,
    perf_sample_lock_key,
    run_perf_sample_loop,
)
from services.infrastructure.utils.logging_config import (
    TimestampedRotatingFileHandler,
    UnifiedFormatter,
)


def _sample() -> PerfSample:
    return PerfSample(
        cpu_percent=22.4,
        ram_percent=48.1,
        ram_used_gb=7.81,
        ram_free_gb=8.43,
        disk_percent=11.5,
        uvicorn_concurrency=4,
        api_workers=4,
        api_cpu_percent=12.0,
        api_rss_gb=3.59,
        celery_concurrency=4,
        celery_rss_gb=1.20,
        queue_default=6,
        queue_knowledge=0,
        classroom_active=8,
        zhihui_active=1,
        covers_active=2,
    )


def test_perf_sample_line_includes_tuning_fields() -> None:
    """Caps, free RAM, API CPU, and Celery RSS are present for worker reviews."""
    line = format_perf_sample_line(_sample())
    assert line.startswith("cpu=22.4")
    assert "ram_free_gb=8.43" in line
    assert "uv_c=4" in line
    assert "api_cpu=12.0" in line
    assert "ce_c=4" in line
    assert "ce_rss_gb=1.20" in line
    assert "q_default=6" in line
    assert "classroom=8" in line
    assert "[" not in line
    assert len(line) < 320


def test_perf_sample_uses_app_log_line_shape() -> None:
    """A formatted record matches [HH:MM:SS] INFO | PERF | [pid] …."""
    record = logging.LogRecord(
        name="mindgraph.performance",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="cpu=12.4 ram=41.2%",
        args=(),
        exc_info=None,
    )
    formatted = UnifiedFormatter(use_colors=False).format(record)
    assert formatted.startswith("[")
    assert "] INFO  | PERF | [" in formatted
    assert formatted.endswith("cpu=12.4 ram=41.2%")


def test_perf_sample_rotation_matches_app_log_period() -> None:
    """Same 72-hour stamp windows as app.log; 10 files stay small."""
    assert ROTATE_INTERVAL_HOURS == 72
    assert BACKUP_COUNT == 10


def test_configured_uvicorn_workers_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """UVICORN_WORKERS wins over the CPU default."""
    monkeypatch.setenv("UVICORN_WORKERS", "3")
    assert configured_uvicorn_workers() == 3
    monkeypatch.setenv("UVICORN_WORKERS", "0")
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    assert configured_uvicorn_workers() >= 1


def test_perf_sample_interval_clamps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid or extreme intervals fall back to a sane minute-scale cadence."""
    monkeypatch.delenv("PERF_SAMPLE_INTERVAL_SECONDS", raising=False)
    assert perf_sample_interval_seconds() == 60
    monkeypatch.setenv("PERF_SAMPLE_INTERVAL_SECONDS", "5")
    assert perf_sample_interval_seconds() == 30
    monkeypatch.setenv("PERF_SAMPLE_INTERVAL_SECONDS", "9999")
    assert perf_sample_interval_seconds() == 600
    monkeypatch.setenv("PERF_SAMPLE_INTERVAL_SECONDS", "nope")
    assert perf_sample_interval_seconds() == 60


def test_perf_sample_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operators can turn the file off without touching app.log."""
    monkeypatch.setenv("PERF_SAMPLE_LOG", "false")
    assert perf_sample_enabled() is False
    monkeypatch.setenv("PERF_SAMPLE_LOG", "true")
    assert perf_sample_enabled() is True


def test_performance_log_path_pairs_with_app_log() -> None:
    """Samples land in CWD logs/ next to app.YYYY-MM-DD_HH-MM-SS.log."""
    path = performance_log_base_path()
    assert path.as_posix() == "logs/performance.log"


@pytest.mark.asyncio
async def test_claim_perf_sample_lock_skips_when_redis_missing() -> None:
    """Without Redis, do not write from every Uvicorn worker."""
    with patch(
        "services.infrastructure.monitoring.perf_sample_log.get_async_redis",
        return_value=None,
    ):
        assert await claim_perf_sample_lock(90) is False


@pytest.mark.asyncio
async def test_claim_perf_sample_lock_single_writer() -> None:
    """First claim wins; another pid must not write the same minute."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    with patch(
        "services.infrastructure.monitoring.perf_sample_log.get_async_redis",
        return_value=client,
    ):
        assert await claim_perf_sample_lock(90) is True
    client.set.assert_awaited()
    client.get = AsyncMock(return_value=b"other-pid")
    client.set = AsyncMock(return_value=False)
    with patch(
        "services.infrastructure.monitoring.perf_sample_log.get_async_redis",
        return_value=client,
    ):
        assert await claim_perf_sample_lock(90) is False


def test_perf_sample_lock_key_is_per_host() -> None:
    """Shared Redis must not let one host silence another node's samples."""
    key = perf_sample_lock_key()
    assert key.startswith("lock:mindgraph:perf_sample:")
    assert key != "lock:mindgraph:perf_sample:{host}"
    assert "{host}" not in key


@pytest.mark.asyncio
async def test_claim_perf_sample_lock_refreshes_owner() -> None:
    """The writer renews TTL so a slow sample does not drop the lock."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=str(os.getpid()).encode("utf-8"))
    client.expire = AsyncMock(return_value=True)
    client.set = AsyncMock(return_value=True)
    with patch(
        "services.infrastructure.monitoring.perf_sample_log.get_async_redis",
        return_value=client,
    ):
        assert await claim_perf_sample_lock(90) is True
    client.expire.assert_awaited()
    client.set.assert_not_called()


@pytest.mark.asyncio
async def test_run_loop_skips_write_without_lock() -> None:
    """Non-writers must not append lines or open extra DB/Redis work."""
    stop = asyncio.Event()

    async def _deny_lock(_ttl: int) -> bool:
        stop.set()
        return False

    with (
        patch(
            "services.infrastructure.monitoring.perf_sample_log.claim_perf_sample_lock",
            side_effect=_deny_lock,
        ),
        patch(
            "services.infrastructure.monitoring.perf_sample_log.write_perf_sample",
            new_callable=AsyncMock,
        ) as write,
    ):
        await run_perf_sample_loop(stop)
    write.assert_not_called()


def test_performance_logger_uses_timestamped_handler() -> None:
    """Samples stay off app.log and rotate on the same 72h calendar as app."""
    log = get_performance_logger()
    assert log.propagate is False
    assert any(isinstance(handler, TimestampedRotatingFileHandler) for handler in log.handlers)
