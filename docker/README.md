# MindGraph Docker Configuration

This folder contains all Docker-related files for the MindGraph application.

**Version**: 4.0.0 (FastAPI + Uvicorn)

## Files

- **`Dockerfile`** - Multi-stage optimized Docker build configuration (FastAPI stack)
- **`docker-compose.yml`** - Docker Compose configuration for easy deployment
- **`docker-entrypoint.sh`** - Container startup script with FastAPI/Uvicorn validation
- **`docker.env.example`** - Environment variables template
- **`README.md`** - This file

## Quick Start

### 1. Build the Docker Image
```bash
# From project root
docker build -f docker/Dockerfile -t mindgraph:latest .
```

### 2. Run with Docker Compose
```bash
# From project root
docker-compose -f docker/docker-compose.yml up -d
```

### 3. Environment Setup
```bash
# Copy the example environment file
cp docker/docker.env.example .env

# Edit .env with your actual values
# - QWEN_API_KEY=your-api-key
# - EXTERNAL_HOST=your-server-ip
```

## Features

- **FastAPI + Uvicorn stack** for high-performance async SSE support
- **Optimized multi-stage build** (~2.93GB final image)
- **Pre-installed Playwright browser** (no runtime downloads)
- **Comprehensive environment variable support**
- **Health checks and monitoring**
- **Non-root user for security**
- **Automatic dependency validation** (FastAPI, Uvicorn, Playwright, LangChain)
- **4,000+ concurrent SSE connections support**

## Architecture

MindGraph uses **FastAPI** with **Uvicorn** (async ASGI server) to support:
- 4,000+ concurrent SSE (Server-Sent Events) connections
- Non-blocking I/O for diagram generation
- Async browser automation (Playwright)
- High-performance bilingual API (zh/en)

## Docker Hub Deployment

The Dockerfile is ready for Docker Hub deployment with all optimizations applied.
