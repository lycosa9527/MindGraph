# DashScope SDK vs REST API Implementation Guide

**Document Version:** 1.0  
**Date:** 2025-10-26  
**Author:** lyc9527  
**Made by:** MTEL Team from Educational Technology, Beijing Normal University

---

## Table of Contents

1. [Current Implementation Analysis](#current-implementation-analysis)
2. [DashScope SDK Benefits](#dashscope-sdk-benefits)
3. [Comparison Matrix](#comparison-matrix)
4. [Migration Guide (If Needed)](#migration-guide-if-needed)
5. [Code Examples](#code-examples)
6. [Testing Strategy](#testing-strategy)
7. [Recommendation](#recommendation)

---

## Current Implementation Analysis

### Overview

MindGraph currently uses **two different approaches** for LLM integration:

| LLM | SDK/Approach | Location | Purpose |
|-----|-------------|----------|---------|
| **Qwen** (text) | Direct REST API (aiohttp) | `clients/llm.py` | Text generation, classification |
| **DeepSeek** | Direct REST API (aiohttp) | `clients/llm.py` | Reasoning tasks |
| **Kimi** | Direct REST API (aiohttp) | `clients/llm.py` | Creative generation |
| **Hunyuan** | OpenAI SDK | `clients/llm.py` | Alternative text generation |
| **Qwen Omni** | DashScope SDK | `clients/omni_client.py` | Voice conversation |

### Current REST API Implementation

**File:** `clients/llm.py`

**Key Features:**
- Uses `aiohttp` for async HTTP requests
- Manual SSE (Server-Sent Events) parsing for streaming
- Custom error handling and logging
- Temperature and token control
- Supports both streaming and non-streaming modes

**Code Structure (per client):**
```python
class QwenClient:
    def __init__(self):
        self.api_url = config.QWEN_API_URL  # DashScope compatible-mode endpoint
        self.api_key = config.QWEN_API_KEY
        
    async def chat_completion(self, messages, temperature, max_tokens):
        # Manual HTTP request with aiohttp
        # Manual JSON parsing
        # Manual error handling
        
    async def async_stream_chat_completion(self, messages, ...):
        # Manual SSE stream parsing
        # line.startswith('data: ')
        # [DONE] detection
```

**Lines of Code:**
- QwenClient: ~180 lines
- DeepSeekClient: ~145 lines
- KimiClient: ~140 lines
- HunyuanClient: ~110 lines (using OpenAI SDK)
- **Total:** ~575 lines for REST implementations

---

## DashScope SDK Benefits

### 1. **Simplified API Interaction**

**Current (Manual):**
```python
async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
    async with session.post(self.api_url, json=payload, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            return data.get('choices', [{}])[0].get('message', {}).get('content', '')
        else:
            error_text = await response.text()
            raise Exception(f"API error: {response.status}")
```

**With DashScope SDK:**
```python
from dashscope import Generation

response = Generation.call(
    model='qwen-plus',
    messages=messages,
    temperature=temperature,
    max_tokens=max_tokens
)
if response.status_code == 200:
    return response.output.text
```

**Reduction:** ~10 lines → ~7 lines (30% less code)

---

### 2. **Built-in Error Handling & Retry Logic**

**Current:**
- Manual error checking for HTTP status codes
- No automatic retries on transient failures
- Custom exception handling per client

**With SDK:**
- Automatic retry on network errors (with exponential backoff)
- Standardized error codes and messages
- Built-in rate limiting support

---

### 3. **Enhanced Streaming Support**

**Current (Manual SSE Parsing):**
```python
async for line_bytes in response.content:
    line = line_bytes.decode('utf-8').strip()
    
    if not line or not line.startswith('data: '):
        continue
    
    data_content = line[6:]  # Remove 'data: ' prefix
    
    if data_content.strip() == '[DONE]':
        break
    
    try:
        data = json.loads(data_content)
        delta = data.get('choices', [{}])[0].get('delta', {})
        content = delta.get('content', '')
        
        if content:
            yield content
    except json.JSONDecodeError:
        continue
```

**With SDK:**
```python
responses = Generation.call(
    model='qwen-plus',
    messages=messages,
    stream=True
)

for response in responses:
    if response.status_code == 200:
        yield response.output.text
```

**Reduction:** ~20 lines → ~5 lines (75% less code)

---

### 4. **Consistent Response Structure**

All DashScope SDK responses follow this pattern:

```python
class Response:
    status_code: int
    request_id: str
    output: Output
    usage: Usage
    
class Output:
    text: str
    finish_reason: str
    
class Usage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
```

**Current:** You manually parse different response formats for each model.

---

### 5. **Connection Pooling & Performance**

- **SDK:** Optimized connection pooling, HTTP/2 support, persistent connections
- **Current:** Creates new `ClientSession` per request (can be optimized, but requires more code)

---

### 6. **Official Support & Updates**

- **SDK:** Maintained by Alibaba, automatic support for new models
- **Current:** You manually update for API changes

---

## Comparison Matrix

| Feature | Current (REST API) | DashScope SDK | Winner |
|---------|-------------------|---------------|--------|
| **Lines of Code** | ~575 lines | ~250 lines (est.) | SDK ✅ |
| **Error Handling** | Manual | Automatic + Retry | SDK ✅ |
| **Streaming** | Manual SSE parsing | Built-in | SDK ✅ |
| **Rate Limiting** | Custom implementation | Built-in | SDK ✅ |
| **Connection Pooling** | Manual (not implemented) | Automatic | SDK ✅ |
| **Debugging** | Full HTTP visibility | Abstracted | REST ✅ |
| **Flexibility** | High (custom headers, etc.) | Medium | REST ✅ |
| **Dependencies** | aiohttp (already used) | dashscope (already have) | Tie ⚖️ |
| **OpenAI Compatibility** | Uses compatible-mode endpoint | Uses native DashScope API | REST ✅ |
| **Maintenance** | You maintain | Alibaba maintains | SDK ✅ |
| **Learning Curve** | Low (standard HTTP) | Medium (SDK-specific) | REST ✅ |
| **Multi-Provider Support** | Easy (just change URL) | DashScope-only | REST ✅ |
| **Performance** | Good | Slightly better | SDK ✅ |
| **Current Stability** | Works perfectly | Unknown (not tested) | REST ✅ |

**Score:** SDK (8) vs REST (6)

---

## Migration Guide (If Needed)

### Prerequisites

✅ You already have `dashscope>=1.23.9` in `requirements.txt`

### Step 1: Import DashScope SDK

**File:** `clients/llm.py`

```python
# Add at top of file
from dashscope import Generation
import dashscope
```

### Step 2: Create SDK-Based QwenClient

**Option A: Replace Current Implementation**

```python
class QwenClientSDK:
    """Qwen client using DashScope SDK"""
    
    def __init__(self, model_type='classification'):
        dashscope.api_key = config.QWEN_API_KEY
        self.model_type = model_type
        self.default_temperature = 0.9 if model_type == 'generation' else 0.7
        
    async def chat_completion(self, messages: List[Dict], temperature: float = None,
                            max_tokens: int = 1000) -> str:
        """Send chat completion request using SDK"""
        if temperature is None:
            temperature = self.default_temperature
        
        # Select model
        if self.model_type == 'classification':
            model_name = config.QWEN_MODEL_CLASSIFICATION
        else:
            model_name = config.QWEN_MODEL_GENERATION
        
        # Call SDK
        response = Generation.call(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            result_format='message'  # Returns OpenAI-compatible format
        )
        
        if response.status_code == 200:
            return response.output.text
        else:
            raise Exception(f"DashScope error {response.code}: {response.message}")
    
    async def async_stream_chat_completion(
        self, 
        messages: List[Dict], 
        temperature: float = None,
        max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion using SDK"""
        if temperature is None:
            temperature = self.default_temperature
        
        model_name = (config.QWEN_MODEL_CLASSIFICATION if self.model_type == 'classification' 
                     else config.QWEN_MODEL_GENERATION)
        
        responses = Generation.call(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            result_format='message'
        )
        
        for response in responses:
            if response.status_code == 200:
                if response.output.text:
                    yield response.output.text
            else:
                raise Exception(f"Stream error {response.code}: {response.message}")
```

**Option B: Keep Both (Recommended for Testing)**

```python
# Keep existing QwenClient as QwenClientREST
class QwenClientREST:
    # ... existing implementation ...

# Add new SDK version
class QwenClientSDK:
    # ... SDK implementation ...

# Add feature flag to choose
USE_DASHSCOPE_SDK = os.getenv('USE_DASHSCOPE_SDK', 'false').lower() == 'true'

if USE_DASHSCOPE_SDK:
    qwen_client_classification = QwenClientSDK(model_type='classification')
    qwen_client_generation = QwenClientSDK(model_type='generation')
else:
    qwen_client_classification = QwenClientREST(model_type='classification')
    qwen_client_generation = QwenClientREST(model_type='generation')
```

### Step 3: Update DeepSeek Client

```python
class DeepSeekClientSDK:
    """DeepSeek client using DashScope SDK"""
    
    def __init__(self):
        dashscope.api_key = config.QWEN_API_KEY
        self.model_name = config.DEEPSEEK_MODEL
        self.default_temperature = 0.6
    
    async def chat_completion(self, messages: List[Dict], temperature: float = None,
                             max_tokens: int = 2000) -> str:
        """DeepSeek via DashScope SDK"""
        if temperature is None:
            temperature = self.default_temperature
        
        response = Generation.call(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            result_format='message'
        )
        
        if response.status_code == 200:
            return response.output.text
        else:
            raise Exception(f"DeepSeek error {response.code}: {response.message}")
    
    # Add streaming method...
```

### Step 4: Update Kimi Client

Similar pattern to DeepSeek.

### Step 5: Update Environment Variables

**File:** `.env`

```bash
# Enable DashScope SDK (optional feature flag)
USE_DASHSCOPE_SDK=false  # Set to 'true' to use SDK

# DashScope API settings
QWEN_API_KEY=sk-xxx
# Note: SDK doesn't need QWEN_API_URL, it uses DashScope endpoint automatically
```

### Step 6: Update Configuration

**File:** `config/settings.py`

```python
@property
def USE_DASHSCOPE_SDK(self):
    """Use DashScope SDK instead of REST API"""
    return self._get_cached_value('USE_DASHSCOPE_SDK', 'false').lower() == 'true'
```

### Step 7: Testing Strategy

See [Testing Strategy](#testing-strategy) section below.

### Step 8: Gradual Rollout

1. ✅ **Week 1:** Implement SDK versions alongside REST versions
2. ✅ **Week 2:** Test SDK versions with feature flag disabled (REST still active)
3. ✅ **Week 3:** Enable SDK for 10% of requests (A/B testing)
4. ✅ **Week 4:** Enable SDK for 50% of requests
5. ✅ **Week 5:** Full SDK rollout if no issues
6. ✅ **Week 6:** Remove REST implementation (optional)

---

## Code Examples

### Example 1: Non-Streaming Request

**Current (REST):**
```python
async def chat_completion(self, messages, temperature=0.7, max_tokens=1000):
    payload = {
        "model": self.model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        "extra_body": {"enable_thinking": False}
    }
    
    headers = {
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
        async with session.post(self.api_url, json=payload, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('choices', [{}])[0].get('message', {}).get('content', '')
            else:
                error_text = await response.text()
                logger.error(f"API error {response.status}: {error_text}")
                raise Exception(f"API error: {response.status}")
```

**With SDK:**
```python
def chat_completion(self, messages, temperature=0.7, max_tokens=1000):
    response = Generation.call(
        model=self.model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        result_format='message'
    )
    
    if response.status_code == 200:
        return response.output.text
    else:
        raise Exception(f"API error {response.code}: {response.message}")
```

**Lines:** 25 → 9 (64% reduction)

---

### Example 2: Streaming Request

**Current (REST):**
```python
async def async_stream_chat_completion(self, messages, temperature=0.7, max_tokens=1000):
    payload = {
        "model": self.model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "extra_body": {"enable_thinking": False}
    }
    
    headers = {
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json"
    }
    
    timeout = aiohttp.ClientTimeout(
        total=None,
        connect=10,
        sock_read=self.timeout
    )
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(self.api_url, json=payload, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Stream error: {response.status}")
            
            async for line_bytes in response.content:
                line = line_bytes.decode('utf-8').strip()
                
                if not line or not line.startswith('data: '):
                    continue
                
                data_content = line[6:]
                
                if data_content.strip() == '[DONE]':
                    break
                
                try:
                    data = json.loads(data_content)
                    delta = data.get('choices', [{}])[0].get('delta', {})
                    content = delta.get('content', '')
                    
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
```

**With SDK:**
```python
def stream_chat_completion(self, messages, temperature=0.7, max_tokens=1000):
    responses = Generation.call(
        model=self.model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        result_format='message'
    )
    
    for response in responses:
        if response.status_code == 200:
            if response.output.text:
                yield response.output.text
        else:
            raise Exception(f"Stream error {response.code}: {response.message}")
```

**Lines:** 47 → 15 (68% reduction)

---

## Testing Strategy

### Phase 1: Unit Tests

**File:** `tests/services/test_dashscope_sdk.py`

```python
import pytest
from clients.llm import QwenClientSDK, DeepSeekClientSDK, KimiClientSDK

@pytest.mark.asyncio
async def test_qwen_sdk_chat_completion():
    """Test Qwen SDK non-streaming"""
    client = QwenClientSDK(model_type='generation')
    messages = [{"role": "user", "content": "What is 2+2?"}]
    
    response = await client.chat_completion(messages, temperature=0.1, max_tokens=100)
    
    assert isinstance(response, str)
    assert len(response) > 0
    assert "4" in response.lower()

@pytest.mark.asyncio
async def test_qwen_sdk_streaming():
    """Test Qwen SDK streaming"""
    client = QwenClientSDK(model_type='generation')
    messages = [{"role": "user", "content": "Count to 5"}]
    
    chunks = []
    async for chunk in client.async_stream_chat_completion(messages, temperature=0.1):
        chunks.append(chunk)
    
    full_response = ''.join(chunks)
    assert len(chunks) > 0
    assert len(full_response) > 0

@pytest.mark.asyncio
async def test_deepseek_sdk():
    """Test DeepSeek via SDK"""
    client = DeepSeekClientSDK()
    messages = [{"role": "user", "content": "Solve: 3x + 5 = 20"}]
    
    response = await client.chat_completion(messages, max_tokens=200)
    
    assert isinstance(response, str)
    assert len(response) > 0
```

### Phase 2: Integration Tests

**File:** `tests/services/test_sdk_vs_rest_comparison.py`

```python
import pytest
from clients.llm import QwenClientREST, QwenClientSDK

@pytest.mark.asyncio
async def test_rest_vs_sdk_consistency():
    """Compare REST and SDK responses for consistency"""
    messages = [{"role": "user", "content": "What is the capital of France?"}]
    
    # REST client
    rest_client = QwenClientREST(model_type='generation')
    rest_response = await rest_client.chat_completion(messages, temperature=0.1, max_tokens=50)
    
    # SDK client
    sdk_client = QwenClientSDK(model_type='generation')
    sdk_response = await sdk_client.chat_completion(messages, temperature=0.1, max_tokens=50)
    
    # Both should mention Paris
    assert "paris" in rest_response.lower()
    assert "paris" in sdk_response.lower()
    
    # Responses should be similar length (within 50% difference)
    len_diff = abs(len(rest_response) - len(sdk_response)) / max(len(rest_response), len(sdk_response))
    assert len_diff < 0.5
```

### Phase 3: Load Testing

```bash
# Test both implementations under load
pytest tests/services/test_dashscope_sdk.py -n 10 --count 100
```

### Phase 4: Production A/B Testing

**File:** `services/llm_service.py`

```python
import random

async def get_llm_response(messages, use_sdk=None):
    """Get LLM response with optional A/B testing"""
    
    # A/B testing: 50% SDK, 50% REST
    if use_sdk is None:
        use_sdk = random.random() < 0.5
    
    if use_sdk:
        client = qwen_client_sdk
        logger.info("Using DashScope SDK")
    else:
        client = qwen_client_rest
        logger.info("Using REST API")
    
    return await client.chat_completion(messages)
```

---

## Recommendation

### **Keep Current REST API Implementation**

**Reasons:**

1. ✅ **Current Implementation Works Well**
   - Stable, tested, and production-ready
   - No reported issues with current approach
   - Clean async implementation

2. ✅ **You Already Use DashScope SDK Where Needed**
   - Qwen Omni (voice) uses SDK because REST doesn't support it
   - Text generation has good REST API support

3. ✅ **OpenAI-Compatible Endpoint**
   - Your REST approach uses `/compatible-mode/v1` endpoint
   - More standard, easier to switch providers if needed
   - Future-proof for multi-provider support

4. ✅ **Multi-Provider Architecture**
   - You support Qwen, DeepSeek, Kimi, Hunyuan
   - REST approach is more flexible for mixed providers
   - SDK locks you into DashScope ecosystem

5. ✅ **Code Quality**
   - Your current implementation is well-structured
   - Good error handling and logging
   - Proper async/await patterns

6. ⚠️ **Migration Risk vs Reward**
   - Migration effort: ~2-3 days
   - Testing required: ~1 week
   - Benefits: Marginal (slight code reduction, built-in retry)
   - Risk: Breaking production code that works

### **Consider SDK Migration If:**

- ❌ You encounter rate limiting issues frequently
- ❌ You want automatic retries on network failures
- ❌ You're spending time maintaining HTTP client code
- ❌ Alibaba releases SDK-only features you need
- ❌ You want to reduce overall codebase size

### **Hybrid Approach (Current Status):**

✅ **Keep this approach:**
- Qwen Omni voice: **DashScope SDK** (required)
- Text generation (Qwen/DeepSeek/Kimi): **REST API** (works well)
- Hunyuan: **OpenAI SDK** (Tencent-specific)

This hybrid approach gives you:
- Best of both worlds
- Flexibility and control
- SDK support where needed (voice)
- Standard REST for text

---

## Conclusion

Your current implementation is **production-ready and well-architected**. The DashScope SDK would provide marginal benefits (code reduction, automatic retries) but at the cost of migration effort and reduced flexibility.

**Final Recommendation:** **Keep current REST API implementation** unless you encounter specific issues that SDK would solve.

---

## Appendix: Quick Reference

### DashScope SDK Documentation

- Official Docs: https://help.aliyun.com/zh/dashscope/
- Python SDK: https://github.com/aliyun/dashscope-sdk-python
- API Reference: https://dashscope.aliyuncs.com/api/v1/

### Key SDK Classes

```python
from dashscope import Generation, MultiModalConversation
from dashscope.audio.qwen_omni import OmniRealtimeConversation

# Text generation
Generation.call(model='qwen-plus', messages=[...])

# Streaming
responses = Generation.call(model='qwen-plus', messages=[...], stream=True)
for response in responses:
    print(response.output.text)
```

### Migration Checklist

- [ ] Add SDK imports to `clients/llm.py`
- [ ] Create `*ClientSDK` classes alongside REST versions
- [ ] Add `USE_DASHSCOPE_SDK` feature flag
- [ ] Write unit tests for SDK clients
- [ ] Compare REST vs SDK responses
- [ ] Load testing with both implementations
- [ ] Production A/B testing (10% → 50% → 100%)
- [ ] Monitor error rates and performance
- [ ] Update documentation
- [ ] Remove REST implementation (optional, after 1 month)

---

**End of Document**

