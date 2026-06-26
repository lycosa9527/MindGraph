"""Tests for PG merge staging schema restore rewriting."""

from __future__ import annotations

from services.admin.pg_merge_staging import (
    StagingArea,
    _format_psql_error,
    _rewrite_restore_line,
    _skip_restore_line,
)


def test_skip_public_schema_bootstrap_lines() -> None:
    """Bootstrap DDL for the public schema is skipped during restore rewrite."""
    assert _skip_restore_line("CREATE SCHEMA public;\n") is True
    assert _skip_restore_line("COMMENT ON SCHEMA public IS 'standard public schema';\n") is True
    assert _skip_restore_line("ALTER SCHEMA public OWNER TO postgres;\n") is True
    assert _skip_restore_line("GRANT ALL ON SCHEMA public TO postgres;\n") is True
    assert _skip_restore_line("CREATE TABLE public.users (\n") is False


def test_skip_extension_and_global_lines() -> None:
    """Extension and global database lines are skipped during restore rewrite."""
    assert _skip_restore_line("CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA public;\n") is True
    assert (
        _skip_restore_line("COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics';\n")
        is True
    )
    assert _skip_restore_line("ALTER DATABASE mindgraph SET timezone TO 'UTC';\n") is True
    assert _skip_restore_line("GRANT CONNECT ON DATABASE mindgraph TO mindgraph_app;\n") is True
    assert _skip_restore_line("ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT SELECT ON TABLES TO public;\n") is True
    assert (
        _rewrite_restore_line(
            "COMMENT ON EXTENSION pg_stat_statements IS 'track';\n",
            "mindgraph_merge_staging_ab12cd34",
        )
        is None
    )


def test_rewrite_restore_line_maps_public_to_staging_schema() -> None:
    """public references are rewritten to the staging schema name."""
    schema = "mindgraph_merge_staging_ab12cd34"
    create_table = _rewrite_restore_line("CREATE TABLE public.users (\n", schema)
    assert create_table == f'CREATE TABLE "{schema}".users (\n'

    copy_line = _rewrite_restore_line("COPY public.users FROM stdin;\n", schema)
    assert copy_line == f'COPY "{schema}".users FROM stdin;\n'

    search_path = _rewrite_restore_line(
        "SELECT pg_catalog.set_config('search_path', 'public', false);\n",
        schema,
    )
    assert search_path == f"SELECT pg_catalog.set_config('search_path', '{schema}', false);\n"


def test_rewrite_restore_line_skips_connect_meta() -> None:
    """psql \\connect meta lines are dropped during rewrite."""
    assert _rewrite_restore_line("\\connect mindgraph\n", "mindgraph_merge_staging_x") is None


def test_format_psql_error_extracts_message() -> None:
    """psql stderr is parsed to extract the ERROR message."""
    stderr = "psql:/tmp/test.sql:47: ERROR: must be owner of extension pg_stat_statements\n"
    assert _format_psql_error(stderr) == "must be owner of extension pg_stat_statements"


def test_staging_area_dataclass() -> None:
    """StagingArea holds db_url and staging schema name."""
    area = StagingArea(
        db_url="postgresql://mindgraph_migrate:pw@localhost:5432/mindgraph",
        schema_name="mindgraph_merge_staging_test1234",
    )
    assert area.schema_name.startswith("mindgraph_merge_staging_")
