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
# @date December 13, 2025
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "================================================"
echo "  MindGraph - Clear Python Bytecode Cache"
echo "================================================"
echo ""
echo "Project root: $PROJECT_ROOT"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Count before clearing
PYCACHE_DIRS=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
PYC_FILES=$(find . -type f -name "*.pyc" 2>/dev/null | wc -l)

echo -e "${YELLOW}Found:${NC}"
echo "  - $PYCACHE_DIRS __pycache__ directories"
echo "  - $PYC_FILES .pyc files"
echo ""

# Clear __pycache__ directories
echo -e "${YELLOW}Clearing __pycache__ directories...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Clear .pyc files
echo -e "${YELLOW}Clearing .pyc files...${NC}"
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Clear .pyo files (optimized bytecode)
echo -e "${YELLOW}Clearing .pyo files...${NC}"
find . -type f -name "*.pyo" -delete 2>/dev/null || true

# Verify
REMAINING_DIRS=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
REMAINING_FILES=$(find . -type f -name "*.pyc" 2>/dev/null | wc -l)

echo ""
echo -e "${GREEN}Cache cleared successfully!${NC}"
echo "  - Removed $((PYCACHE_DIRS - REMAINING_DIRS)) __pycache__ directories"
echo "  - Removed $((PYC_FILES - REMAINING_FILES)) .pyc files"
echo ""

# Check for --restart flag
if [[ "$1" == "--restart" ]]; then
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
        echo "  pkill -f uvicorn && cd $PROJECT_ROOT && python -m uvicorn app:app --host 0.0.0.0 --port 9527 &"
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
