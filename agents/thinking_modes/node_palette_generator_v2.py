"""
Node Palette Generator V2 (Concurrent Multi-LLM)
================================================

Infinite concurrent brainstorming using LLM Service middleware.
Fires all 4 LLMs simultaneously, yields results progressively.

Key Features:
- Concurrent execution via llm_service.generate_progressive()
- Infinite scroll with 2/3 trigger point
- Real-time deduplication across all LLMs
- Rate limiter middleware protection
- Circuit breaker integration

Author: lycosa9527
Made by: MindSpring Team
"""

import logging
import time
import re
from typing import Dict, List, Set, AsyncGenerator, Tuple, Optional, Any
from difflib import SequenceMatcher

from services.llm_service import llm_service
from prompts.thinking_modes.circle_map import get_prompt

logger = logging.getLogger(__name__)


class NodePaletteGeneratorV2:
    """
    Infinite concurrent node generation for Node Palette.
    
    Architecture:
    - Uses llm_service.generate_progressive() for concurrent calls
    - All 4 LLMs (qwen, deepseek, hunyuan, kimi) fire simultaneously
    - Results yield as each completes (progressive streaming)
    - Deduplication across all batches and LLMs
    - No limits - keeps generating on scroll
    """
    
    def __init__(self):
        """Initialize concurrent node palette generator"""
        self.llm_service = llm_service
        self.llm_models = ['qwen', 'deepseek', 'hunyuan', 'kimi']
        
        # Session storage
        self.generated_nodes = {}  # session_id -> List[Dict]
        self.seen_texts = {}  # session_id -> Set[str] (normalized)
        self.session_start_times = {}  # session_id -> timestamp
        self.batch_counts = {}  # session_id -> int (total batches)
        
        logger.info("[NodePaletteV2] Initialized with concurrent multi-LLM architecture")
        logger.info("[NodePaletteV2] LLMs: %s", ', '.join(self.llm_models))
    
    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch of nodes using ALL 4 LLMs with concurrent token streaming.
        
        Circles render progressively as tokens arrive from any LLM!
        
        Args:
            session_id: Unique session identifier
            center_topic: Center node text from Circle Map
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
            logger.info("[NodePaletteV2] New session: %s | Topic: '%s'", session_id[:8], center_topic)
        
        batch_num = self.batch_counts[session_id] + 1
        self.batch_counts[session_id] = batch_num
        
        total_before = len(self.generated_nodes.get(session_id, []))
        logger.info("[NodePaletteV2] Batch %d starting | Session: %s | Topic: '%s'", 
                   batch_num, session_id[:8], center_topic)
        
        # Yield batch start
        yield {
            'event': 'batch_start',
            'batch_number': batch_num,
            'llm_count': len(self.llm_models),
            'nodes_per_llm': nodes_per_llm
        }
        
        # Build focused prompt for all LLMs
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
        logger.info("[NodePaletteV2] Streaming from %d LLMs with progressive rendering...", len(self.llm_models))
        
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
                            
                            # Store
                            if session_id not in self.generated_nodes:
                                self.generated_nodes[session_id] = []
                            self.generated_nodes[session_id].append(node)
                            
                            # Yield immediately - circle appears NOW!
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
                    "[NodePaletteV2] %s batch %d complete | Unique: %d | Duplicates: %d | Time: %.2fs",
                    llm_name, batch_num, llm_unique_counts[llm_name], 
                    llm_duplicate_counts[llm_name], chunk.get('duration', 0)
                )
            
            elif event == 'error':
                # LLM failed
                logger.error("[NodePaletteV2] %s stream error: %s", llm_name, chunk.get('error'))
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
            "[NodePaletteV2] Batch %d complete (%.2fs) | New unique: %d | Total: %d",
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
    
    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        """Build Circle Map prompt using CENTRALIZED prompt system"""
        # Detect language
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', center_topic))
        language = 'zh' if has_chinese else 'en'
        
        # Use same context extraction as auto-complete
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'
        
        # Get prompt from centralized system
        prompt_template = get_prompt('NODE_GENERATION', language)
        
        # Format the template
        prompt = prompt_template.format(
            count=count,
            center_topic=center_topic,
            educational_context=context_desc
        )
        
        # Add diversity note for later batches (node palette specific)
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity and avoid any repetition from previous batches."
        
        return prompt
    
    def _get_system_message(self, educational_context: Optional[Dict[str, Any]]) -> str:
        """Get system message"""
        has_chinese = False
        if educational_context and educational_context.get('raw_message'):
            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', educational_context['raw_message']))
        
        return '你是一个有帮助的K12教育助手。' if has_chinese else 'You are a helpful K12 education assistant.'
    
    def _get_temperature_for_batch(self, batch_num: int) -> float:
        """Increase temperature for later batches to maximize diversity"""
        base_temp = 0.7
        # Gradually increase temperature for diversity
        return min(base_temp + (batch_num - 1) * 0.1, 1.0)
    
    def _deduplicate_node(self, new_text: str, session_id: str) -> Tuple[bool, str, float]:
        """
        Deduplicate node using exact and fuzzy matching.
        
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
        """Normalize text for deduplication"""
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def end_session(self, session_id: str, reason: str = "complete"):
        """End session and cleanup"""
        if session_id not in self.session_start_times:
            return
        
        elapsed = time.time() - self.session_start_times[session_id]
        total_nodes = len(self.generated_nodes.get(session_id, []))
        batches = self.batch_counts.get(session_id, 0)
        
        logger.info("[NodePaletteV2] Session ended: %s | Reason: %s", session_id[:8], reason)
        logger.info("[NodePaletteV2]   Duration: %.2fs | Batches: %d | Total nodes: %d", 
                   elapsed, batches, total_nodes)
        
        # Cleanup
        self.session_start_times.pop(session_id, None)
        self.generated_nodes.pop(session_id, None)
        self.seen_texts.pop(session_id, None)
        self.batch_counts.pop(session_id, None)


# Global singleton instance
_node_palette_generator_v2 = None

def get_node_palette_generator_v2() -> NodePaletteGeneratorV2:
    """Get singleton instance"""
    global _node_palette_generator_v2
    if _node_palette_generator_v2 is None:
        _node_palette_generator_v2 = NodePaletteGeneratorV2()
    return _node_palette_generator_v2

