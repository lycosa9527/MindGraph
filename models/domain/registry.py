"""
Central registry of all SQLAlchemy ORM models.

Importing this module ensures every table is registered on ``Base.metadata``.
Used by Alembic ``env.py`` for autogenerate and by ``config.database.init_db``
to guarantee model visibility before seeding.
"""

from models.domain.auth import (
    Base,
    Organization,
    User,
    APIKey,
    UpdateNotification,
    UpdateNotificationDismissed,
)
from models.domain.user_api_token import UserAPIToken
from models.domain.token_usage import TokenUsage
from models.domain.diagrams import Diagram
from models.domain.diagram_snapshots import DiagramSnapshot
from models.domain.knowledge_space import (
    KnowledgeSpace,
    KnowledgeDocument,
    DocumentChunk,
    Embedding,
    KnowledgeQuery,
    ChunkAttachment,
    ChildChunk,
    DocumentBatch,
    DocumentVersion,
    QueryFeedback,
    QueryTemplate,
    DocumentRelationship,
    EvaluationDataset,
    EvaluationResult,
    ChunkTestResult,
    ChunkTestDocument,
    ChunkTestDocumentChunk,
)
from models.domain.debateverse import (
    DebateSession,
    DebateParticipant,
    DebateMessage,
    DebateJudgment,
)
from models.domain.community import (
    CommunityPost,
    CommunityPostLike,
    CommunityPostComment,
)
from models.domain.school_zone import (
    SharedDiagram,
    SharedDiagramLike,
    SharedDiagramComment,
)
from models.domain.pinned_conversations import PinnedConversation
from models.domain.dashboard_activity import DashboardActivity
from models.domain.user_activity_log import UserActivityLog
from models.domain.user_usage_stats import UserUsageStats
from models.domain.teacher_usage_config import TeacherUsageConfig
from models.domain.library import (
    LibraryDocument,
    LibraryDanmaku,
    LibraryDanmakuLike,
    LibraryDanmakuReply,
    LibraryBookmark,
)
from models.domain.gewe_message import GeweMessage
from models.domain.gewe_contact import GeweContact
from models.domain.gewe_group_member import GeweGroupMember
from models.domain.workshop_chat import (
    ChatChannel,
    ChannelMember,
    ChatTopic,
    ChatMessage,
    DirectMessage,
    MessageReaction,
    StarredMessage,
    FileAttachment,
    UserTopicPreference,
)
from models.domain.feature_access_control import (
    FeatureAccessRule,
    FeatureAccessOrgGrant,
    FeatureAccessUserGrant,
)
from models.domain.device import Device
from models.domain.markets import (
    MarketEntitlement,
    MarketListing,
    MarketOrder,
    MarketPayment,
    MarketSubscription,
)
from models.domain.mindbot_config import OrganizationMindbotConfig
from models.domain.mindbot_usage import MindbotUsageEvent

__all__ = [
    "Base",
    "Organization",
    "User",
    "APIKey",
    "UserAPIToken",
    "UpdateNotification",
    "UpdateNotificationDismissed",
    "TokenUsage",
    "Diagram",
    "DiagramSnapshot",
    "KnowledgeSpace",
    "KnowledgeDocument",
    "DocumentChunk",
    "Embedding",
    "KnowledgeQuery",
    "ChunkAttachment",
    "ChildChunk",
    "DocumentBatch",
    "DocumentVersion",
    "QueryFeedback",
    "QueryTemplate",
    "DocumentRelationship",
    "EvaluationDataset",
    "EvaluationResult",
    "ChunkTestResult",
    "ChunkTestDocument",
    "ChunkTestDocumentChunk",
    "DebateSession",
    "DebateParticipant",
    "DebateMessage",
    "DebateJudgment",
    "CommunityPost",
    "CommunityPostLike",
    "CommunityPostComment",
    "SharedDiagram",
    "SharedDiagramLike",
    "SharedDiagramComment",
    "PinnedConversation",
    "DashboardActivity",
    "UserActivityLog",
    "UserUsageStats",
    "TeacherUsageConfig",
    "LibraryDocument",
    "LibraryDanmaku",
    "LibraryDanmakuLike",
    "LibraryDanmakuReply",
    "LibraryBookmark",
    "GeweMessage",
    "GeweContact",
    "GeweGroupMember",
    "ChatChannel",
    "ChannelMember",
    "ChatTopic",
    "ChatMessage",
    "DirectMessage",
    "MessageReaction",
    "StarredMessage",
    "FileAttachment",
    "UserTopicPreference",
    "FeatureAccessRule",
    "FeatureAccessOrgGrant",
    "FeatureAccessUserGrant",
    "Device",
]
__all__.extend(
    [
        MarketEntitlement.__name__,
        MarketListing.__name__,
        MarketOrder.__name__,
        MarketPayment.__name__,
        MarketSubscription.__name__,
        OrganizationMindbotConfig.__name__,
        MindbotUsageEvent.__name__,
    ]
)
