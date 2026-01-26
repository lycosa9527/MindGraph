"""Frontend Logging API Router.

API endpoints for frontend log collection:
- /api/frontend_log: Single log entry
- /api/frontend_log_batch: Batch log entries

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging

from fastapi import APIRouter, HTTPException, Request

from models import FrontendLogRequest, FrontendLogBatchRequest
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter


logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


@router.post('/frontend_log')
async def frontend_log(req: FrontendLogRequest, request: Request):
    """
    Log single frontend message to backend console.
    Receives logs from browser and displays them in Python terminal.

    Rate limited to prevent log injection and DoS attacks.
    """
    # Rate limiting: 100 requests per minute per IP
    rate_limiter = RedisRateLimiter()

    client_ip = request.client.host if request.client else 'unknown'
    is_allowed, count, error_msg = rate_limiter.check_and_record(
        category='frontend_log',
        identifier=client_ip,
        max_attempts=100,  # 100 logs per minute per IP
        window_seconds=60
    )

    if not is_allowed:
        logger.warning("Frontend log rate limit exceeded for IP %s: %s attempts", client_ip, count)
        raise HTTPException(
            status_code=429,
            detail=f"Too many log requests. {error_msg}"
        )

    level_map = {
        'error': logging.ERROR,
        'warn': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }
    level = level_map.get(req.level.lower(), logging.INFO)

    # Create a dedicated frontend logger
    frontend_logger = logging.getLogger('frontend')
    frontend_logger.setLevel(logging.DEBUG)  # Accept all levels

    # Log message directly - Python logger will add its own timestamp
    # Don't include frontend timestamp to avoid duplication
    message = req.message

    # Security: Sanitize message to prevent log injection
    # Remove control characters and limit length
    message = ''.join(char for char in message if ord(char) >= 32 or char in '\n\r\t')
    if len(message) > 10000:  # Limit message length
        message = message[:10000] + "... [truncated]"

    # Log with clean formatting
    frontend_logger.log(level, message)

    return {'status': 'logged'}


@router.post('/frontend_log_batch')
async def frontend_log_batch(req: FrontendLogBatchRequest, request: Request):
    """
    Log batched frontend messages to backend console (efficient bulk logging).
    Receives multiple logs from browser and displays them in Python terminal.

    Rate limited to prevent log injection and DoS attacks.
    """
    # Rate limiting: 10 batches per minute per IP, max 50 logs per batch
    rate_limiter = RedisRateLimiter()

    client_ip = request.client.host if request.client else 'unknown'
    is_allowed, count, error_msg = rate_limiter.check_and_record(
        category='frontend_log_batch',
        identifier=client_ip,
        max_attempts=10,  # 10 batches per minute per IP
        window_seconds=60
    )

    if not is_allowed:
        logger.warning("Frontend log batch rate limit exceeded for IP %s: %s attempts", client_ip, count)
        raise HTTPException(
            status_code=429,
            detail=f"Too many log batch requests. {error_msg}"
        )

    # Validate batch size
    if req.batch_size > 50:
        raise HTTPException(
            status_code=400,
            detail="Batch size too large. Maximum 50 logs per batch."
        )

    level_map = {
        'error': logging.ERROR,
        'warn': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }

    # Create a dedicated frontend logger
    frontend_logger = logging.getLogger('frontend')
    frontend_logger.setLevel(logging.DEBUG)  # Accept all levels

    # Log batch header
    frontend_logger.info("=== FRONTEND LOG BATCH (%s logs) ===", req.batch_size)

    # Log each message in the batch
    for log_entry in req.logs:
        level = level_map.get(log_entry.level.lower(), logging.INFO)

        # Log message directly - Python logger will add its own timestamp
        # Don't include frontend timestamp to avoid duplication
        message = log_entry.message

        # Security: Sanitize message to prevent log injection
        # Remove control characters and limit length
        message = ''.join(char for char in message if ord(char) >= 32 or char in '\n\r\t')
        if len(message) > 10000:  # Limit message length
            message = message[:10000] + "... [truncated]"

        # Log to backend console
        frontend_logger.log(level, message)

    return {'status': 'logged', 'count': req.batch_size}
