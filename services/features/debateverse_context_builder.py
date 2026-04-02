"""
DebateVerse Context Builder
============================

Builds context-aware prompts for debate participants using LangChain agents
for argument analysis and flaw detection.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict, List, Optional
import logging

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
        if self._participants_by_id_cache is None:
            result = await self.db.execute(
                select(DebateParticipant).where(DebateParticipant.session_id == self.session_id)
            )
            rows = result.scalars().all()
            self._participants_by_id_cache = {p.id: p for p in rows}
        return self._participants_by_id_cache

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
            await self.db.execute(select(DebateSession).where(DebateSession.id == self.session_id))
        ).scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {self.session_id} not found")

        all_messages = (
            (
                await self.db.execute(
                    select(DebateMessage)
                    .where(DebateMessage.session_id == self.session_id)
                    .order_by(DebateMessage.created_at)
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

        system_prompt = get_debater_system_prompt(
            role=participant.role,
            side=participant.side or "",
            stage=stage,
            topic=session.topic,
            language=language,
            time_limit=1,
            opponent_arguments=analysis.get("opponent_summary", ""),
            attack_strategy=analysis.get("attack_strategy", ""),
            unaddressed_points=analysis.get("unaddressed_points", ""),
        )

        messages = [{"role": "system", "content": system_prompt}]

        for msg in all_messages:
            msg_participant = participants.get(msg.participant_id)
            if not msg_participant:
                continue

            speaker_info = f"[{msg_participant.name} ({msg_participant.side or 'judge'}, {msg_participant.role})]"
            stage_info = f"[{msg.stage}, Round {msg.round_number}]"

            if msg.participant_id == participant_id:
                messages.append(
                    {
                        "role": "assistant",
                        "content": f"{speaker_info} {stage_info}\n{msg.content}",
                    }
                )
            else:
                flaw_note = ""
                if msg.id in analysis.get("flawed_message_ids", []):
                    flaw = next(
                        (f for f in analysis.get("flaws", []) if f.get("message_id") == msg.id),
                        None,
                    )
                    if flaw:
                        flaw_note = f"\n[WEAKNESS: {flaw.get('flaw_type', 'unknown')} - {flaw.get('description', '')}]"

                messages.append(
                    {
                        "role": "user",
                        "content": f"{speaker_info} {stage_info}\n{msg.content}{flaw_note}",
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
            await self.db.execute(select(DebateSession).where(DebateSession.id == self.session_id))
        ).scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {self.session_id} not found")

        all_messages = (
            (
                await self.db.execute(
                    select(DebateMessage)
                    .where(DebateMessage.session_id == self.session_id)
                    .order_by(DebateMessage.created_at)
                )
            )
            .scalars()
            .all()
        )

        system_prompt = get_judge_system_prompt(current_stage=stage, topic=session.topic, language=language)

        messages = [{"role": "system", "content": system_prompt}]

        participants = await self._get_participants_by_id()

        for msg in all_messages:
            msg_participant = participants.get(msg.participant_id)
            if not msg_participant:
                continue

            speaker_info = f"[{msg_participant.name} ({msg_participant.side or 'judge'}, {msg_participant.role})]"
            stage_info = f"[{msg.stage}, Round {msg.round_number}]"

            messages.append(
                {
                    "role": "user" if msg_participant.id != judge_participant_id else "assistant",
                    "content": f"{speaker_info} {stage_info}\n{msg.content}",
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
                    .where(DebateMessage.session_id == self.session_id, DebateMessage.stage == "cross_exam")
                    .order_by(DebateMessage.created_at)
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
            msg_participant = participants.get(msg.participant_id)
            if not msg_participant:
                continue

            if msg.message_type == "cross_question":
                messages.append({"role": "user", "content": f"[Question] {msg.content}"})
            elif msg.message_type == "cross_answer":
                messages.append({"role": "assistant", "content": f"[Answer] {msg.content}"})

        return messages

    def _analyze_opponent_arguments(
        self,
        participant: DebateParticipant,
        stage: str,
        all_messages: List[DebateMessage],
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
        cache_key = f"{stage}_{participant.side}"
        if use_cache and cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        opponent_side = "negative" if participant.side == "affirmative" else "affirmative"
        opponent_messages = [
            msg
            for msg in all_messages
            if msg.participant_id != participant.id and self._get_message_side(msg.participant_id) == opponent_side
        ]

        opponent_summary = "\n".join(
            [
                f"- {msg.content[:200]}..." if len(msg.content) > 200 else f"- {msg.content}"
                for msg in opponent_messages[-5:]
            ]
        )

        flaws = []
        flawed_message_ids = []

        for msg in opponent_messages:
            if len(msg.content) < 50:
                flaws.append(
                    {
                        "message_id": msg.id,
                        "flaw_type": "weak_evidence",
                        "description": "Argument too brief, lacks detail",
                    }
                )
                flawed_message_ids.append(msg.id)

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
        participant = self._participants_by_id_cache.get(participant_id)
        return participant.side if participant else None

    async def _get_participant_arguments(self, participant_id: int) -> str:
        """Get summary of participant's arguments."""
        result = await self.db.execute(
            select(DebateMessage)
            .where(DebateMessage.session_id == self.session_id, DebateMessage.participant_id == participant_id)
            .order_by(DebateMessage.created_at)
        )
        messages = result.scalars().all()

        return "\n".join([msg.content[:200] for msg in messages[-3:]])

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

    def _get_unaddressed_points(self, participant: DebateParticipant, all_messages: List[DebateMessage]) -> str:
        """Get points that haven't been addressed yet."""
        my_team_messages = [
            msg for msg in all_messages if self._get_message_side(msg.participant_id) == participant.side
        ]

        unaddressed = []
        for msg in my_team_messages[-3:]:
            has_rebuttal = any(
                m.participant_id != msg.participant_id
                and m.created_at > msg.created_at
                and m.stage in ["rebuttal", "cross_exam"]
                for m in all_messages
            )
            if not has_rebuttal:
                unaddressed.append(msg.content[:100])

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
