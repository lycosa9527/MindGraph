# D3.js_Dify - AI-Powered Graph Generation Application
# Version: 2.0.0
# 
# Features:
# - AI-powered graph generation with Qwen and DeepSeek LLMs
# - Interactive D3.js visualization
# - PNG export functionality
# - Comprehensive dependency validation
# - Professional startup sequence
# - Cross-platform compatibility
#
# This Dockerfile creates a production-ready container with optimized logging
# and comprehensive dependency validation.

# Use Python 3.12 slim image for optimal size and performance
FROM python:3.12-slim

# Install system dependencies
# - curl: Required for API calls and status checks
# - gnupg: Required for Node.js repository verification
# - nodejs: Required for D3.js graph rendering
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory for the application
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt ./

# Install Python dependencies with optimized settings
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright Chrome browser for PNG generation
# Only installs Chromium to save space and build time
RUN python -m playwright install chromium

# Copy D3.js dependencies and install them
# D3.js is required for client-side graph rendering
COPY d3.js/package*.json ./d3.js/
WORKDIR /app/d3.js
RUN npm ci --only=production

# Return to main application directory
WORKDIR /app

# Copy the entire project source code
COPY . .

# Create necessary directories for logs and exports
RUN mkdir -p logs d3js_dify_exports

# Expose the application port
EXPOSE 9527

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================

# Application configuration
ENV HOST=0.0.0.0
ENV PORT=9527
ENV DEBUG=False
ENV GRAPH_LANGUAGE=zh
ENV WATERMARK_TEXT=D3.js_Dify

# Qwen API configuration (required for core functionality)
# These must be provided at runtime via docker run or docker-compose
ENV QWEN_API_KEY=""
ENV QWEN_API_URL="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
ENV QWEN_MODEL="qwen-turbo"
ENV QWEN_TEMPERATURE=0.7
ENV QWEN_MAX_TOKENS=1000
ENV QWEN_TIMEOUT=40

# DeepSeek API configuration (optional for enhanced features)
ENV DEEPSEEK_API_KEY=""
ENV DEEPSEEK_API_URL="https://api.deepseek.com/v1/chat/completions"
ENV DEEPSEEK_MODEL="deepseek-chat"
ENV DEEPSEEK_TEMPERATURE=0.7
ENV DEEPSEEK_MAX_TOKENS=2000
ENV DEEPSEEK_TIMEOUT=60

# D3.js visualization configuration
ENV TOPIC_FONT_SIZE=18
ENV CHAR_FONT_SIZE=14
ENV D3_BASE_WIDTH=700
ENV D3_BASE_HEIGHT=500
ENV D3_PADDING=40

# Color theme configuration
ENV D3_TOPIC_FILL="#4e79a7"
ENV D3_TOPIC_TEXT="#ffffff"
ENV D3_TOPIC_STROKE="#2c3e50"
ENV D3_SIM_FILL="#a7c7e7"
ENV D3_SIM_TEXT="#2c3e50"
ENV D3_SIM_STROKE="#4e79a7"
ENV D3_DIFF_FILL="#f4f6fb"
ENV D3_DIFF_TEXT="#2c3e50"
ENV D3_DIFF_STROKE="#a7c7e7"

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9527/status || exit 1

# Start the application with comprehensive validation
CMD ["python", "app.py"] 
