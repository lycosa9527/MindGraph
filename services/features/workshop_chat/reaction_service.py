"""
Reaction Service
==================

Emoji reaction operations on channel/topic messages.

Follows the same singleton-class pattern as the other workshop chat services.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from models.domain.workshop_chat import MessageReaction

logger = logging.getLogger(__name__)


class ReactionService:
    """Emoji reaction operations on messages."""

    @staticmethod
    def toggle_reaction(
        db: Session,
        message_id: int,
        user_id: int,
        emoji_name: str,
        emoji_code: str,
    ) -> Dict[str, Any]:
        """Add a reaction if it does not exist, remove it if it does.

        Returns ``{"action": "added"|"removed", ...}``.
        """
        existing = (
            db.query(MessageReaction)
            .filter(
                MessageReaction.message_id == message_id,
                MessageReaction.user_id == user_id,
                MessageReaction.emoji_name == emoji_name,
            )
            .first()
        )
        if existing:
            db.delete(existing)
            db.commit()
            return {
                "action": "removed",
                "message_id": message_id,
                "emoji_name": emoji_name,
                "emoji_code": emoji_code,
                "user_id": user_id,
            }

        reaction = MessageReaction(
            message_id=message_id,
            user_id=user_id,
            emoji_name=emoji_name,
            emoji_code=emoji_code,
        )
        db.add(reaction)
        db.commit()
        return {
            "action": "added",
            "message_id": message_id,
            "emoji_name": emoji_name,
            "emoji_code": emoji_code,
            "user_id": user_id,
        }

    @staticmethod
    def get_message_reactions(
        db: Session,
        message_id: int,
    ) -> List[Dict[str, Any]]:
        """Get grouped reactions for a single message."""
        rows = db.query(MessageReaction).filter(MessageReaction.message_id == message_id).all()
        return ReactionService._group_reactions(rows)

    @staticmethod
    def get_reactions_batch(
        db: Session,
        message_ids: List[int],
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Batch-fetch grouped reactions keyed by message_id."""
        if not message_ids:
            return {}
        rows = db.query(MessageReaction).filter(MessageReaction.message_id.in_(message_ids)).all()
        by_msg: Dict[int, list] = {}
        for row in rows:
            by_msg.setdefault(row.message_id, []).append(row)
        return {mid: ReactionService._group_reactions(rlist) for mid, rlist in by_msg.items()}

    @staticmethod
    def _group_reactions(
        rows: List[MessageReaction],
    ) -> List[Dict[str, Any]]:
        """Collapse individual reaction rows into grouped pills."""
        groups: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            key = row.emoji_name
            if key not in groups:
                groups[key] = {
                    "emoji_name": row.emoji_name,
                    "emoji_code": row.emoji_code,
                    "count": 0,
                    "user_ids": [],
                }
            groups[key]["count"] += 1
            groups[key]["user_ids"].append(row.user_id)
        return list(groups.values())


reaction_service = ReactionService()
