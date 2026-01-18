"""
Base Node Palette Generator
============================

Shared logic for all diagram-specific palette generators.
"""
from abc import ABC, abstractmethod
from difflib import SequenceMatcher
from typing import Optional, Dict, Any, Tuple, AsyncGenerator
import logging
import re
import time

from services.llm import llm_service

"""
base palette generator module.

Shared logic for all diagram-specific palette generators.

Features:
- Concurrent multi-LLM streaming
- Real-time deduplication
- Progressive node rendering
- Session management
- Temperature-based diversity

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)


class BasePaletteGenerator(ABC):
    """
    Base class for all diagram-specific node palette generators.

    Architecture:
    - Uses llm_service.stream_progressive() for concurrent token streaming
    - 3 LLMs (qwen, deepseek, doubao) fire simultaneously (Hunyuan disabled, Kimi removed due to Volcengine load issues)
    - Nodes render progressively as tokens arrive from any LLM
    - Deduplication across all batches and LLMs
    - Subclasses override _build_prompt() for diagram-specific generation
    """

    def __init__(self):
        """Initialize base palette generator"""
        self.llm_service = llm_service
        # NOTE: Hunyuan disabled due to 5 concurrent connection limit
        # NOTE: Kimi removed from node palette - Volcengine server cannot handle load
        self.llm_models = ['qwen', 'deepseek', 'doubao']

        # Session storage
        self.generated_nodes = {}  # session_id -> List[Dict]
        self.seen_texts = {}  # session_id -> Set[str] (normalized)
        self.session_start_times = {}  # session_id -> timestamp
        self.batch_counts = {}  # session_id -> int (total batches)

        logger.debug("[NodePalette-%s] Initialized with concurrent multi-LLM architecture",
                   self.__class__.__name__)
        logger.debug("[NodePalette-%s] LLMs: %s",
                   self.__class__.__name__, ', '.join(self.llm_models))

    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        mode: Optional[str] = None,  # For tab-enabled diagrams (double_bubble_map, multi_flow_map)
        stage: Optional[str] = None,  # For staged generation (tree_map, flow_map, brace_map)
        stage_data: Optional[Dict[str, Any]] = None,  # Stage-specific data
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch of nodes using 3 LLMs (qwen, deepseek, doubao) with concurrent token streaming.

        Nodes render progressively as tokens arrive from any LLM!

        Args:
            session_id: Unique session identifier
            center_topic: Center node text from diagram
            educational_context: Educational context (grade, subject, etc.)
            nodes_per_llm: Nodes to request from each LLM (default: 15)
            endpoint_path: API endpoint path for token tracking (e.g., '/thinking_mode/node_palette/start')

        Yields:
            Dict events:
            - {'event': 'batch_start', 'batch_number': 1, 'llm_count': 4}
            - {'event': 'node_generated', 'node': {...}}
            - {'event': 'llm_complete', 'llm': 'qwen', 'unique_nodes': 12, ...}
            - {'event': 'batch_complete', 'total_unique': 45, ...}
        """
        # Track session
        if session_id not in self.session_start_times:
            self.session_start_times[session_id] = time.time()
            self.batch_counts[session_id] = 0
            logger.debug("[NodePalette] New session: %s | Topic: '%s'", session_id[:8], center_topic)

        batch_num = self.batch_counts[session_id] + 1
        self.batch_counts[session_id] = batch_num

        total_before = len(self.generated_nodes.get(session_id, []))
        logger.debug("[NodePalette] Batch %d starting | Session: %s | Topic: '%s'",
                   batch_num, session_id[:8], center_topic)

        # Yield batch start
        yield {
            'event': 'batch_start',
            'batch_number': batch_num,
            'llm_count': len(self.llm_models),
            'nodes_per_llm': nodes_per_llm
        }

        # Build prompt using diagram-specific logic (subclass implements this)
        prompt = self._build_prompt  # pylint: disable=protected-access(center_topic, educational_context, nodes_per_llm, batch_num)
        system_message = self._get_system_message  # pylint: disable=protected-access(educational_context, center_topic)

        # Get temperature for diversity
        temperature = self._get_temperature_for_batch  # pylint: disable=protected-access(batch_num)

        batch_start_time = time.time()
        llm_stats = {}

        # Track current lines being built for each LLM
        current_lines = {llm: "" for llm in self.llm_models}
        llm_unique_counts = {llm: 0 for llm in self.llm_models}
        llm_duplicate_counts = {llm: 0 for llm in self.llm_models}

        # Round-robin buffering: collect nodes from each LLM and yield in interleaved order
        # This ensures users see nodes from all LLMs mixed together, not grouped by LLM
        pending_nodes = {llm: [] for llm in self.llm_models}
        llm_active = {llm: True for llm in self.llm_models}  # Track which LLMs are still streaming
        llm_yield_order = self.llm_models.copy()  # Round-robin order
        next_llm_index = 0

        # 🚀 CONCURRENT TOKEN STREAMING - 3 LLMs fire simultaneously (qwen, deepseek, doubao)!
        logger.debug("[NodePalette] Streaming from %d LLMs with progressive rendering (round-robin interleaving)...", len(self.llm_models))

        async for chunk in self.llm_service.stream_progressive(
            prompt=prompt,
            models=self.llm_models,
            temperature=temperature,
            max_tokens=500,
            timeout=20.0,
            system_message=system_message,
            # Token tracking parameters
            user_id=user_id,
            organization_id=organization_id,
            request_type='node_palette',
            diagram_type=diagram_type,
            endpoint_path=endpoint_path or '/thinking_mode/node_palette/start',
            session_id=session_id
        ):
            event = chunk['event']
            llm_name = chunk['llm']

            if event == 'token':
                # Accumulate tokens into lines
                token = chunk['token']
                current_lines[llm_name] += token

                # Check if we have complete line(s)
                if '\n' in current_lines[llm_name]:
                    lines = current_lines[llm_name].split('\n')
                    current_lines[llm_name] = lines[-1]  # Keep incomplete part

                    # Process each complete line
                    for line in lines[:-1]:
                        line = line.strip()
                        if not line:
                            continue

                        # Clean node text
                        node_text = line.lstrip('0123456789.-、）) ').strip()

                        if not node_text or len(node_text) < 2:
                            continue

                        # Deduplicate
                        is_unique, match_type, similarity = self._deduplicate_node  # pylint: disable=protected-access(node_text, session_id)

                        if is_unique:
                            # UNIQUE NODE - add to round-robin buffer for interleaved yielding
                            node = {
                                'id': f"{session_id}_{llm_name}_{batch_num}_{llm_unique_counts[llm_name]}",
                                'text': node_text,
                                'source_llm': llm_name,
                                'batch_number': batch_num,
                                'relevance_score': 0.8,
                                'selected': False
                            }

                            # Verbose logging for streaming nodes (DEBUG level - very frequent)
                            logger.debug(
                                "[NodePalette-Stream] Node generated | LLM: %s | Batch: %d | ID: %s | Text: '%s'",
                                llm_name, batch_num, node['id'], node_text[:50] + ('...' if len(node_text) > 50 else '')
                            )

                            # Store
                            if session_id not in self.generated_nodes:
                                self.generated_nodes[session_id] = []
                            self.generated_nodes[session_id].append(node)

                            # Add to round-robin buffer instead of yielding immediately
                            pending_nodes[llm_name].append({
                                'event': 'node_generated',
                                'node': node
                            })

                            # Yield nodes in round-robin order (ensures interleaving)
                            # Yield up to 4 nodes (one from each LLM if available)
                            for _ in range(len(self.llm_models)):
                                llm = llm_yield_order[next_llm_index]
                                next_llm_index = (next_llm_index + 1) % len(llm_yield_order)

                                if len(pending_nodes[llm]) > 0:
                                    yield pending_nodes[llm].pop(0)

                            # If no nodes yielded (all buffers empty), don't block
                            # The next node arrival will trigger another round-robin cycle

                            llm_unique_counts[llm_name] += 1
                        else:
                            llm_duplicate_counts[llm_name] += 1

            elif event == 'complete':
                # LLM stream complete - mark as inactive and yield any remaining pending nodes
                llm_active[llm_name] = False

                # LLM stream complete - process any remaining text
                if current_lines[llm_name].strip():
                    node_text = current_lines[llm_name].lstrip('0123456789.-、）) ').strip()
                    if node_text and len(node_text) >= 2:
                        is_unique, match_type, similarity = self._deduplicate_node  # pylint: disable=protected-access(node_text, session_id)
                        if is_unique:
                            node = {
                                'id': f"{session_id}_{llm_name}_{batch_num}_{llm_unique_counts[llm_name]}",
                                'text': node_text,
                                'source_llm': llm_name,
                                'batch_number': batch_num,
                                'relevance_score': 0.8,
                                'selected': False
                            }

                            # Verbose logging for final node in stream (DEBUG level - per-LLM)
                            logger.debug(
                                "[NodePalette-Complete] Final node | LLM: %s | Batch: %d | ID: %s | Text: '%s'",
                                llm_name, batch_num, node['id'], node_text[:50] + ('...' if len(node_text) > 50 else '')
                            )

                            if session_id not in self.generated_nodes:
                                self.generated_nodes[session_id] = []
                            self.generated_nodes[session_id].append(node)

                            # Add to round-robin buffer (final node from this LLM)
                            pending_nodes[llm_name].append({
                                'event': 'node_generated',
                                'node': node
                            })

                            # Yield any pending nodes in round-robin order
                            for _ in range(len(self.llm_models)):
                                llm = llm_yield_order[next_llm_index]
                                next_llm_index = (next_llm_index + 1) % len(llm_yield_order)

                                if len(pending_nodes[llm]) > 0:
                                    yield pending_nodes[llm].pop(0)

                            llm_unique_counts[llm_name] += 1

                # Record stats for this LLM
                llm_stats[llm_name] = {
                    'unique': llm_unique_counts[llm_name],
                    'duplicates': llm_duplicate_counts[llm_name],
                    'duration': chunk.get('duration', 0),
                    'token_count': chunk.get('token_count', 0),
                    'success': True
                }

                # Yield any remaining pending nodes from this LLM before completing
                while len(pending_nodes[llm_name]) > 0:
                    yield pending_nodes[llm_name].pop(0)

                # Yield llm_complete event
                yield {
                    'event': 'llm_complete',
                    'llm': llm_name,
                    'unique_nodes': llm_unique_counts[llm_name],
                    'duplicates': llm_duplicate_counts[llm_name],
                    'duration': chunk.get('duration', 0),
                    'success': True
                }

                logger.debug(
                    "[NodePalette] %s batch %d complete | Unique: %d | Duplicates: %d | Time: %.2fs",
                    llm_name, batch_num, llm_unique_counts[llm_name],
                    llm_duplicate_counts[llm_name], chunk.get('duration', 0)
                )

                # After LLM completes, yield any remaining nodes from other LLMs in round-robin
                for _ in range(len(self.llm_models)):
                    llm = llm_yield_order[next_llm_index]
                    next_llm_index = (next_llm_index + 1) % len(llm_yield_order)

                    if len(pending_nodes[llm]) > 0:
                        yield pending_nodes[llm].pop(0)

            elif event == 'error':
                # LLM failed - categorize the error type
                error_msg = chunk.get('error', 'Unknown error')
                error_type = 'unknown'

                # Detect error type from message
                error_lower = error_msg.lower()
                if 'rate' in error_lower or '429' in error_lower or '2003' in error_lower or 'limit' in error_lower:
                    error_type = 'rate_limit'
                elif 'content' in error_lower or 'filter' in error_lower or 'inspection' in error_lower:
                    error_type = 'content_filter'
                elif 'timeout' in error_lower:
                    error_type = 'timeout'

                logger.error("[NodePalette] %s stream error (%s): %s", llm_name, error_type, error_msg)

                llm_stats[llm_name] = {
                    'unique': llm_unique_counts[llm_name],
                    'duplicates': llm_duplicate_counts[llm_name],
                    'duration': chunk.get('duration', 0),
                    'error': error_msg,
                    'error_type': error_type,
                    'success': False
                }

                # Yield llm_error event for frontend tracking
                yield {
                    'event': 'llm_error',
                    'llm': llm_name,
                    'error': error_msg,
                    'error_type': error_type,
                    'nodes_before_error': llm_unique_counts[llm_name]
                }

        # Batch complete
        batch_duration = time.time() - batch_start_time
        total_after = len(self.generated_nodes.get(session_id, []))
        batch_unique = total_after - total_before

        logger.debug(
            "[NodePalette] Batch %d complete (%.2fs) | New unique: %d | Total: %d",
            batch_num, batch_duration, batch_unique, total_after
        )

        yield {
            'event': 'batch_complete',
            'batch_number': batch_num,
            'batch_duration': round(batch_duration, 2),
            'new_unique_nodes': batch_unique,
            'total_nodes': total_after,
            'llm_stats': llm_stats
        }

    @abstractmethod
    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        """
        Build diagram-specific prompt for node generation.

        Subclasses MUST implement this method with their specific prompt logic.

        Args:
            center_topic: Center/main topic from diagram
            educational_context: Educational context dict
            count: Number of nodes to request
            batch_num: Current batch number

        Returns:
            Formatted prompt string
        """
        pass

    def _get_system_message(self, educational_context: Optional[Dict[str, Any]], center_topic: str = "") -> str:
        """
        Get system message for LLM.

        Default implementation detects language from content.
        Subclasses can override for diagram-specific instructions.

        Args:
            educational_context: Educational context dict
            center_topic: Center topic text for language detection

        Returns:
            System message string
        """
        language = self._detect_language  # pylint: disable=protected-access(center_topic, educational_context)
        return '你是一个有帮助的K12教育助手。' if language == 'zh' else 'You are a helpful K12 education assistant.'

    def _get_temperature_for_batch(self, batch_num: int) -> float:
        """
        Increase temperature for later batches to maximize diversity.

        Same for all diagrams.
        """
        base_temp = 0.7
        # Gradually increase temperature for diversity
        return min(base_temp + (batch_num - 1) * 0.1, 1.0)

    def _deduplicate_node(self, new_text: str, session_id: str) -> Tuple[bool, str, float]:
        """
        Deduplicate node using exact and fuzzy matching.

        Same for all diagrams.

        Returns:
            (is_unique, match_type, similarity)
        """
        normalized = self._normalize_text  # pylint: disable=protected-access(new_text)

        if session_id not in self.seen_texts:
            self.seen_texts[session_id] = set()

        seen = self.seen_texts[session_id]

        # Exact match
        if normalized in seen:
            return (False, 'exact', 1.0)

        # Fuzzy match
        for seen_text in seen:
            similarity = SequenceMatcher(None, normalized, seen_text).ratio()
            if similarity > 0.85:
                return (False, 'fuzzy', similarity)

        # Unique!
        seen.add(normalized)
        return (True, 'unique', 0.0)

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for deduplication.

        Same for all diagrams.
        """
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _detect_language(self, center_topic: str, educational_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Detect language from content, prioritizing Chinese character detection.

        Priority order:
        1. If center_topic contains Chinese characters -> 'zh'
        2. If educational_context.raw_message contains Chinese -> 'zh'
        3. If educational_context.language is explicitly set -> use it
        4. Default -> 'en'

        Args:
            center_topic: The main topic text
            educational_context: Educational context dict

        Returns:
            'zh' or 'en'
        """
        # Check center_topic for Chinese characters (highest priority)
        if center_topic and re.search(r'[\u4e00-\u9fff]', center_topic):
            return 'zh'

        # Check raw_message for Chinese characters
        if educational_context and educational_context.get('raw_message'):
            if re.search(r'[\u4e00-\u9fff]', educational_context['raw_message']):
                return 'zh'

        # Fall back to explicit language setting
        if educational_context and educational_context.get('language'):
            return educational_context['language']

        # Default to English
        return 'en'

    def end_session(self, session_id: str, reason: str = "complete") -> None:
        """
        End session and cleanup.

        Same for all diagrams.
        """
        if session_id not in self.session_start_times:
            return

        elapsed = time.time() - self.session_start_times[session_id]
        total_nodes = len(self.generated_nodes.get(session_id, []))
        batches = self.batch_counts.get(session_id, 0)

        logger.debug("[NodePalette] Session ended: %s | Reason: %s", session_id[:8], reason)
        logger.debug("[NodePalette]   Duration: %.2fs | Batches: %d | Total nodes: %d",
                   elapsed, batches, total_nodes)

        # Cleanup
        self.session_start_times.pop(session_id, None)
        self.generated_nodes.pop(session_id, None)
        self.seen_texts.pop(session_id, None)
        self.batch_counts.pop(session_id, None)

