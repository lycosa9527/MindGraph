# Docker Configuration

This folder contains all Docker-related files for the MindGraph project.

## 📁 Files Overview

### **Dockerfile**
The main Docker image definition that:
- Uses Python 3.12 slim base image
- Installs system dependencies (Node.js, curl, gnupg)
- Copies application code
- Installs Python dependencies
- Sets up Playwright for browser rendering
- Exposes port 9527
- Runs the Flask application

### **docker-compose.yml**
Docker Compose configuration for easy deployment:
- Defines the MindGraph service
- Maps port 9527 to host
- Mounts environment variables
- Sets up volume for logs
- Includes health checks

### **.dockerignore**
Specifies files and directories to exclude from Docker build context:
- Git files
- Python cache
- Logs
- Documentation
- Test files
- Development files

### **run-docker.sh** (Linux/macOS)
Shell script for easy Docker deployment:
- Builds the Docker image
- Runs the container
- Opens browser automatically
- Includes error handling

### **run-docker.bat** (Windows)
Windows batch script for Docker deployment:
- Builds the Docker image
- Runs the container
- Opens browser automatically
- Includes error handling

## 🚀 Quick Start

### Using Docker Compose (Recommended)
```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Using Docker directly
```bash
# Build image
docker build -t d3-dify .

# Run container
docker run -p 9527:9527 d3-dify
```

### Using scripts
```bash
# Linux/macOS
./docker/run-docker.sh

# Windows
docker\run-docker.bat
```

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the project root:
```bash
API_KEY=your_api_key_here
API_BASE_URL=https://api.example.com
HOST=0.0.0.0
PORT=9527
DEBUG=False
```

### Custom Port
To use a different port:
```bash
# Docker Compose
docker-compose up -d -p 8080:9527

# Docker run
docker run -p 8080:9527 d3-dify
```

## 🐛 Troubleshooting

### Common Issues

**Q: Container fails to start?**
A: Check if port 9527 is available and environment variables are set correctly

**Q: Browser doesn't open automatically?**
A: The scripts try to open the browser, but you can manually navigate to `http://localhost:9527`

**Q: Playwright not working in container?**
A: The Dockerfile includes Playwright installation. If issues persist, rebuild the image.

## 📝 Development

### Building for Development
```bash
# Build with development dependencies
docker build -t d3-dify-dev --target development .

# Run with volume mounting for live code changes
docker run -p 9527:9527 -v $(pwd):/app d3-dify-dev
```

### Production Build
```bash
# Multi-stage build for production
docker build -t d3-dify-prod --target production .
```

## 🔗 Related Files

- **Main README**: `../README.md` - Project overview and setup
- **Wiki**: `../WIKI.md` - Comprehensive documentation
- **Environment**: `../env.example` - Environment variables template 