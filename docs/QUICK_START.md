# Quick Start Guide

**MindGraph** - AI-Powered Graph Generation Application

Get up and running with MindGraph in minutes! Create beautiful interactive visualizations using AI.

## 🚀 Prerequisites

### **System Requirements**
- **Python 3.8+** (required for version 2.1.0)
- **Node.js 18.19+** (for D3.js dependencies)
- **Modern web browser** (Chrome, Firefox, Safari, Edge)
- **4GB RAM minimum** (8GB recommended)
- **2GB free disk space**

### **Required API Key**
- **Qwen API Key** - Get from [Alibaba Cloud DashScope](https://dashscope.aliyun.com/)

## ⚡ Quick Installation

### **Option 1: Local Installation (Recommended)**

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
   # Edit .env with your API keys
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:9527/debug`

### **Option 2: Docker Installation**

1. **Clone the repository**
   ```bash
   git clone https://github.com/lycosa9527/MindGraph.git
   cd MindGraph
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
   Navigate to `http://localhost:9527/debug`

## 🎯 First Steps

### **1. Test the Application**

1. **Check the status**
   ```bash
   curl http://localhost:9527/status
   ```

2. **Visit the debug page**
   Open `http://localhost:9527/debug` in your browser

3. **Try a simple prompt**
   Enter: "Compare cats and dogs"

### **2. Generate Your First Graph**

1. **Navigate to the web interface**
   - Go to `http://localhost:9527/debug`

2. **Enter a natural language description**
   - Example: "Show the similarities and differences between cats and dogs"

3. **Click "Generate Graph"**
   - The AI will analyze your request
   - D3.js will create an interactive visualization

4. **Export your graph**
   - Click "Export PNG" for image download
   - Click "Export HTML" for interactive file

## 🎨 Example Prompts

Try these prompts to get started:

- "Compare cats and dogs"
- "Define artificial intelligence"
- "Show the relationship between cause and effect"
- "Create a mind map about climate change"
- "Compare traditional and modern education"



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
**Solution**: Ensure your `.env` file has the correct API key

#### **Port Already in Use**
```
Address already in use
```
**Solution**: Change the port in your `.env` file: `PORT=9528`

#### **Browser Not Opening**
```
Server not ready, skipping browser opening
```
**Solution**: Wait a few seconds and manually open `http://localhost:9527/debug`

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
1. **Explore the debug interface** - Try different prompts and graph types
2. **Learn about Thinking Maps** - Read the [Thinking Maps Guide](THINKING_MAPS_GUIDE.md)
3. **Deploy to production** - Check the [Deployment Guide](DEPLOYMENT.md)

### **Useful Commands**

```bash
# Check application status
curl http://localhost:9527/status

# View logs
tail -f logs/app.log

# Restart application
python app.py

# Docker commands
docker-compose down
docker-compose up -d
docker-compose logs -f
```

## 📞 Support

### **Getting Help**
- **Documentation**: Check the [full documentation](../docs/)
- **Issues**: Create an issue on GitHub
- **Discussions**: Join the community discussions

---

**🎉 Congratulations!** You're now running MindGraph and ready to create beautiful visualizations!

**Made with ❤️ by the MindSpring Team**

Transform your ideas into beautiful visualizations with the power of AI! 🚀 