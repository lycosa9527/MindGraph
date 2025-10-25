"""
Base Node Palette Generator
============================

Shared logic for all diagram-specific palette generators.

Features:
- Concurrent multi-LLM streaming
- Real-time deduplication
- Progressive node rendering
- Session management
- Temperature-based diversity

Author: lycosa9527
Made by: MindSpring Team
"""

import logging
import time
import re
from typing import Dict, List, Set, AsyncGenerator, Tuple, Optional, Any
from difflib import SequenceMatcher
from abc import ABC, abstractmethod

from services.llm_service import llm_service

logger = logging.getLogger(__name__)


class BasePaletteGenerator(ABC):
    """
    Base class for all diagram-specific node palette generators.
    
    Architecture:
    - Uses llm_service.stream_progressive() for concurrent token streaming
    - All 4 LLMs (qwen, deepseek, hunyuan, kimi) fire simultaneously
    - Nodes render progressively as tokens arrive from any LLM
    - Deduplication across all batches and LLMs
    - Subclasses override _build_prompt() for diagram-specific generation
    """
    
    def __init__(self):
        """Initialize base palette generator"""
        self.llm_service = llm_service
        self.llm_models = ['qwen', 'deepseek', 'hunyuan', 'kimi']
        
        # Session storage
        self.generated_nodes = {}  # session_id -> List[Dict]
        self.seen_texts = {}  # session_id -> Set[str] (normalized)
        self.session_start_times = {}  # session_id -> timestamp
        self.batch_counts = {}  # session_id -> int (total batches)
        
        logger.info("[NodePalette-%s] Initialized with concurrent multi-LLM architecture", 
                   self.__class__.__name__)
        logger.info("[NodePalette-%s] LLMs: %s", 
                   self.__class__.__name__, ', '.join(self.llm_models))
    
    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch of nodes using ALL 4 LLMs with concurrent token streaming.
        
        Nodes render progressively as tokens arrive from any LLM!
        
        Args:
            session_id: Unique session identifier
            center_topic: Center node text from diagram
            educational_context: Educational context (grade, subject, etc.)
            nodes_per_llm: Nodes to request from each LLM (default: 15)
            
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
            logger.info("[NodePalette] New session: %s | Topic: '%s'", session_id[:8], center_topic)
        
        batch_num = self.batch_counts[session_id] + 1
        self.batch_counts[session_id] = batch_num
        
        total_before = len(self.generated_nodes.get(session_id, []))
        logger.info("[NodePalette] Batch %d starting | Session: %s | Topic: '%s'", 
                   batch_num, session_id[:8], center_topic)
        
        # Yield batch start
        yield {
            'event': 'batch_start',
            'batch_number': batch_num,
            'llm_count': len(self.llm_models),
            'nodes_per_llm': nodes_per_llm
        }
        
        # Build prompt using diagram-specific logic (subclass implements this)
        prompt = self._build_prompt(center_topic, educational_context, nodes_per_llm, batch_num)
        system_message = self._get_system_message(educational_context)
        
        # Get temperature for diversity
        temperature = self._get_temperature_for_batch(batch_num)
        
        batch_start_time = time.time()
        llm_stats = {}
        
        # Track current lines being built for each LLM
        current_lines = {llm: "" for llm in self.llm_models}
        llm_unique_counts = {llm: 0 for llm in self.llm_models}
        llm_duplicate_counts = {llm: 0 for llm in self.llm_models}
        
        # 🚀 CONCURRENT TOKEN STREAMING - All 4 LLMs fire simultaneously!
        logger.info("[NodePalette] Streaming from %d LLMs with progressive rendering...", len(self.llm_models))
        
        async for chunk in self.llm_service.stream_progressive(
            prompt=prompt,
            models=self.llm_models,
            temperature=temperature,
            max_tokens=500,
            timeout=20.0,
            system_message=system_message
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
                        is_unique, match_type, similarity = self._deduplicate_node(node_text, session_id)
                        
                        if is_unique:
                            # UNIQUE NODE - yield immediately for progressive rendering!
                            node = {
                                'id': f"{session_id}_{llm_name}_{batch_num}_{llm_unique_counts[llm_name]}",
                                'text': node_text,
                                'source_llm': llm_name,
                                'batch_number': batch_num,
                                'relevance_score': 0.8,
                                'selected': False
                            }
                            
                            # Verbose logging for streaming nodes
                            logger.info(
                                "[NodePalette-Stream] Node generated | LLM: %s | Batch: %d | ID: %s | Text: '%s'",
                                llm_name, batch_num, node['id'], node_text[:50] + ('...' if len(node_text) > 50 else '')
                            )
                            
                            # Store
                            if session_id not in self.generated_nodes:
                                self.generated_nodes[session_id] = []
                            self.generated_nodes[session_id].append(node)
                            
                            # Yield immediately - node appears NOW!
                            yield {
                                'event': 'node_generated',
                                'node': node
                            }
                            
                            llm_unique_counts[llm_name] += 1
                        else:
                            llm_duplicate_counts[llm_name] += 1
            
            elif event == 'complete':
                # LLM stream complete - process any remaining text
                if current_lines[llm_name].strip():
                    node_text = current_lines[llm_name].lstrip('0123456789.-、）) ').strip()
                    if node_text and len(node_text) >= 2:
                        is_unique, match_type, similarity = self._deduplicate_node(node_text, session_id)
                        if is_unique:
                            node = {
                                'id': f"{session_id}_{llm_name}_{batch_num}_{llm_unique_counts[llm_name]}",
                                'text': node_text,
                                'source_llm': llm_name,
                                'batch_number': batch_num,
                                'relevance_score': 0.8,
                                'selected': False
                            }
                            
                            # Verbose logging for final node in stream
                            logger.info(
                                "[NodePalette-Complete] Final node | LLM: %s | Batch: %d | ID: %s | Text: '%s'",
                                llm_name, batch_num, node['id'], node_text[:50] + ('...' if len(node_text) > 50 else '')
                            )
                            
                            if session_id not in self.generated_nodes:
                                self.generated_nodes[session_id] = []
                            self.generated_nodes[session_id].append(node)
                            yield {
                                'event': 'node_generated',
                                'node': node
                            }
                            llm_unique_counts[llm_name] += 1
                
                # Record stats for this LLM
                llm_stats[llm_name] = {
                    'unique': llm_unique_counts[llm_name],
                    'duplicates': llm_duplicate_counts[llm_name],
                    'duration': chunk.get('duration', 0),
                    'token_count': chunk.get('token_count', 0)
                }
                
                # Yield llm_complete event
                yield {
                    'event': 'llm_complete',
                    'llm': llm_name,
                    'unique_nodes': llm_unique_counts[llm_name],
                    'duplicates': llm_duplicate_counts[llm_name],
                    'duration': chunk.get('duration', 0)
                }
                
                logger.info(
                    "[NodePalette] %s batch %d complete | Unique: %d | Duplicates: %d | Time: %.2fs",
                    llm_name, batch_num, llm_unique_counts[llm_name], 
                    llm_duplicate_counts[llm_name], chunk.get('duration', 0)
                )
            
            elif event == 'error':
                # LLM failed
                logger.error("[NodePalette] %s stream error: %s", llm_name, chunk.get('error'))
                llm_stats[llm_name] = {
                    'unique': llm_unique_counts[llm_name],
                    'duplicates': llm_duplicate_counts[llm_name],
                    'duration': chunk.get('duration', 0),
                    'error': chunk.get('error')
                }
        
        # Batch complete
        batch_duration = time.time() - batch_start_time
        total_after = len(self.generated_nodes.get(session_id, []))
        batch_unique = total_after - total_before
        
        logger.info(
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
    
    @abstractmethod
    def _get_system_message(self, educational_context: Optional[Dict[str, Any]]) -> str:
        """
        Get system message for LLM.
        
        Subclasses can override for diagram-specific instructions.
        
        Args:
            educational_context: Educational context dict
            
        Returns:
            System message string
        """
        pass
    
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
        normalized = self._normalize_text(new_text)
        
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
    
    def end_session(self, session_id: str, reason: str = "complete"):
        """
        End session and cleanup.
        
        Same for all diagrams.
        """
        if session_id not in self.session_start_times:
            return
        
        elapsed = time.time() - self.session_start_times[session_id]
        total_nodes = len(self.generated_nodes.get(session_id, []))
        batches = self.batch_counts.get(session_id, 0)
        
        logger.info("[NodePalette] Session ended: %s | Reason: %s", session_id[:8], reason)
        logger.info("[NodePalette]   Duration: %.2fs | Batches: %d | Total nodes: %d", 
                   elapsed, batches, total_nodes)
        
        # Cleanup
        self.session_start_times.pop(session_id, None)
        self.generated_nodes.pop(session_id, None)
        self.seen_texts.pop(session_id, None)
        self.batch_counts.pop(session_id, None)

