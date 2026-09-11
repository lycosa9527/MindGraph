"""Dify upload MIME and chat-messages file type mapping."""

import pytest
from pydantic import ValidationError

from models.requests.requests_assistant import AIAssistantFile
from services.dify.file_upload_types import (
    DIFY_DOCUMENT_MAX_BYTES,
    DIFY_GATEWAY_UPLOAD_EXTENSIONS,
    DIFY_IMAGE_MAX_BYTES,
    dify_chat_file_type,
    dify_upload_content_type,
    dify_upload_max_bytes,
)
from services.mindbot.platforms.dingtalk.inbound.parser import media_filename_and_types


def test_office_and_pdf_are_document() -> None:
    """Word, PDF, and PowerPoint map to Dify type document."""
    assert dify_chat_file_type("plan.doc", "") == "document"
    assert dify_chat_file_type("plan.docx", "") == "document"
    assert dify_chat_file_type("notes.pdf", "") == "document"
    assert dify_chat_file_type("deck.ppt", "") == "document"
    assert dify_chat_file_type("deck.pptx", "") == "document"


def test_image_extension_wins_over_empty_mime() -> None:
    """Dify classifies by extension before MIME."""
    assert dify_chat_file_type("shot.png", "") == "image"
    assert dify_chat_file_type("shot.png", "application/octet-stream") == "image"


def test_mime_fallback_matches_dify() -> None:
    """Without a known extension, only image/video/audio/text/pdf MIME count."""
    assert dify_chat_file_type("notes", "application/pdf") == "document"
    assert dify_chat_file_type("plan", "application/msword") == "custom"
    assert dify_chat_file_type("photo", "image/jpeg") == "image"


def test_upload_infers_office_mime_from_extension() -> None:
    """Generic browser MIME is replaced with the Dify-facing Office MIME."""
    assert (
        dify_upload_content_type("plan.docx", "application/octet-stream")
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert dify_upload_content_type("notes.pdf", "") == "application/pdf"
    assert (
        dify_upload_content_type("deck.pptx", None)
        == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    assert dify_upload_content_type("notes.pdf", "application/pdf") == "application/pdf"


def test_size_caps_match_dify_defaults() -> None:
    """Images 10MB; documents 15MB."""
    assert dify_upload_max_bytes("shot.png") == DIFY_IMAGE_MAX_BYTES
    assert dify_upload_max_bytes("notes.pdf") == DIFY_DOCUMENT_MAX_BYTES
    assert dify_upload_max_bytes("deck.pptx") == DIFY_DOCUMENT_MAX_BYTES


def test_gateway_allowlist_covers_office_and_pdf() -> None:
    """Composer formats are accepted by the Dify upload gateway."""
    assert {"doc", "docx", "pdf", "ppt", "pptx", "png"} <= DIFY_GATEWAY_UPLOAD_EXTENSIONS


def test_chat_file_model_normalizes_dify_type() -> None:
    """Stream requests lowercase and reject unknown Dify file types."""
    item = AIAssistantFile(
        type="DOCUMENT",
        transfer_method="LOCAL_FILE",
        url=None,
        upload_file_id="abc",
    )
    assert item.type == "document"
    assert item.transfer_method == "local_file"
    with pytest.raises(ValidationError):
        AIAssistantFile(
            type="photo",
            transfer_method="local_file",
            url=None,
            upload_file_id="abc",
        )


def test_dingtalk_office_files_use_dify_document_mapping() -> None:
    """DingTalk file attachments share the MindMate Dify type/MIME path."""
    _name, mime, file_type = media_filename_and_types(
        "file",
        {"content": {"fileName": "deck.pptx"}},
    )
    assert file_type == "document"
    assert mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    _name, pdf_mime, pdf_type = media_filename_and_types(
        "file",
        {"content": {"fileName": "notes.pdf"}},
    )
    assert pdf_type == "document"
    assert pdf_mime == "application/pdf"
