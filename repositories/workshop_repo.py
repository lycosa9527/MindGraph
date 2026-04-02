"""Workshop & Chat async repository."""

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.domain.workshop_chat import (
    ChannelMember,
    ChatChannel,
    ChatMessage,
    ChatTopic,
    DirectMessage,
)

from .base import BaseRepository


class ChatChannelRepository(BaseRepository[ChatChannel]):
    model = ChatChannel

    async def get_by_organization(self, organization_id: int) -> Sequence[ChatChannel]:
        result = await self.session.execute(
            select(ChatChannel)
            .where(ChatChannel.organization_id == organization_id)
            .order_by(ChatChannel.display_order)
        )
        return result.scalars().all()

    async def get_with_members(self, channel_id: int) -> Optional[ChatChannel]:
        result = await self.session.execute(
            select(ChatChannel).options(selectinload(ChatChannel.members)).where(ChatChannel.id == channel_id)
        )
        return result.scalar_one_or_none()


class ChatMessageRepository(BaseRepository[ChatMessage]):
    model = ChatMessage

    async def get_by_channel(
        self,
        channel_id: int,
        *,
        before_id: Optional[int] = None,
        limit: int = 50,
    ) -> Sequence[ChatMessage]:
        stmt = select(ChatMessage).options(selectinload(ChatMessage.sender)).where(ChatMessage.channel_id == channel_id)
        if before_id is not None:
            stmt = stmt.where(ChatMessage.id < before_id)
        stmt = stmt.order_by(ChatMessage.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_channel(self, channel_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(ChatMessage).where(ChatMessage.channel_id == channel_id)
        )
        return result.scalar_one()


class ChatTopicRepository(BaseRepository[ChatTopic]):
    model = ChatTopic

    async def get_by_channel(self, channel_id: int) -> Sequence[ChatTopic]:
        result = await self.session.execute(
            select(ChatTopic).where(ChatTopic.channel_id == channel_id).order_by(ChatTopic.created_at.desc())
        )
        return result.scalars().all()


class DirectMessageRepository(BaseRepository[DirectMessage]):
    model = DirectMessage

    async def get_conversation(
        self,
        user_a: int,
        user_b: int,
        *,
        before_id: Optional[int] = None,
        limit: int = 50,
    ) -> Sequence[DirectMessage]:
        stmt = select(DirectMessage).where(
            ((DirectMessage.sender_id == user_a) & (DirectMessage.recipient_id == user_b))
            | ((DirectMessage.sender_id == user_b) & (DirectMessage.recipient_id == user_a))
        )
        if before_id is not None:
            stmt = stmt.where(DirectMessage.id < before_id)
        stmt = stmt.order_by(DirectMessage.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ChannelMemberRepository(BaseRepository[ChannelMember]):
    model = ChannelMember

    async def is_member(self, channel_id: int, user_id: int) -> bool:
        return await self.exists(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )


def get_channel_repo(session: AsyncSession) -> ChatChannelRepository:
    return ChatChannelRepository(session)


def get_message_repo(session: AsyncSession) -> ChatMessageRepository:
    return ChatMessageRepository(session)


def get_topic_repo(session: AsyncSession) -> ChatTopicRepository:
    return ChatTopicRepository(session)


def get_dm_repo(session: AsyncSession) -> DirectMessageRepository:
    return DirectMessageRepository(session)


def get_member_repo(session: AsyncSession) -> ChannelMemberRepository:
    return ChannelMemberRepository(session)
