#!/bin/bash
#
# Qdrant Installation Script (Backward Compatibility Wrapper)
# ============================================================
# 
# This script is a wrapper for install_dependencies.sh
# It maintains backward compatibility with existing references.
#
# Usage:
#   chmod +x install_qdrant.sh
#   sudo ./install_qdrant.sh
#
# @author MindSpring Team
# @date December 2025
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/install_dependencies.sh" --qdrant-only "$@"
