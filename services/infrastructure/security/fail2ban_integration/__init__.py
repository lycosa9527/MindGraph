"""
Fail2ban integration: repo template paths, deploy helper, ban-action CLI for AbuseIPDB.
"""

from .paths import fail2ban_resources_dir, project_root_from_here

__all__ = ["fail2ban_resources_dir", "project_root_from_here"]
