# D3.js_Dify Deployment Guide

This guide explains how to deploy D3.js_Dify using Docker with the unified configuration system.

## 🚀 Quick Start

### 1. Prerequisites

- Docker and Docker Compose installed
- Qwen API key from DashScope
- Playwright Python package and browsers (for local runs)

### 2. Environment Configuration

Copy the example environment file and configure your settings:

```bash
cp env.example .env
```

Edit `.env` and set your Qwen API key:

```bash
# REQUIRED: Your Qwen API key
QWEN_API_KEY=your_actual_api_key_here

# Optional: Override other settings as needed
GRAPH_LANGUAGE=en
DEBUG=False
```

### 3. Install Python Dependencies (for local runs)

```bash
pip install -r requirements.txt
python -m playwright install
```

### 4. Deploy with Docker Compose

```bash
# Build and start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

### 4. Access the Application

- **Web Demo**: http://localhost:9527/demo
- **API Documentation**: http://localhost:9527

## 🔧 Configuration Options

### Qwen API Configuration (Required)

| Variable | Default | Description |
|----------|---------|-------------|
| `QWEN_API_KEY` | - | Your Qwen API key from DashScope |
| `QWEN_API_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions` | Qwen API endpoint |
| `QWEN_MODEL` | `qwen-plus` | Qwen model to use |
| `QWEN_TEMPERATURE` | `0.7` | Temperature for LLM responses (0.0-1.0) |
| `QWEN_MAX_TOKENS` | `1000` | Maximum tokens for responses |

### Flask Application Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Host to bind to |
| `PORT` | `9527` | Port to run on |
| `DEBUG` | `False` | Debug mode (set to `True` for development) |

### Graph Language Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_LANGUAGE` | `zh` | Default language for graphs (`zh` or `en`) |

### Watermark Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WATERMARK_TEXT` | `MindSpring` | Watermark text on images |
| `WATERMARK_OPACITY` | `80` | Watermark opacity (0-255) |
| `WATERMARK_FONT_SCALE` | `40` | Font scale for watermark |
| `WATERMARK_BG_OPACITY` | `30` | Background opacity (0-255) |

### Export Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EXPORT_DIR` | `d3js_dify_exports` | Directory for exported images |
| `EXPORT_CLEANUP_HOURS` | `24` | Hours to keep exported files |

## 🐳 Docker Deployment Options

### Option 1: Docker Compose (Recommended)

```bash
# Start with default settings
docker-compose up -d

# Start with custom environment file
docker-compose --env-file .env.production up -d
```

### Option 2: Docker Run

```bash
# Build the image
docker build -t d3js-dify .

# Run with environment variables
docker run -d \
  --name d3js-dify \
  -p 9527:9527 \
  -e QWEN_API_KEY=your_api_key \
  -e GRAPH_LANGUAGE=en \
  -v $(pwd)/d3js_dify_exports:/app/d3js_dify_exports \
  d3js-dify
```

### Option 3: Production Deployment

For production, create a `.env.production` file:

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

The application includes basic monitoring:

```bash
# View Docker status
docker-compose ps

# View logs
docker-compose logs -f d3js-dify
```

## 📁 Volume Mounts

The application mounts the export directory to persist generated images:

```yaml
volumes:
  - ./d3js_dify_exports:/app/d3js_dify_exports
```

This ensures generated images persist between container restarts.

## 🔒 Security Considerations

1. **API Key Security**: Never commit your `.env` file to version control
2. **Network Security**: Use reverse proxy (nginx) for production
3. **Resource Limits**: Set Docker resource limits for production

Example production docker-compose with security:

```yaml
version: '3.8'
services:
  d3js-dify:
    build: .
    ports:
      - "127.0.0.1:9527:9527"  # Only bind to localhost
    environment:
      - QWEN_API_KEY=${QWEN_API_KEY}
      - DEBUG=False
    volumes:
      - ./d3js_dify_exports:/app/d3js_dify_exports:ro
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
```

## 🚨 Troubleshooting

### Common Issues

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
   Permission denied: ./d3js_dify_exports
   ```
   Solution: Create directory with proper permissions:
   ```bash
   mkdir -p d3js_dify_exports
   chmod 755 d3js_dify_exports
   ```

### Debug Mode

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
# Generate a double bubble map
curl -X POST http://localhost:9527/agent_double_bubble \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare cats and dogs", "language": "en"}'

# Convert markdown to image
curl -X POST http://localhost:9527/convert \
  -H "Content-Type: application/json" \
  -d '{"markdown": "```json\n{\"type\": \"force\", \"nodes\": [{\"id\": \"A\", \"name\": \"Test\"}, {\"id\": \"B\", \"name\": \"Success\"}], \"links\": [{\"source\": \"A\", \"target\": \"B\"}]}\n```"}'
```

## 🔄 Updates and Maintenance

To update the application:

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

To clean up old exports:

```bash
# The application automatically cleans up old files
# You can also manually clean up:
docker-compose exec d3js-dify find /app/d3js_dify_exports -mtime +1 -delete
``` 