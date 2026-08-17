"""Host/workload samples in timestamped ``logs/performance.*.log`` (not app.log)."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psutil
import redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.celery import BROKER_URL, celery_worker_concurrency
from models.domain.mind_classroom import MindClassroomJob
from models.domain.showcase import ShowcaseCoverJob
from models.domain.zhihui import ZhihuiConversation
from services.infrastructure.monitoring.worker_perf_redis import load_all_worker_perf_snapshots
from services.infrastructure.utils.logging_config import TimestampedRotatingFileHandler, UnifiedFormatter
from services.redis import keys as redis_keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_connection_options import celery_redis_pool_options
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS, REDIS_ERRORS
from utils.db.session_open import system_rls_session

LOGGER_NAME = "mindgraph.performance"
LOG_FILENAME = "performance.log"
# Same 72h dated files as app.log so periods line up; 10 files ≈ 30 days, still a few MB.
ROTATE_INTERVAL_HOURS = 72
BACKUP_COUNT = 10
DEFAULT_INTERVAL_SECONDS = 60
_MIN_INTERVAL_SECONDS = 30
_MAX_INTERVAL_SECONDS = 600
_CLASSROOM_ACTIVE = ("queued", "planning", "generating")
_ZHIHUI_ACTIVE = ("queued", "planning", "generating")
_COVER_ACTIVE = ("queued", "running")
_SAMPLE_ERRORS = BACKGROUND_INFRA_ERRORS + DATABASE_ERRORS + REDIS_ERRORS


class _LoggerHolder:
    """Process-local logger so we do not use a module global statement."""

    logger: Optional[logging.Logger] = None


@dataclass(frozen=True)
class PerfSample:
    """One compact host + queue + in-flight job snapshot."""

    cpu_percent: Optional[float]
    ram_percent: Optional[float]
    ram_used_gb: Optional[float]
    ram_free_gb: Optional[float]
    disk_percent: Optional[float]
    uvicorn_concurrency: int
    api_workers: Optional[int]
    api_cpu_percent: Optional[float]
    api_rss_gb: Optional[float]
    celery_concurrency: int
    celery_rss_gb: Optional[float]
    queue_default: Optional[int]
    queue_knowledge: Optional[int]
    classroom_active: Optional[int]
    zhihui_active: Optional[int]
    covers_active: Optional[int]


def perf_sample_enabled() -> bool:
    """True unless ``PERF_SAMPLE_LOG`` is an explicit off value."""
    raw = (os.getenv("PERF_SAMPLE_LOG") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def perf_sample_interval_seconds() -> int:
    """Seconds between samples (default 60, clamped)."""
    raw = (os.getenv("PERF_SAMPLE_INTERVAL_SECONDS") or "").strip()
    if not raw:
        return DEFAULT_INTERVAL_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_INTERVAL_SECONDS
    return min(_MAX_INTERVAL_SECONDS, max(_MIN_INTERVAL_SECONDS, value))


def performance_log_base_path() -> Path:
    """Same CWD ``logs/`` directory as ``app.log`` so dated files stay paired."""
    return Path("logs") / LOG_FILENAME


def _fmt_num(value: Optional[float], digits: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def _fmt_int(value: Optional[int]) -> str:
    return "-" if value is None else str(value)


def configured_uvicorn_workers() -> int:
    """Match ``server_launcher``: ``UVICORN_WORKERS`` or ``min(cpus, 4)``."""
    raw = (os.getenv("UVICORN_WORKERS") or os.getenv("WEB_CONCURRENCY") or "").strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            value = 0
        if value > 0:
            return value
    if os.name == "nt":
        return 1
    cpus = psutil.cpu_count(logical=True) or 1
    return min(int(cpus), 4)


def format_perf_sample_line(sample: PerfSample) -> str:
    """Metrics only; ``UnifiedFormatter`` adds the same ``[HH:MM:SS]`` prefix as app.log."""
    return (
        f"cpu={_fmt_num(sample.cpu_percent, 1)} "
        f"ram={_fmt_num(sample.ram_percent, 1)}% "
        f"ram_gb={_fmt_num(sample.ram_used_gb, 2)} "
        f"ram_free_gb={_fmt_num(sample.ram_free_gb, 2)} "
        f"disk={_fmt_num(sample.disk_percent, 1)}% "
        f"uv_c={sample.uvicorn_concurrency} "
        f"api_n={_fmt_int(sample.api_workers)} "
        f"api_cpu={_fmt_num(sample.api_cpu_percent, 1)} "
        f"api_rss_gb={_fmt_num(sample.api_rss_gb, 2)} "
        f"ce_c={sample.celery_concurrency} "
        f"ce_rss_gb={_fmt_num(sample.celery_rss_gb, 2)} "
        f"q_default={_fmt_int(sample.queue_default)} "
        f"q_knowledge={_fmt_int(sample.queue_knowledge)} "
        f"classroom={_fmt_int(sample.classroom_active)} "
        f"zhihui={_fmt_int(sample.zhihui_active)} "
        f"covers={_fmt_int(sample.covers_active)}"
    )


def _primary_disk_mount() -> str:
    """Root volume on Linux; system drive on Windows."""
    if os.name == "nt":
        drive = os.environ.get("SystemDrive", "C:")
        if drive.endswith("\\") or drive.endswith("/"):
            return drive
        return f"{drive}\\"
    return "/"


def _host_fields() -> tuple[
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
]:
    try:
        cpu = float(psutil.cpu_percent(interval=0.1, percpu=False))
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage(_primary_disk_mount())
        return (
            round(cpu, 1),
            round(float(vm.percent), 1),
            round(int(vm.used) / 1_000_000_000, 2),
            round(int(vm.available) / 1_000_000_000, 2),
            round(float(disk.percent), 1),
        )
    except (OSError, ValueError, TypeError, RuntimeError):
        return None, None, None, None, None


def _celery_rss_gb() -> Optional[float]:
    """RSS of Celery parent + prefork children (not Uvicorn)."""
    total = 0
    found = 0
    try:
        for proc in psutil.process_iter(["cmdline", "memory_info"]):
            try:
                cmd = proc.info.get("cmdline") or []
                joined = " ".join(str(part) for part in cmd)
                if "celery" not in joined or "config.celery" not in joined:
                    continue
                mem = proc.info.get("memory_info")
                if mem is None:
                    continue
                total += int(mem.rss)
                found += 1
            except (psutil.Error, OSError, TypeError, ValueError):
                continue
    except (psutil.Error, OSError, TypeError, ValueError):
        return None
    if found == 0:
        return None
    return round(total / 1_000_000_000, 2)


def _celery_queue_lengths() -> tuple[Optional[int], Optional[int]]:
    client = None
    try:
        client = redis.Redis.from_url(
            BROKER_URL,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
            **celery_redis_pool_options(),
        )
        default = client.llen("default")
        knowledge = client.llen("knowledge")
        return int(default or 0), int(knowledge or 0)
    except _SAMPLE_ERRORS:
        return None, None
    finally:
        if client is not None:
            try:
                client.close()
            except _SAMPLE_ERRORS:
                pass


async def _api_worker_stats_async() -> tuple[Optional[int], Optional[float], Optional[float]]:
    rows = await load_all_worker_perf_snapshots()
    rss_sum = 0
    cpu_sum = 0.0
    count = 0
    for row in rows:
        proc = row.get("process")
        if not isinstance(proc, dict):
            continue
        rss = proc.get("rss_bytes")
        if not isinstance(rss, int) or rss < 0:
            continue
        rss_sum += rss
        cpu = proc.get("cpu_percent")
        if isinstance(cpu, (int, float)):
            cpu_sum += float(cpu)
        count += 1
    if count == 0:
        return None, None, None
    return count, round(cpu_sum, 1), round(rss_sum / 1_000_000_000, 2)


async def _count_one(
    db: AsyncSession,
    model: type[MindClassroomJob] | type[ZhihuiConversation] | type[ShowcaseCoverJob],
    statuses: tuple[str, ...],
) -> int:
    stmt = select(func.count()).select_from(model).where(model.status.in_(statuses))
    result = await db.execute(stmt)
    return int(result.scalar_one())


async def _job_counts() -> tuple[Optional[int], Optional[int], Optional[int]]:
    try:
        async with system_rls_session() as db:
            classroom = await _count_one(db, MindClassroomJob, _CLASSROOM_ACTIVE)
            zhihui = await _count_one(db, ZhihuiConversation, _ZHIHUI_ACTIVE)
            covers = await _count_one(db, ShowcaseCoverJob, _COVER_ACTIVE)
            return classroom, zhihui, covers
    except _SAMPLE_ERRORS:
        return None, None, None


def perf_sample_lock_key() -> str:
    """One writer per host so a shared Redis does not silence other nodes."""
    host = (socket.gethostname() or "unknown").strip() or "unknown"
    return redis_keys.LOCK_PERF_SAMPLE.format(host=host)


async def claim_perf_sample_lock(ttl_seconds: int) -> bool:
    """True when this process should write the next sample (one writer per host)."""
    client = get_async_redis()
    if client is None:
        return False
    token = str(os.getpid())
    key = perf_sample_lock_key()
    ttl = max(45, int(ttl_seconds))
    try:
        owned = await client.get(key)
        if owned is not None:
            owned_text = owned.decode("utf-8") if isinstance(owned, (bytes, bytearray)) else str(owned)
            if owned_text == token:
                await client.expire(key, ttl)
                return True
            return False
        acquired = await client.set(key, token, nx=True, ex=ttl)
        return bool(acquired)
    except _SAMPLE_ERRORS:
        return False


def _emit_sample_failed(exc: BaseException) -> None:
    try:
        get_performance_logger().info("sample_failed err=%s", type(exc).__name__)
    except _SAMPLE_ERRORS:
        pass


async def collect_perf_sample() -> PerfSample:
    """Read host, worker caps, RSS, queues, and in-flight job counts."""
    cpu, ram_pct, ram_gb, ram_free, disk_pct = await asyncio.to_thread(_host_fields)
    q_default, q_knowledge = await asyncio.to_thread(_celery_queue_lengths)
    celery_rss = await asyncio.to_thread(_celery_rss_gb)
    api_n, api_cpu, api_rss = await _api_worker_stats_async()
    classroom, zhihui, covers = await _job_counts()
    return PerfSample(
        cpu_percent=cpu,
        ram_percent=ram_pct,
        ram_used_gb=ram_gb,
        ram_free_gb=ram_free,
        disk_percent=disk_pct,
        uvicorn_concurrency=configured_uvicorn_workers(),
        api_workers=api_n,
        api_cpu_percent=api_cpu,
        api_rss_gb=api_rss,
        celery_concurrency=celery_worker_concurrency(),
        celery_rss_gb=celery_rss,
        queue_default=q_default,
        queue_knowledge=q_knowledge,
        classroom_active=classroom,
        zhihui_active=zhihui,
        covers_active=covers,
    )


def get_performance_logger() -> logging.Logger:
    """Logger that writes only to ``logs/performance.log`` (does not propagate)."""
    held = _LoggerHolder.logger
    if held is not None:
        return held
    log = logging.getLogger(LOGGER_NAME)
    log.setLevel(logging.INFO)
    log.propagate = False
    if not log.handlers:
        path = performance_log_base_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = TimestampedRotatingFileHandler(
            str(path),
            interval_hours=ROTATE_INTERVAL_HOURS,
            backup_count=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(UnifiedFormatter(use_colors=False))
        log.addHandler(handler)
    _LoggerHolder.logger = log
    return log


async def write_perf_sample() -> None:
    """Collect one sample and append a single line."""
    sample = await collect_perf_sample()
    get_performance_logger().info(format_perf_sample_line(sample))


async def run_perf_sample_loop(stop: asyncio.Event) -> None:
    """Write one line per interval until ``stop`` is set."""
    interval = float(perf_sample_interval_seconds())
    lock_ttl = int(interval) + 30
    while not stop.is_set():
        try:
            if await claim_perf_sample_lock(lock_ttl):
                await write_perf_sample()
        except asyncio.CancelledError:
            raise
        except _SAMPLE_ERRORS as exc:
            _emit_sample_failed(exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


def start_perf_sample_loop() -> tuple[asyncio.Task[None], asyncio.Event]:
    """Start the background sampler. Caller must stop the event on shutdown."""
    stop = asyncio.Event()
    task = asyncio.create_task(run_perf_sample_loop(stop), name="perf_sample_log")
    return task, stop
