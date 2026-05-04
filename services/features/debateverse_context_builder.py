"""
DebateVerse Context Builder
============================

Builds context-aware prompts for debate participants using LangChain agents
for argument analysis and flaw detection.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from collections.abc import Sequence
from typing import Any, Dict, List, Optional, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.debateverse import DebateMessage, DebateParticipant, DebateSession
from prompts.debateverse import (
    get_debater_system_prompt,
    get_judge_system_prompt,
    get_cross_exam_questioner_prompt,
    get_cross_exam_respondent_prompt,
)

logger = logging.getLogger(__name__)

_DEBATE_MESSAGES = DebateMessage.__table__
_DEBATE_SESSIONS = DebateSession.__table__
_DEBATE_PARTICIPANTS = DebateParticipant.__table__


class DebateVerseContextBuilder:
    """
    Builds context-aware prompts for debate participants.

    Uses LangChain agents to analyze debate history and identify logical flaws,
    then builds enriched prompts with attack strategies.
    """

    def __init__(self, session_id: str, db: AsyncSession):
        """
        Initialize context builder.

        Args:
            session_id: Debate session ID
            db: Database session
        """
        self.session_id = session_id
        self.db = db
        self._analysis_cache: Dict[str, Any] = {}
        self._participants_by_id_cache: Optional[Dict[int, DebateParticipant]] = None

    async def _get_participants_by_id(self) -> Dict[int, DebateParticipant]:
        """Load all participants for this session once (avoids N+1 in message loops)."""
        cached = self._participants_by_id_cache
        if cached is not None:
            return cached
        result = await self.db.execute(
            select(DebateParticipant).where(
                _DEBATE_PARTICIPANTS.c.session_id == self.session_id,
            )
        )
        rows = list(result.scalars().all())
        by_id: Dict[int, DebateParticipant] = {}
        for row in rows:
            by_id[cast(int, row.id)] = row
        self._participants_by_id_cache = by_id
        return by_id

    async def build_debater_messages(
        self,
        participant_id: int,
        stage: str,
        language: str = "zh",
        use_cache: bool = True,
    ) -> List[Dict[str, str]]:
        """
        Build full message array for a debater with context.

        Args:
            participant_id: Participant ID
            stage: Current stage (opening, rebuttal, cross_exam, closing)
            language: Language ('zh' or 'en')
            use_cache: Whether to use cached analysis

        Returns:
            List of message dicts ready for LLM service
        """
        participants = await self._get_participants_by_id()
        participant = participants.get(participant_id)
        if not participant:
            raise ValueError(f"Participant {participant_id} not found")

        session = (
            await self.db.execute(
                select(DebateSession).where(_DEBATE_SESSIONS.c.id == self.session_id),
            )
        ).scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {self.session_id} not found")

        all_messages = (
            (
                await self.db.execute(
                    select(DebateMessage)
                    .where(_DEBATE_MESSAGES.c.session_id == self.session_id)
                    .order_by(_DEBATE_MESSAGES.c.created_at)
                )
            )
            .scalars()
            .all()
        )

        analysis = self._analyze_opponent_arguments(
            participant=participant,
            stage=stage,
            all_messages=all_messages,
            use_cache=use_cache,
        )

        side_text = cast(Optional[str], participant.side)
        topic_text = cast(str, session.topic)
        role_text = cast(str, participant.role)
        system_prompt = get_debater_system_prompt(
            role=role_text,
            side=side_text or "",
            stage=stage,
            topic=topic_text,
            language=language,
            time_limit=1,
            opponent_arguments=analysis.get("opponent_summary", ""),
            attack_strategy=analysis.get("attack_strategy", ""),
            unaddressed_points=analysis.get("unaddressed_points", ""),
        )

        messages = [{"role": "system", "content": system_prompt}]

        for msg in all_messages:
            mid = cast(int, msg.id)
            msg_pid = cast(int, msg.participant_id)
            msg_content = cast(str, msg.content)
            msg_participant = participants.get(msg_pid)
            if not msg_participant:
                continue

            mp_name = cast(str, msg_participant.name)
            mp_side = cast(Optional[str], msg_participant.side)
            mp_role = cast(str, msg_participant.role)
            speaker_info = (
                f"[{mp_name} ({mp_side or 'judge'}, {mp_role})]"
            )
            stage_label = cast(str, msg.stage)
            rnd = cast(int, msg.round_number)
            stage_info = f"[{stage_label}, Round {rnd}]"

            if msg_pid == participant_id:
                messages.append(
                    {
                        "role": "assistant",
                        "content": f"{speaker_info} {stage_info}\n{msg_content}",
                    }
                )
            else:
                flaw_note = ""
                if mid in analysis.get("flawed_message_ids", []):
                    flaw = next(
                        (
                            f
                            for f in analysis.get("flaws", [])
                            if f.get("message_id") == mid
                        ),
                        None,
                    )
                    if flaw:
                        flaw_note = (
                            f"\n[WEAKNESS: {flaw.get('flaw_type', 'unknown')} - "
                            f"{flaw.get('description', '')}]"
                        )

                messages.append(
                    {
                        "role": "user",
                        "content": f"{speaker_info} {stage_info}\n{msg_content}{flaw_note}",
                    }
                )

        stage_instruction = self._get_stage_instruction(stage, language)
        attack_strategy = analysis.get("attack_strategy", "")

        if attack_strategy:
            messages.append(
                {
                    "role": "user",
                    "content": f"{stage_instruction}\n\n[ATTACK STRATEGY]\n{attack_strategy}",
                }
            )
        else:
            messages.append({"role": "user", "content": stage_instruction})

        return messages

    async def build_judge_messages(
        self, judge_participant_id: int, stage: str, language: str = "zh"
    ) -> List[Dict[str, str]]:
        """
        Build message array for judge.

        Args:
            judge_participant_id: Judge participant ID
            stage: Current stage
            language: Language ('zh' or 'en')

        Returns:
            List of message dicts ready for LLM service
        """
        session = (
            await self.db.execute(
                select(DebateSession).where(_DEBATE_SESSIONS.c.id == self.session_id),
            )
        ).scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {self.session_id} not found")

        all_messages = (
            (
                await self.db.execute(
                    select(DebateMessage)
                    .where(_DEBATE_MESSAGES.c.session_id == self.session_id)
                    .order_by(_DEBATE_MESSAGES.c.created_at)
                )
            )
            .scalars()
            .all()
        )

        topic_text = cast(str, session.topic)
        system_prompt = get_judge_system_prompt(
            current_stage=stage, topic=topic_text, language=language,
        )

        messages = [{"role": "system", "content": system_prompt}]

        participants = await self._get_participants_by_id()

        for msg in all_messages:
            msg_pid = cast(int, msg.participant_id)
            msg_content = cast(str, msg.content)
            msg_participant = participants.get(msg_pid)
            if not msg_participant:
                continue

            mp_name = cast(str, msg_participant.name)
            mp_side = cast(Optional[str], msg_participant.side)
            mp_role = cast(str, msg_participant.role)
            judge_row_id = cast(int, msg_participant.id)
            speaker_info = (
                f"[{mp_name} ({mp_side or 'judge'}, {mp_role})]"
            )
            stage_label = cast(str, msg.stage)
            rnd = cast(int, msg.round_number)
            stage_info = f"[{stage_label}, Round {rnd}]"

            messages.append(
                {
                    "role": (
                        "user" if judge_row_id != judge_participant_id else "assistant"
                    ),
                    "content": f"{speaker_info} {stage_info}\n{msg_content}",
                }
            )

        stage_instruction = self._get_judge_stage_instruction(stage, language)
        messages.append({"role": "user", "content": stage_instruction})

        return messages

    async def build_cross_exam_messages(
        self,
        questioner_id: int,
        respondent_id: int,
        question: Optional[str] = None,
        language: str = "zh",
    ) -> List[Dict[str, str]]:
        """
        Build message array for cross-examination Q&A.

        Args:
            questioner_id: Questioner participant ID
            respondent_id: Respondent participant ID
            question: Question text (if generating answer)
            language: Language ('zh' or 'en')

        Returns:
            List of message dicts ready for LLM service
        """
        participants = await self._get_participants_by_id()
        questioner = participants.get(questioner_id)
        respondent = participants.get(respondent_id)

        if not questioner or not respondent:
            raise ValueError("Questioner or respondent not found")

        cross_exam_messages = (
            (
                await self.db.execute(
                    select(DebateMessage)
                    .where(_DEBATE_MESSAGES.c.session_id == self.session_id)
                    .where(_DEBATE_MESSAGES.c.stage == "cross_exam")
                    .order_by(_DEBATE_MESSAGES.c.created_at),
                )
            )
            .scalars()
            .all()
        )

        if question:
            prompt = get_cross_exam_respondent_prompt(
                question=question,
                my_arguments=await self._get_participant_arguments(respondent_id),
                response_strategy="Avoid traps, reinforce position",
                language=language,
            )
        else:
            opponent_args = await self._get_participant_arguments(respondent_id)
            flaws = self._identify_flaws(opponent_args)

            prompt = get_cross_exam_questioner_prompt(
                opponent_arguments=opponent_args,
                identified_flaws=flaws,
                question_strategy="Expose contradictions, reveal weaknesses",
                language=language,
            )

        messages = [{"role": "system", "content": prompt}]

        for msg in cross_exam_messages:
            msg_type = cast(str, msg.message_type)
            msg_content = cast(str, msg.content)
            msg_pid = cast(int, msg.participant_id)
            msg_participant = participants.get(msg_pid)
            if not msg_participant:
                continue

            if msg_type == "cross_question":
                messages.append(
                    {"role": "user", "content": f"[Question] {msg_content}"},
                )
            elif msg_type == "cross_answer":
                messages.append(
                    {
                        "role": "assistant",
                        "content": f"[Answer] {msg_content}",
                    },
                )

        return messages

    def _analyze_opponent_arguments(
        self,
        participant: DebateParticipant,
        stage: str,
        all_messages: Sequence[DebateMessage],
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze opponent's arguments using LangChain agent.

        For now, uses simple analysis. Will be enhanced with LangChain agent later.

        Args:
            participant: Current participant
            stage: Current stage
            all_messages: All debate messages
            use_cache: Whether to use cached analysis

        Returns:
            Analysis dict with flaws, attack strategies, etc.
        """
        cache_key = f"{stage}_{cast(Optional[str], participant.side)}"
        if use_cache and cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        p_side = cast(Optional[str], participant.side)
        opponent_side = "negative" if p_side == "affirmative" else "affirmative"
        own_id = cast(int, participant.id)
        opponent_messages = [
            msg
            for msg in all_messages
            if cast(int, msg.participant_id) != own_id
            and self._get_message_side(cast(int, msg.participant_id))
            == opponent_side
        ]

        lines: List[str] = []
        for msg in opponent_messages[-5:]:
            text_body = cast(str, msg.content)
            item = (
                f"- {text_body[:200]}..."
                if len(text_body) > 200
                else f"- {text_body}"
            )
            lines.append(item)
        opponent_summary = "\n".join(lines)

        flaws = []
        flawed_message_ids = []

        for msg in opponent_messages:
            text_body = cast(str, msg.content)
            mid_msg = cast(int, msg.id)
            if len(text_body) < 50:
                flaws.append(
                    {
                        "message_id": mid_msg,
                        "flaw_type": "weak_evidence",
                        "description": "Argument too brief, lacks detail",
                    }
                )
                flawed_message_ids.append(mid_msg)

        attack_strategy = self._build_attack_strategy(flaws, opponent_messages)

        unaddressed_points = self._get_unaddressed_points(participant, all_messages)

        analysis = {
            "opponent_summary": opponent_summary,
            "flaws": flaws,
            "flawed_message_ids": flawed_message_ids,
            "attack_strategy": attack_strategy,
            "unaddressed_points": unaddressed_points,
        }

        if use_cache:
            self._analysis_cache[cache_key] = analysis

        return analysis

    def _get_message_side(self, participant_id: int) -> Optional[str]:
        """Get side for a participant from pre-loaded cache."""
        if self._participants_by_id_cache is None:
            return None
        row = self._participants_by_id_cache.get(participant_id)
        if row is None:
            return None
        return cast(Optional[str], row.side)

    async def _get_participant_arguments(self, participant_id: int) -> str:
        """Get summary of participant's arguments."""
        result = await self.db.execute(
            select(DebateMessage)
            .where(_DEBATE_MESSAGES.c.session_id == self.session_id)
            .where(_DEBATE_MESSAGES.c.participant_id == participant_id)
            .order_by(_DEBATE_MESSAGES.c.created_at),
        )
        msgs = result.scalars().all()
        excerpts = [
            cast(str, m.content)[:200] for m in msgs[-3:]
        ]
        return "\n".join(excerpts)

    def _identify_flaws(self, _arguments: str) -> str:
        """Identify flaws in arguments (simplified, will use LangChain agent)."""
        return "Check for contradictions, weak evidence, logical gaps"

    def _build_attack_strategy(self, flaws: List[Dict], _opponent_messages: List[DebateMessage]) -> str:
        """Build attack strategy based on identified flaws."""
        if not flaws:
            return "Focus on strengthening your position and addressing opponent's main points"

        strategies = []
        for flaw in flaws[:3]:
            flaw_type = flaw.get("flaw_type", "unknown")
            if flaw_type == "contradiction":
                strategies.append("Point out the contradiction in opponent's argument")
            elif flaw_type == "weak_evidence":
                strategies.append("Challenge the lack of evidence")
            elif flaw_type == "logical_gap":
                strategies.append("Expose the logical gap")

        return "\n".join(strategies) if strategies else "Focus on your strongest arguments"

    def _get_unaddressed_points(self, participant: DebateParticipant, all_messages: Sequence[DebateMessage]) -> str:
        """Get points that haven't been addressed yet."""
        p_side_own = cast(Optional[str], participant.side)
        my_team_messages = [
            msg
            for msg in all_messages
            if self._get_message_side(cast(int, msg.participant_id))
            == p_side_own
        ]

        unaddressed = []
        for msg in my_team_messages[-3:]:
            has_rebuttal = any(
                cast(int, m.participant_id) != cast(int, msg.participant_id)
                and cast(Any, m.created_at) > cast(Any, msg.created_at)
                and cast(str, m.stage) in ["rebuttal", "cross_exam"]
                for m in all_messages
            )
            if not has_rebuttal:
                unaddressed.append(cast(str, msg.content)[:100])

        return "\n".join(unaddressed) if unaddressed else "暂无"

    def _get_stage_instruction(self, stage: str, language: str) -> str:
        """Get instruction for current stage."""
        instructions = {
            "zh": {
                "opening": "请开始你的立论发言。",
                "rebuttal": "请开始你的驳论发言。",
                "cross_exam": "请提出你的问题。",
                "closing": "请开始你的总结陈词。",
            },
            "en": {
                "opening": "Please begin your opening statement.",
                "rebuttal": "Please begin your rebuttal.",
                "cross_exam": "Please ask your question.",
                "closing": "Please begin your closing statement.",
            },
        }
        return instructions.get(language, {}).get(stage, "请开始发言。")

    def _get_judge_stage_instruction(self, stage: str, language: str) -> str:
        """Get instruction for judge at current stage."""
        instructions = {
            "zh": {
                "coin_toss": "请执行掷硬币，决定发言顺序。",
                "opening": "请引导立论发言阶段。",
                "rebuttal": "请引导驳论发言阶段。",
                "cross_exam": "请引导交叉质询阶段。",
                "closing": "请引导总结陈词阶段。",
                "judgment": "请进行最终评判。",
            },
            "en": {
                "coin_toss": "Please execute coin toss to determine speaking order.",
                "opening": "Please guide the opening statements stage.",
                "rebuttal": "Please guide the rebuttal stage.",
                "cross_exam": "Please guide the cross-examination stage.",
                "closing": "Please guide the closing statements stage.",
                "judgment": "Please provide final judgment.",
            },
        }
        return instructions.get(language, {}).get(stage, "请继续。")
