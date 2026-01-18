"""
Role Checking for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Functions to check user roles and permissions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from .config import AUTH_MODE, ADMIN_PHONES


def is_admin(current_user) -> bool:
    """
    Check if user is admin (full access to all data)

    Admin access granted if:
    1. User has role='admin' in database
    2. User phone in ADMIN_PHONES env variable (production admins)
    3. User is demo-admin@system.com AND server is in demo mode (demo admin)
    4. User is bayi-admin@system.com AND server is in bayi mode (bayi admin)

    This ensures demo/bayi admin passkey only works in their respective modes
    for security.

    Args:
        current_user: User model object

    Returns:
        True if user is admin, False otherwise
    """
    # Check database role field
    if hasattr(current_user, 'role') and current_user.role == 'admin':
        return True

    # Check ADMIN_PHONES list (production admins)
    admin_phones = [p.strip() for p in ADMIN_PHONES if p.strip()]
    if current_user.phone in admin_phones:
        return True

    # Check demo admin (only in demo mode for security)
    if AUTH_MODE == "demo" and current_user.phone == "demo-admin@system.com":
        return True

    # Check bayi admin (only in bayi mode for security)
    if AUTH_MODE == "bayi" and current_user.phone == "bayi-admin@system.com":
        return True

    return False


def is_manager(current_user) -> bool:
    """
    Check if user is a manager (org-scoped admin access)

    Manager can access admin dashboard but only sees their organization's data.

    Args:
        current_user: User model object

    Returns:
        True if user is manager, False otherwise
    """
    if hasattr(current_user, 'role') and current_user.role == 'manager':
        return True
    return False


def is_admin_or_manager(current_user) -> bool:
    """
    Check if user has any elevated access (admin or manager)

    Used for routes that both admin and manager can access.

    Args:
        current_user: User model object

    Returns:
        True if user is admin or manager, False otherwise
    """
    return is_admin(current_user) or is_manager(current_user)


def get_user_role(current_user) -> str:
    """
    Get the effective role of a user

    Args:
        current_user: User model object

    Returns:
        'admin', 'manager', or 'user'
    """
    if is_admin(current_user):
        return 'admin'
    if is_manager(current_user):
        return 'manager'
    return 'user'
