"""
Node Palette Generator
======================

Generates diverse observation nodes for Circle Maps using multiple LLMs
with round-robin rotation, real-time deduplication, and streaming responses.

Author: lycosa9527
Made by: MindSpring Team
"""

import logging
import time
import re
from typing import Dict, List, Set, AsyncGenerator, Tuple, Optional, Any
from difflib import SequenceMatcher

from services.llm_service import llm_service

logger = logging.getLogger(__name__)


class NodePaletteGenerator:
    """
    Generates nodes for Node Palette using 4 middleware LLMs in round-robin rotation.
    
    Features:
    - Round-robin LLM rotation per session
    - Real-time deduplication (exact + fuzzy matching)
    - Streaming responses via async generator
    - Session lifecycle tracking with metrics
    - Comprehensive logging for debugging
    """
    
    def __init__(self):
        """Initialize Node Palette Generator with 4 LLMs"""
        self.llm_rotation = ['qwen', 'deepseek', 'hunyuan', 'kimi']
        self.current_llm_index = {}  # session_id -> int
        self.generated_nodes = {}  # session_id -> List[Dict]
        self.seen_texts = {}  # session_id -> Set[str] (normalized)
        self.batch_counters = {}  # session_id -> {llm_name -> count}
        self.session_start_times = {}  # session_id -> timestamp
        self.llm_metrics = {}  # session_id -> {llm_name -> {calls, successes, failures, total_time}}
        
        logger.info("[NodePalette] Initialized with 4 LLMs: %s", ', '.join(self.llm_rotation))
    
    async def generate_next_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        batch_size: int = 20
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate next batch of nodes using round-robin LLM selection.
        
        Args:
            session_id: Unique session identifier
            center_topic: Center node text from Circle Map
            educational_context: Optional educational context (grade level, subject)
            batch_size: Number of nodes to generate (default: 20)
            
        Yields:
            Dict events:
            - {'event': 'batch_start', 'llm': 'qwen', 'batch_number': 1, 'target_count': 20}
            - {'event': 'node_generated', 'node': {...}}
            - {'event': 'batch_complete', 'llm': 'qwen', 'unique_nodes': 18, ...}
            - {'event': 'error', 'message': '...', 'fallback': '...'}
        """
        # Track session start
        if session_id not in self.session_start_times:
            self.session_start_times[session_id] = time.time()
            logger.info("[NodePalette] New session started: %s | Topic: '%s'", session_id[:8], center_topic)
        
        # Log batch start
        llm_name = self._get_next_llm(session_id)
        batch_num = self._get_batch_number(session_id, llm_name)
        total_so_far = len(self.generated_nodes.get(session_id, []))
        
        logger.info("[NodePalette] Session %s: Starting batch %d with %s | Total nodes: %d", 
                   session_id[:8], batch_num, llm_name, total_so_far)
        
        # Yield batch start event
        yield {
            'event': 'batch_start',
            'llm': llm_name,
            'batch_number': batch_num,
            'target_count': batch_size
        }
        
        # Call LLM with retry
        start_time = time.time()
        try:
            response = await self._call_llm_with_retry(
                llm_name=llm_name,
                center_topic=center_topic,
                educational_context=educational_context,
                batch_num=batch_num,
                batch_size=batch_size
            )
            elapsed = time.time() - start_time
            logger.info("[NodePalette] %s responded in %.2fs | Session: %s | Batch: %d", 
                       llm_name, elapsed, session_id[:8], batch_num)
            
            # Track metrics
            self._track_llm_call(session_id, llm_name, success=True, elapsed_time=elapsed)
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("[NodePalette] %s failed after %.2fs | Session: %s | Error: %s", 
                        llm_name, elapsed, session_id[:8], str(e))
            
            # Track metrics
            self._track_llm_call(session_id, llm_name, success=False, elapsed_time=elapsed)
            
            yield {
                'event': 'error',
                'message': f'{llm_name} failed',
                'fallback': 'Continuing with next LLM...'
            }
            return
        
        # Parse and deduplicate
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        logger.debug("[NodePalette] %s returned %d lines for session %s", llm_name, len(lines), session_id[:8])
        
        unique_count = 0
        duplicate_count = 0
        
        for i, line in enumerate(lines):
            # Strip numbering and punctuation from start
            node_text = line.lstrip('0123456789.-、）) ')
            
            if not node_text or len(node_text) < 2:
                logger.debug("[NodePalette] Skipped empty/short line: '%s'", line)
                continue
            
            # Deduplicate in real-time
            is_unique, match_type, similarity = self._deduplicate_node_streaming(node_text, session_id)
            
            if is_unique:
                # UNIQUE NODE
                node = {
                    'id': f"{session_id}_{llm_name}_{batch_num}_{unique_count}",
                    'text': node_text,
                    'source_llm': llm_name,
                    'batch_number': batch_num,
                    'relevance_score': 0.8,
                    'selected': False
                }
                
                logger.debug("[NodePalette] Unique node #%d from %s: '%s'", unique_count+1, llm_name, node_text)
                
                # Store node
                if session_id not in self.generated_nodes:
                    self.generated_nodes[session_id] = []
                self.generated_nodes[session_id].append(node)
                
                yield {
                    'event': 'node_generated',
                    'node': node
                }
                
                unique_count += 1
            else:
                # DUPLICATE
                logger.debug("[NodePalette] Duplicate %s (%.2f): '%s'", match_type, similarity, node_text)
                duplicate_count += 1
        
        # Batch complete - comprehensive stats
        total_now = len(self.generated_nodes.get(session_id, []))
        dedup_rate = (duplicate_count / max(len(lines), 1)) * 100
        
        logger.info("[NodePalette] Batch %d (%s) complete | Session: %s", batch_num, llm_name, session_id[:8])
        logger.info("[NodePalette]   Unique: %d | Duplicates: %d | Total nodes: %d | Dedup rate: %.1f%%", 
                   unique_count, duplicate_count, total_now, dedup_rate)
        
        yield {
            'event': 'batch_complete',
            'llm': llm_name,
            'batch_number': batch_num,
            'unique_nodes': unique_count,
            'duplicates_filtered': duplicate_count,
            'total_requested': batch_size,
            'total_nodes_now': total_now
        }
    
    def _get_next_llm(self, session_id: str) -> str:
        """Get next LLM in round-robin rotation per session"""
        if session_id not in self.current_llm_index:
            self.current_llm_index[session_id] = 0
        
        index = self.current_llm_index[session_id]
        llm = self.llm_rotation[index % len(self.llm_rotation)]
        self.current_llm_index[session_id] = index + 1
        
        return llm
    
    def _get_batch_number(self, session_id: str, llm_name: str) -> int:
        """Track batch number per LLM per session"""
        if session_id not in self.batch_counters:
            self.batch_counters[session_id] = {}
        
        if llm_name not in self.batch_counters[session_id]:
            self.batch_counters[session_id][llm_name] = 0
        
        self.batch_counters[session_id][llm_name] += 1
        return self.batch_counters[session_id][llm_name]
    
    async def _call_llm_with_retry(
        self,
        llm_name: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        batch_num: int,
        batch_size: int
    ) -> str:
        """
        Call LLM with retry logic and timeout handling.
        
        Returns:
            str: LLM response with newline-separated observations
        """
        # Detect language from center_topic (Chinese characters = zh, otherwise en)
        import re
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', center_topic))
        language = 'zh' if has_chinese else 'en'
        
        # Build prompt with diversity instructions
        diversity_suffix = f" (Batch {batch_num} - Generate DIVERSE and UNIQUE observations, avoid repetition)" if batch_num > 1 else ""
        
        grade_level = educational_context.get('grade_level', '5th grade') if educational_context else '5th grade'
        subject = educational_context.get('subject', 'Science') if educational_context else 'Science'
        
        if language == 'zh':
            prompt = f"""为「{center_topic}」的圆圈图生成{batch_size}个不同的观察点。

教育背景：
- 年级水平：{grade_level}
- 学科：{subject}

【重要】语言要求：
- 必须全部使用中文
- 每个观察点2-6个汉字
- 不要使用任何英文

内容要求：
- 关注具体、可观察的方面
- 适合年龄的语言
- 多样化视角（避免重复）
- 纯文本列表格式（每行一个）

现在生成{batch_size}个中文观察点：{diversity_suffix}"""
        else:
            prompt = f"""Generate {batch_size} diverse observations about "{center_topic}" for a Circle Map.

Educational Context:
- Grade Level: {grade_level}
- Subject: {subject}

【IMPORTANT】Language Requirements:
- ALL observations MUST be in English only
- Each observation should be 2-6 words
- NO Chinese characters allowed

Content Requirements:
- Focus on concrete, observable aspects
- Age-appropriate language
- DIVERSE perspectives (avoid repetition)
- Plain text list format (one per line)

Generate {batch_size} English observations now:{diversity_suffix}"""
        
        # Call LLM with timeout
        try:
            response = await llm_service.chat(
                prompt=prompt,
                model=llm_name,
                temperature=self._get_llm_temperature(llm_name),
                max_tokens=500,
                timeout=15
            )
            return response
        except Exception as e:
            logger.error("[NodePalette] LLM call failed for %s: %s", llm_name, str(e))
            raise
    
    def _get_llm_temperature(self, llm_name: str) -> float:
        """Get temperature setting for each LLM to encourage diversity"""
        temperatures = {
            'qwen': 0.7,
            'deepseek': 0.8,
            'hunyuan': 0.9,
            'kimi': 1.0
        }
        return temperatures.get(llm_name, 0.8)
    
    def _deduplicate_node_streaming(self, new_text: str, session_id: str) -> Tuple[bool, str, float]:
        """
        Deduplicate node in real-time using exact and fuzzy matching.
        
        Args:
            new_text: New node text to check
            session_id: Session ID
            
        Returns:
            Tuple: (is_unique, match_type, similarity)
                - is_unique: True if node is unique
                - match_type: 'unique', 'exact', or 'fuzzy'
                - similarity: Similarity score (0.0-1.0)
        """
        normalized = self._normalize_text(new_text)
        
        if session_id not in self.seen_texts:
            self.seen_texts[session_id] = set()
        
        seen = self.seen_texts[session_id]
        
        # Exact match
        if normalized in seen:
            return (False, 'exact', 1.0)
        
        # Fuzzy match
        max_similarity = 0.0
        for seen_text in seen:
            similarity = self._compute_similarity(normalized, seen_text)
            max_similarity = max(max_similarity, similarity)
            if similarity > 0.85:
                return (False, 'fuzzy', similarity)
        
        # Unique!
        seen.add(normalized)
        total_unique = len(seen)
        logger.debug("[NodePalette] New unique node (total unique: %d): '%s'", total_unique, new_text)
        return (True, 'unique', 0.0)
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for deduplication"""
        # Lowercase, remove punctuation, normalize whitespace
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Compute similarity between two texts using SequenceMatcher"""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _track_llm_call(self, session_id: str, llm_name: str, success: bool, elapsed_time: float):
        """Track LLM performance metrics"""
        if session_id not in self.llm_metrics:
            self.llm_metrics[session_id] = {}
        
        if llm_name not in self.llm_metrics[session_id]:
            self.llm_metrics[session_id][llm_name] = {
                'calls': 0,
                'successes': 0,
                'failures': 0,
                'total_time': 0
            }
        
        metrics = self.llm_metrics[session_id][llm_name]
        metrics['calls'] += 1
        metrics['total_time'] += elapsed_time
        
        if success:
            metrics['successes'] += 1
        else:
            metrics['failures'] += 1
        
        # Log metrics occasionally
        if metrics['calls'] % 3 == 0:  # Every 3 calls
            avg_time = metrics['total_time'] / metrics['calls']
            success_rate = (metrics['successes'] / metrics['calls']) * 100
            logger.debug("[NodePalette] %s metrics | Calls: %d | Success: %.0f%% | Avg time: %.2fs", 
                        llm_name, metrics['calls'], success_rate, avg_time)
    
    def end_session(self, session_id: str, reason: str = "complete"):
        """
        End session and log summary metrics.
        
        Args:
            session_id: Session ID to end
            reason: Reason for ending (user_finished, timeout, error, etc.)
        """
        if session_id not in self.session_start_times:
            logger.warning("[NodePalette] Attempted to end non-existent session: %s", session_id[:8])
            return
        
        elapsed = time.time() - self.session_start_times[session_id]
        total_nodes = len(self.generated_nodes.get(session_id, []))
        batches = sum(self.batch_counters.get(session_id, {}).values())
        avg_nodes = total_nodes / max(batches, 1)
        
        logger.info("[NodePalette] Session ended: %s | Reason: %s", session_id[:8], reason)
        logger.info("[NodePalette]   Duration: %.2fs | Batches: %d | Total nodes: %d | Avg nodes/batch: %.1f", 
                   elapsed, batches, total_nodes, avg_nodes)
        
        # Log LLM performance summary
        if session_id in self.llm_metrics:
            for llm_name, metrics in self.llm_metrics[session_id].items():
                success_rate = (metrics['successes'] / max(metrics['calls'], 1)) * 100
                avg_time = metrics['total_time'] / max(metrics['calls'], 1)
                logger.info("[NodePalette]   %s: %d/%d calls (%.0f%% success, %.2fs avg)", 
                           llm_name, metrics['successes'], metrics['calls'], success_rate, avg_time)
        
        # Cleanup
        del self.session_start_times[session_id]
        if session_id in self.generated_nodes:
            del self.generated_nodes[session_id]
        if session_id in self.seen_texts:
            del self.seen_texts[session_id]
        if session_id in self.llm_metrics:
            del self.llm_metrics[session_id]
        if session_id in self.batch_counters:
            del self.batch_counters[session_id]
        if session_id in self.current_llm_index:
            del self.current_llm_index[session_id]
        
        logger.info("[NodePalette] Session cleanup complete: %s", session_id[:8])
    
    def get_session_debug_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get debug information for a session.
        
        Args:
            session_id: Session ID to inspect
            
        Returns:
            Dict with session stats and metrics
        """
        generated_nodes = self.generated_nodes.get(session_id, [])
        seen_texts = list(self.seen_texts.get(session_id, set()))
        batch_counters = self.batch_counters.get(session_id, {})
        current_llm_index = self.current_llm_index.get(session_id, 0)
        llm_metrics = self.llm_metrics.get(session_id, {})
        
        # Calculate stats
        total_nodes = len(generated_nodes)
        total_batches = sum(batch_counters.values())
        nodes_by_llm = {}
        for node in generated_nodes:
            llm = node.get('source_llm', 'unknown')
            nodes_by_llm[llm] = nodes_by_llm.get(llm, 0) + 1
        
        return {
            'session_id': session_id,
            'session_exists': session_id in self.session_start_times,
            'total_nodes_generated': total_nodes,
            'unique_texts_count': len(seen_texts),
            'total_batches': total_batches,
            'batch_counters': batch_counters,
            'current_llm_index': current_llm_index,
            'next_llm': self.llm_rotation[current_llm_index % len(self.llm_rotation)],
            'nodes_by_llm': nodes_by_llm,
            'llm_metrics': llm_metrics,
            'sample_nodes': generated_nodes[:5] if generated_nodes else [],
            'sample_seen_texts': seen_texts[:10] if seen_texts else []
        }


# Global singleton instance
_node_palette_generator = None

def get_node_palette_generator() -> NodePaletteGenerator:
    """Get singleton instance of NodePaletteGenerator"""
    global _node_palette_generator
    if _node_palette_generator is None:
        _node_palette_generator = NodePaletteGenerator()
    return _node_palette_generator

