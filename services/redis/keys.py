"""Central registry of all Redis key patterns and TTL constants for MindGraph.

Every Redis key pattern and TTL used across the codebase is defined here as a
single source of truth.  All cache modules import their constants from this
file instead of defining them locally.

Key patterns use ``str.format_map`` / ``.format(**kwargs)`` style placeholders
so callers can substitute concrete values:

    key = keys.USER_BY_ID.format(user_id=42)
"""

import os

# ---------------------------------------------------------------------------
# User cache  (redis_user_cache.py)
# ---------------------------------------------------------------------------
USER_BY_ID = "user:{user_id}"
USER_BY_PHONE = "user:phone:{phone}"
USER_BY_EMAIL = "user:email:{email}"
TTL_USER = 86_400  # 24 h

# ---------------------------------------------------------------------------
# Org cache  (redis_org_cache.py)
# ---------------------------------------------------------------------------
ORG_BY_ID = "org:{org_id}"
ORG_BY_CODE = "org:code:{code}"
ORG_BY_INVITE = "org:invite:{invite_code}"
TTL_ORG = 86_400  # 24 h

# ---------------------------------------------------------------------------
# API key cache  (redis_api_key_cache.py)
# ---------------------------------------------------------------------------
API_KEY_BY_HASH = "apikey:hash:{hash}"
API_KEY_USAGE_INCR = "apikey:usage:{key_id}"
TTL_API_KEY = 300  # 5 min

# ---------------------------------------------------------------------------
# User API token cache  (redis_user_token_cache.py) — OpenClaw mgat_ tokens
# ---------------------------------------------------------------------------
USER_TOKEN_BY_HASH = "usertoken:hash:{hash}"
TTL_USER_TOKEN = 604800  # 7 days (matches default token expiry)

# ---------------------------------------------------------------------------
# Diagram cache  (_redis_diagram_cache_helpers.py / redis_diagram_cache.py)
# ---------------------------------------------------------------------------
DIAGRAM = "diagram:{user_id}:{diagram_id}"
DIAGRAMS_USER_META = "diagrams:user:{user_id}:meta"
DIAGRAMS_USER_LIST = "diagrams:user:{user_id}:list"
TTL_DIAGRAM = int(os.getenv("DIAGRAM_CACHE_TTL", "604800"))  # 7 d default

# ---------------------------------------------------------------------------
# Community cache  (redis_community_cache.py)
# ---------------------------------------------------------------------------
COMMUNITY_VERSION = "community:version"
COMMUNITY_LIST = "community:list:{hash16}:v{version}"
COMMUNITY_POST = "community:post:{post_id}"
TTL_COMMUNITY_LIST = 60
TTL_COMMUNITY_POST = 300
TTL_COMMUNITY_VERSION = 86_400

# ---------------------------------------------------------------------------
# Feature org access cache  (redis_feature_org_access_cache.py)
# ---------------------------------------------------------------------------
FEATURE_ORG_ACCESS = "cache:feature_org_access:v1"
TTL_FEATURE_ACCESS = 86_400

# ---------------------------------------------------------------------------
# Cache loader lock  (redis_cache_loader.py)
# ---------------------------------------------------------------------------
CACHE_LOADER_LOCK = "cache:loader:lock"
TTL_CACHE_LOADER_LOCK = 300

# ---------------------------------------------------------------------------
# Session / tokens  (redis_session_manager.py)
# ---------------------------------------------------------------------------
SESSION_USER = "session:user:{user_id}"  # legacy single-session
SESSION_USER_SET = "session:user:set:{user_id}"  # multi-session set
SESSION_INVALIDATED = "session_invalidated:{user_id}:{token_hash}"
REFRESH_TOKEN = "refresh:{user_id}:{token_hash}"
REFRESH_USER_SET = "refresh:user:{user_id}"
REFRESH_LOOKUP = "refresh:lookup:{token_hash}"
TTL_ACCESS_SESSION = (
    int(os.getenv("ACCESS_TOKEN_EXPIRY_MINUTES", "60")) * 60
)  # default 3600 s
TTL_REFRESH_TOKEN = (
    int(os.getenv("REFRESH_TOKEN_EXPIRY_DAYS", "7")) * 86_400
)  # default 604800 s

# ---------------------------------------------------------------------------
# Rate limiting  (redis_rate_limiter.py)
# ---------------------------------------------------------------------------
RATE_KEY = "rate:{category}:{identifier}"
TTL_RATE_DEFAULT = (
    int(os.getenv("RATE_LIMIT_DEFAULT_WINDOW_MINUTES", "15")) * 60
)  # default 900 s

# ---------------------------------------------------------------------------
# Token usage buffer  (redis_token_buffer.py)
# ---------------------------------------------------------------------------
TOKENS_STREAM = "tokens:stream"
TOKENS_STATS = "tokens:stats"
# No TTL — stream is consumed by background worker

# ---------------------------------------------------------------------------
# Distributed locks  (redis_distributed_lock.py)
# ---------------------------------------------------------------------------
LOCK = "lock:{resource}"
LOCK_STARTUP_SMS = "lock:mindgraph:lifespan:startup_sms"
TTL_LOCK_DEFAULT = 10
TTL_LOCK_STARTUP = 120

# ---------------------------------------------------------------------------
# Activity tracker  (redis_activity_tracker.py)
# ---------------------------------------------------------------------------
ACTIVITY_SESSION = "activity:session:{session_id}"
ACTIVITY_USER = "activity:user:{user_id}"
ACTIVITY_HISTORY = "activity:history"
TTL_ACTIVITY_SESSION = 1_800  # 30 min; history has no TTL (LTRIMmed)

# SCAN match patterns — derived from the key templates so they stay in sync.
ACTIVITY_SESSION_PATTERN = "activity:session:*"
ACTIVITY_USER_PATTERN = "activity:user:*"

# ---------------------------------------------------------------------------
# SMS verification  (redis_sms_storage.py)
# ---------------------------------------------------------------------------
SMS_VERIFY = "sms:verify:{purpose}:{phone}"
TTL_SMS = 300

# ---------------------------------------------------------------------------
# Email verification  (redis_email_storage.py)
# ---------------------------------------------------------------------------
EMAIL_VERIFY = "email:verify:{purpose}:{email}"
TTL_EMAIL = 600

# ---------------------------------------------------------------------------
# Bayi tokens / whitelist  (redis_bayi_token.py / redis_bayi_whitelist.py)
# ---------------------------------------------------------------------------
BAYI_TOKEN_USED = "bayi:token:used:{sha256}"
BAYI_TOKEN_VALID = "bayi:token:valid:{sha256}"
BAYI_IP_WHITELIST = "bayi:ip_whitelist"  # no TTL — managed explicitly
BAYI_WHITELIST_LOCK = "bayi:whitelist:load:lock"
TTL_BAYI_TOKEN = 300
TTL_BAYI_WHITELIST_LOCK = 300
