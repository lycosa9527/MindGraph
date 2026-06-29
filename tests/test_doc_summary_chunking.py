"""Chunking policy tests for Document Summary chat sources."""

from services.knowledge.chunking_policy import resolve_chunking_policy


def test_paste_uses_flat_chunking() -> None:
    """Pasted notes use automatic (flat) chunking."""
    policy = resolve_chunking_policy("text/markdown", None, ingest_source="paste")
    assert policy.mode == "automatic"


def test_wechat_uses_flat_chunking() -> None:
    """WeChat transcripts use automatic chunking."""
    policy = resolve_chunking_policy("text/markdown", None, ingest_source="wechat")
    assert policy.mode == "automatic"


def test_dingtalk_uses_flat_chunking() -> None:
    """DingTalk transcripts use automatic chunking."""
    policy = resolve_chunking_policy("text/markdown", None, ingest_source="dingtalk")
    assert policy.mode == "automatic"


def test_wecom_uses_flat_chunking() -> None:
    """WeCom transcripts use automatic chunking."""
    policy = resolve_chunking_policy("text/markdown", None, ingest_source="wecom")
    assert policy.mode == "automatic"


def test_pdf_still_hierarchical() -> None:
    """PDF documents keep hierarchical chunking."""
    policy = resolve_chunking_policy("application/pdf", None, ingest_source="file")
    assert policy.mode == "hierarchical"
