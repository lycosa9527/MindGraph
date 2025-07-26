#!/bin/bash

echo "========================================"
echo "D3.js_Dify Dependency Checker"
echo "========================================"
echo

cd "$(dirname "$0")"
python3 check_dependencies.py

echo
echo "Press Enter to exit..."
read 