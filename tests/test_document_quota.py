"""The per-user document cap ignores files the settings panel cannot show."""

from services.knowledge.document_quota import documents_toward_cap_stmt, over_quota_message


def test_cap_skips_document_summary_and_folderless_rows() -> None:
    """The count keeps files that still have a folder, and leaves Document Summary out."""
    sql = str(documents_toward_cap_stmt(7).compile(compile_kwargs={"literal_binds": True})).lower()
    assert "join document_batches" in sql
    assert "doc_summary" in sql
    assert "is null" in sql


def test_rejection_names_how_many_are_stored() -> None:
    """The API text includes the stored count behind an empty-looking folder."""
    assert over_quota_message(5, 5) == (
        "Maximum 5 documents allowed (5 already stored). Please delete a document first."
    )
