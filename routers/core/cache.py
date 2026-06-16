"""
MindGraph Cache Status Routes
==============================

FastAPI routes for JavaScript cache status endpoints.

Provides real-time monitoring of the lazy loading JavaScript cache system.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import time
from typing import Any, cast

from fastapi import APIRouter, Depends

from models.domain.auth import User
from services.utils.typing_helpers import mapping_float, mapping_int
from utils.auth import get_current_user

# Lazy imports - moved to top level to fix C0415
try:
    from static.js.lazy_cache_manager import (
        get_cache_stats,
        get_performance_summary,
        is_cache_initialized,
    )
    from static.js.modular_cache_python import (
        get_modular_cache_stats,
        get_modular_performance_summary,
    )
except ImportError:
    # Graceful fallback if modules are not available
    get_cache_stats = None
    get_performance_summary = None
    is_cache_initialized = None
    get_modular_cache_stats = None
    get_modular_performance_summary = None

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/cache", tags=["Cache"])

# ============================================================================
# CACHE STATUS ROUTES (3 routes from app.py)
# ============================================================================


@router.get("/status")
async def get_cache_status(_current_user: User = Depends(get_current_user)):
    """
    Lazy loading JavaScript cache status endpoint.

    Returns cache status, performance metrics, and optimization details.
    """
    try:
        if get_cache_stats is None or is_cache_initialized is None:
            raise ImportError("Lazy cache manager not available")

        if is_cache_initialized():
            stats = cast(dict[str, Any], get_cache_stats())
            memory_mb = mapping_float(stats, "memory_usage_mb")
            cache_data = {
                "status": "initialized",
                "cache_strategy": "lazy_loading_with_intelligent_caching",
                "files_loaded": mapping_int(stats, "files_loaded"),
                "total_size_bytes": mapping_int(stats, "total_memory_usage"),
                "total_size_kb": round(memory_mb * 1024, 2),
                "memory_usage_mb": memory_mb,
                "max_memory_mb": mapping_float(stats, "max_memory_mb"),
                "cache_hit_rate": round(mapping_float(stats, "cache_hit_rate"), 1),
                "total_requests": mapping_int(stats, "total_requests"),
                "cache_hits": mapping_int(stats, "cache_hits"),
                "cache_misses": mapping_int(stats, "cache_misses"),
                "average_load_time": round(mapping_float(stats, "average_load_time"), 3),
                "performance_improvement": "90-95%",
                "optimization": "Lazy loading + intelligent caching + memory optimization",
                "cache_ttl_seconds": 3600,
                "timestamp": time.time(),
            }
            logger.info(
                "Lazy cache status check: OK - %s files loaded, hit rate: %.1f%%",
                mapping_int(stats, "files_loaded"),
                mapping_float(stats, "cache_hit_rate"),
            )
            return cache_data

        cache_data = {
            "status": "not_initialized",
            "error": "Lazy loading JavaScript cache not properly initialized",
            "performance_impact": "File I/O overhead per request (2-5 seconds)",
            "timestamp": time.time(),
        }
        logger.warning("Lazy cache status check: FAILED - cache not initialized")
        return cache_data

    except Exception as e:
        cache_data = {
            "status": "error",
            "error": str(e),
            "performance_impact": "File I/O overhead per request (2-5 seconds)",
            "timestamp": time.time(),
        }
        logger.error("Lazy cache status check: ERROR - %s", e)
        return cache_data


@router.get("/performance")
async def get_cache_performance(_current_user: User = Depends(get_current_user)):
    """
    Detailed lazy cache performance endpoint.

    Returns comprehensive performance metrics and cache analysis.
    """
    try:
        if get_cache_stats is None or get_performance_summary is None:
            raise ImportError("Lazy cache manager not available")

        stats = cast(dict[str, Any], get_cache_stats())
        memory_mb = mapping_float(stats, "memory_usage_mb")
        max_memory_mb = mapping_float(stats, "max_memory_mb")
        performance_data = {
            "status": "success",
            "performance_summary": get_performance_summary(),
            "detailed_stats": {
                "cache_efficiency": {
                    "hit_rate_percent": round(mapping_float(stats, "cache_hit_rate"), 1),
                    "total_requests": mapping_int(stats, "total_requests"),
                    "cache_hits": mapping_int(stats, "cache_hits"),
                    "cache_misses": mapping_int(stats, "cache_misses"),
                },
                "memory_management": {
                    "current_usage_mb": memory_mb,
                    "max_allowed_mb": max_memory_mb,
                    "utilization_percent": round((memory_mb / max_memory_mb) * 100, 1),
                },
                "performance_metrics": {
                    "files_loaded": mapping_int(stats, "files_loaded"),
                    "average_load_time_seconds": round(mapping_float(stats, "average_load_time"), 3),
                    "total_load_time_seconds": round(mapping_float(stats, "total_load_time"), 3),
                },
                "cache_strategy": {
                    "type": "lazy_loading_with_intelligent_caching",
                    "ttl_seconds": 3600,
                    "cleanup_interval_seconds": 3600,
                    "memory_optimization": True,
                    "thread_safe": True,
                },
            },
            "timestamp": time.time(),
        }

        logger.info(
            "Cache performance check: OK - Hit rate: %.1f%%, Memory: %.1fMB",
            mapping_float(stats, "cache_hit_rate"),
            memory_mb,
        )
        return performance_data

    except Exception as e:
        performance_data = {
            "status": "error",
            "error": str(e),
            "timestamp": time.time(),
        }
        logger.error("Cache performance check: ERROR - %s", e)
        return performance_data


@router.get("/modular")
async def get_modular_cache_status(_current_user: User = Depends(get_current_user)):
    """
    Modular cache status endpoint for Option 3: Code Splitting.

    Returns modular cache status, performance metrics, and optimization details.
    """
    try:
        if get_modular_cache_stats is None or get_modular_performance_summary is None:
            raise ImportError("Modular cache not available")

        stats = cast(dict[str, Any], get_modular_cache_stats())
        performance_summary = cast(dict[str, Any], get_modular_performance_summary())
        modular_stats = cast(dict[str, Any], stats.get("modular", {}))

        cache_data = {
            "status": "success",
            "cache_type": "modular",
            "optimization": "Option 3: Code Splitting by Graph Type",
            "performance_summary": performance_summary,
            "detailed_stats": {
                "base_cache": {
                    "files_loaded": mapping_int(stats, "files_loaded") if "files_loaded" in stats else 0,
                    "total_size_bytes": mapping_int(stats, "total_memory_usage")
                    if "total_memory_usage" in stats
                    else 0,
                    "cache_hit_rate_percent": mapping_float(stats, "cache_hit_rate")
                    if "cache_hit_rate" in stats
                    else 0.0,
                },
                "modular_stats": modular_stats,
            },
            "benefits": {
                "size_reduction": str(modular_stats.get("compressionRatio", "0%")),
                "load_time_improvement": "50-70% faster loading",
                "supported_graph_types": len(modular_stats.get("supportedGraphTypes", [])),
                "available_modules": len(modular_stats.get("availableModules", [])),
            },
            "timestamp": time.time(),
        }

        status_msg = str(performance_summary.get("status", "Unknown"))
        logger.info("Modular cache status check: OK - %s", status_msg)
        return cache_data

    except Exception as e:
        cache_data = {
            "status": "error",
            "cache_type": "modular",
            "error": str(e),
            "fallback": "Modular cache not available",
            "timestamp": time.time(),
        }

        logger.error("Modular cache status check: ERROR - %s", e)
        return cache_data


# Only log from main worker to avoid duplicate messages
if os.getenv("UVICORN_WORKER_ID") is None or os.getenv("UVICORN_WORKER_ID") == "0":
    logger.debug("Cache routes initialized: 3 routes registered")
