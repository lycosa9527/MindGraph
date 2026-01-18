"""
Environment File Utilities
==========================

Utility functions for handling .env file encoding and loading.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from pathlib import Path
import logging
import shutil


# Try to get logger, but handle case where logging isn't configured yet
try:
    LOGGER = logging.getLogger(__name__)
except Exception:
    LOGGER = None

def _log(message: str, level: str = 'info'):
    """Log message, fallback to print if logging not configured"""
    if LOGGER:
        if level == 'warning':
            LOGGER.warning(message)
        elif level == 'error':
            LOGGER.error(message)
        else:
            LOGGER.info(message)
    else:
        print(f"[ENV_UTILS] {message}")


def ensure_utf8_env_file(env_path: str = ".env") -> None:
    """
    Ensure .env file is UTF-8 encoded before loading.

    This function detects and converts non-UTF-8 encoded .env files to UTF-8,
    preventing UnicodeDecodeError when load_dotenv() reads the file.

    Args:
        env_path: Path to .env file (default: ".env")
    """
    env_file = Path(env_path)

    # Skip if file doesn't exist
    if not env_file.exists():
        return

    try:
        # Try to read as UTF-8 first
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # If successful, file is already UTF-8
        return

    except UnicodeDecodeError:
        # File is not UTF-8, need to convert
        _log(".env file is not UTF-8 encoded, attempting to convert...", 'warning')

        # Try common encodings
        encodings_to_try = ['utf-16', 'utf-16-le', 'utf-16-be', 'utf-8-sig',
                           'latin1', 'cp1252', 'gbk', 'gb2312']

        content = None
        detected_encoding = None

        for encoding in encodings_to_try:
            try:
                with open(env_file, 'r', encoding=encoding) as f:
                    content = f.read()
                detected_encoding = encoding
                _log(f"Successfully read .env file as {encoding}, converting to UTF-8...")
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if content is None:
            # Last resort: try with errors='ignore' to salvage what we can
            _log("Could not detect encoding, attempting to read with error handling...", 'warning')
            try:
                with open(env_file, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                detected_encoding = 'utf-8 (with replacements)'
            except Exception as e:
                _log(f"Failed to read .env file: {e}", 'error')
                raise ValueError("Cannot read .env file: invalid encoding. Please save the file as UTF-8.") from e

        # Write back as UTF-8
        try:
            # Create backup before converting
            backup_path = env_file.with_suffix('.env.backup.before_utf8_conversion')
            if not backup_path.exists():
                shutil.copy2(env_file, backup_path)
                _log(f"Created backup: {backup_path}")

            # Write as UTF-8
            with open(env_file, 'w', encoding='utf-8', newline='') as f:
                f.write(content)

            _log(f"Successfully converted .env file from {detected_encoding} to UTF-8")

        except Exception as e:
            _log(f"Failed to write UTF-8 .env file: {e}", 'error')
            raise ValueError(f"Cannot convert .env file to UTF-8: {e}") from e
