from typing import
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.database import get_db
from models.auth import User
from models.messages import Messages, Language
from services.redis.redis_user_cache import user_cache
from utils.auth import get_current_user

"""
Avatar Management Endpoints
===========================

Avatar management endpoints:
- GET /api/auth/avatars - Get list of available avatars
- PUT /api/auth/avatar - Update user's avatar

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""




logger = logging.getLogger(__name__)

router = APIRouter()

# Available emoji avatars (matches frontend list - 200+ emojis)
AVAILABLE_AVATARS = [
    # Smileys & Faces
    '🐈‍⬛', '😀', '😃', '😄', '😁', '😊', '😉', '😍', '🤩', '😎', '🤗',
    '🙂', '😇', '🤔', '😋', '😌', '😏', '😴', '🤤', '😪', '😵',
    '🤐', '🤨', '🧐', '🤓', '🥳', '😮', '😯', '😲', '😱', '😭',
    '😓', '😤', '😠', '😡', '🤬', '🤯', '😳', '🥺', '😞', '😟',
    '🙁', '☹️', '😣', '😖', '😫', '😩', '🥱', '😑', '😶', '😐',
    '🤢', '🤮', '🤧', '😷', '🤒', '🤕', '🤑', '🤠', '😈', '👿',
    '👹', '👺', '🤡', '💩', '👻', '💀', '☠️', '👽', '👾', '🤖',
    '🎃', '😺', '😸', '😹', '😻', '😼', '😽', '🙀', '😿', '😾',
    # People & Gestures
    '👋', '🤚', '🖐️', '✋', '🖖', '👌', '🤏', '✌️', '🤞', '🤟',
    '🤘', '🤙', '👈', '👉', '👆', '🖕', '👇', '☝️', '👍', '👎',
    '✊', '👊', '🤛', '🤜', '👏', '🙌', '👐', '🤲', '🤝', '🙏',
    '✍️', '💪', '🦾', '🦿', '🦵', '🦶', '👂', '🦻', '👃', '🧠',
    '🫀', '🫁', '🦷', '🦴', '👀', '👁️', '👅', '👄', '💋', '👶',
    '👧', '🧒', '👦', '👩', '🧑', '👨', '👩‍🦱', '👨‍🦱', '👩‍🦰', '👨‍🦰',
    '👱‍♀️', '👱', '👩‍🦳', '👨‍🦳', '👩‍🦲', '👨‍🦲', '🧔', '👵', '🧓', '👴',
    # Animals & Nature
    '🦁', '🐯', '🐅', '🐆', '🐴', '🦄', '🦓', '🦌', '🦬', '🐮',
    '🐂', '🐃', '🐄', '🐷', '🐖', '🐗', '🐽', '🐏', '🐑', '🐐',
    '🐪', '🐫', '🦙', '🦒', '🐘', '🦣', '🦏', '🦛', '🐭', '🐁',
    '🐀', '🐹', '🐰', '🐇', '🐿️', '🦫', '🦔', '🦇', '🐻', '🐻‍❄️',
    '🐨', '🐼', '🦥', '🦦', '🦨', '🦘', '🦡', '🐾', '🦃', '🐔',
    '🐓', '🐣', '🐤', '🐥', '🐦', '🐧', '🕊️', '🦅', '🦆', '🦢',
    '🦉', '🦤', '🪶', '🦩', '🦚', '🦜', '🐸', '🐊', '🐢', '🦎',
    '🐍', '🐲', '🐉', '🦕', '🦖', '🐳', '🐋', '🐬', '🦭', '🐟',
    '🐠', '🐡', '🦈', '🐙', '🐚', '🐌', '🦋', '🐛', '🐜', '🐝',
    '🪲', '🐞', '🦗', '🪳', '🕷️', '🕸️', '🦂', '🦟', '🪰', '🪱',
    '🦠', '💐', '🌸', '💮', '🪷', '🏵️', '🌹', '🥀', '🌺', '🌻',
    '🌼', '🌷', '🪻', '🌱', '🪴', '🌲', '🌳', '🌴', '🌵', '🌶️',
    '🫑', '🌾', '🌿', '☘️', '🍀', '🍁', '🍂', '🍃', '🪹', '🪺',
    # Food & Drink
    '🍇', '🍈', '🍉', '🍊', '🍋', '🍌', '🍍', '🥭', '🍎', '🍏',
    '🍐', '🍑', '🍒', '🍓', '🫐', '🥝', '🍅', '🫒', '🥥', '🥑',
    '🍆', '🥔', '🥕', '🌽', '🥒', '🥬', '🥦', '🧄', '🧅', '🍄',
    '🥜', '🫘', '🌰', '🍞', '🥐', '🥖', '🫓', '🥨', '🥯', '🥞',
    '🧇', '🧈', '🍳', '🥚', '🧀', '🥓', '🥩', '🍗', '🍖', '🦴',
    '🌭', '🍔', '🍟', '🍕', '🥪', '🥙', '🧆', '🌮', '🌯', '🫔',
    '🥗', '🥘', '🫕', '🥫', '🍝', '🍜', '🍲', '🍛', '🍣', '🍱',
    '🥟', '🦪', '🍤', '🍙', '🍚', '🍘', '🍥', '🥠', '🥡', '🍢',
    '🍡', '🍧', '🍨', '🍦', '🥧', '🧁', '🍰', '🎂', '🍮', '🍭',
    '🍬', '🍫', '🍿', '🍩', '🍪', '🍯', '🥛', '🍼', '🫖', '☕️',
    '🍵', '🧃', '🥤', '🧋', '🍶', '🍺', '🍻', '🥂', '🍷', '🥃',
    '🍸', '🍹', '🧉', '🍾', '🧊',
    # Travel & Places
    '🗺️', '🧭', '🏔️', '⛰️', '🌋', '🗻', '🏕️', '🏖️', '🏜️', '🏝️',
    '🏞️', '🏟️', '🏛️', '🏗️', '🧱', '🪨', '🪵', '🛖', '🏘️', '🏚️',
    '🏠', '🏡', '🏢', '🏣', '🏤', '🏥', '🏦', '🏨', '🏩', '🏪',
    '🏫', '🏬', '🏭', '🏯', '🏰', '💒', '🗼', '🗽', '⛪', '🕌',
    '🛕', '🕍', '⛩️', '🕋', '⛲', '⛺', '🌁', '🌃', '🏙️', '🌄',
    '🌅', '🌆', '🌇', '🌉', '♨️', '🎠', '🎡', '🎢', '💈', '🎪',
    '🚂', '🚃', '🚄', '🚅', '🚆', '🚇', '🚈', '🚉', '🚊', '🚝',
    '🚞', '🚋', '🚌', '🚍', '🚎', '🚐', '🚑', '🚒', '🚓', '🚔',
    '🚕', '🚖', '🚗', '🚘', '🚙', '🚚', '🚛', '🚜', '🏎️', '🏍️',
    '🛵', '🦽', '🦼', '🛴', '🚲', '🛺', '🛸', '🚁', '✈️', '🛩️',
    '🛫', '🛬', '🪂', '💺', '🚀', '🚠', '🚡', '🛰️', '🚢', '⛵',
    '🛶', '🛥️', '🛳️', '⛴️', '🚤', '🛟',
    # Activities & Objects
    '🎯', '🎮', '🎰', '🎲', '🃏', '🀄', '🎴', '🎭', '🖼️', '🎨',
    '🧩', '🏸', '🎬', '🎤', '🎧', '🎼', '🎹', '🥁', '🪘', '🎷',
    '🎺', '🪗', '🎸', '🪕', '🎻', '🎳', '🧸', '🪅', '🪩', '🪆',
    '🎁', '🎀', '🎊', '🎉', '🎈', '🎂', '🎃', '🎄', '🎆', '🎇',
    '🧨', '✨', '🎊', '🎉', '🎈',
]


class AvatarResponse(BaseModel):
    id: str
    emoji: str


class UpdateAvatarRequest(BaseModel):
    avatar: str


@router.get("/avatars", response_model=List[AvatarResponse])
async def get_avatars():
    """
    Get list of available avatars

    Returns list of emoji avatars.
    """
    return [
        AvatarResponse(id=emoji, emoji=emoji)
        for emoji in AVAILABLE_AVATARS
    ]


@router.put("/avatar")
async def update_avatar(
    request: UpdateAvatarRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Update user's avatar

    Requires authentication.
    Avatar must be from the list of available avatars.
    """
    if request.avatar not in AVAILABLE_AVATARS:
        error_msg = Messages.error("avatar_not_found", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.avatar = request.avatar

    try:
        db.commit()
        user_cache.invalidate(user.id, user.phone)
        user_cache.cache_user(user)
        logger.info(f"User {user.id} updated avatar to {user.avatar}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update avatar for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update avatar"
        )

    success_msg = Messages.success("avatar_update_success", lang)
    return {
        "message": success_msg,
        "avatar": user.avatar
    }
