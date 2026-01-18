from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional, List
import asyncio
import logging
import re


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

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""


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

        # Log file patterns (base names - will resolve to timestamped files)
        self.log_files = {
            'app': 'app',
            'uvicorn': 'uvicorn.log',
            'error': 'error.log'
        }

        logger.info("LogStreamer initialized for directory: %s", self.log_dir)

    def _find_latest_log_file(self, base_name: str) -> Optional[Path]:
        """
        Find the most recent timestamped log file for a given base name.

        Args:
            base_name: Base log file name (e.g., 'app' or 'app.log')

        Returns:
            Path to the most recent log file, or None if not found
        """
        # Handle both 'app' and 'app.log' formats
        if base_name.endswith('.log'):
            base_name = base_name[:-4]

        # Pattern: base_name.YYYY-MM-DD_HH-MM-SS.log
        matching_files = []

        try:
            for filename in self.log_dir.iterdir():
                if filename.is_file() and filename.name.startswith(base_name + '.') and filename.name.endswith('.log'):
                    # Extract timestamp from filename: base_name.YYYY-MM-DD_HH-MM-SS.log
                    try:
                        # Get modification time as fallback, but prefer filename timestamp
                        mtime = filename.stat().st_mtime
                        matching_files.append((mtime, filename))
                    except OSError:
                        continue

            if matching_files:
                # Sort by modification time (most recent first)
                matching_files.sort(reverse=True)
                return matching_files[0][1]
        except OSError:
            pass

        return None

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
            base_name = self.log_files.get(source, 'app')
            log_file = self._find_latest_log_file(base_name)

            if log_file is None:
                logger.warning("Log file not found for source '%s' (base: %s)", source, base_name)
                yield {
                    'timestamp': datetime.now().isoformat(),
                    'level': 'WARNING',
                    'module': 'LogStreamer',
                    'message': f'Log file not found for source: {source}',
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
                check_rotation_counter = 0  # Check rotation every 10 iterations (1 second)

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

                        # Check rotation periodically (every ~1 second) to avoid excessive checks
                        check_rotation_counter += 1
                        if check_rotation_counter >= 10:
                            check_rotation_counter = 0

                            # Check if file was rotated (size decreased) or new timestamped file created
                            try:
                                current_pos = await f.tell()
                                file_size = log_file.stat().st_size

                                if current_pos > file_size:
                                    # File was rotated, reopen
                                    logger.info("Log rotation detected for %s, reopening...", log_file)
                                    break  # Exit and let caller handle reconnection

                                # Check if a newer timestamped file exists (for timestamped rotation)
                                base_name = self.log_files.get(source, 'app')
                                latest_file = self._find_latest_log_file(base_name)
                                if latest_file and latest_file != log_file:
                                    # New timestamped file created, switch to it
                                    logger.info("New log file detected: %s, switching from %s", latest_file, log_file)
                                    break  # Exit and let caller handle reconnection
                            except Exception as e:
                                logger.error("Error checking file rotation: %s", e)

        except Exception as e:
            logger.error("Error tailing log file %s: %s", log_file, e)
            yield {
                'timestamp': datetime.now().isoformat(),
                'level': 'ERROR',
                'module': 'LogStreamer',
                'message': 'Error reading log file: %s' % str(e),
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
            logger.error("Error tailing log file %s: %s", log_file, e)
            yield {
                'timestamp': datetime.now().isoformat(),
                'level': 'ERROR',
                'module': 'LogStreamer',
                'message': 'Error reading log file: %s' % str(e),
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
            for name, base_name in self.log_files.items():
                # For timestamped files (like 'app'), find the latest one
                if name == 'app':
                    log_path = self._find_latest_log_file(base_name)
                    if log_path:
                        stat = log_path.stat()
                        log_files.append({
                            'name': name,
                            'filename': log_path.name,
                            'path': str(log_path),
                            'size_bytes': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
                else:
                    # For non-timestamped files, use direct path
                    log_path = self.log_dir / base_name
                    if log_path.exists():
                        stat = log_path.stat()
                        log_files.append({
                            'name': name,
                            'filename': base_name,
                            'path': str(log_path),
                            'size_bytes': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
        except Exception as e:
            logger.error("Error listing log files: %s", e)

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
        base_name = self.log_files.get(source, 'app')
        log_file = self._find_latest_log_file(base_name)

        if log_file is None:
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
            logger.error("Error reading log file %s: %s", log_file, e)

        return entries

