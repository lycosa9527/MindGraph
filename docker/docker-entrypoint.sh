#!/bin/bash
# MindGraph Docker Entrypoint Script
# Handles Playwright browser installation and application startup

set -e

echo "=== MindGraph Docker Container Starting ==="
echo "Container started at: $(date)"
echo "Python version: $(python --version)"
echo "Node.js version: $(node --version)"

# Function to check if Playwright browsers are installed
check_playwright_browsers() {
    echo "Checking Playwright browser installation..."
    if python -c "
from playwright.sync_api import sync_playwright
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        browser.close()
    print('✓ Playwright browsers are properly installed')
    exit(0)
except Exception as e:
    print(f'✗ Playwright browser check failed: {e}')
    exit(1)
" 2>/dev/null; then
        return 0
    else
        echo "✗ Playwright browsers need to be installed"
        return 1
    fi
}

# Function to install Playwright browsers
install_playwright_browsers() {
    echo "Installing Playwright browsers..."
    # Install system dependencies first (matching setup.py approach)
    playwright install-deps
    # Install Chromium browser
    playwright install chromium
    echo "✓ Playwright browsers installed successfully"
}

# Function to validate environment
validate_environment() {
    echo "Validating environment configuration..."
    
    # Check if QWEN_API_KEY is set
    if [ -z "$QWEN_API_KEY" ]; then
        echo "⚠️  WARNING: QWEN_API_KEY environment variable is not set"
        echo "   The application will start but AI features may not work"
        echo "   Set QWEN_API_KEY in your environment or docker-compose.yml"
    else
        echo "✓ QWEN_API_KEY is configured"
    fi
    
    # Check if required directories exist
    mkdir -p logs static/images test/images
    echo "✓ Required directories created"
    
    # Check essential log files (matching setup.py requirements)
    local log_files=("app.log" "agent.log")
    for log_file in "${log_files[@]}"; do
        if [ ! -f "logs/$log_file" ]; then
            touch "logs/$log_file"
            echo "✓ Created missing log file: $log_file"
        fi
    done
    
    # Check Python dependencies
    if python -c "import fastapi, uvicorn, playwright, langchain" 2>/dev/null; then
        echo "✓ Core Python dependencies are available (FastAPI + Uvicorn)"
    else
        echo "✗ Missing core Python dependencies (FastAPI, Uvicorn, Playwright, or LangChain)"
        exit 1
    fi
}

# Function to start the application
start_application() {
    echo "Starting MindGraph application..."
    echo "Port: ${PORT:-9527}"
    echo "Environment: ${MINDGRAPH_ENV:-production}"
    
    # Execute the command passed to the container
    exec "$@"
}

# Main execution
main() {
    echo "=== Environment Validation ==="
    validate_environment
    
    echo "=== Playwright Browser Setup ==="
    if ! check_playwright_browsers; then
        install_playwright_browsers
    fi
    
    echo "=== Starting Application ==="
    start_application "$@"
}

# Handle signals for graceful shutdown
trap 'echo "Received shutdown signal, stopping gracefully..."; exit 0' SIGTERM SIGINT

# Run main function
main "$@"
