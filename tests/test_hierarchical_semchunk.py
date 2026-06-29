"""Hierarchical semchunk emits section metadata on chunks."""

from services.knowledge.chunking_service import ChunkingService


def test_hierarchical_semchunk_tags_sections() -> None:
    """Hierarchical mode attaches section_key metadata to chunks."""
    text = (
        "Chapter 1: Start\n"
        "First chapter content that is long enough to remain after split.\n\n"
        "Chapter 2: Next\n"
        "Second chapter with different material for retrieval tests."
    )
    service = ChunkingService(chunk_size=500, overlap=50, mode="hierarchical")
    chunks = service.chunk_text(text, metadata={"document_id": 1}, extract_structure=True)
    assert chunks
    keys = {chunk.metadata.get("section_key") for chunk in chunks}
    assert "chapter-1" in keys
    assert "chapter-2" in keys
    assert any(chunk.metadata.get("section_title", "").startswith("Chapter 1") for chunk in chunks)
