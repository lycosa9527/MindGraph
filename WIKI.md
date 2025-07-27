# MindGraph - AI-Powered Data Visualization Generator

[![Version](https://img.shields.io/badge/version-2.3.1-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![D3.js](https://img.shields.io/badge/D3.js-7.0+-orange.svg)](https://d3js.org/)
[![License](https://img.shields.io/badge/License-AGPLv3-red.svg)](LICENSE)
[![WakaTime](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/MindGraph.svg)](https://wakatime.com/@60ba0518-3829-457f-ae10-3eff184d5f69/projects/MindGraph)

## 🎯 What is MindGraph?

**MindGraph** is an intelligent data visualization API and plugin solution designed specifically for workflow platforms like Dify, Coze, Zapier, and other automation tools. It automatically generates interactive charts and graphs from natural language descriptions, making it easy to add visual content to your AI workflows and chatbots. Powered by AI and D3.js, it transforms text prompts into beautiful, interactive visualizations that can be seamlessly integrated into your applications.

### ✨ Key Features

- **🔌 API-First Design**: Built as a RESTful API for easy integration with workflow platforms
- **🤖 AI-Powered**: Uses AI to understand your requests and generate appropriate chart types
- **🧠 Educational Focus**: Specializes in Thinking Maps® and educational diagram generation
- **📊 Multiple Chart Types**: Supports Thinking Maps® (Bubble Maps, Circle Maps, Double Bubble Maps, Bridge Maps), concept maps, mind maps, and traditional charts
- **🌐 Interactive**: Fully interactive D3.js visualizations with hover effects, animations, and zoom
- **🎨 Beautiful Design**: Modern, responsive UI with customizable themes
- **📱 Export Options**: Export charts as PNG images or interactive HTML
- **🌍 Multi-language**: Supports both English and Chinese
- **⚡ Real-time**: Instant chart generation with live preview
- **🔗 Workflow Integration**: Optimized for Dify, Coze, Zapier, Make, and other automation platforms

### 🆕 What's New in Version 2.3.1

- **🔧 Enhanced Bridge Maps**: Improved visual clarity with cleaner presentation
- **🎯 Better User Experience**: Enhanced interface and performance
- **⚡ Automatic Setup**: No manual configuration required

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

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:9527/debug` to access the web interface.

## 🛠️ Using the Debug Interface

The debug interface is your primary tool for testing and exploring MindGraph's capabilities before integrating it into your workflow platforms. Here's how to use it effectively:

### 📍 Accessing the Debug Interface

After launching the application, visit: `http://localhost:9527/debug`

### 🎯 Step-by-Step Example

Let's walk through a complete example of generating a diagram:

#### Step 1: Enter Your Prompt
In the debug interface, you'll see a text input field. Try this example:
```
Compare traditional education and online learning
```

#### Step 2: Select Language
Choose your preferred language (English or Chinese) from the dropdown.

#### Step 3: Generate the Diagram
Click the "Generate" button. The system will:
- Analyze your prompt using AI
- Determine the best chart type (likely a Double Bubble Map for comparison)
- Generate the interactive visualization

#### Step 4: View the Results
You'll see:
- **Interactive Diagram**: A fully interactive D3.js visualization
- **Chart Type**: The AI-selected visualization type
- **Generated Data**: The structured data used to create the diagram

#### Step 5: Export Options
- **Download PNG**: Click to save a high-resolution image
- **View JSON**: See the raw data structure
- **Regenerate**: Try different variations

### 🎨 Example Prompts to Try

Here are some tested prompts that work well with MindGraph:

#### Educational Comparisons
```
Compare cats and dogs
```
*Result: Double Bubble Map showing similarities and differences*

```
Compare traditional and modern education methods
```
*Result: Double Bubble Map with detailed educational comparisons*

#### Concept Definitions
```
Define artificial intelligence
```
*Result: Bubble Map with AI characteristics and applications*

```
Explain the concept of climate change
```
*Result: Circle Map with central topic and surrounding context*

#### Process and Relationships
```
Show the relationship between cause and effect
```
*Result: Bridge Map showing analogical relationships*

```
Create a mind map about renewable energy
```
*Result: Network Graph showing interconnected concepts*

#### Business and Data
```
Show quarterly sales performance trends
```
*Result: Line Chart with time-series data*

```
Compare features of different software platforms
```
*Result: Bar Chart comparing platform capabilities*

### 🔍 Understanding the Output

#### Interactive Features
- **Hover Effects**: Move your mouse over elements to see details
- **Zoom**: Use mouse wheel or pinch gestures to zoom in/out
- **Pan**: Click and drag to move around the diagram
- **Tooltips**: Detailed information appears on hover

#### Chart Types Explained
- **Double Bubble Map**: Perfect for comparing two concepts
- **Bubble Map**: Great for describing characteristics of a single topic
- **Circle Map**: Ideal for defining topics in context
- **Bridge Map**: Excellent for showing analogies and relationships
- **Network Graph**: Best for complex interconnected concepts

### 📸 PNG Export Feature

The debug interface includes a powerful PNG export feature:

1. **Generate your diagram** using any prompt
2. **Click "Download PNG"** button
3. **High-resolution image** is automatically downloaded
4. **Perfect for**: Presentations, documents, social media, embedding in workflow platforms, or API responses

#### PNG Export Example
```
Prompt: "Compare traditional and online education"
↓
Interactive Double Bubble Map
↓
Click "Download PNG"
↓
High-resolution image saved to your computer
```

### 🔧 Debug Interface Tips

#### For Best Results:
- **Be Specific**: "Compare cats and dogs" works better than "animals"
- **Use Clear Language**: Simple, direct descriptions work best
- **Try Variations**: If one prompt doesn't work, try rephrasing
- **Check Language**: Ensure you've selected the correct language

#### Troubleshooting:
- **No Response**: Check if the application is running on the correct port
- **Slow Generation**: Complex prompts may take a few seconds
- **Wrong Chart Type**: Try rephrasing your prompt to be more specific
- **Export Issues**: Ensure your browser allows downloads

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

### 4. API Response & Integration
The system returns:
- **JSON specification** for interactive visualizations (via `/generate_graph`)
- **PNG image data** for immediate use in workflows (via `/generate_png`)
- **Ready for integration** with Dify, Coze, Zapier, and other platforms

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

## 🔧 API Usage

MindGraph is designed as a RESTful API for seamless integration with workflow platforms. Here are the core endpoints:

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

## 🔌 Workflow Platform Integration

### 🤖 Dify Integration
Add visual diagram generation to your AI workflows and chatbots:
- Use the `/generate_graph` endpoint to create interactive visualizations
- Use the `/generate_png` endpoint for static images in chat responses
- Perfect for educational content, business analysis, and concept explanations

### ⚡ Coze Integration
Enhance your bot responses with dynamic visual content:
- Generate diagrams based on user queries
- Export PNG images for immediate sharing
- Support for both English and Chinese prompts

### 🔗 Zapier Integration
Automate diagram creation in your business processes:
- Connect to your existing workflows
- Generate visual content automatically
- Export images for reports and presentations

### 🔄 Make Integration
Integrate visual generation into your automation scenarios:
- Create diagrams as part of your workflow
- Use generated images in subsequent steps
- Perfect for content creation automation

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

**Q: Debug interface not loading?**
A: Make sure you're accessing `http://localhost:9527/debug` (not just the root URL)

**Q: PNG export fails?**
A: Check browser download settings and ensure the application has proper permissions

**Q: Integration with workflow platforms not working?**
A: Ensure your MindGraph instance is accessible via HTTPS for production deployments, and check CORS settings if needed

**Q: API responses too slow for real-time workflows?**
A: Consider using the PNG endpoint for faster responses, or implement caching for frequently requested diagrams

## 📄 License

This project is licensed under the GNU Affero General Public License v3.0 (AGPLv3) - see the [LICENSE](LICENSE) file for details.

### 🔒 AGPLv3 Key Requirements

The AGPLv3 license includes additional requirements beyond the standard GPLv3:

- **Network Use**: If you run a modified version of this software on a server and let other users communicate with it there, your server must also allow them to download the source code corresponding to the modified version running there.
- **Source Code Availability**: Users interacting with the software over a network must be able to receive the source code.
- **Copyleft**: Any derivative works must also be licensed under AGPLv3.

This ensures that improvements to MindGraph remain open source and available to the community, especially when used in network services.

## 🙏 Acknowledgments

- **D3.js** - The powerful visualization library
- **LangChain** - The AI framework that powers our agents
- **Flask** - The web framework
- **Playwright** - For headless browser rendering

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/lycosa9527/MindGraph/issues)
- **Discussions**: [GitHub Discussions](https://github.com/lycosa9527/MindGraph/discussions)
- **Documentation**: [Wiki](https://github.com/lycosa9527/MindGraph/wiki)

---

**Made with ❤️ by the MindSpring Team**

Transform your ideas into beautiful visualizations with the power of AI! 🚀 