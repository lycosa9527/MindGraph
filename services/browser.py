"""
Browser Manager for MindGraph

Simple browser manager that creates a fresh browser instance for each request.
This approach ensures reliability and isolation between requests.

Features:
- Fresh browser instance per request
- Automatic cleanup of browser resources
- Optimized browser configuration for PNG generation
- Thread-safe operations
- Support for offline Chromium installation (browsers/chromium/)
"""

import logging
import os
import platform
import subprocess
import re
import sys
import asyncio
from pathlib import Path
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext

logger = logging.getLogger(__name__)

def _get_chromium_version(executable_path: str) -> Optional[str]:
    """
    Get Chromium version from executable.
    Uses multiple methods to handle different platforms and Chromium behaviors.
    
    Args:
        executable_path: Path to Chromium executable
        
    Returns:
        Version string (e.g., "141.0.7390.37") or None if failed
    """
    # Method 1: Try using Playwright to launch browser and get version (works for any Chromium)
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            # Try to launch browser and get version
            browser = p.chromium.launch(
                executable_path=executable_path,
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            try:
                # Get version from browser object
                version = browser.version
                if version:
                    version_str = str(version).strip()
                    # browser.version returns version directly (e.g., "141.0.7390.37")
                    # or sometimes "Chromium 141.0.7390.37"
                    version_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', version_str)
                    if version_match:
                        browser.close()
                        return version_match.group(1)
                    # If it's already a version-like string, return it
                    if re.match(r'^\d+\.\d+\.\d+\.\d+$', version_str):
                        browser.close()
                        return version_str
                browser.close()
            except Exception:
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception:
        pass
    
    # Method 2: Try --version flag with timeout (fallback)
    try:
        result = subprocess.run(
            [executable_path, "--version"],
            capture_output=True,
            text=True,
            timeout=3,
            stderr=subprocess.DEVNULL
        )
        if result.returncode == 0 and result.stdout:
            # Parse version from output like "Chromium 141.0.7390.37" or "Google Chrome 141.0.7390.37"
            version_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', result.stdout)
            if version_match:
                return version_match.group(1)
    except subprocess.TimeoutExpired:
        # Chromium might hang on --version, skip
        pass
    except Exception:
        pass
    
    # Method 3: Extract revision from path (fallback for Playwright browsers)
    # Only use this if we couldn't get actual version
    if 'chromium-' in executable_path and 'ms-playwright' in executable_path:
        try:
            revision_match = re.search(r'chromium-(\d+)', executable_path)
            if revision_match:
                # Return revision as fallback (will be compared as revision number)
                return revision_match.group(1)
        except Exception:
            pass
    
    return None


def _compare_versions(version1: str, version2: str) -> int:
    """
    Compare two version strings.
    Handles both full version strings (e.g., "141.0.7390.37") and revision numbers (e.g., "1194").
    
    Args:
        version1: First version string
        version2: Second version string
        
    Returns:
        -1 if version1 < version2, 0 if equal, 1 if version1 > version2
    """
    def version_tuple(v: str) -> Tuple[int, ...]:
        # If it's just a revision number (single number), treat as major version
        parts = v.split('.')
        if len(parts) == 1:
            # Single number - likely a revision, treat as major version
            return (int(parts[0]), 0, 0, 0)
        else:
            # Full version string
            return tuple(int(x) for x in parts)
    
    try:
        v1_tuple = version_tuple(version1)
        v2_tuple = version_tuple(version2)
        
        # Pad with zeros to same length
        max_len = max(len(v1_tuple), len(v2_tuple))
        v1_tuple = v1_tuple + (0,) * (max_len - len(v1_tuple))
        v2_tuple = v2_tuple + (0,) * (max_len - len(v2_tuple))
        
        if v1_tuple < v2_tuple:
            return -1
        elif v1_tuple > v2_tuple:
            return 1
        else:
            return 0
    except Exception:
        # If parsing fails, assume versions are equal
        return 0


def _get_playwright_chromium_executable() -> Optional[str]:
    """
    Get the path to Playwright's managed Chromium executable.
    
    Returns:
        str or None: Path to Chromium executable, or None if not found
    """
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser_path = p.chromium.executable_path
            if browser_path and os.path.exists(browser_path):
                return browser_path
    except Exception:
        pass
    return None


def _get_local_chromium_executable():
    """
    Get the path to local Chromium executable if available.
    
    Returns:
        str or None: Path to Chromium executable, or None if not found
    """
    # Get project root (assuming this file is in services/)
    project_root = Path(__file__).parent.parent
    browsers_dir = project_root / "browsers" / "chromium"
    
    if not browsers_dir.exists():
        return None
    
    system = platform.system().lower()
    
    # Note: Windows support removed - Linux/WSL only
    if system == "darwin":  # macOS
        # macOS: browsers/chromium/chrome-mac/Chromium.app/Contents/MacOS/Chromium
        possible_paths = [
            browsers_dir / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
            browsers_dir / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
            browsers_dir / "chrome"
        ]
        for path in possible_paths:
            if path.exists():
                return str(path)
        return None
    else:  # Linux (default for WSL/production)
        # Linux: browsers/chromium/chrome-linux/chrome
        possible_paths = [
            browsers_dir / "chrome-linux" / "chrome",
            browsers_dir / "chrome"
        ]
        for path in possible_paths:
            if path.exists():
                return str(path)
        return None


def _get_best_chromium_executable() -> Optional[str]:
    """
    Get the best available Chromium executable, preferring newer version.
    Compares local packed browser vs Playwright's managed browser.
    
    Returns:
        str or None: Path to best Chromium executable, or None if not found
    """
    local_chromium = _get_local_chromium_executable()
    playwright_chromium = _get_playwright_chromium_executable()
    
    # If only one is available, use it
    if local_chromium and not playwright_chromium:
        logger.debug(f"Using local Chromium (Playwright browser not found): {local_chromium}")
        return local_chromium
    
    if playwright_chromium and not local_chromium:
        logger.debug(f"Using Playwright Chromium (local browser not found): {playwright_chromium}")
        return playwright_chromium
    
    # If neither is available, return None
    if not local_chromium and not playwright_chromium:
        return None
    
    # Both are available - compare versions
    local_version = _get_chromium_version(local_chromium)
    playwright_version = _get_chromium_version(playwright_chromium)
    
    if not local_version and not playwright_version:
        # Can't determine versions, prefer local (faster, no download needed)
        logger.debug(f"Using local Chromium (version check failed): {local_chromium}")
        return local_chromium
    
    if not local_version:
        logger.debug(f"Using Playwright Chromium (local version check failed): {playwright_chromium}")
        return playwright_chromium
    
    if not playwright_version:
        logger.debug(f"Using local Chromium (Playwright version check failed): {local_chromium}")
        return local_chromium
    
    # Check if one is a revision number (single number) and the other is a full version
    local_is_revision = '.' not in local_version
    playwright_is_revision = '.' not in playwright_version
    
    # If one is a revision and the other is a full version, prefer the full version
    # (revision numbers cannot be reliably compared to version numbers)
    # (we can't reliably compare revision numbers to version numbers)
    if local_is_revision and not playwright_is_revision:
        logger.info(f"Using Playwright Chromium (v{playwright_version}) - has full version vs local revision {local_version}")
        return playwright_chromium
    
    if playwright_is_revision and not local_is_revision:
        logger.info(f"Using local Chromium (v{local_version}) - has full version vs Playwright revision {playwright_version}")
        return local_chromium
    
    # Both are either revisions or full versions - compare them
    comparison = _compare_versions(local_version, playwright_version)
    if comparison < 0:
        # Playwright version is newer
        logger.info(f"Using Playwright Chromium (v{playwright_version}) - newer than local (v{local_version})")
        return playwright_chromium
    elif comparison > 0:
        # Local version is newer (unlikely but possible)
        logger.info(f"Using local Chromium (v{local_version}) - newer than Playwright (v{playwright_version})")
        return local_chromium
    else:
        # Versions are equal, prefer local (faster, no download needed)
        logger.debug(f"Using local Chromium (v{local_version}) - same version as Playwright")
        return local_chromium


class BrowserContextManager:
    """Context manager that creates a fresh browser for each request"""
    
    def __init__(self):
        self.context = None
        self.browser = None
        self.playwright = None
    
    async def __aenter__(self):
        """Create fresh browser instance for this request"""
        logger.debug("Creating fresh browser instance for PNG generation")
        
        # Diagnostic: Check Python executable and Playwright installation
        import sys
        python_exe = sys.executable
        logger.info(f"[BrowserContextManager] Python executable: {python_exe}")
        logger.info(f"[BrowserContextManager] Python version: {sys.version}")
        
        # Check if Playwright module is available
        try:
            import playwright
            playwright_path = playwright.__file__
            logger.info(f"[BrowserContextManager] Playwright module path: {playwright_path}")
        except Exception as e:
            logger.error(f"[BrowserContextManager] Cannot import playwright: {e}")
        
        try:
            # Log event loop information for debugging (useful for troubleshooting)
            try:
                loop = asyncio.get_running_loop()
                loop_type = type(loop).__name__
                policy = asyncio.get_event_loop_policy()
                policy_type = type(policy).__name__
                logger.info(f"[BrowserContextManager] Event loop type: {loop_type}")
                logger.info(f"[BrowserContextManager] Event loop policy: {policy_type}")
            except Exception as loop_check_error:
                logger.debug(f"[BrowserContextManager] Could not check event loop: {loop_check_error}")
            
            logger.info("[BrowserContextManager] Starting async_playwright().start()...")
            self.playwright = await async_playwright().start()
            logger.info("[BrowserContextManager] async_playwright().start() succeeded!")
            
            # Check Chromium executable path after starting (using async API)
            try:
                chromium_path = self.playwright.chromium.executable_path
                logger.info(f"[BrowserContextManager] Chromium executable path: {chromium_path}")
                if chromium_path and os.path.exists(chromium_path):
                    logger.info(f"[BrowserContextManager] Chromium executable exists: YES")
                else:
                    logger.warning(f"[BrowserContextManager] Chromium executable exists: NO")
            except Exception as e:
                logger.warning(f"[BrowserContextManager] Could not check Chromium path: {e}")
                
        except NotImplementedError as e:
            # NotImplementedError should not occur on Linux/WSL (this is Windows-specific)
            # If it happens, it indicates a serious configuration issue
            logger.error(f"[BrowserContextManager] NotImplementedError occurred - this is unexpected on Linux/WSL")
            logger.error(f"[BrowserContextManager] Original error: {e}")
            logger.error(f"[BrowserContextManager] Platform: {platform.system()}")
            logger.error(f"[BrowserContextManager] Python executable: {python_exe}")
            
            # Check if browsers are actually installed
            import subprocess
            try:
                result = subprocess.run(
                    [python_exe, '-m', 'playwright', 'install', '--list'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    logger.error(f"[BrowserContextManager] Playwright browsers check output:\n{result.stdout}")
                    if 'chromium' in result.stdout.lower():
                        logger.error("[BrowserContextManager] Browsers ARE installed but Playwright can't access them!")
            except Exception as check_error:
                logger.error(f"[BrowserContextManager] Could not check browser installation: {check_error}")
            
            error_msg = (
                "Playwright browsers are not installed or cannot be accessed. "
                "Please run: python -m playwright install chromium\n"
                "Or install all browsers: python -m playwright install"
            )
            logger.error(f"[BrowserContextManager] {error_msg}")
            raise RuntimeError(error_msg) from e
        except Exception as e:
            logger.error(f"[BrowserContextManager] Error starting Playwright: {e}", exc_info=True)
            logger.error(f"[BrowserContextManager] Error type: {type(e)}")
            raise
        
        # Get best available Chromium (compares versions, prefers newer)
        chromium_executable = _get_best_chromium_executable()
        launch_options = {
            'headless': True,
            'args': [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--memory-pressure-off',
                '--max_old_space_size=4096',
                '--disable-background-networking',
                '--disable-background-timer-throttling',
                '--disable-renderer-backgrounding',
                '--disable-backgrounding-occluded-windows',
                '--disable-ipc-flooding-protection'
            ]
        }
        
        if chromium_executable:
            logger.debug(f"Using Chromium executable: {chromium_executable}")
            launch_options['executable_path'] = chromium_executable
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        
        # Create fresh context with high resolution for crisp PNG output
        self.context = await self.browser.new_context(
            viewport={'width': 1200, 'height': 800},
            device_scale_factor=3,  # 3x for high-DPI displays (Retina quality)
            user_agent='MindGraph/2.0 (PNG Generator)'
        )
        
        logger.debug(f"Fresh browser context created - type: {type(self.context)}, id: {id(self.context)}")
        return self.context
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up browser resources"""
        if self.context:
            await self.context.close()
            self.context = None
        
        if self.browser:
            await self.browser.close()
            self.browser = None
            
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        
        logger.debug("Fresh browser instance cleaned up")

# Only log from main worker to avoid duplicate messages
import os
if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
    logger.debug("Browser manager module loaded")
