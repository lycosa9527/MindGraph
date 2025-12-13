#!/bin/bash
#
# MindGraph systemd Service Setup Script
# =======================================
#
# This script sets up MindGraph as a systemd service for production deployment.
# Run this once per server after installing dependencies.
#
# Usage:
#   conda activate python313  # or your environment
#   cd /path/to/MindGraph
#   ./scripts/setup_systemd.sh
#
# Requirements:
#   - Linux with systemd
#   - Python environment activated (conda or venv)
#   - sudo privileges
#
# Author: MindGraph Team
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    print_error "This script only works on Linux with systemd"
    print_info "On Windows/macOS, just run: python run_server.py"
    exit 1
fi

# Check if systemd is available
if ! command -v systemctl &> /dev/null; then
    print_error "systemctl not found. Is systemd installed?"
    exit 1
fi

# Check for sudo privileges
if ! sudo -n true 2>/dev/null; then
    print_warning "This script requires sudo privileges"
    print_info "You may be prompted for your password"
fi

echo ""
echo "========================================"
echo "  MindGraph systemd Service Setup"
echo "========================================"
echo ""

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check if we're in the right directory
if [[ ! -f "$PROJECT_DIR/run_server.py" ]]; then
    print_error "run_server.py not found in $PROJECT_DIR"
    print_error "Please run this script from the MindGraph project directory"
    exit 1
fi

# Check if template exists
TEMPLATE_FILE="$SCRIPT_DIR/mindgraph.service.template"
if [[ ! -f "$TEMPLATE_FILE" ]]; then
    print_error "Template file not found: $TEMPLATE_FILE"
    exit 1
fi

# Check if service already exists
if [[ -f "/etc/systemd/system/mindgraph.service" ]]; then
    print_warning "MindGraph service already exists!"
    print_info "Current service file: /etc/systemd/system/mindgraph.service"
    read -p "Overwrite existing service? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Setup cancelled. Existing service unchanged."
        exit 0
    fi
    print_info "Will overwrite existing service..."
fi

# Auto-detect settings
print_info "Detecting configuration..."

# Get current user (the one who will run the service)
# If running as root via sudo, try to get the original user
if [[ "$EUID" -eq 0 ]] && [[ -n "$SUDO_USER" ]]; then
    CURRENT_USER="$SUDO_USER"
    CURRENT_GROUP=$(id -gn "$SUDO_USER")
else
    CURRENT_USER=$(whoami)
    CURRENT_GROUP=$(id -gn)
fi

# Get Python path (works with conda, venv, or system Python)
# Priority: 1) CONDA_PREFIX (if conda is active), 2) which python, 3) which python3
if [[ -n "$CONDA_PREFIX" ]]; then
    # Conda environment is active
    PYTHON_PATH="$CONDA_PREFIX/bin/python"
elif [[ -n "$VIRTUAL_ENV" ]]; then
    # Virtualenv is active
    PYTHON_PATH="$VIRTUAL_ENV/bin/python"
else
    # Fallback to which (may not work correctly with sudo)
    PYTHON_PATH=$(which python 2>/dev/null || which python3 2>/dev/null)
fi

# Validate Python path
if [[ -z "$PYTHON_PATH" ]] || [[ ! -x "$PYTHON_PATH" ]]; then
    print_error "Python not found or not executable"
    print_info "Please activate your conda/venv environment first:"
    print_info "  conda activate python313"
    print_info "  # or: source venv/bin/activate"
    print_info ""
    print_info "Then run this script WITHOUT sudo:"
    print_info "  ./scripts/setup_systemd.sh"
    print_info ""
    print_info "Or specify Python path manually:"
    print_info "  PYTHON_PATH=/path/to/python ./scripts/setup_systemd.sh"
    exit 1
fi

# Check if we're using system Python when conda/venv might be intended
if [[ "$PYTHON_PATH" == "/usr/bin/python"* ]] && [[ "$EUID" -eq 0 ]]; then
    print_warning "Detected system Python: $PYTHON_PATH"
    print_warning "If you intended to use conda/venv, the environment may not be active."
    print_info ""
    print_info "To use your conda environment, run WITHOUT sudo first:"
    print_info "  conda activate python313"
    print_info "  ./scripts/setup_systemd.sh"
    print_info ""
    read -p "Continue with system Python? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Setup cancelled. Please activate your environment and try again."
        exit 0
    fi
fi

PYTHON_BIN_DIR=$(dirname "$PYTHON_PATH")

# Verify Python
PYTHON_VERSION=$($PYTHON_PATH --version 2>&1)

echo ""
print_info "Detected configuration:"
echo "  User:        $CURRENT_USER"
echo "  Group:       $CURRENT_GROUP"
echo "  Project:     $PROJECT_DIR"
echo "  Python:      $PYTHON_PATH"
echo "  Version:     $PYTHON_VERSION"
echo ""

# Confirm with user
read -p "Is this correct? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Setup cancelled by user"
    exit 0
fi

# Generate service file from template
print_info "Generating service file..."

SERVICE_FILE="/tmp/mindgraph.service"

sed -e "s|{{USER}}|$CURRENT_USER|g" \
    -e "s|{{GROUP}}|$CURRENT_GROUP|g" \
    -e "s|{{WORKING_DIR}}|$PROJECT_DIR|g" \
    -e "s|{{PYTHON_PATH}}|$PYTHON_PATH|g" \
    -e "s|{{PYTHON_BIN_DIR}}|$PYTHON_BIN_DIR|g" \
    "$TEMPLATE_FILE" > "$SERVICE_FILE"

print_success "Service file generated"

# Show generated service file
echo ""
print_info "Generated service file:"
echo "----------------------------------------"
cat "$SERVICE_FILE"
echo "----------------------------------------"
echo ""

# Confirm installation
read -p "Install this service file? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Installation cancelled"
    print_info "Service file saved to: $SERVICE_FILE"
    exit 0
fi

# Install service file
print_info "Installing service file..."

sudo cp "$SERVICE_FILE" /etc/systemd/system/mindgraph.service
sudo chmod 644 /etc/systemd/system/mindgraph.service

print_success "Service file installed to /etc/systemd/system/mindgraph.service"

# Reload systemd
print_info "Reloading systemd..."
sudo systemctl daemon-reload
print_success "systemd reloaded"

# Enable service (start on boot)
print_info "Enabling service to start on boot..."
sudo systemctl enable mindgraph
print_success "Service enabled"

# Ask if user wants to start now
echo ""
read -p "Start MindGraph now? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Check if already running (e.g., via nohup)
    if pgrep -f "run_server.py" > /dev/null; then
        print_warning "MindGraph appears to be already running"
        read -p "Stop existing process and start via systemd? (y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Stopping existing process..."
            pkill -f "run_server.py" || true
            sleep 2
        else
            print_warning "Please stop the existing process manually, then run:"
            echo "  sudo systemctl start mindgraph"
            exit 0
        fi
    fi
    
    print_info "Starting MindGraph..."
    sudo systemctl start mindgraph
    sleep 2
    
    # Check status
    if sudo systemctl is-active --quiet mindgraph; then
        print_success "MindGraph is running!"
    else
        print_error "Failed to start MindGraph"
        print_info "Check logs with: sudo journalctl -u mindgraph -n 50"
        exit 1
    fi
fi

# Print summary
echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
print_success "MindGraph is now a systemd service"
echo ""
echo "Commands:"
echo "  sudo systemctl start mindgraph     # Start the service"
echo "  sudo systemctl stop mindgraph      # Stop the service"
echo "  sudo systemctl restart mindgraph   # Restart the service"
echo "  sudo systemctl status mindgraph    # Check status"
echo "  sudo journalctl -u mindgraph -f    # View live logs"
echo "  sudo journalctl -u mindgraph -n 50 # View last 50 log lines"
echo ""
echo "The service will automatically:"
echo "  - Start on system boot"
echo "  - Restart if it crashes (except for database corruption)"
echo "  - Stop gracefully with 30 second timeout"
echo ""
print_info "To uninstall: sudo systemctl disable mindgraph && sudo rm /etc/systemd/system/mindgraph.service"
echo ""

