#!/bin/bash

# MindGraph Docker Runner Script
# This script helps you run the MindGraph application using Docker

set -e

echo "🚀 MindGraph Docker Setup"
echo "=========================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating one from template..."
    if [ -f env.example ]; then
        cp env.example .env
        echo "✅ Created .env from env.example"
        echo "📝 Please edit .env file and add your QWEN_API_KEY"
    else
        echo "❌ No env.example found. Please create a .env file with your configuration."
        exit 1
    fi
fi

# Check if QWEN_API_KEY is set
if ! grep -q "QWEN_API_KEY=" .env || grep -q "QWEN_API_KEY=$" .env; then
    echo "❌ QWEN_API_KEY not set in .env file"
    echo "📝 Please add your Qwen API key to the .env file:"
    echo "   QWEN_API_KEY=your_api_key_here"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Create necessary directories
mkdir -p mindgraph_exports logs

echo "🔧 Building Docker image..."
docker-compose build

echo "🚀 Starting MindGraph application..."
docker-compose up -d

echo "⏳ Waiting for application to start..."
sleep 10

# Check if the application is running
if curl -f http://localhost:9527/status > /dev/null 2>&1; then
    echo "✅ Application is running successfully!"
    echo "🌐 Open your browser and visit: http://localhost:9527"
    echo ""
    echo "📋 Useful commands:"
    echo "   View logs: docker-compose logs -f"
    echo "   Stop: docker-compose down"
    echo "   Restart: docker-compose restart"
else
    echo "⚠️  Application may still be starting. Please wait a moment and try:"
    echo "   http://localhost:9527"
    echo ""
    echo "📋 To check logs: docker-compose logs -f"
fi 