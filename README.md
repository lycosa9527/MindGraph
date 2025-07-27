# MindGraph - AI-Powered Data Visualization Generator

[![Version](https://img.shields.io/badge/version-2.3.1-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![D3.js](https://img.shields.io/badge/D3.js-7.0+-orange.svg)](https://d3js.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![WakaTime](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69.svg)](https://wakatime.com/@60ba0518-3829-457f-ae10-3eff184d5f69)

## 🎯 What is MindGraph?

**MindGraph** is an intelligent data visualization platform that automatically generates interactive charts and graphs from natural language descriptions. Powered by AI and D3.js, it transforms your ideas into beautiful, interactive visualizations in seconds.

### ✨ Key Features

- **🤖 AI-Powered**: Uses AI to understand your requests and generate appropriate chart types
- **🧠 Educational Focus**: Specializes in Thinking Maps® and educational diagram generation
- **📊 Multiple Chart Types**: Supports Thinking Maps® (Bubble Maps, Circle Maps, Double Bubble Maps, Bridge Maps), concept maps, mind maps, and traditional charts
- **🌐 Interactive**: Fully interactive D3.js visualizations with hover effects, animations, and zoom
- **🎨 Beautiful Design**: Modern, responsive UI with customizable themes
- **📱 Export Options**: Export charts as PNG images or interactive HTML
- **🌍 Multi-language**: Supports both English and Chinese
- **⚡ Real-time**: Instant chart generation with live preview

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Node.js (for D3.js components)
- Modern web browser

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/lycosa9527/MindGraph.git
   cd MindGraph
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your API keys and configuration
   ```
   
   **Required Configuration:**
   - `QWEN_API_KEY` - Required for core functionality

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:9527/debug` to access the web interface.

## 🎨 How It Works

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
- Smooth animations
- Interactive tooltips
- Zoom and pan capabilities

### 4. Export & Share
Export your charts as:
- Interactive HTML files
- High-resolution PNG images

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

## 🎨 Example Prompts

Try these prompts to get started:

- "Compare cats and dogs"
- "Define artificial intelligence"
- "Show the relationship between cause and effect"
- "Create a mind map about climate change"
- "Compare traditional and modern education"

## 🔧 API Usage

### Generate Chart from Text

```bash
curl -X POST http://localhost:9527/generate_graph \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Compare cats and dogs",
    "language": "en"
  }'
```

### Export as PNG

```bash
curl -X POST http://localhost:9527/generate_png \
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
cd docker
docker-compose up -d

# Or build manually
docker build -t mindgraph .
docker run -p 9527:9527 mindgraph
```

## 📚 Documentation

- **[Quick Start Guide](docs/QUICK_START.md)** - Get up and running in minutes
- **[Thinking Maps Guide](docs/THINKING_MAPS_GUIDE.md)** - Learn about Thinking Maps®
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment instructions
- **[Complete Documentation](docs/README.md)** - Full documentation index

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit your changes** (`git commit -m 'Add amazing feature'`)
4. **Push to the branch** (`git push origin feature/amazing-feature`)
5. **Open a Pull Request**

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/lycosa9527/MindGraph/issues)
- **Discussions**: [GitHub Discussions](https://github.com/lycosa9527/MindGraph/discussions)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Made with ❤️ by the MindSpring Team**

Transform your ideas into beautiful visualizations with the power of AI! 🚀