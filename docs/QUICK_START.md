# Quick Start Guide - Version 2.0.0

**D3.js_Dify** - AI-Powered Graph Generation Application

Get up and running with D3.js_Dify in minutes! This guide covers the enhanced startup sequence and new features in version 2.0.0.

## 🚀 Prerequisites

### **System Requirements**
- **Python 3.8+** (required for version 2.0.0)
- **Node.js 18.19+** (for D3.js dependencies)
- **Modern web browser** (Chrome, Firefox, Safari, Edge)
- **4GB RAM minimum** (8GB recommended)
- **2GB free disk space**

### **API Keys Required**
- **Qwen API Key** (required for core functionality)
- **DeepSeek API Key** (optional for enhanced features)

## ⚡ Quick Installation

### **Option 1: Local Installation (Recommended)**

1. **Clone the repository**
   ```bash
   git clone https://github.com/lycosa9527/D3.js_Dify.git
   cd D3.js_Dify
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your API keys
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:9527`

### **Option 2: Docker Installation**

1. **Clone the repository**
   ```bash
   git clone https://github.com/lycosa9527/D3.js_Dify.git
   cd D3.js_Dify
   ```

2. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your API keys
   ```

3. **Run with Docker Compose**
   ```bash
   cd docker
   docker-compose up -d
   ```

4. **Open your browser**
   Navigate to `http://localhost:9527`

## 🆕 Version 2.0.0 Features

### **Enhanced Startup Sequence**

When you run `python app.py`, you'll see a professional startup sequence:

```
🔍 Validating dependencies and configuration...
✅ All dependencies and configuration validated successfully
🚀 Starting D3.js_Dify application...
📋 Configuration Summary:
   Flask: 0.0.0.0:9527 (Debug: False)
   Qwen: qwen-turbo at https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
   DeepSeek: deepseek-chat (❌ Not Available)
   Language: zh
   Theme: #4e79a7 / #a7c7e7 / #f4f6fb
   Dimensions: 700x500px

================================================================================
    ███╗   ███╗██╗███╗   ██╗██████╗ ███╗   ███╗ █████╗ ████████╗███████╗
    ████╗ ████║██║████╗  ██║██╔══██╗████╗ ████║██╔══██╗╚══██╔══╝██╔════╝
    ██╔████╔██║██║██╔██╗ ██║██║  ██║██╔████╔██║███████║   ██║   █████╗  
    ██║╚██╔╝██║██║██║╚██╗██║██║  ██║██║╚██╔╝██║██╔══██║   ██║   ██╔══╝  
    ██║ ╚═╝ ██║██║██║ ╚████║██████╔╝██║ ╚═╝ ██║██║  ██║   ██║   ███████╗
    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝
================================================================================

🌐 Application URLs:
   Local: http://localhost:9527
   Network: http://192.168.0.94:9527

🌐 Open in browser: http://localhost:9527

🌐 Starting Flask development server...
```

### **Automatic Features**

- ✅ **Dependency Validation** - Checks all required packages automatically
- ✅ **Configuration Validation** - Validates API keys and settings
- ✅ **Playwright Installation** - Installs browser automatically if needed
- ✅ **Browser Opening** - Opens browser automatically when server is ready
- ✅ **Cross-Platform Support** - Works on Windows, macOS, and Linux

## 🔧 Configuration

### **Required Environment Variables**

Create a `.env` file in the project root:

```bash
# Required for core functionality
QWEN_API_KEY=your_qwen_api_key_here

# Optional for enhanced features
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Application settings
HOST=0.0.0.0
PORT=9527
DEBUG=False
GRAPH_LANGUAGE=zh
```

### **Optional Configuration**

```bash
# DeepSeek settings (optional)
DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TEMPERATURE=0.7
DEEPSEEK_MAX_TOKENS=2000
DEEPSEEK_TIMEOUT=60

# D3.js visualization settings
TOPIC_FONT_SIZE=18
CHAR_FONT_SIZE=14
D3_BASE_WIDTH=700
D3_BASE_HEIGHT=500
D3_PADDING=40

# Color theme
D3_TOPIC_FILL=#4e79a7
D3_SIM_FILL=#a7c7e7
D3_DIFF_FILL=#f4f6fb
```

## 🎯 First Steps

### **1. Test the Application**

1. **Check the status endpoint**
   ```bash
   curl http://localhost:9527/status
   ```

2. **Visit the demo page**
   Open `http://localhost:9527/demo` in your browser

3. **Try a simple prompt**
   Enter: "Create a mind map about artificial intelligence"

### **2. Generate Your First Graph**

1. **Navigate to the web interface**
   - Go to `http://localhost:9527/demo`

2. **Enter a natural language description**
   - Example: "Show the similarities and differences between cats and dogs"

3. **Click "Generate Graph"**
   - The AI will analyze your request
   - D3.js will create an interactive visualization

4. **Export your graph**
   - Click "Export PNG" for image download
   - Click "Export HTML" for interactive file

## 🐳 Docker Quick Start

### **Using Docker Compose**

1. **Navigate to Docker directory**
   ```bash
   cd docker
   ```

2. **Set environment variables**
   ```bash
   # Create .env file with your API keys
   echo "QWEN_API_KEY=your_key_here" > .env
   echo "DEEPSEEK_API_KEY=your_key_here" >> .env
   ```

3. **Start the application**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   Open `http://localhost:9527` in your browser

### **Using Docker directly**

```bash
docker build -t d3js-dify:2.0.0 .
docker run -p 9527:9527 \
  -e QWEN_API_KEY=your_key_here \
  -e DEEPSEEK_API_KEY=your_key_here \
  d3js-dify:2.0.0
```

## 🔍 Troubleshooting

### **Common Issues**

#### **Missing Dependencies**
```
❌ Missing required packages: pillow
💡 Please install missing packages: pip install -r requirements.txt
```
**Solution**: Run `pip install -r requirements.txt`

#### **API Key Issues**
```
❌ Qwen configuration validation failed
💡 Please check QWEN_API_KEY and QWEN_API_URL in your environment
```
**Solution**: Ensure your `.env` file has the correct API keys

#### **Port Already in Use**
```
Address already in use
```
**Solution**: Change the port in your `.env` file: `PORT=9528`

#### **Browser Not Opening**
```
Server not ready, skipping browser opening
```
**Solution**: Wait a few seconds and manually open `http://localhost:9527`

### **Health Checks**

Check application status:
```bash
curl http://localhost:9527/status
```

Expected response:
```json
{
  "status": "running",
  "uptime_seconds": 45.2,
  "memory_percent": 12.3,
  "timestamp": 1640995200.0
}
```

## 🚀 Next Steps

### **For Users**
1. **Explore the demo interface** - Try different prompts and graph types
2. **Customize settings** - Adjust colors, fonts, and dimensions
3. **Export graphs** - Save your visualizations as PNG or HTML
4. **Check documentation** - Read the full guides for advanced features

### **For Developers**
1. **Review the code** - Check `app.py` for the enhanced startup sequence
2. **Explore configuration** - See `config.py` for property-based settings
3. **Test the API** - Use the RESTful API for programmatic access
4. **Contribute** - Follow the development guide for contributions

### **For Production**
1. **Set up monitoring** - Configure logging and health checks
2. **Optimize performance** - Adjust resource limits and caching
3. **Secure deployment** - Configure CORS and rate limiting
4. **Backup strategy** - Set up data persistence and backups

## 📞 Support

### **Getting Help**
- **Documentation**: Check the [full documentation](../docs/)
- **Issues**: Create an issue on GitHub
- **Discussions**: Join the community discussions

### **Useful Commands**

```bash
# Check application status
curl http://localhost:9527/status

# View logs
tail -f logs/app.log

# Restart application
python app.py

# Update dependencies
pip install -r requirements.txt

# Docker commands
docker-compose down
docker-compose up -d
docker-compose logs -f
```

---

**🎉 Congratulations!** You're now running D3.js_Dify version 2.0.0 with enhanced startup sequences and professional configuration management.

**Made with ❤️ by the D3.js Dify Team**

Transform your data into beautiful visualizations with the power of AI! 🚀 