#!/usr/bin/env python3
"""
MindGraph Complete Setup Script

This script handles the complete installation and setup of MindGraph, including:
- Python dependency installation (FastAPI stack)
- Playwright browser setup
- Logging system configuration
- Comprehensive verification

Requirements:
- Python 3.8+
- pip package manager
- Internet connection for package downloads

Usage:
    python scripts/setup.py
    # Or from scripts directory:
    cd scripts && python setup.py

Author: MindGraph Development Team
Version: See VERSION file (centralized version management)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import subprocess
import sys
import platform
import os
import importlib
import time
import shutil
import zipfile
from pathlib import Path
from typing import List, Dict, Optional


# Constants
CORE_DEPENDENCIES = {
    # Web framework (FastAPI)
    'fastapi': 'FastAPI',
    'uvicorn': 'Uvicorn',
    'starlette': 'starlette',
    'pydantic': 'pydantic',
    'pydantic_settings': 'pydantic-settings',
    'email_validator': 'email-validator',
    'jinja2': 'jinja2',

    # HTTP and networking (async)
    'aiohttp': 'aiohttp',
    'httpx': 'httpx',
    'requests': 'requests',
    'openai': 'openai',
    'multipart': 'python-multipart',
    'websockets': 'websockets',

    # AI and language processing
    'langchain': 'langchain',
    'langchain_community': 'langchain-community',
    'langchain_core': 'langchain-core',
    'langchain_openai': 'langchain-openai',
    'langgraph': 'langgraph',
    'langgraph_checkpoint': 'langgraph-checkpoint',
    'dashscope': 'dashscope',

    # Configuration and environment
    'yaml': 'PyYAML',
    'dotenv': 'python-dotenv',

    # Async and concurrency
    'nest_asyncio': 'nest-asyncio',
    'aiofiles': 'aiofiles',

    # Browser automation and image processing
    'playwright': 'playwright',
    'PIL': 'Pillow',

    # Database and authentication
    'sqlalchemy': 'SQLAlchemy',
    'alembic': 'alembic',
    'jose': 'python-jose',
    'bcrypt': 'bcrypt',  # passlib removed in v4.12.0, using bcrypt directly
    'captcha': 'captcha',
    'Crypto': 'pycryptodome',

    # System utilities
    'psutil': 'psutil',
    'watchfiles': 'watchfiles',

    # JSON serialization
    'orjson': 'orjson'
}

PROGRESS_BAR_LENGTH = 30
MAX_LINE_LENGTH = 100
SETUP_STEPS = 5

REQUIRED_LOG_FILES = [
    "uvicorn_access.log",
    "uvicorn_error.log",
    "app.log",
    "agent.log"
]

ESSENTIAL_FILES = [
    "VERSION",
    "main.py",
    "requirements.txt",
    "uvicorn_config.py"
]

ESSENTIAL_DIRECTORIES = [
    "logs",
    "data",
    "static",
    "templates",
    "routers",
    "models",
    "clients",
    "services",
    "config"
]

# Offline Chromium installation directory
BROWSERS_DIR = "browsers"
CHROMIUM_DIR = os.path.join(BROWSERS_DIR, "chromium")


class SetupError(Exception):
    """Custom exception for setup failures"""
    pass


def run_command(command: str, description: str, check: bool = True) -> bool:
    """
    Execute a shell command with proper error handling.

    Args:
        command: The shell command to execute
        description: Human-readable description of what the command does
        check: Whether to raise an exception on non-zero return code

    Returns:
        True if command succeeded, False otherwise

    Raises:
        SetupError: If check=True and command fails
    """
    print(f"[INFO] {description}...")

    try:
        result = subprocess.run(
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"[SUCCESS] {description} completed")
            return True
        else:
            print(f"[WARNING] {description} completed with warnings")
            if result.stderr:
                print(f"    Warning: {result.stderr.strip()}")
            return True

    except subprocess.SubprocessError as e:
        print(f"[ERROR] {description} failed: {e}")
        if check:
            raise SetupError(f"Command failed: {description}")
        return False


def run_command_with_progress(command: str, description: str, check: bool = True) -> bool:
    """
    Execute a shell command with real-time progress tracking and download speed.

    Args:
        command: The shell command to execute
        description: Human-readable description of what the command does
        check: Whether to raise an exception on non-zero return code

    Returns:
        True if command succeeded, False otherwise

    Raises:
        SetupError: If check=True and command fails
    """
    print(f"[INFO] {description}...")

    try:
        # Start the process with real-time output
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Track progress and download speed
        start_time = time.time()
        total_bytes = 0

        print("    [INFO] Downloading and installing packages...")

        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                line = output.strip()

                # Parse pip progress output
                if "Downloading" in line and "%" in line:
                    # Extract percentage and speed info
                    print(f"\r    [INFO] {line}", end='', flush=True)
                elif "Installing collected packages" in line:
                    print(f"\n    [INFO] {line}")
                elif "Successfully installed" in line:
                    print(f"    [SUCCESS] {line}")
                elif "Requirement already satisfied" in line:
                    print(f"    [INFO] {line}")
                elif "Collecting" in line:
                    package_name = line.split("Collecting ")[-1].split()[0]
                    print(f"    [INFO] Collecting {package_name}...")
                elif "Downloading" in line and "MB" in line:
                    # Extract download size and speed
                    if "MB" in line:
                        size_match = line.split("MB")[0].split()[-1]
                        try:
                            size_mb = float(size_match)
                            total_bytes += size_mb * 1024 * 1024
                        except ValueError:
                            pass
                    print(f"\r    [INFO] {line}", end='', flush=True)
                elif "Installing" in line and "..." in line:
                    print(f"\n    [INFO] {line}")
                elif "Successfully" in line:
                    print(f"    [SUCCESS] {line}")
                elif "ERROR:" in line or "FAILED" in line:
                    print(f"\n    [ERROR] {line}")
                elif line and not line.startswith("WARNING:"):
                    # Show other relevant output
                    if len(line) < MAX_LINE_LENGTH:  # Avoid very long lines
                        print(f"    [INFO] {line}")

        # Wait for process to complete
        return_code = process.poll()

        if return_code == 0:
            elapsed_time = time.time() - start_time
            if total_bytes > 0:
                avg_speed = total_bytes / elapsed_time / (1024 * 1024)  # MB/s
                print(f"\n    [SUCCESS] {description} completed in {elapsed_time:.1f}s (avg: {avg_speed:.1f} MB/s)")
            else:
                print(f"\n    [SUCCESS] {description} completed in {elapsed_time:.1f}s")
            return True
        else:
            print(f"\n    [ERROR] {description} failed with return code {return_code}")
            if check:
                raise SetupError(f"Command failed: {description}")
            return False

    except subprocess.SubprocessError as e:
        print(f"\n[ERROR] {description} failed: {e}")
        if check:
            raise SetupError(f"Command failed: {description}")
        return False


def check_python_version() -> bool:
    """
    Verify Python version compatibility.

    Returns:
        True if Python version is compatible

    Raises:
        SetupError: If Python version is incompatible
    """
    print("[INFO] Checking Python version...")

    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        raise SetupError(
            f"Python {version.major}.{version.minor} detected. "
            "MindGraph requires Python 3.8+"
        )

    print(f"[SUCCESS] Python {version.major}.{version.minor}.{version.micro} - Compatible")
    return True


def print_system_info() -> None:
    """Print system information for diagnostics"""
    print("[INFO] System Information:")
    print(f"    Platform: {platform.system()} {platform.release()}")
    print(f"    Architecture: {platform.machine()}")
    print(f"    Python: {sys.version}")
    print(f"    Python Executable: {sys.executable}")
    print(f"    Working Directory: {os.getcwd()}")
    print(f"    Available Memory: {get_available_memory():.1f} GB")
    print()


def get_available_memory() -> float:
    """Get available system memory in GB"""
    try:
        import psutil
        memory = psutil.virtual_memory()
        return memory.available / (1024**3)  # Convert to GB
    except ImportError:
        return 0.0


def get_package_version(package_name: str) -> str:
    """
    Get package version using modern importlib.metadata approach.

    Args:
        package_name: The package name to get version for

    Returns:
        Package version string or 'unknown' if not available
    """
    try:
        # Try modern approach first (Python 3.8+)
        from importlib.metadata import version
        return version(package_name)
    except ImportError:
        try:
            # Fallback for older Python versions
            import pkg_resources
            return pkg_resources.get_distribution(package_name).version
        except Exception:
            return 'unknown'


def check_pip() -> bool:
    """
    Verify pip package manager availability.

    Returns:
        True if pip is available

    Raises:
        SetupError: If pip is not available
    """
    print("[INFO] Checking pip availability...")

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            check=True,
            capture_output=True
        )
        print("[SUCCESS] pip is available")
        return True

    except (subprocess.CalledProcessError, FileNotFoundError):
        raise SetupError("pip not found. Please install pip first")


def check_dependencies_already_installed() -> bool:
    """
    Check if all required dependencies are already installed.

    Returns:
        True if all dependencies are already installed, False otherwise
    """
    print("[INFO] Checking if dependencies are already installed...")

    # Core dependencies to check (production only)
    core_dependencies = CORE_DEPENDENCIES

    missing_dependencies = []

    for module_name, package_name in core_dependencies.items():
        try:
            # Handle special cases for packages with different import names
            if module_name in ['PIL', 'multipart', 'yaml', 'dotenv', 'nest_asyncio', 'Crypto', 'jose', 'pydantic_settings', 'email_validator']:
                pass  # Module availability checked via importlib
            elif module_name == 'langchain_openai':
                importlib.import_module('langchain_openai')
            elif module_name == 'langgraph_checkpoint':
                importlib.import_module('langgraph_checkpoint')
            else:
                importlib.import_module(module_name)

        except ImportError:
            missing_dependencies.append(package_name)

    if not missing_dependencies:
        print("[SUCCESS] All Python dependencies are already installed!")
        return True
    else:
        print(f"[INFO] Missing dependencies: {', '.join(missing_dependencies)}")
        return False


def install_python_dependencies() -> bool:
    """
    Install Python dependencies from requirements.txt.

    Returns:
        True if installation succeeded

    Raises:
        SetupError: If requirements.txt not found or installation fails
    """
    print("\n[INFO] Installing Python dependencies...")

    # Check if dependencies are already installed
    if check_dependencies_already_installed():
        print("[INFO] Skipping Python dependency installation - already complete")
        return True

    # Check requirements.txt (we're already in project root from main())
    if not os.path.exists("requirements.txt"):
        raise SetupError("requirements.txt not found")

    print("[INFO] Installing packages with progress tracking...")

    # Use pip with progress bar and verbose output
    if not run_command_with_progress(
        f"{sys.executable} -m pip install -r requirements.txt --progress-bar on",
        "Installing Python packages"
    ):
        raise SetupError("Failed to install Python dependencies")

    print("[SUCCESS] Python dependencies installed successfully")
    return True


def check_playwright_already_installed() -> bool:
    """
    Check if Playwright and Chromium browser are already installed.

    Returns:
        True if Playwright is fully installed, False otherwise
    """
    print("[INFO] Checking if Playwright is already installed...")

    try:
        # Check if Playwright Python module is available
        from playwright.sync_api import sync_playwright

        # Try to launch Chromium to verify browser installation
        with sync_playwright() as p:
            try:
                # Try to launch with minimal options to avoid issues
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )

                # If browser launches successfully, consider it working regardless of version check
                print("[SUCCESS] Playwright Chromium already installed and working")
                browser.close()
                return True

            except Exception as e:
                error_msg = str(e).lower()
                if "chromium" in error_msg and "not found" in error_msg:
                    print("[INFO] Playwright module found but Chromium browser not installed")
                elif "font" in error_msg or "library" in error_msg:
                    print("[INFO] Playwright module found but system dependencies may be missing")
                else:
                    print(f"[INFO] Playwright module found but browser launch failed: {e}")
                return False

    except ImportError:
        print("[INFO] Playwright Python module not found")
        return False
    except Exception as e:
        print(f"[INFO] Playwright check failed: {e}")
        return False


def install_playwright() -> bool:
    """
    Install Playwright with Chromium browser only.

    Returns:
        True if installation succeeded

    Raises:
        SetupError: If Playwright installation fails
    """
    print("\n[INFO] Installing Playwright (Chromium only)...")

    # Check if Playwright is already installed
    if check_playwright_already_installed():
        print("[INFO] Skipping Playwright installation - already complete")
        return True

    os_name = platform.system().lower()
    print(f"[INFO] Platform: {platform.system()} {platform.release()}")

    # Show installation details
    print("[INFO] Installation includes:")
    print("    - Playwright Python package (already installed via pip)")
    print("    - Chromium browser binary (~150MB)")

    if os_name != "windows":
        print("    - System dependencies (fonts, libraries, etc.)")
        print("      - Font packages (libwoff1, libwebp7, etc.)")
        print("      - Graphics libraries (libgdk-pixbuf2.0-0, libegl1)")
        print("      - Audio libraries (libopus0, libvpx7)")
        print("      - Other system packages (~50-100MB)")

    # Use --with-deps flag for automatic system dependency installation
    print("\n[INFO] Installing Chromium browser with system dependencies...")

    if os_name == "windows":
        print("[INFO] Windows detected - using playwright install")

        # On Windows, --with-deps is less critical but still useful
        if not run_command_with_progress("playwright install chromium --with-deps", "Installing Chromium with dependencies"):
            print("[WARNING] Installation with --with-deps failed, trying without...")
            if not run_command_with_progress("playwright install chromium", "Installing Chromium"):
                raise SetupError(
                    "Playwright installation failed. "
                    "Try manually: playwright install chromium"
                )
    else:
        print("[INFO] Unix-like system detected - installing with system dependencies")
        print("[INFO] This will install fonts, libraries, and other system packages")
        print("[INFO] May require sudo/administrator privileges")

        # Use --with-deps to install everything in one command
        if not run_command_with_progress("playwright install chromium --with-deps", "Installing Chromium with system dependencies"):
            print("[WARNING] Installation with --with-deps failed")
            print("[INFO] Trying two-step installation (install-deps + install chromium)...")

            # Fallback to two-step process
            if not run_command_with_progress("playwright install-deps", "Installing system dependencies"):
                raise SetupError(
                    "Failed to install system dependencies. "
                    "This may require sudo/administrator privileges. "
                    "Try: sudo playwright install chromium --with-deps"
                )

            if not run_command_with_progress("playwright install chromium", "Installing Chromium browser"):
                raise SetupError("Failed to install Chromium browser")

    print("[SUCCESS] Playwright Chromium installed successfully")
    return True


def get_local_chromium_executable() -> Optional[str]:
    """
    Get the path to local Chromium executable if available.

    Returns:
        str or None: Path to Chromium executable, or None if not found
    """
    system = platform.system().lower()
    chromium_path = Path(CHROMIUM_DIR)

    if not chromium_path.exists():
        return None

    if system == "windows":
        exe_path = chromium_path / "chrome.exe"
        return str(exe_path) if exe_path.exists() else None
    elif system == "darwin":  # macOS
        possible_paths = [
            chromium_path / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
            chromium_path / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
            chromium_path / "chrome"
        ]
        for path in possible_paths:
            if path.exists():
                return str(path)
        return None
    else:  # Linux
        possible_paths = [
            chromium_path / "chrome-linux" / "chrome",
            chromium_path / "chrome"
        ]
        for path in possible_paths:
            if path.exists():
                return str(path)
        return None


def check_offline_chromium_installed() -> bool:
    """
    Check if offline Chromium is already installed in browsers/chromium/.

    Returns:
        True if offline Chromium is installed and working, False otherwise
    """
    local_chromium = get_local_chromium_executable()

    if not local_chromium or not os.path.exists(local_chromium):
        return False

    # Try to verify the executable works
    try:
        result = subprocess.run(
            [local_chromium, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"[INFO] Found offline Chromium: {version}")
            return True
    except Exception:
        pass

    return False


def get_platform_name():
    """Get platform name for zip extraction"""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "mac"
    elif system == "linux":
        return "linux"
    else:
        return system

def extract_chromium_zip() -> bool:
    """
    Extract Chromium from multi-platform zip file if it exists.
    Extracts only the platform-specific folder from chromium.zip.

    Returns:
        True if extraction succeeded or zip doesn't exist, False on error
    """
    zip_path = Path(BROWSERS_DIR) / "chromium.zip"
    chromium_dest_dir = Path(CHROMIUM_DIR)
    platform_name = get_platform_name()

    # Check if zip exists
    if not zip_path.exists():
        return False

    print(f"\n[INFO] Found Chromium zip file: {zip_path.name}")
    print(f"[INFO] Extracting {platform_name} platform for: {platform.system()}")

    # Check if already extracted
    if check_offline_chromium_installed():
        print("[INFO] Chromium already extracted - skipping")
        return True

    try:
        # Create browsers directory if it doesn't exist
        browsers_path = Path(BROWSERS_DIR)
        browsers_path.mkdir(exist_ok=True)

        # Remove existing chromium directory if it exists
        if chromium_dest_dir.exists():
            print("[INFO] Removing existing Chromium installation...")
            shutil.rmtree(chromium_dest_dir)

        # Check what platforms are available in zip
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            available_platforms = set()
            for name in zipf.namelist():
                if '/' in name:
                    platform_in_zip = name.split('/')[0]
                    if platform_in_zip in ['windows', 'linux', 'mac']:
                        available_platforms.add(platform_in_zip)

            if available_platforms:
                print(f"[INFO] Zip contains platforms: {', '.join(sorted(available_platforms))}")

            if platform_name not in available_platforms:
                print(f"[ERROR] {platform_name} platform not found in zip file")
                print(f"[INFO] Available platforms in zip: {', '.join(sorted(available_platforms))}")
                print(f"[INFO] Your platform ({platform.system()}) requires: {platform_name}")
                print("[INFO] Falling back to Playwright download...")
                return False

        # Extract zip file (only platform-specific folder)
        print(f"[INFO] Extracting {platform_name} platform from zip...")
        print("    This may take a few minutes (~150MB)...")

        with zipfile.ZipFile(zip_path, 'r') as zipf:
            # Get files for current platform
            platform_files = [f for f in zipf.namelist() if f.startswith(f'{platform_name}/')]
            total_files = len(platform_files)
            extracted = 0

            # Extract only platform-specific files
            for member in platform_files:
                # Remove platform prefix from path
                target_path = member[len(f'{platform_name}/'):]
                if target_path:  # Skip empty paths
                    # Extract to chromium directory
                    full_path = chromium_dest_dir / target_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)

                    # Extract file (use copyfileobj for better memory efficiency)
                    with zipf.open(member) as source:
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(full_path, 'wb') as target:
                            shutil.copyfileobj(source, target)

                    extracted += 1
                    if extracted % 100 == 0:
                        print(f"    Progress: {extracted}/{total_files} files...", end='\r')

        # Clear progress line and print completion
        print(f"    Progress: {extracted}/{total_files} files...")
        print("\n[SUCCESS] Chromium extracted successfully!")

        # Verify installation
        if check_offline_chromium_installed():
            print(f"[INFO] Chromium is now available at: {CHROMIUM_DIR}")
            return True
        else:
            print("[WARNING] Chromium extracted but verification failed")
            return False

    except Exception as e:
        print(f"[ERROR] Failed to extract Chromium zip: {e}")
        return False


def copy_playwright_chromium_to_offline() -> bool:
    """
    Copy Playwright's installed Chromium to browsers/chromium/ for offline use.
    This is a fallback if zip extraction is not available.

    Returns:
        True if copy succeeded, False otherwise
    """
    print("\n[INFO] Setting up offline Chromium installation...")

    # Check if already installed
    if check_offline_chromium_installed():
        print("[INFO] Offline Chromium already installed - skipping")
        return True

    # Get Playwright's Chromium path
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            playwright_chromium_path = p.chromium.executable_path
            if not playwright_chromium_path or not os.path.exists(playwright_chromium_path):
                print("[WARNING] Playwright Chromium not found - skipping offline copy")
                return False

            print(f"[INFO] Found Playwright Chromium at: {playwright_chromium_path}")

            # Find the Chromium directory (parent of executable)
            chromium_source_dir = os.path.dirname(playwright_chromium_path)

            # On macOS, Chromium.app is a bundle
            if platform.system().lower() == "darwin" and chromium_source_dir.endswith(".app"):
                chromium_source_dir = os.path.dirname(chromium_source_dir)

            # Create browsers directory if it doesn't exist
            browsers_path = Path(BROWSERS_DIR)
            browsers_path.mkdir(exist_ok=True)

            # Remove existing chromium directory if it exists
            chromium_dest_dir = Path(CHROMIUM_DIR)
            if chromium_dest_dir.exists():
                print("[INFO] Removing existing Chromium installation...")
                shutil.rmtree(chromium_dest_dir)

            # Copy Chromium directory
            print(f"[INFO] Copying Chromium to {CHROMIUM_DIR}...")
            print("    This may take a few minutes (~150MB)...")

            shutil.copytree(chromium_source_dir, chromium_dest_dir)

            # Verify installation
            if check_offline_chromium_installed():
                print("[SUCCESS] Offline Chromium installation complete!")
                print(f"[INFO] Chromium is now available at: {CHROMIUM_DIR}")
                return True
            else:
                print("[WARNING] Chromium copied but verification failed")
                return False

    except ImportError:
        print("[WARNING] Playwright not available - cannot copy Chromium")
        return False
    except Exception as e:
        print(f"[WARNING] Failed to copy Chromium for offline use: {e}")
        return False





def verify_dependencies() -> bool:
    """
    Verify all key dependencies are properly installed.

    Returns:
        True if all dependencies are verified

    Raises:
        SetupError: If dependency verification fails
    """
    print("\n[INFO] Verifying all dependencies...")

    # Core dependencies to check (production only)
    core_dependencies = CORE_DEPENDENCIES

    print("[INFO] Checking core dependencies...")
    failed_imports: List[str] = []
    successful_imports: List[str] = []

    total_deps = len(core_dependencies)
    for idx, (module_name, package_name) in enumerate(core_dependencies.items(), 1):
        print_progress(idx, total_deps, f"Checking {package_name}")

        try:
            # Handle special cases for packages with different import names
            if module_name == 'PIL':
                importlib.import_module('PIL')
                version = get_package_version('Pillow')
            elif module_name == 'multipart':
                importlib.import_module('multipart')
                version = get_package_version('python-multipart')
            elif module_name == 'yaml':
                importlib.import_module('yaml')
                version = get_package_version('PyYAML')
            elif module_name == 'dotenv':
                importlib.import_module('dotenv')
                version = get_package_version('python-dotenv')
            elif module_name == 'nest_asyncio':
                importlib.import_module('nest_asyncio')
                version = get_package_version('nest-asyncio')
            elif module_name == 'Crypto':
                importlib.import_module('Crypto.Cipher')
                version = get_package_version('pycryptodome')
            elif module_name == 'jose':
                importlib.import_module('jose.jwt')
                version = get_package_version('python-jose')
            elif module_name == 'pydantic_settings':
                importlib.import_module('pydantic_settings')
                version = get_package_version('pydantic-settings')
            elif module_name == 'email_validator':
                importlib.import_module('email_validator')
                version = get_package_version('email-validator')
            elif module_name == 'langchain_openai':
                importlib.import_module('langchain_openai')
                version = get_package_version('langchain-openai')
            elif module_name == 'langgraph_checkpoint':
                importlib.import_module('langgraph_checkpoint')
                version = get_package_version('langgraph-checkpoint')
            else:
                importlib.import_module(module_name)
                version = get_package_version(package_name)

            print(f"    [SUCCESS] {package_name:<20} - {version}")
            successful_imports.append(package_name)

        except ImportError as e:
            print(f"    [ERROR] {package_name:<20} - Import failed: {e}")
            failed_imports.append(package_name)
        except Exception as e:
            print(f"    [WARNING] {package_name:<20} - Version check failed: {e}")
            successful_imports.append(package_name)

    # Summary
    print("\n[INFO] Dependency Check Summary:")
    print(f"    [SUCCESS] Successful: {len(successful_imports)}/{len(core_dependencies)}")
    print(f"    [ERROR] Failed: {len(failed_imports)}/{len(core_dependencies)}")

    if failed_imports:
        raise SetupError(
            f"Failed dependencies: {', '.join(failed_imports)}. "
            "Please reinstall: pip install -r requirements.txt"
        )

    print("[SUCCESS] All core dependencies verified successfully!")
    return True


def verify_playwright_browsers() -> bool:
    """
    Verify Playwright browsers are properly installed.

    Returns:
        True if browsers are verified

    Raises:
        SetupError: If browser verification failed
    """
    print("\n[INFO] Verifying Playwright browsers...")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Check if Chromium is available
            try:
                browser = p.chromium.launch(headless=True)

                # Try to get version, but don't worry if it fails
                try:
                    if hasattr(browser, 'version') and callable(browser.version):
                        version = browser.version()
                        print(f"    [SUCCESS] Chromium browser - {version}")
                    elif hasattr(browser, 'version'):
                        version = browser.version
                        print(f"    [SUCCESS] Chromium browser - {version}")
                    else:
                        print("    [SUCCESS] Chromium browser - Working")
                except Exception:
                    print("    [SUCCESS] Chromium browser - Working")

                browser.close()

                # Additional verification for system dependencies
                if platform.system().lower() != "windows":
                    print("    [INFO] Verifying system dependencies...")
                    try:
                        # Test browser launch with system dependency flags
                        browser = p.chromium.launch(
                            headless=True,
                            args=['--no-sandbox', '--disable-dev-shm-usage']
                        )
                        browser.close()
                        print("    [SUCCESS] System dependencies verified (fonts, libraries)")
                    except Exception as e:
                        print(f"    [WARNING] System dependency warning: {e}")
                        print("    [INFO] This may affect rendering quality but browser should work")

                return True

            except Exception as e:
                print(f"    [ERROR] Chromium browser - Failed to launch: {e}")
                if "font" in str(e).lower() or "library" in str(e).lower():
                    print("    [INFO] This may be a system dependency issue")
                    print("    [INFO] Try: playwright install-deps")
                raise SetupError("Chromium browser verification failed")

    except ImportError:
        raise SetupError("Playwright module not importable")
    except Exception as e:
        raise SetupError(f"Browser verification failed: {e}")


def verify_file_structure() -> bool:
    """
    Verify essential files and directories exist.

    Returns:
        True if file structure is verified

    Raises:
        SetupError: If file structure verification fails
    """
    print("\n[INFO] Verifying file structure...")

    # Check files (we're already in project root from main())
    for file_path in ESSENTIAL_FILES:
        if os.path.exists(file_path):
            print(f"    [SUCCESS] {file_path}")
        else:
            raise SetupError(f"Essential file missing: {file_path}")

    # Check directories
    for dir_path in ESSENTIAL_DIRECTORIES:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            print(f"    [SUCCESS] {dir_path}/")
        else:
            raise SetupError(f"Essential directory missing: {dir_path}/")

    # Check log files
    for log_file in REQUIRED_LOG_FILES:
        log_path = os.path.join("logs", log_file)
        if os.path.exists(log_path):
            print(f"    [SUCCESS] logs/{log_file}")
        else:
            raise SetupError(f"Log file missing: logs/{log_file}")

    print("[SUCCESS] File structure verified successfully!")
    return True


def print_banner() -> None:
    """Display the MindGraph ASCII banner"""
    banner = """
    ███╗   ███╗██╗███╗   ██╗██████╗ ███╗   ███╗ █████╗ ████████╗███████╗
    ████╗ ████║██║████╗  ██║██╔══██╗████╗ ████║██╔══██╗╚══██╔══╝██╔════╝
    ██╔████╔██║██║██╔██╗ ██║██║  ██║██╔████╔██║███████║   ██║   █████╗
    ██║╚██╔╝██║██║██║╚██╗██║██║  ██║██║╚██╔╝██║██╔══██║   ██║   ██╔══╝
    ██║ ╚═╝ ██║██║██║ ╚████║██████╔╝██║ ╚═╝ ██║██║  ██║   ██║   ███████╗
    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝
================================================================================
    MindGraph - AI-Powered Graph Generation Application
    ==================================================
    """
    print(banner)


def print_progress(current: int, total: int, description: str = "") -> None:
    """Print a simple progress indicator"""
    percentage = (current / total) * 100
    bar_length = PROGRESS_BAR_LENGTH
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)

    if description:
        print(f"\r[INFO] {description} [{bar}] {percentage:.1f}% ({current}/{total})", end='', flush=True)
    else:
        print(f"\r[INFO] Progress [{bar}] {percentage:.1f}% ({current}/{total})", end='', flush=True)

    if current == total:
        print()  # New line when complete


def check_logs_already_configured() -> bool:
    """
    Check if the logging system is already properly configured.

    Returns:
        True if logs are already configured, False otherwise
    """
    print("[INFO] Checking if logging system is already configured...")

    try:
        # We're already in project root from main()
        logs_dir = "logs"

        # Check if logs directory exists
        if not os.path.exists(logs_dir):
            print("[INFO] Logs directory not found")
            return False

        # Check if all required log files exist
        log_files = REQUIRED_LOG_FILES

        missing_files = []
        for log_file in log_files:
            log_path = os.path.join(logs_dir, log_file)
            if not os.path.exists(log_path):
                missing_files.append(log_file)

        if not missing_files:
            print("[SUCCESS] Logging system already configured - all files present")
            return True
        else:
            print(f"[INFO] Missing log files: {', '.join(missing_files)}")
            return False

    except Exception as e:
        print(f"[INFO] Logs check failed: {e}")
        return False


def setup_logs_directory() -> bool:
    """
    Create logs directory and set proper permissions.

    Returns:
        True if setup succeeded

    Raises:
        SetupError: If logs setup fails
    """
    print("[INFO] Setting up logging system...")

    # Check if logs are already configured
    if check_logs_already_configured():
        print("[INFO] Skipping logs setup - already configured")
        return True

    try:
        # We're already in project root from main()
        logs_dir = "logs"

        # Create logs directory if it doesn't exist
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, mode=0o755)
            print("    [SUCCESS] Created logs directory")
        else:
            print("    [INFO] Logs directory already exists")

        # Create log files if they don't exist
        log_files = REQUIRED_LOG_FILES

        for log_file in log_files:
            log_path = os.path.join(logs_dir, log_file)
            if not os.path.exists(log_path):
                # Create empty log file
                with open(log_path, 'w'):
                    pass
                print(f"    [SUCCESS] Created log file: {log_file}")
            else:
                print(f"    [INFO] Log file exists: {log_file}")

        # Set proper permissions (755 for directory, 644 for files)
        os.chmod(logs_dir, 0o755)

        # Set file permissions
        for log_file in log_files:
            log_path = os.path.join(logs_dir, log_file)
            if os.path.isfile(log_path):
                os.chmod(log_path, 0o644)

        print("[SUCCESS] Logging system configured")
        return True

    except Exception as e:
        raise SetupError(f"Failed to setup logging system: {e}")


def setup_data_directory() -> bool:
    """
    Create data directory for database files.

    Returns:
        True if setup succeeded

    Raises:
        SetupError: If data directory setup fails
    """
    print("[INFO] Setting up data directory...")

    try:
        # We're already in project root from main()
        data_dir = "data"

        # Create data directory if it doesn't exist
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, mode=0o755)
            print("    [SUCCESS] Created data directory")
        else:
            print("    [INFO] Data directory already exists")

        # Set proper permissions (755 for directory)
        os.chmod(data_dir, 0o755)

        print("[SUCCESS] Data directory configured")
        return True

    except Exception as e:
        raise SetupError(f"Failed to setup data directory: {e}")


def setup_application_directories() -> bool:
    """
    Create application-specific directories needed at runtime.

    Creates:
    - static/images/ - for uploaded images
    - tests/images/ - for test images
    - temp_images/ - for temporary PNG files

    Returns:
        True if setup succeeded

    Raises:
        SetupError: If directory setup fails
    """
    print("[INFO] Setting up application directories...")

    try:
        # We're already in project root from main()
        directories_to_create = [
            ("static/images", "Static images"),
            ("tests/images", "Test images"),
            ("temp_images", "Temporary images")
        ]

        for dir_path, description in directories_to_create:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, mode=0o755)
                print(f"    [SUCCESS] Created {description} directory: {dir_path}/")
            else:
                print(f"    [INFO] {description} directory already exists: {dir_path}/")

            # Set proper permissions (755 for directory)
            os.chmod(dir_path, 0o755)

        print("[SUCCESS] Application directories configured")
        return True

    except Exception as e:
        raise SetupError(f"Failed to setup application directories: {e}")


def cleanup_temp_files() -> None:
    """Clean up any temporary files created during setup"""
    try:
        # We're already in project root from main()
        debug_script = "debug_playwright.py"
        if os.path.exists(debug_script):
            os.remove(debug_script)
            print("[INFO] Cleaned up temporary debug script")
    except Exception as e:
        print(f"[WARNING] Could not clean up temporary files: {e}")


def print_setup_summary(setup_summary: Dict[str, bool]) -> None:
    """Print a formatted setup summary"""
    print("\n[INFO] Setup Summary:")

    if setup_summary['python_deps']:
        print("    ✅ Python dependencies - Installed/Updated")
    else:
        print("    ⏭️  Python dependencies - Already installed (skipped)")

    if setup_summary['playwright']:
        print("    ✅ Playwright browser - Installed/Updated")
    else:
        print("    ⏭️  Playwright browser - Already installed (skipped)")

    if setup_summary.get('offline_chromium', False):
        print("    ✅ Offline Chromium - Installed in browsers/chromium/")
    elif check_offline_chromium_installed():
        print("    ⏭️  Offline Chromium - Already installed (skipped)")
    else:
        print("    ⏭️  Offline Chromium - Not installed (optional)")

    if setup_summary['logs']:
        print("    ✅ Logging system - Configured")
    else:
        print("    ⏭️  Logging system - Already configured (skipped)")


def print_next_steps() -> None:
    """Print next steps for the user"""
    print("\n[INFO] Next steps:")
    print("    1. Copy env.example to .env and configure your API keys")
    print("    2. Run: python main.py")
    print("    3. Open http://localhost:9527 in your browser")

    # Show platform-specific hints
    os_name = platform.system().lower()
    if os_name == "linux":
        print("\n[INFO] For Linux deployment:")
        print("    - System dependencies: sudo bash scripts/install_linux_dependencies.sh")
        print("    - Production deployment: ./scripts/setup_systemd.sh")
        print("    - Then use: sudo systemctl start/stop/restart mindgraph")
        print("    - See docs/LINUX_DEPLOYMENT.md for detailed instructions")

    print("\n[INFO] For more information, see README.md")


def main() -> None:
    """
    Main setup function that orchestrates the entire installation process.

    Raises:
        SetupError: If any step fails
        SystemExit: On successful completion or user interruption
    """
    start_time = time.time()

    # Get project root and change to it
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(script_dir) == "scripts":
        project_root = os.path.dirname(script_dir)
    else:
        project_root = script_dir

    # Change to project root directory for all operations
    original_cwd = os.getcwd()
    os.chdir(project_root)

    # Display the MindGraph banner
    print_banner()
    print("[INFO] Starting MindGraph Complete Setup")
    print("=" * 60)
    print("[INFO] Smart Setup: Will skip steps that are already complete")
    print("=" * 60)

    # Show platform-specific notes
    os_name = platform.system().lower()
    if os_name != "windows":
        print("[INFO] Note: On Linux/macOS, system dependencies will be installed")
        print("    This may require sudo privileges for some packages")
        print("    If you encounter permission errors, try: sudo python scripts/setup.py")
        print()

    # Track what was actually performed vs skipped
    setup_summary = {
        'python_deps': False,
        'playwright': False,
        'logs': False,
        'offline_chromium': False
    }

    try:
        # Step 1: Environment checks
        print(f"[STEP 1/{SETUP_STEPS}] Environment validation...")
        print_system_info()
        check_python_version()
        check_pip()
        print("[SUCCESS] Environment validation completed")

        # Step 2: Install Python dependencies
        print(f"\n[STEP 2/{SETUP_STEPS}] Python dependencies...")
        if install_python_dependencies():
            setup_summary['python_deps'] = True

        # Step 3: Install Playwright
        print(f"\n[STEP 3/{SETUP_STEPS}] Playwright browser...")

        # First, try to extract from zip if available (fastest option)
        chromium_from_zip = False
        zip_path = Path(BROWSERS_DIR) / "chromium.zip"

        if zip_path.exists():
            print("[INFO] Found chromium.zip - attempting extraction...")
            try:
                if extract_chromium_zip():
                    chromium_from_zip = True
                    setup_summary['offline_chromium'] = True
                    print("[SUCCESS] Using Chromium from zip file - skipping Playwright download")
                else:
                    print("[WARNING] Zip extraction failed, falling back to Playwright download")
            except Exception as e:
                print(f"[WARNING] Error extracting zip: {e}")
                print("[INFO] Falling back to Playwright download...")
        else:
            print("[INFO] No chromium.zip found - will download via Playwright")

        # If zip extraction didn't work, install via Playwright
        if not chromium_from_zip:
            if install_playwright():
                setup_summary['playwright'] = True

                # Copy Chromium for offline use (optional, non-blocking)
                try:
                    if copy_playwright_chromium_to_offline():
                        setup_summary['offline_chromium'] = True
                except Exception as e:
                    print(f"[WARNING] Offline Chromium setup skipped: {e}")
                    print("[INFO] You can run this manually later if needed")

        # Step 4: Setup logging and data directories
        print(f"\n[STEP 4/{SETUP_STEPS}] Directory setup...")
        if setup_logs_directory():
            setup_summary['logs'] = True
        setup_data_directory()
        setup_application_directories()

        # Step 5: Comprehensive verification
        print(f"\n[STEP 5/{SETUP_STEPS}] System verification...")
        verify_dependencies()
        verify_playwright_browsers()
        verify_file_structure()

        # Cleanup temporary files
        cleanup_temp_files()

        # Calculate execution time
        execution_time = time.time() - start_time

        # Show setup summary
        print("\n" + "=" * 60)
        print("[SUCCESS] MindGraph setup completed successfully!")
        print(f"[INFO] Total execution time: {execution_time:.1f} seconds")

        print_setup_summary(setup_summary)
        print_next_steps()
        print("=" * 60)

        # Restore original working directory
        os.chdir(original_cwd)
        sys.exit(0)

    except SetupError as e:
        print(f"\n[ERROR] Setup failed: {e}")
        print(f"[INFO] Execution time: {time.time() - start_time:.1f} seconds")
        print("\n[INFO] Troubleshooting:")
        print("    - Check your internet connection")
        print("    - Ensure you have sufficient disk space")
        print("    - Try running with administrator privileges if needed")
        os.chdir(original_cwd)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n[WARNING] Setup interrupted by user")
        print(f"[INFO] Execution time: {time.time() - start_time:.1f} seconds")
        os.chdir(original_cwd)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        print(f"[INFO] Execution time: {time.time() - start_time:.1f} seconds")
        print("\n[INFO] This may be a bug. Please report the issue with:")
        print("    - Python version:", sys.version)
        print("    - Platform:", platform.system(), platform.release())
        print("    - Error details:", str(e))
        os.chdir(original_cwd)
        sys.exit(1)


if __name__ == "__main__":
    main()
