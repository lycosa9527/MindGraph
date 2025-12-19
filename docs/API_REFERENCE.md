# MindGraph API Reference

## Overview

MindGraph provides a RESTful API for generating AI-powered data visualizations from natural language prompts. The API features intelligent LLM-based classification, supports 10 diagram types, and provides both interactive graph generation and direct PNG export.

**Base URL**: `https://mg.mindspringedu.com` (or your deployed server URL)  
**API Version**: 4.12.0  
**Architecture**: Multi-agent system with smart LLM classification

**Key Features**:
- **Smart Classification**: LLM-based diagram type detection
- **10 Diagram Types**: Complete Thinking Maps, Mind Maps, and Concept Maps coverage
- **High Performance**: Dual-model LLM system (qwen-turbo + qwen-plus)
- **Multi-language**: English and Chinese support
- **Secure Authentication**: API key and JWT token support

**Endpoint Compatibility**: Both `/endpoint` and `/api/endpoint` formats are supported.

## Authentication | 身份验证

MindGraph supports **two authentication methods** depending on your use case:

### Method 1: API Key (Public API Access) | 方法1：API密钥（公共API访问）

**For external services (e.g., Dify, partners) accessing MindGraph API**  
**适用于外部服务（如Dify、合作伙伴）访问MindGraph API**

```http
X-API-Key: your_generated_api_key_here
```

**How to get an API key | 如何获取API密钥:**
1. Login to admin panel at `/admin` (admin account required)  
   登录管理面板 `/admin`（需要管理员账户）
2. Navigate to "🔑 API Keys" tab  
   进入"🔑 API Keys"标签页
3. Click "Create New API Key"  
   点击"创建新API密钥"
4. Copy the generated key (shown only once!)  
   复制生成的密钥（仅显示一次！）

**Supported endpoints | 支持的端点:**
- ✅ `/api/generate_png` - PNG generation
- ✅ `/api/generate_graph` - Graph generation
- ✅ `/api/ai_assistant/stream` - AI assistant
- ✅ `/api/generate_dingtalk` - DingTalk integration
- ✅ `/api/generate_multi_*` - Multi-generation endpoints
- ❌ Premium features (learning, thinking modes) - require JWT token

**Example | 示例:**
```bash
# Production server
curl -X POST https://mg.mindspringedu.com/api/generate_png \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mg_wX864RN8F7ZQtuDQU3zfjozR_R45i_-eQp9hYYq6JlQ" \
  -d '{"prompt": "Compare cats and dogs", "language": "en"}'

# Local development (localhost:9527)
# curl -X POST http://localhost:9527/api/generate_png ...
```

---

### Method 2: JWT Bearer Token (User Authentication) | 方法2：JWT令牌（用户认证）

**For authenticated users accessing premium features**  
**适用于已认证用户访问高级功能**

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**How to get a JWT token | 如何获取JWT令牌:**
1. Login via `/api/auth/login` or demo mode `/api/auth/demo/verify`  
   通过 `/api/auth/login` 或演示模式 `/api/auth/demo/verify` 登录
2. Receive `access_token` in response  
   在响应中获取 `access_token`
3. Include in `Authorization: Bearer <token>` header  
   在请求头中包含 `Authorization: Bearer <token>`

**Required for premium endpoints | 高级端点必需:**
- ✅ `/api/learning/*` - Learning mode features
- ✅ `/thinking_mode/*` - Thinking mode features
- ✅ `/api/cache/*` - Cache monitoring (admin only)
- ✅ `/admin/*` - Admin panel endpoints

**Example | 示例:**
```bash
# Production server
curl -X POST https://mg.mindspringedu.com/api/learning/start_session \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{"spec": {...}, "knocked_out_nodes": []}'

# Local development (localhost:9527)
# curl -X POST http://localhost:9527/api/learning/start_session ...
```

---

### Summary | 总结

| Use Case | Header | Example Value |
|----------|--------|---------------|
| **External services (Dify, etc.)** <br> 外部服务（Dify等） | `X-API-Key` | `mg_wX864RN8F7ZQtuDQU3zfjozR_R45i_-eQp9hYYq6JlQ` |
| **Authenticated users** <br> 已认证用户 | `Authorization: Bearer` | `Bearer eyJhbGci...` |

**Important Notes | 重要说明:**
- API keys have quotas and expiration dates (configurable in admin panel)  
  API密钥有配额和过期时间（可在管理面板配置）
- JWT tokens expire after 7 days by default  
  JWT令牌默认7天后过期
- Public endpoints work with either authentication method  
  公共端点支持两种认证方式
- Premium endpoints **require** JWT tokens (API keys will return 401)  
  高级端点**必须**使用JWT令牌（API密钥将返回401错误）

---

### LLM Service Configuration | LLM服务配置

The API also requires LLM service API keys configured via environment variables:

- **QWEN_API_KEY**: Required for core functionality
- **DEEPSEEK_API_KEY**: Optional for enhanced features

## Endpoints

### 1. PNG Generation

Generates a PNG image directly from a text prompt.

```http
POST /api/generate_png
POST /generate_png
```

**Authentication**: Optional (supports both API key and JWT token) | 可选（支持API密钥和JWT令牌）  
**Note**: Both endpoints are supported for backward compatibility.

#### Request

**Headers:**
```
Content-Type: application/json
X-API-Key: your_api_key_here          # Option 1: API Key authentication
# OR
Authorization: Bearer your_jwt_token   # Option 2: JWT token authentication
```

**Body:**
```json
{
  "prompt": "Compare cats and dogs",
  "language": "en",
  "style": {
    "theme": "modern",
    "colors": {
      "primary": "#4e79a7",
      "secondary": "#f28e2c"
    }
  }
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | ✅ | Natural language description of what to visualize |
| `language` | string | ❌ | Language code (`en` or `zh`). Defaults to `en` |
| `style` | object | ❌ | Visual styling options |

#### Default Values

- **`language`**: Defaults to `"en"` (English) if not specified
- **`style`**: Uses professional default theme and color scheme if not specified
- **`prompt`**: **Required** - cannot be omitted or left blank

#### Style Options

```json
{
  "theme": "modern|classic|minimal|dark|light",
  "colors": {
    "primary": "#hex_color",
    "secondary": "#hex_color",
    "accent": "#hex_color"
  }
}
```

#### Response

Returns a PNG image file that can be displayed directly in a web browser, downloaded, or embedded in documents.

### 2. DingTalk Integration

Generates a PNG image for DingTalk platform and returns markdown format with image URL.

```http
POST /api/generate_dingtalk
POST /generate_dingtalk
```

**Authentication**: Optional (supports both API key and JWT token) | 可选（支持API密钥和JWT令牌）

**Production Endpoint**: `https://mg.mindspringedu.com/api/generate_dingtalk`  
**生产环境端点**: `https://mg.mindspringedu.com/api/generate_dingtalk`

**Note**: Both endpoints are supported for backward compatibility.

#### Request

**Headers:**
```
Content-Type: application/json
X-API-Key: your_api_key_here          # Option 1: API Key authentication
# OR
Authorization: Bearer your_jwt_token   # Option 2: JWT token authentication
```

**Body:**
```json
{
  "prompt": "Compare cats and dogs",
  "language": "zh"
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | ✅ | Natural language description of what to visualize |
| `language` | string | ❌ | Language code (`en` or `zh`). Defaults to `zh` |

#### Response

Returns **plain text** in markdown image format (not JSON):

```
Content-Type: text/plain; charset=utf-8

![](https://mg.mindspringedu.com/api/temp_images/dingtalk_a1b2c3d4_1692812345.png)
```

**Response Format**: The endpoint returns raw plain text (not JSON) containing markdown image syntax with an empty alt text field. This format is optimized for direct use in DingTalk messages.

**Example Response**:
```
![](https://mg.mindspringedu.com/api/temp_images/dingtalk_346703f0_1760217144.png)
```

#### Important Notes

- **Plain Text Output**: Returns `Content-Type: text/plain`, not JSON - can be sent directly to DingTalk
- **Empty Alt Text**: Uses `![]()` format (empty brackets) to prevent duplicate text in DingTalk messages
- **Temporary Storage**: Images are stored temporarily and automatically cleaned up after 24 hours
- **Image Access**: Images are served through the `/api/temp_images/<filename>` endpoint
- **No Persistence**: Images are not permanently stored and will be lost after the cleanup period
- **Default Dimensions**: PNG exports use 1200x800 base dimensions with scale=2 for high quality

### 3. Cache Status

Returns JavaScript cache status and performance metrics for development and debugging.

```http
GET /cache/status
```

**Authentication**: Required (JWT token only - admin/authenticated users) | 必需（仅JWT令牌 - 管理员/已认证用户）  
**Note**: This endpoint is primarily for development use.

#### Response

**Success (200):**
```json
{
  "status": "initialized",
  "cache_strategy": "lazy_loading_with_intelligent_caching",
  "files_loaded": 15,
  "total_size_kb": 245.6,
  "memory_usage_mb": 0.24,
  "cache_hit_rate": 87.5,
  "total_requests": 120,
  "cache_hits": 105,
  "cache_misses": 15,
  "average_load_time": 0.023
}
```

#### Example Usage

```bash
# Basic PNG generation
curl -X POST http://localhost:9527/api/generate_png \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare cats and dogs"}' \
  --output comparison.png

# With language specification
curl -X POST http://localhost:9527/api/generate_png \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare cats and dogs", "language": "zh"}' \
  --output comparison_zh.png

# With custom styling
curl -X POST http://localhost:9527/api/generate_png \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a mind map about artificial intelligence",
    "language": "en",
    "style": {
      "theme": "modern",
      "colors": {
        "primary": "#4e79a7",
        "secondary": "#f28e2c"
      }
    }
  }' \
  --output ai_mindmap.png
```

#### Request Body Examples

**Minimal Request:**
```json
{
  "prompt": "Compare cats and dogs"
}
```

**With Language:**
```json
{
  "prompt": "Compare cats and dogs",
  "language": "zh"
}
```

**With Custom Styling:**
```json
{
  "prompt": "Compare cats and dogs",
  "language": "en",
  "style": {
    "theme": "dark",
    "colors": {
      "primary": "#ff6b6b",
      "secondary": "#4ecdc4"
    }
  }
}
```

#### Best Practices

- **For Quick Testing**: Use minimal request with just `prompt`
- **For Production**: Include language detection and consistent theming
- **For Dify Integration**: `{"prompt": "{{user_input}}"}` works perfectly

### 4. Interactive Graph Generation

Generates an interactive D3.js visualization with JSON data.

```http
POST /api/generate_graph
POST /generate_graph
```

**Authentication**: Optional (supports both API key and JWT token) | 可选（支持API密钥和JWT令牌）  
**Note**: Both endpoints are supported for backward compatibility.

#### Request

**Headers:**
```
Content-Type: application/json
X-API-Key: your_api_key_here          # Option 1: API Key authentication
# OR
Authorization: Bearer your_jwt_token   # Option 2: JWT token authentication
```

**Body:**
```json
{
  "prompt": "Compare traditional and modern education",
  "language": "en",
  "style": {
    "theme": "modern"
  }
}
```

#### Response

**Success (200):**
```json
{
  "status": "success",
  "data": {
    "type": "double_bubble_map",
    "svg_data": "...",
    "d3_config": {...},
    "metadata": {
      "prompt": "Compare traditional and modern education",
      "language": "en",
      "generated_at": "2024-01-01T00:00:00Z"
    }
  }
}
```

### 5. Multi-Model Generation (Parallel)

Generate diagrams using multiple LLM models in parallel for comparison.

```http
POST /api/generate_multi_parallel
```

**Authentication**: Optional (supports both API key and JWT token) | 可选（支持API密钥和JWT令牌）

#### Request

**Headers:**
```
Content-Type: application/json
X-API-Key: your_api_key_here          # Option 1: API Key authentication
# OR
Authorization: Bearer your_jwt_token   # Option 2: JWT token authentication
```

**Body:**
```json
{
  "prompt": "Compare cats and dogs",
  "language": "en",
  "models": ["qwen-turbo", "qwen-plus"]
}
```

#### Response

Returns results from all models as they complete:

```json
{
  "status": "success",
  "results": [
    {
      "model": "qwen-turbo",
      "data": {...},
      "timing": {"total_time": 2.1}
    },
    {
      "model": "qwen-plus",
      "data": {...},
      "timing": {"total_time": 3.5}
    }
  ]
}
```

### 6. Multi-Model Generation (Progressive)

Progressive parallel generation with Server-Sent Events (SSE) streaming.

```http
POST /api/generate_multi_progressive
```

**Authentication**: Optional (supports both API key and JWT token) | 可选（支持API密钥和JWT令牌）  
**Note**: Uses SSE for real-time progressive results.

#### Request

Same as parallel generation, but results stream as they complete.

### 7. Export PNG

Export existing graph data to PNG format.

```http
POST /api/export_png
```

**Authentication**: Optional (supports both API key and JWT token) | 可选（支持API密钥和JWT令牌）

#### Request

**Body:**
```json
{
  "graph_data": {...},
  "graph_type": "mind_map",
  "options": {
    "width": 1200,
    "height": 800,
    "scale": 2
  }
}
```

### 8. Health Check

Returns application status and version information.

```http
GET /health
GET /status
```

#### Response

**`/health` Response:**
```json
{
  "status": "ok",
  "version": "4.12.0"
}
```

**`/status` Response (with metrics):**
```json
{
  "status": "running",
  "framework": "FastAPI",
  "version": "4.12.0",
  "uptime_seconds": 3600.5,
  "memory_percent": 45.2,
  "timestamp": 1642012345.678
}
```

## Integration Examples

### Dify Integration | Dify集成

**Integration Direction**: Dify → MindGraph  
**集成方向**: Dify → MindGraph

MindGraph provides seamless integration with Dify through HTTP POST requests. This section covers how to configure Dify (external service) to call MindGraph API endpoints for diagram generation.  
MindGraph通过HTTP POST请求提供与Dify的无缝集成。本节介绍如何配置Dify（外部服务）调用MindGraph API端点进行图表生成。

**Note**: MindGraph also uses Dify API internally for its AI Assistant feature (`/api/ai_assistant/stream`). That configuration is separate and managed via environment variables (`DIFY_API_KEY`, `DIFY_API_URL`, `DIFY_TIMEOUT`).  
**注意**: MindGraph内部也使用Dify API来实现AI助手功能（`/api/ai_assistant/stream`）。该配置是独立的，通过环境变量（`DIFY_API_KEY`、`DIFY_API_URL`、`DIFY_TIMEOUT`）进行管理。

#### Step 1: Generate API Key | 步骤1：生成API密钥

**Before integrating with Dify, generate an API key in MindGraph:**  
**在与Dify集成之前，在MindGraph中生成API密钥：**

1. Login to MindGraph admin panel at `https://mg.mindspringedu.com/admin`  
   登录MindGraph管理面板 `https://mg.mindspringedu.com/admin`
   
2. Go to "🔑 API Keys" tab  
   进入"🔑 API Keys"标签页
   
3. Click "Create New API Key"  
   点击"创建新API密钥"
   
4. Fill in the details:  
   填写详细信息：
   - **Name**: `Dify Integration` (or any descriptive name)
   - **Description**: `API key for Dify to access MindGraph`
   - **Quota Limit**: Leave blank for unlimited, or set a number
   - **Expires At**: Optional expiration date
   
5. Click "Create" and **copy the generated key immediately** (it won't be shown again!)  
   点击"创建"并**立即复制生成的密钥**（不会再次显示！）
   
6. Save the key securely (format: `mg_xxxxx...`)  
   安全保存密钥（格式：`mg_xxxxx...`）

---

#### Step 2: Configure Dify HTTP Node | 步骤2：配置Dify HTTP节点

**HTTP Request Node Configuration:**
- **URL**: `https://mg.mindspringedu.com/api/generate_png`
- **Method**: `POST`
- **Headers**: 
  - `Content-Type: application/json`
  - **`X-API-Key: mg_xxxxx...`** ← **REQUIRED | 必需**

**Request Body:**
```json
{
  "prompt": "{{user_input}}"
}
```

**⚠️ Important | 重要提示:**
- You **MUST** include the `X-API-Key` header with your generated API key  
  你**必须**在请求头中包含带有生成的API密钥的`X-API-Key`
- Do **NOT** use `Authorization: Bearer` for Dify → MindGraph requests  
  对于Dify → MindGraph请求，**不要**使用`Authorization: Bearer`
- The API key format is: `X-API-Key: mg_xxxxx...`  
  API密钥格式为：`X-API-Key: mg_xxxxx...`

#### Step 3: Advanced Configuration (Optional) | 步骤3：高级配置（可选）

**With Language Detection:**
```json
{
  "prompt": "{{user_input}}",
  "language": "{{#if contains user_input '中文'}}zh{{else}}en{{/if}}"
}
```

**With Custom Styling:**
```json
{
  "prompt": "{{user_input}}",
  "language": "en",
  "style": {
    "theme": "dark",
    "colors": {
      "primary": "#1976d2",
      "secondary": "#f28e2c"
    }
  }
}
```

**Complete Dify HTTP Node Example | 完整的Dify HTTP节点示例:**
```
URL: https://mg.mindspringedu.com/api/generate_png
Method: POST
Headers:
  Content-Type: application/json
  X-API-Key: mg_wX864RN8F7ZQtuDQU3zfjozR_R45i_-eQp9hYYq6JlQ
Body:
  {
    "prompt": "{{user_input}}",
    "language": "en"
  }
```

#### Response Handling

**For PNG Images** (`/api/generate_png`): The response is a binary PNG image that can be directly displayed or saved.

**Content-Type**: `image/png`

**Example:**
```bash
# Save PNG response to file
curl -X POST https://mg.mindspringedu.com/api/generate_png \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mg_xxxxx" \
  -d '{"prompt": "Compare cats and dogs"}' \
  --output diagram.png
```

**For Interactive Diagrams** (`/api/generate_graph`): Returns JSON with diagram specification for frontend rendering.

**Content-Type**: `application/json`

**Response Format:**
```json
{
  "success": true,
  "spec": {
    "topic": "Climate Change",
    "concepts": [
      {"id": "1", "label": "Global Warming", "x": 100, "y": 200},
      {"id": "2", "label": "Carbon Emissions", "x": 300, "y": 200}
    ],
    "relationships": [
      {"source": "1", "target": "2", "label": "causes"}
    ]
  },
  "diagram_type": "mind_map",
  "language": "en",
  "extracted_topic": "Climate Change"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether generation succeeded |
| `spec` | object | Diagram specification with nodes, edges, and layout data |
| `diagram_type` | string | Detected/used diagram type (e.g., `mind_map`, `concept_map`, `double_bubble_map`) |
| `language` | string | Language used (`en` or `zh`) |
| `extracted_topic` | string | Main topic extracted from prompt |
| `error` | string | Error message if generation failed |
| `warning` | string | Warning message if partial recovery occurred |

**Note**: The `spec` object contains the complete diagram data structure that can be used to render the diagram in the frontend editor or export to PNG using `/api/export_png`.

### Python Integration

**With API Key Authentication:**
```python
import requests

def generate_png(prompt, api_key, language="en", style=None):
    # Production server
    url = "https://mg.mindspringedu.com/api/generate_png"
    # Local development: url = "http://localhost:9527/api/generate_png"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key  # API Key authentication
    }
    
    payload = {
        "prompt": prompt,
        "language": language
    }
    
    if style:
        payload["style"] = style
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        with open("generated_graph.png", "wb") as f:
            f.write(response.content)
        return "generated_graph.png"
    else:
        error = response.json()
        raise Exception(f"API Error: {error['error']}")

# Usage
api_key = "mg_wX864RN8F7ZQtuDQU3zfjozR_R45i_-eQp9hYYq6JlQ"  # Your generated API key
filename = generate_png("Compare cats and dogs", api_key, "en", {"theme": "modern"})
print(f"Graph saved as: {filename}")
```

**With JWT Token Authentication:**
```python
import requests

def generate_png_with_jwt(prompt, jwt_token, language="en", style=None):
    # Production server
    url = "https://mg.mindspringedu.com/api/generate_png"
    # Local development: url = "http://localhost:9527/api/generate_png"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {jwt_token}"  # JWT token authentication
    }
    
    payload = {
        "prompt": prompt,
        "language": language
    }
    
    if style:
        payload["style"] = style
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        with open("generated_graph.png", "wb") as f:
            f.write(response.content)
        return "generated_graph.png"
    else:
        error = response.json()
        raise Exception(f"API Error: {error['error']}")

# First, login to get JWT token
def login(username, password):
    # Production server
    response = requests.post("https://mg.mindspringedu.com/api/auth/login", json={
    # Local development: response = requests.post("http://localhost:9527/api/auth/login", json={
        "username": username,
        "password": password
    })
    return response.json()["access_token"]

# Usage
jwt_token = login("teacher@example.com", "password123")
filename = generate_png_with_jwt("Compare cats and dogs", jwt_token, "en")
print(f"Graph saved as: {filename}")
```

### JavaScript/Node.js Integration

**With API Key Authentication:**
```javascript
const axios = require('axios');
const fs = require('fs');

async function generatePNG(prompt, apiKey, language = 'en', style = null) {
    const payload = { prompt, language };
    if (style) payload.style = style;
    
    // Production server
    const response = await axios.post('https://mg.mindspringedu.com/api/generate_png', payload, {
    // Local development: const response = await axios.post('http://localhost:9527/api/generate_png', payload, {
        headers: {
            'Content-Type': 'application/json',
            'X-API-Key': apiKey  // API Key authentication
        },
        responseType: 'arraybuffer'
    });
    
    fs.writeFileSync('generated_graph.png', response.data);
    return 'generated_graph.png';
}

// Usage
const apiKey = 'mg_wX864RN8F7ZQtuDQU3zfjozR_R45i_-eQp9hYYq6JlQ';  // Your generated API key
generatePNG('Compare cats and dogs', apiKey, 'en', { theme: 'modern' })
    .then(filename => console.log(`Graph saved as: ${filename}`))
    .catch(error => console.error('Error:', error));
```

**With JWT Token Authentication:**
```javascript
const axios = require('axios');
const fs = require('fs');

// First, login to get JWT token
async function login(username, password) {
    // Production server
    const response = await axios.post('https://mg.mindspringedu.com/api/auth/login', {
    // Local development: const response = await axios.post('http://localhost:9527/api/auth/login', {
        username,
        password
    });
    return response.data.access_token;
}

async function generatePNGWithJWT(prompt, jwtToken, language = 'en', style = null) {
    const payload = { prompt, language };
    if (style) payload.style = style;
    
    // Production server
    const response = await axios.post('https://mg.mindspringedu.com/api/generate_png', payload, {
    // Local development: const response = await axios.post('http://localhost:9527/api/generate_png', payload, {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${jwtToken}`  // JWT token authentication
        },
        responseType: 'arraybuffer'
    });
    
    fs.writeFileSync('generated_graph.png', response.data);
    return 'generated_graph.png';
}

// Usage
(async () => {
    const jwtToken = await login('teacher@example.com', 'password123');
    const filename = await generatePNGWithJWT('Compare cats and dogs', jwtToken, 'en');
    console.log(`Graph saved as: ${filename}`);
})();
```

## Supported Visualization Types

MindGraph supports 10 diagram types with intelligent LLM-based classification.

### Smart Classification

The system correctly distinguishes between what users want to **create** vs what the diagram is **about**:

| User Input | Detected Type | Topic | Explanation |
|------------|---------------|--------|-------------|
| `"生成一个关于概念图的思维导图"` | `mind_map` | concept maps | User wants to CREATE a mind map ABOUT concept maps |
| `"生成一个关于思维导图的概念图"` | `concept_map` | mind maps | User wants to CREATE a concept map ABOUT mind maps |
| `"create a bubble map about double bubble maps"` | `bubble_map` | double bubble maps | User wants to CREATE a bubble map ABOUT double bubbles |
| `"compare cats and dogs"` | `double_bubble_map` | cats vs dogs | Comparison intent automatically detected |

### Thinking Maps

| Type | Description | Best For | Example Prompt |
|------|-------------|----------|----------------|
| **Bubble Map** | Central topic with connected attributes | Describing characteristics | "Define artificial intelligence" |
| **Circle Map** | Outer boundary with central topic | Defining topics in context | "What is climate change?" |
| **Double Bubble Map** | Two topics with shared/unique characteristics | Comparing and contrasting | "Compare cats and dogs" |
| **Brace Map** | Whole-to-part relationships | Breaking down concepts | "Parts of a computer" |
| **Flow Map** | Sequence of events | Processes and timelines | "How to make coffee" |
| **Multi-Flow Map** | Cause and effect relationships | Analyzing consequences | "Effects of climate change" |
| **Bridge Map** | Analogical relationships | Showing similarities | "Learning is like building" |

#### Flow Map Enhancements

The Flow Map features optimized layout with adaptive spacing and professional design:

**Key Features:**
- **Adaptive Spacing**: Canvas dimensions automatically adjust to content
- **Smart Positioning**: Substeps positioned first, then main steps align to their groups
- **Professional Design**: Clean, compact layout without sacrificing readability

**Example Flow Map Prompt:**
```json
{
  "prompt": "制作咖啡的流程图",
  "language": "zh"
}
```

### Mind Maps & Concept Maps

| Type | Description | Best For | Example Prompt |
|------|-------------|----------|----------------|
| **Mind Map** | Clockwise branch positioning with smart alignment | Brainstorming and topic exploration | "Create a mind map about climate change" |
| **Concept Map** | Advanced relationship mapping with optimized spacing | Complex concept relationships | "Show relationships in artificial intelligence" |
| **Tree Map** | Hierarchical rectangles for nested data | Organizational structures and hierarchies | "Company organization structure" |

### Diagram Specification Formats

Each diagram type has a specific JSON structure. The API automatically normalizes field names to match renderer expectations.

#### Field Mapping Table

| Diagram Type | API Returns | Renderer Expects | Normalization |
|--------------|-------------|------------------|---------------|
| **bubble_map** | `topic`, `attributes` | `topic`, `attributes` | None needed |
| **circle_map** | `topic`, `context` | `topic`, `context` | `contexts` → `context` (if present) |
| **double_bubble_map** | `left`, `right`, `similarities`, `left_differences`, `right_differences` | `left`, `right`, `similarities`, `left_differences`, `right_differences` | `left_topic` → `left`, `right_topic` → `right` |
| **brace_map** | `topic`, `parts` | `whole`, `parts` | `topic` → `whole` |
| **bridge_map** | `relating_factor`, `analogies` | `relating_factor`, `analogies` | None needed |
| **tree_map** | `topic`, `children` | `topic`, `children` | `categories` → `children` (fallback normalization if present) |
| **flow_map** | `title`, `steps`, `substeps` | `title`, `steps`, `substeps` | None needed |
| **multi_flow_map** | `event`, `causes`, `effects` | `event`, `causes`, `effects` | None needed |
| **mind_map** | `topic`, `children` | `topic`, `children`, `_layout` | Requires `_layout` enhancement (automatic) |
| **concept_map** | `topic`, `concepts`, `relationships` | `topic`, `concepts`, `relationships` | None needed |

#### Detailed Spec Formats

**Bubble Map** (`bubble_map`):
```json
{
  "topic": "Artificial Intelligence",
  "attributes": ["intelligent", "adaptive", "learning", "automated"]
}
```

**Circle Map** (`circle_map`):
```json
{
  "topic": "Climate Change",
  "context": ["global warming", "carbon emissions", "rising sea levels"]
}
```

**Double Bubble Map** (`double_bubble_map`):
```json
{
  "left": "Cats",
  "right": "Dogs",
  "similarities": ["mammals", "pets", "carnivores"],
  "left_differences": ["independent", "nocturnal"],
  "right_differences": ["social", "diurnal"]
}
```

**Brace Map** (`brace_map`):
```json
{
  "whole": "Computer",
  "parts": [
    {"name": "CPU", "subparts": [{"name": "Processor"}, {"name": "Cache"}]},
    {"name": "Memory", "subparts": [{"name": "RAM"}, {"name": "ROM"}]}
  ]
}
```
*Note: API accepts `topic` field which is automatically converted to `whole`*

**Bridge Map** (`bridge_map`):
```json
{
  "relating_factor": "as",
  "analogies": [
    {"left": "Book", "right": "Library", "id": 0},
    {"left": "Song", "right": "Album", "id": 1}
  ]
}
```

**Tree Map** (`tree_map`):
```json
{
  "topic": "Food Categories",
  "children": [
    {"id": "cat-1", "label": "Fruits", "children": [
      {"id": "item-1", "label": "Apple"},
      {"id": "item-2", "label": "Banana"}
    ]},
    {"id": "cat-2", "label": "Vegetables", "children": [
      {"id": "item-3", "label": "Carrot"}
    ]}
  ]
}
```

**Flow Map** (`flow_map`):
```json
{
  "title": "Coffee Making Process",
  "steps": ["Prepare", "Brew", "Serve"],
  "substeps": [
    {"step": "Prepare", "substeps": ["Grind beans", "Heat water"]},
    {"step": "Brew", "substeps": ["Pour water", "Steep"]}
  ]
}
```

**Multi-Flow Map** (`multi_flow_map`):
```json
{
  "event": "Climate Change",
  "causes": ["Carbon emissions", "Deforestation"],
  "effects": ["Rising temperatures", "Sea level rise"]
}
```

**Mind Map** (`mind_map`):
```json
{
  "topic": "Climate Change",
  "children": [
    {
      "id": "branch_1",
      "label": "Causes",
      "children": [
        {"id": "sub_1_1", "label": "Carbon emissions"},
        {"id": "sub_1_2", "label": "Deforestation"}
      ]
    }
  ],
  "_layout": {
    "positions": {...},
    "connections": [...]
  }
}
```
*Note: `_layout` is automatically generated by the API for mind maps*

**Concept Map** (`concept_map`):
```json
{
  "topic": "Artificial Intelligence",
  "concepts": ["Machine Learning", "Neural Networks", "Deep Learning"],
  "relationships": [
    {"from": "Artificial Intelligence", "to": "Machine Learning", "label": "includes"},
    {"from": "Machine Learning", "to": "Neural Networks", "label": "uses"}
  ]
}
```

### Diagram Classification Intelligence

The LLM classification system uses semantic understanding with robust fallback:

1. **Primary**: LLM-based semantic classification using qwen-turbo (1.5s avg)
2. **Fallback**: Intelligent keyword-based detection with priority patterns
3. **Edge Cases**: Handles complex prompts like "生成关于X的Y图" correctly

**Supported Languages**: 
- **English**: Full support with native prompts
- **Chinese**: Complete localization with cultural context understanding

## Error Handling

### HTTP Status Codes

| Code | Description | Common Causes |
|------|-------------|---------------|
| **200** | Success | Request processed successfully |
| **400** | Bad Request | Invalid prompt, missing parameters, or unsupported language |
| **401** | Unauthorized | Missing or invalid authentication (API key or JWT token) |
| **403** | Forbidden | Valid authentication but insufficient permissions |
| **500** | Internal Server Error | Server-side processing error, API service unavailable |

### Error Response Format

```json
{
  "error": "Detailed error description",
  "status": "error",
  "code": "ERROR_CODE",
  "timestamp": "2024-01-01T00:00:00Z",
  "details": {
    "parameter": "Additional error context",
    "suggestion": "How to fix the error"
  }
}
```

## API Quotas

API keys support configurable quotas:

- **Quota Limit**: Set per API key (configurable in admin panel)
- **Usage Tracking**: Automatic usage counting per key
- **Expiration**: Optional expiration dates per key
- **Note**: Internal rate limiting applies to external LLM services (Dashscope)

## Best Practices

### Prompt Engineering

- **Be Specific**: "Compare renewable vs fossil fuel energy sources" vs "energy"
- **Include Context**: "Show monthly sales trends for Q4 2023"
- **Specify Chart Type**: "Create a bar chart comparing sales by region"

### Request Body Optimization

- **Start Simple**: Begin with just the `prompt` field, add complexity as needed
- **Use Defaults**: Leverage automatic defaults for language and styling
- **Minimal Requests**: `{"prompt": "your text"}` works perfectly for most use cases

### Error Handling

- Always check HTTP status codes
- Implement retry logic for 5xx errors
- Provide user-friendly error messages

## Troubleshooting

### Common Issues

1. **PNG Generation Fails**
   - Check Playwright browser installation: `python -m playwright install chromium`
   - Verify system has sufficient memory
   - Check logs for detailed error messages

2. **API Timeout**
   - Increase timeout settings for complex prompts
   - Check network connectivity
   - Verify server performance

3. **Image Quality Issues**
   - Adjust D3.js configuration parameters
   - Use higher resolution settings
   - Check browser compatibility

### Getting Help

- Check application logs in the `logs/` directory
- Check dependencies manually: `pip list`, `node --version`, `npm --version`
- Review error messages for specific guidance
- Check system resources and API service status

---

## Premium Features

### 9. AI Assistant (Streaming)

Interactive AI assistant with streaming responses for guided diagram creation. Uses Server-Sent Events (SSE) for real-time streaming and supports 100+ concurrent connections.

```http
POST /api/ai_assistant/stream
```

**Authentication**: Optional (supports both API key and JWT token) | 可选（支持API密钥和JWT令牌）  
**Content-Type**: `application/json`  
**Response Type**: `text/event-stream` (SSE)

#### Request

**Headers:**
```
Content-Type: application/json
X-API-Key: your_api_key_here          # Option 1: API Key authentication
# OR
Authorization: Bearer your_jwt_token   # Option 2: JWT token authentication
X-Language: en                         # Optional: Language for error messages (en/zh)
```

**Body:**
```json
{
  "message": "Help me create a mind map about climate change",
  "user_id": "user_123",
  "conversation_id": "conv_456"
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | ✅ | User message to AI assistant (1-5000 characters). Use `"start"` to trigger Dify conversation opener |
| `user_id` | string | ✅ | Unique user identifier (1-100 characters) |
| `conversation_id` | string | ❌ | Conversation ID for context continuity. Omit or use `null` for new conversations |

#### Special Message Values

- **`"start"`**: When sent with no `conversation_id`, triggers the Dify conversation opener (greeting message)
- **Regular messages**: Normal conversation messages that will be processed by the AI assistant

#### Response

Returns a stream of Server-Sent Events (SSE) with AI responses in real-time.

**Response Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
Connection: keep-alive
```

**SSE Event Format:**

Each event is sent as:
```
data: {"event": "message", "answer": "chunk text", ...}

```

**Event Types:**

1. **`message`** - Streaming message chunks
   ```json
   {
     "event": "message",
     "answer": "partial text chunk",
     "conversation_id": "conv_456",
     "timestamp": 1642012345678
   }
   ```

2. **`message_end`** - End of message stream
   ```json
   {
     "event": "message_end",
     "conversation_id": "conv_456",
     "timestamp": 1642012345678
   }
   ```

3. **`error`** - Error occurred
   ```json
   {
     "event": "error",
     "error": "Error description",
     "error_type": "ErrorType",
     "message": "User-friendly error message",
     "timestamp": 1642012345678
   }
   ```

#### Example Usage

**JavaScript/TypeScript (EventSource):**
```javascript
const eventSource = new EventSource('/api/ai_assistant/stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your_api_key_here'
  },
  body: JSON.stringify({
    message: 'Help me create a mind map about climate change',
    user_id: 'user_123',
    conversation_id: null
  })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.event === 'message') {
    // Append chunk to UI
    appendToChat(data.answer);
  } else if (data.event === 'message_end') {
    // Message complete
    eventSource.close();
  } else if (data.event === 'error') {
    // Handle error
    showError(data.message || data.error);
    eventSource.close();
  }
};
```

**Python (with requests):**
```python
import requests
import json

def stream_ai_assistant(message, user_id, conversation_id=None, api_key=None):
    url = "http://localhost:9527/api/ai_assistant/stream"
    
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["X-API-Key"] = api_key
    
    payload = {
        "message": message,
        "user_id": user_id,
        "conversation_id": conversation_id
    }
    
    response = requests.post(url, json=payload, headers=headers, stream=True)
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])
                if data.get('event') == 'message':
                    print(data.get('answer', ''), end='', flush=True)
                elif data.get('event') == 'message_end':
                    print('\n[Message complete]')
                    break
                elif data.get('event') == 'error':
                    print(f'\n[Error]: {data.get("message", data.get("error"))}')
                    break

# Usage
stream_ai_assistant(
    "Help me create a mind map about climate change",
    "user_123",
    api_key="mg_wX864RN8F7ZQtuDQU3zfjozR_R45i_-eQp9hYYq6JlQ"
)
```

**Triggering Conversation Opener:**
```json
{
  "message": "start",
  "user_id": "user_123",
  "conversation_id": null
}
```

#### Important Notes

- **SSE Streaming**: Uses Server-Sent Events for real-time streaming responses
- **Concurrent Connections**: Supports 100+ concurrent SSE connections
- **Conversation Context**: Use `conversation_id` to maintain context across multiple messages
- **Error Handling**: Always check for `event: "error"` in the stream
- **Connection Management**: Close EventSource connections when done to free resources
- **Timeout**: Default timeout is 30 seconds (configurable via `DIFY_TIMEOUT` environment variable)

### 10. LLM Monitoring

Monitor LLM performance and health status.

```http
GET /api/llm/metrics
GET /api/llm/health
```

#### `/api/llm/metrics` Response

```json
{
  "total_requests": 1234,
  "average_response_time": 2.45,
  "success_rate": 98.5,
  "active_connections": 12
}
```

#### `/api/llm/health` Response

```json
{
  "status": "healthy",
  "qwen_api": "connected",
  "response_time_ms": 125
}
```

### 11. Frontend Logging

Log frontend events and errors for debugging.

```http
POST /api/frontend_log
POST /api/frontend_log_batch
```

**Note**: These endpoints are for internal frontend telemetry.

## Additional Information

For detailed changelog and version history, see the [CHANGELOG.md](../CHANGELOG.md).

For more information, see the [main documentation](../README.md).
