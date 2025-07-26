# D3.js Dify - AI-Powered Data Visualization Generator

[![Version](https://img.shields.io/badge/version-2.2.0-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![D3.js](https://img.shields.io/badge/D3.js-7.0+-orange.svg)](https://d3js.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 What is D3.js Dify?

**D3.js Dify** is an intelligent data visualization platform that automatically generates interactive charts and graphs from natural language descriptions. Powered by AI (LangChain agents) and D3.js, it transforms your ideas into beautiful, interactive visualizations in seconds.

### ✨ Key Features

- **🤖 AI-Powered**: Uses LangChain agents (Qwen & DeepSeek) to understand your requests and generate appropriate chart types
- **🧠 Educational Focus**: DeepSeek agent specializes in Thinking Maps® and educational diagram generation
- **📊 Multiple Chart Types**: Supports Thinking Maps® (Bubble Maps, Circle Maps, Double Bubble Maps, Bridge Maps), concept maps, mind maps, and traditional charts
- **🌐 Interactive**: Fully interactive D3.js visualizations with hover effects, animations, and zoom
- **🎨 Beautiful Design**: Modern, responsive UI with customizable themes
- **📱 Export Options**: Export charts as PNG images or interactive HTML
- **🌍 Multi-language**: Supports both English and Chinese
- **⚡ Real-time**: Instant chart generation with live preview
- **🔧 Developer Friendly**: RESTful API, Docker support, and comprehensive documentation
- **🛡️ Robust Validation**: Comprehensive dependency validation and professional startup sequence
- **🚀 Production Ready**: Enhanced error handling, logging, and monitoring capabilities

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Node.js (for D3.js components)
- Modern web browser

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/lycosa9527/D3.js_Dify.git
   cd D3.js_Dify
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright for browser rendering**
   ```bash
   python -m playwright install chromium
   ```

4. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your API keys and configuration
   ```
   
   **Required Configuration:**
   - `QWEN_API_KEY` - Required for core functionality
   
   **Optional Configuration:**
   - `DEEPSEEK_API_KEY` - Optional for enhanced features and development phase
   - If DeepSeek is not configured, the application will run using Qwen as default

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Open your browser**
   Navigate to `http://localhost:9527` to access the web interface.

## 🎨 How It Works

### 1. Natural Language Input
Simply describe what you want to visualize:
- "Compare sales performance between Q1 and Q2"
- "Show the distribution of customer ages"
- "Create a timeline of project milestones"

### 2. AI Analysis
The LangChain agent:
- Analyzes your request
- Determines the best chart type
- Extracts relevant data characteristics
- Generates appropriate sample data

### 3. Chart Generation
D3.js creates an interactive visualization with:
- Responsive design
- Smooth animations
- Interactive tooltips
- Zoom and pan capabilities

### 4. Export & Share
Export your charts as:
- Interactive HTML files
- High-resolution PNG images
- Embeddable code snippets

## 📊 Supported Chart Types

### 🧠 Thinking Maps® (Educational Diagrams)

| Chart Type | Description | Best For |
|------------|-------------|----------|
| **Bubble Map** | Central topic with connected attributes | Describing characteristics of a single topic |
| **Circle Map** | Outer boundary with central topic and perimeter context | Defining topics in context |
| **Double Bubble Map** | Two topics with shared and unique characteristics | Comparing and contrasting two topics |
| **Bridge Map** | Analogical relationships with relating factors | Showing analogies and similarities |

### 📈 Traditional Charts

| Chart Type | Description | Best For |
|------------|-------------|----------|
| **Bar Chart** | Vertical or horizontal bars | Comparing categories |
| **Line Chart** | Connected data points | Trends over time |
| **Pie Chart** | Circular segments | Proportions and percentages |
| **Scatter Plot** | Points on X-Y axes | Correlations and distributions |
| **Area Chart** | Filled areas under lines | Cumulative data over time |
| **Heatmap** | Color-coded grid | Matrix data visualization |
| **Tree Map** | Nested rectangles | Hierarchical data |
| **Network Graph** | Connected nodes | Relationships and connections |

## 🧠 DeepSeek Agent - Development Phase Tool

The DeepSeek agent is a **development phase tool** that generates enhanced prompt templates for educational diagrams. It is designed to be used by **developers during development** to create better, more focused prompts that can be saved and used with the Qwen agent in production.

### Architecture

```
Development Phase:
User Request → DeepSeek Agent → Development Prompt Template → Save to File

Production Phase:
User Request → Qwen Agent → D3.js JSON (default)
User Request → DeepSeek+Qwen → Enhanced JSON (optional)
```

### Key Features

- **🎯 Development Phase Tool**: Used during development, not in production
- **📝 Prompt Template Generator**: Creates enhanced prompts for educational context
- **💾 File Management**: Saves prompt templates to `development_prompts/` directory
- **🧠 Educational Focus**: Specializes in Thinking Maps® and educational diagram generation
- **🔄 Optional Choice**: Users can choose between Qwen (default) and DeepSeek+Qwen

### Thinking Maps® Supported

1. **Circle Map** - Define topics in context
2. **Bubble Map** - Describe attributes and characteristics  
3. **Double Bubble Map** - Compare and contrast two topics
4. **Tree Map** - Categorize and classify information
5. **Brace Map** - Show whole/part relationships
6. **Flow Map** - Sequence events and processes
7. **Multi-Flow Map** - Analyze cause and effect relationships
8. **Bridge Map** - Show analogies and similarities

### Usage Examples

#### Development Phase (for developers)

```bash
# Generate development prompt template
curl -X POST http://localhost:9527/generate_development_prompt \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Compare cats and dogs",
    "language": "en",
    "save_to_file": true
  }'
```

#### Production Phase (default - Qwen only)

```bash
# Use Qwen as default agent
curl -X POST http://localhost:9527/generate_graph \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Compare cats and dogs",
    "language": "zh"
  }'
```

#### Production Phase (optional - DeepSeek + Qwen)

```bash
# Use DeepSeek for enhancement + Qwen for JSON
curl -X POST http://localhost:9527/generate_graph_deepseek \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Compare cats and dogs",
    "language": "en"
  }'
```

### Development Prompt Template Example

**Generated Template**:
```markdown
# Development Phase Prompt Template Generator
## Diagram Type: double_bubble_map
## Generated: 2024-12-01 14:30:22

This prompt template is designed for the development phase to generate high-quality educational diagrams.
Developers can save this template and use it with the Qwen agent in production.

# Double Bubble Map - Development Phase Prompt Template

## Original User Request
Compare cats and dogs

## Educational Goal
Through comparative analysis, help students understand the commonalities and differences between two topics, developing critical thinking.

## Enhanced Requirements
- Generate 5 common characteristics (shared by both) - use 2-4 words, avoid complete sentences
- Generate 5 unique characteristics for topic 1 - use 2-4 words, avoid complete sentences
- Generate 5 unique characteristics for topic 2 - use 2-4 words, avoid complete sentences
- Ensure differences are comparable - each difference should represent the same type of attribute
- Use concise keywords, focus on core, essential differences
- Cover diverse dimensions (geographic, economic, cultural, physical, temporal, etc.)
- Highly abstract and condensed, maintain conciseness

## Output Format
{
  "left": "topic1",
  "right": "topic2",
  "similarities": ["feature1", "feature2", "feature3", "feature4", "feature5"],
  "left_differences": ["trait1", "trait2", "trait3", "trait4", "trait5"],
  "right_differences": ["trait1", "trait2", "trait3", "trait4", "trait5"]
}

## Usage Instructions
This prompt template is designed for the development phase to generate high-quality educational double bubble maps.
Please ensure the JSON format is correct, do not include any code block markers.
```

For detailed documentation, see [DeepSeek Agent Guide](docs/DEEPSEEK_AGENT.md).

## ⚙️ Configuration

### Environment Variables

The application uses environment variables for configuration. Copy `env.example` to `.env` and configure:

#### Required (Core Functionality)
- `QWEN_API_KEY` - Your Qwen API key (required for all features)

#### Optional (Enhanced Features)
- `DEEPSEEK_API_KEY` - Your DeepSeek API key (optional, for development phase)
- `DEEPSEEK_API_URL` - DeepSeek API endpoint (defaults to official endpoint)
- `DEEPSEEK_MODEL` - DeepSeek model name (defaults to `deepseek-chat`)

#### Application Settings
- `HOST` - Flask host (default: `0.0.0.0`)
- `PORT` - Flask port (default: `9527`)
- `DEBUG` - Debug mode (default: `False`)
- `GRAPH_LANGUAGE` - Default language (default: `zh`)

### Configuration Validation

The application validates configuration on startup:

- ✅ **Qwen API**: Required for core functionality
- ⚠️ **DeepSeek API**: Optional, application runs without it
- ✅ **Numeric Settings**: Validates ranges and formats
- ✅ **D3.js Theme**: Validates color formats and dimensions

### Startup Behavior

- If Qwen is not configured: ❌ Application will not start
- If DeepSeek is not configured: ✅ Application starts with Qwen as default
- Configuration summary is displayed on startup

## 🔧 API Usage

### Generate Chart from Text

```bash
curl -X POST http://localhost:9527/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Compare sales performance between Q1 and Q2",
    "language": "en"
  }'
```

### Export as PNG

```bash
curl -X POST http://localhost:9527/api/generate_png \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Show monthly revenue trends",
    "language": "en"
  }'
```

## 🐳 Docker Deployment

### Quick Docker Setup

```bash
# Build and run with Docker Compose
docker-compose -f docker/docker-compose.yml up -d

# Or build manually
docker build -t d3-dify docker/
docker run -p 9527:9527 d3-dify

# Or use the convenience scripts
# Linux/macOS
./docker/run-docker.sh

# Windows
docker\run-docker.bat
```

## 📚 Documentation

- **[Agent Guide](docs/AGENT.md)** - LangChain agent functionality
- **[DeepSeek Agent Guide](docs/DEEPSEEK_AGENT.md)** - Educational diagram generation
- **[Thinking Maps Guide](docs/THINKING_MAPS_GUIDE.md)** - Thinking Maps® methodology
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Installation and deployment
- **[Graph Specs](docs/GRAPH_SPECS.md)** - Custom chart specifications
- **[Complete Wiki](WIKI.md)** - Comprehensive project documentation

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit your changes** (`git commit -m 'Add amazing feature'`)
4. **Push to the branch** (`git push origin feature/amazing-feature`)
5. **Open a Pull Request**

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/lycosa9527/D3.js_Dify/issues)
- **Discussions**: [GitHub Discussions](https://github.com/lycosa9527/D3.js_Dify/discussions)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Made with ❤️ by the MindSpring Team**

Transform your data into beautiful visualizations with the power of AI! 🚀