"""
Token Tracker Service
=====================

Centralized service for tracking LLM token usage and costs.
Records token consumption per user, per organization, and globally.

Performance Optimizations:
- Async queue-based batch writes
- Non-blocking writes (don't slow down LLM responses)
- Automatic batching (every N records or time interval)
- Graceful degradation if queue is full

Author: lycosa9527
Made by: MindSpring Team
"""

import logging
import uuid
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
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
    - Async queue-based batch writes (performance optimized)
    
    Performance:
    - Non-blocking: Token tracking doesn't slow down LLM responses
    - Batch writes: Groups multiple records to reduce database overhead
    - Queue-based: Uses async queue to buffer writes
    - Auto-flush: Writes every N records or time interval
    """
    
    # Model pricing (per 1M tokens in CNY)
    # From docs/TOKEN_COST_TRACKING_IMPLEMENTATION.md
    MODEL_PRICING = {
        'qwen': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope'},
        'qwen-turbo': {'input': 0.3, 'output': 0.6, 'provider': 'dashscope'},
        'qwen-plus': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope'},
        'deepseek': {'input': 0.4, 'output': 2.0, 'provider': 'dashscope'},
        'kimi': {'input': 2.0, 'output': 6.0, 'provider': 'dashscope'},
        'hunyuan': {'input': 0.45, 'output': 0.5, 'provider': 'tencent'},
    }
    
    # Batch write configuration
    BATCH_SIZE = 10  # Write after N records
    BATCH_INTERVAL = 5.0  # Write after N seconds
    MAX_QUEUE_SIZE = 1000  # Max queue size before dropping records
    
    def __init__(self):
        """Initialize async queue and background worker"""
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=self.MAX_QUEUE_SIZE)
        self._worker_task: Optional[asyncio.Task] = None
        self._batch_buffer: List[Dict[str, Any]] = []
        self._last_flush: float = asyncio.get_event_loop().time()
        self._initialized = False
        self._corruption_detected = False
        self._write_count = 0
        self._checkpoint_interval = 50  # Checkpoint every N writes
    
    def _ensure_worker_started(self):
        """Start background worker if not already running"""
        if not self._initialized:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    self._worker_task = loop.create_task(self._batch_worker())
                    self._initialized = True
                    logger.debug("[TokenTracker] Background batch worker started")
            except RuntimeError:
                # No event loop running - will start on first async call
                logger.debug("[TokenTracker] No event loop - will start worker on first call")
    
    async def _batch_worker(self):
        """Background worker that batches and writes token usage records"""
        logger.debug("[TokenTracker] Batch worker started")
        
        while True:
            try:
                # Wait for record or timeout
                try:
                    record = await asyncio.wait_for(
                        self._queue.get(), 
                        timeout=self.BATCH_INTERVAL
                    )
                    self._batch_buffer.append(record)
                    
                    # Check if batch is full
                    if len(self._batch_buffer) >= self.BATCH_SIZE:
                        await self._flush_batch()
                        
                except asyncio.TimeoutError:
                    # Timeout - flush if we have records
                    if self._batch_buffer:
                        await self._flush_batch()
                
                # Check if time interval passed
                current_time = asyncio.get_event_loop().time()
                if (current_time - self._last_flush) >= self.BATCH_INTERVAL:
                    if self._batch_buffer:
                        await self._flush_batch()
                
            except asyncio.CancelledError:
                # Shutdown - flush remaining records
                if self._batch_buffer:
                    logger.info(f"[TokenTracker] Flushing {len(self._batch_buffer)} records on shutdown")
                    await self._flush_batch()
                break
            except Exception as e:
                logger.error(f"[TokenTracker] Batch worker error: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause before retrying
    
    async def _flush_batch(self):
        """Flush batch buffer to database"""
        if not self._batch_buffer:
            return
        
        # If corruption detected, skip writes to prevent further issues
        if self._corruption_detected:
            logger.warning(f"[TokenTracker] Skipping batch write - database corruption detected. {len(self._batch_buffer)} records dropped.")
            self._batch_buffer.clear()
            return
        
        # Check disk space BEFORE clearing buffer (prevent data loss)
        try:
            from config.database import check_disk_space
            if not check_disk_space(required_mb=50):
                logger.error("[TokenTracker] Insufficient disk space - skipping batch write")
                # Don't clear buffer - records will be retried later
                return
        except Exception as e:
            logger.warning(f"[TokenTracker] Disk space check failed: {e}, proceeding with write")
        
        # Now safe to clear buffer
        records = self._batch_buffer.copy()
        self._batch_buffer.clear()
        self._last_flush = asyncio.get_event_loop().time()
        
        try:
            
            from config.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Bulk insert all records
                usage_objects = []
                for record in records:
                    usage = TokenUsage(**record)
                    usage_objects.append(usage)
                
                db.add_all(usage_objects)
                db.commit()
                
                self._write_count += len(records)
                total_tokens = sum(r['total_tokens'] for r in records)
                logger.debug(f"[TokenTracker] Batch wrote {len(records)} records ({total_tokens} tokens)")
                
                # Periodic WAL checkpoint to prevent corruption
                if self._write_count >= self._checkpoint_interval:
                    try:
                        from config.database import checkpoint_wal
                        checkpoint_wal()
                        self._write_count = 0
                    except Exception as e:
                        logger.warning(f"[TokenTracker] WAL checkpoint failed: {e}")
                
            except (DatabaseError, OperationalError) as e:
                db.rollback()
                error_msg = str(e).lower()
                
                # Detect corruption
                if "malformed" in error_msg or "corrupt" in error_msg or "database disk image" in error_msg:
                    self._corruption_detected = True
                    logger.error(
                        "[TokenTracker] DATABASE CORRUPTION DETECTED! "
                        "Token tracking disabled to prevent further damage. "
                        "Please run: python scripts/recover_database.py"
                    )
                else:
                    logger.error(f"[TokenTracker] Database error during batch write: {e}", exc_info=True)
                    
            except Exception as e:
                db.rollback()
                logger.error(f"[TokenTracker] Batch write failed: {e}", exc_info=True)
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"[TokenTracker] Failed to flush batch: {e}", exc_info=True)
    
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
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        response_time: Optional[float] = None,
        success: bool = True,
        db: Optional[Session] = None  # Optional for backward compatibility
    ) -> bool:
        """
        Track token usage (async, non-blocking, batched).
        
        This method is NON-BLOCKING - it queues the record for batch writing.
        The actual database write happens in a background worker.
        
        Args:
            model_alias: Model identifier ('qwen', 'deepseek', 'kimi', 'hunyuan')
            input_tokens: Number of input tokens (from API)
            output_tokens: Number of output tokens (from API)
            total_tokens: Total tokens from API (authoritative billing value). 
                         If None, will be calculated as input_tokens + output_tokens.
            request_type: Type of request ('diagram_generation', 'node_palette', 'thinkguide', 'autocomplete')
            diagram_type: Type of diagram if applicable
            user_id: User ID if authenticated
            organization_id: Organization ID (school) - IMPORTANT for per-school tracking!
            session_id: Session ID to group multi-LLM requests
            conversation_id: Conversation ID for multi-turn conversations
            endpoint_path: API endpoint path
            response_time: Response time in seconds
            success: Whether the request was successful
            db: Database session (deprecated - kept for backward compatibility, not used)
            
        Returns:
            True if queued successfully, False if queue is full
        """
        try:
            # Ensure worker is started
            self._ensure_worker_started()
            
            # Use API's total_tokens if provided (authoritative billing value),
            # otherwise calculate it. APIs may include overhead tokens in total_tokens
            # that aren't in the simple sum, so we prefer the API value.
            if total_tokens is None:
                total_tokens = input_tokens + output_tokens
            
            # Calculate cost
            pricing = self.MODEL_PRICING.get(model_alias, {
                'input': 0.4,
                'output': 1.2,
                'provider': 'dashscope'
            })
            
            # Convert to per-token cost (pricing is per 1M tokens)
            input_cost_per_token = pricing['input'] / 1_000_000
            output_cost_per_token = pricing['output'] / 1_000_000
            
            input_cost = input_tokens * input_cost_per_token
            output_cost = output_tokens * output_cost_per_token
            total_cost = input_cost + output_cost
            
            # Determine model name from alias
            model_name_map = {
                'qwen': 'qwen-plus-latest',
                'qwen-turbo': 'qwen-turbo-latest',
                'qwen-plus': 'qwen-plus-latest',
                'deepseek': 'deepseek-v3.1',
                'kimi': 'moonshot-v1-32k',
                'hunyuan': 'hunyuan-turbo'
            }
            model_name = model_name_map.get(model_alias, model_alias)
            
            # Prepare record (as dict for batch insert)
            record = {
                'user_id': user_id,
                'organization_id': organization_id,
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
            
            # Try to add to queue (non-blocking)
            try:
                self._queue.put_nowait(record)
                
                # Log (debug level to avoid spam)
                if organization_id:
                    logger.debug(
                        f"[TokenTracker] Queued usage for org_id={organization_id}: "
                        f"{model_alias} ({input_tokens}+{output_tokens} tokens)"
                    )
                
                return True
                
            except asyncio.QueueFull:
                # Queue is full - log warning but don't block
                logger.warning(
                    f"[TokenTracker] Queue full! Dropping token record "
                    f"({model_alias}, {input_tokens}+{output_tokens} tokens). "
                    f"Consider increasing MAX_QUEUE_SIZE or BATCH_SIZE."
                )
                return False
                
        except Exception as e:
            logger.error(f"[TokenTracker] Failed to queue usage record: {e}", exc_info=True)
            return False
    
    async def flush(self):
        """Manually flush pending records (useful for shutdown)"""
        if self._batch_buffer:
            await self._flush_batch()
        # Also process any remaining items in queue
        if self._queue:
            while not self._queue.empty():
                try:
                    record = self._queue.get_nowait()
                    self._batch_buffer.append(record)
                except asyncio.QueueEmpty:
                    break
        if self._batch_buffer:
            await self._flush_batch()
        
        # Final WAL checkpoint on shutdown
        try:
            from config.database import checkpoint_wal
            checkpoint_wal()
        except Exception as e:
            logger.warning(f"[TokenTracker] Final WAL checkpoint failed: {e}")


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

