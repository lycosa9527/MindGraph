"""
LLM Message Builder
===================

Centralizes message building and RAG context injection logic.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, List, Optional, Any
import logging

from config.database import SessionLocal
from services.llm.rag_service import get_rag_service

logger = logging.getLogger(__name__)


class LLMMessageBuilder:
    """Builds chat messages with RAG context injection support."""

    @staticmethod
    def build_chat_messages(
        prompt: str = '',
        system_message: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None
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
    def extract_query_for_rag(
        messages: Optional[List[Dict[str, Any]]],
        prompt: str = ''
    ) -> str:
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
                if msg.get('role') == 'user':
                    last_user_msg = msg.get('content', '')
                    if isinstance(last_user_msg, list):
                        # Multimodal: extract text content
                        for item in last_user_msg:
                            if item.get('type') == 'text':
                                last_user_msg = item.get('text', '')
                                break
                        else:
                            last_user_msg = ''
                    break
            return last_user_msg if last_user_msg else prompt

        # Single-turn conversation: use prompt directly
        return prompt

    @staticmethod
    def inject_rag_context(
        messages: List[Dict[str, Any]],
        user_id: Optional[int],
        query: str,
        use_knowledge_base: bool = True
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
        if not use_knowledge_base or not user_id or not query:
            return messages

        try:
            rag_service = get_rag_service()
            db = SessionLocal()
            try:
                # Check if user has knowledge base
                if not rag_service.has_knowledge_base(db, user_id):
                    return messages

                # Retrieve context
                context_chunks = rag_service.retrieve_context(
                    db=db,
                    user_id=user_id,
                    query=query,
                    top_k=5,
                    method='hybrid'
                )

                if not context_chunks:
                    return messages

                # Enhance prompt with context
                enhanced_prompt = rag_service.enhance_prompt(
                    _user_id=user_id,
                    prompt=query,
                    context_chunks=context_chunks,
                    max_context_length=2000
                )

                # Update the last user message with enhanced prompt
                for msg in reversed(messages):
                    if msg.get('role') == 'user':
                        content = msg.get('content')
                        if isinstance(content, str):
                            msg['content'] = enhanced_prompt
                        elif isinstance(content, list):
                            # Multimodal: update text content
                            for item in content:
                                if item.get('type') == 'text':
                                    item['text'] = enhanced_prompt
                                    break
                        break

                logger.debug(
                    "[LLMMessageBuilder] Injected RAG context: %s chunks",
                    len(context_chunks)
                )

            finally:
                db.close()

        except Exception as e:
            # If RAG fails, continue with original prompt
            logger.warning(
                "[LLMMessageBuilder] RAG failed, using original prompt: %s",
                e
            )

        return messages

    @staticmethod
    def build_with_rag(
        prompt: str = '',
        system_message: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[int] = None,
        use_knowledge_base: bool = True
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
        # Build messages
        chat_messages = LLMMessageBuilder.build_chat_messages(
            prompt=prompt,
            system_message=system_message,
            messages=messages
        )

        # Extract query for RAG
        query = LLMMessageBuilder.extract_query_for_rag(messages, prompt)

        # Inject RAG context if enabled
        if use_knowledge_base:
            chat_messages = LLMMessageBuilder.inject_rag_context(
                messages=chat_messages,
                user_id=user_id,
                query=query,
                use_knowledge_base=use_knowledge_base
            )

        return chat_messages

    @staticmethod
    def enhance_prompt_for_streaming(
        prompt: str,
        user_id: Optional[int],
        use_knowledge_base: bool = True
    ) -> str:
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
        if not use_knowledge_base or not user_id or not prompt:
            return prompt

        try:
            rag_service = get_rag_service()
            db = SessionLocal()
            try:
                # Check if user has knowledge base
                if not rag_service.has_knowledge_base(db, user_id):
                    return prompt

                # Retrieve context
                context_chunks = rag_service.retrieve_context(
                    db=db,
                    user_id=user_id,
                    query=prompt,
                    top_k=5,
                    method='hybrid'
                )

                if not context_chunks:
                    return prompt

                # Enhance prompt with context
                enhanced_prompt = rag_service.enhance_prompt(
                    _user_id=user_id,
                    prompt=prompt,
                    context_chunks=context_chunks,
                    max_context_length=2000
                )

                logger.debug(
                    "[LLMMessageBuilder] Injected RAG context for "
                    "streaming: %s chunks",
                    len(context_chunks)
                )

                return enhanced_prompt

            finally:
                db.close()

        except Exception as e:
            # If RAG fails, continue with original prompt
            logger.warning(
                "[LLMMessageBuilder] RAG failed for streaming, "
                "using original prompt: %s",
                e
            )
            return prompt
