"""
DebateVerse Service
===================

Core service for orchestrating debate sessions, managing stages, and generating
debater responses using LLM service.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import UTC, datetime
from typing import Dict, Optional
import logging
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.debateverse import DebateSession, DebateParticipant, DebateMessage
from services.features.debateverse_context_builder import DebateVerseContextBuilder
from services.llm import llm_service

logger = logging.getLogger(__name__)


class DebateVerseService:
    """
    Core service for managing debate sessions and orchestrating debate flow.
    """

    def __init__(self, session_id: str, db: AsyncSession):
        """
        Initialize debate service.

        Args:
            session_id: Debate session ID
            db: Database session
        """
        self.session_id = session_id
        self.db = db
        self.context_builder = DebateVerseContextBuilder(session_id, db)

    async def create_debate_session(
        self,
        topic: str,
        user_id: int,
        llm_assignments: Dict[str, str],
        debate_format: str = "us_parliamentary",
    ) -> DebateSession:
        """
        Create a new debate session with AI participants.

        Args:
            topic: Debate topic
            user_id: User ID who created the session
            llm_assignments: Dict mapping roles to LLM models
                Format: {
                    'affirmative_1': 'qwen',
                    'affirmative_2': 'deepseek',
                    'negative_1': 'doubao',
                    'negative_2': 'kimi',
                    'judge': 'deepseek'
                }
            debate_format: Debate format (default: 'us_parliamentary')

        Returns:
            Created DebateSession
        """
        session = DebateSession(
            topic=topic,
            format=debate_format,
            user_id=user_id,
            current_stage="setup",
            status="pending",
        )
        self.db.add(session)
        await self.db.flush()

        participants = []

        for role in ["affirmative_1", "affirmative_2"]:
            model_id = llm_assignments.get(role, "qwen")
            participant = DebateParticipant(
                session_id=session.id,
                is_ai=True,
                role=role,
                side="affirmative",
                model_id=model_id,
                name=self._get_model_display_name(model_id),
            )
            participants.append(participant)

        for role in ["negative_1", "negative_2"]:
            model_id = llm_assignments.get(role, "doubao")
            participant = DebateParticipant(
                session_id=session.id,
                is_ai=True,
                role=role,
                side="negative",
                model_id=model_id,
                name=self._get_model_display_name(model_id),
            )
            participants.append(participant)

        judge_model = llm_assignments.get("judge", "deepseek")
        judge = DebateParticipant(
            session_id=session.id,
            is_ai=True,
            role="judge",
            side=None,
            model_id=judge_model,
            name=self._get_model_display_name(judge_model),
        )
        participants.append(judge)

        self.db.add_all(participants)
        await self.db.commit()

        logger.info("Created debate session %s with topic: %s", session.id, topic)
        return session

    async def coin_toss(self) -> str:
        """
        Execute coin toss to determine speaking order.

        Note: This only determines the result. Stage should be set to 'coin_toss'
        before calling this, and advanced to 'opening' after user clicks next.

        Returns:
            'affirmative_first' or 'negative_first'
        """
        result = random.choice(["affirmative_first", "negative_first"])

        session = (
            await self.db.execute(select(DebateSession).where(DebateSession.id == self.session_id))
        ).scalar_one_or_none()
        if session:
            session.coin_toss_result = result
            if session.status != "active":
                session.status = "active"
            if not session.started_at:
                session.started_at = datetime.now(tz=UTC)
            await self.db.commit()

        logger.info("Coin toss result for session %s: %s", self.session_id, result)
        return result

    async def get_next_speaker(self, stage: str) -> Optional[DebateParticipant]:
        """
        Determine who speaks next based on stage and round structure.

        Args:
            stage: Current stage

        Returns:
            Next speaker participant or None if stage complete
        """
        session = (
            await self.db.execute(select(DebateSession).where(DebateSession.id == self.session_id))
        ).scalar_one_or_none()
        if not session:
            return None

        stage_messages = (
            (
                await self.db.execute(
                    select(DebateMessage)
                    .where(DebateMessage.session_id == self.session_id, DebateMessage.stage == stage)
                    .order_by(DebateMessage.round_number, DebateMessage.created_at)
                )
            )
            .scalars()
            .all()
        )

        if stage == "opening":
            if not stage_messages:
                return await self._get_participant_by_role("affirmative_1")
            if len(stage_messages) == 1:
                return await self._get_participant_by_role("negative_1")
            return None

        if stage == "rebuttal":
            if not stage_messages:
                return await self._get_participant_by_role("affirmative_2")
            if len(stage_messages) == 1:
                return await self._get_participant_by_role("negative_2")
            return None

        if stage == "cross_exam":
            round_1_complete = False
            for m in stage_messages:
                if m.message_type == "cross_answer":
                    participant = await self._get_participant_by_id(m.participant_id)
                    if participant is not None and participant.role == "negative_1":
                        round_1_complete = True
                        break

            if not round_1_complete:
                last_msg = stage_messages[-1] if stage_messages else None
                if not last_msg or last_msg.message_type == "cross_answer":
                    return await self._get_participant_by_role("affirmative_2")
                return await self._get_participant_by_role("negative_1")

            now_utc = datetime.now(tz=UTC)
            round_2_messages = [
                m
                for m in stage_messages
                if (m.created_at.replace(tzinfo=UTC) if m.created_at.tzinfo is None else m.created_at.astimezone(UTC))
                > now_utc
            ]
            last_msg = round_2_messages[-1] if round_2_messages else None
            if not last_msg or last_msg.message_type == "cross_answer":
                return await self._get_participant_by_role("negative_2")
            return await self._get_participant_by_role("affirmative_1")

        if stage == "closing":
            if not stage_messages:
                return await self._get_participant_by_role("affirmative_1")
            if len(stage_messages) == 1:
                return await self._get_participant_by_role("negative_1")
            return None

        return None

    async def generate_debater_response(self, participant_id: int, stage: str, language: str = "zh") -> str:
        """
        Generate AI debater response using assigned LLM.

        Args:
            participant_id: Participant ID
            stage: Current stage
            language: Language ('zh' or 'en')

        Returns:
            Generated response content
        """
        participant = (
            await self.db.execute(select(DebateParticipant).where(DebateParticipant.id == participant_id))
        ).scalar_one_or_none()
        if not participant or not participant.is_ai:
            raise ValueError(f"Participant {participant_id} is not an AI debater")

        messages = await self.context_builder.build_debater_messages(
            participant_id=participant_id, stage=stage, language=language
        )

        model = participant.model_id or "qwen"

        enable_thinking = model.lower() != "kimi"

        logger.info(
            "Generating response for %s (%s) in stage %s",
            participant.name,
            model,
            stage,
        )

        response_content = ""
        async for chunk in llm_service.chat_stream(
            messages=messages,
            model=model,
            temperature=0.7,
            max_tokens=2000,
            enable_thinking=enable_thinking,
            yield_structured=True,
            user_id=None,
            request_type="debateverse",
            endpoint_path=f"/api/debateverse/sessions/{self.session_id}/messages",
        ):
            if isinstance(chunk, dict):
                if chunk.get("type") == "token":
                    response_content += chunk.get("content", "")

        (await self.db.execute(select(DebateSession).where(DebateSession.id == self.session_id))).scalar_one_or_none()
        round_number = await self.get_next_round_number(stage)

        message = DebateMessage(
            session_id=self.session_id,
            participant_id=participant_id,
            content=response_content,
            stage=stage,
            round_number=round_number,
            message_type=self.get_message_type_for_stage(stage),
        )
        self.db.add(message)
        await self.db.commit()

        logger.info(
            "Generated response for %s: %s chars",
            participant.name,
            len(response_content),
        )
        return response_content

    async def generate_judge_commentary(self, stage: str, language: str = "zh") -> str:
        """
        Generate judge's commentary for current stage.

        Args:
            stage: Current stage
            language: Language ('zh' or 'en')

        Returns:
            Judge's commentary
        """
        judge = await self._get_participant_by_role("judge")
        if not judge:
            raise ValueError("Judge not found")

        messages = await self.context_builder.build_judge_messages(
            judge_participant_id=judge.id, stage=stage, language=language
        )

        model = judge.model_id or "deepseek"

        enable_thinking = model.lower() != "kimi"

        logger.info("Generating judge commentary for stage %s", stage)

        response_content = ""
        async for chunk in llm_service.chat_stream(
            messages=messages,
            model=model,
            temperature=0.6,
            max_tokens=1000,
            enable_thinking=enable_thinking,
            yield_structured=True,
            request_type="debateverse",
            endpoint_path=f"/api/debateverse/sessions/{self.session_id}/judge",
        ):
            if isinstance(chunk, dict):
                if chunk.get("type") == "token":
                    response_content += chunk.get("content", "")

        round_number = await self.get_next_round_number(stage)
        message = DebateMessage(
            session_id=self.session_id,
            participant_id=judge.id,
            content=response_content,
            stage=stage,
            round_number=round_number,
            message_type="judgment" if stage == "judgment" else stage,
        )
        self.db.add(message)
        await self.db.commit()

        return response_content

    async def advance_stage(self, new_stage: str) -> bool:
        """
        Advance debate to next stage.

        Args:
            new_stage: New stage to advance to

        Returns:
            True if advanced successfully
        """
        session = (
            await self.db.execute(select(DebateSession).where(DebateSession.id == self.session_id))
        ).scalar_one_or_none()
        if not session:
            return False

        valid_transitions = {
            "setup": ["coin_toss"],
            "coin_toss": ["opening"],
            "opening": ["rebuttal"],
            "rebuttal": ["cross_exam"],
            "cross_exam": ["closing"],
            "closing": ["judgment"],
            "judgment": ["completed"],
        }

        if new_stage not in valid_transitions.get(session.current_stage, []):
            logger.warning("Invalid stage transition: %s → %s", session.current_stage, new_stage)
            return False

        session.current_stage = new_stage
        if new_stage == "completed":
            session.status = "completed"
            session.completed_at = datetime.now(tz=UTC)

        await self.db.commit()
        logger.info("Advanced session %s to stage %s", self.session_id, new_stage)
        return True

    async def _get_participant_by_role(self, role: str) -> Optional[DebateParticipant]:
        """Get participant by role."""
        return (
            await self.db.execute(
                select(DebateParticipant).where(
                    DebateParticipant.session_id == self.session_id,
                    DebateParticipant.role == role,
                )
            )
        ).scalar_one_or_none()

    async def _get_participant_by_id(self, participant_id: int) -> Optional[DebateParticipant]:
        """Get participant by ID."""
        return (
            await self.db.execute(select(DebateParticipant).where(DebateParticipant.id == participant_id))
        ).scalar_one_or_none()

    async def get_next_round_number(self, stage: str) -> int:
        """Get next round number for stage."""
        result = await self.db.execute(
            select(DebateMessage.round_number)
            .where(DebateMessage.session_id == self.session_id, DebateMessage.stage == stage)
            .order_by(DebateMessage.round_number.desc())
        )
        max_round = result.first()

        return (max_round[0] if max_round else 0) + 1

    def get_message_type_for_stage(self, stage: str) -> str:
        """Get message type for stage."""
        mapping = {
            "coin_toss": "coin_toss",
            "opening": "opening",
            "rebuttal": "rebuttal",
            "cross_exam": "cross_question",
            "closing": "closing",
            "judgment": "judgment",
        }
        return mapping.get(stage, stage)

    def _get_model_display_name(self, model_id: str) -> str:
        """Get display name for model."""
        names = {
            "qwen": "Qwen",
            "doubao": "Doubao",
            "deepseek": "DeepSeek",
            "kimi": "Kimi",
        }
        return names.get(model_id, model_id.capitalize())
