"""
Domain Models

SQLAlchemy database models representing core domain entities.
"""

from .auth import (
    Base,
    Organization,
    User,
    APIKey,
)
from .diagrams import Diagram
from .knowledge_space import (
    KnowledgeSpace,
    KnowledgeDocument,
    DocumentChunk,
    DocumentBatch,
    DocumentVersion,
    KnowledgeQuery,
    QueryTemplate,
    QueryFeedback,
    ChunkTestDocument,
    ChunkTestDocumentChunk,
    ChunkTestResult,
    EvaluationDataset,
    EvaluationResult,
    DocumentRelationship,
    Embedding,
)
from .messages import Messages, Language, get_request_language
from .token_usage import TokenUsage
from .dashboard_activity import DashboardActivity
from .user_activity_log import UserActivityLog
from .user_usage_stats import UserUsageStats
from .debateverse import (
    DebateSession,
    DebateMessage,
    DebateParticipant,
)
from .school_zone import (
    SharedDiagram,
    SharedDiagramLike,
    SharedDiagramComment,
)
from .library import (
    LibraryDocument,
    LibraryDanmaku,
    LibraryDanmakuLike,
    LibraryDanmakuReply,
)
from .pinned_conversations import PinnedConversation
from .env_settings import EnvSetting
from .gewe_message import GeweMessage
from .gewe_contact import GeweContact
from .gewe_group_member import GeweGroupMember

__all__ = [
    # Base
    "Base",
    # Auth
    "Organization",
    "User",
    "APIKey",
    # Diagrams
    "Diagram",
    # Knowledge Space
    "KnowledgeSpace",
    "KnowledgeDocument",
    "DocumentChunk",
    "DocumentBatch",
    "DocumentVersion",
    "KnowledgeQuery",
    "QueryTemplate",
    "QueryFeedback",
    "ChunkTestDocument",
    "ChunkTestDocumentChunk",
    "ChunkTestResult",
    "EvaluationDataset",
    "EvaluationResult",
    "DocumentRelationship",
    "Embedding",
    # Messages
    "Messages",
    "Language",
    "get_request_language",
    # Token Usage
    "TokenUsage",
    # Dashboard
    "DashboardActivity",
    # User Activity / Usage Stats
    "UserActivityLog",
    "UserUsageStats",
    # Debateverse
    "DebateSession",
    "DebateMessage",
    "DebateParticipant",
    # School Zone
    "SharedDiagram",
    "SharedDiagramLike",
    "SharedDiagramComment",
    # Library
    "LibraryDocument",
    "LibraryDanmaku",
    "LibraryDanmakuLike",
    "LibraryDanmakuReply",
    # Pinned Conversations
    "PinnedConversation",
    # Env Settings
    "EnvSetting",
    # Gewe Messages
    "GeweMessage",
    # Gewe Contacts
    "GeweContact",
    # Gewe Group Members
    "GeweGroupMember",
]

from models.domain.device import Device
