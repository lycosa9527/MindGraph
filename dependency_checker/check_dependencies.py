#!/usr/bin/env python3
"""
MindGraph Dependency Checker

This script checks if all required dependencies are installed:
- Python packages from requirements.txt
- Node.js and npm installation
- D3.js Node.js dependencies

Usage:
    python check_dependencies.py
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def check_python_packages(verbose=True):
    """Check if all required Python packages are installed."""
    if verbose:
        logger.info("🔍 Checking Python packages...")

    required_packages = [
        'flask', 'requests', 'langchain', 'yaml', 'dotenv',
        'nest_asyncio', 'pyee', 'playwright', 'pillow'
    ]
    package_mapping = {
        'yaml': 'yaml',
        'dotenv': 'dotenv',
        'pillow': 'PIL',
    }

    missing_packages = []
    for package in required_packages:
        try:
            import_name = package_mapping.get(package, package)
            __import__(import_name)
            if verbose:
                logger.debug(f"Successfully imported {package} as {import_name}")
        except ImportError as e:
            if verbose:
                logger.debug(f"Failed to import {package} as {import_name}: {e}")
            missing_packages.append(package)

    if missing_packages:
        if verbose:
            logger.error(f"❌ Missing Python packages: {', '.join(missing_packages)}")
            logger.info("Please install missing packages with:")
            logger.info("   pip install -r requirements.txt")
        return False

    if verbose:
        logger.info("✅ All Python packages are installed!")
    return True

def check_playwright_browsers(verbose=True):
    """Check if Playwright browsers are installed."""
    if verbose:
        logger.info("🔍 Checking Playwright browsers...")
    
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Try to launch Chrome to check if it's installed
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                if verbose:
                    logger.info("✅ Playwright Chrome browser is installed")
                return True
            except Exception as e:
                if verbose:
                    logger.error(f"❌ Playwright Chrome browser is not installed: {e}")
                return False
    except ImportError:
        if verbose:
            logger.error("❌ Playwright package is not installed")
        return False

def check_nodejs_installation(verbose=True):
    """Check if Node.js and npm are installed."""
    if verbose:
        logger.info("🔍 Checking Node.js installation...")
    
    # Check Node.js
    try:
        node_version = subprocess.run(['node', '--version'], 
                                    capture_output=True, text=True, check=True)
        if verbose:
            logger.info(f"✅ Node.js {node_version.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        if verbose:
            logger.error("❌ Node.js is not installed or not in PATH")
        return False
    
    # Check npm - try multiple approaches for Windows compatibility
    npm_found = False
    npm_version = None
    
    # Try direct npm command
    try:
        result = subprocess.run(['npm', '--version'], 
                              capture_output=True, text=True, check=True)
        npm_version = result.stdout.strip()
        npm_found = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Try with shell=True for Windows PowerShell compatibility
    if not npm_found:
        try:
            result = subprocess.run('npm --version', 
                                  shell=True, capture_output=True, text=True, check=True)
            npm_version = result.stdout.strip()
            npm_found = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    
    # Try using where/which to find npm
    if not npm_found:
        try:
            if os.name == 'nt':  # Windows
                result = subprocess.run(['where', 'npm'], 
                                      capture_output=True, text=True, check=True)
            else:  # Unix/Linux/macOS
                result = subprocess.run(['which', 'npm'], 
                                      capture_output=True, text=True, check=True)
            if result.stdout.strip():
                # Try running npm with the found path
                npm_path = result.stdout.strip().split('\n')[0]
                result = subprocess.run([npm_path, '--version'], 
                                      capture_output=True, text=True, check=True)
                npm_version = result.stdout.strip()
                npm_found = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    
    if npm_found and npm_version:
        if verbose:
            logger.info(f"✅ npm {npm_version}")
        return True
    else:
        if verbose:
            logger.error("❌ npm is not installed or not in PATH")
        return False

def check_d3js_dependencies(verbose=True):
    """Check if Node.js dependencies are installed in d3.js directory."""
    if verbose:
        logger.info("🔍 Checking D3.js dependencies...")
    
    # Get the script directory and find d3.js folder
    script_dir = Path(__file__).parent
    d3js_dir = script_dir.parent / 'd3.js'
    
    # Check if d3.js directory exists
    if not d3js_dir.exists():
        if verbose:
            logger.error(f"❌ D3.js directory not found: {d3js_dir}")
        return False
    
    # Check if package.json exists
    package_json = d3js_dir / 'package.json'
    if not package_json.exists():
        if verbose:
            logger.error(f"❌ package.json not found in D3.js directory")
        return False
    
    # Check if node_modules exists
    node_modules = d3js_dir / 'node_modules'
    if not node_modules.exists():
        if verbose:
            logger.error("❌ node_modules directory not found in D3.js directory")
            logger.info("Please run the following commands:")
            logger.info(f"   cd {d3js_dir}")
            logger.info("   npm install")
        return False
    
    # Check for key D3.js dependencies
    key_dependencies = [
        'd3-array', 'd3-axis', 'd3-scale', 'd3-selection', 
        'd3-shape', 'd3-color', 'd3-format'
    ]
    
    missing_deps = []
    for dep in key_dependencies:
        dep_path = node_modules / dep
        if not dep_path.exists():
            missing_deps.append(dep)
    
    if missing_deps:
        if verbose:
            logger.error(f"❌ Missing D3.js dependencies: {', '.join(missing_deps)}")
            logger.info("Please run the following commands:")
            logger.info(f"   cd {d3js_dir}")
            logger.info("   npm install")
        return False
    
    if verbose:
        logger.info("✅ All D3.js dependencies are installed!")
    return True

def print_setup_instructions():
    """Print setup instructions for missing dependencies."""
    logger.info("""
================================================================================
🚀 MindGraph Setup Instructions

If you are seeing this message, you may be missing required dependencies.

🖥️ Option 1: Run Locally (Recommended for Developers)

1. Install Python dependencies:
   pip install -r requirements.txt

2. Install Node.js (18.19+ or 20+): https://nodejs.org/

3. Install D3.js dependencies:
   cd d3.js
   npm install
   cd ..

4. Install Playwright Chrome browser:
   python -m playwright install chromium

5. Start the Flask app:
   python app.py

6. Open your browser and visit: http://localhost:9527

🐳 Option 2: Run with Docker (No Node.js or Python setup needed)

1. Install Docker: https://www.docker.com/products/docker-desktop
2. Build the Docker image:
   docker build -t mindgraph .
3. Run the Docker container:
   docker run -p 9527:9527 mindgraph
4. Open your browser and visit: http://localhost:9527

📋 Manual Dependency Check

If you want to check dependencies manually:
- Python packages: pip list
- Node.js version: node --version
- npm version: npm --version
- D3.js dependencies: cd d3.js && npm list
- Playwright browsers: python -m playwright --version
================================================================================
""")

def install_python_packages():
    """Install Python packages from requirements.txt."""
    logger.info("🔧 Installing Python packages...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                      capture_output=True, text=True, check=True)
        logger.info("✅ Python packages installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install Python packages: {e.stderr}")
        return False

def install_d3js_dependencies():
    """Install D3.js dependencies."""
    logger.info("🔧 Installing D3.js dependencies...")
    d3js_dir = Path(__file__).parent.parent / 'd3.js'
    
    try:
        # Change to d3.js directory and run npm install
        subprocess.run(['npm', 'install'], 
                      cwd=d3js_dir, capture_output=True, text=True, check=True)
        logger.info("✅ D3.js dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install D3.js dependencies: {e.stderr}")
        return False

def install_playwright_browsers():
    """Install Playwright Chrome browser only."""
    logger.info("🔧 Installing Playwright Chrome browser...")
    try:
        # Install only Chrome browser (chromium)
        subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], 
                      capture_output=True, text=True, check=True)
        logger.info("✅ Playwright Chrome browser installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install Playwright Chrome browser: {e.stderr}")
        return False

def print_nodejs_installation_guide():
    """Print comprehensive Node.js installation guide."""
    logger.info("""
===============================================================================
📥 NODE.JS INSTALLATION GUIDE
===============================================================================

Node.js is required for running D3.js dependencies. Here are installation options:

🖥️ WINDOWS INSTALLATION:

Option 1: Download from Official Website (Recommended)
1. Visit: https://nodejs.org/
2. Download the LTS version (Recommended for most users)
3. Run the installer (.msi file)
4. Follow the installation wizard
5. Restart your terminal/command prompt

Option 2: Using Chocolatey (if installed)
   choco install nodejs

Option 3: Using Winget (Windows 10/11)
   winget install OpenJS.NodeJS

Option 4: Using Scoop (if installed)
   scoop install nodejs

🍎 macOS INSTALLATION:

Option 1: Download from Official Website
1. Visit: https://nodejs.org/
2. Download the macOS installer (.pkg file)
3. Run the installer and follow the instructions

Option 2: Using Homebrew (Recommended)
   brew install node

Option 3: Using MacPorts
   sudo port install nodejs

🐧 LINUX INSTALLATION:

Ubuntu/Debian:
   curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
   sudo apt-get install -y nodejs

CentOS/RHEL/Fedora:
   curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -
   sudo yum install -y nodejs

Arch Linux:
   sudo pacman -S nodejs npm

📋 VERIFICATION:

After installation, verify Node.js is installed:
   node --version
   npm --version

Both commands should return version numbers.

🔄 RESTART REQUIRED:

After installing Node.js, you may need to:
1. Close and reopen your terminal/command prompt
2. Restart your IDE/editor
3. Run the dependency checker again

===============================================================================
""")

def install_nodejs_automatically():
    """Attempt to install Node.js automatically based on the platform."""
    logger.info("🔧 Attempting automatic Node.js installation...")
    
    platform = sys.platform.lower()
    
    try:
        if platform.startswith('win'):
            # Windows - try winget first, then chocolatey
            # Try winget (Windows 10/11)
            try:
                subprocess.run(['winget', 'install', 'OpenJS.NodeJS'], 
                              capture_output=True, text=True, check=True)
                logger.info("✅ Node.js installed successfully via winget!")
                logger.info("Please restart your terminal and run the dependency checker again.")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Try chocolatey
                try:
                    subprocess.run(['choco', 'install', 'nodejs', '-y'], 
                                  capture_output=True, text=True, check=True)
                    logger.info("✅ Node.js installed successfully via Chocolatey!")
                    logger.info("Please restart your terminal and run the dependency checker again.")
                    return True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass
            
        elif platform.startswith('darwin'):
            # macOS - try Homebrew
            try:
                subprocess.run(['brew', 'install', 'node'], 
                              capture_output=True, text=True, check=True)
                logger.info("✅ Node.js installed successfully via Homebrew!")
                logger.info("Please restart your terminal and run the dependency checker again.")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        
        elif platform.startswith('linux'):
            # Linux - try package manager
            # Try apt (Ubuntu/Debian)
            try:
                # Add NodeSource repository
                subprocess.run(['curl', '-fsSL', 'https://deb.nodesource.com/setup_lts.x'], 
                             capture_output=True, text=True, check=True)
                subprocess.run(['sudo', 'apt-get', 'install', '-y', 'nodejs'], 
                              capture_output=True, text=True, check=True)
                logger.info("✅ Node.js installed successfully via apt!")
                logger.info("Please restart your terminal and run the dependency checker again.")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        
        logger.info("❌ Automatic installation not available for this platform.")
        logger.info("Please install Node.js manually using the guide above.")
        return False
        
    except Exception as e:
        logger.error(f"❌ Automatic installation failed: {e}")
        logger.info("Please install Node.js manually using the guide above.")
        return False

def prompt_user_installation():
    """Prompt user for automatic installation of missing dependencies."""
    print("\nMissing dependencies detected. Would you like to install them automatically?")
    
    while True:
        try:
            choice = input("Install all missing dependencies? (y/n): ").strip().lower()
            if choice in ['y', 'yes']:
                return 'install_all'
            elif choice in ['n', 'no']:
                return 'skip'
            else:
                print("Please enter 'y' for yes or 'n' for no")
        except KeyboardInterrupt:
            print("\nInstallation cancelled by user.")
            return 'skip'

def main():
    """Main function to run all dependency checks."""
    logger.info("🔍 MindGraph Dependency Checker")
    
    # Check Python packages
    python_ok = check_python_packages(verbose=True)
    
    # Check Node.js installation
    nodejs_ok = check_nodejs_installation(verbose=True)
    
    # Check D3.js dependencies
    d3js_ok = check_d3js_dependencies(verbose=True)
    
    # Check Playwright browsers
    playwright_ok = check_playwright_browsers(verbose=True)
    
    # Summary
    if python_ok and nodejs_ok and d3js_ok and playwright_ok:
        logger.info("✅ All dependencies are properly installed!")
        logger.info("🚀 Application is ready to start!")
        return 0
    else:
        logger.error("❌ Some dependencies are missing!")
        
        # Show what's missing
        missing_items = []
        if not python_ok:
            missing_items.append("Python packages")
        if not nodejs_ok:
            missing_items.append("Node.js/npm")
        if not d3js_ok:
            missing_items.append("D3.js dependencies")
        if not playwright_ok:
            missing_items.append("Playwright Chrome browser")
        
        logger.info(f"Missing: {', '.join(missing_items)}")
        
        # Provide installation options
        choice = prompt_user_installation()
        
        if choice == 'install_all':  # Install all missing
            success = True
            if not python_ok:
                success = success and install_python_packages()
            if not nodejs_ok:
                logger.info("🔧 Attempting to install Node.js automatically...")
                if install_nodejs_automatically():
                    logger.info("✅ Node.js installed successfully!")
                    logger.info("Please restart your terminal and run the dependency checker again.")
                    return 0
                else:
                    logger.error("❌ Node.js installation failed")
                    print_nodejs_installation_guide()
                    success = False
            if not d3js_ok:
                success = success and install_d3js_dependencies()
            if not playwright_ok:
                success = success and install_playwright_browsers()
            
            if success:
                logger.info("✅ All installable dependencies have been installed!")
                logger.info("🚀 You can now run: python app.py")
                return 0
            else:
                logger.error("❌ Some dependencies could not be installed automatically")
                print_setup_instructions()
                return 1
                
        else:  # Skip installation or manual installation
            logger.info("To fix missing dependencies manually:")
            if not python_ok:
                logger.info("1. Install Python packages: pip install -r requirements.txt")
            if not nodejs_ok:
                logger.info("2. Install Node.js: https://nodejs.org/")
            if not d3js_ok:
                logger.info("3. Install D3.js dependencies: cd d3.js && npm install")
            if not playwright_ok:
                logger.info("4. Install Playwright Chrome browser: python -m playwright install chromium")
            print_setup_instructions()
            return 1

if __name__ == '__main__':
    sys.exit(main()) 