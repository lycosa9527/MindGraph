"""
Quick verification and fix script for chunk test table schema issues.

This script checks if the required columns exist and provides SQL to fix them.
Run with: python scripts/verify_and_fix_chunk_test_schema.py
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('PYTHONPATH', str(project_root))

try:
    from sqlalchemy import inspect, text
    from config.database import engine
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    print("\nPlease ensure you're in the correct Python environment.")
    sys.exit(1)


def check_and_fix():
    """Check schema and provide fix SQL."""
    inspector = inspect(engine)
    dialect = engine.dialect.name
    
    print("=" * 80)
    print("Chunk Test Schema Verification")
    print("=" * 80)
    print(f"Database dialect: {dialect}\n")
    
    issues_found = []
    fixes = []
    
    # Check chunk_test_results.session_id
    if 'chunk_test_results' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('chunk_test_results')]
        if 'session_id' not in columns:
            issues_found.append("chunk_test_results.session_id is missing")
            if dialect == 'sqlite':
                fixes.append("ALTER TABLE chunk_test_results ADD COLUMN session_id TEXT NULL;")
            else:
                fixes.append("ALTER TABLE chunk_test_results ADD COLUMN session_id VARCHAR(36) NULL;")
            fixes.append("CREATE INDEX IF NOT EXISTS ix_chunk_test_results_session_id ON chunk_test_results(session_id);")
        else:
            print("✓ chunk_test_results.session_id exists")
    else:
        print("⚠ Table chunk_test_results does not exist yet")
    
    # Check chunk_test_documents.meta_data
    if 'chunk_test_documents' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('chunk_test_documents')]
        if 'meta_data' not in columns:
            issues_found.append("chunk_test_documents.meta_data is missing")
            if dialect == 'sqlite':
                fixes.append("ALTER TABLE chunk_test_documents ADD COLUMN meta_data TEXT NULL;")
            else:
                fixes.append("ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;")
        else:
            print("✓ chunk_test_documents.meta_data exists")
    else:
        print("⚠ Table chunk_test_documents does not exist yet")
    
    # Check chunk_test_document_chunks.chunking_method
    if 'chunk_test_document_chunks' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('chunk_test_document_chunks')]
        if 'chunking_method' not in columns:
            issues_found.append("chunk_test_document_chunks.chunking_method is missing")
            if dialect == 'sqlite':
                fixes.append("ALTER TABLE chunk_test_document_chunks ADD COLUMN chunking_method TEXT NULL;")
            else:
                fixes.append("ALTER TABLE chunk_test_document_chunks ADD COLUMN chunking_method VARCHAR(50) NULL;")
            fixes.append("CREATE INDEX IF NOT EXISTS ix_chunk_test_document_chunks_chunking_method ON chunk_test_document_chunks(chunking_method);")
            fixes.append("CREATE INDEX IF NOT EXISTS ix_chunk_test_document_chunks_document_method ON chunk_test_document_chunks(document_id, chunking_method);")
        else:
            print("✓ chunk_test_document_chunks.chunking_method exists")
        
        # Check chunk_test_document_chunks.meta_data
        if 'meta_data' not in columns:
            issues_found.append("chunk_test_document_chunks.meta_data is missing")
            if dialect == 'sqlite':
                fixes.append("ALTER TABLE chunk_test_document_chunks ADD COLUMN meta_data TEXT NULL;")
            else:
                fixes.append("ALTER TABLE chunk_test_document_chunks ADD COLUMN meta_data JSON NULL;")
        else:
            print("✓ chunk_test_document_chunks.meta_data exists")
    else:
        print("⚠ Table chunk_test_document_chunks does not exist yet")
    
    if issues_found:
        print("\n" + "=" * 80)
        print("ISSUES FOUND:")
        print("=" * 80)
        for issue in issues_found:
            print(f"  ✗ {issue}")
        
        print("\n" + "=" * 80)
        print("SQL FIXES:")
        print("=" * 80)
        for fix in fixes:
            print(fix)
        
        print("\n" + "=" * 80)
        print("APPLY FIXES?")
        print("=" * 80)
        response = input("Apply these fixes now? (y/n): ").strip().lower()
        
        if response == 'y':
            try:
                with engine.connect() as conn:
                    for fix in fixes:
                        print(f"Executing: {fix}")
                        conn.execute(text(fix))
                    conn.commit()
                print("\n✓ All fixes applied successfully!")
                print("\nPlease restart your server for changes to take effect.")
            except Exception as e:
                print(f"\n✗ Error applying fixes: {e}")
                print("\nYou can run the SQL commands manually using your database client.")
        else:
            print("\nSkipped. You can run the SQL commands manually.")
    else:
        print("\n✓ All required columns exist. Schema is up to date!")


if __name__ == "__main__":
    try:
        check_and_fix()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
