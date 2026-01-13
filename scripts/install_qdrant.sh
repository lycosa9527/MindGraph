#!/bin/bash
#
# Qdrant Installation Script for Ubuntu
# MindGraph - AI-Powered Visual Thinking Tools
#
# Usage: bash scripts/install_qdrant.sh
#
# This script will:
# 1. Download the latest Qdrant release
# 2. Create a systemd service
# 3. Start Qdrant on port 6333
# 4. Add QDRANT_HOST to .env file
#

set -e

echo "========================================"
echo "  Qdrant Installation Script"
echo "  MindGraph Vector Database Setup"
echo "========================================"
echo ""

# Configuration
QDRANT_DIR="$HOME/qdrant"
QDRANT_STORAGE="$QDRANT_DIR/storage"
QDRANT_PORT=6333

# Save the directory where script was invoked (MindGraph root)
SCRIPT_INVOKE_DIR="$(pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    print_error "This script is for Ubuntu/Linux only"
    exit 1
fi

# Check for required commands
if ! command -v wget &> /dev/null; then
    print_error "wget is required but not installed"
    echo "Install with: sudo apt-get install wget"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    print_error "curl is required but not installed"
    echo "Install with: sudo apt-get install curl"
    exit 1
fi

# Check if Qdrant is already running
if curl -s http://localhost:$QDRANT_PORT/collections > /dev/null 2>&1; then
    print_warning "Qdrant is already running on port $QDRANT_PORT"
    echo ""
    curl -s http://localhost:$QDRANT_PORT | grep -o '"version":"[^"]*"' || true
    echo ""
    read -p "Do you want to reinstall/upgrade? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    echo "Stopping existing Qdrant..."
    sudo systemctl stop qdrant 2>/dev/null || true
fi

# Step 1: Create directories
echo ""
echo "Step 1: Creating directories..."
mkdir -p "$QDRANT_DIR"
mkdir -p "$QDRANT_STORAGE"
print_status "Created $QDRANT_DIR"

# Step 2: Download latest Qdrant
echo ""
echo "Step 2: Downloading latest Qdrant..."
cd "$QDRANT_DIR"

# Get latest release URL
LATEST_URL="https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-gnu.tar.gz"
DOWNLOAD_FILE="qdrant-x86_64-unknown-linux-gnu.tar.gz"

# Backup existing binary if present
if [ -f "$QDRANT_DIR/qdrant" ]; then
    mv "$QDRANT_DIR/qdrant" "$QDRANT_DIR/qdrant.bak"
    print_status "Backed up existing binary"
fi

# Download
echo "Downloading from: $LATEST_URL"
wget -q --show-progress "$LATEST_URL" -O "$DOWNLOAD_FILE"
print_status "Download complete"

# Step 3: Extract and setup
echo ""
echo "Step 3: Extracting..."
tar -xzf "$DOWNLOAD_FILE"
chmod +x qdrant
rm -f "$DOWNLOAD_FILE"
print_status "Extracted and set permissions"

# Step 4: Create systemd service
echo ""
echo "Step 4: Creating systemd service..."

SERVICE_FILE="/etc/systemd/system/qdrant.service"
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Qdrant Vector Database
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$QDRANT_DIR
ExecStart=$QDRANT_DIR/qdrant
Restart=always
RestartSec=10
Environment="QDRANT__STORAGE__STORAGE_PATH=$QDRANT_STORAGE"
Environment="QDRANT__SERVICE__HTTP_PORT=$QDRANT_PORT"

[Install]
WantedBy=multi-user.target
EOF

print_status "Created systemd service"

# Step 5: Enable and start service
echo ""
echo "Step 5: Starting Qdrant service..."
sudo systemctl daemon-reload
sudo systemctl enable qdrant
sudo systemctl start qdrant
print_status "Service started"

# Wait for Qdrant to be ready
echo "Waiting for Qdrant to start..."
sleep 2

# Step 6: Verify installation
echo ""
echo "Step 6: Verifying installation..."
MAX_RETRIES=10
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:$QDRANT_PORT/collections > /dev/null 2>&1; then
        print_status "Qdrant is running on port $QDRANT_PORT"
        break
    fi
    RETRY=$((RETRY + 1))
    sleep 1
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    print_error "Qdrant failed to start. Check logs: sudo journalctl -u qdrant -n 50"
    exit 1
fi

# Get version from API
VERSION=$(curl -s http://localhost:$QDRANT_PORT | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
print_status "Installed version: $VERSION"

# Step 7: Verify .env configuration
echo ""
echo "Step 7: Verifying .env configuration..."

# Use the directory where script was invoked (should be MindGraph root)
ENV_FILE="$SCRIPT_INVOKE_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    if grep -q "^QDRANT_HOST=localhost:$QDRANT_PORT" "$ENV_FILE"; then
        print_status "QDRANT_HOST=localhost:$QDRANT_PORT is configured"
    elif grep -q "^QDRANT_HOST=" "$ENV_FILE"; then
        CURRENT_VALUE=$(grep "^QDRANT_HOST=" "$ENV_FILE" | cut -d'=' -f2)
        print_warning "QDRANT_HOST is set to '$CURRENT_VALUE' (expected localhost:$QDRANT_PORT)"
    else
        print_warning "QDRANT_HOST not found in .env"
        echo "Add this line to your .env: QDRANT_HOST=localhost:$QDRANT_PORT"
    fi
else
    print_warning ".env file not found"
    echo "Copy env.example to .env - QDRANT_HOST is already configured there."
fi

# Done!
echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""
echo "Qdrant is running on: http://localhost:$QDRANT_PORT"
echo "Dashboard URL: http://localhost:$QDRANT_PORT/dashboard"
echo ""
echo "Service commands:"
echo "  sudo systemctl status qdrant   # Check status"
echo "  sudo systemctl restart qdrant  # Restart"
echo "  sudo journalctl -u qdrant -f   # View logs"
echo ""
echo "Next step: Restart MindGraph to enable background processing"
echo "  python run_server.py"
echo ""
