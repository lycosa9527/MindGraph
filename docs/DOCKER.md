# Docker Setup for D3.js_Dify

This document provides instructions for running D3.js_Dify using Docker.

## Prerequisites

- Docker Desktop installed and running
- Qwen API key from Alibaba Cloud

## Quick Start

### Option 1: Using the provided scripts

**Linux/macOS:**
```bash
./run-docker.sh
```

**Windows:**
```cmd
run-docker.bat
```

### Option 2: Manual setup

1. **Create environment file:**
   ```bash
   cp env.example .env
   ```

2. **Edit .env file and add your Qwen API key:**
   ```
   QWEN_API_KEY=your_api_key_here
   ```

3. **Build and run:**
   ```bash
   docker-compose up -d
   ```

4. **Access the application:**
   Open your browser and visit: http://localhost:9527

## Configuration

### Environment Variables

The following environment variables can be configured in your `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `QWEN_API_KEY` | (required) | Your Qwen API key from Alibaba Cloud |
| `QWEN_API_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions` | Qwen API endpoint |
| `QWEN_MODEL` | `qwen-turbo` | Qwen model to use |
| `QWEN_TEMPERATURE` | `0.7` | Model temperature |
| `QWEN_MAX_TOKENS` | `1000` | Maximum tokens for responses |
| `GRAPH_LANGUAGE` | `zh` | Language for graph generation |
| `WATERMARK_TEXT` | `D3.js_Dify` | Watermark text for exports |
| `DEBUG` | `False` | Enable debug mode |

### Volumes

The following directories are mounted as volumes:

- `./d3js_dify_exports` → `/app/d3js_dify_exports` - Exported files
- `./logs` → `/app/logs` - Application logs

## Docker Commands

### Basic Commands

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
```

### Status Check

The application includes a status endpoint at `/status`. You can test it with:

```bash
curl http://localhost:9527/status
```

Expected response:
```json
{
  "status": "running",
  "timestamp": 1234567890.123,
  "service": "D3.js_Dify"
}
```

## Troubleshooting

### Common Issues

1. **Port already in use:**
   ```bash
   # Check what's using port 9527
   netstat -tulpn | grep 9527
   
   # Or change the port in docker-compose.yml
   ports:
     - "9528:9527"  # Use port 9528 instead
   ```

2. **Permission issues:**
   ```bash
   # Create directories with proper permissions
   mkdir -p d3js_dify_exports logs
chmod 755 d3js_dify_exports logs
   ```

3. **Docker not running:**
   - Start Docker Desktop
   - Wait for Docker to be ready
   - Try the command again

4. **API key issues:**
   - Verify your Qwen API key is correct
   - Check that the API key has sufficient credits
   - Ensure the API key is properly set in the `.env` file

### Viewing Logs

```bash
# View all logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# View logs for specific service
docker-compose logs d3js-dify

# View last 100 lines
docker-compose logs --tail=100
```

### Container Management

```bash
# Enter the container
docker-compose exec d3js-dify bash

# Check container status
docker-compose ps

# Remove containers and volumes
docker-compose down -v

# Rebuild without cache
docker-compose build --no-cache
```

## Production Deployment

For production deployment, consider:

1. **Security:**
   - Use secrets management for API keys
   - Enable HTTPS with reverse proxy
   - Restrict container permissions

2. **Monitoring:**
   - Set up log aggregation
   - Monitor resource usage
   - Configure alerts

3. **Scaling:**
   - Use Docker Swarm or Kubernetes
   - Implement load balancing
   - Set up auto-scaling

## Development

For development with Docker:

```bash
# Run with volume mounts for live code changes
docker-compose -f docker-compose.dev.yml up

# Run tests in container
docker-compose exec d3js-dify python -m pytest

# Install new dependencies
docker-compose exec d3js-dify pip install new-package
```

## Support

If you encounter issues:

1. Check the logs: `docker-compose logs -f`
2. Verify your configuration in `.env`
3. Ensure Docker has sufficient resources
4. Check the [main README](../README.md) for general troubleshooting 