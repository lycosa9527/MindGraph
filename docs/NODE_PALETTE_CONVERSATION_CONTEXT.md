# Node Palette: Conversation Context & Multi-Round Memory

**Maintaining LLM conversation history for better diversity and natural deduplication**

---

## 📋 Table of Contents

1. [The Problem](#the-problem)
2. [The Solution](#the-solution)
3. [Architecture Support](#architecture-support)
4. [Implementation Plan](#implementation-plan)
5. [Expected Benefits](#expected-benefits)
6. [Integration with Streaming](#integration-with-streaming)

---

## The Problem

### Current Behavior (Stateless)

**Each batch is a fresh conversation - LLM has amnesia!**

```python
# Batch 1
messages = [
    {"role": "system", "content": "You are a K12 assistant"},
    {"role": "user", "content": "Generate 15 nodes about 汽车"}
]
# qwen generates: 车轮, 引擎, 车门...

# Batch 2 (FORGETS Batch 1!)
messages = [
    {"role": "system", "content": "You are a K12 assistant"},
    {"role": "user", "content": "Generate 15 nodes about 汽车"}
]
# qwen generates: 车轮, 引擎... (DUPLICATES!)
```

### Issues

1. **High Duplicate Rate:** ~30% duplicates across batches
2. **Limited Diversity:** LLMs repeat similar themes
3. **Wasted Computation:** Generating duplicates that get filtered
4. **Poor User Experience:** Same ideas appearing multiple times

---

## The Solution

### Conversation Continuity

**Maintain conversation history per LLM - each LLM remembers what it said!**

```python
# Batch 1
messages = [
    {"role": "system", "content": "You are a K12 assistant"},
    {"role": "user", "content": "Generate 15 nodes about 汽车"}
]
# qwen response: "车轮\n引擎\n车门\n方向盘..."

# Batch 2 (REMEMBERS Batch 1!)
messages = [
    {"role": "system", "content": "You are a K12 assistant"},
    {"role": "user", "content": "Generate 15 nodes about 汽车"},
    {"role": "assistant", "content": "车轮\n引擎\n车门\n方向盘..."},  # Previous response
    {"role": "user", "content": "Generate 15 MORE DIFFERENT nodes about 汽车 (avoid repeating previous ones)"}
]
# qwen generates: 轮胎, 油箱, 挡风玻璃... (NEW IDEAS!)
```

### Key Benefits

- ✅ **LLM knows what it already generated**
- ✅ **Naturally avoids duplicates**
- ✅ **Generates more diverse content**
- ✅ **Can explicitly ask for "different" ideas**
- ✅ **Progressive exploration of topic**

---

## Architecture Support

### LLM Clients ✅

**All clients already support conversation format!**

```python
# clients/llm.py - All clients accept:
async def chat_completion(self, messages: List[Dict], ...):
    # messages = [
    #     {"role": "system", "content": "..."},
    #     {"role": "user", "content": "..."},
    #     {"role": "assistant", "content": "..."},  # Previous response
    #     {"role": "user", "content": "..."}         # Follow-up
    # ]
```

**Verified in:**
- QwenClient (line 41)
- DeepSeekClient (line 255)
- HunyuanClient (line 349)
- KimiClient (line 494)

### LLM Service ❌

**Currently stateless - builds fresh messages each time:**

```python
# services/llm_service.py:251-254
messages = []
if system_message:
    messages.append({"role": "system", "content": system_message})
messages.append({"role": "user", "content": prompt})
```

**Needs update to accept pre-built messages.**

---

## Implementation Plan

### Phase 1: Update LLM Service

#### Step 1.1: Add `messages` Parameter to `chat_stream()`

**File:** `services/llm_service.py`

**Modify signature:**

```python
async def chat_stream(
    self,
    prompt: str = None,                      # Make optional
    model: str = 'qwen',
    temperature: Optional[float] = None,
    max_tokens: int = 2000,
    timeout: Optional[float] = None,
    system_message: Optional[str] = None,
    messages: Optional[List[Dict]] = None,   # NEW: Accept pre-built messages
    **kwargs
):
    """
    Stream chat completion from a specific LLM.
    
    Args:
        prompt: User prompt (ignored if messages provided)
        messages: Pre-built conversation messages (overrides prompt/system_message)
        model: Model identifier
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        timeout: Request timeout
        system_message: Optional system message (ignored if messages provided)
        **kwargs: Additional parameters
        
    Yields:
        Response chunks as they arrive
        
    Example (legacy mode):
        async for token in llm_service.chat_stream(
            prompt="Generate nodes",
            system_message="You are an assistant"
        ):
            print(token)
    
    Example (conversation mode):
        messages = [
            {"role": "system", "content": "You are an assistant"},
            {"role": "user", "content": "Generate nodes about cars"},
            {"role": "assistant", "content": "wheels\nengine\ndoors"},
            {"role": "user", "content": "Generate MORE DIFFERENT nodes"}
        ]
        async for token in llm_service.chat_stream(messages=messages):
            print(token)
    """
    start_time = time.time()
    
    try:
        logger.debug(f"[LLMService] chat_stream() - model={model}")
        
        # Get client
        client = self.client_manager.get_client(model)
        
        # Build messages
        if messages is None:
            # Legacy behavior: build from prompt
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})
        
        # Use provided messages directly (conversation mode)
        logger.debug(f"[LLMService] Using {len(messages)} messages for conversation")
        
        # Set timeout
        if timeout is None:
            timeout = self._get_default_timeout(model)
        
        # ... rest of existing implementation
```

#### Step 1.2: Update `chat()` Method Similarly

**Same pattern for non-streaming:**

```python
async def chat(
    self,
    prompt: str = None,
    model: str = 'qwen',
    temperature: Optional[float] = None,
    max_tokens: int = 2000,
    system_message: Optional[str] = None,
    timeout: Optional[float] = None,
    messages: Optional[List[Dict]] = None,   # NEW
    **kwargs
) -> str:
    # ... same message building logic
```

---

### Phase 2: Update Node Palette Generator

#### Step 2.1: Add Conversation Storage

**File:** `agents/thinking_modes/node_palette_generator_v2.py`

```python
class NodePaletteGeneratorV2:
    def __init__(self):
        # ... existing init ...
        self.llm_service = llm_service
        self.llm_models = ['qwen', 'deepseek', 'hunyuan', 'kimi']
        
        # Session storage (existing)
        self.generated_nodes = {}
        self.seen_texts = {}
        self.session_start_times = {}
        self.batch_counts = {}
        
        # NEW: Conversation history storage
        self.conversation_history = {}  # session_id -> {llm_name -> messages[]}
        
        logger.info("[NodePaletteV2] Initialized with conversation context support")
```

#### Step 2.2: Initialize Conversation on First Batch

```python
async def generate_batch(
    self,
    session_id: str,
    center_topic: str,
    educational_context: Optional[Dict[str, Any]] = None,
    nodes_per_llm: int = 15
) -> AsyncGenerator[Dict, None]:
    # Track session
    if session_id not in self.session_start_times:
        self.session_start_times[session_id] = time.time()
        self.batch_counts[session_id] = 0
        
        # NEW: Initialize conversation history
        self.conversation_history[session_id] = {
            llm: [] for llm in self.llm_models
        }
        
        logger.info("[NodePaletteV2] New session: %s | Initialized conversations for %d LLMs", 
                   session_id[:8], len(self.llm_models))
    
    batch_num = self.batch_counts[session_id] + 1
    self.batch_counts[session_id] = batch_num
    
    # ... rest of method
```

#### Step 2.3: Build Conversation-Aware Messages

```python
async def stream_from_llm(llm_name: str):
    """Stream tokens from one LLM with conversation context"""
    llm_start = time.time()
    unique_count = 0
    duplicate_count = 0
    accumulated_response = ""
    
    try:
        # Build messages with conversation history
        if batch_num == 1:
            # First batch: standard prompt
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
        else:
            # Subsequent batches: include conversation history
            messages = self.conversation_history[session_id][llm_name].copy()
            
            # Add follow-up request emphasizing DIFFERENT content
            follow_up = f"Generate {nodes_per_llm} MORE DIFFERENT nodes about {center_topic}. "
            follow_up += "Avoid repeating previous nodes. Explore new angles and perspectives."
            
            messages.append({
                "role": "user",
                "content": follow_up
            })
            
            logger.debug(
                "[NodePaletteV2] %s batch %d - using %d conversation messages",
                llm_name, batch_num, len(messages)
            )
        
        # Stream tokens from this LLM with conversation context
        async for token in self.llm_service.chat_stream(
            model=llm_name,
            messages=messages,  # Pass full conversation
            temperature=temperature,
            max_tokens=500
        ):
            current_line += token
            accumulated_response += token  # Track full response
            
            # ... process tokens into nodes ...
        
        # After LLM completes, save to conversation history
        if accumulated_response.strip():
            # Update conversation history with this exchange
            if batch_num == 1:
                # First batch: save initial Q&A
                self.conversation_history[session_id][llm_name] = [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": accumulated_response.strip()}
                ]
            else:
                # Subsequent batches: append to existing history
                self.conversation_history[session_id][llm_name].append(
                    {"role": "assistant", "content": accumulated_response.strip()}
                )
            
            logger.debug(
                "[NodePaletteV2] %s conversation saved | History length: %d messages",
                llm_name, len(self.conversation_history[session_id][llm_name])
            )
        
        # ... yield llm_complete event ...
```

#### Step 2.4: Cleanup Old Sessions

```python
def cleanup_session(self, session_id: str):
    """Clean up session data including conversation history"""
    if session_id in self.generated_nodes:
        del self.generated_nodes[session_id]
    if session_id in self.seen_texts:
        del self.seen_texts[session_id]
    if session_id in self.conversation_history:
        del self.conversation_history[session_id]
    if session_id in self.session_start_times:
        del self.session_start_times[session_id]
    if session_id in self.batch_counts:
        del self.batch_counts[session_id]
    
    logger.info("[NodePaletteV2] Session %s cleaned up (including conversation history)", session_id[:8])
```

---

### Phase 3: Update stream_progressive() (Optional)

**If using middleware for streaming:**

```python
# services/llm_service.py - stream_progressive()

async def stream_progressive(
    self,
    prompt: str = None,
    models: List[str] = None,
    messages_per_llm: Optional[Dict[str, List[Dict]]] = None,  # NEW: Per-LLM messages
    temperature: Optional[float] = None,
    max_tokens: int = 2000,
    timeout: Optional[float] = None,
    system_message: Optional[str] = None,
    **kwargs
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream from multiple LLMs concurrently, yield tokens as they arrive.
    
    Args:
        prompt: Prompt to send to all LLMs (ignored if messages_per_llm provided)
        models: List of model names
        messages_per_llm: Optional dict mapping llm_name -> messages list
                         Example: {
                             'qwen': [{"role": "user", "content": "..."}, ...],
                             'deepseek': [{"role": "user", "content": "..."}, ...]
                         }
        ...
        
    Yields:
        Dict for each token/event with conversation context
    """
    if models is None:
        models = ['qwen', 'deepseek', 'kimi', 'hunyuan']
    
    queue = asyncio.Queue()
    
    async def stream_single(model: str):
        """Stream from one LLM with optional conversation context."""
        start_time = time.time()
        
        try:
            # Use per-LLM messages if provided, otherwise build from prompt
            if messages_per_llm and model in messages_per_llm:
                llm_messages = messages_per_llm[model]
                logger.debug(f"[LLMService] {model} - using {len(llm_messages)} conversation messages")
            else:
                llm_messages = None  # Will use prompt/system_message
            
            async for token in self.chat_stream(
                model=model,
                messages=llm_messages,  # Pass conversation context
                prompt=prompt,           # Fallback if no messages
                system_message=system_message,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                **kwargs
            ):
                await queue.put({
                    'event': 'token',
                    'llm': model,
                    'token': token,
                    'timestamp': time.time()
                })
            
            # ... rest of implementation
```

---

## Expected Benefits

### Deduplication Improvement

| Metric | Current (Stateless) | With Conversation Context |
|--------|---------------------|---------------------------|
| **Duplicate Rate** | ~30% | ~5% |
| **Unique Nodes/Batch** | ~40-45 (out of 60) | ~57-58 (out of 60) |
| **Wasted Generation** | High | Minimal |

### Diversity Improvement

**Current (Stateless):**
- Batch 1: Similar themes
- Batch 2: Repeats Batch 1 themes
- Batch 3: Still similar patterns

**With Context (Progressive Exploration):**
- Batch 1: Core concepts
- Batch 2: Related but different angles
- Batch 3: Advanced/creative connections

### Example: Circle Map "汽车" (Car)

#### Without Conversation Context:

**Batch 1 (4 LLMs):**
- qwen: 车轮, 引擎, 车门, 方向盘
- deepseek: 轮胎, 发动机, 车窗, 座椅
- hunyuan: 引擎, 车门, 方向盘, 车轮
- kimi: 车轮, 车门, 座椅, 方向盘

**Batch 2 (Many duplicates!):**
- qwen: 车轮, 引擎, 座椅, 车灯
- deepseek: 轮胎, 车窗, 车门, 保险杠
- hunyuan: 车轮, 车门, 后视镜, 引擎
- kimi: 方向盘, 座椅, 车门, 车灯

#### With Conversation Context:

**Batch 1 (Core concepts):**
- qwen: 车轮, 引擎, 车门, 方向盘
- deepseek: 轮胎, 发动机, 车窗, 座椅
- hunyuan: 车灯, 保险杠, 后视镜, 刹车
- kimi: 油箱, 排气管, 仪表盘, 挡风玻璃

**Batch 2 (Progressive exploration - NEW angles!):**
- qwen: 油箱, 变速器, 刹车系统, 悬挂系统
- deepseek: 电瓶, 空调, 音响, 导航
- hunyuan: 雨刷, 安全带, 安全气囊, 儿童座椅
- kimi: 行李箱, 备胎, 工具箱, 三角警示牌

**Result:** 95% unique nodes instead of 70%!

---

## Integration with Streaming

### Compatible with Concurrent Token Streaming

**Conversation context is INDEPENDENT of streaming architecture:**

1. **Streaming decides:** HOW tokens arrive (concurrent, progressive)
2. **Context decides:** WHAT messages are sent (with/without history)

**Can combine both:**

```python
# Node Palette with BOTH features:
# 1. Concurrent token streaming (4 LLMs at once)
# 2. Conversation context (each LLM remembers)

async def generate_batch(...):
    # Build per-LLM messages with conversation history
    messages_per_llm = {}
    for llm in self.llm_models:
        if batch_num == 1:
            messages_per_llm[llm] = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
        else:
            messages_per_llm[llm] = self.conversation_history[session_id][llm].copy()
            messages_per_llm[llm].append({
                "role": "user",
                "content": f"Generate MORE DIFFERENT nodes about {topic}"
            })
    
    # Stream with BOTH concurrent execution AND conversation context
    async for chunk in self.llm_service.stream_progressive(
        models=self.llm_models,
        messages_per_llm=messages_per_llm,  # Conversation context
        temperature=temperature,
        max_tokens=500
    ):
        # Tokens arrive concurrently from 4 LLMs, each with memory!
        yield chunk
```

---

## Implementation Priority

### Recommendation: Phase 2 (After Streaming)

**Why:**
1. **Streaming is foundation** - Must work first
2. **Context is enhancement** - Adds on top of streaming
3. **Independent features** - Can be developed separately
4. **Easy to test** - Can measure impact with A/B testing

### Timeline

1. **Week 1:** Concurrent Token Streaming (foundation)
2. **Week 2:** Conversation Context (this feature)
3. **Week 3:** Batch Pipelining (speed optimization)

### Effort Estimate

| Task | Files | Lines of Code | Effort |
|------|-------|---------------|--------|
| Update llm_service.py | 1 | ~20 | Low |
| Update node_palette_generator_v2.py | 1 | ~60 | Medium |
| Testing & validation | - | - | Low |
| **Total** | **2** | **~80** | **Medium** |

### Impact

| Metric | Impact Level |
|--------|--------------|
| **Deduplication** | High (30% → 5%) |
| **Diversity** | High (progressive exploration) |
| **User Experience** | High (better content quality) |
| **Code Complexity** | Low (simple history tracking) |

---

## Testing Plan

### Unit Tests

```python
# Test conversation history tracking
async def test_conversation_context():
    generator = NodePaletteGeneratorV2()
    session_id = "test_session"
    
    # Batch 1
    async for event in generator.generate_batch(
        session_id=session_id,
        center_topic="汽车",
        nodes_per_llm=5
    ):
        pass
    
    # Verify history exists
    assert session_id in generator.conversation_history
    assert 'qwen' in generator.conversation_history[session_id]
    assert len(generator.conversation_history[session_id]['qwen']) == 3  # system, user, assistant
    
    # Batch 2
    async for event in generator.generate_batch(
        session_id=session_id,
        center_topic="汽车",
        nodes_per_llm=5
    ):
        pass
    
    # Verify history grew
    assert len(generator.conversation_history[session_id]['qwen']) == 5  # +user, +assistant
```

### Integration Tests

1. **Test duplicate reduction:** Compare batch 2 duplicates with/without context
2. **Test diversity:** Measure semantic distance between batches
3. **Test memory usage:** Ensure history doesn't grow unbounded

### A/B Testing

**Metrics to track:**
- Duplicate rate per batch
- Unique node count per batch
- User satisfaction (if applicable)
- LLM token usage (context adds tokens)

---

*Author: lycosa9527*  
*Team: MindSpring Team*  
*Date: October 13, 2025*  
*Purpose: Conversation Context Design for Node Palette*


