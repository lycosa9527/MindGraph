#!/bin/bash
#
# Clear Python Bytecode Cache Script
# ===================================
# 
# This script clears all Python bytecode cache files and directories
# to ensure fresh code is loaded on the next application start.
#
# Usage:
#   chmod +x clear_pycache.sh
#   ./clear_pycache.sh [--restart]
#
# Options:
#   --restart    Also restart the mindgraph service after clearing cache
#
# @author MindSpring Team
# @date January 27, 2026
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in scripts/utils/, so go up 2 levels to reach project root
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "================================================"
echo "  MindGraph - Clear Python Bytecode Cache"
echo "================================================"
echo ""
echo "Project root: $PROJECT_ROOT"
echo ""

# Change to project root
cd "$PROJECT_ROOT" || {
    echo -e "${RED}Error: Could not change to project root: $PROJECT_ROOT${NC}"
    exit 1
}

# Function to run find with exclusions for counting/listing
# Excludes common directories that shouldn't be searched (improves performance)
run_find() {
    find . \( \
        -path ./.git -o \
        -path ./.venv -o \
        -path ./venv -o \
        -path ./env -o \
        -path ./.env -o \
        -path ./node_modules -o \
        -path ./.pytest_cache -o \
        -path ./.mypy_cache -o \
        -path ./.ruff_cache -o \
        -path ./dist -o \
        -path ./build \
    \) -prune -o "$@" -print
}

# Function to run find with exclusions and execute action
run_find_exec() {
    find . \( \
        -path ./.git -o \
        -path ./.venv -o \
        -path ./venv -o \
        -path ./env -o \
        -path ./.env -o \
        -path ./node_modules -o \
        -path ./.pytest_cache -o \
        -path ./.mypy_cache -o \
        -path ./.ruff_cache -o \
        -path ./dist -o \
        -path ./build \
    \) -prune -o "$@"
}

# Count before clearing
PYCACHE_DIRS=$(run_find -type d -name "__pycache__" 2>/dev/null | wc -l)
PYC_FILES=$(run_find -type f -name "*.pyc" 2>/dev/null | wc -l)
PYO_FILES=$(run_find -type f -name "*.pyo" 2>/dev/null | wc -l)

echo -e "${YELLOW}Found:${NC}"
echo "  - $PYCACHE_DIRS __pycache__ directories"
echo "  - $PYC_FILES .pyc files"
echo "  - $PYO_FILES .pyo files"
echo ""

# Clear __pycache__ directories
if [ "$PYCACHE_DIRS" -gt 0 ]; then
    echo -e "${YELLOW}Clearing __pycache__ directories...${NC}"
    run_find_exec -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
fi

# Clear .pyc files
if [ "$PYC_FILES" -gt 0 ]; then
    echo -e "${YELLOW}Clearing .pyc files...${NC}"
    run_find_exec -type f -name "*.pyc" -delete 2>/dev/null || true
fi

# Clear .pyo files (optimized bytecode)
if [ "$PYO_FILES" -gt 0 ]; then
    echo -e "${YELLOW}Clearing .pyo files...${NC}"
    run_find_exec -type f -name "*.pyo" -delete 2>/dev/null || true
fi

# Verify
REMAINING_DIRS=$(run_find -type d -name "__pycache__" 2>/dev/null | wc -l)
REMAINING_FILES=$(run_find -type f -name "*.pyc" 2>/dev/null | wc -l)
REMAINING_PYO=$(run_find -type f -name "*.pyo" 2>/dev/null | wc -l)

echo ""
if [ "$PYCACHE_DIRS" -eq 0 ] && [ "$PYC_FILES" -eq 0 ] && [ "$PYO_FILES" -eq 0 ]; then
    echo -e "${GREEN}No cache files found. Cache is already clean!${NC}"
else
    echo -e "${GREEN}Cache cleared successfully!${NC}"
    echo "  - Removed $((PYCACHE_DIRS - REMAINING_DIRS)) __pycache__ directories"
    echo "  - Removed $((PYC_FILES - REMAINING_FILES)) .pyc files"
    echo "  - Removed $((PYO_FILES - REMAINING_PYO)) .pyo files"
fi
echo ""

# Check for --restart flag
if [ $# -gt 0 ] && [[ "$1" == "--restart" ]]; then
    echo -e "${YELLOW}Restarting mindgraph service...${NC}"
    
    # Try systemctl first (systemd)
    if command -v systemctl &> /dev/null && systemctl list-units --type=service | grep -q mindgraph; then
        sudo systemctl restart mindgraph
        echo -e "${GREEN}Service restarted via systemctl${NC}"
    # Try supervisorctl
    elif command -v supervisorctl &> /dev/null; then
        sudo supervisorctl restart mindgraph
        echo -e "${GREEN}Service restarted via supervisorctl${NC}"
    # Try pm2
    elif command -v pm2 &> /dev/null; then
        pm2 restart mindgraph
        echo -e "${GREEN}Service restarted via pm2${NC}"
    else
        echo -e "${RED}Could not find service manager. Please restart manually:${NC}"
        echo "  sudo systemctl restart mindgraph"
        echo "  OR"
        echo "  sudo supervisorctl restart mindgraph"
        echo "  OR"
        echo "  pm2 restart mindgraph"
        echo "  OR"
        echo "  pkill -f uvicorn && cd $PROJECT_ROOT && python -m uvicorn main:app --host 0.0.0.0 --port 9527 &"
    fi
    
    echo ""
    echo -e "${GREEN}Done! Application should now use fresh bytecode.${NC}"
else
    echo -e "${YELLOW}Note:${NC} Run with --restart to also restart the service:"
    echo "  ./clear_pycache.sh --restart"
    echo ""
    echo "Or restart manually:"
    echo "  sudo systemctl restart mindgraph"
fi

echo ""
echo "================================================"
