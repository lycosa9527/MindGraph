"""Admin live performance metrics snapshot (Performance tab polling).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import time
from typing import Any, Dict, List, Optional

import psutil
from fastapi import APIRouter, Depends

from config.database import async_engine, engine
from config.settings import config
from models.domain.auth import User
from routers.auth.dependencies import require_admin
from routers.core.health import _cached_redis_info, _collect_pool_stats, _fetch_redis_memory_stats
from services.infrastructure.monitoring.worker_perf_redis import load_all_worker_perf_snapshots
from services.infrastructure.monitoring.ws_metrics import get_ws_metrics_snapshot
from services.redis.redis_activity_tracker import get_activity_tracker
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
logger = logging.getLogger(__name__)

router = APIRouter()


class _NetworkRateState:
    """Hold previous ``net_io_counters`` sample for delta B/s (per API process)."""

    __slots__ = ("t_mono", "bytes_sent", "bytes_recv")

    def __init__(self) -> None:
        self.t_mono: Optional[float] = None
        self.bytes_sent: Optional[int] = None
        self.bytes_recv: Optional[int] = None


_NET_RATE = _NetworkRateState()


def _compute_network_rates() -> Dict[str, Any]:
    try:
        counters = psutil.net_io_counters()
    except (OSError, RuntimeError, TypeError) as exc:
        return {"error": str(exc), "bytes_sent_per_sec": None, "bytes_recv_per_sec": None}
    now = time.monotonic()
    sent = int(counters.bytes_sent)
    recv = int(counters.bytes_recv)
    prev_t = _NET_RATE.t_mono
    prev_s = _NET_RATE.bytes_sent
    prev_r = _NET_RATE.bytes_recv
    _NET_RATE.t_mono = now
    _NET_RATE.bytes_sent = sent
    _NET_RATE.bytes_recv = recv
    if prev_t is None or prev_s is None or prev_r is None:
        return {"bytes_sent_per_sec": 0.0, "bytes_recv_per_sec": 0.0}
    elapsed = now - prev_t
    if elapsed <= 0:
        return {"bytes_sent_per_sec": 0.0, "bytes_recv_per_sec": 0.0}
    return {
        "bytes_sent_per_sec": max(0.0, (sent - prev_s) / elapsed),
        "bytes_recv_per_sec": max(0.0, (recv - prev_r) / elapsed),
    }


def _primary_disk_mount() -> str:
    if platform.system() == "Windows":
        drive = os.environ.get("SystemDrive", "C:")
        if not drive.endswith("\\") and not drive.endswith("/"):
            return f"{drive}\\"
        return drive
    return "/"


def _disk_usage_one(path: str) -> Optional[Dict[str, Any]]:
    try:
        usage = psutil.disk_usage(path)
        total = int(usage.total)
        free = int(usage.free)
        used = int(usage.used)
        pct = round((used / total) * 100.0, 2) if total > 0 else 0.0
        return {
            "mount": path,
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "percent_used": pct,
        }
    except OSError:
        return None


def _collect_disk_volumes() -> List[Dict[str, Any]]:
    primary = _primary_disk_mount()
    out: List[Dict[str, Any]] = []
    try:
        for part in psutil.disk_partitions(all=False):
            opts = (part.opts or "").lower()
            if "cdrom" in opts or part.fstype == "cdfs":
                continue
            if "remote" in opts or part.fstype in ("nfs", "cifs", "smbfs"):
                continue
            if not part.mountpoint:
                continue
            if part.mountpoint.rstrip("\\") == primary.rstrip("\\"):
                continue
            du = _disk_usage_one(part.mountpoint)
            if du is not None:
                out.append(du)
    except (OSError, AttributeError) as exc:
        logger.debug("disk_partitions skipped: %s", exc)
    return out


def _host_snapshot() -> Dict[str, Any]:
    try:
        cpu_percent = float(psutil.cpu_percent(interval=None))
        vm = psutil.virtual_memory()
        mount = _primary_disk_mount()
        disk_primary = _disk_usage_one(mount)
        disk_volumes = _collect_disk_volumes()
        return {
            "cpu_percent": round(cpu_percent, 2),
            "cpu_count": int(psutil.cpu_count(logical=True) or 0),
            "mem_total_bytes": int(vm.total),
            "mem_used_bytes": int(vm.used),
            "mem_percent": round(float(vm.percent), 2),
            "disk_primary": disk_primary,
            "disk_volumes": disk_volumes,
        }
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        logger.debug("host snapshot failed: %s", exc)
        return {"error": str(exc)}


def _process_snapshot() -> Dict[str, Any]:
    try:
        proc = psutil.Process()
        with proc.oneshot():
            cpu = float(proc.cpu_percent(interval=None))
            mem = proc.memory_info()
            rss = int(mem.rss)
        return {
            "pid": int(proc.pid),
            "cpu_percent": round(cpu, 2),
            "rss_bytes": rss,
        }
    except (OSError, ValueError, TypeError, RuntimeError, psutil.Error) as exc:
        logger.debug("process snapshot failed: %s", exc)
        return {"error": str(exc)}


def _database_pools_snapshot() -> Dict[str, Any]:
    try:
        return {
            "async": _collect_pool_stats(async_engine.pool),
            "sync": _collect_pool_stats(engine.pool),
        }
    except (AttributeError, TypeError) as exc:
        return {"error": str(exc)}


def _dingtalk_snapshot() -> Dict[str, Any]:
    try:
        from services.mindbot.platforms.dingtalk.cards.stream_client import get_stream_manager

        mgr = get_stream_manager()
        clients = mgr.stream_clients_snapshot()
        running_n = sum(1 for row in clients if row.get("running"))
        return {
            "registered_count": int(mgr.registered_client_count()),
            "running_count": int(running_n),
            "clients": clients,
        }
    except ImportError as exc:
        return {"error": str(exc)}
    except (TypeError, ValueError, AttributeError, KeyError) as exc:
        return {"error": str(exc)}


def _process_services_snapshot() -> Dict[str, Any]:
    try:
        from services.infrastructure.monitoring.process_monitor import get_process_monitor

        return get_process_monitor().get_status()
    except ImportError as exc:
        return {"error": str(exc)}
    except (TypeError, ValueError, RuntimeError, AttributeError) as exc:
        logger.debug("process services snapshot failed: %s", exc)
        return {"error": str(exc)}


def _llm_snapshot() -> Dict[str, Any]:
    try:
        from services.llm import llm_service

        raw = llm_service.get_performance_metrics()
        out: Dict[str, Any] = {}
        for name, data in raw.items():
            if not isinstance(data, dict):
                continue
            row = dict(data)
            circuit = row.get("circuit_state")
            if hasattr(circuit, "value"):
                row["circuit_state"] = circuit.value
            elif circuit is not None:
                row["circuit_state"] = str(circuit)
            out[str(name)] = row
        return out
    except ImportError as exc:
        return {"error": str(exc)}
    except (TypeError, ValueError, RuntimeError, AttributeError) as exc:
        logger.debug("llm snapshot failed: %s", exc)
        return {"error": str(exc)}


def _app_snapshot() -> Dict[str, Any]:
    try:
        import main

        app = main.app
        uptime = time.time() - app.state.start_time if hasattr(app.state, "start_time") else 0.0
        return {
            "version": config.version,
            "uptime_seconds": round(uptime, 1),
        }
    except (ImportError, AttributeError) as exc:
        return {"error": str(exc)}


async def _redis_snapshot() -> Dict[str, Any]:
    if not is_redis_available():
        return {"status": "unavailable", "message": "Redis not connected"}
    redis_client = get_async_redis()
    if redis_client is None:
        return {"status": "unavailable", "message": "Async Redis client not initialized"}

    async def _probe() -> Dict[str, Any]:
        ping_ok = await redis_client.ping()
        if not ping_ok:
            return {"status": "unhealthy", "message": "Ping failed"}
        mem_info = await _cached_redis_info(redis_client, "memory")
        human = await _fetch_redis_memory_stats(redis_client)
        server = await _cached_redis_info(redis_client, "server")
        used_b = mem_info.get("used_memory")
        peak_b = mem_info.get("used_memory_peak")
        frag = mem_info.get("mem_fragmentation_ratio")
        try:
            frag_f = float(frag) if frag is not None else None
        except (TypeError, ValueError):
            frag_f = None
        used_int = int(used_b) if used_b is not None else None
        peak_int = int(peak_b) if peak_b is not None else None
        return {
            "status": "healthy",
            "used_memory_bytes": used_int,
            "used_memory_peak_bytes": peak_int,
            "used_memory_human": human.get("used_memory_human"),
            "used_memory_peak_human": human.get("used_memory_peak_human"),
            "mem_fragmentation_ratio": frag_f,
            "redis_version": server.get("redis_version"),
            "uptime_in_seconds": server.get("uptime_in_seconds"),
        }

    try:
        return await asyncio.wait_for(_probe(), timeout=3.0)
    except asyncio.TimeoutError:
        return {"status": "error", "message": "Redis snapshot timed out"}
    except (ConnectionError, RuntimeError, ValueError, TypeError) as exc:
        return {"status": "error", "message": str(exc)}


async def _activity_snapshot() -> Dict[str, Any]:
    try:
        return await asyncio.wait_for(get_activity_tracker().get_stats(), timeout=3.0)
    except asyncio.TimeoutError:
        return {"error": "activity stats timed out"}
    except (ConnectionError, RuntimeError, ValueError, TypeError) as exc:
        return {"error": str(exc)}


_WS_SUM_KEYS = frozenset(
    {
        "ws_chat_connections",
        "ws_workshop_connections",
        "ws_fanout_chat_published",
        "ws_fanout_chat_received",
        "ws_fanout_workshop_published",
        "ws_fanout_workshop_received",
        "ws_auth_failures",
        "ws_rate_limit_hits",
    }
)


async def build_worker_perf_payload_async() -> Dict[str, Any]:
    """Per-uvicorn-worker snapshot (published to Redis and merged on admin poll)."""
    websockets: Dict[str, Any] = {}
    try:
        websockets = await asyncio.wait_for(get_ws_metrics_snapshot(), timeout=2.0)
    except asyncio.TimeoutError:
        websockets = {"error": "websocket metrics timed out"}
    except (ConnectionError, RuntimeError, ValueError, TypeError) as exc:
        websockets = {"error": str(exc)}
    return {
        "pid": int(os.getpid()),
        "ts": time.time(),
        "process": _process_snapshot(),
        "database_pools": _database_pools_snapshot(),
        "dingtalk_stream": _dingtalk_snapshot(),
        "process_services": _process_services_snapshot(),
        "llm": _llm_snapshot(),
        "websockets": websockets,
        "app": _app_snapshot(),
    }


def _coalesce_worker_rows(stored: List[Dict[str, Any]], live: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_pid: Dict[int, Dict[str, Any]] = {}
    for row in stored:
        pid = row.get("pid")
        if isinstance(pid, int):
            by_pid[pid] = row
    live_pid = live.get("pid")
    if isinstance(live_pid, int):
        by_pid[live_pid] = live
    return list(by_pid.values())


def _merge_process_cluster(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    workers: List[Dict[str, Any]] = []
    rss_sum = 0
    cpu_sum = 0.0
    cpu_max = 0.0
    for row in rows:
        proc = row.get("process") or {}
        if proc.get("error"):
            continue
        pid = proc.get("pid")
        rss = proc.get("rss_bytes")
        cpu = proc.get("cpu_percent")
        if not isinstance(pid, int) or not isinstance(rss, int):
            continue
        cpu_f = float(cpu) if isinstance(cpu, (int, float)) else 0.0
        workers.append({"pid": int(pid), "rss_bytes": int(rss), "cpu_percent": round(cpu_f, 2)})
        rss_sum += int(rss)
        cpu_sum += cpu_f
        cpu_max = max(cpu_max, cpu_f)
    if not workers:
        return {"error": "no process samples"}
    return {
        "workers": workers,
        "worker_count": len(workers),
        "rss_bytes": rss_sum,
        "cpu_percent": round(cpu_sum, 2),
        "cpu_percent_max": round(cpu_max, 2),
        "pid": workers[0]["pid"],
    }


def _merge_pool_half(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    size = checked_in = checked_out = 0
    overflow_max = 0
    any_ok = False
    for row in rows:
        pools = row.get("database_pools") or {}
        if pools.get("error"):
            continue
        part = pools.get(key) or {}
        if not part:
            continue
        try:
            size += int(part.get("size") or 0)
            checked_in += int(part.get("checked_in") or 0)
            checked_out += int(part.get("checked_out") or 0)
            overflow_max = max(overflow_max, int(part.get("overflow") or 0))
        except (TypeError, ValueError):
            continue
        any_ok = True
    if not any_ok:
        return {}
    return {
        "size": size,
        "checked_in": checked_in,
        "checked_out": checked_out,
        "overflow": overflow_max,
        "total": size + overflow_max,
    }


def _merge_database_pools_cluster(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    async_part = _merge_pool_half(rows, "async")
    sync_part = _merge_pool_half(rows, "sync")
    if not async_part and not sync_part:
        first = rows[0].get("database_pools") if rows else {}
        if isinstance(first, dict) and first.get("error"):
            return {"error": first["error"]}
        return {"error": "no pool samples"}
    out: Dict[str, Any] = {}
    if async_part:
        out["async"] = async_part
    if sync_part:
        out["sync"] = sync_part
    return out


def _merge_dingtalk_cluster(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    clients_map: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        dt = row.get("dingtalk_stream") or {}
        if dt.get("error"):
            continue
        for c in dt.get("clients") or []:
            if not isinstance(c, dict):
                continue
            cid = c.get("client_id")
            if not isinstance(cid, str) or not cid:
                continue
            running = bool(c.get("running"))
            prev = clients_map.get(cid)
            if prev is None:
                clients_map[cid] = {"client_id": cid, "running": running}
            else:
                clients_map[cid] = {"client_id": cid, "running": prev["running"] or running}
    client_list = list(clients_map.values())
    running_n = sum(1 for x in client_list if x.get("running"))
    return {
        "registered_count": len(client_list),
        "running_count": int(running_n),
        "clients": client_list,
    }


def _merge_process_services_cluster(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        ps = row.get("process_services") or {}
        if not isinstance(ps, dict):
            continue
        if len(ps) == 1 and "error" in ps:
            continue
        for name, data in ps.items():
            if name == "error" or not isinstance(data, dict):
                continue
            up = data.get("uptime_seconds")
            up_f = float(up) if isinstance(up, (int, float)) else 0.0
            prev = merged.get(name)
            if prev is None:
                merged[name] = dict(data)
                continue
            p_up = prev.get("uptime_seconds")
            p_up_f = float(p_up) if isinstance(p_up, (int, float)) else 0.0
            if up_f > p_up_f:
                merged[name] = dict(data)
    return merged


def _merge_llm_cluster(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    acc: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        llm = row.get("llm") or {}
        if not isinstance(llm, dict) or (len(llm) == 1 and "error" in llm):
            continue
        for model, data in llm.items():
            if model == "error" or not isinstance(data, dict):
                continue
            tr = data.get("total_requests")
            sr = data.get("success_rate")
            tr_i = int(tr) if isinstance(tr, (int, float)) else 0
            sr_f = float(sr) if isinstance(sr, (int, float)) else None
            cur = acc.get(model)
            if cur is None:
                row_copy = dict(data)
                row_copy["total_requests"] = tr_i
                if sr_f is not None:
                    row_copy["success_rate"] = sr_f
                acc[model] = row_copy
                continue
            prev_req = cur.get("total_requests")
            prev_i = int(prev_req) if isinstance(prev_req, (int, float)) else 0
            new_req = prev_i + tr_i
            cur_sr = cur.get("success_rate")
            prev_sr = float(cur_sr) if isinstance(cur_sr, (int, float)) else None
            if prev_sr is not None and sr_f is not None and new_req > 0:
                weighted = (prev_sr * prev_i + sr_f * tr_i) / new_req
                cur["success_rate"] = round(weighted, 4)
            elif sr_f is not None:
                cur["success_rate"] = sr_f
            cur["total_requests"] = new_req
            for k, v in data.items():
                if k not in ("total_requests", "success_rate"):
                    cur[k] = v
    if not acc and rows:
        first = rows[0].get("llm")
        if isinstance(first, dict) and first.get("error"):
            return {"error": first["error"]}
    return acc


def _merge_websockets_cluster(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {k: 0 for k in _WS_SUM_KEYS}
    redis_total: Optional[int] = None
    for row in rows:
        ws = row.get("websockets") or {}
        if ws.get("error"):
            continue
        for key in _WS_SUM_KEYS:
            val = ws.get(key)
            if isinstance(val, (int, float)):
                merged[key] += int(val)
        rt = ws.get("ws_active_total_redis")
        if isinstance(rt, int):
            redis_total = rt if redis_total is None else max(redis_total, rt)
    out: Dict[str, Any] = {**merged, "timestamp": time.time()}
    if redis_total is not None:
        out["ws_active_total_redis"] = redis_total
    return out


def _merge_cluster_worker_fields(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge per-worker payloads into cluster-level sections."""
    return {
        "process": _merge_process_cluster(rows),
        "database_pools": _merge_database_pools_cluster(rows),
        "dingtalk_stream": _merge_dingtalk_cluster(rows),
        "process_services": _merge_process_services_cluster(rows),
        "llm": _merge_llm_cluster(rows),
        "websockets": _merge_websockets_cluster(rows),
    }


def _pick_app_cluster(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    best: Optional[Dict[str, Any]] = None
    best_uptime = -1.0
    for row in rows:
        app = row.get("app") or {}
        if app.get("error"):
            continue
        up = app.get("uptime_seconds")
        up_f = float(up) if isinstance(up, (int, float)) else 0.0
        if up_f > best_uptime:
            best_uptime = up_f
            best = dict(app)
    if best is not None:
        return best
    return _app_snapshot()


@router.get("/admin/performance/live")
async def get_admin_performance_live(
    _current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Aggregated live metrics for the admin Performance tab (poll every 1–2s)."""
    live_worker = await build_worker_perf_payload_async()
    stored = await load_all_worker_perf_snapshots()
    cluster_rows = _coalesce_worker_rows(stored, live_worker)
    cluster_fields = _merge_cluster_worker_fields(cluster_rows)

    payload: Dict[str, Any] = {
        "timestamp": time.time(),
        "host": _host_snapshot(),
        "network": _compute_network_rates(),
        "process": cluster_fields["process"],
        "database_pools": cluster_fields["database_pools"],
        "dingtalk_stream": cluster_fields["dingtalk_stream"],
        "process_services": cluster_fields["process_services"],
        "app": _pick_app_cluster(cluster_rows),
        "llm": cluster_fields["llm"],
        "websockets": cluster_fields["websockets"],
        "redis": {},
        "activity": {},
        "cluster": {
            "workers_reporting": len(cluster_rows),
        },
    }
    payload["redis"] = await _redis_snapshot()
    payload["activity"] = await _activity_snapshot()
    return payload
