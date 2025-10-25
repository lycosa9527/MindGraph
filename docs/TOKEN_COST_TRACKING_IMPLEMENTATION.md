# Token Usage & Cost Tracking Implementation Guide

## Overview

Track and display **real-time token usage and costs** for multi-LLM operations (4 LLMs running simultaneously).

### Features
- ✅ Track tokens for all 4 LLMs (Qwen, DeepSeek, Kimi, Hunyuan)
- ✅ Calculate costs using official pricing (DashScope + Tencent Cloud)
- ✅ Store usage in database with timestamps
- ✅ Admin panel dashboard with charts
- ✅ Real-time cost estimation
- ✅ Per-user, per-organization, and global statistics

---

## Current Pricing (2025)

### DashScope (Alibaba Cloud) - Per 1M Tokens

| Model | Input Price | Output Price | Provider |
|-------|-------------|--------------|----------|
| **Qwen-Plus** (qwen-plus-latest) | ¥0.4 | ¥1.2 | DashScope |
| **Qwen-Turbo** (qwen-turbo-latest) | ¥0.3 | ¥0.6 | DashScope |
| **DeepSeek-V3.1** (deepseek-v3.1) | ¥0.4 | ¥2.0 | DashScope |
| **Kimi** (moonshot-v1-32k) | ¥2.0 | ¥6.0 | DashScope |

### Tencent Cloud - Per 1M Tokens

| Model | Input Price | Output Price | Provider |
|-------|-------------|--------------|----------|
| **Hunyuan-Pro** (hunyuan-pro) | ¥3.0 | ¥9.0 | Tencent |
| **Hunyuan-Standard** (hunyuan-standard) | ¥0.45 | ¥0.5 | Tencent |

### Example Cost Calculation

**Node Palette Generation (1 batch, 4 LLMs):**
- Input: ~200 tokens × 4 LLMs = 800 tokens
- Output: ~500 tokens × 4 LLMs = 2000 tokens

**Cost:**
```
Qwen: (200 × 0.0000004 + 500 × 0.0000012) = ¥0.00068
DeepSeek: (200 × 0.0000004 + 500 × 0.000002) = ¥0.00108
Kimi: (200 × 0.000002 + 500 × 0.000006) = ¥0.00340
Hunyuan: (200 × 0.000003 + 500 × 0.000009) = ¥0.00510

Total per batch: ¥0.01026 (~$0.0014 USD)
```

**Daily usage (100 users, 10 generations each):**
- 1,000 generations × ¥0.01026 = **¥10.26/day (~$1.40 USD/day)**

---

## Implementation

### Step 1: Database Schema

**File:** `models/token_usage.py` (NEW)

```python
"""
Token Usage Tracking Models
Stores LLM token usage and costs for analytics.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from config.database import Base

class TokenUsage(Base):
    """Track token usage and costs for all LLM calls"""
    __tablename__ = 'token_usage'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Request metadata
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=True, index=True)
    session_id = Column(String(100), index=True)  # For grouping multi-LLM requests
    
    # LLM details
    model_provider = Column(String(50), index=True)  # 'dashscope', 'tencent'
    model_name = Column(String(100), index=True)  # 'qwen-plus', 'deepseek-v3.1', etc.
    model_alias = Column(String(50), index=True)  # 'qwen', 'deepseek', 'kimi', 'hunyuan'
    
    # Token counts
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # Cost (in CNY)
    input_cost = Column(Float, default=0.0)
    output_cost = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    
    # Request details
    request_type = Column(String(50), index=True)  # 'diagram_generation', 'node_palette', 'autocomplete'
    diagram_type = Column(String(50))  # 'mind_map', 'concept_map', etc.
    success = Column(Boolean, default=True)
    
    # Timing
    response_time = Column(Float)  # seconds
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])
    
    # Indexes for fast queries
    __table_args__ = (
        Index('idx_user_date', 'user_id', 'created_at'),
        Index('idx_org_date', 'organization_id', 'created_at'),
        Index('idx_session_date', 'session_id', 'created_at'),
        Index('idx_model_date', 'model_alias', 'created_at'),
        Index('idx_request_type_date', 'request_type', 'created_at'),
    )

class DailyCostSummary(Base):
    """Daily aggregated costs for quick dashboard queries"""
    __tablename__ = 'daily_cost_summary'
    
    id = Column(Integer, primary_key=True, index=True)
    
    date = Column(DateTime, index=True)  # Date (YYYY-MM-DD)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=True, index=True)
    
    # Aggregated counts
    total_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    
    # Per-model breakdown (JSON)
    model_breakdown = Column(Text)  # JSON: {model: {tokens, cost}}
    
    # Updated timestamp
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    organization = relationship("Organization")
    
    __table_args__ = (
        Index('idx_date_org', 'date', 'organization_id', unique=True),
    )
```

### Step 2: Cost Calculation Service

**File:** `services/cost_calculator.py` (NEW)

```python
"""
Cost Calculator for LLM Token Usage
Calculates costs based on official pricing from DashScope and Tencent Cloud.
"""

import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class CostCalculator:
    """Calculate LLM usage costs based on token counts"""
    
    # Pricing in CNY per 1M tokens (updated 2025-01)
    PRICING = {
        # DashScope (Alibaba Cloud)
        'qwen': {
            'provider': 'dashscope',
            'model': 'qwen-plus-latest',
            'input_price_per_million': 0.4,
            'output_price_per_million': 1.2,
        },
        'qwen-turbo': {
            'provider': 'dashscope',
            'model': 'qwen-turbo-latest',
            'input_price_per_million': 0.3,
            'output_price_per_million': 0.6,
        },
        'deepseek': {
            'provider': 'dashscope',
            'model': 'deepseek-v3.1',
            'input_price_per_million': 0.4,
            'output_price_per_million': 2.0,
        },
        'kimi': {
            'provider': 'dashscope',
            'model': 'moonshot-v1-32k',
            'input_price_per_million': 2.0,
            'output_price_per_million': 6.0,
        },
        
        # Tencent Cloud
        'hunyuan': {
            'provider': 'tencent',
            'model': 'hunyuan-pro',
            'input_price_per_million': 3.0,
            'output_price_per_million': 9.0,
        },
        'hunyuan-standard': {
            'provider': 'tencent',
            'model': 'hunyuan-standard',
            'input_price_per_million': 0.45,
            'output_price_per_million': 0.5,
        },
    }
    
    @staticmethod
    def calculate_cost(
        model_alias: str,
        input_tokens: int,
        output_tokens: int
    ) -> Tuple[float, float, float, Dict]:
        """
        Calculate cost for given token usage.
        
        Args:
            model_alias: Model identifier ('qwen', 'deepseek', 'kimi', 'hunyuan')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Tuple of (input_cost, output_cost, total_cost, model_info)
        """
        pricing = CostCalculator.PRICING.get(model_alias)
        
        if not pricing:
            logger.warning(f"No pricing data for model: {model_alias}, using default")
            pricing = CostCalculator.PRICING['qwen']  # Default fallback
        
        # Calculate costs (price is per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * pricing['input_price_per_million']
        output_cost = (output_tokens / 1_000_000) * pricing['output_price_per_million']
        total_cost = input_cost + output_cost
        
        model_info = {
            'provider': pricing['provider'],
            'model': pricing['model'],
        }
        
        return input_cost, output_cost, total_cost, model_info
    
    @staticmethod
    def estimate_cost(
        model_alias: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int
    ) -> Dict:
        """
        Estimate cost before making request (for budgeting).
        
        Returns:
            Dict with cost breakdown and model info
        """
        input_cost, output_cost, total_cost, model_info = CostCalculator.calculate_cost(
            model_alias, estimated_input_tokens, estimated_output_tokens
        )
        
        return {
            'model_alias': model_alias,
            'provider': model_info['provider'],
            'model': model_info['model'],
            'estimated_input_tokens': estimated_input_tokens,
            'estimated_output_tokens': estimated_output_tokens,
            'estimated_input_cost': round(input_cost, 6),
            'estimated_output_cost': round(output_cost, 6),
            'estimated_total_cost': round(total_cost, 6),
            'estimated_total_cost_usd': round(total_cost / 7.3, 6),  # Approximate CNY to USD
        }
    
    @staticmethod
    def get_pricing_info() -> Dict:
        """Get current pricing information for all models"""
        return CostCalculator.PRICING

# Singleton instance
cost_calculator = CostCalculator()
```

### Step 3: Token Usage Tracker Service

**File:** `services/token_tracker.py` (NEW)

```python
"""
Token Usage Tracker
Records LLM token usage to database for analytics and cost tracking.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session

from models.token_usage import TokenUsage
from services.cost_calculator import cost_calculator

logger = logging.getLogger(__name__)

class TokenTracker:
    """Track and record token usage for all LLM calls"""
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate unique session ID for multi-LLM requests"""
        return f"session_{uuid.uuid4().hex[:16]}"
    
    @staticmethod
    async def track_usage(
        db: Session,
        model_alias: str,
        input_tokens: int,
        output_tokens: int,
        request_type: str = 'diagram_generation',
        diagram_type: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        session_id: Optional[str] = None,
        response_time: Optional[float] = None,
        success: bool = True
    ) -> TokenUsage:
        """
        Track token usage and calculate cost.
        
        Args:
            db: Database session
            model_alias: Model identifier ('qwen', 'deepseek', 'kimi', 'hunyuan')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            request_type: Type of request ('diagram_generation', 'node_palette', 'autocomplete')
            diagram_type: Type of diagram if applicable
            user_id: User ID if authenticated
            organization_id: Organization ID if applicable
            session_id: Session ID to group multi-LLM requests
            response_time: Response time in seconds
            success: Whether the request was successful
            
        Returns:
            TokenUsage record
        """
        try:
            # Calculate cost
            input_cost, output_cost, total_cost, model_info = cost_calculator.calculate_cost(
                model_alias, input_tokens, output_tokens
            )
            
            total_tokens = input_tokens + output_tokens
            
            # Create usage record
            usage = TokenUsage(
                user_id=user_id,
                organization_id=organization_id,
                session_id=session_id or TokenTracker.generate_session_id(),
                model_provider=model_info['provider'],
                model_name=model_info['model'],
                model_alias=model_alias,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                input_cost=round(input_cost, 6),
                output_cost=round(output_cost, 6),
                total_cost=round(total_cost, 6),
                request_type=request_type,
                diagram_type=diagram_type,
                success=success,
                response_time=response_time,
                created_at=datetime.utcnow()
            )
            
            db.add(usage)
            db.commit()
            db.refresh(usage)
            
            logger.info(
                f"[TokenTracker] Recorded usage: {model_alias} "
                f"({input_tokens}+{output_tokens} tokens, ¥{total_cost:.6f})"
            )
            
            return usage
            
        except Exception as e:
            logger.error(f"[TokenTracker] Failed to record usage: {e}")
            db.rollback()
            return None
    
    @staticmethod
    def count_tokens_estimate(text: str) -> int:
        """
        Estimate token count from text (rough approximation).
        For accurate counting, use tiktoken or model-specific tokenizer.
        
        Rule of thumb: 1 token ≈ 4 characters for English, 1.5 chars for Chinese
        """
        # Simple heuristic
        char_count = len(text)
        
        # Check if text is mostly Chinese
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if chinese_chars > char_count * 0.5:
            # Mostly Chinese text
            return int(char_count / 1.5)
        else:
            # Mostly English/code
            return int(char_count / 4)

# Singleton instance
token_tracker = TokenTracker()
```

### Step 4: Modify LLM Clients to Return Token Usage

**File:** `clients/llm.py` (MODIFY)

Add token extraction to existing clients:

```python
# At top of file, add:
from services.token_tracker import token_tracker

# ============================================================================
# MODIFY: QwenClient.chat_completion()
# ============================================================================

async def chat_completion(self, messages: List[Dict], temperature: float = None,
                        max_tokens: int = 1000) -> Dict:  # CHANGED: Return dict instead of str
    """
    Send chat completion request to Qwen (async version)
    
    Returns:
        Dict with 'content' and 'usage' keys
    """
    try:
        # ... existing code ...
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.post(self.api_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    usage = data.get('usage', {})  # NEW: Extract usage
                    
                    return {
                        'content': content,
                        'usage': {
                            'input_tokens': usage.get('prompt_tokens', 0),
                            'output_tokens': usage.get('completion_tokens', 0),
                            'total_tokens': usage.get('total_tokens', 0)
                        }
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Qwen API error {response.status}: {error_text}")
                    raise Exception(f"Qwen API error: {response.status}")
    # ... rest of error handling ...

# ============================================================================
# MODIFY: DeepSeekClient.async_chat_completion()
# ============================================================================

async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                               max_tokens: int = 2000) -> Dict:  # CHANGED: Return dict
    """Async chat completion for DeepSeek"""
    try:
        # ... existing code ...
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.api_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    usage = data.get('usage', {})  # NEW: Extract usage
                    
                    return {
                        'content': content,
                        'usage': {
                            'input_tokens': usage.get('prompt_tokens', 0),
                            'output_tokens': usage.get('completion_tokens', 0),
                            'total_tokens': usage.get('total_tokens', 0)
                        }
                    }
    # ... rest of code ...

# ============================================================================
# MODIFY: HunyuanClient.async_chat_completion()
# ============================================================================

async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                               max_tokens: int = 2000) -> Dict:  # CHANGED: Return dict
    """Async chat completion for Hunyuan"""
    try:
        # ... existing code ...
        
        completion = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        content = completion.choices[0].message.content
        
        # NEW: Extract usage from OpenAI-compatible response
        usage = completion.usage if hasattr(completion, 'usage') else {}
        
        return {
            'content': content,
            'usage': {
                'input_tokens': usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0,
                'output_tokens': usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0,
                'total_tokens': usage.total_tokens if hasattr(usage, 'total_tokens') else 0
            }
        }
    # ... rest of code ...
```

**Important:** For streaming mode, we need to track tokens differently since usage comes at the end.

### Step 5: Modify LLM Service to Track Usage

**File:** `services/llm_service.py` (MODIFY)

```python
# Add import at top
from services.token_tracker import token_tracker
from config.database import SessionLocal

# ============================================================================
# MODIFY: chat() method
# ============================================================================

async def chat(
    self,
    prompt: str,
    model: str = 'qwen',
    temperature: Optional[float] = None,
    max_tokens: int = 2000,
    timeout: Optional[float] = None,
    system_message: Optional[str] = None,
    # NEW: Track usage parameters
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    session_id: Optional[str] = None,
    request_type: str = 'diagram_generation',
    diagram_type: Optional[str] = None,
    **kwargs
) -> str:
    """
    Chat with LLM (non-streaming).
    Automatically tracks token usage and costs.
    """
    import time
    start_time = time.time()
    
    try:
        # ... existing code to call LLM ...
        result = await self._call_single_model(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            system_message=system_message,
            **kwargs
        )
        
        response_time = time.time() - start_time
        
        # NEW: Track token usage
        if isinstance(result, dict) and 'usage' in result:
            usage = result['usage']
            
            # Track in background (don't block response)
            db = SessionLocal()
            try:
                await token_tracker.track_usage(
                    db=db,
                    model_alias=model,
                    input_tokens=usage.get('input_tokens', 0),
                    output_tokens=usage.get('output_tokens', 0),
                    request_type=request_type,
                    diagram_type=diagram_type,
                    user_id=user_id,
                    organization_id=organization_id,
                    session_id=session_id,
                    response_time=response_time,
                    success=True
                )
            finally:
                db.close()
            
            # Return just content for backward compatibility
            return result.get('content', result)
        
        return result
        
    except Exception as e:
        # Track failed request
        response_time = time.time() - start_time
        
        db = SessionLocal()
        try:
            # Estimate tokens from prompt
            estimated_input = token_tracker.count_tokens_estimate(prompt)
            
            await token_tracker.track_usage(
                db=db,
                model_alias=model,
                input_tokens=estimated_input,
                output_tokens=0,
                request_type=request_type,
                diagram_type=diagram_type,
                user_id=user_id,
                organization_id=organization_id,
                session_id=session_id,
                response_time=response_time,
                success=False
            )
        finally:
            db.close()
        
        raise

# ============================================================================
# MODIFY: stream_progressive() to track usage
# ============================================================================

async def stream_progressive(
    self,
    prompt: str,
    models: List[str] = None,
    temperature: Optional[float] = None,
    max_tokens: int = 2000,
    timeout: Optional[float] = None,
    system_message: Optional[str] = None,
    # NEW: Track usage parameters
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    session_id: Optional[str] = None,
    request_type: str = 'node_palette',
    diagram_type: Optional[str] = None,
    **kwargs
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream from multiple LLMs concurrently.
    Tracks token usage for each LLM.
    """
    if models is None:
        models = ['qwen', 'deepseek', 'kimi', 'hunyuan']
    
    # Generate session ID for this multi-LLM request
    if not session_id:
        session_id = token_tracker.generate_session_id()
    
    logger.info(f"[LLMService] stream_progressive() - session {session_id}")
    
    # Track token counts per LLM
    token_counts = {model: {'input': 0, 'output': 0, 'start_time': time.time()} for model in models}
    
    # ... existing streaming code ...
    
    async for chunk in ...:  # existing streaming loop
        event = chunk['event']
        llm = chunk['llm']
        
        if event == 'token':
            # Count output tokens
            token_counts[llm]['output'] += 1
            yield chunk
        
        elif event == 'complete':
            # LLM finished - record usage
            duration = chunk.get('duration', 0)
            output_tokens = token_counts[llm]['output']
            
            # Estimate input tokens from prompt
            input_tokens = token_tracker.count_tokens_estimate(prompt)
            
            # Track usage in background
            db = SessionLocal()
            try:
                await token_tracker.track_usage(
                    db=db,
                    model_alias=llm,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    request_type=request_type,
                    diagram_type=diagram_type,
                    user_id=user_id,
                    organization_id=organization_id,
                    session_id=session_id,
                    response_time=duration,
                    success=True
                )
            finally:
                db.close()
            
            yield chunk
        
        elif event == 'error':
            # Track failed request
            db = SessionLocal()
            try:
                input_tokens = token_tracker.count_tokens_estimate(prompt)
                
                await token_tracker.track_usage(
                    db=db,
                    model_alias=llm,
                    input_tokens=input_tokens,
                    output_tokens=0,
                    request_type=request_type,
                    diagram_type=diagram_type,
                    user_id=user_id,
                    organization_id=organization_id,
                    session_id=session_id,
                    response_time=0,
                    success=False
                )
            finally:
                db.close()
            
            yield chunk
```

---

## Step 6: Admin Panel API Endpoints

**File:** `routers/admin_cost_tracking.py` (NEW)

```python
"""
Admin API for Token Usage and Cost Tracking
View token consumption and costs across all LLM providers.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import List, Optional
import json

from config.database import get_db
from models.auth import User
from models.token_usage import TokenUsage, DailyCostSummary
from utils.auth import get_current_user, is_admin
from services.cost_calculator import cost_calculator

router = APIRouter(prefix="/api/admin/cost-tracking", tags=["admin-cost-tracking"])

# ============================================================================
# Token Usage Endpoints
# ============================================================================

@router.get("/overview")
async def get_cost_overview(
    days: int = Query(7, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get overall token usage and cost overview.
    Admin only.
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    since_date = datetime.utcnow() - timedelta(days=days)
    
    # Total stats
    total_stats = db.query(
        func.count(TokenUsage.id).label('total_requests'),
        func.sum(TokenUsage.total_tokens).label('total_tokens'),
        func.sum(TokenUsage.input_tokens).label('total_input_tokens'),
        func.sum(TokenUsage.output_tokens).label('total_output_tokens'),
        func.sum(TokenUsage.total_cost).label('total_cost'),
        func.avg(TokenUsage.response_time).label('avg_response_time'),
    ).filter(
        TokenUsage.created_at >= since_date
    ).first()
    
    # Per-model breakdown
    model_stats = db.query(
        TokenUsage.model_alias,
        TokenUsage.model_provider,
        func.count(TokenUsage.id).label('requests'),
        func.sum(TokenUsage.total_tokens).label('tokens'),
        func.sum(TokenUsage.total_cost).label('cost'),
        func.avg(TokenUsage.response_time).label('avg_time'),
    ).filter(
        TokenUsage.created_at >= since_date
    ).group_by(
        TokenUsage.model_alias,
        TokenUsage.model_provider
    ).all()
    
    # Request type breakdown
    request_type_stats = db.query(
        TokenUsage.request_type,
        func.count(TokenUsage.id).label('requests'),
        func.sum(TokenUsage.total_cost).label('cost'),
    ).filter(
        TokenUsage.created_at >= since_date
    ).group_by(
        TokenUsage.request_type
    ).all()
    
    return {
        "period_days": days,
        "total": {
            "requests": total_stats.total_requests or 0,
            "tokens": int(total_stats.total_tokens or 0),
            "input_tokens": int(total_stats.total_input_tokens or 0),
            "output_tokens": int(total_stats.total_output_tokens or 0),
            "cost_cny": round(total_stats.total_cost or 0, 2),
            "cost_usd": round((total_stats.total_cost or 0) / 7.3, 2),
            "avg_response_time": round(total_stats.avg_response_time or 0, 2),
        },
        "by_model": [
            {
                "model": stat.model_alias,
                "provider": stat.model_provider,
                "requests": stat.requests,
                "tokens": int(stat.tokens),
                "cost_cny": round(stat.cost, 2),
                "cost_usd": round(stat.cost / 7.3, 2),
                "avg_time": round(stat.avg_time, 2),
            }
            for stat in model_stats
        ],
        "by_request_type": [
            {
                "type": stat.request_type,
                "requests": stat.requests,
                "cost_cny": round(stat.cost, 2),
                "cost_usd": round(stat.cost / 7.3, 2),
            }
            for stat in request_type_stats
        ]
    }

@router.get("/daily-breakdown")
async def get_daily_breakdown(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get daily token usage and cost breakdown (for charts)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    since_date = datetime.utcnow() - timedelta(days=days)
    
    # Daily aggregation
    daily_stats = db.query(
        func.date(TokenUsage.created_at).label('date'),
        func.count(TokenUsage.id).label('requests'),
        func.sum(TokenUsage.total_tokens).label('tokens'),
        func.sum(TokenUsage.total_cost).label('cost'),
    ).filter(
        TokenUsage.created_at >= since_date
    ).group_by(
        func.date(TokenUsage.created_at)
    ).order_by(
        func.date(TokenUsage.created_at)
    ).all()
    
    return {
        "daily_data": [
            {
                "date": stat.date.isoformat(),
                "requests": stat.requests,
                "tokens": int(stat.tokens),
                "cost_cny": round(stat.cost, 2),
                "cost_usd": round(stat.cost / 7.3, 2),
            }
            for stat in daily_stats
        ]
    }

@router.get("/top-users")
async def get_top_users(
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get top users by cost"""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    since_date = datetime.utcnow() - timedelta(days=days)
    
    # Top users by cost
    top_users = db.query(
        TokenUsage.user_id,
        User.username,
        func.count(TokenUsage.id).label('requests'),
        func.sum(TokenUsage.total_tokens).label('tokens'),
        func.sum(TokenUsage.total_cost).label('cost'),
    ).join(
        User, TokenUsage.user_id == User.id
    ).filter(
        TokenUsage.created_at >= since_date,
        TokenUsage.user_id.isnot(None)
    ).group_by(
        TokenUsage.user_id,
        User.username
    ).order_by(
        func.sum(TokenUsage.total_cost).desc()
    ).limit(limit).all()
    
    return {
        "top_users": [
            {
                "user_id": user.user_id,
                "username": user.username,
                "requests": user.requests,
                "tokens": int(user.tokens),
                "cost_cny": round(user.cost, 2),
                "cost_usd": round(user.cost / 7.3, 2),
            }
            for user in top_users
        ]
    }

@router.get("/pricing")
async def get_pricing_info(
    current_user: User = Depends(get_current_user)
):
    """Get current pricing information for all models"""
    return {
        "pricing": cost_calculator.get_pricing_info(),
        "currency": "CNY",
        "unit": "per 1M tokens",
        "updated": "2025-01-01"
    }

@router.get("/estimate-cost")
async def estimate_cost(
    model: str = Query(..., description="Model alias (qwen, deepseek, kimi, hunyuan)"),
    input_tokens: int = Query(..., ge=1),
    output_tokens: int = Query(..., ge=1),
    current_user: User = Depends(get_current_user)
):
    """Estimate cost for given token usage"""
    return cost_calculator.estimate_cost(model, input_tokens, output_tokens)
```

---

## Step 7: Admin Panel UI

**File:** `templates/admin_cost_tracking.html` (NEW or add to existing admin.html)

```html
<!-- Cost Tracking Dashboard -->
<div class="admin-section" id="cost-tracking-section">
    <h2>💰 Token Usage & Cost Tracking</h2>
    
    <!-- Period Selector -->
    <div class="controls">
        <label>Time Period:</label>
        <select id="period-selector" onchange="loadCostData()">
            <option value="1">Last 24 Hours</option>
            <option value="7" selected>Last 7 Days</option>
            <option value="30">Last 30 Days</option>
            <option value="90">Last 90 Days</option>
        </select>
        
        <button onclick="refreshCostData()" class="btn-small">🔄 Refresh</button>
    </div>
    
    <!-- Summary Cards -->
    <div class="stats-cards">
        <div class="stat-card">
            <div class="stat-icon">📊</div>
            <div class="stat-content">
                <div class="stat-label">Total Requests</div>
                <div class="stat-value" id="total-requests">-</div>
            </div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon">🔢</div>
            <div class="stat-content">
                <div class="stat-label">Total Tokens</div>
                <div class="stat-value" id="total-tokens">-</div>
            </div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon">💵</div>
            <div class="stat-content">
                <div class="stat-label">Total Cost (CNY)</div>
                <div class="stat-value" id="total-cost-cny">-</div>
            </div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon">💵</div>
            <div class="stat-content">
                <div class="stat-label">Total Cost (USD)</div>
                <div class="stat-value" id="total-cost-usd">-</div>
            </div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon">⚡</div>
            <div class="stat-content">
                <div class="stat-label">Avg Response Time</div>
                <div class="stat-value" id="avg-response-time">-</div>
            </div>
        </div>
    </div>
    
    <!-- Charts -->
    <div class="charts-row">
        <div class="chart-container">
            <h3>Daily Cost Trend</h3>
            <canvas id="daily-cost-chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h3>Cost by Model</h3>
            <canvas id="model-cost-chart"></canvas>
        </div>
    </div>
    
    <div class="charts-row">
        <div class="chart-container">
            <h3>Requests by Type</h3>
            <canvas id="request-type-chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h3>Token Distribution</h3>
            <canvas id="token-distribution-chart"></canvas>
        </div>
    </div>
    
    <!-- Model Breakdown Table -->
    <div class="table-section">
        <h3>Model Breakdown</h3>
        <table id="model-breakdown-table">
            <thead>
                <tr>
                    <th>Model</th>
                    <th>Provider</th>
                    <th>Requests</th>
                    <th>Tokens</th>
                    <th>Cost (CNY)</th>
                    <th>Cost (USD)</th>
                    <th>Avg Time (s)</th>
                </tr>
            </thead>
            <tbody id="model-breakdown-tbody">
                <!-- Populated by JS -->
            </tbody>
        </table>
    </div>
    
    <!-- Top Users Table -->
    <div class="table-section">
        <h3>Top Users by Cost</h3>
        <table id="top-users-table">
            <thead>
                <tr>
                    <th>User ID</th>
                    <th>Username</th>
                    <th>Requests</th>
                    <th>Tokens</th>
                    <th>Cost (CNY)</th>
                    <th>Cost (USD)</th>
                </tr>
            </thead>
            <tbody id="top-users-tbody">
                <!-- Populated by JS -->
            </tbody>
        </table>
    </div>
</div>

<!-- Include Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<script>
// Cost Tracking Dashboard JavaScript

let dailyCostChart, modelCostChart, requestTypeChart, tokenDistChart;

async function loadCostData() {
    const days = document.getElementById('period-selector').value;
    
    try {
        // Load overview data
        const overview = await fetch(`/api/admin/cost-tracking/overview?days=${days}`, {
            headers: { 'Authorization': `Bearer ${getAuthToken()}` }
        }).then(r => r.json());
        
        // Update summary cards
        document.getElementById('total-requests').textContent = 
            overview.total.requests.toLocaleString();
        document.getElementById('total-tokens').textContent = 
            overview.total.tokens.toLocaleString();
        document.getElementById('total-cost-cny').textContent = 
            `¥${overview.total.cost_cny.toFixed(2)}`;
        document.getElementById('total-cost-usd').textContent = 
            `$${overview.total.cost_usd.toFixed(2)}`;
        document.getElementById('avg-response-time').textContent = 
            `${overview.total.avg_response_time.toFixed(2)}s`;
        
        // Update model breakdown table
        updateModelBreakdown(overview.by_model);
        
        // Load daily breakdown for chart
        const daily = await fetch(`/api/admin/cost-tracking/daily-breakdown?days=${days}`, {
            headers: { 'Authorization': `Bearer ${getAuthToken()}` }
        }).then(r => r.json());
        
        // Update charts
        updateDailyCostChart(daily.daily_data);
        updateModelCostChart(overview.by_model);
        updateRequestTypeChart(overview.by_request_type);
        
        // Load top users
        const topUsers = await fetch(`/api/admin/cost-tracking/top-users?days=${days}`, {
            headers: { 'Authorization': `Bearer ${getAuthToken()}` }
        }).then(r => r.json());
        
        updateTopUsersTable(topUsers.top_users);
        
    } catch (error) {
        console.error('Failed to load cost data:', error);
    }
}

function updateModelBreakdown(models) {
    const tbody = document.getElementById('model-breakdown-tbody');
    tbody.innerHTML = '';
    
    models.forEach(model => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td><strong>${model.model}</strong></td>
            <td><span class="badge">${model.provider}</span></td>
            <td>${model.requests.toLocaleString()}</td>
            <td>${model.tokens.toLocaleString()}</td>
            <td>¥${model.cost_cny.toFixed(2)}</td>
            <td>$${model.cost_usd.toFixed(2)}</td>
            <td>${model.avg_time.toFixed(2)}s</td>
        `;
    });
}

function updateTopUsersTable(users) {
    const tbody = document.getElementById('top-users-tbody');
    tbody.innerHTML = '';
    
    users.forEach((user, index) => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td>#${index + 1}</td>
            <td><strong>${user.username}</strong></td>
            <td>${user.requests.toLocaleString()}</td>
            <td>${user.tokens.toLocaleString()}</td>
            <td>¥${user.cost_cny.toFixed(2)}</td>
            <td>$${user.cost_usd.toFixed(2)}</td>
        `;
    });
}

function updateDailyCostChart(dailyData) {
    const ctx = document.getElementById('daily-cost-chart').getContext('2d');
    
    if (dailyCostChart) {
        dailyCostChart.destroy();
    }
    
    dailyCostChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dailyData.map(d => d.date),
            datasets: [{
                label: 'Cost (CNY)',
                data: dailyData.map(d => d.cost_cny),
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

function updateModelCostChart(models) {
    const ctx = document.getElementById('model-cost-chart').getContext('2d');
    
    if (modelCostChart) {
        modelCostChart.destroy();
    }
    
    modelCostChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: models.map(m => m.model),
            datasets: [{
                data: models.map(m => m.cost_cny),
                backgroundColor: [
                    'rgb(255, 99, 132)',
                    'rgb(54, 162, 235)',
                    'rgb(255, 205, 86)',
                    'rgb(75, 192, 192)'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

function updateRequestTypeChart(requestTypes) {
    const ctx = document.getElementById('request-type-chart').getContext('2d');
    
    if (requestTypeChart) {
        requestTypeChart.destroy();
    }
    
    requestTypeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: requestTypes.map(r => r.type),
            datasets: [{
                label: 'Requests',
                data: requestTypes.map(r => r.requests),
                backgroundColor: 'rgb(54, 162, 235)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

function refreshCostData() {
    loadCostData();
}

// Load on page load
if (document.getElementById('cost-tracking-section')) {
    loadCostData();
}
</script>

<style>
.stats-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin: 20px 0;
}

.stat-card {
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 20px;
    display: flex;
    align-items: center;
    gap: 15px;
}

.stat-icon {
    font-size: 2em;
}

.stat-label {
    font-size: 0.9em;
    color: #666;
    margin-bottom: 5px;
}

.stat-value {
    font-size: 1.5em;
    font-weight: bold;
    color: #333;
}

.charts-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin: 20px 0;
}

.chart-container {
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 20px;
    height: 300px;
}

.table-section {
    margin: 30px 0;
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 20px;
}

.table-section table {
    width: 100%;
    border-collapse: collapse;
}

.table-section th {
    background: #f5f5f5;
    padding: 12px;
    text-align: left;
    font-weight: 600;
}

.table-section td {
    padding: 12px;
    border-bottom: 1px solid #eee;
}

.badge {
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.85em;
    background: #e3f2fd;
    color: #1976d2;
}
</style>
```

---

## Summary

### What's Implemented

✅ **Token tracking** for all 4 LLMs (Qwen, DeepSeek, Kimi, Hunyuan)  
✅ **Cost calculation** using official pricing  
✅ **Database storage** with indexed queries  
✅ **Admin API** for analytics  
✅ **Dashboard UI** with charts and tables  
✅ **Real-time tracking** during multi-LLM requests  
✅ **Per-user and per-org** breakdowns  

### Key Features

- **Automatic tracking**: Every LLM call logs token usage
- **Multi-LLM support**: Session ID groups 4 concurrent LLM calls
- **Cost transparency**: See exact costs in CNY and USD
- **Performance metrics**: Track response times
- **Visual dashboards**: Charts for daily trends, model breakdown
- **Top users**: Identify heavy users

### Expected Data

**Sample dashboard numbers:**
```
Total Requests: 1,247
Total Tokens: 1,245,890
Total Cost: ¥58.23 ($7.98 USD)
Avg Response Time: 4.2s

By Model:
- Qwen: 312 requests, 310K tokens, ¥8.45
- DeepSeek: 311 requests, 312K tokens, ¥13.22
- Kimi: 312 requests, 311K tokens, ¥18.66
- Hunyuan: 312 requests, 312K tokens, ¥17.90
```

### Implementation Time

- **Database schema**: 1 hour
- **Cost calculator**: 30 min
- **Token tracker**: 1 hour
- **Modify LLM clients**: 2 hours
- **Admin API**: 2 hours
- **Admin UI**: 2 hours

**Total: ~8 hours**

This gives you complete visibility into your LLM costs! 📊💰


