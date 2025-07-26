# Dependency Checker

This folder contains all the dependency checking and installation tools for D3.js_Dify.

## Files

### Core Scripts
- **`check_dependencies.py`** - Main command-line dependency checker
- **`check_dependencies_gui.py`** - Graphical user interface for dependency checking

### Convenience Scripts
- **`check_dependencies.bat`** - Windows batch script for CLI checker
- **`check_dependencies_gui.bat`** - Windows batch script for GUI checker
- **`check_dependencies.sh`** - Unix/Linux/macOS shell script for CLI checker

## Usage

### From Project Root
```bash
# Command line interface
python dependency_checker/check_dependencies.py
dependency_checker/check_dependencies.bat  # Windows
dependency_checker/check_dependencies.sh   # Linux/macOS

# Graphical interface
python dependency_checker/check_dependencies_gui.py
dependency_checker/check_dependencies_gui.bat  # Windows
```

### From This Directory
```bash
# Command line interface
python check_dependencies.py
check_dependencies.bat  # Windows
./check_dependencies.sh  # Linux/macOS

# Graphical interface
python check_dependencies_gui.py
check_dependencies_gui.bat  # Windows
```

## Features

- **Python Package Checking**: Verifies all required Python packages from requirements.txt
- **Node.js Installation**: Checks if Node.js and npm are installed
- **D3.js Dependencies**: Ensures all Node.js dependencies in the d3.js directory are installed
- **Playwright Browser**: Checks if Playwright Chrome browser is installed
- **Simplified Interactive Installation**: Simple "Yes/No" prompt for installing all missing dependencies
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Installation Options

- **Yes**: Install all missing dependencies automatically
- **No**: Skip installation and get manual instructions

The system automatically:
- Installs Python packages using `pip install -r requirements.txt`
- Installs D3.js dependencies using `npm install` in the d3.js directory
- Installs Playwright Chrome browser using `python -m playwright install chromium`
- Installs Node.js using platform-specific package managers (winget, chocolatey, homebrew, apt, etc.)
- Provides comprehensive Node.js installation guides for all platforms

The dependency checker now provides a simple "Yes/No" prompt for installing all missing dependencies at once. 