"""Request-scoped attribution for MindChunk LLM calls.

MindChunk's structure/boundary/content-type agents make LLM calls during
document ingestion. Threading ``user_id`` through every signature is noisy, so
the knowledge-space ingest path sets a ``ContextVar`` that the agents read for
per-user token attribution. The flag is isolated per asyncio task.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, Optional, Tuple

INGEST_REQUEST_TYPE = "knowledge_ingest"

# MindChunk's structure/boundary/content-type calls are classification-style work;
# route them to the classification model (QwenClient("classification")), not the
# generation model used for diagram content.
CLASSIFICATION_MODEL = "qwen-turbo"

_ingest_user_id: ContextVar[Optional[int]] = ContextVar("ingest_user_id", default=None)
_ingest_org_id: ContextVar[Optional[int]] = ContextVar("ingest_org_id", default=None)


def get_ingest_attribution() -> Tuple[Optional[int], Optional[int], str]:
    """Return (user_id, organization_id, request_type) for the active ingest."""
    return _ingest_user_id.get(), _ingest_org_id.get(), INGEST_REQUEST_TYPE


def ingest_chat_kwargs() -> Dict[str, Any]:
    """Common ``llm_service.chat`` kwargs for MindChunk agents.

    Routes to the classification model, disables implicit whole-library RAG
    (ingest must never read the user's KB), and attributes token usage.
    """
    user_id, organization_id, request_type = get_ingest_attribution()
    return {
        "model": CLASSIFICATION_MODEL,
        "use_knowledge_base": False,
        "user_id": user_id,
        "organization_id": organization_id,
        "request_type": request_type,
    }


@contextmanager
def ingest_attribution(user_id: Optional[int], organization_id: Optional[int] = None) -> Iterator[None]:
    """Attribute MindChunk LLM token usage to a user during ingestion."""
    user_token = _ingest_user_id.set(user_id)
    org_token = _ingest_org_id.set(organization_id)
    try:
        yield
    finally:
        _ingest_user_id.reset(user_token)
        _ingest_org_id.reset(org_token)
