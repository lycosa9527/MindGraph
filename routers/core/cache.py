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

from fastapi import APIRouter, Depends

from models.domain.auth import User
from utils.auth import get_current_user

# Lazy imports - moved to top level to fix C0415
try:
    from static.js.lazy_cache_manager import (
        get_cache_stats,
        get_performance_summary,
        is_cache_initialized
    )
    from static.js.modular_cache_python import (
        get_modular_cache_stats,
        get_modular_performance_summary
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
            stats = get_cache_stats()
            cache_data = {
                'status': 'initialized',
                'cache_strategy': 'lazy_loading_with_intelligent_caching',
                'files_loaded': stats['files_loaded'],
                'total_size_bytes': stats['total_memory_usage'],
                'total_size_kb': round(stats['memory_usage_mb'] * 1024, 2),
                'memory_usage_mb': stats['memory_usage_mb'],
                'max_memory_mb': stats['max_memory_mb'],
                'cache_hit_rate': round(stats['cache_hit_rate'], 1),
                'total_requests': stats['total_requests'],
                'cache_hits': stats['cache_hits'],
                'cache_misses': stats['cache_misses'],
                'average_load_time': round(stats['average_load_time'], 3),
                'performance_improvement': '90-95%',
                'optimization': 'Lazy loading + intelligent caching + memory optimization',
                'cache_ttl_seconds': 3600,
                'timestamp': time.time()
            }
            logger.info(
                "Lazy cache status check: OK - %s files loaded, hit rate: %.1f%%",
                stats['files_loaded'],
                stats['cache_hit_rate']
            )
            return cache_data

        cache_data = {
            'status': 'not_initialized',
            'error': 'Lazy loading JavaScript cache not properly initialized',
            'performance_impact': 'File I/O overhead per request (2-5 seconds)',
            'timestamp': time.time()
        }
        logger.warning("Lazy cache status check: FAILED - cache not initialized")
        return cache_data

    except Exception as e:
        cache_data = {
            'status': 'error',
            'error': str(e),
            'performance_impact': 'File I/O overhead per request (2-5 seconds)',
            'timestamp': time.time()
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

        stats = get_cache_stats()
        performance_data = {
            'status': 'success',
            'performance_summary': get_performance_summary(),
            'detailed_stats': {
                'cache_efficiency': {
                    'hit_rate_percent': round(stats['cache_hit_rate'], 1),
                    'total_requests': stats['total_requests'],
                    'cache_hits': stats['cache_hits'],
                    'cache_misses': stats['cache_misses']
                },
                'memory_management': {
                    'current_usage_mb': stats['memory_usage_mb'],
                    'max_allowed_mb': stats['max_memory_mb'],
                    'utilization_percent': round((stats['memory_usage_mb'] / stats['max_memory_mb']) * 100, 1)
                },
                'performance_metrics': {
                    'files_loaded': stats['files_loaded'],
                    'average_load_time_seconds': round(stats['average_load_time'], 3),
                    'total_load_time_seconds': round(stats['total_load_time'], 3)
                },
                'cache_strategy': {
                    'type': 'lazy_loading_with_intelligent_caching',
                    'ttl_seconds': 3600,
                    'cleanup_interval_seconds': 3600,
                    'memory_optimization': True,
                    'thread_safe': True
                }
            },
            'timestamp': time.time()
        }

        logger.info(
            "Cache performance check: OK - Hit rate: %.1f%%, Memory: %.1fMB",
            stats['cache_hit_rate'],
            stats['memory_usage_mb']
        )
        return performance_data

    except Exception as e:
        performance_data = {
            'status': 'error',
            'error': str(e),
            'timestamp': time.time()
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

        stats = get_modular_cache_stats()
        performance_summary = get_modular_performance_summary()

        cache_data = {
            'status': 'success',
            'cache_type': 'modular',
            'optimization': 'Option 3: Code Splitting by Graph Type',
            'performance_summary': performance_summary,
            'detailed_stats': {
                'base_cache': {
                    'files_loaded': stats.get('files_loaded', 0),
                    'total_size_bytes': stats.get('total_memory_usage', 0),
                    'cache_hit_rate_percent': stats.get('cache_hit_rate', 0)
                },
                'modular_stats': stats.get('modular', {})
            },
            'benefits': {
                'size_reduction': stats.get('modular', {}).get('compressionRatio', '0%'),
                'load_time_improvement': '50-70% faster loading',
                'supported_graph_types': len(stats.get('modular', {}).get('supportedGraphTypes', [])),
                'available_modules': len(stats.get('modular', {}).get('availableModules', []))
            },
            'timestamp': time.time()
        }

        status_msg = performance_summary.get('status', 'Unknown')
        logger.info("Modular cache status check: OK - %s", status_msg)
        return cache_data

    except Exception as e:
        cache_data = {
            'status': 'error',
            'cache_type': 'modular',
            'error': str(e),
            'fallback': 'Modular cache not available',
            'timestamp': time.time()
        }

        logger.error("Modular cache status check: ERROR - %s", e)
        return cache_data

# Only log from main worker to avoid duplicate messages
if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
    logger.debug("Cache routes initialized: 3 routes registered")
