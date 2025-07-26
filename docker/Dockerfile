# D3.js_Dify - AI-Powered Graph Generation Service
# This Dockerfile creates a production-ready container with simple logging

# Use the latest stable Python image as base
FROM python:3.12-slim

# Install system dependencies including Node.js for D3.js
# curl: Required for API calls and status checks
# gnupg: Required for Node.js repository verification
# nodejs: Required for D3.js graph rendering
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
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright Chrome browser for graph rendering
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

# Create necessary directories
RUN mkdir -p logs d3js_dify_exports

# Expose the application port
EXPOSE 9527

# Set default environment variables for the application
ENV HOST=0.0.0.0
ENV PORT=9527
ENV DEBUG=False
ENV GRAPH_LANGUAGE=zh
ENV WATERMARK_TEXT=D3.js_Dify

# Qwen API configuration (must be provided at runtime)
# These are required for AI-powered graph generation
ENV QWEN_API_KEY=""
ENV QWEN_API_URL="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
ENV QWEN_MODEL="qwen-turbo"
ENV QWEN_TEMPERATURE=0.7
ENV QWEN_MAX_TOKENS=1000
ENV QWEN_TIMEOUT=40

# Status check configuration


# Start the application
CMD ["python", "app.py"] 
