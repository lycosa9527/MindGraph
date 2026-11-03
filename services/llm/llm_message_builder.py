"""
LLM Message Builder
===================

Centralizes message building and RAG context injection logic.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Any, Dict, List, Optional

from services.llm.rag_context_state import is_implicit_rag_suppressed

logger = logging.getLogger(__name__)


class LLMMessageBuilder:
    """Builds chat messages with RAG context injection support."""

    @staticmethod
    def build_chat_messages(
        prompt: str = "",
        system_message: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build chat messages array from prompt/system_message or use provided messages.

        Args:
            prompt: User message/prompt (used if messages is not provided)
            system_message: Optional system message (used if messages is not provided)
            messages: Optional list of message dicts for multi-turn conversations.
                     If provided, overrides prompt and system_message.

        Returns:
            List of message dicts ready for LLM API
        """
        if messages is not None:
            # Multi-turn conversation: use provided messages directly
            # Make a copy to avoid mutating the original
            return list(messages)

        # Single-turn conversation: build from prompt and system_message
        chat_messages = []
        if system_message:
            chat_messages.append({"role": "system", "content": system_message})
        if prompt:
            chat_messages.append({"role": "user", "content": prompt})

        return chat_messages

    @staticmethod
    def extract_query_for_rag(messages: Optional[List[Dict[str, Any]]], prompt: str = "") -> str:
        """
        Extract query text from messages for RAG context retrieval.

        For multi-turn conversations, extracts from last user message.
        Handles multimodal content by extracting text portion.

        Args:
            messages: List of message dicts (if multi-turn)
            prompt: User prompt (if single-turn)

        Returns:
            Query string for RAG retrieval
        """
        if messages is not None:
            # Multi-turn conversation: extract from last user message
            last_user_msg = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "")
                    if isinstance(last_user_msg, list):
                        # Multimodal: extract text content
                        for item in last_user_msg:
                            if item.get("type") == "text":
                                last_user_msg = item.get("text", "")
                                break
                        else:
                            last_user_msg = ""
                    break
            return last_user_msg if last_user_msg else prompt

        # Single-turn conversation: use prompt directly
        return prompt

    @staticmethod
    async def inject_rag_context(
        messages: List[Dict[str, Any]],
        user_id: Optional[int],
        query: str,
        use_knowledge_base: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Inject RAG context into messages if enabled and user has knowledge base.

        Args:
            messages: List of message dicts (will be modified in place)
            user_id: User ID for knowledge base lookup
            query: Query string for RAG retrieval
            use_knowledge_base: Whether to enable RAG context injection

        Returns:
            Modified messages list with RAG context injected
        """
        if use_knowledge_base and user_id and query and not is_implicit_rag_suppressed():
            logger.debug("[LLMMessageBuilder] Personal knowledge is attached by the diagram workflow")
        return messages

    @staticmethod
    async def build_with_rag(
        prompt: str = "",
        system_message: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[int] = None,
        use_knowledge_base: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Build chat messages and inject RAG context if enabled.

        Convenience method that combines build_chat_messages and inject_rag_context.

        Args:
            prompt: User message/prompt (used if messages is not provided)
            system_message: Optional system message (used if messages is not provided)
            messages: Optional list of message dicts for multi-turn conversations
            user_id: User ID for knowledge base lookup
            use_knowledge_base: Whether to enable RAG context injection

        Returns:
            List of message dicts with RAG context injected (if enabled)
        """
        chat_messages = LLMMessageBuilder.build_chat_messages(
            prompt=prompt, system_message=system_message, messages=messages
        )

        query = LLMMessageBuilder.extract_query_for_rag(messages, prompt)

        if use_knowledge_base:
            chat_messages = await LLMMessageBuilder.inject_rag_context(
                messages=chat_messages,
                user_id=user_id,
                query=query,
                use_knowledge_base=use_knowledge_base,
            )

        return chat_messages

    @staticmethod
    async def enhance_prompt_for_streaming(prompt: str, user_id: Optional[int], use_knowledge_base: bool = True) -> str:
        """
        Enhance prompt with RAG context for streaming requests.

        This is a simplified version for streaming where we only enhance
        the prompt string (not full messages array).

        Args:
            prompt: User prompt string
            user_id: User ID for knowledge base lookup
            use_knowledge_base: Whether to enable RAG context injection

        Returns:
            Enhanced prompt string with RAG context (if enabled)
        """
        if use_knowledge_base and user_id and prompt and not is_implicit_rag_suppressed():
            logger.debug("[LLMMessageBuilder] Personal knowledge is attached by the diagram workflow")
        return prompt
