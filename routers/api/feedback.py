"""
Feedback API Router
===================

API endpoint for user feedback submission:
- /api/feedback: Submit user feedback with captcha verification

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from models import FeedbackRequest
from services.auth.captcha_storage import get_captcha_storage
from services.redis.cache.redis_user_cache import user_cache
from utils.auth import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


@router.post('/feedback')
async def submit_feedback(
    req: FeedbackRequest,
    request: Request
):
    """
    Submit user feedback (bugs, features, issues).
    Feedback is logged to application logs for review.
    Includes captcha verification to prevent spam.
    """
    try:
        # Use Redis-based captcha storage (multi-server support)
        captcha_storage = get_captcha_storage()

        # Validate captcha first (anti-spam protection)
        # verify_and_remove() atomically verifies and removes (one-time use)
        is_valid, error_reason = captcha_storage.verify_and_remove(
            req.captcha_id,
            req.captcha
        )

        if not is_valid:
            if error_reason == "not_found":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Captcha expired or invalid. Please refresh."
                )
            elif error_reason == "incorrect":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Incorrect captcha code"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Captcha verification failed. Please refresh."
                )

        logger.debug("Captcha verified for feedback from user %s", req.user_id or 'anonymous')

        # Try to get user from JWT token if available (optional - allows anonymous feedback)
        # Use manual session management - close immediately after DB query
        user_id_from_db = None
        user_name_from_db = None
        try:
            # Try to get token from Authorization header first
            auth_header = request.headers.get('Authorization', '')
            token = None
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
            else:
                # Try to get token from cookies (how browser-based auth typically works)
                token = request.cookies.get('access_token')

            if token:
                payload = decode_access_token(token)
                user_id_from_token = payload.get("sub")
                if user_id_from_token:
                    # Use cache for user lookup (with database fallback)
                    current_user = user_cache.get_by_id(int(user_id_from_token))
                    if current_user:
                        user_id_from_db = current_user.id
                        user_name_from_db = current_user.name if hasattr(current_user, 'name') else None
        except Exception:
            # No valid token, continue as anonymous (this is OK for feedback)
            pass

        # Get user info (use from request if provided, otherwise from token, otherwise anonymous)
        user_id = req.user_id or (str(user_id_from_db) if user_id_from_db else 'anonymous')
        user_name = req.user_name or (user_name_from_db if user_name_from_db else 'Anonymous User')

        # Log feedback to application logs
        logger.info("[FEEDBACK] User: %s (%s)", user_name, user_id)
        logger.info("[FEEDBACK] Message: %s", req.message)

        return JSONResponse(
            status_code=200,
            content={
                'success': True,
                'message': 'Feedback submitted successfully'
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like 400 for invalid captcha) as-is
        raise
    except Exception as e:
        logger.error("Error processing feedback: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail='Failed to submit feedback. Please try again later.'
        ) from e
