@echo off
REM MindGraph Docker Runner Script for Windows
REM This script helps you run the MindGraph application using Docker

echo 🚀 MindGraph Docker Setup
echo ==========================

REM Check if .env file exists
if not exist .env (
    echo ⚠️  No .env file found. Creating one from template...
    if exist env.example (
        copy env.example .env >nul
        echo ✅ Created .env from env.example
        echo 📝 Please edit .env file and add your QWEN_API_KEY
    ) else (
        echo ❌ No env.example found. Please create a .env file with your configuration.
        pause
        exit /b 1
    )
)

REM Check if QWEN_API_KEY is set
findstr /C:"QWEN_API_KEY=" .env >nul 2>&1
if errorlevel 1 (
    echo ❌ QWEN_API_KEY not set in .env file
    echo 📝 Please add your Qwen API key to the .env file:
    echo    QWEN_API_KEY=your_api_key_here
    pause
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running. Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM Create necessary directories
if not exist mindgraph_exports mkdir mindgraph_exports
if not exist logs mkdir logs

echo 🔧 Building Docker image...
docker-compose build

echo 🚀 Starting MindGraph application...
docker-compose up -d

echo ⏳ Waiting for application to start...
timeout /t 10 /nobreak >nul

REM Check if the application is running
curl -f http://localhost:9527/status >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Application may still be starting. Please wait a moment and try:
    echo    http://localhost:9527
    echo.
    echo 📋 To check logs: docker-compose logs -f
) else (
    echo ✅ Application is running successfully!
    echo 🌐 Open your browser and visit: http://localhost:9527
    echo.
    echo 📋 Useful commands:
    echo    View logs: docker-compose logs -f
    echo    Stop: docker-compose down
    echo    Restart: docker-compose restart
)

pause 