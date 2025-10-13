"""
Temporary Image Cleanup Service
================================

Background task to clean up old PNG files from temp_images/ directory.
Automatically removes files older than 24 hours.

100% async implementation - all file operations use asyncio.
Compatible with Windows and Ubuntu when running under Uvicorn.

@author lycosa9527
@made_by MindSpring Team
"""

import asyncio
import logging
import time
from pathlib import Path
import aiofiles.os  # Async file system operations

logger = logging.getLogger(__name__)


async def cleanup_temp_images(max_age_seconds: int = 86400):
    """
    Remove PNG files older than max_age_seconds from temp_images/ directory.
    
    100% async implementation - uses aiofiles.os for non-blocking file operations.
    
    Args:
        max_age_seconds: Maximum age in seconds (default 24 hours)
        
    Returns:
        Number of files deleted
    """
    temp_dir = Path("temp_images")
    
    if not temp_dir.exists():
        # Silently skip if directory doesn't exist - nothing to clean
        return 0
    
    current_time = time.time()
    deleted_count = 0
    
    try:
        # Use asyncio to run blocking glob operation in thread pool
        files = await asyncio.to_thread(list, temp_dir.glob("dingtalk_*.png"))
        
        for file_path in files:
            # Get file stats asynchronously
            try:
                stat_result = await aiofiles.os.stat(file_path)
                file_age = current_time - stat_result.st_mtime
                
                if file_age > max_age_seconds:
                    try:
                        # Delete file asynchronously (non-blocking)
                        await aiofiles.os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"Deleted expired image: {file_path.name} (age: {file_age/3600:.1f}h)")
                    except Exception as e:
                        logger.error(f"Failed to delete {file_path.name}: {e}")
            except Exception as e:
                logger.error(f"Failed to stat {file_path.name}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Temp image cleanup: Deleted {deleted_count} expired files")
        else:
            logger.debug("Temp image cleanup: No expired files found")
            
        return deleted_count
        
    except Exception as e:
        logger.error(f"Temp image cleanup failed: {e}", exc_info=True)
        return deleted_count


async def start_cleanup_scheduler(interval_hours: int = 1):
    """
    Run cleanup task periodically in background.
    
    Args:
        interval_hours: How often to run cleanup (default: every 1 hour)
    """
    interval_seconds = interval_hours * 3600
    
    logger.info(f"Starting temp image cleanup scheduler (every {interval_hours}h)")
    
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await cleanup_temp_images()
        except Exception as e:
            logger.error(f"Cleanup scheduler error: {e}", exc_info=True)

