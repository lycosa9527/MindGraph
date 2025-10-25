# Accurate Token Tracking Using API-Provided Counts

## The Problem with Current Code

**Currently, we're IGNORING the token counts that APIs return!**

### What DashScope/Tencent Actually Returns

**DashScope API Response Format:**
```json
{
  "id": "chatcmpl-abc123",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Generated text here..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {                    // ← WE'RE IGNORING THIS!
    "prompt_tokens": 152,       // Actual input tokens
    "completion_tokens": 487,   // Actual output tokens  
    "total_tokens": 639         // Total
  },
  "model": "qwen-plus"
}
```

**Current Code (clients/llm.py line 84-85):**
```python
data = await response.json()
return data.get('choices', [{}])[0].get('message', {}).get('content', '')
# ❌ THROWS AWAY usage data!
```

---

## Solution: Extract & Use Actual Token Counts

### Step 1: Modify LLM Clients to Return Usage

**File:** `clients/llm.py`

#### Fix QwenClient

```python
async def chat_completion(self, messages: List[Dict], temperature: float = None,
                        max_tokens: int = 1000) -> Dict:  # ← Changed return type
    """
    Send chat completion request to Qwen (async version)
    
    Returns:
        Dict with 'content' and 'usage' keys
    """
    try:
        # ... existing setup code ...
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.post(self.api_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract both content AND usage
                    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    usage = data.get('usage', {})  # ← NEW: Get actual token counts
                    
                    return {
                        'content': content,
                        'usage': {
                            'prompt_tokens': usage.get('prompt_tokens', 0),
                            'completion_tokens': usage.get('completion_tokens', 0),
                            'total_tokens': usage.get('total_tokens', 0)
                        }
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Qwen API error {response.status}: {error_text}")
                    raise Exception(f"Qwen API error: {response.status}")
                    
    except Exception as e:
        logger.error(f"Qwen API error: {e}")
        raise
```

#### Fix DeepSeekClient

```python
async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                               max_tokens: int = 2000) -> Dict:  # ← Changed return type
    """Async chat completion for DeepSeek with usage tracking"""
    try:
        # ... existing setup code ...
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.api_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract content AND usage
                    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    usage = data.get('usage', {})  # ← NEW: Get actual token counts
                    
                    return {
                        'content': content,
                        'usage': {
                            'prompt_tokens': usage.get('prompt_tokens', 0),
                            'completion_tokens': usage.get('completion_tokens', 0),
                            'total_tokens': usage.get('total_tokens', 0)
                        }
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"DeepSeek API error {response.status}: {error_text}")
                    raise Exception(f"DeepSeek API error: {response.status}")
                    
    except Exception as e:
        logger.error(f"DeepSeek API error: {e}")
        raise
```

#### Fix KimiClient

```python
async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                               max_tokens: int = 2000) -> Dict:  # ← Changed return type
    """Async chat completion for Kimi with usage tracking"""
    try:
        # ... existing setup code ...
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.api_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract content AND usage
                    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    usage = data.get('usage', {})  # ← NEW: Get actual token counts
                    
                    return {
                        'content': content,
                        'usage': {
                            'prompt_tokens': usage.get('prompt_tokens', 0),
                            'completion_tokens': usage.get('completion_tokens', 0),
                            'total_tokens': usage.get('total_tokens', 0)
                        }
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Kimi API error {response.status}: {error_text}")
                    raise Exception(f"Kimi API error: {response.status}")
                    
    except Exception as e:
        logger.error(f"Kimi API error: {e}")
        raise
```

#### Fix HunyuanClient (OpenAI-compatible)

```python
async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                               max_tokens: int = 2000) -> Dict:  # ← Changed return type
    """Async chat completion for Hunyuan with usage tracking"""
    try:
        # ... existing setup code ...
        
        # Call OpenAI-compatible API
        completion = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Extract content AND usage (OpenAI format)
        content = completion.choices[0].message.content
        usage = completion.usage  # ← Already an object with attributes
        
        return {
            'content': content,
            'usage': {
                'prompt_tokens': usage.prompt_tokens if usage else 0,
                'completion_tokens': usage.completion_tokens if usage else 0,
                'total_tokens': usage.total_tokens if usage else 0
            }
        }
            
    except Exception as e:
        logger.error(f"Hunyuan API error: {e}")
        raise
```

---

## Streaming: How to Get Token Counts

### The Challenge with Streaming

**Problem:** Token counts arrive at the END of the stream, not during.

**DashScope Streaming Response:**
```
data: {"choices":[{"delta":{"content":"Hello"}}]}
data: {"choices":[{"delta":{"content":" world"}}]}
data: {"choices":[{"delta":{"content":"!"}}]}
data: {"choices":[{"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":3}}
data: [DONE]
```

**Solution:** Accumulate chunks and extract usage from final message.

### Modified Streaming Client

**File:** `clients/llm.py`

```python
async def async_stream_chat_completion(
    self, 
    messages: List[Dict], 
    temperature: float = None,
    max_tokens: int = 1000
) -> AsyncGenerator[Dict, None]:  # ← Changed to yield dicts
    """
    Stream chat completion from Qwen API (async generator).
    Yields both tokens AND final usage stats.
    
    Yields:
        Dict with:
        - type: 'token' or 'usage'
        - content: token text (if type='token')
        - usage: token counts (if type='usage')
    """
    try:
        # ... existing setup code ...
        
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True}  # ← Important!
        }
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.api_url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Qwen stream error {response.status}: {error_text}")
                    raise Exception(f"Qwen stream error: {response.status}")
                
                async for line_bytes in response.content:
                    line = line_bytes.decode('utf-8').strip()
                    
                    if not line or not line.startswith('data: '):
                        continue
                    
                    data_content = line[6:]  # Remove 'data: '
                    
                    if data_content.strip() == '[DONE]':
                        break
                    
                    try:
                        data = json.loads(data_content)
                        
                        # Check for token content
                        delta = data.get('choices', [{}])[0].get('delta', {})
                        content = delta.get('content', '')
                        
                        if content:
                            yield {
                                'type': 'token',
                                'content': content
                            }
                        
                        # Check for usage info (comes at end)
                        usage = data.get('usage')
                        if usage:
                            yield {
                                'type': 'usage',
                                'usage': {
                                    'prompt_tokens': usage.get('prompt_tokens', 0),
                                    'completion_tokens': usage.get('completion_tokens', 0),
                                    'total_tokens': usage.get('total_tokens', 0)
                                }
                            }
                    
                    except json.JSONDecodeError:
                        continue
    
    except Exception as e:
        logger.error(f"Qwen streaming error: {e}")
        raise
```

---

## Modified LLM Service to Track Usage

**File:** `services/llm_service.py`

### Non-Streaming: Extract Usage Directly

```python
async def chat(
    self,
    prompt: str,
    model: str = 'qwen',
    temperature: Optional[float] = None,
    max_tokens: int = 2000,
    timeout: Optional[float] = None,
    system_message: Optional[str] = None,
    # Track usage parameters
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    session_id: Optional[str] = None,
    request_type: str = 'diagram_generation',
    diagram_type: Optional[str] = None,
    **kwargs
) -> str:
    """
    Chat with LLM (non-streaming).
    Automatically tracks ACTUAL token usage from API response.
    """
    import time
    start_time = time.time()
    
    try:
        # Call LLM (now returns dict with usage)
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
        
        # Extract usage from response
        if isinstance(result, dict):
            content = result.get('content', '')
            usage = result.get('usage', {})
            
            # Track ACTUAL usage (not estimated!)
            if usage and (usage.get('total_tokens', 0) > 0):
                from services.token_tracker import token_tracker
                from config.database import SessionLocal
                
                db = SessionLocal()
                try:
                    await token_tracker.track_usage(
                        db=db,
                        model_alias=model,
                        input_tokens=usage.get('prompt_tokens', 0),      # ← ACTUAL
                        output_tokens=usage.get('completion_tokens', 0), # ← ACTUAL
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
            
            return content
        
        # Backward compatibility (if client doesn't return dict)
        return result
        
    except Exception as e:
        logger.error(f"LLM chat error: {e}")
        raise
```

### Streaming: Capture Usage from Final Message

```python
async def stream_progressive(
    self,
    prompt: str,
    models: List[str] = None,
    temperature: Optional[float] = None,
    max_tokens: int = 2000,
    timeout: Optional[float] = None,
    system_message: Optional[str] = None,
    # Track usage parameters
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    session_id: Optional[str] = None,
    request_type: str = 'node_palette',
    diagram_type: Optional[str] = None,
    **kwargs
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream from multiple LLMs concurrently.
    Tracks ACTUAL token usage for each LLM from API responses.
    """
    if models is None:
        models = ['qwen', 'deepseek', 'kimi', 'hunyuan']
    
    if not session_id:
        from services.token_tracker import token_tracker
        session_id = token_tracker.generate_session_id()
    
    logger.info(f"[LLMService] stream_progressive() - session {session_id}")
    
    # Track usage per LLM
    llm_usage = {model: None for model in models}
    llm_start_times = {model: time.time() for model in models}
    
    queue = asyncio.Queue()
    
    async def stream_single(model: str):
        """Stream from one LLM, capture usage at end."""
        try:
            async for chunk in self.chat_stream(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                system_message=system_message,
                **kwargs
            ):
                # New format: chunk is dict with 'type' and content/usage
                if isinstance(chunk, dict):
                    if chunk.get('type') == 'token':
                        # Forward token to client
                        await queue.put({
                            'event': 'token',
                            'llm': model,
                            'token': chunk.get('content', ''),
                            'timestamp': time.time()
                        })
                    
                    elif chunk.get('type') == 'usage':
                        # Capture ACTUAL usage stats
                        llm_usage[model] = chunk.get('usage', {})
                
                else:
                    # Backward compatibility: plain string tokens
                    await queue.put({
                        'event': 'token',
                        'llm': model,
                        'token': chunk,
                        'timestamp': time.time()
                    })
            
            # LLM completed
            duration = time.time() - llm_start_times[model]
            
            await queue.put({
                'event': 'complete',
                'llm': model,
                'duration': duration,
                'usage': llm_usage[model],  # ← Include ACTUAL usage
                'timestamp': time.time()
            })
            
        except Exception as e:
            await queue.put({
                'event': 'error',
                'llm': model,
                'error': str(e),
                'timestamp': time.time()
            })
    
    # Start all LLMs
    tasks = [asyncio.create_task(stream_single(model)) for model in models]
    active_tasks = len(tasks)
    
    # Yield chunks from queue
    while active_tasks > 0:
        try:
            chunk = await asyncio.wait_for(queue.get(), timeout=0.1)
            
            # Track usage when LLM completes
            if chunk['event'] == 'complete':
                active_tasks -= 1
                
                # Record ACTUAL usage
                usage = chunk.get('usage')
                if usage:
                    from services.token_tracker import token_tracker
                    from config.database import SessionLocal
                    
                    db = SessionLocal()
                    try:
                        await token_tracker.track_usage(
                            db=db,
                            model_alias=chunk['llm'],
                            input_tokens=usage.get('prompt_tokens', 0),      # ← ACTUAL
                            output_tokens=usage.get('completion_tokens', 0), # ← ACTUAL
                            request_type=request_type,
                            diagram_type=diagram_type,
                            user_id=user_id,
                            organization_id=organization_id,
                            session_id=session_id,
                            response_time=chunk['duration'],
                            success=True
                        )
                    finally:
                        db.close()
            
            elif chunk['event'] == 'error':
                active_tasks -= 1
            
            yield chunk
            
        except asyncio.TimeoutError:
            continue
    
    # Wait for all tasks to complete
    await asyncio.gather(*tasks, return_exceptions=True)
```

---

## Middleware Approach (Alternative)

**You mentioned middleware - that's also a great approach!**

### Response Middleware to Log All LLM Calls

**File:** `middleware/llm_usage_middleware.py` (NEW)

```python
"""
Middleware to automatically track ALL LLM token usage.
Intercepts responses and extracts usage data.
"""

import logging
import time
import json
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

from services.token_tracker import token_tracker
from config.database import SessionLocal

logger = logging.getLogger(__name__)

class LLMUsageMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track LLM token usage from API responses.
    Works with both streaming and non-streaming endpoints.
    """
    
    # Endpoints that make LLM calls
    LLM_ENDPOINTS = [
        '/api/generate',
        '/api/node-palette',
        '/api/autocomplete',
        '/api/generate-multi',
    ]
    
    async def dispatch(self, request, call_next: Callable):
        """Intercept requests to LLM endpoints"""
        
        # Check if this is an LLM endpoint
        path = request.url.path
        is_llm_endpoint = any(path.startswith(ep) for ep in self.LLM_ENDPOINTS)
        
        if not is_llm_endpoint:
            return await call_next(request)
        
        # Track request timing
        start_time = time.time()
        
        # Get user info from request state (if authenticated)
        user_id = getattr(request.state, 'user_id', None)
        organization_id = getattr(request.state, 'organization_id', None)
        
        # Process request
        response = await call_next(request)
        
        # For non-streaming responses, extract usage from response body
        if not response.headers.get('content-type', '').startswith('text/event-stream'):
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            try:
                # Try to parse as JSON
                data = json.loads(body.decode('utf-8'))
                
                # Check for usage data
                usage = data.get('usage')
                if usage:
                    response_time = time.time() - start_time
                    
                    # Track usage
                    db = SessionLocal()
                    try:
                        await token_tracker.track_usage(
                            db=db,
                            model_alias=data.get('model', 'unknown'),
                            input_tokens=usage.get('prompt_tokens', 0),
                            output_tokens=usage.get('completion_tokens', 0),
                            request_type=path.split('/')[-1],  # Extract from path
                            user_id=user_id,
                            organization_id=organization_id,
                            response_time=response_time,
                            success=True
                        )
                    finally:
                        db.close()
            
            except Exception as e:
                logger.debug(f"Could not extract usage from response: {e}")
            
            # Reconstruct response with original body
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        
        # For streaming, usage is tracked in the stream handler
        return response
```

**Register in main.py:**
```python
from middleware.llm_usage_middleware import LLMUsageMiddleware

app.add_middleware(LLMUsageMiddleware)
```

---

## Why This is Better

### ❌ Old Approach (Estimation)

```python
# Estimate tokens from text
input_tokens = len(prompt) / 4  # ← Inaccurate!
output_tokens = len(response) / 4  # ← Inaccurate!
```

**Problems:**
- ❌ English ≈ 4 chars/token, Chinese ≈ 1.5 chars/token
- ❌ Code has different tokenization
- ❌ Can be off by 20-30%!
- ❌ No way to validate

### ✅ New Approach (API-Provided)

```python
# Use actual counts from API
usage = response.get('usage')
input_tokens = usage.get('prompt_tokens')    # ← ACTUAL
output_tokens = usage.get('completion_tokens')  # ← ACTUAL
```

**Benefits:**
- ✅ **100% accurate** (from API itself)
- ✅ **Matches billing** (same counts provider uses)
- ✅ **No estimation errors**
- ✅ **Consistent** across all languages/content

---

## Example: Before vs After

### Before (Estimation)

```
Prompt: "生成思维导图关于Python编程" (15 chars)
Response: "好的，我来为您生成..." (120 chars)

Estimated:
- Input: 15/1.5 = 10 tokens
- Output: 120/1.5 = 80 tokens
- Total: 90 tokens
- Cost: ¥0.00011

Actual from API:
- Input: 18 tokens  (80% error!)
- Output: 95 tokens (16% error!)
- Total: 113 tokens (20% error!)
- Cost: ¥0.00014  (27% cost error!)
```

### After (API-Provided)

```
Response from API:
{
  "usage": {
    "prompt_tokens": 18,
    "completion_tokens": 95,
    "total_tokens": 113
  }
}

Tracked:
- Input: 18 tokens  (100% accurate)
- Output: 95 tokens (100% accurate)
- Total: 113 tokens (100% accurate)
- Cost: ¥0.00014   (100% accurate)
```

---

## Implementation Priority

### Option 1: Modify Clients (Recommended)
**Time:** 2-3 hours  
**Accuracy:** 100%  
**Effort:** Low  

Just change return type from `str` to `Dict` with usage.

### Option 2: Middleware (Alternative)
**Time:** 1-2 hours  
**Accuracy:** 100%  
**Effort:** Very Low  

Intercept all responses automatically, but harder to get request context.

### Option 3: Both! (Best)
**Time:** 3-4 hours  
**Accuracy:** 100%  
**Effort:** Low  

Use both approaches:
- Clients return usage (primary)
- Middleware as backup/validation

---

## Summary

### What We Were Doing Wrong

❌ **Throwing away** actual token counts from API  
❌ **Estimating** from character counts (20-30% error)  
❌ **Inaccurate** cost calculations  

### What We Should Do

✅ **Extract** `usage` field from API responses  
✅ **Use actual** `prompt_tokens` and `completion_tokens`  
✅ **Track accurately** for billing  
✅ **100% match** with provider's counts  

### Impact

- **Cost accuracy**: ±30% → 100%
- **Token tracking**: Estimated → Actual
- **Billing match**: No → Yes
- **Audit trail**: Incomplete → Complete

This is the **correct** way to track tokens! 🎯


