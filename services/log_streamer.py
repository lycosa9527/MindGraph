"""
Log Streaming Service
=====================

Real-time log tailing and streaming for admin debug viewer.

Features:
- Tail log files with follow mode
- Parse log lines into structured data
- Support multiple log sources (app, uvicorn, errors)
- Handle log rotation gracefully
- Rate limiting to prevent overwhelming clients

Author: lycosa9527
Made by: MindSpring Team
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional, List
import re
from datetime import datetime

try:
    import aiofiles
except ImportError:
    aiofiles = None

logger = logging.getLogger(__name__)


class LogStreamer:
    """
    Streams log files to clients with real-time tailing.
    
    Supports async iteration and handles log rotation.
    """
    
    def __init__(self, log_dir: str = "logs", max_lines_per_second: int = 100):
        """
        Initialize LogStreamer.
        
        Args:
            log_dir: Directory containing log files
            max_lines_per_second: Rate limit for streaming (prevents overwhelming client)
        """
        self.log_dir = Path(log_dir)
        self.max_lines_per_second = max_lines_per_second
        
        # Log file patterns
        self.log_files = {
            'app': 'app.log',
            'uvicorn': 'uvicorn.log',
            'error': 'error.log'
        }
        
        logger.info(f"LogStreamer initialized for directory: {self.log_dir}")
    
    async def tail_logs(
        self,
        source: str = 'app',
        follow: bool = True,
        max_lines: int = 1000
    ) -> AsyncGenerator[Dict, None]:
        """
        Tail a log file and yield parsed log entries.
        
        Args:
            source: Log source ('app', 'uvicorn', 'error', or 'all')
            follow: If True, continue watching for new lines (like `tail -f`)
            max_lines: Maximum number of historical lines to read first
            
        Yields:
            Dict with parsed log data: {timestamp, level, module, message}
        """
        if source == 'all':
            # Stream from all log sources
            async for entry in self._tail_all_logs(follow, max_lines):
                yield entry
        else:
            # Stream from single source
            log_file = self.log_dir / self.log_files.get(source, 'app.log')
            
            if not log_file.exists():
                logger.warning(f"Log file not found: {log_file}")
                yield {
                    'timestamp': datetime.now().isoformat(),
                    'level': 'WARNING',
                    'module': 'LogStreamer',
                    'message': f'Log file not found: {log_file}',
                    'source': source
                }
                return
            
            async for entry in self._tail_file(log_file, follow, max_lines, source):
                yield entry
    
    async def _tail_all_logs(
        self,
        follow: bool,
        max_lines: int
    ) -> AsyncGenerator[Dict, None]:
        """Tail all log sources and merge streams."""
        # For simplicity, just tail app.log (primary log)
        # In production, could use asyncio.gather to tail multiple files
        async for entry in self.tail_logs('app', follow, max_lines):
            yield entry
    
    async def _tail_file(
        self,
        log_file: Path,
        follow: bool,
        max_lines: int,
        source: str
    ) -> AsyncGenerator[Dict, None]:
        """
        Tail a single log file.
        
        Args:
            log_file: Path to log file
            follow: Continue watching for new lines
            max_lines: Maximum historical lines to read
            source: Source identifier
            
        Yields:
            Parsed log entries
        """
        if aiofiles is None:
            # Fallback to sync file reading
            logger.warning("aiofiles not available, using synchronous file reading")
            async for entry in self._tail_file_sync(log_file, follow, max_lines, source):
                yield entry
            return
        
        try:
            async with aiofiles.open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Seek to end if following, otherwise read from start
                if follow:
                    await f.seek(0, 2)  # Seek to end
                else:
                    # Read last N lines
                    await f.seek(0, 0)  # Seek to start
                    lines = await f.readlines()
                    
                    # Take last max_lines
                    for line in lines[-max_lines:]:
                        entry = self.parse_log_line(line.strip(), source)
                        if entry:
                            yield entry
                    
                    if not follow:
                        return
                
                # Follow mode: continuously read new lines
                line_count = 0
                last_yield_time = asyncio.get_event_loop().time()
                
                while follow:
                    line = await f.readline()
                    
                    if line:
                        entry = self.parse_log_line(line.strip(), source)
                        if entry:
                            yield entry
                            line_count += 1
                            
                            # Rate limiting
                            current_time = asyncio.get_event_loop().time()
                            if current_time - last_yield_time < 1.0 and line_count >= self.max_lines_per_second:
                                # Exceeded rate limit, wait
                                await asyncio.sleep(1.0 - (current_time - last_yield_time))
                                line_count = 0
                                last_yield_time = asyncio.get_event_loop().time()
                    else:
                        # No new lines, wait a bit
                        await asyncio.sleep(0.1)
                        
                        # Check if file was rotated (size decreased)
                        try:
                            current_pos = await f.tell()
                            file_size = log_file.stat().st_size
                            
                            if current_pos > file_size:
                                # File was rotated, reopen
                                logger.info(f"Log rotation detected for {log_file}, reopening...")
                                break  # Exit and let caller handle reconnection
                        except Exception as e:
                            logger.error(f"Error checking file rotation: {e}")
                            
        except Exception as e:
            logger.error(f"Error tailing log file {log_file}: {e}")
            yield {
                'timestamp': datetime.now().isoformat(),
                'level': 'ERROR',
                'module': 'LogStreamer',
                'message': f'Error reading log file: {str(e)}',
                'source': source
            }
    
    async def _tail_file_sync(
        self,
        log_file: Path,
        follow: bool,
        max_lines: int,
        source: str
    ) -> AsyncGenerator[Dict, None]:
        """Synchronous fallback for tailing files."""
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                if follow:
                    f.seek(0, 2)  # Seek to end
                else:
                    # Read last N lines
                    lines = f.readlines()
                    for line in lines[-max_lines:]:
                        entry = self.parse_log_line(line.strip(), source)
                        if entry:
                            yield entry
                    return
                
                # Follow mode
                while follow:
                    line = f.readline()
                    if line:
                        entry = self.parse_log_line(line.strip(), source)
                        if entry:
                            yield entry
                    else:
                        await asyncio.sleep(0.1)
                        
        except Exception as e:
            logger.error(f"Error tailing log file {log_file}: {e}")
            yield {
                'timestamp': datetime.now().isoformat(),
                'level': 'ERROR',
                'module': 'LogStreamer',
                'message': f'Error reading log file: {str(e)}',
                'source': source
            }
    
    def parse_log_line(self, line: str, source: str) -> Optional[Dict]:
        """
        Parse a log line into structured data.
        
        Supports multiple log formats:
        - Uvicorn format: [HH:MM:SS] LEVEL | MODULE | Message
        - Python logging format: LEVEL:module:message
        - Generic format
        
        Args:
            line: Raw log line
            source: Source identifier
            
        Returns:
            Dict with timestamp, level, module, message or None if can't parse
        """
        if not line or line.strip() == '':
            return None
        
        # Try to parse Uvicorn-style format: [HH:MM:SS] LEVEL | MODULE | Message
        uvicorn_pattern = r'^\[(\d{2}:\d{2}:\d{2})\]\s+(\w+)\s+\|\s+(\w+)\s+\|\s+(.+)$'
        match = re.match(uvicorn_pattern, line)
        
        if match:
            time_str, level, module, message = match.groups()
            return {
                'timestamp': f"{datetime.now().strftime('%Y-%m-%d')} {time_str}",
                'level': level.strip(),
                'module': module.strip(),
                'message': message.strip(),
                'source': source,
                'raw': line
            }
        
        # Try Python logging format: LEVEL:module:message
        python_pattern = r'^(\w+):([^:]+):(.+)$'
        match = re.match(python_pattern, line)
        
        if match:
            level, module, message = match.groups()
            return {
                'timestamp': datetime.now().isoformat(),
                'level': level.strip(),
                'module': module.strip(),
                'message': message.strip(),
                'source': source,
                'raw': line
            }
        
        # Fallback: return as generic log entry
        return {
            'timestamp': datetime.now().isoformat(),
            'level': 'INFO',
            'module': source,
            'message': line,
            'source': source,
            'raw': line
        }
    
    def get_log_files(self) -> List[Dict]:
        """
        List available log files.
        
        Returns:
            List of dicts with file info: {name, path, size, modified}
        """
        log_files = []
        
        try:
            for name, filename in self.log_files.items():
                log_path = self.log_dir / filename
                
                if log_path.exists():
                    stat = log_path.stat()
                    log_files.append({
                        'name': name,
                        'filename': filename,
                        'path': str(log_path),
                        'size_bytes': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
        except Exception as e:
            logger.error(f"Error listing log files: {e}")
        
        return log_files
    
    async def read_log_file(
        self,
        source: str = 'app',
        start_line: int = 0,
        num_lines: int = 100
    ) -> List[Dict]:
        """
        Read a range of lines from a log file.
        
        Args:
            source: Log source
            start_line: Starting line number (0-based)
            num_lines: Number of lines to read
            
        Returns:
            List of parsed log entries
        """
        log_file = self.log_dir / self.log_files.get(source, 'app.log')
        
        if not log_file.exists():
            return []
        
        entries = []
        
        try:
            if aiofiles:
                async with aiofiles.open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = await f.readlines()
            else:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
            
            # Get requested range
            for line in lines[start_line:start_line + num_lines]:
                entry = self.parse_log_line(line.strip(), source)
                if entry:
                    entries.append(entry)
                    
        except Exception as e:
            logger.error(f"Error reading log file {log_file}: {e}")
        
        return entries

