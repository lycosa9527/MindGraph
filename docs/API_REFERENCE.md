# MindGraph API Reference

## Overview

MindGraph provides a RESTful API for generating AI-powered data visualizations from natural language prompts. The API features an advanced LLM-based classification system that intelligently understands user intent, supports 10 diagram types, and provides both interactive graph generation and direct PNG export.

**Base URL**: `http://localhost:9527` (or your deployed server URL)

**API Version**: 2.5.3  
**Architecture**: Multi-agent system with smart LLM classification and organized module structure

**Key Features**:
- 🧠 **Smart Intent Understanding**: Distinguishes between diagram type to create vs topic content
- 🎯 **10 Diagram Types**: Complete coverage of Thinking Maps®, Mind Maps, and Concept Maps
- 🚀 **High Performance**: Dual-model LLM system (qwen-turbo + qwen-plus)
- 🌍 **Multi-language**: English and Chinese with automatic detection

**Endpoint Compatibility**: Both `/endpoint` and `/api/endpoint` formats are supported for backward compatibility.

## Authentication

Currently, the API uses API key authentication through environment variables:

- **QWEN_API_KEY**: Required for core functionality
- **DEEPSEEK_API_KEY**: Optional for enhanced features

## Endpoints

### 1. PNG Generation (Primary Endpoint)

Generates a PNG image directly from a text prompt.

```http
POST /generate_png
POST /api/generate_png
```

**Note**: Both endpoints are supported for backward compatibility. The `/api/generate_png` endpoint is the primary one.

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

When parameters are omitted, MindGraph automatically applies sensible defaults:

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

Returns a PNG image file that can be:
- Displayed directly in a web browser
- Downloaded and saved locally
- Embedded in documents or presentations

### 2. DingTalk Integration Endpoint

Generates a PNG image for DingTalk platform and returns markdown format with image URL.

```http
POST /generate_dingtalk
POST /api/generate_dingtalk
```

**Note**: Both endpoints are supported for backward compatibility. The `/api/generate_dingtalk` endpoint is the primary one.

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

Returns JSON with markdown format and image URL:

```json
{
  "success": true,
  "markdown": "![Compare cats and dogs](http://localhost:9527/api/temp_images/dingtalk_a1b2c3d4_1692812345.png)",
  "image_url": "http://localhost:9527/api/temp_images/dingtalk_a1b2c3d4_1692812345.png",
  "filename": "dingtalk_a1b2c3d4_1692812345.png",
  "prompt": "Compare cats and dogs",
  "language": "zh",
  "graph_type": "bubble_map",
  "timing": {
    "llm_time": 2.456,
    "render_time": 1.234,
    "total_time": 3.690
  }
}
```

#### Important Notes

- **Temporary Storage**: Images are stored in temporary storage and automatically cleaned up after 24 hours
- **Image Access**: Images are served through the `/api/temp_images/<filename>` endpoint
- **Automatic Cleanup**: The system automatically removes expired images every 24 hours
- **No Persistence**: Images are not permanently stored and will be lost after the cleanup period

#### Usage in DingTalk

The `markdown` field can be directly used in DingTalk markdown messages:

```java
// Example DingTalk integration
OapiRobotSendRequest.Markdown markdown = new OapiRobotSendRequest.Markdown();
markdown.setTitle("MindGraph Generated");
markdown.setText("@" + userId + "  \n  " + response.getMarkdown());
```

### 3. Style Update Endpoint

#### Clear Cache Endpoint

Clears the modular JavaScript cache for development and debugging purposes.

```http
POST /api/clear_cache
```

**Note**: This endpoint is primarily for development use to clear cached JavaScript modules.

#### Request

**Headers:**
```
Content-Type: application/json
```

**Body:** Empty (no body required)

#### Response

**Success (200):**
```json
{
  "status": "success",
  "message": "Cache cleared successfully"
}
```

**Error (500):**
```json
{
  "status": "error",
  "message": "Error description"
}
```

#### Use Cases

- **Development**: Clear cache when making changes to JavaScript modules
- **Debugging**: Reset cache state when troubleshooting rendering issues
- **Testing**: Ensure fresh module loading for testing scenarios
  "status": "error",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Example Usage

```bash
# Basic PNG generation (minimal request - uses all defaults)
# Both endpoints work:
curl -X POST http://localhost:9527/generate_png \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare cats and dogs"}' \
  --output comparison.png

# Or use the primary API endpoint:
curl -X POST http://localhost:9527/api/generate_png \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare cats and dogs"}' \
  --output comparison.png

# With language specification
curl -X POST http://localhost:9527/generate_png \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare cats and dogs", "language": "zh"}' \
  --output comparison_zh.png

# With custom styling
curl -X POST http://localhost:9527/generate_png \
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

#### Request Body Examples (From Simple to Complex)

**Level 1: Minimal (Just Prompt)**
```json
{
  "prompt": "Compare cats and dogs"
}
```
✅ **Works perfectly** - Uses all defaults

**Level 2: With Language**
```json
{
  "prompt": "Compare cats and dogs",
  "language": "zh"
}
```
✅ **Works perfectly** - Uses default styling

**Level 3: With Basic Style**
```json
{
  "prompt": "Compare cats and dogs",
  "style": {
    "theme": "classic"
  }
}
```
✅ **Works perfectly** - Overrides theme, keeps other defaults

**Level 4: Full Customization**
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
✅ **Full control** - Overrides all defaults

#### What NOT to Do

**❌ Invalid Requests**
```json
{
  "prompt": ""  // Empty prompt - will fail
}
```

```json
{
  "prompt": "Compare cats and dogs",
  "language": "fr"  // Unsupported language - will fail
}
```

```json
{
  "prompt": "Compare cats and dogs",
  "style": {
    "theme": "invalid_theme"  // Invalid theme - will use default
  }
}
```

#### Best Practices for Request Bodies

- **For Quick Testing**: Use minimal request with just `prompt`
- **For Production**: Include language detection and consistent theming
- **For Dify Integration**: `{"prompt": "{{user_input}}"}` works perfectly
- **Progressive Enhancement**: Start simple, add complexity as needed

### 2. Interactive Graph Generation

Generates an interactive D3.js visualization with JSON data.

```http
POST /generate_graph
POST /api/generate_graph
```

**Note**: Both endpoints are supported for backward compatibility. The `/api/generate_graph` endpoint is the primary one.

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

### 3. Health Check

Returns application status and version information.

```http
GET /status
```

#### Response

```json
{
  "status": "healthy",
  "version": "2.4.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "services": {
    "qwen_api": "connected",
    "deepseek_api": "not_configured",
    "playwright": "ready"
  },
  "system": {
    "python_version": "3.13.5",
    "memory_usage": "45.2MB",
    "uptime": "2h 15m"
  }
}
```

## Integration Examples

### 🔗 Dify Integration (Complete Guide)

MindGraph provides seamless integration with Dify through HTTP POST requests. This guide covers all scenarios from basic to advanced usage.

#### 1. Basic HTTP Request Node Setup

**Step 1: Create HTTP Request Node**
- **URL**: `http://your-mindgraph-server:9527/api/generate_png`
- **Method**: `POST`
- **Headers**: 
  ```json
  {
    "Content-Type": "application/json"
  }
  ```

**Step 2: Basic Request Body**
```json
{
  "prompt": "{{user_input}}"
}
```
✅ **This works perfectly** - Uses automatic language detection and default styling

#### 2. Advanced Configuration Options

**Option A: With Language Detection**
```json
{
  "prompt": "{{user_input}}",
  "language": "{{#if contains user_input '中文'}}zh{{else}}en{{/if}}"
}
```

**Option B: With Custom Styling**
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

**Option C: Full Customization**
```json
{
  "prompt": "{{user_input}}",
  "language": "{{language_var}}",
  "style": {
    "theme": "{{theme_preference}}",
    "colors": {
      "primary": "{{primary_color}}",
      "secondary": "{{secondary_color}}"
    }
  }
}
```

#### 3. Response Handling in Dify

**For PNG Images (Binary Response)**:
- The response is a binary PNG image
- Can be directly displayed or saved
- Use Dify's image handling capabilities

**For Interactive Diagrams (use `/api/generate_graph`)**:
```json
{
  "prompt": "{{user_input}}",
  "language": "en"
}
```

Response structure:
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

#### 4. Error Handling in Dify

**Configure Error Response Handling**:
```javascript
// In Dify's response processing
if (response.status !== 200) {
  return {
    error: "Failed to generate diagram",
    details: response.error || "Unknown error occurred",
    suggestion: "Please try rephrasing your request"
  };
}
```

**Common Error Scenarios**:
- **Empty Prompt**: `{"error": "Prompt cannot be empty"}`
- **Invalid Language**: `{"error": "Language 'fr' not supported"}`
- **API Timeout**: `{"error": "Request timeout"}`

#### 5. Dify Workflow Examples

**Example 1: Simple Diagram Generator**
```
[User Input] → [HTTP Request to MindGraph] → [Display PNG]
```

**Example 2: Educational Assistant**
```
[User Question] → [Classify Intent] → [Generate Educational Diagram] → [Return with Explanation]
```

**Example 3: Business Process Mapper** 
```
[Process Description] → [Extract Steps] → [Generate Flow Map] → [Export for Documentation]
```

#### 6. Best Practices for Dify Integration

**Performance Optimization**:
- Use `/api/generate_png` for final images
- Use `/api/generate_graph` for interactive content
- Cache responses when possible
- Set appropriate timeouts (10-15 seconds)

**User Experience**:
- Show loading indicators during generation
- Provide fallback messages for errors
- Allow users to regenerate with different parameters

**Production Considerations**:
- Use environment variables for server URLs
- Implement retry logic for failed requests
- Monitor API usage and response times
- Consider rate limiting for high-traffic scenarios

### Python Integration

```python
import requests
import json

def generate_png(prompt, language="en", style=None):
    url = "http://localhost:9527/generate_png"
    
    payload = {
        "prompt": prompt,
        "language": language
    }
    
    if style:
        payload["style"] = style
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        # Save PNG to file
        with open("generated_graph.png", "wb") as f:
            f.write(response.content)
        return "generated_graph.png"
    else:
        error = response.json()
        raise Exception(f"API Error: {error['error']}")

# Usage
try:
    filename = generate_png(
        prompt="Compare cats and dogs",
        language="en",
        style={"theme": "modern"}
    )
    print(f"Graph saved as: {filename}")
except Exception as e:
    print(f"Error: {e}")
```

### JavaScript/Node.js Integration

```javascript
const axios = require('axios');
const fs = require('fs');

async function generatePNG(prompt, language = 'en', style = null) {
    try {
        const payload = {
            prompt: prompt,
            language: language
        };
        
        if (style) {
            payload.style = style;
        }
        
        const response = await axios.post('http://localhost:9527/generate_png', payload, {
            responseType: 'arraybuffer',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        // Save PNG to file
        fs.writeFileSync('generated_graph.png', response.data);
        return 'generated_graph.png';
        
    } catch (error) {
        console.error('API Error:', error.response?.data || error.message);
        throw error;
    }
}

// Usage
generatePNG('Compare cats and dogs', 'en', { theme: 'modern' })
    .then(filename => console.log(`Graph saved as: ${filename}`))
    .catch(error => console.error('Error:', error));
```

## Supported Visualization Types

MindGraph supports 10 diagram types with intelligent LLM-based classification that understands user intent vs topic content.

### 🧠 Smart Classification Examples

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

#### 🚀 Flow Map Enhancements (v2.3.9)

The Flow Map has received major improvements for optimal visual presentation:

**Ultra-Compact Layout Features:**
- **Revolutionary Positioning**: Substep-first algorithm eliminates all overlapping issues
- **Adaptive Spacing**: Canvas dimensions automatically adjust to content
- **75% Title Spacing Reduction**: Minimal spacing around topic text for maximum content density
- **Professional Design**: Clean, compact layout without sacrificing readability

**Enhanced Flow Map Structure:**
- **Main Steps**: Sequential process steps positioned vertically
- **Substeps**: Sub-processes connected to main steps with L-shaped connectors
- **Adaptive Canvas**: Automatically sized to fit all content perfectly
- **Smart Positioning**: Substeps positioned first, then main steps align to their groups

**Example Flow Map Prompt:**
```json
{
  "prompt": "制作咖啡的流程图",
  "language": "zh"
}
```

**Flow Map JSON Structure:**
```json
{
  "title": "制作咖啡",
  "steps": ["准备材料", "加热水", "冲泡", "享用"],
  "substeps": [
    {"step": "准备材料", "substeps": ["咖啡豆", "过滤纸", "咖啡杯"]},
    {"step": "加热水", "substeps": ["烧开水", "调节温度"]},
    {"step": "冲泡", "substeps": ["湿润过滤纸", "倒入咖啡粉", "缓慢注水"]},
    {"step": "享用", "substeps": ["品尝", "清洗器具"]}
  ]
}
```

### Mind Maps & Concept Maps

| Type | Description | Best For | Example Prompt |
|------|-------------|----------|----------------|
| **Mind Map** | Clockwise branch positioning with smart alignment | Brainstorming and topic exploration | "Create a mind map about climate change" |
| **Concept Map** | Advanced relationship mapping with optimized spacing | Complex concept relationships | "Show relationships in artificial intelligence" |
| **Tree Map** | Hierarchical rectangles for nested data | Organizational structures and hierarchies | "Company organization structure" |

### 🎯 Diagram Classification Intelligence

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

### Common Error Scenarios

1. **Invalid Prompt**
   ```json
   {
     "error": "Prompt is too short or contains invalid characters",
     "code": "INVALID_PROMPT",
     "suggestion": "Use descriptive prompts with at least 3 words"
   }
   ```

2. **Unsupported Language**
   ```json
   {
     "error": "Language 'fr' is not supported",
     "code": "UNSUPPORTED_LANGUAGE",
     "suggestion": "Use 'en' for English or 'zh' for Chinese"
   }
   ```

3. **API Service Unavailable**
   ```json
   {
     "error": "Qwen API service is currently unavailable",
     "code": "API_UNAVAILABLE",
     "suggestion": "Check your API key and try again later"
   }
   ```

## Rate Limiting

The API implements rate limiting to ensure fair usage:

- **Default Limit**: 100 requests per minute per IP
- **Burst Limit**: 10 requests per second
- **Headers**: Rate limit information is included in response headers

### Rate Limit Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Best Practices

### 1. Prompt Engineering

- **Be Specific**: "Compare renewable vs fossil fuel energy sources" vs "energy"
- **Include Context**: "Show monthly sales trends for Q4 2023"
- **Specify Chart Type**: "Create a bar chart comparing sales by region"

### 2. Request Body Optimization

- **Start Simple**: Begin with just the `prompt` field, add complexity as needed
- **Use Defaults**: Leverage automatic defaults for language and styling
- **Minimal Requests**: `{"prompt": "your text"}` works perfectly for most use cases
- **Progressive Enhancement**: Add language and style options for specific requirements

### 3. Error Handling

- Always check HTTP status codes
- Implement retry logic for 5xx errors
- Provide user-friendly error messages

### 4. Performance Optimization

- Cache generated images when possible
- Use appropriate image formats (PNG for quality, JPEG for size)
- Implement client-side caching headers

### 5. Security Considerations

- Validate all input parameters
- Implement proper authentication
- Use HTTPS in production
- Sanitize user prompts

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

## Changelog

### Version 2.5.3
- **Agent File Organization**: ✅ **COMPLETED** - Organized agents into clean module structure for 20% development efficiency improvement
- Added `/api/clear_cache` endpoint for development workflow
- Fixed flow map rendering with professional substep positioning
- Enhanced modular JavaScript system integration
- Improved watermark styling consistency across diagram types

### Version 2.4.0
- Added comprehensive API documentation
- Enhanced error handling and response formats
- Improved rate limiting implementation
- Added style customization options

### Version 2.3.8
- Added PNG generation endpoint
- Enhanced D3.js visualization support
- Improved multi-language support
- Added health check endpoint

---

For more information, see the [main documentation](../README.md).
