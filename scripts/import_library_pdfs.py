"""
Command-line script to import existing PDFs from storage/library/ into the database.

This script uses the pdf_importer module from services.library.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.database import SessionLocal
from services.library.pdf_importer import import_pdfs_from_folder


def main():
    """Main entry point for command-line script."""
    db = SessionLocal()
    try:
        print("Importing PDFs from storage/library/...")
        print()
        
        imported_count, skipped_count = import_pdfs_from_folder(db)
        
        print("=" * 80)
        print(f"Import complete: {imported_count} imported, {skipped_count} skipped")
        
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nError importing PDFs: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
