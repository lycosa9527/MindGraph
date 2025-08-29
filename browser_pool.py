"""
Browser Context Pool Management for MindGraph

Simplified browser context pool that works for any WSGI server deployment.
Uses a single browser instance with multiple contexts for optimal performance.

Features:
- Single browser instance shared across all requests
- Pool of reusable browser contexts
- Automatic context creation, cleanup, and reuse
- Thread-safe operations
- Performance monitoring and statistics
"""

import os
import sys
import time
import threading
import asyncio
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables for logging configuration
load_dotenv()

# Playwright imports
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext
except ImportError:
    Browser = None
    BrowserContext = None
    async_playwright = None

logger = logging.getLogger(__name__)
log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logger.setLevel(log_level)

# Global singleton pool instance
_singleton_pool = None
_global_pool_lock = threading.Lock()

class BrowserContextPool:
    """
    Simplified browser context pool that works for any WSGI server deployment.
    
    Features:
    - Single browser instance shared across all requests
    - Pool of reusable browser contexts
    - Automatic context creation, cleanup, and reuse
    - Thread-safe operations
    - Performance monitoring and statistics
    """
    
    def __init__(self, pool_size: int = 3):
        """
        Initialize browser context pool
        
        Args:
            pool_size: Number of contexts to maintain in the pool (default: 3)
        """
        self.pool_size = pool_size
        self.available_contexts: List[BrowserContext] = []
        self.in_use_contexts: List[BrowserContext] = []
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.initialized = False
        self._lock = threading.Lock()
        self._init_lock = None
        
        # Performance statistics
        self.stats = {
            'total_requests': 0,
            'context_creations': 0,
            'context_reuses': 0,
            'pool_hits': 0,
            'pool_misses': 0,
            'total_startup_time_saved': 0.0,
            'last_request_time': 0.0
        }
        
        # Browser launch configuration (optimized for PNG generation)
        self.browser_args = [
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
    
    async def initialize(self):
        """Initialize the browser context pool with a single browser instance"""
        if self.initialized:
            return
            
        if self._init_lock is None:
            self._init_lock = asyncio.Lock()
            
        async with self._init_lock:
            if self.initialized:
                return
                
            try:
                logger.info("Initializing browser context pool...")
                
                # Initialize Playwright
                self.playwright = await async_playwright().start()
                
                # Launch browser
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=self.browser_args
                )
                
                # Create initial pool of contexts
                for i in range(self.pool_size):
                    context = await self.browser.new_context(
                        viewport={'width': 1200, 'height': 800},
                        user_agent='MindGraph/2.0 (PNG Generator)'
                    )
                    self.available_contexts.append(context)
                
                self.initialized = True
                logger.info(f"Browser context pool initialized with {self.pool_size} contexts (reduced from 5)")
                
            except Exception as e:
                logger.error(f"Failed to initialize browser context pool: {e}")
                raise
    
    async def get_context(self) -> BrowserContext:
        """Get an available browser context from the pool"""
        if not self.initialized:
            await self.initialize()
        
        with self._lock:
            if self.available_contexts:
                # Reuse existing context
                context = self.available_contexts.pop()
                self.in_use_contexts.append(context)
                self.stats['context_reuses'] += 1
                self.stats['pool_hits'] += 1
                logger.debug("Reusing existing browser context from pool")
            else:
                # Create new context if pool is empty
                context = await self.browser.new_context(
                    viewport={'width': 1200, 'height': 800},
                    user_agent='MindGraph/2.0 (PNG Generator)'
                )
                self.in_use_contexts.append(context)
                self.stats['context_creations'] += 1
                self.stats['pool_misses'] += 1
                logger.debug("Created new browser context (pool was empty)")
            
            self.stats['total_requests'] += 1
            self.stats['last_request_time'] = time.time()
            
            return context
    
    async def return_context(self, context: BrowserContext):
        """Return a browser context to the pool for reuse"""
        if not context:
            return
            
        with self._lock:
            if context in self.in_use_contexts:
                self.in_use_contexts.remove(context)
                
                # Reset context for reuse
                try:
                    await context.clear_cookies()
                    await context.clear_permissions()
                    
                    # Add back to available pool
                    self.available_contexts.append(context)
                    logger.debug("Browser context returned to pool for reuse")
                    
                except Exception as e:
                    logger.warning(f"Error resetting context, closing it: {e}")
                    await context.close()
    
    async def cleanup(self):
        """Clean up all browser contexts and browser instance"""
        logger.info("Cleaning up browser context pool...")
        
        try:
            # Close all contexts
            all_contexts = self.available_contexts + self.in_use_contexts
            for context in all_contexts:
                try:
                    await context.close()
                except Exception as e:
                    logger.warning(f"Error closing context: {e}")
            
            # Close browser
            if self.browser:
                await self.browser.close()
            
            # Stop Playwright
            if self.playwright:
                await self.playwright.stop()
            
            # Reset state
            self.available_contexts.clear()
            self.in_use_contexts.clear()
            self.browser = None
            self.playwright = None
            self.initialized = False
            
            logger.info("Browser context pool cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during browser context pool cleanup: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current pool statistics"""
        with self._lock:
            stats = self.stats.copy()
            
            # Calculate efficiency
            if stats['total_requests'] > 0:
                stats['pool_efficiency_percent'] = (stats['pool_hits'] / stats['total_requests']) * 100
                stats['average_startup_time_saved_per_request'] = stats['total_startup_time_saved'] / stats['total_requests']
            else:
                stats['pool_efficiency_percent'] = 0.0
                stats['average_startup_time_saved_per_request'] = 0.0
            
            # Add current pool state
            stats.update({
                'pool_size': self.pool_size,
                'available_contexts': len(self.available_contexts),
                'in_use_contexts': len(self.in_use_contexts),
                'total_contexts': len(self.available_contexts) + len(self.in_use_contexts),
                'initialized': self.initialized
            })
            
            return stats

# Global pool instance
def get_browser_context_pool() -> BrowserContextPool:
    """Get the global browser context pool instance"""
    global _singleton_pool
    
    if _singleton_pool is None:
        with _global_pool_lock:
            if _singleton_pool is None:
                logger.info("Creating global browser context pool")
                _singleton_pool = BrowserContextPool(pool_size=3)  # Reduced from 5 to 3
    
    return _singleton_pool

async def initialize_browser_context_pool():
    """Initialize the global browser context pool"""
    pool = get_browser_context_pool()
    await pool.initialize()
    logger.info("Global browser context pool initialized")

async def cleanup_browser_context_pool():
    """Clean up the global browser context pool"""
    global _singleton_pool
    
    if _singleton_pool:
        await _singleton_pool.cleanup()
        with _global_pool_lock:
            _singleton_pool = None
        logger.info("Global browser context pool cleaned up")

def cleanup_browser_context_pool_sync():
    """Synchronous cleanup for shutdown scenarios"""
    global _singleton_pool
    
    if _singleton_pool:
        try:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_singleton_pool.cleanup())
                with _global_pool_lock:
                    _singleton_pool = None
                logger.info("Browser context pool manually cleaned up")
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error during manual cleanup: {e}")

# Context manager for safe context usage
class BrowserContextManager:
    """Context manager for safe browser context usage"""
    
    def __init__(self):
        self.context = None
        self.pool = get_browser_context_pool()
    
    async def __aenter__(self):
        self.context = await self.pool.get_context()
        return self.context
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            await self.pool.return_context(self.context)
            self.context = None

# Auto-cleanup on application shutdown
import atexit
atexit.register(cleanup_browser_context_pool_sync)

logger.info("Browser context pool module loaded - simplified single-strategy approach")
