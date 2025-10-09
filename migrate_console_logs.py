#!/usr/bin/env python3
"""
Console Log Migration Script
=============================

Automatically migrates console.log/warn/error to the new logger system.

@author lycosa9527
@made_by MindSpring Team
"""

import re
import sys
from pathlib import Path

# Patterns to delete entirely (obvious/unnecessary logs)
DELETE_PATTERNS = [
    r"console\.log\('ToolbarManager: .*button clicked'\);?\s*\n",
    r"console\.log\('ToolbarManager: .*Button button clicked'\);?\s*\n",
    r"console\.log\('Property panel cleared to default values'\);?\s*\n",
    r"console\.log\('ToolbarManager: applyText showing notification.*'\);?\s*\n",
    r"console\.log\('ToolbarManager: applyText notification suppressed.*'\);?\s*\n",
]

# Simple replacements (console.log → logger.debug)
SIMPLE_REPLACEMENTS = {
    # Format: (pattern, replacement)
    (r"console\.log\('ToolbarManager: (.*?)'\);", r"logger.debug('ToolbarManager', '\1');"),
    (r"console\.warn\('ToolbarManager: (.*?)'\);", r"logger.warn('ToolbarManager', '\1');"),
    (r"console\.error\('ToolbarManager: (.*?)'\);", r"logger.error('ToolbarManager', '\1');"),
}

def migrate_file(filepath):
    """Migrate a single JavaScript file"""
    print(f"Migrating {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Step 1: Delete unnecessary logs
    for pattern in DELETE_PATTERNS:
        content = re.sub(pattern, '', content, flags=re.MULTILINE)
    
    # Step 2: Simple replacements
    for pattern, replacement in SIMPLE_REPLACEMENTS:
        content = re.sub(pattern, replacement, content)
    
    # Step 3: More complex patterns (with data objects)
    # console.log('Message:', data) → logger.debug('Component', 'Message', data)
    content = re.sub(
        r"console\.log\('ToolbarManager: (.*?):', (.*?)\);",
        r"logger.debug('ToolbarManager', '\1', \2);",
        content
    )
    
    if content != original_content:
        # Backup original
        backup_path = Path(str(filepath) + '.backup')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        
        # Write migrated version
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Migrated {filepath}")
        print(f"   Backup saved to {backup_path}")
        return True
    else:
        print(f"ℹ️  No changes needed for {filepath}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate_console_logs.py <file1.js> [file2.js] ...")
        sys.exit(1)
    
    files = sys.argv[1:]
    migrated_count = 0
    
    for filepath in files:
        if migrate_file(filepath):
            migrated_count += 1
    
    print(f"\n✅ Migration complete! {migrated_count}/{len(files)} files modified.")

if __name__ == '__main__':
    main()

