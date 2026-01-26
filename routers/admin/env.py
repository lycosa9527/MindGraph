"""Admin Environment Settings Router.

Enhanced .env configuration management endpoints with:
- Full backup/restore capabilities
- Comprehensive validation
- Settings schema metadata
- Audit logging

Security:
- JWT authentication required
- Admin role check on all endpoints
- Path traversal prevention
- Sensitive data masking

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from models.domain.auth import User
from services.infrastructure.utils.env_manager import EnvManager
from utils.auth import get_current_user, is_admin



logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/admin/env", tags=["Admin - Environment Settings"])


@router.get("/settings", dependencies=[Depends(get_current_user)])
async def get_env_settings(
    current_user: User = Depends(get_current_user)
):
    """
    Get all environment settings with metadata (ADMIN ONLY)

    Returns:
        - settings: Current .env values (sensitive fields masked)
        - schema: Metadata for each setting (type, category, description, validation)

    Security:
        - Masks API keys, secrets, passkeys (shows last 4 chars only)
        - Hides DATABASE_URL completely
        - JWT_SECRET_KEY is auto-managed via Redis (not in .env)
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        env_manager = EnvManager()

        # Read current settings
        settings = env_manager.read_env()

        # Get schema metadata
        schema = env_manager.get_env_schema()

        # Mask sensitive values
        masked_settings = {}
        for key, value in settings.items():
            if not value:
                masked_settings[key] = value
                continue

            # Completely hide these critical settings
            # Note: JWT_SECRET_KEY is now auto-managed via Redis (not in .env)
            if key in ['DATABASE_URL']:
                masked_settings[key] = "***HIDDEN***"
                continue

            # Mask API keys, secrets, passwords, passkeys
            if any(sensitive in key for sensitive in ['API_KEY', 'SECRET', 'PASSWORD', 'PASSKEY']):
                if len(value) > 4:
                    masked_settings[key] = f"***...{value[-4:]}"
                else:
                    masked_settings[key] = "***"
                continue

            # Not sensitive, return as-is
            masked_settings[key] = value

        logger.info("Admin %s accessed environment settings", current_user.phone)

        return {
            "settings": masked_settings,
            "schema": schema
        }

    except Exception as e:
        logger.error("Failed to get environment settings: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get settings: {str(e)}"
        ) from e


@router.put("/settings", dependencies=[Depends(get_current_user)])
async def update_env_settings(
    request: Dict[str, str],
    current_user: User = Depends(get_current_user)
):
    """
    Update environment settings in .env file (ADMIN ONLY)

    Process:
    1. Validate all provided settings
    2. Create backup of current .env
    3. Write new settings (preserving comments)
    4. Return success with backup filename

    Security:
    - Validates all inputs before writing
    - Creates automatic backup before changes
    - Prevents modification of DATABASE_URL via this endpoint
    - JWT_SECRET_KEY is auto-managed via Redis (not configurable)
    - Logs all changes with admin user ID
    - Skips masked values to preserve existing secrets

    Args:
        request: Dict of setting key-value pairs to update

    Returns:
        {
            "message": "Settings updated successfully",
            "backup_file": "backup filename",
            "updated_keys": ["list", "of", "updated", "keys"],
            "warning": "Server restart required for changes to take effect"
        }
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    # Security: Prevent modification of critical settings via web UI
    # Note: JWT_SECRET_KEY is now auto-managed via Redis (not in .env)
    forbidden_keys = ['DATABASE_URL']
    for key in request:
        if key in forbidden_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot modify {key} via web interface. Edit .env file directly for security."
            )

    try:
        env_manager = EnvManager()

        # Read existing settings to preserve masked values
        existing_settings = env_manager.read_env()

        # Filter out masked values - preserve existing secrets
        def _is_masked_value(value):
            """Check if value is a masked placeholder."""
            if not value:
                return False
            masked_patterns = ("***...", "***HIDDEN***", "***", "******")
            return value.startswith("***...") or value in masked_patterns

        filtered_request = {}
        skipped_masked = []
        for key, value in request.items():
            if _is_masked_value(value):
                # This is a masked value - keep the existing value from .env
                if key in existing_settings:
                    filtered_request[key] = existing_settings[key]
                    skipped_masked.append(key)
            else:
                # This is a real value - use it
                filtered_request[key] = value

        if skipped_masked:
            logger.info("Preserved %d masked values: %s", len(skipped_masked), ', '.join(skipped_masked))

        # Validate settings before writing
        is_valid, errors = env_manager.validate_env(filtered_request)
        if not is_valid:
            logger.warning("Settings validation failed: %s", errors)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation errors: {', '.join(errors)}"
            )

        # Create backup before making changes
        backup_file = env_manager.backup_env()
        logger.info("Created backup: %s", backup_file)

        # Write new settings
        env_manager.write_env(filtered_request)

        # Log the change (mask sensitive values in log)
        masked_keys = []
        for key, value in filtered_request.items():
            if any(sensitive in key for sensitive in ['API_KEY', 'SECRET', 'PASSWORD', 'PASSKEY']):
                masked_keys.append(f"{key}=***")
            else:
                masked_keys.append(f"{key}={value}")

        logger.warning(
            "Admin %s updated .env settings: %s",
            current_user.phone,
            ', '.join(masked_keys)
        )

        return {
            "message": "Settings updated successfully",
            "backup_file": backup_file,
            "updated_keys": list(filtered_request.keys()),
            "warning": "⚠️ Server restart required for changes to take effect!"
        }

    except ValueError as e:
        logger.error("Settings update failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error("Unexpected error updating settings: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        ) from e


@router.post("/validate", dependencies=[Depends(get_current_user)])
async def validate_env_settings(
    request: Dict[str, str],
    current_user: User = Depends(get_current_user)
):
    """
    Validate settings without writing to file (ADMIN ONLY)

    Useful for:
    - Frontend validation before save
    - Testing configuration changes
    - Checking for errors before applying

    Args:
        request: Dict of settings to validate

    Returns:
        {
            "is_valid": True/False,
            "errors": ["list", "of", "errors"] or []
        }
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        env_manager = EnvManager()
        is_valid, errors = env_manager.validate_env(request)

        return {
            "is_valid": is_valid,
            "errors": errors
        }

    except Exception as e:
        logger.error("Validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        ) from e


@router.get("/backups", dependencies=[Depends(get_current_user)])
async def list_env_backups(
    current_user: User = Depends(get_current_user)
):
    """
    List all available .env backup files (ADMIN ONLY)

    Returns:
        List of backup info dicts:
        [
            {
                "filename": ".env.backup.2025-10-14_15-30-45",
                "size_bytes": 1234,
                "created_at": "2025-10-14T15:30:45",
                "timestamp": "2025-10-14 15:30:45"
            },
            ...
        ]

    Sorted by timestamp (newest first)
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        env_manager = EnvManager()
        backups = env_manager.list_backups()

        logger.info("Admin %s listed %d backups", current_user.phone, len(backups))

        return backups

    except Exception as e:
        logger.error("Failed to list backups: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list backups: {str(e)}"
        ) from e


@router.post("/restore", dependencies=[Depends(get_current_user)])
async def restore_env_from_backup(
    backup_filename: str,
    current_user: User = Depends(get_current_user)
):
    """
    Restore .env from a backup file (ADMIN ONLY)

    Safety features:
    - Creates new backup of current state before restoring
    - Validates backup file exists and is safe
    - Prevents path traversal attacks

    Args:
        backup_filename: Name of backup file (e.g., ".env.backup.2025-10-14_15-30-45")

    Returns:
        {
            "message": "Restored successfully",
            "restored_from": "backup filename",
            "safety_backup": "new backup filename created before restore"
        }

    Security:
    - Path validation (prevents ../../../etc/passwd attacks)
    - Admin authentication required
    - Audit logging
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    # Security: Validate filename to prevent path traversal
    if not backup_filename or ".." in backup_filename or "/" in backup_filename or "\\" in backup_filename:
        logger.warning(
            "Admin %s attempted invalid backup filename: %s",
            current_user.phone,
            backup_filename
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid backup filename. Path traversal not allowed."
        )

    try:
        env_manager = EnvManager()

        # Restore (this creates a safety backup automatically)
        success = env_manager.restore_env(backup_filename)

        if success:
            logger.warning(
                "Admin %s restored .env from backup: %s",
                current_user.phone,
                backup_filename
            )

            return {
                "message": "Restored successfully from backup",
                "restored_from": backup_filename,
                "warning": "⚠️ Server restart required for changes to take effect!"
            }
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Restore operation failed"
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup file not found: {backup_filename}"
        ) from exc
    except ValueError as e:
        logger.error("Restore failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error("Unexpected error during restore: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore from backup: {str(e)}"
        ) from e


@router.get("/schema", dependencies=[Depends(get_current_user)])
async def get_env_schema(
    current_user: User = Depends(get_current_user)
):
    """
    Get environment settings schema metadata (ADMIN ONLY)

    Returns metadata for each setting:
    - Type (string, integer, boolean, etc.)
    - Category (for UI grouping)
    - Description
    - Default value
    - Whether required
    - Validation constraints (min, max, etc.)

    Used by frontend to dynamically generate settings form.
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        env_manager = EnvManager()
        schema = env_manager.get_env_schema()

        return schema

    except Exception as e:
        logger.error("Failed to get schema: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get schema: {str(e)}"
        ) from e
