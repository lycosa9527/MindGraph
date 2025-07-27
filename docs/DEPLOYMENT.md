# MindGraph Deployment Guide

This guide explains how to deploy MindGraph for production use, including both local and Docker deployment options.

## 🚀 Quick Start

### **Option 1: Local Deployment (Recommended for Development)**

1. **Prerequisites**
   - Python 3.8+
   - Node.js 18.19+
   - Qwen API key

2. **Install and Run**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Set up environment
   cp env.example .env
   # Edit .env with your API keys
   
   # Run the application
   python app.py
   ```

3. **Access the Application**
   - Open `http://localhost:9527` in your browser
   - Use the debug interface at `http://localhost:9527/debug`

### **Option 2: Docker Deployment (Recommended for Production)**

1. **Prerequisites**
   - Docker and Docker Compose installed
   - Qwen API key

2. **Deploy with Docker Compose**
   ```bash
   # Set up environment
   cp env.example .env
   # Edit .env with your API keys
   
   # Deploy
   cd docker
   docker-compose up -d
   ```

3. **Access the Application**
   - Open `http://localhost:9527` in your browser
   - Use the debug interface at `http://localhost:9527/debug`

## 🔧 Configuration

### **Required Environment Variables**

Create a `.env` file in the project root:

```bash
# REQUIRED: Your Qwen API key
QWEN_API_KEY=your_actual_api_key_here

# Application settings
HOST=0.0.0.0
PORT=9527
DEBUG=False
GRAPH_LANGUAGE=zh
```

### **Optional Configuration**

```bash
# DeepSeek settings (optional for enhanced features)
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# D3.js visualization settings
TOPIC_FONT_SIZE=18
CHAR_FONT_SIZE=14
D3_BASE_WIDTH=700
D3_BASE_HEIGHT=500

# Color theme
D3_TOPIC_FILL=#4e79a7
D3_SIM_FILL=#a7c7e7
D3_DIFF_FILL=#f4f6fb
```

## 🐳 Docker Options

### **Docker Compose (Recommended)**

The easiest way to deploy with Docker:

```bash
# Start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

### **Direct Docker Run**

For more control over the deployment:

```bash
# Build the image
docker build -t mindgraph .

# Run with environment variables
docker run -d \
  --name mindgraph \
  -p 9527:9527 \
  -e QWEN_API_KEY=your_api_key \
  -e GRAPH_LANGUAGE=en \
  -v $(pwd)/mindgraph_exports:/app/mindgraph_exports \
  mindgraph
```

### **Production Docker Setup**

For production environments, create a `.env.production` file:

```bash
# Production settings
QWEN_API_KEY=your_production_api_key
DEBUG=False
HOST=0.0.0.0
PORT=9527
GRAPH_LANGUAGE=zh
WATERMARK_TEXT=YourCompany
EXPORT_CLEANUP_HOURS=48
```

Then deploy:

```bash
docker-compose --env-file .env.production up -d
```

## 🔍 Monitoring

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

### **Docker Monitoring**

```bash
# View container status
docker-compose ps

# View logs
docker-compose logs -f mindgraph

# Monitor resources
docker stats mindgraph
```

## 🔒 Security Considerations

1. **API Key Security**: Never commit your `.env` file to version control
2. **Network Security**: Use reverse proxy (nginx) for production
3. **Resource Limits**: Set Docker resource limits for production

Example production docker-compose with security:

```yaml
version: '3.8'
services:
  mindgraph:
    build: .
    ports:
      - "127.0.0.1:9527:9527"  # Only bind to localhost
    environment:
      - QWEN_API_KEY=${QWEN_API_KEY}
      - DEBUG=False
    volumes:
      - ./mindgraph_exports:/app/mindgraph_exports:ro
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
```

## 🚨 Troubleshooting

### **Common Issues**

1. **Qwen API Key Not Set**
   ```
   ❌ Invalid Qwen configuration. Please check your environment variables.
   ```
   Solution: Set `QWEN_API_KEY` in your `.env` file

2. **Port Already in Use**
   ```
   Error: Port 9527 is already in use
   ```
   Solution: Change `PORT` in `.env` or stop conflicting service

3. **Permission Denied**
   ```
   Permission denied: ./mindgraph_exports
   ```
   Solution: Create directory with proper permissions:
   ```bash
   mkdir -p mindgraph_exports
   chmod 755 mindgraph_exports
   ```

### **Debug Mode**

Enable debug mode for troubleshooting:

```bash
# In .env file
DEBUG=True

# Restart container
docker-compose restart
```

## 📚 API Usage

Once deployed, you can use the API:

```bash
# Generate a graph
curl -X POST http://localhost:9527/generate_graph \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare cats and dogs", "language": "en"}'

# Generate PNG image
curl -X POST http://localhost:9527/generate_png \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare cats and dogs", "language": "en"}'
```

## 🔄 Updates and Maintenance

### **Updating the Application**

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### **Cleaning Up**

The application automatically cleans up old export files. You can also manually clean up:

```bash
# Clean old exports
docker-compose exec mindgraph find /app/mindgraph_exports -mtime +1 -delete
```

---

**Made with ❤️ by the MindSpring Team** 