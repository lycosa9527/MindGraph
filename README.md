# MindGraph - AI-Powered Diagram Generation Platform

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![D3.js](https://img.shields.io/badge/D3.js-7.0+-orange.svg)](https://d3js.org/)
[![License](https://img.shields.io/badge/License-AGPLv3-red.svg)](LICENSE)
[![wakatime](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199.svg)](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199)

## Overview

MindGraph is an AI-powered platform that generates professional diagrams from natural language descriptions. It supports 10 diagram types including Thinking Maps®, Mind Maps, and Concept Maps, powered by advanced LLM technology and D3.js rendering.

## Features

- **Smart Classification**: LLM-based diagram type detection
- **10 Diagram Types**: Complete Thinking Maps® coverage plus Mind Maps and Concept Maps
- **Multi-language**: English and Chinese support
- **API-First**: RESTful endpoints for integrations
- **Export Options**: PNG, SVG, and interactive HTML
- **Production Ready**: Thread-safe, enterprise-grade architecture

## Quick Start

### Prerequisites
- Python 3.8+
- Modern web browser
- Internet connection for LLM API access

### Installation

1. **Clone and Setup**
   ```bash
   git clone https://github.com/lycosa9527/MindGraph.git
   cd MindGraph
   python setup.py
   ```

2. **Configure Environment**
   ```bash
   cp env.example .env
   # Edit .env with your QWEN_API_KEY
   ```

3. **Run Server**
   ```bash
   python run_server.py  # Production server
   # OR
   python app.py         # Development server
   ```

4. **Access Interface**
   - Web UI: `http://localhost:9527/debug`
   - API: `http://localhost:9527/api/generate_graph`

## API Reference

### Core Endpoints

#### Generate Diagram
```http
POST /api/generate_graph
Content-Type: application/json

{
  "prompt": "Compare traditional education vs online learning",
  "language": "en"
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

## Integration Examples

### DingTalk Bot Integration

```python
import requests

def generate_dingtalk_diagram(prompt, language="zh"):
    response = requests.post(
        "http://your-mindgraph-server:9527/api/generate_dingtalk",
        json={"prompt": prompt, "language": language}
    )
    return response.json()

# Example usage
result = generate_dingtalk_diagram("Create a flow map about project management")
if result["success"]:
    markdown = result["markdown"]
    image_url = result["image_url"]
    # Send markdown to DingTalk chat
```

### Python Integration

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

## Supported Diagram Types

### Thinking Maps®
1. **Bubble Map** - Define concepts and characteristics
2. **Circle Map** - Brainstorming and context definition  
3. **Double Bubble Map** - Compare and contrast concepts
4. **Brace Map** - Part-whole relationships
5. **Flow Map** - Processes and sequences
6. **Multi-Flow Map** - Complex multi-process flows
7. **Bridge Map** - Analogies and relationships
8. **Tree Map** - Hierarchical data visualization

### Additional Types
9. **Mind Map** - Clockwise branch positioning
10. **Concept Map** - Advanced relationship mapping

## Architecture

```
agents/
├── main_agent.py              # Orchestrator with LLM classification
├── thinking_maps/             # 7 Thinking Maps agents
├── mind_maps/                 # Mind map agent
├── concept_maps/              # Concept map agent
└── core/                      # Base classes and utilities
```

## Performance

- **Classification**: ~1.5s (qwen-turbo)
- **Generation**: ~3-5s (qwen-plus) 
- **Rendering**: ~0.1-0.2s (D3.js)
- **PNG Export**: ~1-2s (Playwright)

## Deployment

### Production Server
```bash
python run_server.py  # Waitress WSGI server
```

### Environment Variables
```bash
QWEN_API_KEY=your_api_key_here  # Required
PORT=9527                        # Optional
DEBUG=false                      # Optional
```

## Troubleshooting

### Common Issues

**API Key Configuration**
```bash
# Check .env file
cat .env | grep QWEN_API_KEY
```

**Font Rendering**
- Fonts are embedded as base64 data URIs
- No additional font installation required

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

This project is licensed under the AGPLv3 License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for complete version history.
