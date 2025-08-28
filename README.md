# MindGraph - AI-Powered Data Visualization Generator

[![Version](https://img.shields.io/badge/version-2.5.3-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![D3.js](https://img.shields.io/badge/D3.js-7.0+-orange.svg)](https://d3js.org/)
[![License](https://img.shields.io/badge/License-AGPLv3-red.svg)](LICENSE)
[![WakaTime](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199.svg)](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199)

## 🎯 What is MindGraph?

**MindGraph** is an intelligent data visualization platform that automatically generates interactive charts and graphs from natural language descriptions. Powered by AI and D3.js, it transforms your ideas into beautiful, interactive visualizations in seconds.

### ✨ Key Features

- **🤖 AI-Powered**: Understands natural language and selects the best diagram type automatically
- **🏗️ Multi-Agent Architecture**: 6 specialized agents working together for optimal results
- **🧠 Complete Diagram System**: All core diagram types are now fully developed and production-ready
- **🎨 Advanced Theming**: Modern themes via centralized style manager with easy customization
- **🌐 Interactive**: Smooth D3.js interactions (hover, zoom/pan) and instant style updates
- **📱 Export Options**: PNG export and shareable interactive HTML
- **🔗 DingTalk Integration**: Special endpoint for DingTalk platform with markdown format and image URLs
- **🌍 Multi-language**: English and Chinese support
- **⚡ Real-time**: Instant preview and fast PNG generation

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Modern web browser
- Internet connection (for initial setup)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/lycosa9527/MindGraph.git
   cd MindGraph
   ```

2. **🚀 Run the automated setup (Recommended)**
   ```bash
   python setup.py
   ```
   
   This will automatically:
   - ✅ Install all Python dependencies
   - ✅ Set up Playwright with Chromium browser
   - ✅ Configure the logging system
   - ✅ Verify everything is working correctly
   
   **Note**: The setup script is smart and will skip steps that are already complete!

3. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your API keys and configuration
   ```
   
   **Required Configuration:**
   - `QWEN_API_KEY` - Required for core functionality

4. **Run the application**
   
   **Production (Recommended):**
   ```bash
   python run_server.py
   ```
   
   **Development:**
   ```bash
   python app.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:9527/debug` to access the web interface.

### Alternative Manual Installation

If you prefer manual installation or encounter issues with the automated setup:

1. **Install Python dependencies manually**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Playwright browser manually**
   ```bash
   # Install Playwright Python package (if not already installed)
   pip install playwright
   
   # Install Chromium browser
   playwright install chromium
   
   # On Linux/macOS, also install system dependencies
   playwright install-deps
   ```

3. **Continue with steps 3-5 above**

## 🔗 DingTalk Integration

MindGraph provides a special endpoint specifically designed for DingTalk platform integration. Unlike the regular PNG endpoint that returns binary image data, the DingTalk endpoint returns markdown format with image URLs.

### DingTalk Endpoint

```http
POST /api/generate_dingtalk
POST /generate_dingtalk  # Backward compatibility
```

### Request Example

```json
{
  "prompt": "Compare traditional education vs online learning",
  "language": "zh"
}
```

### Response Format

```json
{
  "success": true,
  "markdown": "![Compare traditional education vs online learning](http://localhost:9527/api/temp_images/dingtalk_a1b2c3d4_1692812345.png)",
  "image_url": "http://localhost:9527/api/temp_images/dingtalk_a1b2c3d4_1692812345.png",
  "filename": "dingtalk_a1b2c3d4_1692812345.png",
  "prompt": "Compare traditional education vs online learning",
  "language": "zh",
  "graph_type": "bubble_map",
  "timing": {
    "llm_time": 2.456,
    "render_time": 1.234,
    "total_time": 3.690
  }
}
```

### Usage in DingTalk

The `markdown` field can be directly used in DingTalk markdown messages:

```java
// Example DingTalk integration
OapiRobotSendRequest.Markdown markdown = new OapiRobotSendRequest.Markdown();
markdown.setTitle("MindGraph Generated");
markdown.setText("@" + userId + "  \n  " + response.getMarkdown());
```

### Key Benefits

- **Markdown Ready**: Returns formatted markdown that works directly in DingTalk
- **Image URLs**: Provides accessible image URLs instead of binary data
- **Temporary Storage**: Images are automatically cleaned up after 24 hours
- **Automatic Cleanup**: Built-in cleanup mechanism every 24 hours
- **Performance Tracking**: Includes detailed timing information
- **Backward Compatible**: Both `/api/generate_dingtalk` and `/generate_dingtalk` work

## 🖥️ Server Configuration

MindGraph now uses **Waitress** as the primary WSGI server for both development and production:

- **Cross-platform compatibility**: Works on Windows, macOS, and Linux
- **Ubuntu Server Support**: Full font compatibility with embedded Inter fonts for consistent rendering
- **Production-ready**: Handles concurrent requests efficiently
- **Simple configuration**: Single configuration file (`waitress.conf.py`)
- **No complex setup**: Just run `python run_server.py`

### Server Options

- **Waitress (Production)**: `python run_server.py` - Uses Waitress with optimized settings
- **Flask Dev**: `python app.py` - Development server with auto-reload
- **Docker**: Docker support removed - will be added back later

## 🎨 Supported Diagram Types

### 🧠 Thinking Maps® (Complete Coverage)
- **Bubble Map**: For defining concepts and their characteristics
- **Circle Map**: For brainstorming and defining in context
- **Double Bubble Map**: For comparing and contrasting concepts
- **Brace Map**: For part-whole relationships and hierarchies
- **Flow Map**: For processes and sequences with professional substep rendering
- **Multi-Flow Map**: For complex processes with multiple flows
- **Bridge Map**: For analogies and relationships

### 🌳 Mind Maps (Enhanced with Clockwise Positioning)
- **Revolutionary Clockwise System**: Branches distributed in perfect clockwise order
- **Smart Branch Alignment**: Branch 2 and 5 automatically align with central topic
- **Perfect Left/Right Balance**: Even distribution between left and right sides
- **Children-First Positioning**: Maintains proven positioning system
- **Scalable Layout**: Works perfectly for 4, 6, 8, 10+ branches

### 🔗 Concept Maps
- **Radial Layout**: Optimized spacing with larger starting radius
- **Enhanced Readability**: Improved font sizes and text wrapping
- **Professional Appearance**: Clean, organized layouts suitable for business use

### 📊 Traditional Charts
- **Tree Maps**: Hierarchical data visualization with rectangle nodes
- **Flow Charts**: Process visualization with step-by-step flow
- **Custom Visualizations**: AI-generated charts based on your descriptions

## 🏗️ Architecture Overview

### Multi-Agent System
MindGraph uses a sophisticated multi-agent architecture where specialized agents handle different aspects of diagram generation:

#### ✅ **Agent File Organization Completed** 
The agent system is now fully organized with clean module structure:

```
agents/
├── __init__.py                    # Main agent registry and imports
├── core/                          # Core agent functionality
│   ├── base_agent.py             # Base agent class
│   └── agent_utils.py            # Shared agent utilities
├── thinking_maps/                 # Thinking Maps agents
│   ├── brace_map_agent.py        # Hierarchical relationships
│   ├── flow_map_agent.py         # Process and sequence visualization
│   ├── multi_flow_map_agent.py   # Complex multi-process flows
│   ├── tree_map_agent.py         # Hierarchical tree structures
│   ├── bubble_map_agent.py       # Concept definitions
│   ├── circle_map_agent.py       # Brainstorming and context
│   ├── double_bubble_map_agent.py # Comparison and contrast
│   └── bridge_map_agent.py       # Analogies and relationships
├── concept_maps/                  # Concept Map agents
│   └── concept_map_agent.py      # Advanced concept relationship mapping
├── mind_maps/                     # Mind Map agents
│   └── mind_map_agent.py         # Clockwise branch positioning
└── main_agent.py                  # Main agent orchestrator
```

#### **LLM System**
1. **Dual-Model LLM System**: 
   - **qwen-turbo**: Fast classification and topic extraction
   - **qwen-plus**: High-quality diagram generation and content creation

### Core Components
- **Flask Web Server**: RESTful API and web interface
- **D3.js Renderer**: Interactive visualization engine
- **Style Manager**: Centralized theming and customization
- **Memory System**: User preference tracking and learning

## 🎯 How It Works

### 1. Natural Language Input
Simply describe what you want to visualize:
- "Compare cats and dogs"
- "Define artificial intelligence"
- "Show the relationship between cause and effect"
- "Create a mind map about climate change"

### 2. AI Analysis
The AI:
- Analyzes your request
- Determines the best chart type
- Extracts relevant data characteristics
- Generates appropriate sample data

### 3. Chart Generation
D3.js creates an interactive visualization with:
- Responsive design
- Interactive elements
- Professional styling
- Export capabilities

## 🔧 API Reference

### Main Endpoints

#### Generate Diagram
```http
POST /api/generate_graph
Content-Type: application/json

{
  "prompt": "Create a mind map about artificial intelligence",
  "language": "en"
}
```

#### Generate PNG
```http
POST /api/generate_png
Content-Type: application/json

{
  "prompt": "Create a mind map about artificial intelligence",
  "language": "en"
}
```

#### Style Management
```http
POST /api/update_style
Content-Type: application/json

{
  "theme": "dark",
  "primary_color": "#1976d2",
  "font_size": 14
}
```

### Response Format
```json
{
  "success": true,
  "data": {
    "html": "<div>...</div>",
    "dimensions": {
      "width": 1200,
      "height": 800
    },
    "metadata": {
      "diagram_type": "mindmap",
      "algorithm": "clean_vertical_stack"
    }
  }
}
```

## 🎨 Customization & Theming

### Style Manager
MindGraph includes a powerful style manager that allows you to:
- Change color themes (light/dark)
- Customize primary colors
- Adjust font sizes and families
- Modify border radius and stroke widths
- Apply custom CSS overrides

### Theme Configuration
```javascript
// Example theme configuration
const theme = {
  background: '#ffffff',
  primaryColor: '#1976d2',
  fontSize: 14,
  fontFamily: 'Inter, sans-serif',
  borderRadius: 4,
  strokeWidth: 2
};
```

## 🚀 Automated Setup Features

### What `setup.py` Does

The automated setup script (`setup.py`) provides a professional, one-command installation experience:

- **🧠 Smart Setup**: Automatically detects and skips already installed components
- **🌐 Cross-Platform**: Works seamlessly on Windows, macOS, and Linux
- **📦 Dependency Management**: Installs all required Python packages automatically
- **🌍 Browser Setup**: Installs Playwright with Chromium browser (~150MB)
- **🔧 System Dependencies**: Automatically installs fonts, libraries, and system packages on Linux/macOS
- **📊 Progress Tracking**: Real-time progress bars with download speeds
- **✅ Verification**: Comprehensive system verification after installation
- **📝 Logging**: Sets up complete logging system automatically
- **⚡ Performance**: Optimized for fast execution (typically 3-5 seconds)

### Setup Process

1. **Environment Validation** - Checks Python version, pip availability, and system info
2. **Python Dependencies** - Installs all required packages from `requirements.txt`
3. **Playwright Browser** - Downloads and configures Chromium browser
4. **Logging System** - Creates log directories and files with proper permissions
5. **System Verification** - Verifies all components are working correctly

### Troubleshooting Setup

If you encounter issues with the automated setup:

- **Permission Errors**: On Linux/macOS, try `sudo python setup.py`
- **Network Issues**: Ensure stable internet connection for package downloads
- **Python Version**: Verify you have Python 3.8+ installed
- **Manual Fallback**: Use the alternative manual installation steps above

## 🚀 Performance & Optimization

### Current Optimization Status
- **✅ LLM API Performance**: **COMPLETED** - Dual-model system implemented
- **✅ Browser Context Pooling**: **COMPLETED** - BrowserContext pool implemented (23% improvement)
- **✅ Agent File Organization**: **COMPLETED** - Clean module structure implemented (20% improvement)
- **🔄 PNG Generation Fix**: **NEXT PRIORITY** - Enable context pooling + remove unnecessary waits (47.1% improvement)
- **🔄 Theme System**: **PLANNED** - Consolidation and standardization (30% improvement)

### Recent Performance Improvements
- **LLM API Optimization**: ✅ **COMPLETED** - Dual-model system with 70% performance improvement
  - qwen-turbo for fast classification (1.5s vs 3.59s)
  - qwen-plus for high-quality generation (12s vs 17.45s)
- **Bridge Map Rendering**: Fixed layout issues and styling inconsistencies
- **Code Quality**: Comprehensive cleanup with production-ready codebase
- **Local Font System**: Eliminated external CDN dependencies for offline operation
- **Browser Context Pooling**: ✅ **COMPLETED** - BrowserContext pool implemented (23% improvement for SVG)

### Rendering Performance
- **Optimized Algorithms**: Streamlined positioning and layout calculations
- **Memory Efficiency**: Better resource usage in complex operations
- **Fast Generation**: Quick diagram creation even for complex layouts

### Canvas Optimization
- **Content-Based Sizing**: Canvas dimensions calculated from actual content
- **Adaptive Spacing**: Intelligent spacing that responds to content complexity
- **Zero Overlapping**: Advanced algorithms prevent element conflicts

## 🔍 Troubleshooting

### Common Issues

#### API Key Configuration
- Ensure `QWEN_API_KEY` is set in your `.env` file
- Check API key validity and quota limits

#### Rendering Issues
- Clear browser cache and refresh
- Check browser console for JavaScript errors
- Verify D3.js is loading correctly

#### Ubuntu Server Font Issues
- **Problem**: Mindmaps showing grey background with no text on Ubuntu servers
- **Solution**: ✅ **FIXED** - Fonts are now embedded as base64 data URIs in generated HTML
- **Result**: Consistent rendering across Windows, macOS, and Ubuntu environments
- **Note**: Server restart required after applying font fixes

#### Performance Issues
- Use minimal installation for production
- Monitor memory usage for large diagrams
- Consider reducing diagram complexity

### Getting Help
- Check the [CHANGELOG.md](CHANGELOG.md) for recent updates
- Review browser console for error messages
- Ensure all dependencies are properly installed

## 📈 Version History

### Version 2.5.3 (Current)
- **🚀 Automated Setup System**: ✅ **COMPLETED** - Professional `setup.py` script for one-command installation
- **Ubuntu Server Compatibility**: ✅ **COMPLETED** - Font embedding fix for consistent cross-platform rendering
- **Browser Context Pooling**: ✅ **COMPLETED** - BrowserContext pool implemented (23% improvement for SVG)
- **LLM API Performance**: ✅ **COMPLETED** - Dual-model system with 70% performance improvement
- **Complete Diagram System**: All core diagram types finished and fully optimized
- **Bridge Map Rendering**: Completely fixed with correct horizontal layout and styling
- **Code Quality**: Comprehensive cleanup with production-ready codebase
- **Local Font System**: Offline operation with embedded Inter font family
- **Production Ready**: Enterprise-grade system suitable for business use
- **Enhanced Performance**: Optimized algorithms and improved stability

### Version 2.5.2
- **LLM API Performance**: ✅ **COMPLETED** - Dual-model system with 70% performance improvement
- **Complete Diagram System**: All core diagram types finished and fully optimized
- **Bridge Map Rendering**: Completely fixed with correct horizontal layout and styling
- **Code Quality**: Comprehensive cleanup with production-ready codebase
- **Local Font System**: Offline operation with embedded Inter font family
- **Production Ready**: Enterprise-grade system suitable for business use
- **Enhanced Performance**: Optimized algorithms and improved stability

### Previous Versions
See [CHANGELOG.md](CHANGELOG.md) for complete version history and detailed change logs.

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines and code of conduct.

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the AGPLv3 License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **D3.js Community**: For the amazing visualization library
- **Qwen Team**: For powerful AI models (qwen-turbo and qwen-plus)
- **Open Source Contributors**: For making this project possible

## 📞 Support

- **Documentation**: This README and [CHANGELOG.md](CHANGELOG.md)
- **Issues**: Report bugs and feature requests via GitHub Issues
- **Discussions**: Join community discussions on GitHub

---

**MindGraph** - Transforming ideas into beautiful visualizations, one prompt at a time. 🚀