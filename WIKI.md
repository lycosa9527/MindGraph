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

## 🏗️ Architecture

```
D3.js Dify
├── Frontend (Web Interface)
│   ├── Modern UI with real-time preview
│   ├── Chart customization options
│   └── Export functionality
├── Backend (Flask API)
│   ├── LangChain agent processing
│   ├── D3.js chart generation
│   └── Image export service
├── AI Engine (LangChain)
│   ├── Natural language processing
│   ├── Chart type detection
│   └── Data generation
└── Visualization Engine (D3.js)
    ├── Interactive charts
    ├── Responsive design
    └── Animation system
```

## 🛠️ Configuration

### Environment Variables

```bash
# API Configuration
API_KEY=your_api_key_here
API_BASE_URL=https://api.example.com

# Server Configuration
HOST=0.0.0.0
PORT=9527
DEBUG=True

# Chart Configuration
DEFAULT_THEME=light
CHART_WIDTH=800
CHART_HEIGHT=600
```

### Custom Chart Themes

Create custom themes by modifying the D3.js configuration:

```javascript
const customTheme = {
  colors: ['#ff6b6b', '#4ecdc4', '#45b7d1'],
  background: '#ffffff',
  textColor: '#333333'
};
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

### Production Deployment

```bash
# Production build
docker build -f docker/Dockerfile -t d3-dify-prod docker/

# Run with environment variables
docker run -d \
  -p 9527:9527 \
  -e API_KEY=your_key \
  -e DEBUG=False \
  d3-dify-prod
```

### Docker Configuration

All Docker-related files are organized in the `docker/` folder:
- **Dockerfile** - Main image definition
- **docker-compose.yml** - Multi-service orchestration
- **run-docker.sh** - Linux/macOS deployment script
- **run-docker.bat** - Windows deployment script
- **.dockerignore** - Build context exclusions

See [docker/README.md](docker/README.md) for detailed Docker documentation.

## 📚 Documentation

- **[Agent Guide](docs/AGENT.md)** - LangChain agent functionality
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Installation and deployment
- **[Graph Specs](docs/GRAPH_SPECS.md)** - Custom chart specifications
- **[API Reference](docs/API.md)** - Complete API documentation

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit your changes** (`git commit -m 'Add amazing feature'`)
4. **Push to the branch** (`git push origin feature/amazing-feature`)
5. **Open a Pull Request**

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Run linting
flake8 .
black .
```

## 🐛 Troubleshooting

### Common Issues

**Q: Charts not rendering properly?**
A: Ensure Playwright is installed: `python -m playwright install chromium`

**Q: API requests failing?**
A: Check your API key in the `.env` file and ensure the service is running

**Q: Slow chart generation?**
A: This is normal for complex charts. Consider using the async API for better performance

**Q: Export not working?**
A: Verify that the export directory has write permissions

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **D3.js** - The powerful visualization library
- **LangChain** - The AI framework that powers our agents
- **Flask** - The web framework
- **Playwright** - For headless browser rendering

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/lycosa9527/D3.js_Dify/issues)
- **Discussions**: [GitHub Discussions](https://github.com/lycosa9527/D3.js_Dify/discussions)
- **Documentation**: [Wiki](https://github.com/lycosa9527/D3.js_Dify/wiki)

---

**Made with ❤️ by the D3.js Dify Team**

Transform your data into beautiful visualizations with the power of AI! 🚀 