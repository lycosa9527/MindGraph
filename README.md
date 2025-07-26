# D3.js Dify - AI-Powered Data Visualization Generator

[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![D3.js](https://img.shields.io/badge/D3.js-7.0+-orange.svg)](https://d3js.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 What is D3.js Dify?

**D3.js Dify** is an intelligent data visualization platform that automatically generates interactive charts and graphs from natural language descriptions. Powered by AI (LangChain agents) and D3.js, it transforms your ideas into beautiful, interactive visualizations in seconds.

### ✨ Key Features

- **🤖 AI-Powered**: Uses LangChain agents to understand your requests and generate appropriate chart types
- **📊 Multiple Chart Types**: Supports bar charts, line charts, pie charts, scatter plots, and more
- **🌐 Interactive**: Fully interactive D3.js visualizations with hover effects, animations, and zoom
- **🎨 Beautiful Design**: Modern, responsive UI with customizable themes
- **📱 Export Options**: Export charts as PNG images or interactive HTML
- **🌍 Multi-language**: Supports both English and Chinese
- **⚡ Real-time**: Instant chart generation with live preview
- **🔧 Developer Friendly**: RESTful API, Docker support, and comprehensive documentation

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
   pip install playwright
   python -m playwright install chromium
   ```

4. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your API keys and configuration
   ```

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

**Made with ❤️ by the D3.js Dify Team**

Transform your data into beautiful visualizations with the power of AI! 🚀