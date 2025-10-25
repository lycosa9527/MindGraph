"""
Browser Manager for MindGraph

Simple browser manager that creates a fresh browser instance for each request.
This approach ensures reliability and isolation between requests.

Features:
- Fresh browser instance per request
- Automatic cleanup of browser resources
- Optimized browser configuration for PNG generation
- Thread-safe operations
"""

import logging
from playwright.async_api import async_playwright, Browser, BrowserContext

logger = logging.getLogger(__name__)

class BrowserContextManager:
    """Context manager that creates a fresh browser for each request"""
    
    def __init__(self):
        self.context = None
        self.browser = None
        self.playwright = None
    
    async def __aenter__(self):
        """Create fresh browser instance for this request"""
        logger.debug("Creating fresh browser instance for PNG generation")
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
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
        )
        
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
