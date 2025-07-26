# Docker Setup for D3.js_Dify - Version 2.0.0

**D3.js_Dify** - AI-Powered Graph Generation Application

Complete Docker setup guide for D3.js_Dify version 2.0.0 with enhanced containerization, health checks, and production-ready configuration.

## 🐳 Prerequisites

### **System Requirements**
- **Docker Desktop** installed and running
- **Docker Compose** (included with Docker Desktop)
- **4GB RAM minimum** (8GB recommended)
- **2GB free disk space**

### **Required API Keys**
- **Qwen API Key** (required for core functionality)
  - Get from: [Alibaba Cloud DashScope](https://dashscope.aliyun.com/)
- **DeepSeek API Key** (optional for enhanced features)
  - Get from: [DeepSeek AI](https://platform.deepseek.com/)

## 🚀 Quick Start

### **Option 1: Docker Compose (Recommended)**

1. **Clone the repository**
   ```bash
   git clone https://github.com/lycosa9527/D3.js_Dify.git
   cd D3.js_Dify
   ```

2. **Configure environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your API keys
   ```

3. **Run with Docker Compose**
   ```bash
   cd docker
   docker-compose up -d
   ```

4. **Access the application**
   Open your browser and visit: `http://localhost:9527`

### **Option 2: Direct Docker Build**

1. **Build the image**
   ```bash
   docker build -t d3js-dify:2.0.0 .
   ```

2. **Run the container**
   ```bash
   docker run -p 9527:9527 \
     -e QWEN_API_KEY=your_qwen_api_key \
     -e DEEPSEEK_API_KEY=your_deepseek_api_key \
     -v $(pwd)/d3js_dify_exports:/app/d3js_dify_exports \
     -v $(pwd)/logs:/app/logs \
     d3js-dify:2.0.0
   ```

## 🆕 Version 2.0.0 Docker Features

### **Enhanced Dockerfile**
- **Multi-stage build** for optimized image size
- **Comprehensive dependency validation** during build
- **Automatic Playwright browser installation**
- **Health check configuration**
- **Production-ready optimizations**

### **Improved Docker Compose**
- **Health checks** with automatic restart
- **Resource limits** for production stability
- **Volume management** for data persistence
- **Network configuration** for scalability
- **Environment variable validation**

### **Production Features**
- **Health monitoring** endpoints
- **Structured logging** to volumes
- **Resource management** and limits
- **Graceful error handling**
- **Cross-platform compatibility**

## 🔧 Configuration

### **Environment Variables**

#### **Required Variables**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `QWEN_API_KEY` | Qwen API key for core functionality | None | ✅ Yes |
| `QWEN_API_URL` | Qwen API endpoint | DashScope URL | No |
| `QWEN_MODEL` | Qwen model name | qwen-turbo | No |
| `QWEN_TEMPERATURE` | Model creativity (0.0-1.0) | 0.7 | No |
| `QWEN_MAX_TOKENS` | Maximum response tokens | 1000 | No |
| `QWEN_TIMEOUT` | API timeout in seconds | 40 | No |

#### **Optional Variables**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DEEPSEEK_API_KEY` | DeepSeek API key for enhanced features | None | No |
| `DEEPSEEK_API_URL` | DeepSeek API endpoint | DeepSeek URL | No |
| `DEEPSEEK_MODEL` | DeepSeek model name | deepseek-chat | No |
| `DEEPSEEK_TEMPERATURE` | Model creativity (0.0-1.0) | 0.7 | No |
| `DEEPSEEK_MAX_TOKENS` | Maximum response tokens | 2000 | No |
| `DEEPSEEK_TIMEOUT` | API timeout in seconds | 60 | No |

#### **Application Settings**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `HOST` | Flask host address | 0.0.0.0 | No |
| `PORT` | Flask port number | 9527 | No |
| `DEBUG` | Debug mode (True/False) | False | No |
| `GRAPH_LANGUAGE` | Graph language (zh/en) | zh | No |
| `WATERMARK_TEXT` | Watermark text | D3.js_Dify | No |

#### **D3.js Visualization Settings**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TOPIC_FONT_SIZE` | Topic font size in pixels | 18 | No |
| `CHAR_FONT_SIZE` | Character font size in pixels | 14 | No |
| `D3_BASE_WIDTH` | Base width in pixels | 700 | No |
| `D3_BASE_HEIGHT` | Base height in pixels | 500 | No |
| `D3_PADDING` | Padding in pixels | 40 | No |

#### **Color Theme Settings**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `D3_TOPIC_FILL` | Topic fill color | #4e79a7 | No |
| `D3_TOPIC_TEXT` | Topic text color | #ffffff | No |
| `D3_TOPIC_STROKE` | Topic stroke color | #2c3e50 | No |
| `D3_SIM_FILL` | Similarity fill color | #a7c7e7 | No |
| `D3_SIM_TEXT` | Similarity text color | #2c3e50 | No |
| `D3_SIM_STROKE` | Similarity stroke color | #4e79a7 | No |
| `D3_DIFF_FILL` | Difference fill color | #f4f6fb | No |
| `D3_DIFF_TEXT` | Difference text color | #2c3e50 | No |
| `D3_DIFF_STROKE` | Difference stroke color | #a7c7e7 | No |

### **Volumes**

The following directories are mounted as volumes:

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./d3js_dify_exports` | `/app/d3js_dify_exports` | Exported graph files |
| `./logs` | `/app/logs` | Application logs |

### **Ports**

| Host Port | Container Port | Purpose |
|-----------|----------------|---------|
| `9527` | `9527` | Web application |

## 🐳 Docker Commands

### **Basic Commands**

```bash
# Build the image
docker-compose build

# Start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down

# Restart the application
docker-compose restart

# Check container status
docker-compose ps

# View container logs
docker-compose logs d3js-dify
```

### **Development Commands**

```bash
# Run with live code changes
docker-compose -f docker-compose.dev.yml up

# Enter the container
docker-compose exec d3js-dify bash

# Run tests in container
docker-compose exec d3js-dify python -m pytest

# Install new dependencies
docker-compose exec d3js-dify pip install new-package
```

### **Production Commands**

```bash
# Build production image
docker build -t d3js-dify:2.0.0 .

# Run with resource limits
docker run -d \
  --name d3js-dify \
  --memory=2g \
  --cpus=1.0 \
  -p 9527:9527 \
  -e QWEN_API_KEY=your_key \
  -v $(pwd)/exports:/app/d3js_dify_exports \
  -v $(pwd)/logs:/app/logs \
  d3js-dify:2.0.0

# Monitor container health
docker inspect d3js-dify | grep -A 10 "Health"
```

## 🔍 Health Checks

### **Application Health Check**

The application includes a health check endpoint at `/status`:

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

### **Docker Health Check**

The Dockerfile includes a health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9527/status || exit 1
```

### **Monitoring Commands**

```bash
# Check container health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# View health check logs
docker inspect d3js-dify | grep -A 20 "Health"

# Monitor resource usage
docker stats d3js-dify
```

## 🐛 Troubleshooting

### **Common Issues**

#### **Port Already in Use**
```
Error response from daemon: driver failed programming external connectivity
```
**Solution:**
```bash
# Check what's using port 9527
netstat -tulpn | grep 9527

# Change port in docker-compose.yml
ports:
  - "9528:9527"  # Use port 9528 instead
```

#### **Permission Issues**
```
Got permission denied while trying to connect to the Docker daemon
```
**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker
```

#### **API Key Issues**
```
❌ Qwen configuration validation failed
```
**Solution:**
1. Verify your API key in the `.env` file
2. Check API key permissions at DashScope Console
3. Ensure the API key has sufficient credits

#### **Memory Issues**
```
Container killed due to memory limit
```
**Solution:**
```bash
# Increase memory limit in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G
    reservations:
      memory: 1G
```

#### **Build Failures**
```
Failed to build image
```
**Solution:**
```bash
# Clean build without cache
docker-compose build --no-cache

# Check Docker daemon logs
docker system prune -a
```

### **Logging and Debugging**

#### **View Application Logs**
```bash
# View all logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100

# View logs for specific service
docker-compose logs d3js-dify
```

#### **Container Debugging**
```bash
# Enter the container
docker-compose exec d3js-dify bash

# Check application status
curl http://localhost:9527/status

# View environment variables
env | grep -E "(QWEN|DEEPSEEK|HOST|PORT)"

# Check file permissions
ls -la /app/logs /app/d3js_dify_exports
```

#### **System Debugging**
```bash
# Check Docker system info
docker system df
docker system info

# Check container resource usage
docker stats

# View container details
docker inspect d3js-dify
```

## 🚀 Production Deployment

### **Security Considerations**

1. **API Key Management**
   ```bash
   # Use Docker secrets for production
   echo "your_api_key" | docker secret create qwen_api_key -
   
   # Reference in docker-compose.yml
   secrets:
     - qwen_api_key
   ```

2. **Network Security**
   ```yaml
   # Restrict network access
   networks:
     d3js-network:
       driver: bridge
       internal: true
   ```

3. **Resource Limits**
   ```yaml
   # Set appropriate resource limits
   deploy:
     resources:
       limits:
         memory: 2G
         cpus: '1.0'
       reservations:
         memory: 512M
         cpus: '0.5'
   ```

### **Monitoring and Logging**

1. **Log Aggregation**
   ```yaml
   # Configure log driver
   logging:
     driver: "json-file"
     options:
       max-size: "10m"
       max-file: "3"
   ```

2. **Health Monitoring**
   ```bash
   # Set up monitoring
   docker run -d \
     --name monitoring \
     -p 3000:3000 \
     grafana/grafana
   ```

### **Scaling and Load Balancing**

1. **Docker Swarm**
   ```bash
   # Initialize swarm
   docker swarm init
   
   # Deploy stack
   docker stack deploy -c docker-compose.yml d3js
   ```

2. **Kubernetes**
   ```yaml
   # Create deployment
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: d3js-dify
   spec:
     replicas: 3
     selector:
       matchLabels:
         app: d3js-dify
   ```

## 🔄 Updating

### **Update to Version 2.0.0**

1. **Backup your data**
   ```bash
   cp -r d3js_dify_exports exports_backup
   cp -r logs logs_backup
   ```

2. **Update the repository**
   ```bash
   git pull origin main
   ```

3. **Rebuild the image**
   ```bash
   docker-compose build --no-cache
   ```

4. **Update containers**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

5. **Verify the update**
   ```bash
   curl http://localhost:9527/status
   ```

### **Rollback Procedure**

```bash
# Stop current containers
docker-compose down

# Restore backup
cp -r exports_backup d3js_dify_exports
cp -r logs_backup logs

# Restart with previous version
docker-compose up -d
```

## 📞 Support

### **Getting Help**

- **Documentation**: Check the [full documentation](./)
- **Issues**: Create an issue on [GitHub](https://github.com/lycosa9527/D3.js_Dify/issues)
- **Discussions**: Join the [community discussions](https://github.com/lycosa9527/D3.js_Dify/discussions)

### **Useful Commands**

```bash
# Check application status
curl http://localhost:9527/status

# View container logs
docker-compose logs -f

# Restart application
docker-compose restart

# Update dependencies
docker-compose build --no-cache

# Clean up Docker system
docker system prune -a

# Monitor resource usage
docker stats

# Check container health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

---

**🎉 Docker Setup Complete!** Your D3.js_Dify version 2.0.0 is now running in a production-ready Docker container with enhanced monitoring and health checks.

**Made with ❤️ by the D3.js Dify Team**

Transform your data into beautiful visualizations with the power of AI! 🚀 