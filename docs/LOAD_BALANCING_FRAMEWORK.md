# LLM Load Balancing Framework

> **SINGLE SOURCE OF TRUTH** for implementing LLM load balancing in MindGraph.
> For implementation, jump directly to [Step-by-Step Build Guide](#step-by-step-build-guide).

## Quick Reference

| What | Where |
|------|-------|
| **Implementation Steps** | [Step-by-Step Build Guide](#step-by-step-build-guide) |
| **Route Definitions** | [Load Balancing Architecture](#load-balancing-architecture) |
| **Model Mapping** | [Model Abstraction Layer](#model-abstraction-layer) |
| **Configuration** | [Environment Variables](#environment-variables) |
| **Multi-Worker** | [Multi-Worker Considerations](#multi-worker-considerations) |
| **Request Flows** | [Complete Request Flow](#complete-request-flow-with-load-balancing) |

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `services/load_balancer.py` | **CREATE** | Core load balancing logic |
| `clients/llm.py` | **MODIFY** | Add VolcengineClient class |
| `services/client_manager.py` | **MODIFY** | Register Volcengine clients |
| `config/settings.py` | **MODIFY** | Add load balancing config |
| `services/llm_service.py` | **MODIFY** | Integrate load balancer |
| `services/token_tracker.py` | **MODIFY** | Add Volcengine pricing |
| `env.example` | **VERIFY** | Environment variables |

### Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Load balancer location | LLM Service level | Transparent to routers/agents |
| Strategy | Weighted random | Multi-worker safe, stateless |
| Weight distribution | 30% Route A, 70% Route B | Volcengine higher capacity |
| Kimi provider | Always Volcengine | Dashscope only 60 RPM! |
| Model names | Logical → Physical mapping | Users never see provider details |

---

## Overview

This document describes the load balancing framework for distributing LLM requests between two provider routes to mitigate Dashscope rate limiting issues.

## Problem Statement

### The Real Bottleneck: Kimi on Dashscope

After reviewing actual rate limits from [Aliyun Bailian Console](https://bailian.console.aliyun.com), we discovered:

| Model on Dashscope | RPM Limit | Status |
|--------------------|-----------|--------|
| qwen-plus | 15,000 | OK |
| deepseek-v3.1 | 15,000 | OK |
| **Moonshot-Kimi-K2** | **60** | **BOTTLENECK!** |

**Kimi on Dashscope is severely limited to only 60 RPM!**

Meanwhile, Volcengine provides:
- **Kimi**: 5,000 RPM (83x higher than Dashscope!)
- **Doubao**: 30,000 RPM
- **DeepSeek**: 15,000 RPM

**Goal**: Route Kimi requests to Volcengine to eliminate the 60 RPM bottleneck, effectively increasing Kimi throughput by 83x.

---

## Provider Capabilities

### Dashscope (Aliyun)

| Model Alias | Model Name | Use Case |
|-------------|------------|----------|
| qwen | qwen-plus | Generation (high quality) |
| qwen-turbo | qwen-turbo | Classification (fast) |
| deepseek | deepseek-v3.1 | Reasoning |
| kimi | Moonshot-Kimi-K2-Instruct | Creative |

### Volcengine (ByteDance ARK)

| Model Alias | Model Name | Use Case |
|-------------|------------|----------|
| doubao | doubao-1-5-pro-32k-250115 | Generation |
| ark-deepseek | DeepSeek-V3 (or endpoint ID) | Reasoning |
| ark-qwen | Qwen3-14B (or endpoint ID) | Generation |
| ark-kimi | Kimi (or endpoint ID) | Creative |

---

## Load Balancing Architecture

### Route Definition

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INCOMING REQUEST                                   │
│                    (e.g., generate mind map for "汽车")                      │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                          ▼
                          ┌───────────────────────────────┐
                          │       LOAD BALANCER           │
                          │   (30% Route A / 70% Route B) │
                          └───────────────┬───────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    │                                           │
                    ▼ (30%)                                     ▼ (70%)
     ┌──────────────────────────────┐           ┌──────────────────────────────┐
     │         ROUTE A              │           │         ROUTE B              │
     │   (Dashscope + Volcengine)   │           │   (Full Volcengine)          │
     └──────────────┬───────────────┘           └──────────────┬───────────────┘
                    │                                          │
     ┌──────────────┴──────────────┐            ┌──────────────┴──────────────┐
     │                             │            │                             │
     ▼                             ▼            ▼                             ▼
┌─────────────┐            ┌─────────────┐ ┌─────────────┐            ┌─────────────┐
│  Dashscope  │            │ Volcengine  │ │ Volcengine  │            │ Volcengine  │
├─────────────┤            ├─────────────┤ ├─────────────┤            ├─────────────┤
│ qwen-plus   │            │   doubao    │ │ ark-qwen    │            │   doubao    │
│ deepseek    │            │  ark-kimi   │ │ ark-deepseek│            │  ark-kimi   │
└─────────────┘            └─────────────┘ └─────────────┘            └─────────────┘

Route A: qwen/deepseek on Dashscope, kimi/doubao on Volcengine
Route B: All 4 models on Volcengine
```

### Route A: Mixed (Dashscope + Volcengine for Doubao/Kimi)

- **Dashscope**: qwen, deepseek (15,000 RPM each)
- **Volcengine**: doubao (30,000 RPM), kimi (5,000 RPM)
- Avoids Dashscope Kimi bottleneck (only 60 RPM on Dashscope!)
- **4 models** for Node Palette: qwen, deepseek, kimi, doubao

### Route B: Full Volcengine

- **Volcengine**: ark-qwen, ark-deepseek, ark-kimi, doubao
- All requests go through Volcengine ARK API
- Uses Volcengine rate limits only
- **4 models** for Node Palette: all on Volcengine

---

## Model Abstraction Layer

### Principle: Users See Logical Names, Not Providers

**The frontend shows 4 buttons with logical model names. Users should NEVER know which provider is being used.**

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (User Sees)                          │
│                                                                  │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│   │ DeepSeek │  │   Qwen   │  │  Doubao  │  │   Kimi   │        │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                                                                  │
│   These are LOGICAL model names - provider-agnostic!             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (Load Balancer)                       │
│                                                                  │
│   Logical Name → Physical Model (based on selected route)        │
│                                                                  │
│   Route A: deepseek → Dashscope deepseek-v3.1                   │
│   Route B: deepseek → Volcengine ark-deepseek                   │
│                                                                  │
│   User never knows which provider is used!                       │
└─────────────────────────────────────────────────────────────────┘
```

### Three-Layer Model Naming

| Layer | Example | Description |
|-------|---------|-------------|
| **Logical Name** | `deepseek` | What users see in buttons, API requests |
| **Route Model** | `ark-deepseek` | Internal alias after load balancer |
| **Physical Model** | `ep-xxxxx` or `deepseek-v3` | Actual API model name/endpoint |

### Model Mapping Table

| Logical Name (Frontend) | Route A (Physical) | Route B (Physical) |
|-------------------------|--------------------|--------------------|
| `qwen` | Dashscope `qwen-plus-latest` | Volcengine `ark-qwen` |
| `deepseek` | Dashscope `deepseek-v3.1` | Volcengine `ark-deepseek` |
| `kimi` | Volcengine `ark-kimi` | Volcengine `ark-kimi` |
| `doubao` | Volcengine `doubao` | Volcengine `doubao` |

**Note**: Kimi and Doubao ALWAYS use Volcengine (even on Route A) to avoid Dashscope's 60 RPM Kimi limit!

### Internal Model Aliases (Backend Only)

These are NEVER exposed to frontend:

| Internal Alias | Provider | Purpose |
|----------------|----------|---------|
| `qwen-turbo` | Dashscope | Fast classification |
| `qwen-plus` | Dashscope | High-quality generation |
| `ark-qwen` | Volcengine | Qwen3-14B on ARK |
| `ark-deepseek` | Volcengine | DeepSeek-V3 on ARK |
| `ark-kimi` | Volcengine | Kimi on ARK |

### Frontend Button Configuration

**Buttons should NOT be hardcoded!** Use configuration:

```javascript
// static/js/config.js or from API
const MODEL_BUTTONS = [
    { id: 'deepseek', label: 'DeepSeek', icon: 'deepseek-icon' },
    { id: 'qwen', label: 'Qwen', icon: 'qwen-icon' },
    { id: 'doubao', label: 'Doubao', icon: 'doubao-icon' },
    { id: 'kimi', label: 'Kimi', icon: 'kimi-icon' }
];

// When user clicks button:
// Send: { model: 'deepseek' }  ← logical name
// Backend handles routing transparently
```

### API Contract

**Request (Frontend → Backend):**
```json
{
    "prompt": "Generate a mind map for 汽车",
    "model": "deepseek"  // ← Logical name only!
}
```

**Backend Processing:**
```python
# In load_balancer.py
logical_model = request.model  # 'deepseek'
route = self.select_route()    # 'route_a' or 'route_b'
physical_model = self.map_model(logical_model, route)
# Route A: 'deepseek' → uses Dashscope deepseek-v3.1 client
# Route B: 'deepseek' → uses Volcengine ark-deepseek client
```

**Response (Backend → Frontend):**
```json
{
    "success": true,
    "model": "deepseek",  // ← Return logical name, NOT provider!
    "data": { ... }
}
```

### Token Tracking (Analytics Only)

For internal analytics, track both logical and physical:

```python
await token_tracker.track_usage(
    model_alias='deepseek',           # Logical name (user-facing)
    model_provider='volcengine',      # Actual provider used
    route='route_b',                  # Which route was selected
    # ... other fields
)
```

**Note**: Hunyuan is not affected by load balancing as it uses Tencent's separate API.

---

## Configuration

### Environment Variables

```bash
# ============================================================================
# LOAD BALANCING CONFIGURATION
# ============================================================================

# Enable/disable load balancing (default: false for backward compatibility)
LOAD_BALANCING_ENABLED=true

# Strategy: 'weighted', 'round_robin', 'random'
LOAD_BALANCING_STRATEGY=weighted

# Weight distribution (must sum to 100)
# Format: route_a:weight,route_b:weight
# 30% Dashscope, 70% Volcengine (Volcengine has higher TPM limits)
LOAD_BALANCING_WEIGHTS=route_a:30,route_b:70

# ============================================================================
# VOLCENGINE ARK CONFIGURATION
# ============================================================================

# ARK API credentials
ARK_API_KEY=your-ark-api-key-here
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

# ============================================================================
# VOLCENGINE ENDPOINT IDs (Higher RPM than direct API!)
# ============================================================================
# Using endpoint IDs instead of model names provides significantly higher RPM limits.
# Create endpoints in Volcengine ARK Console: https://console.volcengine.com/ark

# Route B Endpoints (for load-balanced requests)
ARK_QWEN_ENDPOINT=ep-20251222212931-hjqh2       # Qwen3-14B
ARK_DEEPSEEK_ENDPOINT=ep-20251222212434-cxpzb   # DeepSeek-V3
ARK_KIMI_ENDPOINT=ep-20251222212350-wxbks       # Kimi
ARK_DOUBAO_ENDPOINT=ep-20251222212319-qqzb7     # Doubao (Route B)

# Route A Doubao (existing, uses model name - can also use endpoint for consistency)
ARK_DOUBAO_MODEL=doubao-1-5-pro-32k-250115

# ============================================================================
# VOLCENGINE RATE LIMITING (Per-Model Limits)
# ============================================================================
# Volcengine has MUCH higher limits than Dashscope!

# ============================================================================
# DASHSCOPE RATE LIMITS (Route A) - From Aliyun Bailian Console
# ============================================================================
# qwen-plus: 15,000 RPM, 5,000,000 TPM
DASHSCOPE_QWEN_RPM_LIMIT=15000
DASHSCOPE_QWEN_TPM_LIMIT=5000000

# deepseek-v3.1: 15,000 RPM, 1,200,000 TPM
DASHSCOPE_DEEPSEEK_RPM_LIMIT=15000
DASHSCOPE_DEEPSEEK_TPM_LIMIT=1200000

# Moonshot-Kimi-K2: 60 RPM, 100,000 TPM (BOTTLENECK!)
DASHSCOPE_KIMI_RPM_LIMIT=60
DASHSCOPE_KIMI_TPM_LIMIT=100000

# ============================================================================
# VOLCENGINE RATE LIMITS (Route B) - Much higher!
# ============================================================================
# Doubao: 30,000 RPM, 5,000,000 TPM
ARK_DOUBAO_RPM_LIMIT=30000
ARK_DOUBAO_TPM_LIMIT=5000000

# Kimi: 5,000 RPM, 500,000 TPM (83x better than Dashscope!)
ARK_KIMI_RPM_LIMIT=5000
ARK_KIMI_TPM_LIMIT=500000

# DeepSeek: 15,000 RPM, 1,500,000 TPM
ARK_DEEPSEEK_RPM_LIMIT=15000
ARK_DEEPSEEK_TPM_LIMIT=1500000

# Qwen3-14B: Elastic scaling (L5 tier, 4200 TPS = ~252K TPM)
ARK_QWEN_TPS_LIMIT=4200
ARK_QWEN_TPM_LIMIT=252000

# Rate limiting: Volcengine has high limits, Dashscope Kimi needs protection
ARK_RATE_LIMITING_ENABLED=false
DASHSCOPE_RATE_LIMITING_ENABLED=true  # Protect Kimi's 60 RPM limit
```

---

## Implementation Components

### 1. Load Balancer Module

**File**: `services/load_balancer.py`

```python
class LLMLoadBalancer:
    """
    Distributes requests between Route A (Mixed) and Route B (Full Volcengine).
    
    KEY PRINCIPLE: Users see logical model names (deepseek, qwen, kimi, doubao).
    The load balancer maps these to physical models transparently.
    """
    
    ROUTE_A = 'route_a'  # Mixed: Dashscope + Volcengine Doubao
    ROUTE_B = 'route_b'  # Full Volcengine
    
    # Logical model names (what frontend sends)
    LOGICAL_MODELS = ['deepseek', 'qwen', 'kimi', 'doubao']
    
    # Internal aliases (used within backend, never exposed to frontend)
    INTERNAL_ALIASES = ['qwen-turbo', 'qwen-plus']
    
    # Route A mapping: logical → physical (Dashscope + Volcengine for Kimi/Doubao)
    # Kimi and Doubao ALWAYS use Volcengine to avoid Dashscope's 60 RPM Kimi limit
    ROUTE_A_MODEL_MAP = {
        # Logical models (frontend buttons)
        'qwen': 'qwen',             # → Dashscope qwen-plus-latest (15,000 RPM)
        'deepseek': 'deepseek',     # → Dashscope deepseek-v3.1 (15,000 RPM)
        'kimi': 'ark-kimi',         # → Volcengine Kimi (5,000 RPM) - NOT Dashscope!
        'doubao': 'doubao',         # → Volcengine doubao (30,000 RPM)
        # Internal aliases
        'qwen-turbo': 'qwen-turbo', # → Dashscope qwen-turbo
        'qwen-plus': 'qwen-plus',   # → Dashscope qwen-plus-latest
        # Unaffected
        'hunyuan': 'hunyuan',       # → Tencent hunyuan
        'omni': 'omni',             # → Voice agent
    }
    
    # Route B mapping: logical → physical (Full Volcengine)
    # All 4 models on Volcengine
    ROUTE_B_MODEL_MAP = {
        # Logical models (frontend buttons)
        'qwen': 'ark-qwen',         # → Volcengine Qwen3-14B (Elastic)
        'deepseek': 'ark-deepseek', # → Volcengine DeepSeek-V3 (15,000 RPM)
        'kimi': 'ark-kimi',         # → Volcengine Kimi (5,000 RPM)
        'doubao': 'doubao',         # → Volcengine doubao (30,000 RPM)
        # Internal aliases also mapped
        'qwen-turbo': 'ark-qwen',   # → Volcengine Qwen3-14B
        'qwen-plus': 'ark-qwen',    # → Volcengine Qwen3-14B
        # Unaffected
        'hunyuan': 'hunyuan',       # → Tencent hunyuan (not on Volcengine)
        'omni': 'omni',             # → Voice agent
    }
    
    def __init__(self, strategy='weighted', weights=None, enabled=True):
        self.strategy = strategy
        self.weights = weights or {'route_a': 30, 'route_b': 70}
        self.enabled = enabled
        self._counter = 0
        self._current_route = None  # Cache for request consistency
        
    def select_route(self) -> str:
        """Select route based on strategy."""
        if not self.enabled:
            return self.ROUTE_A
        
        if self.strategy == 'round_robin':
            self._counter += 1
            return self.ROUTE_A if self._counter % 2 == 0 else self.ROUTE_B
        
        elif self.strategy == 'weighted':
            import random
            rand = random.randint(1, 100)
            if rand <= self.weights['route_a']:
                return self.ROUTE_A
            return self.ROUTE_B
        
        elif self.strategy == 'random':
            import random
            return random.choice([self.ROUTE_A, self.ROUTE_B])
        
        return self.ROUTE_A
    
    def map_model(self, logical_model: str, route: str) -> str:
        """
        Map logical model name to physical model based on route.
        
        Args:
            logical_model: Frontend model name (e.g., 'deepseek', 'qwen')
            route: Selected route ('route_a' or 'route_b')
            
        Returns:
            Physical model alias for the selected route
        """
        if route == self.ROUTE_A:
            return self.ROUTE_A_MODEL_MAP.get(logical_model, logical_model)
        else:
            return self.ROUTE_B_MODEL_MAP.get(logical_model, logical_model)
    
    def get_palette_models(self, route: str) -> list:
        """
        Get model list for Node Palette based on route.
        
        Args:
            route: Selected route
            
        Returns:
            List of physical model aliases for parallel streaming
            - Route A: 4 models (Dashscope qwen/deepseek + Volcengine kimi/doubao)
            - Route B: 4 models (all on Volcengine)
        """
        if route == self.ROUTE_A:
            # Mixed: Dashscope for qwen/deepseek, Volcengine for kimi/doubao
            return ['qwen', 'deepseek', 'ark-kimi', 'doubao']  # 4 models
        else:
            # All 4 models on Volcengine
            return ['ark-qwen', 'ark-deepseek', 'ark-kimi', 'doubao']  # 4 models
    
    def get_logical_name(self, physical_model: str) -> str:
        """
        Convert physical model back to logical name for API response.
        
        Users should NEVER see 'ark-deepseek' - they see 'deepseek'.
        """
        physical_to_logical = {
            'ark-deepseek': 'deepseek',
            'ark-qwen': 'qwen',
            'ark-kimi': 'kimi',
            'qwen-plus': 'qwen',
            'qwen-turbo': 'qwen',
            # Others map to themselves
        }
        return physical_to_logical.get(physical_model, physical_model)
```

### 2. Volcengine Multi-Model Client (Endpoint-Based)

**File**: `clients/llm.py` (expand existing)

**IMPORTANT**: Use endpoint IDs instead of model names for higher RPM!

```python
from openai import AsyncOpenAI
import os

class VolcengineClient:
    """
    Volcengine ARK client using endpoint IDs for higher RPM.
    
    Uses OpenAI-compatible API with endpoint IDs instead of model names
    to achieve higher request limits.
    """
    
    def __init__(self, model_alias: str):
        self.api_key = os.environ.get("ARK_API_KEY")
        self.base_url = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        self.model_alias = model_alias
        
        # Map alias to endpoint ID (NOT model name - endpoints have higher RPM!)
        self.endpoint_id = self._get_endpoint_id(model_alias)
        
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=60
        )
    
    def _get_endpoint_id(self, alias: str) -> str:
        """
        Map model alias to Volcengine endpoint ID.
        
        Endpoint IDs provide higher RPM than direct model names!
        """
        endpoint_map = {
            'ark-qwen': os.environ.get('ARK_QWEN_ENDPOINT', 'ep-20251222212931-hjqh2'),
            'ark-deepseek': os.environ.get('ARK_DEEPSEEK_ENDPOINT', 'ep-20251222212434-cxpzb'),
            'ark-kimi': os.environ.get('ARK_KIMI_ENDPOINT', 'ep-20251222212350-wxbks'),
            'doubao': os.environ.get('ARK_DOUBAO_ENDPOINT', 'ep-20251222212319-qqzb7'),
        }
        return endpoint_map.get(alias, alias)
    
    async def chat_completion(self, messages, temperature=0.7, max_tokens=2000):
        """Non-streaming chat completion using endpoint ID."""
        try:
            completion = await self.client.chat.completions.create(
                model=self.endpoint_id,  # Use endpoint ID for higher RPM!
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return completion.choices[0].message.content
        except Exception as e:
            # Error handling with Volcengine-specific parsing
            raise
    
    async def chat_completion_stream(self, messages, temperature=0.7, max_tokens=2000):
        """Streaming chat completion using endpoint ID."""
        stream = await self.client.chat.completions.create(
            model=self.endpoint_id,  # Use endpoint ID for higher RPM!
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                yield content
```

**Key Difference from Direct API:**
```python
# Direct API (Lower RPM) - DON'T USE
model="qwen3-14b-instruct"

# Endpoint ID (Higher RPM) - USE THIS!
model="ep-20251222212931-hjqh2"
```

### 3. Client Manager Updates

**File**: `services/client_manager.py`

```python
def initialize(self) -> None:
    # ... existing clients ...
    
    # Route B Volcengine clients
    self._clients['ark-qwen'] = VolcengineClient('ark-qwen')
    self._clients['ark-deepseek'] = VolcengineClient('ark-deepseek')
    self._clients['ark-kimi'] = VolcengineClient('ark-kimi')
    # doubao client already exists
```

### 4. LLM Service Integration

**File**: `services/llm_service.py`

```python
class LLMService:
    def __init__(self):
        self.load_balancer = None  # Initialized in initialize()
    
    def initialize(self) -> None:
        # ... existing initialization ...
        
        # Initialize load balancer
        if config.LOAD_BALANCING_ENABLED:
            self.load_balancer = LLMLoadBalancer(
                strategy=config.LOAD_BALANCING_STRATEGY,
                weights=config.LOAD_BALANCING_WEIGHTS,
                enabled=True
            )
            logger.info("[LLMService] Load balancer enabled")
    
    async def chat(self, prompt, model='qwen', ...):
        # Apply load balancing
        actual_model = model
        selected_route = None
        
        if self.load_balancer and self.load_balancer.enabled:
            selected_route = self.load_balancer.select_route()
            actual_model = self.load_balancer.map_model(model, selected_route)
            logger.debug(f"[LLMService] Route: {selected_route}, Model: {model} -> {actual_model}")
        
        # Get appropriate client
        client = self.client_manager.get_client(actual_model)
        
        # Use appropriate rate limiter based on route
        rate_limiter = self._get_rate_limiter(actual_model, selected_route)
        
        # ... rest of chat implementation ...
```

### 5. Rate Limiter Updates

**File**: `services/rate_limiter.py`

**Current State**: Single global rate limiter with generic QPM limits.

**Analysis with Actual RPM Numbers**:

| Provider | Model | RPM Limit | Rate Limiting Needed? |
|----------|-------|-----------|----------------------|
| Dashscope | qwen-plus-latest | 15,000 | **No** - very high |
| Dashscope | deepseek-v3.1 | 15,000 | **No** - very high |
| Dashscope | Moonshot-Kimi-K2 | 60 | N/A - we use Volcengine for Kimi! |
| Volcengine | ark-qwen | Elastic | **No** - elastic scaling |
| Volcengine | ark-deepseek | 15,000 | **No** - very high |
| Volcengine | ark-kimi | 5,000 | **Maybe** - still high |
| Volcengine | doubao | 30,000 | **No** - extremely high |

**Key Insight**: With our load balancing design:
- **Route A**: Kimi uses Volcengine (5,000 RPM) not Dashscope (60 RPM)
- **All models have 5,000+ RPM** - rate limiting may not be needed!
- **The bottleneck is eliminated** by routing Kimi to Volcengine

**Recommended Changes**:

```python
# Option 1: Disable rate limiting entirely (recommended for now)
DASHSCOPE_RATE_LIMITING_ENABLED=false
ARK_RATE_LIMITING_ENABLED=false

# Option 2: Keep conservative rate limiting as safety net
# services/rate_limiter.py

class ProviderRateLimiter:
    """Rate limiter that respects actual provider limits."""
    
    # Actual RPM limits from providers
    PROVIDER_LIMITS = {
        'dashscope': {
            'qwen': 15000,
            'qwen-plus': 15000,
            'qwen-plus-latest': 15000,
            'qwen-turbo': 1200,
            'deepseek': 15000,
            'kimi': 60,  # NOT USED - we route to Volcengine!
        },
        'volcengine': {
            'ark-qwen': 10000,     # Conservative estimate for elastic
            'ark-deepseek': 15000,
            'ark-kimi': 5000,
            'doubao': 30000,
        }
    }
    
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.rpm_limit = self.PROVIDER_LIMITS.get(provider, {}).get(model, 5000)
```

**Simplified Approach (Recommended)**:

Since all our models now have 5,000+ RPM, use a simple per-provider limiter:

```python
# In llm_service.py

def initialize(self) -> None:
    # ... existing code ...
    
    # With high RPM limits, we can be generous
    if config.DASHSCOPE_RATE_LIMITING_ENABLED:
        # Dashscope: qwen/deepseek have 15,000 RPM - use 10,000 as safe limit
        self.dashscope_limiter = DashscopeRateLimiter(
            qpm_limit=10000,  # Safe margin below 15,000
            concurrent_limit=500,
            enabled=True
        )
    
    if config.ARK_RATE_LIMITING_ENABLED:
        # Volcengine: lowest is ark-kimi at 5,000 RPM
        self.volcengine_limiter = DashscopeRateLimiter(
            qpm_limit=5000,  # Based on ark-kimi (lowest)
            concurrent_limit=500,
            enabled=True
        )
```

**Multi-Worker Consideration**:

With 4 workers, divide limits:
- Dashscope: 10,000 / 4 = 2,500 RPM per worker
- Volcengine: 5,000 / 4 = 1,250 RPM per worker

This is still plenty of capacity for most use cases!

---

## Request Flow Example

### Example: Generate Mind Map for "汽车"

**Request 1 (Route A - 30% chance)**:
```
User Request -> Load Balancer selects Route A
-> model='qwen' stays as 'qwen'
-> Uses Dashscope qwen-plus-latest
-> Rate limited by Dashscope limiter
-> If parallel calls needed (node palette), uses:
   - qwen (Dashscope)      - 15,000 RPM
   - deepseek (Dashscope)  - 15,000 RPM
   - ark-kimi (Volcengine) - 5,000 RPM (NOT Dashscope - avoids 60 RPM limit!)
   - doubao (Volcengine)   - 30,000 RPM
```

**Request 2 (Route B - 70% chance)**:
```
User Request -> Load Balancer selects Route B
-> model='qwen' mapped to 'ark-qwen'
-> Uses Volcengine ark-qwen
-> Rate limited by Volcengine limiter
-> If parallel calls needed (node palette), uses:
   - ark-qwen (Volcengine)     - Elastic
   - ark-deepseek (Volcengine) - 15,000 RPM
   - ark-kimi (Volcengine)     - 5,000 RPM
   - doubao (Volcengine)       - 30,000 RPM
```

---

## Rate Limit Capacity

### Provider Comparison (Actual Limits)

#### Dashscope (Aliyun Bailian) - Route A

| Model | RPM Limit | TPM Limit | Notes |
|-------|-----------|-----------|-------|
| **qwen-plus** | 15,000 | 5,000,000 | **Use this!** |
| **qwen-plus-latest** | 15,000 | 1,200,000 | **Use this!** |
| qwen-plus-2025-xx-xx | 60 | varies | Dated snapshots - LOW RPM! |
| **qwen-turbo** | 1,200 | 5,000,000 | Lower RPM |
| **deepseek-v3.1** | 15,000 | 1,200,000 | High capacity |
| **Moonshot-Kimi-K2** | **60** | 100,000 | **Very limited!** |

**IMPORTANT**: Always use `qwen-plus` or `qwen-plus-latest`, NOT dated versions like `qwen-plus-2025-12-01` (only 60 RPM!)

#### Volcengine (ByteDance ARK) - Route B

| Model | RPM Limit | TPM Limit | vs Dashscope |
|-------|-----------|-----------|--------------|
| **Doubao** | 30,000 | 5,000,000 | 2x qwen-plus |
| **DeepSeek** | 15,000 | 1,500,000 | Same as Dashscope |
| **Kimi** | 5,000 | 500,000 | **83x Dashscope Kimi!** |
| **Qwen3-14B** | Elastic | 4,200 TPS | Elastic scaling |

### Recommended Model Versions for High-Throughput Features

For **autocomplete** and **node palette** (high request volume), use these model versions:

| Feature | Recommended Model | RPM | TPM | Why |
|---------|-------------------|-----|-----|-----|
| Autocomplete | `qwen-plus-latest` | 15,000 | 1,200,000 | High RPM, sufficient TPM |
| Node Palette | `qwen-plus-latest` | 15,000 | 1,200,000 | High RPM, sufficient TPM |
| Classification | `qwen-turbo` | 1,200 | 5,000,000 | Fast |

**Model Comparison:**
| Model | RPM | TPM | Recommendation |
|-------|-----|-----|----------------|
| `qwen-plus-latest` | 15,000 | 1,200,000 | **Recommended - stable, high RPM** |
| `qwen-plus` | 15,000 | 5,000,000 | OK (more TPM if needed) |
| `qwen-plus-2025-xx-xx` | **60** | varies | **AVOID - low RPM!** |

**Recommended Config:**
```python
# In config/settings.py
QWEN_MODEL_CLASSIFICATION = 'qwen-turbo'       # 1,200 RPM (fast)
QWEN_MODEL_GENERATION = 'qwen-plus-latest'     # 15,000 RPM, 1.2M TPM (recommended)
```

**AVOID** dated snapshot versions like `qwen-plus-2025-12-01` - they have only **60 RPM**!

---

### Key Insight: Kimi is the Bottleneck!

```
Dashscope Kimi:  60 RPM (VERY LIMITED!)
Volcengine Kimi: 5,000 RPM (83x higher!)
```

**This is WHY we need load balancing - Kimi on Dashscope is severely limited!**

### Other Models Are Similar

| Model | Dashscope RPM | Volcengine RPM | Difference |
|-------|---------------|----------------|------------|
| Qwen | 15,000 | Elastic | Similar |
| DeepSeek | 15,000 | 15,000 | Same |
| **Kimi** | **60** | **5,000** | **83x better on Volcengine!** |
| Doubao | N/A | 30,000 | Volcengine only |

### Before Load Balancing (Current State)

```
Node Palette fires 4 LLMs in parallel:
┌─────────────────────────────────────────────────────────────────┐
│  qwen (Dashscope)     │ 15,000 RPM  │ OK                        │
│  deepseek (Dashscope) │ 15,000 RPM  │ OK                        │
│  kimi (Dashscope)     │ 60 RPM      │ BOTTLENECK! ← Problem!    │
│  doubao (Volcengine)  │ 30,000 RPM  │ OK                        │
└─────────────────────────────────────────────────────────────────┘

The slowest model (Kimi at 60 RPM) limits the entire parallel request!
```

### After Load Balancing

**Route A (30%): Mixed (Dashscope + Volcengine)**
```
┌─────────────────────────────────────────────────────────────────┐
│  qwen (Dashscope)          │ 15,000 RPM           │ OK          │
│  deepseek (Dashscope)      │ 15,000 RPM           │ OK          │
│  ark-kimi (Volcengine)     │ 5,000 RPM            │ OK          │
│  doubao (Volcengine)       │ 30,000 RPM           │ OK          │
└─────────────────────────────────────────────────────────────────┘
Kimi uses Volcengine even on Route A (avoids 60 RPM Dashscope limit!)
```

**Route B (70%): Full Volcengine**
```
┌─────────────────────────────────────────────────────────────────┐
│  ark-qwen (Volcengine)     │ Elastic (4,200 TPS)  │ OK          │
│  ark-deepseek (Volcengine) │ 15,000 RPM           │ OK          │
│  ark-kimi (Volcengine)     │ 5,000 RPM            │ OK          │
│  doubao (Volcengine)       │ 30,000 RPM           │ OK          │
└─────────────────────────────────────────────────────────────────┘
All 4 models on Volcengine with high capacity!
```

### Capacity Comparison by Model

| Model | Route A (Dashscope) | Route B (Volcengine) | Improvement |
|-------|---------------------|----------------------|-------------|
| Qwen | 15,000 RPM | Elastic | ~ |
| DeepSeek | 15,000 RPM | 15,000 RPM | Same |
| **Kimi** | **60 RPM** | **5,000 RPM** | **83x!** |
| Doubao | N/A | 30,000 RPM | N/A |

### Why 30/70 Split?

- **70% Route B**: Eliminates Kimi bottleneck for most requests
- **30% Route A**: Keeps some Dashscope usage for diversity/fallback
- Could go **10/90** or even **5/95** since Volcengine has much higher limits

---

## Multi-Worker Considerations

### Current Worker Configuration

The application uses Uvicorn with multiple workers:

```python
# From uvicorn_config.py and run_server.py
workers = int(os.getenv('UVICORN_WORKERS', multiprocessing.cpu_count()))
# Linux: typically 4-6 workers
# Windows: defaults to 1 worker (Playwright compatibility)
```

### Load Balancer at LLM Service Level - Multi-Worker Solutions

Since the load balancer intercepts at `llm_service.py` (not router level), and each worker has its own `LLMService` instance with isolated memory, we need to consider this carefully.

#### Problem Analysis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              NGINX / LOAD BALANCER                           │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   ┌─────────┐           ┌─────────┐           ┌─────────┐
   │ Worker 1│           │ Worker 2│           │ Worker 3│
   ├─────────┤           ├─────────┤           ├─────────┤
   │LLMService│          │LLMService│          │LLMService│
   │LoadBalancer│        │LoadBalancer│        │LoadBalancer│
   │(isolated) │         │(isolated) │         │(isolated) │
   └─────────┘           └─────────┘           └─────────┘
```

Each worker has its own `LoadBalancer` instance with:
- Own counter (if using round_robin)
- Own statistics
- Own random state

#### Strategy Comparison for Multi-Worker

| Strategy | Multi-Worker Safe? | Accuracy | Notes |
|----------|-------------------|----------|-------|
| `weighted` | ✅ **Yes** | Excellent | Each request independently selects with probability |
| `random` | ✅ Yes | Good | Stateless, probabilistic |
| `round_robin` | ❌ **No** | Poor | Counter per-worker, distribution skewed |

#### Recommended Solution: Weighted Random (Stateless)

**The `weighted` strategy works perfectly with multiple workers** because:

1. **Stateless per-request** - Each request independently rolls the dice
2. **No shared state needed** - No cross-worker coordination required
3. **Statistically accurate** - Over many requests, converges to exact 30/70 split
4. **No bottleneck** - No locking, no shared storage

```python
# In load_balancer.py - This works perfectly with multiple workers!

def select_route(self) -> str:
    """Stateless route selection - perfect for multi-worker."""
    if not self.enabled:
        return self.ROUTE_A
    
    if self.strategy == 'weighted':
        # Each request independently selects route
        # No shared state, no coordination needed!
        import random
        rand = random.randint(1, 100)
        if rand <= self.weights['route_a']:  # 30
            return self.ROUTE_A
        return self.ROUTE_B  # 70
    
    return self.ROUTE_A
```

#### Why This Works

```
Request Distribution Over Time (4 workers, 1000 total requests):

Worker 1: 250 requests → ~75 Route A, ~175 Route B (30/70)
Worker 2: 250 requests → ~75 Route A, ~175 Route B (30/70)
Worker 3: 250 requests → ~75 Route A, ~175 Route B (30/70)
Worker 4: 250 requests → ~75 Route A, ~175 Route B (30/70)
────────────────────────────────────────────────────────────
Total:   1000 requests → ~300 Route A, ~700 Route B (30/70) ✓
```

Each worker independently achieves the correct distribution!

#### Statistics Aggregation (Optional Enhancement)

If you want to track actual route distribution across all workers:

**Option 1: Log-based aggregation (Simplest)**
```python
# Each worker logs route selection
logger.info(f"[LoadBalancer] Route: {route}, Model: {model}")

# Aggregate from logs using ELK/Grafana
# No code changes needed!
```

**Option 2: File-based counters**
```python
# Append to shared file (thread-safe with file locking)
import fcntl

def track_route(route: str):
    with open('data/route_stats.log', 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(f"{datetime.now().isoformat()},{route}\n")
        fcntl.flock(f, fcntl.LOCK_UN)
```

**Option 3: Redis counters (Production-grade)**
```python
import redis

class LoadBalancerStats:
    def __init__(self):
        self.redis = redis.from_url(os.getenv('REDIS_URL'))
    
    async def track_route(self, route: str):
        key = f"lb:route:{route}:{datetime.now().strftime('%Y%m%d%H')}"
        await self.redis.incr(key)
        await self.redis.expire(key, 86400)  # 24h retention
```

### Impact on Load Balancing and Rate Limiting

**Each worker runs in a separate process with isolated memory.** This affects:

| Component | Issue | Impact |
|-----------|-------|--------|
| **Rate Limiter Counter** | Each worker has its own QPM counter | 4 workers × 200 QPM = potentially 800 requests hitting API |
| **Load Balancer Counter** | Round-robin counter is per-worker | Distribution may vary per worker |
| **Statistics** | Stats are not aggregated across workers | Metrics show per-worker, not global |

### Rate Limiter Accuracy Problem

**Current Situation (Already a Problem)**:
```
Worker 1: Tracks 200 QPM → allows 200 requests
Worker 2: Tracks 200 QPM → allows 200 requests
Worker 3: Tracks 200 QPM → allows 200 requests
Worker 4: Tracks 200 QPM → allows 200 requests
--------------------------------------------
Total hitting Dashscope: Up to 800 requests/minute!
Dashscope limit: 200 QPM → RATE LIMIT ERRORS
```

**This is an existing bug, not introduced by load balancing.**

### Solution Options

#### Option 1: Divide Limits by Worker Count (Simple, Recommended)

Adjust QPM limits per worker at startup:

```python
# In llm_service.py initialize()
import os
import multiprocessing

worker_count = int(os.getenv('UVICORN_WORKERS', multiprocessing.cpu_count()))
effective_qpm = config.DASHSCOPE_QPM_LIMIT // worker_count
effective_concurrent = config.DASHSCOPE_CONCURRENT_LIMIT // worker_count

self.rate_limiter = initialize_rate_limiter(
    qpm_limit=effective_qpm,  # 200 / 4 = 50 QPM per worker
    concurrent_limit=effective_concurrent,
    enabled=config.DASHSCOPE_RATE_LIMITING_ENABLED
)
```

**Pros**: Simple, no external dependencies
**Cons**: Conservative (wastes capacity if workers have uneven load)

#### Option 2: Shared State via File (Medium Complexity)

Use file-based locking for shared counter (similar to existing rate limiter file storage [[memory:6981566]]):

```python
# In rate_limiter.py
import fcntl  # File locking
import json
from pathlib import Path

class SharedRateLimiter:
    def __init__(self, state_file='data/rate_limiter_state.json'):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
    
    def acquire(self):
        with open(self.state_file, 'r+') as f:
            fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock
            state = json.load(f)
            # Check and update counters
            fcntl.flock(f, fcntl.LOCK_UN)
```

**Pros**: Accurate global tracking, no external dependencies
**Cons**: File I/O overhead, Windows compatibility (fcntl)

#### Option 3: Redis Shared State (High Accuracy, More Complex)

Use Redis for atomic counters shared across workers:

```python
import redis

class RedisRateLimiter:
    def __init__(self, redis_url='redis://localhost:6379'):
        self.redis = redis.from_url(redis_url)
    
    async def acquire(self):
        key = f"rate_limit:dashscope:{datetime.now().strftime('%Y%m%d%H%M')}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 60)
        return count <= self.qpm_limit
```

**Pros**: Most accurate, handles distributed deployments
**Cons**: External dependency (Redis), more complex setup

### Recommendation for This Project

**Use Option 1 (Divide by Worker Count)** because:

1. You already use file-based storage for rate limiting [[memory:6981566]]
2. Simple to implement and maintain
3. No external dependencies
4. Slightly conservative but safe

### Load Balancer Strategy Recommendation

For multi-worker environments, use **`weighted` or `random` strategy** instead of `round_robin`:

| Strategy | Multi-Worker Behavior | Recommendation |
|----------|----------------------|----------------|
| `round_robin` | Each worker has own counter, distribution skewed | Not recommended |
| `weighted` | Random per-request, statistically accurate | **Recommended** |
| `random` | Random per-request, statistically accurate | Good alternative |

```python
# Recommended configuration
LOAD_BALANCING_STRATEGY=weighted
LOAD_BALANCING_WEIGHTS=route_a:50,route_b:50
```

With `weighted` strategy:
- Each request independently selects route with 50% probability
- Across many requests, distribution converges to 50/50
- No cross-worker state needed

### Updated Environment Variables

```bash
# Worker-aware rate limiting
# Set these to TOTAL limits; system will divide by worker count automatically
DASHSCOPE_QPM_LIMIT=200        # Total across all workers
DASHSCOPE_CONCURRENT_LIMIT=50   # Total across all workers
ARK_QPM_LIMIT=200               # Total across all workers  
ARK_CONCURRENT_LIMIT=50         # Total across all workers

# Number of workers (auto-detected if not set)
# UVICORN_WORKERS=4
```

### Implementation Changes for Multi-Worker

Add to `services/llm_service.py`:

```python
def initialize(self) -> None:
    # ... existing code ...
    
    # Calculate per-worker limits
    import multiprocessing
    worker_count = int(os.getenv('UVICORN_WORKERS', multiprocessing.cpu_count()))
    
    # On Windows, default is 1 worker
    if sys.platform == 'win32':
        worker_count = int(os.getenv('UVICORN_WORKERS', 1))
    
    if config.DASHSCOPE_RATE_LIMITING_ENABLED:
        per_worker_qpm = max(1, config.DASHSCOPE_QPM_LIMIT // worker_count)
        per_worker_concurrent = max(1, config.DASHSCOPE_CONCURRENT_LIMIT // worker_count)
        
        logger.info(
            f"[LLMService] Rate limiting: {config.DASHSCOPE_QPM_LIMIT} QPM / {worker_count} workers "
            f"= {per_worker_qpm} QPM per worker"
        )
        
        self.rate_limiter = initialize_rate_limiter(
            qpm_limit=per_worker_qpm,
            concurrent_limit=per_worker_concurrent,
            enabled=True
        )
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `services/load_balancer.py` | **Create** | Core load balancing logic |
| `clients/volcengine.py` | **Create** | Multi-model Volcengine client |
| `services/client_manager.py` | **Modify** | Register new Volcengine clients |
| `services/llm_service.py` | **Modify** | Integrate load balancer |
| `services/rate_limiter.py` | **Modify** | Add Volcengine rate limiter |
| `config/settings.py` | **Modify** | Add load balancing and ARK model configs |
| `env.example` | **Modify** | Document new environment variables |

---

## Rollout Strategy

### Phase 1: Preparation
1. Add Volcengine multi-model configuration
2. Create Volcengine client for ark-qwen and ark-deepseek
3. Test Volcengine models independently

### Phase 2: Load Balancer Implementation
1. Create load balancer module
2. Integrate with LLM service
3. Add Volcengine rate limiter

### Phase 3: Testing
1. Test with `LOAD_BALANCING_ENABLED=false` (no change)
2. Test with `LOAD_BALANCING_WEIGHTS=route_a:100,route_b:0` (Route A only)
3. Test with `LOAD_BALANCING_WEIGHTS=route_a:0,route_b:100` (Route B only)
4. Test with `LOAD_BALANCING_WEIGHTS=route_a:50,route_b:50` (balanced)

### Phase 4: Production Rollout
1. Start with 90/10 split (Route A dominant)
2. Monitor error rates and latency
3. Gradually increase to 50/50

---

## Monitoring and Metrics

### Key Metrics to Track

1. **Request Distribution**
   - Requests per route (A vs B)
   - Actual percentage split

2. **Rate Limiter Stats**
   - Dashscope QPM usage
   - Volcengine QPM usage
   - Wait times per limiter

3. **Error Rates**
   - Errors per route
   - Errors per model

4. **Latency**
   - Response time per route
   - Response time per model

### Logging

```python
logger.info(f"[LoadBalancer] Route: {route}, Original: {model}, Mapped: {actual_model}")
logger.info(f"[LoadBalancer] Stats: Route A: {count_a}, Route B: {count_b}")
```

---

## Fallback Behavior

### If Volcengine Fails (Route B)

Options:
1. **Fail Fast**: Return error immediately
2. **Fallback to Route A**: Retry on Dashscope (may cause rate limit issues)
3. **Queue**: Wait and retry on Volcengine

**Recommendation**: Fail fast initially, add fallback later if needed.

### If Model Not Available

If `ark-deepseek` is not configured, fall back to `doubao` or `ark-qwen`.

---

## Future Enhancements

1. **Adaptive Load Balancing**: Adjust weights based on real-time rate limit usage
2. **Per-User Routing**: Consistent routing per user/session
3. **Geographic Routing**: Route based on user location
4. **Cost Optimization**: Route based on model pricing
5. **Health-Based Routing**: Route away from unhealthy providers

---

## Appendix: Volcengine ARK Endpoint Configuration

### Why Endpoints vs Direct API?

| Approach | RPM Limit | Use Case |
|----------|-----------|----------|
| Direct API | Lower | Development/testing |
| Endpoint ID | **Higher** | Production with load balancing |

**Using endpoint IDs provides significantly higher RPM limits!**

### Your Volcengine ARK Endpoints

Based on your configuration, the following endpoints are available:

```bash
# ============================================================================
# VOLCENGINE ARK ENDPOINT CONFIGURATION
# ============================================================================

ARK_API_KEY=your-ark-api-key-here
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

# Route B Endpoints (Higher RPM via endpoint IDs)
ARK_QWEN_ENDPOINT=ep-20251222212931-hjqh2       # Qwen3-14B endpoint
ARK_DEEPSEEK_ENDPOINT=ep-20251222212434-cxpzb   # DeepSeek-V3 endpoint
ARK_KIMI_ENDPOINT=ep-20251222212350-wxbks       # Kimi endpoint
ARK_DOUBAO_ENDPOINT=ep-20251222212319-qqzb7     # Doubao endpoint

# Existing Doubao (Route A uses this)
ARK_DOUBAO_MODEL=doubao-1-5-pro-32k-250115
```

### Client Implementation (Using OpenAI SDK)

```python
from openai import AsyncOpenAI
import os

class VolcengineClient:
    """
    Volcengine ARK client using endpoint IDs for higher RPM.
    Uses OpenAI-compatible API.
    """
    
    def __init__(self, model_alias: str):
        self.api_key = os.environ.get("ARK_API_KEY")
        self.base_url = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        self.model_alias = model_alias
        
        # Map alias to endpoint ID (higher RPM!)
        self.endpoint_id = self._get_endpoint_id(model_alias)
        
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=60
        )
    
    def _get_endpoint_id(self, alias: str) -> str:
        """Map model alias to Volcengine endpoint ID."""
        endpoint_map = {
            'ark-qwen': os.environ.get('ARK_QWEN_ENDPOINT', 'ep-20251222212931-hjqh2'),
            'ark-deepseek': os.environ.get('ARK_DEEPSEEK_ENDPOINT', 'ep-20251222212434-cxpzb'),
            'ark-kimi': os.environ.get('ARK_KIMI_ENDPOINT', 'ep-20251222212350-wxbks'),
            'doubao': os.environ.get('ARK_DOUBAO_ENDPOINT', 'ep-20251222212319-qqzb7'),
        }
        return endpoint_map.get(alias, alias)
    
    async def chat_completion(self, messages, temperature=0.7, max_tokens=2000):
        """Non-streaming chat completion."""
        completion = await self.client.chat.completions.create(
            model=self.endpoint_id,  # Use endpoint ID, NOT model name!
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content
    
    async def chat_completion_stream(self, messages, temperature=0.7, max_tokens=2000):
        """Streaming chat completion."""
        stream = await self.client.chat.completions.create(
            model=self.endpoint_id,  # Use endpoint ID, NOT model name!
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                yield content
```

### Endpoint ID vs Model Name Comparison

| Model Alias | Direct API (Lower RPM) | Endpoint ID (Higher RPM) |
|-------------|------------------------|--------------------------|
| ark-qwen | `qwen3-14b-instruct` | `ep-20251222212931-hjqh2` |
| ark-deepseek | `deepseek-v3` | `ep-20251222212434-cxpzb` |
| ark-kimi | `kimi-k2` | `ep-20251222212350-wxbks` |
| doubao | `doubao-1-5-pro-32k` | `ep-20251222212319-qqzb7` |

### Updated Physical Model Resolution

```python
# In VolcengineClient
# When calling API, use endpoint ID:
completion = await self.client.chat.completions.create(
    model="ep-20251222212931-hjqh2",  # Endpoint ID for higher RPM!
    messages=[
        {"role": "system", "content": "你是人工智能助手"},
        {"role": "user", "content": prompt},
    ],
)
```

### Benefits of Endpoint-Based Routing

1. **Higher RPM**: Endpoint IDs have dedicated quota, not shared with direct API
2. **Configurable**: Can change endpoints without code changes
3. **Monitoring**: Volcengine console shows per-endpoint metrics
4. **Isolation**: Each endpoint has independent rate limits

---

## Comprehensive LLM Module Review

### Overview of LLM Usage in Codebase

The load balancer must integrate with ALL LLM-related modules. Here is a complete inventory:

### 1. Token Tracker (`services/token_tracker.py`)

**Current State:**
```python
MODEL_PRICING = {
    'qwen': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope'},
    'qwen-turbo': {'input': 0.3, 'output': 0.6, 'provider': 'dashscope'},
    'qwen-plus': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope'},
    'deepseek': {'input': 0.4, 'output': 2.0, 'provider': 'dashscope'},
    'kimi': {'input': 2.0, 'output': 6.0, 'provider': 'dashscope'},
    'hunyuan': {'input': 0.45, 'output': 0.5, 'provider': 'tencent'},
}
```

**ISSUES FOUND:**
1. Missing `doubao` pricing - Volcengine Doubao not tracked!
2. Missing Volcengine model pricing for Route B (`ark-qwen`, `ark-deepseek`, `ark-kimi`)
3. No `route` field to track which route was used
4. No distinction between logical and physical model names

**REQUIRED CHANGES:**
```python
MODEL_PRICING = {
    # Dashscope models (Route A physical names)
    'qwen': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope', 'logical': 'qwen'},
    'qwen-turbo': {'input': 0.3, 'output': 0.6, 'provider': 'dashscope', 'logical': 'qwen'},
    'qwen-plus': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope', 'logical': 'qwen'},
    'deepseek': {'input': 0.4, 'output': 2.0, 'provider': 'dashscope', 'logical': 'deepseek'},
    'kimi': {'input': 2.0, 'output': 6.0, 'provider': 'dashscope', 'logical': 'kimi'},
    'hunyuan': {'input': 0.45, 'output': 0.5, 'provider': 'tencent', 'logical': 'hunyuan'},
    
    # Volcengine models (physical names)
    'doubao': {'input': 0.3, 'output': 0.9, 'provider': 'volcengine', 'logical': 'doubao'},
    'ark-qwen': {'input': 0.35, 'output': 1.0, 'provider': 'volcengine', 'logical': 'qwen'},
    'ark-deepseek': {'input': 0.4, 'output': 1.8, 'provider': 'volcengine', 'logical': 'deepseek'},
    'ark-kimi': {'input': 1.8, 'output': 5.5, 'provider': 'volcengine', 'logical': 'kimi'},
}
```

**Token Tracking Call (with abstraction):**
```python
await token_tracker.track_usage(
    model_alias='deepseek',           # Logical name (for user-facing reports)
    physical_model='ark-deepseek',    # Physical model (for cost calculation)
    model_provider='volcengine',      # Actual provider
    route='route_b',                  # Which route was selected
    # ... other fields
)
```

**Database Schema Update:**
```sql
ALTER TABLE token_usage ADD COLUMN route VARCHAR(20);           -- 'route_a' or 'route_b'
ALTER TABLE token_usage ADD COLUMN physical_model VARCHAR(50);  -- 'ark-deepseek', 'qwen-plus', etc.
```

**Analytics Views:**
- **User-facing reports**: Group by `model_alias` (logical name)
- **Cost analysis**: Group by `physical_model` (actual pricing)
- **Load balancing metrics**: Group by `route`

---

### 2. Node Palette (`agents/node_palette/base_palette_generator.py`)

**Current State:**
```python
class BasePaletteGenerator(ABC):
    def __init__(self):
        self.llm_service = llm_service
        # NOTE: Hunyuan disabled due to 5 concurrent connection limit
        self.llm_models = ['qwen', 'deepseek', 'kimi', 'doubao']
```

**CRITICAL FINDING:**
- Fires 4 LLMs in PARALLEL using `llm_service.stream_progressive()`
- Models are HARDCODED: `['qwen', 'deepseek', 'kimi', 'doubao']`
- This is the most rate-limit-intensive feature!

**SOLUTION: Keep Logical Names, Map in LLM Service**

Node Palette should continue to use logical names. The LLM service handles mapping internally:

```python
class BasePaletteGenerator(ABC):
    def __init__(self):
        self.llm_service = llm_service
        # Use LOGICAL model names (same as frontend buttons)
        # LLM Service will map to physical models based on route
        self.llm_models = ['qwen', 'deepseek', 'kimi', 'doubao']
```

**In LLM Service `stream_progressive()`:**
```python
async def stream_progressive(self, prompt, models, ...):
    # Select route ONCE for this request
    route = self.load_balancer.select_route()
    
    # Map logical models to physical models
    physical_models = [
        self.load_balancer.map_model(m, route) 
        for m in models
    ]
    # Route A: ['qwen', 'deepseek', 'ark-kimi', 'doubao']
    #          (Dashscope for qwen/deepseek, Volcengine for kimi/doubao)
    # Route B: ['ark-qwen', 'ark-deepseek', 'ark-kimi', 'doubao']
    #          (All Volcengine)
    
    # Stream from physical models
    for model in physical_models:
        client = self.client_manager.get_client(model)
        # ... stream tokens
```

**Node Palette Output - Logical Names Only:**
```python
# When yielding node events, use logical names
yield {
    'event': 'node_generated',
    'node': {
        'text': 'Some generated content',
        'source_llm': 'deepseek',  # ← Logical name, NOT 'ark-deepseek'!
    }
}
```

**Route Mapping Summary:**

| Logical (Frontend/Node Palette) | Route A (Physical) | Route B (Physical) |
|---------------------------------|--------------------|--------------------|
| qwen | qwen → Dashscope | ark-qwen → Volcengine |
| deepseek | deepseek → Dashscope | ark-deepseek → Volcengine |
| kimi | ark-kimi → Volcengine | ark-kimi → Volcengine |
| doubao | doubao → Volcengine | doubao → Volcengine |

**Note**: Kimi and Doubao ALWAYS use Volcengine to avoid Dashscope's 60 RPM Kimi limit!

---

### 3. Tab Mode Agent (`agents/tab_mode/tab_agent.py`)

**Current State:**
```python
class TabAgent(BaseAgent):
    def __init__(self, model='qwen-plus'):
        super().__init__(model=model)
        
    async def generate_suggestions(self, ...):
        response = await llm_service.chat(
            prompt=partial_input or "Provide suggestions",
            model='qwen-plus',  # HARDCODED!
            ...
        )
```

**ISSUE FOUND:**
- Model is hardcoded to `'qwen-plus'`
- Does NOT respect load balancing

**REQUIRED CHANGES:**
```python
async def generate_suggestions(self, ...):
    # Let load balancer decide model
    # Pass 'qwen-plus' as hint, but load balancer may map to 'ark-qwen'
    response = await llm_service.chat(
        prompt=partial_input or "Provide suggestions",
        model=self.model,  # 'qwen-plus' -> mapped by load balancer
        ...
    )
```

---

### 4. Tab Mode Router (`routers/tab_mode.py`)

**Current State:**
```python
# Determine model (default to qwen-plus for generation)
model = 'qwen-plus'
if req.llm:
    # Map 'qwen' to 'qwen-plus' for generation tasks
    if model_str == 'qwen':
        model = 'qwen-plus'
    else:
        model = model_str

# Create agent
agent = TabAgent(model=model)
```

**ANALYSIS:**
- Router determines model before creating agent
- Load balancer should intercept at LLM service level, NOT router level
- No changes needed here if LLM service handles mapping

---

### 5. Main Agent (`agents/main_agent.py`)

**Current State:**
- Uses `llm_service.chat()` and `llm_service.chat_stream()`
- Model is passed as parameter from routers

**ANALYSIS:**
- Load balancer at LLM service level will handle this automatically
- No changes needed in main_agent.py

---

### 6. Diagram Generation API (`routers/api.py`)

**Current State:**
```python
# Calls main_agent which calls llm_service
# Model selection happens at agent level
```

**ANALYSIS:**
- Load balancer at LLM service level will handle this
- No changes needed in api.py

---

### 7. Voice Agent (`services/voice_agent.py`)

**Current State:**
- Uses `omni` client for voice processing
- Not affected by load balancing (different API)

**ANALYSIS:**
- No changes needed

---

## Integration Points Summary

| Module | LLM Method | Models Used | Changes Required |
|--------|-----------|-------------|------------------|
| `llm_service.py` | `chat()`, `chat_stream()` | Various | **Core integration point** |
| `llm_service.py` | `stream_progressive()` | 4 models parallel | Route-based model mapping |
| `token_tracker.py` | N/A | Pricing lookup | Add Volcengine pricing |
| `base_palette_generator.py` | `stream_progressive()` | Hardcoded list | Model list from load balancer |
| `tab_agent.py` | `chat()` | qwen-plus | Use load-balanced model |
| `main_agent.py` | `chat()`, `chat_stream()` | Passed from router | No change (handled by service) |
| `voice_agent.py` | `omni` client | omni | Not affected |

---

## Complete Request Flow with Load Balancing

### Tab Mode Autocomplete - Detailed Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: HTTP Request                                                         │
│                                                                              │
│ POST /api/tab_suggestions                                                   │
│ {                                                                            │
│   "partial_input": "汽",                                                    │
│   "diagram_type": "circle_map",                                             │
│   "llm": "qwen"                                                              │
│ }                                                                            │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Router (routers/tab_mode.py)                                         │
│                                                                              │
│ # Map 'qwen' to 'qwen-plus' for generation tasks                            │
│ model = 'qwen-plus'  # Logical name                                          │
│ agent = TabAgent(model=model)                                                │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Agent (agents/tab_mode/tab_agent.py)                                 │
│                                                                              │
│ async def generate_suggestions(...):                                         │
│     response = await llm_service.chat(                                       │
│         prompt=prompt,                                                       │
│         model='qwen-plus',  # Still logical name                             │
│         ...                                                                  │
│     )                                                                        │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: LLM Service - Load Balancing (services/llm_service.py)               │
│                                                                              │
│ async def chat(self, prompt, model='qwen', ...):                             │
│     # ──────────────────────────────────────────────────────────────────    │
│     # 🎯 LOAD BALANCER INTERCEPTS HERE                                       │
│     # ──────────────────────────────────────────────────────────────────    │
│     if self.load_balancer and self.load_balancer.enabled:                    │
│         route = self.load_balancer.select_route()  # 30% A, 70% B            │
│         actual_model = self.load_balancer.map_model(model, route)            │
│                                                                              │
│         # Route A: 'qwen-plus' → 'qwen-plus' (Dashscope)                    │
│         # Route B: 'qwen-plus' → 'ark-qwen' (Volcengine)                    │
│                                                                              │
│     client = self.client_manager.get_client(actual_model)                    │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
           ┌──────────────────────────┴──────────────────────────┐
           │                                                      │
           ▼ (Route A - 30%)                                      ▼ (Route B - 70%)
┌──────────────────────────────┐                   ┌──────────────────────────────┐
│ STEP 5A: Dashscope Client    │                   │ STEP 5B: Volcengine Client   │
│                              │                   │                              │
│ DashscopeQwenClient          │                   │ VolcengineClient('ark-qwen') │
│ model = 'qwen-plus-latest'   │                   │ endpoint = ARK_QWEN_ENDPOINT │
│ API: dashscope.aliyuncs.com  │                   │ API: ark.cn-beijing.volces.com│
│ RPM: 15,000                  │                   │ RPM: Elastic (4,200 TPS)     │
└──────────────────────────────┘                   └──────────────────────────────┘
           │                                                      │
           └──────────────────────────┬──────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 6: Response Processing                                                  │
│                                                                              │
│ # Convert physical model back to logical for response                        │
│ logical_model = load_balancer.get_logical_name(actual_model)                 │
│ # 'ark-qwen' → 'qwen'                                                       │
│                                                                              │
│ # Token tracking (internal analytics)                                        │
│ await token_tracker.track_usage(                                             │
│     model_alias='qwen',              # Logical (user sees this)              │
│     physical_model='ark-qwen',       # Physical (cost calculation)           │
│     route='route_b',                 # Load balancing metrics                │
│     provider='volcengine'            # Actual provider                       │
│ )                                                                            │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 7: HTTP Response                                                        │
│                                                                              │
│ {                                                                            │
│   "success": true,                                                           │
│   "suggestions": ["汽车", "汽油", "汽水"],                                   │
│   "model": "qwen"  // ← Logical name, user never sees 'ark-qwen'!           │
│ }                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Node Palette - Detailed Flow (4 Parallel LLMs)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: HTTP Request                                                         │
│                                                                              │
│ POST /thinking_mode/node_palette/start                                       │
│ {                                                                            │
│   "diagram_type": "circle_map",                                              │
│   "diagram_data": { "center": { "text": "汽车" } }                          │
│ }                                                                            │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Router (routers/node_palette.py)                                     │
│                                                                              │
│ generator = get_circle_map_palette_generator()                               │
│ async for chunk in generator.generate_batch(                                 │
│     session_id=session_id,                                                   │
│     center_topic="汽车",                                                     │
│     ...                                                                      │
│ ):                                                                           │
│     yield f"data: {json.dumps(chunk)}\n\n"                                   │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Palette Generator (agents/node_palette/base_palette_generator.py)    │
│                                                                              │
│ class BasePaletteGenerator:                                                  │
│     def __init__(self):                                                      │
│         # Logical model names (same as frontend buttons)                     │
│         self.llm_models = ['qwen', 'deepseek', 'kimi', 'doubao']             │
│                                                                              │
│     async def generate_batch(...):                                           │
│         async for chunk in self.llm_service.stream_progressive(              │
│             prompt=prompt,                                                   │
│             models=self.llm_models,  # Logical names                         │
│             ...                                                              │
│         ):                                                                   │
│             yield chunk                                                      │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: LLM Service - stream_progressive (services/llm_service.py)           │
│                                                                              │
│ async def stream_progressive(self, prompt, models, ...):                     │
│     # ──────────────────────────────────────────────────────────────────    │
│     # 🎯 LOAD BALANCER INTERCEPTS HERE - ONCE PER REQUEST                    │
│     # ──────────────────────────────────────────────────────────────────    │
│     if self.load_balancer and self.load_balancer.enabled:                    │
│         route = self.load_balancer.select_route()  # 30% A, 70% B            │
│                                                                              │
│         # Map ALL models based on selected route                             │
│         physical_models = [                                                  │
│             self.load_balancer.map_model(m, route)                           │
│             for m in models                                                  │
│         ]                                                                    │
│                                                                              │
│     # Fire ALL 4 LLMs concurrently!                                          │
│     tasks = [asyncio.create_task(stream_single(model))                       │
│              for model in physical_models]                                   │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
           ┌──────────────────────────┴──────────────────────────┐
           │                                                      │
           ▼ (Route A - 30%)                                      ▼ (Route B - 70%)
┌──────────────────────────────────────┐       ┌──────────────────────────────────────┐
│ STEP 5A: Mixed Providers (Route A)   │       │ STEP 5B: Full Volcengine (Route B)   │
│                                      │       │                                      │
│ 4 Concurrent LLM Calls:              │       │ 4 Concurrent LLM Calls:              │
│                                      │       │                                      │
│ ┌────────────────────────────────┐   │       │ ┌────────────────────────────────┐   │
│ │ qwen (Dashscope)               │   │       │ │ ark-qwen (Volcengine)          │   │
│ │ model: qwen-plus-latest        │   │       │ │ endpoint: ep-20251222212931    │   │
│ │ RPM: 15,000                    │   │       │ │ RPM: Elastic                   │   │
│ └────────────────────────────────┘   │       │ └────────────────────────────────┘   │
│                                      │       │                                      │
│ ┌────────────────────────────────┐   │       │ ┌────────────────────────────────┐   │
│ │ deepseek (Dashscope)           │   │       │ │ ark-deepseek (Volcengine)      │   │
│ │ model: deepseek-v3.1           │   │       │ │ endpoint: ep-20251222212434    │   │
│ │ RPM: 15,000                    │   │       │ │ RPM: 15,000                    │   │
│ └────────────────────────────────┘   │       │ └────────────────────────────────┘   │
│                                      │       │                                      │
│ ┌────────────────────────────────┐   │       │ ┌────────────────────────────────┐   │
│ │ ark-kimi (Volcengine)          │◀──┼───────┼─│ ark-kimi (Volcengine)          │   │
│ │ endpoint: ep-20251222212350    │   │       │ │ endpoint: ep-20251222212350    │   │
│ │ RPM: 5,000 (NOT Dashscope 60!) │   │       │ │ RPM: 5,000                     │   │
│ └────────────────────────────────┘   │       │ └────────────────────────────────┘   │
│                                      │       │                                      │
│ ┌────────────────────────────────┐   │       │ ┌────────────────────────────────┐   │
│ │ doubao (Volcengine)            │◀──┼───────┼─│ doubao (Volcengine)            │   │
│ │ endpoint: ep-20251222212319    │   │       │ │ endpoint: ep-20251222212319    │   │
│ │ RPM: 30,000                    │   │       │ │ RPM: 30,000                    │   │
│ └────────────────────────────────┘   │       │ └────────────────────────────────┘   │
└──────────────────────────────────────┘       └──────────────────────────────────────┘
           │                                                      │
           └──────────────────────────┬──────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 6: Concurrent Streaming & Token Processing                              │
│                                                                              │
│ # All 4 LLMs stream concurrently into a shared queue                         │
│ queue = asyncio.Queue()                                                      │
│                                                                              │
│ # Tokens arrive from ANY LLM in real-time                                    │
│ while not all_complete:                                                      │
│     chunk = await queue.get()                                                │
│     if chunk['event'] == 'token':                                            │
│         # Parse token, extract node text                                     │
│         node_text = parse_node(chunk['token'])                               │
│         if is_unique(node_text):                                             │
│             yield {                                                          │
│                 'event': 'node_generated',                                   │
│                 'node': {                                                    │
│                     'text': node_text,                                       │
│                     'source_llm': get_logical_name(chunk['llm'])             │
│                     # 'ark-deepseek' → 'deepseek' (user-friendly)            │
│                 }                                                            │
│             }                                                                │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 7: SSE Response Stream                                                  │
│                                                                              │
│ data: {"event":"batch_start","batch_number":1,"llm_count":4}                │
│ data: {"event":"node_generated","node":{"text":"发动机","source_llm":"qwen"}}│
│ data: {"event":"node_generated","node":{"text":"轮胎","source_llm":"deepseek"}}│
│ data: {"event":"node_generated","node":{"text":"安全气囊","source_llm":"kimi"}}│
│ data: {"event":"node_generated","node":{"text":"变速箱","source_llm":"doubao"}}│
│ ...                                                                          │
│ data: {"event":"batch_complete","total_unique":45}                          │
│                                                                              │
│ Note: Users see logical names (qwen, deepseek, kimi, doubao)                │
│       Never see physical names (ark-qwen, ark-deepseek, etc.)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Key Points Summary

| Step | Autocomplete | Node Palette |
|------|--------------|--------------|
| **Entry** | POST /api/tab_suggestions | POST /thinking_mode/node_palette/start |
| **Models** | 1 model (qwen-plus) | 4 models parallel |
| **Load Balancer** | 1 route selection | 1 route selection (applies to all 4) |
| **Route A** | Dashscope qwen-plus | Dashscope (2) + Volcengine (2) |
| **Route B** | Volcengine ark-qwen | Volcengine (4) |
| **Response** | JSON with suggestions | SSE stream with nodes |
| **User sees** | Logical model name | Logical source_llm names |

---

---

## Critical Issues Found During Review

### Issue 1: Missing Doubao Pricing in Token Tracker

**Location**: `services/token_tracker.py`

**Problem**: Doubao model is used but has no pricing entry. Token costs for Doubao requests are not tracked!

**Evidence**:
```python
# Current MODEL_PRICING - missing doubao!
MODEL_PRICING = {
    'qwen': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope'},
    'qwen-turbo': {...},
    'qwen-plus': {...},
    'deepseek': {...},
    'kimi': {...},
    'hunyuan': {...},
    # NO DOUBAO!
}
```

**Impact**: Token usage from Doubao is being tracked but cost calculation falls back to default pricing.

**Fix Required**: Add doubao pricing before implementing load balancing.

---

### Issue 2: Node Palette Hardcoded Model List

**Location**: `agents/node_palette/base_palette_generator.py`

**Problem**: The 4 LLM models are hardcoded, not configurable.

**Evidence**:
```python
self.llm_models = ['qwen', 'deepseek', 'kimi', 'doubao']
```

**Impact**: Cannot dynamically switch to Route B models without code changes.

**Fix Required**: Model list should come from load balancer or configuration.

---

### Issue 3: Tab Agent Hardcoded Model

**Location**: `agents/tab_mode/tab_agent.py`

**Problem**: Default model is hardcoded to `qwen-plus`.

**Evidence**:
```python
def __init__(self, model='qwen-plus'):
    super().__init__(model=model)
```

**Impact**: Tab mode always uses Dashscope qwen-plus regardless of load balancing.

**Fix Required**: Should use load-balanced model selection.

---

### Issue 4: Multi-Worker Rate Limiting Bug (Pre-existing)

**Location**: `services/rate_limiter.py`, `services/llm_service.py`

**Problem**: Rate limiter is per-worker, not global. With 4 workers, actual rate is 4x the limit!

**Evidence**:
```python
# Each worker has isolated memory
# Worker 1: QPM counter = 0 → allows 200 requests
# Worker 2: QPM counter = 0 → allows 200 requests
# ...
# Total hitting API: 800 requests (4 × 200)
```

**Impact**: Rate limiting is ineffective in production with multiple workers.

**Fix Required**: Divide QPM limit by worker count at startup.

---

## Implementation Priority

### Phase 1: Core Infrastructure
1. Create `services/load_balancer.py`
2. Add Volcengine clients for `ark-qwen`, `ark-deepseek`, `ark-kimi`
3. Integrate load balancer into `llm_service.py`
4. Add route parameter to token tracking

### Phase 2: Model Configuration
1. Add `ARK_QWEN_MODEL`, `ARK_DEEPSEEK_MODEL`, `ARK_KIMI_MODEL` to settings
2. Update `env.example` with new variables
3. Add Volcengine rate limiter

### Phase 3: Token Tracking
1. Add Volcengine model pricing to `token_tracker.py`
2. Add `route` column to `token_usage` table
3. Update analytics to show per-route breakdown

### Phase 4: Testing
1. Test diagram generation with both routes
2. Test Node Palette with both routes (4 parallel LLMs)
3. Test Tab Mode autocomplete with both routes
4. Verify token tracking accuracy

---

## Files to Modify (Updated)

| File | Action | Description |
|------|--------|-------------|
| `services/load_balancer.py` | **Create** | Core load balancing logic |
| `clients/llm.py` | **Modify** | Add VolcengineClient class |
| `services/client_manager.py` | **Modify** | Register new Volcengine clients |
| `services/llm_service.py` | **Modify** | Integrate load balancer |
| `services/rate_limiter.py` | **Modify** | Add Volcengine rate limiter |
| `services/token_tracker.py` | **Modify** | Add Volcengine pricing + route tracking |
| `config/settings.py` | **Modify** | Add load balancing and ARK model configs |
| `env.example` | **Modify** | Document new environment variables |

---

## Step-by-Step Build Guide

**This section is the SINGLE SOURCE OF TRUTH for implementing load balancing.**

### Pre-Implementation Checklist

Before starting, verify these files exist and note current line numbers:

| File | Purpose | Status |
|------|---------|--------|
| `services/llm_service.py` | LLM service layer - main integration point | Exists |
| `services/client_manager.py` | Client registration | Exists |
| `services/rate_limiter.py` | Rate limiting | Exists |
| `services/token_tracker.py` | Token usage tracking | Exists |
| `clients/llm.py` | LLM client implementations | Exists |
| `config/settings.py` | Configuration | Exists |
| `env.example` | Environment variables | Exists |
| `services/load_balancer.py` | Load balancer | **CREATE** |

---

### STEP 1: Create Load Balancer Module

**File**: `services/load_balancer.py` (NEW FILE)

```python
"""
LLM Load Balancer
=================

Distributes LLM requests between multiple provider routes to maximize throughput
and avoid rate limiting bottlenecks.

Key Design:
- Route A (30%): Dashscope (qwen, deepseek) + Volcengine (kimi, doubao)
- Route B (70%): Full Volcengine (all models)
- Users see LOGICAL names (deepseek, qwen, kimi, doubao)
- Backend maps to PHYSICAL models transparently

@author MindSpring Team
Copyright 2024-2025 北京思源智教科技有限公司
"""

import logging
import random
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMLoadBalancer:
    """
    Distributes requests between Route A (Mixed) and Route B (Full Volcengine).
    
    KEY PRINCIPLE: Users see logical model names (deepseek, qwen, kimi, doubao).
    The load balancer maps these to physical models transparently.
    """
    
    ROUTE_A = 'route_a'  # Mixed: Dashscope + Volcengine Doubao/Kimi
    ROUTE_B = 'route_b'  # Full Volcengine
    
    # Logical model names (what frontend sends)
    LOGICAL_MODELS = ['deepseek', 'qwen', 'kimi', 'doubao']
    
    # Internal aliases (used within backend, never exposed to frontend)
    INTERNAL_ALIASES = ['qwen-turbo', 'qwen-plus', 'qwen-plus-latest']
    
    # Route A mapping: logical → physical (Dashscope + Volcengine for Kimi/Doubao)
    # Kimi and Doubao ALWAYS use Volcengine to avoid Dashscope's 60 RPM Kimi limit
    ROUTE_A_MODEL_MAP = {
        # Logical models (frontend buttons)
        'qwen': 'qwen',             # → Dashscope qwen-plus-latest (15,000 RPM)
        'deepseek': 'deepseek',     # → Dashscope deepseek-v3.1 (15,000 RPM)
        'kimi': 'ark-kimi',         # → Volcengine Kimi (5,000 RPM) - NOT Dashscope!
        'doubao': 'doubao',         # → Volcengine doubao (30,000 RPM)
        # Internal aliases
        'qwen-turbo': 'qwen-turbo', # → Dashscope qwen-turbo
        'qwen-plus': 'qwen-plus',   # → Dashscope qwen-plus
        'qwen-plus-latest': 'qwen-plus',  # → Dashscope qwen-plus-latest
        # Unaffected
        'hunyuan': 'hunyuan',       # → Tencent hunyuan
        'omni': 'omni',             # → Voice agent
    }
    
    # Route B mapping: logical → physical (Full Volcengine)
    # All 4 models on Volcengine
    ROUTE_B_MODEL_MAP = {
        # Logical models (frontend buttons)
        'qwen': 'ark-qwen',         # → Volcengine Qwen3-14B (Elastic)
        'deepseek': 'ark-deepseek', # → Volcengine DeepSeek-V3 (15,000 RPM)
        'kimi': 'ark-kimi',         # → Volcengine Kimi (5,000 RPM)
        'doubao': 'doubao',         # → Volcengine doubao (30,000 RPM)
        # Internal aliases also mapped
        'qwen-turbo': 'ark-qwen',   # → Volcengine Qwen3-14B
        'qwen-plus': 'ark-qwen',    # → Volcengine Qwen3-14B
        'qwen-plus-latest': 'ark-qwen',  # → Volcengine Qwen3-14B
        # Unaffected
        'hunyuan': 'hunyuan',       # → Tencent hunyuan (not on Volcengine)
        'omni': 'omni',             # → Voice agent
    }
    
    # Physical to logical name mapping (for API responses)
    PHYSICAL_TO_LOGICAL = {
        'ark-deepseek': 'deepseek',
        'ark-qwen': 'qwen',
        'ark-kimi': 'kimi',
        'qwen-plus': 'qwen',
        'qwen-plus-latest': 'qwen',
        'qwen-turbo': 'qwen',
        'deepseek': 'deepseek',
        'kimi': 'kimi',
        'doubao': 'doubao',
        'hunyuan': 'hunyuan',
        'omni': 'omni',
    }
    
    def __init__(self, strategy: str = 'weighted', weights: Dict[str, int] = None, enabled: bool = True):
        """
        Initialize load balancer.
        
        Args:
            strategy: 'weighted', 'random', or 'round_robin' (not recommended for multi-worker)
            weights: Route weights, e.g., {'route_a': 30, 'route_b': 70}
            enabled: Whether load balancing is enabled
        """
        self.strategy = strategy
        self.weights = weights or {'route_a': 30, 'route_b': 70}
        self.enabled = enabled
        self._counter = 0  # For round_robin (not recommended)
        
        logger.info(
            f"[LoadBalancer] Initialized: strategy={strategy}, "
            f"weights={self.weights}, enabled={enabled}"
        )
    
    def select_route(self) -> str:
        """
        Select route based on strategy.
        
        Returns:
            'route_a' or 'route_b'
            
        Note:
            'weighted' strategy is RECOMMENDED for multi-worker environments.
            Each request independently selects route with probability.
            No shared state needed across workers!
        """
        if not self.enabled:
            return self.ROUTE_A
        
        if self.strategy == 'weighted':
            # Stateless! Each request independently rolls dice
            # Perfect for multi-worker - no coordination needed
            rand = random.randint(1, 100)
            route = self.ROUTE_A if rand <= self.weights.get('route_a', 30) else self.ROUTE_B
            logger.debug(f"[LoadBalancer] Weighted selection: rand={rand}, route={route}")
            return route
        
        elif self.strategy == 'random':
            return random.choice([self.ROUTE_A, self.ROUTE_B])
        
        elif self.strategy == 'round_robin':
            # NOT RECOMMENDED for multi-worker (counter is per-worker)
            self._counter += 1
            return self.ROUTE_A if self._counter % 2 == 0 else self.ROUTE_B
        
        return self.ROUTE_A
    
    def map_model(self, logical_model: str, route: str) -> str:
        """
        Map logical model name to physical model based on route.
        
        Args:
            logical_model: Frontend model name (e.g., 'deepseek', 'qwen')
            route: Selected route ('route_a' or 'route_b')
            
        Returns:
            Physical model alias for the selected route
            
        Example:
            map_model('deepseek', 'route_a') → 'deepseek' (Dashscope)
            map_model('deepseek', 'route_b') → 'ark-deepseek' (Volcengine)
        """
        if route == self.ROUTE_A:
            physical = self.ROUTE_A_MODEL_MAP.get(logical_model, logical_model)
        else:
            physical = self.ROUTE_B_MODEL_MAP.get(logical_model, logical_model)
        
        logger.debug(f"[LoadBalancer] map_model: {logical_model} → {physical} (route={route})")
        return physical
    
    def get_logical_name(self, physical_model: str) -> str:
        """
        Convert physical model back to logical name for API response.
        
        Users should NEVER see 'ark-deepseek' - they see 'deepseek'.
        
        Args:
            physical_model: Internal model name (e.g., 'ark-deepseek')
            
        Returns:
            Logical model name (e.g., 'deepseek')
        """
        return self.PHYSICAL_TO_LOGICAL.get(physical_model, physical_model)
    
    def get_provider(self, physical_model: str) -> str:
        """
        Get provider name for a physical model.
        
        Args:
            physical_model: Internal model name
            
        Returns:
            Provider name ('dashscope', 'volcengine', 'tencent')
        """
        if physical_model.startswith('ark-') or physical_model == 'doubao':
            return 'volcengine'
        elif physical_model == 'hunyuan':
            return 'tencent'
        elif physical_model == 'omni':
            return 'dashscope'  # Qwen Omni is on Dashscope
        else:
            return 'dashscope'
    
    def get_stats(self) -> dict:
        """Get load balancer statistics."""
        return {
            'enabled': self.enabled,
            'strategy': self.strategy,
            'weights': self.weights,
            'counter': self._counter,
        }


# Singleton instance (initialized by LLMService)
_load_balancer: Optional[LLMLoadBalancer] = None


def get_load_balancer() -> Optional[LLMLoadBalancer]:
    """Get the global load balancer instance."""
    return _load_balancer


def initialize_load_balancer(
    strategy: str = 'weighted',
    weights: Dict[str, int] = None,
    enabled: bool = True
) -> LLMLoadBalancer:
    """
    Initialize the global load balancer.
    
    Args:
        strategy: Load balancing strategy
        weights: Route weights
        enabled: Whether to enable load balancing
        
    Returns:
        Initialized load balancer instance
    """
    global _load_balancer
    _load_balancer = LLMLoadBalancer(
        strategy=strategy,
        weights=weights,
        enabled=enabled
    )
    return _load_balancer
```

---

### STEP 2: Add VolcengineClient to clients/llm.py

**File**: `clients/llm.py`

**Location**: Add after `DoubaoClient` class (around line 1000)

```python
class VolcengineClient:
    """
    Volcengine ARK client using endpoint IDs for higher RPM.
    
    Uses OpenAI-compatible API with endpoint IDs instead of model names
    to achieve higher request limits.
    
    Supports: ark-qwen, ark-deepseek, ark-kimi
    """
    
    # Endpoint mapping for higher RPM
    ENDPOINT_MAP = {
        'ark-qwen': 'ARK_QWEN_ENDPOINT',
        'ark-deepseek': 'ARK_DEEPSEEK_ENDPOINT',
        'ark-kimi': 'ARK_KIMI_ENDPOINT',
    }
    
    # Default endpoint IDs (from env.example)
    DEFAULT_ENDPOINTS = {
        'ark-qwen': 'ep-20251222212931-hjqh2',
        'ark-deepseek': 'ep-20251222212434-cxpzb',
        'ark-kimi': 'ep-20251222212350-wxbks',
    }
    
    def __init__(self, model_alias: str):
        """
        Initialize Volcengine client.
        
        Args:
            model_alias: Model alias ('ark-qwen', 'ark-deepseek', 'ark-kimi')
        """
        self.api_key = config.ARK_API_KEY
        self.base_url = config.ARK_BASE_URL
        self.model_alias = model_alias
        self.timeout = 60
        
        # Map alias to endpoint ID (higher RPM!)
        self.endpoint_id = self._get_endpoint_id(model_alias)
        
        # DIVERSITY FIX: Moderate temperature
        self.default_temperature = 0.8
        
        # Initialize AsyncOpenAI client
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )
        
        logger.debug(
            f"VolcengineClient initialized: {model_alias} → {self.endpoint_id}"
        )
    
    def _get_endpoint_id(self, alias: str) -> str:
        """
        Map model alias to Volcengine endpoint ID.
        
        Endpoint IDs provide higher RPM than direct model names!
        """
        env_var = self.ENDPOINT_MAP.get(alias)
        if env_var:
            endpoint = os.environ.get(env_var, self.DEFAULT_ENDPOINTS.get(alias, alias))
            return endpoint
        return alias
    
    async def async_chat_completion(
        self,
        messages: List[Dict],
        temperature: float = None,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Non-streaming chat completion using endpoint ID.
        
        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            
        Returns:
            Dict with 'content' and 'usage' keys
        """
        try:
            if temperature is None:
                temperature = self.default_temperature
            
            logger.debug(f"Volcengine {self.model_alias} request: endpoint={self.endpoint_id}")
            
            completion = await self.client.chat.completions.create(
                model=self.endpoint_id,  # Use endpoint ID for higher RPM!
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            content = completion.choices[0].message.content
            
            # Extract usage
            usage = {}
            if hasattr(completion, 'usage') and completion.usage:
                usage = {
                    'prompt_tokens': getattr(completion.usage, 'prompt_tokens', 0),
                    'completion_tokens': getattr(completion.usage, 'completion_tokens', 0),
                    'total_tokens': getattr(completion.usage, 'total_tokens', 0),
                }
            
            return {
                'content': content,
                'usage': usage
            }
            
        except RateLimitError as e:
            logger.error(f"Volcengine {self.model_alias} rate limit: {e}")
            raise LLMRateLimitError(f"Volcengine rate limit: {e}")
            
        except APIStatusError as e:
            logger.error(f"Volcengine {self.model_alias} API error: {e}")
            # Use doubao error parser for Volcengine errors
            parse_and_raise_doubao_error(e.status_code, str(e), {})
            
        except Exception as e:
            logger.error(f"Volcengine {self.model_alias} error: {e}")
            raise
    
    async def async_stream_chat_completion(
        self,
        messages: List[Dict],
        temperature: float = None,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat completion using endpoint ID.
        
        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            
        Yields:
            Content chunks as strings
        """
        try:
            if temperature is None:
                temperature = self.default_temperature
            
            logger.debug(f"Volcengine {self.model_alias} stream: endpoint={self.endpoint_id}")
            
            stream = await self.client.chat.completions.create(
                model=self.endpoint_id,  # Use endpoint ID for higher RPM!
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            
            async for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    yield content
                    
        except RateLimitError as e:
            logger.error(f"Volcengine {self.model_alias} stream rate limit: {e}")
            raise LLMRateLimitError(f"Volcengine rate limit: {e}")
            
        except Exception as e:
            logger.error(f"Volcengine {self.model_alias} stream error: {e}")
            raise
```

**Also add to imports at top of clients/llm.py:**
```python
# Add os import if not present
import os
```

---

### STEP 3: Update Client Manager

**File**: `services/client_manager.py`

**Location**: In `initialize()` method, after existing client registrations (around line 78)

**Add import at top:**
```python
from clients.llm import (
    QwenClient,
    DeepSeekClient,
    KimiClient,
    HunyuanClient,
    DoubaoClient,
    VolcengineClient  # ADD THIS
)
```

**Add in initialize() method:**
```python
# Route B Volcengine clients (endpoint-based for higher RPM)
self._clients['ark-qwen'] = VolcengineClient('ark-qwen')
self._clients['ark-deepseek'] = VolcengineClient('ark-deepseek')
self._clients['ark-kimi'] = VolcengineClient('ark-kimi')
logger.debug("[ClientManager] Volcengine clients initialized (ark-qwen, ark-deepseek, ark-kimi)")
```

---

### STEP 4: Update Config Settings

**File**: `config/settings.py`

**Location**: Add after existing ARK properties (around line 165)

```python
# ============================================================================
# LOAD BALANCING CONFIGURATION
# ============================================================================

@property
def LOAD_BALANCING_ENABLED(self):
    """Enable/disable load balancing"""
    val = self._get_cached_value('LOAD_BALANCING_ENABLED', 'false')
    return val.lower() == 'true'

@property
def LOAD_BALANCING_STRATEGY(self):
    """Load balancing strategy: 'weighted', 'random', 'round_robin'"""
    return self._get_cached_value('LOAD_BALANCING_STRATEGY', 'weighted')

@property
def LOAD_BALANCING_WEIGHTS(self) -> dict:
    """Parse load balancing weights from env"""
    weights_str = self._get_cached_value('LOAD_BALANCING_WEIGHTS', 'route_a:30,route_b:70')
    weights = {}
    try:
        for pair in weights_str.split(','):
            route, weight = pair.strip().split(':')
            weights[route.strip()] = int(weight.strip())
    except Exception as e:
        logger.warning(f"Invalid LOAD_BALANCING_WEIGHTS, using defaults: {e}")
        weights = {'route_a': 30, 'route_b': 70}
    return weights

# ============================================================================
# VOLCENGINE ARK ENDPOINT CONFIGURATION
# ============================================================================

@property
def ARK_QWEN_ENDPOINT(self):
    """Volcengine ARK Qwen3-14B endpoint ID"""
    return self._get_cached_value('ARK_QWEN_ENDPOINT', 'ep-20251222212931-hjqh2')

@property
def ARK_DEEPSEEK_ENDPOINT(self):
    """Volcengine ARK DeepSeek-V3 endpoint ID"""
    return self._get_cached_value('ARK_DEEPSEEK_ENDPOINT', 'ep-20251222212434-cxpzb')

@property
def ARK_KIMI_ENDPOINT(self):
    """Volcengine ARK Kimi endpoint ID"""
    return self._get_cached_value('ARK_KIMI_ENDPOINT', 'ep-20251222212350-wxbks')

@property
def ARK_DOUBAO_ENDPOINT(self):
    """Volcengine ARK Doubao endpoint ID"""
    return self._get_cached_value('ARK_DOUBAO_ENDPOINT', 'ep-20251222212319-qqzb7')

# ============================================================================
# VOLCENGINE RATE LIMITING
# ============================================================================

@property
def ARK_QPM_LIMIT(self):
    """Volcengine ARK Queries Per Minute limit"""
    try:
        return int(self._get_cached_value('ARK_QPM_LIMIT', '5000'))
    except (ValueError, TypeError):
        return 5000

@property
def ARK_CONCURRENT_LIMIT(self):
    """Volcengine ARK concurrent request limit"""
    try:
        return int(self._get_cached_value('ARK_CONCURRENT_LIMIT', '500'))
    except (ValueError, TypeError):
        return 500

@property
def ARK_RATE_LIMITING_ENABLED(self):
    """Enable/disable Volcengine rate limiting"""
    val = self._get_cached_value('ARK_RATE_LIMITING_ENABLED', 'false')
    return val.lower() == 'true'
```

---

### STEP 5: Update LLM Service

**File**: `services/llm_service.py`

**Location 1**: Add import at top (around line 28)
```python
from services.load_balancer import (
    LLMLoadBalancer,
    initialize_load_balancer,
    get_load_balancer
)
```

**Location 2**: Add load_balancer to __init__ (around line 52)
```python
def __init__(self):
    self.client_manager = client_manager
    self.prompt_manager = prompt_manager
    self.performance_tracker = performance_tracker
    self.rate_limiter = None
    self.load_balancer = None  # ADD THIS
    logger.info("[LLMService] Initialized")
```

**Location 3**: Initialize load balancer in initialize() method (after rate limiter, around line 80)
```python
# Initialize load balancer
if config.LOAD_BALANCING_ENABLED:
    self.load_balancer = initialize_load_balancer(
        strategy=config.LOAD_BALANCING_STRATEGY,
        weights=config.LOAD_BALANCING_WEIGHTS,
        enabled=True
    )
    logger.info(
        f"[LLMService] Load balancer enabled: "
        f"strategy={config.LOAD_BALANCING_STRATEGY}, "
        f"weights={config.LOAD_BALANCING_WEIGHTS}"
    )
else:
    logger.info("[LLMService] Load balancing disabled")
```

**Location 4**: Modify chat() method to use load balancer (around line 137)

Replace:
```python
# Get client
client = self.client_manager.get_client(model)
```

With:
```python
# Apply load balancing
actual_model = model
selected_route = None

if self.load_balancer and self.load_balancer.enabled:
    selected_route = self.load_balancer.select_route()
    actual_model = self.load_balancer.map_model(model, selected_route)
    logger.debug(
        f"[LLMService] Load balanced: {model} → {actual_model} (route={selected_route})"
    )

# Get client for actual model
client = self.client_manager.get_client(actual_model)
```

**Location 5**: Similar changes needed in chat_stream() method

**Location 6**: Modify stream_progressive() to select route once for all models (around line 1070)

Add after models default assignment:
```python
# Select route ONCE for this entire parallel request
selected_route = None
physical_models = models

if self.load_balancer and self.load_balancer.enabled:
    selected_route = self.load_balancer.select_route()
    physical_models = [
        self.load_balancer.map_model(m, selected_route)
        for m in models
    ]
    logger.info(
        f"[LLMService] stream_progressive: route={selected_route}, "
        f"models={models} → {physical_models}"
    )
```

Then update the loop to use `physical_models` instead of `models`:
```python
tasks = [asyncio.create_task(stream_single(model)) for model in physical_models]
```

---

### STEP 6: Update Token Tracker

**File**: `services/token_tracker.py`

**Location**: Update MODEL_PRICING dict (around line 56)

```python
MODEL_PRICING = {
    # Dashscope models (Route A physical names)
    'qwen': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope', 'logical': 'qwen'},
    'qwen-turbo': {'input': 0.3, 'output': 0.6, 'provider': 'dashscope', 'logical': 'qwen'},
    'qwen-plus': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope', 'logical': 'qwen'},
    'qwen-plus-latest': {'input': 0.4, 'output': 1.2, 'provider': 'dashscope', 'logical': 'qwen'},
    'deepseek': {'input': 0.4, 'output': 2.0, 'provider': 'dashscope', 'logical': 'deepseek'},
    'kimi': {'input': 2.0, 'output': 6.0, 'provider': 'dashscope', 'logical': 'kimi'},
    'hunyuan': {'input': 0.45, 'output': 0.5, 'provider': 'tencent', 'logical': 'hunyuan'},
    
    # Volcengine models (physical names) - ADD THESE
    'doubao': {'input': 0.3, 'output': 0.9, 'provider': 'volcengine', 'logical': 'doubao'},
    'ark-qwen': {'input': 0.35, 'output': 1.0, 'provider': 'volcengine', 'logical': 'qwen'},
    'ark-deepseek': {'input': 0.4, 'output': 1.8, 'provider': 'volcengine', 'logical': 'deepseek'},
    'ark-kimi': {'input': 1.8, 'output': 5.5, 'provider': 'volcengine', 'logical': 'kimi'},
}
```

---

### STEP 7: Verify env.example

**File**: `env.example`

Confirm these sections exist (already added in previous updates):

```bash
# ============================================================================
# VOLCENGINE ARK API CONFIGURATION
# ============================================================================
ARK_API_KEY=your-ark-api-key-here
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

# Volcengine Endpoint IDs (Higher RPM than direct model names!)
ARK_QWEN_ENDPOINT=ep-20251222212931-hjqh2
ARK_DEEPSEEK_ENDPOINT=ep-20251222212434-cxpzb
ARK_KIMI_ENDPOINT=ep-20251222212350-wxbks
ARK_DOUBAO_ENDPOINT=ep-20251222212319-qqzb7

# ============================================================================
# LOAD BALANCING CONFIGURATION
# ============================================================================
LOAD_BALANCING_ENABLED=true
LOAD_BALANCING_STRATEGY=weighted
LOAD_BALANCING_WEIGHTS=route_a:30,route_b:70

# ============================================================================
# VOLCENGINE RATE LIMITING
# ============================================================================
ARK_QPM_LIMIT=5000
ARK_CONCURRENT_LIMIT=500
ARK_RATE_LIMITING_ENABLED=false
```

---

### STEP 8: Testing Checklist

After implementation, test each scenario:

| Test | Command/Action | Expected Result |
|------|----------------|-----------------|
| Load balancer disabled | Set `LOAD_BALANCING_ENABLED=false` | All requests use Route A (Dashscope) |
| Route A only | Set `LOAD_BALANCING_WEIGHTS=route_a:100,route_b:0` | All requests use Route A |
| Route B only | Set `LOAD_BALANCING_WEIGHTS=route_a:0,route_b:100` | All requests use Route B (Volcengine) |
| Balanced | Set `LOAD_BALANCING_WEIGHTS=route_a:30,route_b:70` | ~30% Route A, ~70% Route B |
| Node Palette | Generate nodes for any diagram | 4 LLMs fire in parallel, all use same route |
| Tab Autocomplete | Type in tab mode | Single LLM call, route varies |
| Token tracking | Check logs/database | Physical model and route logged |

**Verification Logs to Look For:**
```
[LLMService] Load balancer enabled: strategy=weighted, weights={'route_a': 30, 'route_b': 70}
[LoadBalancer] Weighted selection: rand=42, route=route_b
[LLMService] Load balanced: qwen → ark-qwen (route=route_b)
[LLMService] stream_progressive: route=route_a, models=['qwen', 'deepseek', 'kimi', 'doubao'] → ['qwen', 'deepseek', 'ark-kimi', 'doubao']
```

---

### Implementation Order Summary

| Step | File | Action | Time Est. |
|------|------|--------|-----------|
| 1 | `services/load_balancer.py` | Create new file | 15 min |
| 2 | `clients/llm.py` | Add VolcengineClient class | 10 min |
| 3 | `services/client_manager.py` | Register new clients | 5 min |
| 4 | `config/settings.py` | Add load balancing config | 10 min |
| 5 | `services/llm_service.py` | Integrate load balancer | 20 min |
| 6 | `services/token_tracker.py` | Add Volcengine pricing | 5 min |
| 7 | `env.example` | Verify/update variables | 5 min |
| 8 | Testing | Run all test scenarios | 30 min |
| **Total** | | | **~100 min** |

---

### Rollback Plan

If issues occur after deployment:

1. **Quick Disable**: Set `LOAD_BALANCING_ENABLED=false` in `.env`
2. **Restart**: Restart the server
3. **Verify**: All requests now use Route A (original behavior)

No code changes needed for rollback!

---

*Document Version: 3.0*
*Created: 2025-12-22*
*Updated: 2025-12-22*
*Author: MindSpring Team*

