# MindGraph API Reference

## Overview

MindGraph provides a RESTful API for generating AI-powered data visualizations from natural language prompts. The API features intelligent LLM-based classification, supports 10 diagram types, and provides both interactive graph generation and direct PNG export.

**Base URL**: `http://localhost:9527` (or your deployed server URL)  
**API Version**: 4.9.1  
**Architecture**: Multi-agent system with smart LLM classification

**Key Features**:
- **Smart Classification**: LLM-based diagram type detection
- **10 Diagram Types**: Complete Thinking Maps®, Mind Maps, and Concept Maps coverage
- **High Performance**: Dual-model LLM system (qwen-turbo + qwen-plus)
- **Multi-language**: English and Chinese support

**Endpoint Compatibility**: Both `/endpoint` and `/api/endpoint` formats are supported.

## Authentication

The API uses API key authentication through environment variables:

- **QWEN_API_KEY**: Required for core functionality
- **DEEPSEEK_API_KEY**: Optional for enhanced features

## Endpoints

### 1. PNG Generation

Generates a PNG image directly from a text prompt.

```http
POST /api/generate_png
POST /generate_png
```

**Note**: Both endpoints are supported for backward compatibility.

#### Request

**Headers:**
```
Content-Type: application/json
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

**Note**: Both endpoints are supported for backward compatibility.

#### Request

**Headers:**
```
Content-Type: application/json
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

![](http://localhost:9527/api/temp_images/dingtalk_a1b2c3d4_1692812345.png)
```

**Response Format**: The endpoint returns raw plain text (not JSON) containing markdown image syntax with an empty alt text field. This format is optimized for direct use in DingTalk messages.

**Example Response**:
```
![](http://92.168.8.210:9527/api/temp_images/dingtalk_346703f0_1760217144.png)
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

**Note**: Both endpoints are supported for backward compatibility.

#### Request

**Headers:**
```
Content-Type: application/json
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

### 5. Health Check

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
  "version": "4.9.1"  // Dynamic: reads from VERSION file
}
```

**`/status` Response (with metrics):**
```json
{
  "status": "running",
  "framework": "FastAPI",
  "version": "4.9.1",  // Dynamic: reads from VERSION file
  "uptime_seconds": 3600.5,
  "memory_percent": 45.2,
  "timestamp": 1642012345.678
}
```

## Integration Examples

### Dify Integration

MindGraph provides seamless integration with Dify through HTTP POST requests.

#### Basic Setup

**HTTP Request Node Configuration:**
- **URL**: `http://your-mindgraph-server:9527/api/generate_png`
- **Method**: `POST`
- **Headers**: `Content-Type: application/json`

**Request Body:**
```json
{
  "prompt": "{{user_input}}"
}
```

#### Advanced Configuration

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

#### Response Handling

**For PNG Images**: The response is a binary PNG image that can be directly displayed or saved.

**For Interactive Diagrams** (use `/api/generate_graph`):
```json
{
  "success": true,
  "data": {
    "html": "<div class='mindgraph-container'>...</div>",
    "graph_type": "mind_map",
    "dimensions": { "width": 1200, "height": 800 }
  },
  "timing": { "total_time": 3.42 }
}
```

### Python Integration

```python
import requests

def generate_png(prompt, language="en", style=None):
    url = "http://localhost:9527/api/generate_png"
    
    payload = {
        "prompt": prompt,
        "language": language
    }
    
    if style:
        payload["style"] = style
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        with open("generated_graph.png", "wb") as f:
            f.write(response.content)
        return "generated_graph.png"
    else:
        error = response.json()
        raise Exception(f"API Error: {error['error']}")

# Usage
filename = generate_png("Compare cats and dogs", "en", {"theme": "modern"})
print(f"Graph saved as: {filename}")
```

### JavaScript/Node.js Integration

```javascript
const axios = require('axios');
const fs = require('fs');

async function generatePNG(prompt, language = 'en', style = null) {
    const payload = { prompt, language };
    if (style) payload.style = style;
    
    const response = await axios.post('http://localhost:9527/api/generate_png', payload, {
        responseType: 'arraybuffer',
        headers: { 'Content-Type': 'application/json' }
    });
    
    fs.writeFileSync('generated_graph.png', response.data);
    return 'generated_graph.png';
}

// Usage
generatePNG('Compare cats and dogs', 'en', { theme: 'modern' })
    .then(filename => console.log(`Graph saved as: ${filename}`))
    .catch(error => console.error('Error:', error));
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

### Thinking Maps (Complete Coverage)

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
| **401** | Unauthorized | Missing or invalid API key |
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

## Rate Limiting

The API implements rate limiting to ensure fair usage:

- **Default Limit**: 100 requests per minute per IP
- **Burst Limit**: 10 requests per second
- **Headers**: Rate limit information is included in response headers

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

### 6. AI Assistant (Streaming)

Interactive AI assistant with streaming responses for guided diagram creation.

```http
POST /api/ai_assistant/stream
```

**Note**: This endpoint uses Server-Sent Events (SSE) for real-time streaming.

#### Request

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "prompt": "Help me create a mind map about climate change",
  "session_id": "uuid-v4-string",
  "language": "en"
}
```

#### Response

Returns a stream of Server-Sent Events (SSE) with AI responses.

### 7. LLM Monitoring

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

### 8. Frontend Logging

Log frontend events and errors for debugging.

```http
POST /api/frontend_log
POST /api/frontend_log_batch
```

**Note**: These endpoints are for internal frontend telemetry.

## Changelog

### Version 4.9.1 (Current)
- **Mobile Label Alignment Fix**: Fixed vertical alignment of "Nodes:" and "Tools:" labels
- Labels now perfectly centered with buttons on all screen sizes

### Version 4.9.0
- **Mobile Toolbar Optimization**: Improved mobile UI with 3-row compact layout
- Enhanced button sizing and alignment for mobile devices
- Removed collapsible toggles for cleaner interface
- All diagram buttons always visible on mobile

### Version 4.8.1
- **Critical Bug Fix**: Fixed duplicate variable declaration in bubble-map-renderer.js
- Resolved canvas display issues affecting circle, bubble, and double bubble maps

### Version 4.8.0
- **Configurable AI Assistant**: Added `AI_ASSISTANT_NAME` environment variable
- Dynamic branding across toolbar, panel, and welcome messages
- Support for custom AI assistant naming

### Version 4.7.0
- **Circle Map Background Fix**: Added consistent grey background to PNG exports
- All diagram types now have uniform background styling

### Version 4.6.9
- **DingTalk Integration**: Updated markdown format to `![]()` with empty alt text
- Cleaner DingTalk messages without duplicate prompt text

### Version 4.6.8
- **PNG Export Quality**: Fixed missing watermarks and improved dimension handling
- Dynamic container resizing for accurate exports
- Functional scale parameter for quality control

---

For more information, see the [main documentation](../README.md).
