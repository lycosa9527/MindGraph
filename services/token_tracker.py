"""
Token Tracker Service
=====================

Centralized service for tracking LLM token usage and costs.
Records token consumption per user, per organization, and globally.

Performance Optimizations (High Concurrency Design):
- Memory-first approach: Accumulate tokens in memory, write to DB periodically
- Large batch sizes (1000 records) to minimize database write frequency
- Long intervals (5 minutes) to reduce SQLite WAL contention
- Non-blocking writes (don't slow down LLM responses)
- Bulk insert for 3-5x faster database writes

Designed for 50-200+ concurrent users with Node Palette (4 LLMs each)
and Tab Mode autocomplete (frequent LLM calls).

Configuration via environment variables:
- TOKEN_TRACKER_ENABLED: Enable/disable tracking (default: true)
- TOKEN_TRACKER_BATCH_SIZE: Records per batch trigger (default: 1000)
- TOKEN_TRACKER_BATCH_INTERVAL: Seconds between writes (default: 300 = 5 min)
- TOKEN_TRACKER_MAX_BUFFER_SIZE: Max memory buffer before force write (default: 10000)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import logging
import uuid
import asyncio
import threading
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import DatabaseError, OperationalError

from models.token_usage import TokenUsage

logger = logging.getLogger(__name__)


class TokenTracker:
    """
    Tracks and records token usage for all LLM calls.
    
    Features:
    - Tracks per-user token usage
    - Tracks per-organization (school) token usage
    - Calculates costs based on model pricing
    - Records request metadata for analytics
    - Memory-first batch writes (performance optimized for high concurrency)
    
    Performance (Optimized for 50-200+ concurrent users):
    - Non-blocking: Token tracking doesn't slow down LLM responses
    - Memory-first: Accumulates records in memory, writes periodically
    - Large batches: 1000 records per write to minimize DB operations
    - Long intervals: 5 minutes between writes to reduce SQLite contention
    - Thread-safe: Uses lock for memory buffer access
    - Bulk insert: Uses bulk_insert_mappings for 3-5x faster writes
    - Auto-flush: Writes on interval OR when buffer reaches size limit
    """
    
    # Model pricing (per 1M tokens in CNY)
    MODEL_PRICING = {
        'qwen': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope'},
        'qwen-turbo': {'input': 0.3, 'output': 0.6, 'provider': 'dashscope'},
        'qwen-plus': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope'},
        'deepseek': {'input': 0.4, 'output': 2.0, 'provider': 'dashscope'},
        'kimi': {'input': 2.0, 'output': 6.0, 'provider': 'dashscope'},
        'hunyuan': {'input': 0.45, 'output': 0.5, 'provider': 'tencent'},
        'doubao': {'input': 0.8, 'output': 2.0, 'provider': 'volcengine'},
    }
    
    # Model name mapping (alias -> full model name)
    MODEL_NAME_MAP = {
        'qwen': 'qwen-plus-latest',
        'qwen-turbo': 'qwen-turbo-latest',
        'qwen-plus': 'qwen-plus-latest',
        'deepseek': 'deepseek-v3.1',
        'kimi': 'moonshot-v1-32k',
        'hunyuan': 'hunyuan-turbo',
        'doubao': 'doubao-1-5-pro-32k',
    }
    
    # Configuration from environment variables
    ENABLED = os.getenv('TOKEN_TRACKER_ENABLED', 'true').lower() == 'true'
    BATCH_SIZE = int(os.getenv('TOKEN_TRACKER_BATCH_SIZE', '1000'))
    BATCH_INTERVAL = float(os.getenv('TOKEN_TRACKER_BATCH_INTERVAL', '300'))  # 5 minutes
    MAX_BUFFER_SIZE = int(os.getenv('TOKEN_TRACKER_MAX_BUFFER_SIZE', '10000'))
    WORKER_CHECK_INTERVAL = 30.0  # Check buffer every 30 seconds
    
    def __init__(self):
        """Initialize memory buffer and background worker"""
        # Memory buffer with thread-safe lock
        self._buffer: List[Dict[str, Any]] = []
        self._buffer_lock = threading.Lock()
        
        # Worker state
        self._worker_task: Optional[asyncio.Task] = None
        self._last_flush_time: float = time.time()
        self._initialized = False
        self._shutting_down = False
        
        # Error state
        self._corruption_detected = False
        
        # Statistics
        self._total_records_written = 0
        self._total_records_dropped = 0
        self._total_batches_written = 0
        
        # WAL checkpoint tracking
        self._checkpoint_interval = 10  # Checkpoint every N batches
        
        if self.ENABLED:
            logger.info(
                f"[TokenTracker] Initialized: batch_size={self.BATCH_SIZE}, "
                f"interval={self.BATCH_INTERVAL}s, max_buffer={self.MAX_BUFFER_SIZE}"
            )
        else:
            logger.info("[TokenTracker] Disabled via TOKEN_TRACKER_ENABLED=false")
    
    def _ensure_worker_started(self):
        """Start background worker if not already running"""
        if self._initialized or not self.ENABLED:
            return
        
        try:
            loop = asyncio.get_running_loop()
            self._worker_task = loop.create_task(self._flush_worker())
            self._initialized = True
            self._last_flush_time = time.time()
            logger.debug("[TokenTracker] Background flush worker started")
        except RuntimeError:
            # No running event loop - will start on first async call
            pass
    
    async def _flush_worker(self):
        """
        Background worker that periodically flushes the buffer to database.
        
        Flush triggers:
        1. Buffer size >= BATCH_SIZE (1000 records)
        2. Time since last flush >= BATCH_INTERVAL (5 minutes)
        3. Buffer size >= MAX_BUFFER_SIZE (force flush to prevent OOM)
        """
        logger.debug("[TokenTracker] Flush worker started")
        
        while not self._shutting_down:
            try:
                # Wait for check interval
                await asyncio.sleep(self.WORKER_CHECK_INTERVAL)
                
                if self._shutting_down:
                    break
                
                # Check flush conditions
                buffer_size = len(self._buffer)
                time_since_flush = time.time() - self._last_flush_time
                
                should_flush = False
                flush_reason = ""
                
                if buffer_size >= self.MAX_BUFFER_SIZE:
                    should_flush = True
                    flush_reason = f"max buffer ({buffer_size} >= {self.MAX_BUFFER_SIZE})"
                elif buffer_size >= self.BATCH_SIZE:
                    should_flush = True
                    flush_reason = f"batch size ({buffer_size} >= {self.BATCH_SIZE})"
                elif time_since_flush >= self.BATCH_INTERVAL and buffer_size > 0:
                    should_flush = True
                    flush_reason = f"interval ({time_since_flush:.0f}s >= {self.BATCH_INTERVAL}s)"
                
                if should_flush:
                    logger.debug(f"[TokenTracker] Flush triggered: {flush_reason}")
                    await self._flush_buffer()
                
            except asyncio.CancelledError:
                logger.debug("[TokenTracker] Flush worker cancelled")
                break
            except Exception as e:
                logger.error(f"[TokenTracker] Flush worker error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Brief pause before retrying
        
        # Final flush on shutdown
        if len(self._buffer) > 0:
            logger.info(f"[TokenTracker] Final flush: {len(self._buffer)} records")
            await self._flush_buffer()
        
        logger.debug("[TokenTracker] Flush worker stopped")
    
    async def _flush_buffer(self):
        """Flush buffer to database using bulk insert"""
        # Skip if disabled or corruption detected
        if not self.ENABLED:
            return
        
        if self._corruption_detected:
            with self._buffer_lock:
                dropped = len(self._buffer)
                self._buffer.clear()
                self._total_records_dropped += dropped
            logger.warning(
                f"[TokenTracker] Skipping flush - database corruption detected. "
                f"{dropped} records dropped."
            )
            return
        
        # Get records from buffer (thread-safe)
        with self._buffer_lock:
            if not self._buffer:
                return
            records = self._buffer.copy()
            self._buffer.clear()
        
        record_count = len(records)
        
        # Check disk space before writing
        try:
            from config.database import check_disk_space
            if not check_disk_space(required_mb=50):
                logger.error("[TokenTracker] Insufficient disk space - records dropped")
                self._total_records_dropped += record_count
                return
        except Exception as e:
            logger.debug(f"[TokenTracker] Disk space check skipped: {e}")
        
        # Write to database
        start_time = time.time()
        try:
            from config.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Use bulk_insert_mappings for faster inserts (3-5x faster than add_all)
                db.bulk_insert_mappings(TokenUsage, records)
                db.commit()
                
                # Update stats
                write_time = time.time() - start_time
                self._total_records_written += record_count
                self._total_batches_written += 1
                self._last_flush_time = time.time()
                
                total_tokens = sum(r.get('total_tokens', 0) for r in records)
                logger.info(
                    f"[TokenTracker] Wrote {record_count} records ({total_tokens} tokens) "
                    f"in {write_time*1000:.1f}ms | Total: {self._total_records_written}"
                )
                
                # Periodic WAL checkpoint
                if self._total_batches_written % self._checkpoint_interval == 0:
                    try:
                        from config.database import checkpoint_wal
                        checkpoint_wal()
                        logger.debug("[TokenTracker] WAL checkpoint completed")
                    except Exception as e:
                        logger.debug(f"[TokenTracker] WAL checkpoint skipped: {e}")
                
            except (DatabaseError, OperationalError) as e:
                db.rollback()
                error_msg = str(e).lower()
                
                # Detect corruption
                if any(x in error_msg for x in ["malformed", "corrupt", "database disk image"]):
                    self._corruption_detected = True
                    self._total_records_dropped += record_count
                    logger.error(
                        "[TokenTracker] DATABASE CORRUPTION DETECTED! "
                        "Token tracking disabled. Run: python scripts/recover_database.py"
                    )
                else:
                    self._total_records_dropped += record_count
                    logger.error(f"[TokenTracker] Database error: {e}")
                    
            except Exception as e:
                db.rollback()
                self._total_records_dropped += record_count
                logger.error(f"[TokenTracker] Write failed: {e}", exc_info=True)
            finally:
                db.close()
                
        except Exception as e:
            self._total_records_dropped += record_count
            logger.error(f"[TokenTracker] Flush failed: {e}", exc_info=True)
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate unique session ID for multi-LLM requests"""
        return f"session_{uuid.uuid4().hex[:16]}"
    
    async def track_usage(
        self,
        model_alias: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: Optional[int] = None,
        request_type: str = 'diagram_generation',
        diagram_type: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        api_key_id: Optional[int] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        response_time: Optional[float] = None,
        success: bool = True,
        db: Optional[Session] = None  # Deprecated, kept for backward compatibility
    ) -> bool:
        """
        Track token usage (async, non-blocking, batched).
        
        This method is NON-BLOCKING - it adds the record to an in-memory buffer.
        The actual database write happens periodically in a background worker.
        
        Args:
            model_alias: Model identifier ('qwen', 'deepseek', 'kimi', 'hunyuan', 'doubao')
            input_tokens: Number of input tokens (from API)
            output_tokens: Number of output tokens (from API)
            total_tokens: Total tokens from API (authoritative billing value)
            request_type: Type of request ('diagram_generation', 'node_palette', 'autocomplete')
            diagram_type: Type of diagram if applicable
            user_id: User ID if authenticated
            organization_id: Organization ID (school)
            api_key_id: API key ID if request was made with API key
            session_id: Session ID to group multi-LLM requests
            conversation_id: Conversation ID for multi-turn conversations
            endpoint_path: API endpoint path
            response_time: Response time in seconds
            success: Whether the request was successful
            db: Deprecated, not used
            
        Returns:
            True if added to buffer, False if disabled or buffer overflow
        """
        # Skip if disabled
        if not self.ENABLED:
            return False
        
        try:
            # Ensure worker is started
            self._ensure_worker_started()
            
            # Calculate total tokens if not provided
            if total_tokens is None:
                total_tokens = input_tokens + output_tokens
            
            # Get pricing info
            pricing = self.MODEL_PRICING.get(model_alias, {
                'input': 0.4,
                'output': 1.2,
                'provider': 'unknown'
            })
            
            # Calculate cost (pricing is per 1M tokens)
            input_cost = input_tokens * pricing['input'] / 1_000_000
            output_cost = output_tokens * pricing['output'] / 1_000_000
            total_cost = input_cost + output_cost
            
            # Get full model name
            model_name = self.MODEL_NAME_MAP.get(model_alias, model_alias)
            
            # Build record
            record = {
                'user_id': user_id,
                'organization_id': organization_id,
                'api_key_id': api_key_id,
                'session_id': session_id or self.generate_session_id(),
                'conversation_id': conversation_id,
                'model_provider': pricing['provider'],
                'model_name': model_name,
                'model_alias': model_alias,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'input_cost': round(input_cost, 6),
                'output_cost': round(output_cost, 6),
                'total_cost': round(total_cost, 6),
                'request_type': request_type,
                'diagram_type': diagram_type,
                'endpoint_path': endpoint_path,
                'success': success,
                'response_time': response_time,
                'created_at': datetime.utcnow()
            }
            
            # Add to buffer (thread-safe)
            with self._buffer_lock:
                # Check buffer overflow
                if len(self._buffer) >= self.MAX_BUFFER_SIZE:
                    self._total_records_dropped += 1
                    logger.warning(
                        f"[TokenTracker] Buffer overflow! Dropping record. "
                        f"Buffer: {len(self._buffer)}/{self.MAX_BUFFER_SIZE}"
                    )
                    return False
                
                self._buffer.append(record)
            
            # Debug log (only if org_id present to reduce noise)
            if organization_id and logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"[TokenTracker] Buffered: org={organization_id}, "
                    f"model={model_alias}, tokens={total_tokens}"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"[TokenTracker] Failed to buffer record: {e}", exc_info=True)
            return False
    
    async def flush(self):
        """Manually flush pending records (called on shutdown)"""
        if not self.ENABLED:
            return
        
        self._shutting_down = True
        
        # Cancel worker task
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        # Final flush
        if len(self._buffer) > 0:
            logger.info(f"[TokenTracker] Shutdown flush: {len(self._buffer)} records")
            await self._flush_buffer()
        
        # Final WAL checkpoint
        try:
            from config.database import checkpoint_wal
            checkpoint_wal()
        except Exception as e:
            logger.debug(f"[TokenTracker] Final WAL checkpoint skipped: {e}")
        
        # Log final stats
        logger.info(
            f"[TokenTracker] Shutdown complete. "
            f"Total written: {self._total_records_written}, "
            f"dropped: {self._total_records_dropped}"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tracker statistics"""
        return {
            'enabled': self.ENABLED,
            'buffer_size': len(self._buffer),
            'total_written': self._total_records_written,
            'total_dropped': self._total_records_dropped,
            'total_batches': self._total_batches_written,
            'corruption_detected': self._corruption_detected,
            'config': {
                'batch_size': self.BATCH_SIZE,
                'batch_interval': self.BATCH_INTERVAL,
                'max_buffer_size': self.MAX_BUFFER_SIZE,
            }
        }


# Global token tracker instance (singleton)
_token_tracker_instance: Optional[TokenTracker] = None

def get_token_tracker() -> TokenTracker:
    """Get or create global token tracker instance"""
    global _token_tracker_instance
    if _token_tracker_instance is None:
        _token_tracker_instance = TokenTracker()
    return _token_tracker_instance

# Backward compatibility alias
token_tracker = get_token_tracker()
