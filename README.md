# MindGraph - AI-Powered Diagram Generation Platform

[![Version](https://img.shields.io/badge/version-2.5.3-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![D3.js](https://img.shields.io/badge/D3.js-7.0+-orange.svg)](https://d3js.org/)
[![License](https://img.shields.io/badge/License-AGPLv3-red.svg)](LICENSE)
[![wakatime](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199.svg)](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199)

## 🎯 Overview

**MindGraph** is an enterprise-grade AI platform that transforms natural language descriptions into interactive, professional diagrams. Powered by advanced LLM technology and D3.js rendering, it supports 10 diagram types with intelligent classification and semantic understanding.

### ✨ Key Features

- **🤖 Smart LLM Classification**: Advanced semantic understanding distinguishes user intent from content topics
- **🧠 10 Diagram Types**: Complete coverage of Thinking Maps®, Mind Maps, Concept Maps, and more
- **🎨 Professional Rendering**: D3.js-powered interactive visualizations with modern themes
- **🌍 Multi-language Support**: English and Chinese with intelligent language detection
- **🔗 API-First Design**: RESTful APIs perfect for integrations (Dify, DingTalk, custom apps)
- **⚡ High Performance**: Dual-model LLM system with 70% performance improvement
- **📱 Export Options**: PNG, SVG, and interactive HTML formats
- **🛡️ Production Ready**: Thread-safe, enterprise-grade architecture

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Modern web browser
- Internet connection for LLM API access

### Installation

1. **Clone and Setup**
   ```bash
   git clone https://github.com/lycosa9527/MindGraph.git
   cd MindGraph
   python setup.py  # Automated setup with progress tracking
   ```

2. **Configure Environment**
   ```bash
   cp env.example .env
   # Edit .env with your configuration:
   # QWEN_API_KEY=your_api_key_here
   ```

3. **Run the Server**
   ```bash
   python run_server.py  # Production server (Waitress)
   # OR
   python app.py  # Development server
   ```

4. **Access the Interface**
   - Web UI: `http://localhost:9527/debug`
   - API Endpoint: `http://localhost:9527/api/generate_graph`

## 📊 Supported Diagram Types

### 🧠 Thinking Maps® (Complete Coverage)
1. **Bubble Map** - Define concepts and characteristics
2. **Circle Map** - Brainstorming and context definition  
3. **Double Bubble Map** - Compare and contrast concepts
4. **Brace Map** - Part-whole relationships and hierarchies
5. **Flow Map** - Processes and sequences
6. **Multi-Flow Map** - Complex multi-process flows
7. **Bridge Map** - Analogies and relationships

### 🌳 Mind Maps & Concept Maps
8. **Mind Map** - Clockwise branch positioning with smart alignment
9. **Concept Map** - Advanced relationship mapping with optimized spacing
10. **Tree Map** - Hierarchical data visualization

## 🔌 API Reference

### Core Endpoints

#### Generate Diagram
```http
POST /api/generate_graph
Content-Type: application/json

{
  "prompt": "Compare traditional education vs online learning",
  "language": "en"  // Optional: "en" or "zh", auto-detected if not provided
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "html": "<div class='mindgraph-container'>...</div>",
    "graph_type": "double_bubble_map",
    "dimensions": {
      "width": 1200,
      "height": 800
    }
  },
  "timing": {
    "llm_time": 2.45,
    "render_time": 0.12,
    "total_time": 2.57
  }
}
```

#### Generate PNG Image
```http
POST /api/generate_png
Content-Type: application/json

{
  "prompt": "Create a mind map about artificial intelligence",
  "language": "zh"
}
```

**Response:** Binary PNG image data

#### DingTalk Integration
```http
POST /api/generate_dingtalk
Content-Type: application/json

{
  "prompt": "Show the workflow of software development",
  "language": "zh"
}
```

**Response:**
```json
{
  "success": true,
  "markdown": "![Software Development Workflow](http://localhost:9527/api/temp_images/dingtalk_abc123_1692812345.png)",
  "image_url": "http://localhost:9527/api/temp_images/dingtalk_abc123_1692812345.png",
  "graph_type": "flow_map",
  "timing": {
    "total_time": 3.42
  }
}
```

## 🔗 Integration Guides

### Dify Integration

MindGraph provides seamless integration with Dify through HTTP POST requests:

#### 1. Setup Dify HTTP Request Node

```json
{
  "method": "POST",
  "url": "http://your-mindgraph-server:9527/api/generate_graph",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "prompt": "{{user_input}}",
    "language": "{{language}}"
  }
}
```

#### 2. Process Response in Dify

```javascript
// Extract diagram HTML from response
const diagramHtml = response.data.html;
const diagramType = response.data.graph_type;
const timing = response.timing.total_time;

// Return formatted response
return {
  diagram: diagramHtml,
  type: diagramType,
  generation_time: timing
};
```

#### 3. For PNG Images

```json
{
  "method": "POST", 
  "url": "http://your-mindgraph-server:9527/api/generate_png",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "prompt": "{{user_input}}",
    "language": "{{language}}"
  }
}
```

#### 4. Error Handling

```javascript
// Handle API errors gracefully
if (!response.success) {
  return {
    error: response.error || "Failed to generate diagram",
    error_type: response.error_type || "unknown_error"
  };
}
```

### DingTalk Integration

For DingTalk bots and applications:

```java
// Java example for DingTalk integration
String apiUrl = "http://your-mindgraph-server:9527/api/generate_dingtalk";
String requestBody = "{\"prompt\":\"" + userPrompt + "\",\"language\":\"zh\"}";

// Make HTTP request
HttpResponse response = httpClient.post(apiUrl, requestBody);
JSONObject result = new JSONObject(response.getBody());

// Send markdown to DingTalk
if (result.getBoolean("success")) {
    String markdown = result.getString("markdown");
    
    OapiRobotSendRequest.Markdown markdownMsg = new OapiRobotSendRequest.Markdown();
    markdownMsg.setTitle("MindGraph Generated Diagram");
    markdownMsg.setText(markdown);
    
    // Send to DingTalk
    client.execute(markdownMsg);
}
```

### Custom Applications

#### Python Integration
```python
import requests

def generate_diagram(prompt, language="en"):
    response = requests.post(
        "http://localhost:9527/api/generate_graph",
        json={"prompt": prompt, "language": language}
    )
    return response.json()

# Example usage
result = generate_diagram("Create a bubble map about machine learning")
if result["success"]:
    html_content = result["data"]["html"]
    diagram_type = result["data"]["graph_type"]
```

#### JavaScript/Node.js Integration
```javascript
async function generateDiagram(prompt, language = "en") {
  const response = await fetch("http://localhost:9527/api/generate_graph", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, language })
  });
  
  return await response.json();
}

// Example usage
const result = await generateDiagram("Compare cats and dogs");
if (result.success) {
  document.getElementById("diagram").innerHTML = result.data.html;
}
```

## 🧠 Smart Classification System

MindGraph features an advanced LLM-based classification system that understands user intent:

### Intent vs Content Understanding

The system correctly distinguishes between what users want to **create** vs what the diagram is **about**:

- ✅ `"生成一个关于概念图的思维导图"` → Creates **mind_map** about concept maps
- ✅ `"生成一个关于思维导图的概念图"` → Creates **concept_map** about mind maps  
- ✅ `"create a bubble map about double bubble maps"` → Creates **bubble_map** about double bubbles

### Supported Patterns

| Input Pattern | Detected Type | Topic |
|---------------|---------------|-------|
| `"生成...的X图"` | X图 | Content after "关于" |
| `"create a X map about..."` | X map | Content after "about" |
| `"compare A and B"` | double_bubble_map | A vs B |
| `"define X"` | bubble_map | X |

## 🏗️ Architecture

### Multi-Agent System
```
agents/
├── main_agent.py              # Orchestrator with LLM classification
├── thinking_maps/             # 7 Thinking Maps agents
├── mind_maps/                 # Mind map agent with clockwise positioning  
├── concept_maps/              # Concept map agent with relationship mapping
└── core/                      # Base classes and utilities
```

### LLM System
- **qwen-turbo**: Fast classification and topic extraction (1.5s avg)
- **qwen-plus**: High-quality diagram generation (3-5s avg)
- **Thread-safe**: Concurrent request handling with timing stats

### Rendering Pipeline
1. **Input Processing**: Language detection and validation
2. **Classification**: LLM-based diagram type detection  
3. **Generation**: Specialized agent creates diagram specification
4. **Rendering**: D3.js converts to interactive visualization
5. **Export**: PNG/SVG generation via headless browser

## 🎨 Customization

### Theme Configuration
```javascript
const customTheme = {
  background: '#ffffff',
  primaryColor: '#1976d2', 
  fontSize: 14,
  fontFamily: 'Inter, sans-serif',
  borderRadius: 4,
  strokeWidth: 2
};

// Apply via API
fetch('/api/update_style', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(customTheme)
});
```

### Available Themes
- **Light**: Clean, professional appearance
- **Dark**: Modern dark mode with high contrast
- **Custom**: Fully customizable colors and typography

## ⚡ Performance

### Current Optimizations
- **LLM Dual-Model System**: 70% performance improvement
- **Browser Context Pooling**: 23% faster rendering  
- **Smart Caching**: Reduced redundant API calls
- **Optimized Algorithms**: Faster layout calculations

### Benchmarks
- **Classification**: ~1.5s (qwen-turbo)
- **Generation**: ~3-5s (qwen-plus) 
- **Rendering**: ~0.1-0.2s (D3.js)
- **PNG Export**: ~1-2s (Playwright)

## 🛠️ Deployment

### Production Server
```bash
# Waitress WSGI server (recommended)
python run_server.py

# Configuration in waitress.conf.py
```

### Environment Variables
```bash
# Required
QWEN_API_KEY=your_api_key_here

# Optional
PORT=9527
DEBUG=false
LOG_LEVEL=INFO
```

### Docker Support
Docker configuration will be added in future releases.

## 🔍 Troubleshooting

### Common Issues

**API Key Configuration**
```bash
# Check .env file
cat .env | grep QWEN_API_KEY

# Verify API key validity
curl -H "Authorization: Bearer $QWEN_API_KEY" https://dashscope.aliyuncs.com/api/v1/models
```

**Font Rendering on Ubuntu**
- ✅ **FIXED**: Fonts are embedded as base64 data URIs
- No additional font installation required

**Memory Issues**
- Use `python run_server.py` for production
- Monitor memory with complex diagrams
- Consider reducing diagram complexity for large datasets

## 📈 Changelog

### Version 2.5.3 (Current)
- ✅ **Smart LLM Classification**: Advanced intent vs content understanding
- ✅ **Centralized Prompt System**: All prompts managed in dedicated modules
- ✅ **Thread-Safe Architecture**: Production-ready concurrent handling
- ✅ **Enhanced Error Handling**: Standardized error responses with context
- ✅ **Input Validation**: Comprehensive prompt and parameter validation
- ✅ **Enterprise Logging**: Dedicated agent logging with proper isolation

### Previous Versions
See [CHANGELOG.md](CHANGELOG.md) for complete version history.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 📄 License

This project is licensed under the AGPLv3 License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Qwen Team**: Advanced LLM models (qwen-turbo, qwen-plus)
- **D3.js Community**: Powerful visualization framework
- **Open Source Contributors**: Making this project possible

---

**MindGraph** - Enterprise AI diagram generation platform. Transform ideas into professional visualizations. 🚀
