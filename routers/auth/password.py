"""
Password Reset Endpoint
========================

Password reset endpoint:
- /reset_password - Reset password with SMS verification

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.auth import User
from models.messages import Messages
from models.requests import ResetPasswordWithSMSRequest
from services.redis_user_cache import user_cache
from utils.auth import hash_password

from .dependencies import get_language_dependency
from .sms import _verify_and_consume_sms_code

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/reset_password")
async def reset_password_with_sms(
    request: ResetPasswordWithSMSRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
):
    """
    Reset password with SMS verification
    
    Allows users to reset their password using SMS verification.
    Also unlocks the account if it was locked.
    """
    # Find user (use cache with SQLite fallback)
    cached_user = user_cache.get_by_phone(request.phone)
    
    if not cached_user:
        error_msg = Messages.error("phone_not_registered_reset", lang)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_msg
        )
    
    # Verify SMS code
    _verify_and_consume_sms_code(
        request.phone,
        request.sms_code,
        "reset_password",
        db,
        lang
    )
    
    # Reload user from database for modification (cached users are detached)
    user = db.query(User).filter(User.id == cached_user.id).first()
    if not user:
        error_msg = Messages.error("phone_not_registered_reset", lang)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_msg
        )
    
    # Update password and unlock account
    # Note: We manually unlock instead of using reset_failed_attempts() because
    # password reset is not a login event, so last_login should not be updated
    user.password_hash = hash_password(request.new_password)
    user.failed_login_attempts = 0  # Unlock account
    user.locked_until = None
    
    # Write to SQLite FIRST
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[Auth] Failed to update password in SQLite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )
    
    # Invalidate and re-cache user (password changed)
    try:
        user_cache.invalidate(user.id, user.phone)
        user_cache.cache_user(user)
        logger.info(f"[Auth] Password reset and cache updated for user ID {user.id}")
    except Exception as e:
        logger.warning(f"[Auth] Failed to update cache after password reset: {e}")
    
    # Get client IP address
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    logger.info(f"Password reset via SMS for user: {user.phone} (ID: {user.id}, Method: SMS, IP: {client_ip})")
    
    return {
        "message": Messages.success("password_reset_success", lang),
        "phone": user.phone[:3] + "****" + user.phone[-4:]
    }


