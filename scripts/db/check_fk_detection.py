"""
Check foreign key detection logic to find root cause of table creation failures.
"""

import sys
import importlib.util
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import Base using importlib to satisfy Ruff E402 (imports must be at top)
_base_spec = importlib.util.find_spec('models.domain.auth')
if _base_spec is None or _base_spec.loader is None:
    print("Error: Could not find models.domain.auth module")
    sys.exit(1)
_base_module = importlib.util.module_from_spec(_base_spec)
_base_spec.loader.exec_module(_base_module)
Base = _base_module.Base

# Import all models to ensure they're registered with Base.metadata
try:
    _ks_spec = importlib.util.find_spec('models.domain.knowledge_space')
    if _ks_spec is None or _ks_spec.loader is None:
        raise ImportError("Could not find models.domain.knowledge_space module")
    _ks_module = importlib.util.module_from_spec(_ks_spec)
    _ks_spec.loader.exec_module(_ks_module)
    KnowledgeDocument = _ks_module.KnowledgeDocument
    DocumentChunk = _ks_module.DocumentChunk
    ChildChunk = _ks_module.ChildChunk
    ChunkAttachment = _ks_module.ChunkAttachment
    DocumentRelationship = _ks_module.DocumentRelationship
    DocumentVersion = _ks_module.DocumentVersion
    # Access __tablename__ to satisfy linter (models needed for registration)
    _ = KnowledgeDocument.__tablename__
    _ = DocumentChunk.__tablename__
    _ = ChildChunk.__tablename__
    _ = ChunkAttachment.__tablename__
    _ = DocumentRelationship.__tablename__
    _ = DocumentVersion.__tablename__
except ImportError as e:
    print(f"Error importing knowledge_space models: {e}")
    sys.exit(1)

try:
    _dv_spec = importlib.util.find_spec('models.domain.debateverse')
    if _dv_spec is None or _dv_spec.loader is None:
        raise ImportError("Could not find models.domain.debateverse module")
    _dv_module = importlib.util.module_from_spec(_dv_spec)
    _dv_spec.loader.exec_module(_dv_module)
    DebateSession = _dv_module.DebateSession
    DebateParticipant = _dv_module.DebateParticipant
    DebateMessage = _dv_module.DebateMessage
    DebateJudgment = _dv_module.DebateJudgment
    # Access __tablename__ to satisfy linter (models needed for registration)
    _ = DebateSession.__tablename__
    _ = DebateParticipant.__tablename__
    _ = DebateMessage.__tablename__
    _ = DebateJudgment.__tablename__
except ImportError as e:
    print(f"Error importing debateverse models: {e}")
    sys.exit(1)

try:
    _kq_spec = importlib.util.find_spec('models.domain.knowledge_query')
    if _kq_spec is None or _kq_spec.loader is None:
        raise ImportError("Could not find models.domain.knowledge_query module")
    _kq_module = importlib.util.module_from_spec(_kq_spec)
    _kq_spec.loader.exec_module(_kq_module)
    KnowledgeQuery = _kq_module.KnowledgeQuery
    QueryFeedback = _kq_module.QueryFeedback
    EvaluationResult = _kq_module.EvaluationResult
    EvaluationDataset = _kq_module.EvaluationDataset
    # Access __tablename__ to satisfy linter (models needed for registration)
    _ = KnowledgeQuery.__tablename__
    _ = QueryFeedback.__tablename__
    _ = EvaluationResult.__tablename__
    _ = EvaluationDataset.__tablename__
except ImportError as e:
    print(f"Error importing knowledge_query models: {e}")
    sys.exit(1)


def check_table_fks(table_name: str) -> None:
    """Check foreign key relationships for a table."""
    if table_name not in Base.metadata.tables:
        print(f"  Table {table_name} not found in metadata")
        return

    table = Base.metadata.tables[table_name]
    print(f"\n{table_name}:")
    print(f"  Foreign keys: {len(table.foreign_keys)}")

    for fk in table.foreign_keys:
        # Try different ways to get parent table name
        try:
            parent_table_via_column = fk.column.table.name
        except Exception as e:
            parent_table_via_column = f"ERROR: {e}"

        try:
            # Alternative: get via parent column's table
            parent_table_via_parent = fk.parent.table.name if hasattr(fk.parent, 'table') else "N/A"
        except Exception as e:
            parent_table_via_parent = f"ERROR: {e}"

        try:
            # Get referenced table directly
            referenced_table = fk.column.table.name if hasattr(fk.column, 'table') else "N/A"
        except Exception as e:
            referenced_table = f"ERROR: {e}"

        print(f"    FK: {fk.parent.name} -> {parent_table_via_column}.{fk.column.name}")
        print(f"      (via column.table.name: {parent_table_via_column})")
        if parent_table_via_parent != parent_table_via_column:
            print(f"      (via parent.table.name: {parent_table_via_parent})")
        if referenced_table != parent_table_via_column:
            print(f"      (referenced_table: {referenced_table})")

        # Check if parent table exists in metadata
        if parent_table_via_column in Base.metadata.tables:
            print(f"      ✓ Parent table '{parent_table_via_column}' exists in metadata")
        else:
            print(f"      ✗ Parent table '{parent_table_via_column}' MISSING from metadata!")


def main():
    """Main entry point."""
    print("=" * 80)
    print("Foreign Key Detection Analysis")
    print("=" * 80)

    failing_tables = [
        'child_chunks',
        'chunk_attachments',
        'debate_judgments',
        'debate_messages',
        'document_chunks',
        'document_relationships',
        'document_versions',
        'evaluation_results',
        'query_feedback'
    ]

    print("\nAll tables in metadata:")
    for table_name in sorted(Base.metadata.tables.keys()):
        print(f"  - {table_name}")

    print("\n" + "=" * 80)
    print("Checking failing tables:")
    print("=" * 80)

    for table_name in failing_tables:
        check_table_fks(table_name)

    print("\n" + "=" * 80)
    print("Checking parent tables:")
    print("=" * 80)

    parent_tables = [
        'knowledge_documents',
        'document_chunks',
        'debate_sessions',
        'debate_participants',
        'users',
        'knowledge_spaces',
        'knowledge_queries',
        'evaluation_datasets'
    ]

    for table_name in parent_tables:
        if table_name in Base.metadata.tables:
            print(f"\n{table_name}: EXISTS in metadata")
        else:
            print(f"\n{table_name}: MISSING from metadata!")


if __name__ == '__main__':
    main()
