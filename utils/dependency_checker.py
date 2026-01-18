"""
Dependency Checker for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Checks for required system dependencies at startup.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Tuple
import logging
import platform
import shutil
import subprocess
import sys

try:
    import pytesseract
except ImportError:
    pytesseract = None


logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Raised when a required dependency is missing."""


def install_tesseract_ocr() -> Tuple[bool, Optional[str]]:
    """
    Attempt to automatically install Tesseract OCR on Linux systems.

    Returns:
        Tuple of (success, error_message)
        - success: True if installation succeeded or not needed
        - error_message: Error message if installation failed, None if succeeded
    """
    # Only attempt auto-install on Linux (Ubuntu/Debian)
    if platform.system() != 'Linux':
        return True, None  # Not Linux, skip auto-install

    # Check if apt-get is available
    if not shutil.which('apt-get'):
        return True, None  # Not a Debian-based system, skip

    try:
        logger.info("[DependencyCheck] Attempting to automatically install Tesseract OCR...")

        # Check if we can run apt-get without sudo (some systems allow this)
        # Try with sudo first, fall back to direct apt-get if sudo not available
        apt_cmd = ['apt-get', 'install', '-y', 'tesseract-ocr', 'tesseract-ocr-chi-sim']

        # Check if sudo is available
        if shutil.which('sudo'):
            cmd = ['sudo'] + apt_cmd
        else:
            # Try without sudo (may work if running as root or in container)
            cmd = apt_cmd

        # Run the installation command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            check=False
        )

        if result.returncode == 0:
            logger.info("[DependencyCheck] Successfully installed Tesseract OCR")
            return True, None
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            logger.warning(
                "[DependencyCheck] Failed to auto-install Tesseract OCR: %s", error_msg
            )
            return False, f"Auto-installation failed: {error_msg}"

    except subprocess.TimeoutExpired:
        logger.warning("[DependencyCheck] Tesseract OCR installation timed out")
        return False, "Installation timed out after 5 minutes"
    except FileNotFoundError:
        logger.warning("[DependencyCheck] apt-get command not found, cannot auto-install")
        return True, None  # Not an error, just can't auto-install
    except Exception as e:
        logger.warning("[DependencyCheck] Error during auto-installation: %s", e)
        return False, f"Auto-installation error: {str(e)}"


def check_tesseract_ocr() -> Tuple[bool, Optional[str]]:
    """
    Check if Tesseract OCR is installed and accessible.

    Returns:
        Tuple of (is_available, error_message)
        - is_available: True if Tesseract is available
        - error_message: Error message if not available, None if available
    """
    if pytesseract is None:
        return False, "pytesseract Python package is not installed. Install with: pip install pytesseract"

    try:
        # Check if Tesseract binary is available
        # pytesseract.get_tesseract_version() will raise if binary not found
        try:
            version = pytesseract.get_tesseract_version()
            logger.info("[DependencyCheck] Tesseract OCR found: version %s", version)

            # Verify Chinese language pack is available
            try:
                # Try to get available languages
                langs = pytesseract.get_languages()
                if 'chi_sim' not in langs:
                    logger.warning(
                        "[DependencyCheck] Tesseract OCR found but Chinese language pack (chi_sim) is missing. "
                        "Install with: sudo apt-get install tesseract-ocr-chi-sim"
                    )
                    # Don't fail - English OCR will still work
                else:
                    logger.info("[DependencyCheck] Tesseract OCR Chinese language pack (chi_sim) is available")
            except Exception as e:
                logger.warning("[DependencyCheck] Could not verify Tesseract language packs: %s", e)

            return True, None
        except Exception as e:
            # Tesseract binary not found - attempt auto-install on Linux
            if platform.system() == 'Linux' and shutil.which('apt-get'):
                logger.info("[DependencyCheck] Tesseract OCR not found, attempting automatic installation...")
                install_success, install_error = install_tesseract_ocr()

                if install_success:
                    # Retry checking after installation
                    try:
                        version = pytesseract.get_tesseract_version()
                        logger.info(
                            "[DependencyCheck] Tesseract OCR installed successfully: version %s", version
                        )

                        # Verify Chinese language pack
                        try:
                            langs = pytesseract.get_languages()
                            if 'chi_sim' in langs:
                                logger.info(
                                    "[DependencyCheck] Tesseract OCR Chinese language pack "
                                    "(chi_sim) is available"
                                )
                            else:
                                logger.warning("[DependencyCheck] Chinese language pack not found after installation")
                        except Exception:
                            pass  # Language check is optional

                        return True, None
                    except Exception as e2:
                        # Still failed after installation attempt
                        error_msg = (
                            "Tesseract OCR installation attempted but verification failed.\n"
                            f"Error: {str(e2)}\n"
                            "Please install manually:\n"
                            "  - Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim\n"
                        )
                        return False, error_msg
                else:
                    # Auto-install failed, provide manual instructions
                    error_msg = (
                        "Tesseract OCR binary is not installed or not in PATH.\n"
                        f"Auto-installation failed: {install_error}\n"
                        "Please install manually:\n"
                        "  - Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim\n"
                        "  - macOS: brew install tesseract\n"
                        "  - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki\n"
                        f"Original error: {str(e)}"
                    )
                    return False, error_msg
            else:
                # Not Linux or apt-get not available, provide manual instructions
                error_msg = (
                    "Tesseract OCR binary is not installed or not in PATH.\n"
                    "Install with:\n"
                    "  - Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim\n"
                    "  - macOS: brew install tesseract\n"
                    "  - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki\n"
                    f"Error: {str(e)}"
                )
                return False, error_msg

    except Exception as e:
        return False, f"Error checking Tesseract OCR: {str(e)}"


def check_system_dependencies(exit_on_error: bool = True) -> bool:
    """
    Check all required system dependencies for Knowledge Space feature.

    Args:
        exit_on_error: If True, exit the application if dependencies are missing

    Returns:
        True if all dependencies are available, False otherwise
    """
    all_ok = True
    errors = []

    # Check Tesseract OCR (required for image OCR in document processing)
    tesseract_ok, tesseract_error = check_tesseract_ocr()
    if not tesseract_ok:
        all_ok = False
        errors.append(("Tesseract OCR", tesseract_error))

    if not all_ok:
        error_message = "\n\n" + "="*80 + "\n"
        error_message += "MISSING REQUIRED DEPENDENCIES FOR PERSONAL KNOWLEDGE SPACE\n"
        error_message += "="*80 + "\n\n"

        for dep_name, error in errors:
            error_message += f"❌ {dep_name}:\n{error}\n\n"

        error_message += "="*80 + "\n"
        error_message += "Please install the missing dependencies and restart the application.\n"
        error_message += "="*80 + "\n"

        logger.error(error_message)

        if exit_on_error:
            print(error_message, file=sys.stderr)
            sys.exit(1)

    return all_ok


if __name__ == "__main__":
    # Allow running as standalone script for testing
    logging.basicConfig(level=logging.INFO)
    check_system_dependencies(exit_on_error=True)
