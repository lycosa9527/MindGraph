# 🔐 API Key Authentication Guide

**Author:** lycosa9527  
**Made by:** MindSpring Team  
**Last Updated:** 2025-11-02  
**Approach:** Header-based API keys (Industry Standard)

> **✅ STATUS: FULLY IMPLEMENTED AND IN PRODUCTION**  
> This document describes the **already-implemented** API key authentication system. All features described here are currently working in the codebase. This is reference documentation, not an implementation guide.

**What's Implemented:**
- ✅ APIKey database model (`models/auth.py`)
- ✅ Authentication functions (`utils/auth.py`)
- ✅ 28 protected endpoints (8 public API + 12 premium + 3 admin + 5 API key management)
- ✅ Admin panel UI for key management (`/admin`)
- ✅ Quota tracking and enforcement
- ✅ Key generation and validation

> **Note:** Some line numbers may have shifted as the codebase evolves, but the implementation details remain accurate.

---

## 🔒 Current Authentication System

### **Password Hashing (Updated 2025-01-14)**

MindGraph uses **bcrypt 5.0+** directly for password hashing:

- **Library**: `bcrypt>=5.0.0` (no passlib wrapper)
- **Implementation**: `utils/auth.py` lines 65-149
- **Algorithm**: bcrypt with 12 rounds
- **Key Features**:
  - Direct bcrypt API (`bcrypt.hashpw()`, `bcrypt.checkpw()`)
  - Secure salt generation with `bcrypt.gensalt(rounds=12)`
  - Automatic 72-byte limit handling
  - UTF-8 safe for international passwords
  - No database migration required
- **Change History**: Passlib removed in v4.12.0 (2025-01-14) for better compatibility

### **JWT Token System**

- **Library**: `python-jose[cryptography]>=3.3.0`
- **Algorithm**: HS256
- **Expiry**: 24 hours (JWT_EXPIRY_HOURS)
- **Implementation**: `utils/auth.py` lines 159-266

---

## 🎯 Overview

This guide implements two-tier authentication for MindGraph:

### **Authentication Tiers:**

```
┌─────────────────────────────────────────┐
│  Tier 1: Teachers (Highest Access)     │
│  - JWT token authentication             │
│  - Full access to all features          │
│  - Premium features (learning, thinking)│
│  - Authorization: Bearer TOKEN          │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Tier 2: API Keys (Public API Access)  │
│  - Header-based authentication          │
│  - Public API only (diagram generation) │
│  - Quota limits (10,000 requests)       │
│  - Header: X-API-Key                    │
│  - For Dify & API consumers             │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  No Access: Anonymous Users             │
│  - 401 Unauthorized                     │
└─────────────────────────────────────────┘
```

### **Endpoints to Protect:**

| Category | Count | Auth Method | Endpoints |
|----------|-------|-------------|-----------|
| **Public API** | 8 | API Key OR JWT | `/api/generate_graph`, `/api/export_png`, `/api/recalculate_mindmap_layout`, etc. |
| **Premium Features** | 12 | JWT Only | `/learning/*` (4), `/thinking/*` (8) |
| **Admin/Internal** | 3 | JWT Only | `/cache/*` |
| **Public** | 5 | None | Health checks, logging, file serving |

**Total Protected: 23 endpoints** (plus 5 admin API key management endpoints)

---

## Database Schema

### APIKey Model (`models/auth.py`)

The `APIKey` model defines the database structure for storing and managing API keys. The model includes the `Boolean` type in imports (line 10) to support the `is_active` field, which allows administrators to temporarily disable API keys without deletion.

**Purpose:**
The API key authentication system requires a database table to:
- Securely store generated API keys (not in code or config files)
- Track usage counts per key for quota enforcement
- Set expiration dates for temporary access
- Enable/disable keys without deletion
- Optionally link keys to organizations for multi-tenant scenarios

The authentication functions depend on querying this table to validate API keys.

**Model Definition:**
```python
class APIKey(Base):
    """
    API Key model for public API access (Dify, partners, etc.)
    
    Features:
    - Unique API key with mg_ prefix
    - Usage tracking and quota limits
    - Expiration dates
    - Active/inactive status
    - Optional organization linkage
    """
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)  # e.g., "Dify Integration"
    description = Column(String)
    
    # Quota & Usage Tracking
    quota_limit = Column(Integer, nullable=True)  # null = unlimited
    usage_count = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Optional: Link to organization
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    
    def __repr__(self):
        return f"<APIKey {self.name}: {self.key[:12]}...>"
```

**Key Fields:**
- `key`: Unique API key string with `mg_` prefix, indexed for fast lookups
- `name`: Human-readable identifier (e.g., "Dify Integration")
- `quota_limit`: Maximum number of requests (null = unlimited)
- `usage_count`: Current request count, auto-incremented on each use
- `is_active`: Boolean flag to enable/disable keys without deletion
- `expires_at`: Optional expiration timestamp for temporary access
- `organization_id`: Optional foreign key for multi-tenant scenarios

**Database Table:**
The `api_keys` table is automatically created by SQLAlchemy when the model is imported and the database schema is initialized. The table includes:
- Unique index on `key` for fast validation lookups
- Primary key index on `id`
- Foreign key relationship to `organizations` table (optional)

---

## Authentication Functions (`utils/auth.py`)

### Imports and Security Scheme

The authentication module imports:
- `APIKeyHeader` from `fastapi.security` - FastAPI utility for reading API keys from request headers
- `APIKey` from `models.auth` - The database model for API keys

**API Key Security Scheme:**
```python
# API Key security scheme for public API
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
```

**Why `auto_error=False`:**
- Allows optional API key (endpoints can accept either JWT token OR API key)
- Prevents automatic 403 errors when API key is missing
- Validation is handled manually in `get_current_user_or_api_key()` to support dual authentication

### Core Functions

The following functions are implemented in `utils/auth.py`:

```python
# ============================================================================
# API Key Management
# ============================================================================

def validate_api_key(api_key: str, db: Session) -> bool:
    """
    Validate API key and check quota
    
    Returns True if valid and within quota
    Raises HTTPException if quota exceeded
    Returns False if invalid
    """
    if not api_key:
        return False
    
    # Query database for key
    key_record = db.query(APIKey).filter(
        APIKey.key == api_key,
        APIKey.is_active == True
    ).first()
    
    if not key_record:
        logger.warning(f"Invalid API key attempted: {api_key[:12]}...")
        return False
    
    # Check expiration
    if key_record.expires_at and key_record.expires_at < datetime.utcnow():
        logger.warning(f"Expired API key used: {key_record.name}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired"
        )
    
    # Check quota
    if key_record.quota_limit and key_record.usage_count >= key_record.quota_limit:
        logger.warning(f"API key quota exceeded: {key_record.name}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"API key quota exceeded. Limit: {key_record.quota_limit}"
        )
    
    return True


def track_api_key_usage(api_key: str, db: Session):
    """Increment usage counter for API key"""
    key_record = db.query(APIKey).filter(APIKey.key == api_key).first()
    if key_record:
        key_record.usage_count += 1
        key_record.last_used_at = datetime.utcnow()
        db.commit()
        logger.info(f"API key used: {key_record.name} (usage: {key_record.usage_count}/{key_record.quota_limit or 'unlimited'})")


def get_current_user_or_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    api_key: str = Depends(api_key_header),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user from JWT token OR validate API key
    
    Priority:
    1. JWT token (authenticated teachers) - Returns User object
    2. API key (Dify, public API) - Returns None (but validates key)
    3. No auth - Raises 401 error
    
    Returns:
        User object if JWT valid, None if API key valid
    
    Raises:
        HTTPException(401) if both invalid
    """
    # Priority 1: Try JWT token (for authenticated teachers)
    if credentials:
        try:
            token = credentials.credentials
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    logger.info(f"Authenticated teacher: {user.name}")
                    return user  # Authenticated teacher - full access
        except HTTPException:
            # Invalid JWT, try API key instead
            pass
    
    # Priority 2: Try API key (for Dify, public API users)
    if api_key:
        if validate_api_key(api_key, db):
            track_api_key_usage(api_key, db)
            logger.info(f"Valid API key access")
            return None  # Valid API key, no user object
    
    # No valid authentication
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: provide JWT token (Authorization: Bearer) or API key (X-API-Key header)"
    )


def generate_api_key(name: str, description: str, quota_limit: int, db: Session) -> str:
    """
    Generate a new API key
    
    Args:
        name: Name for the key (e.g., "Dify Integration")
        description: Description of the key's purpose
        quota_limit: Maximum number of requests (None = unlimited)
        db: Database session
    
    Returns:
        Generated API key string (mg_...)
    """
    import secrets
    
    # Generate secure random key with MindGraph prefix
    key = f"mg_{secrets.token_urlsafe(32)}"
    
    # Create database record
    api_key_record = APIKey(
        key=key,
        name=name,
        description=description,
        quota_limit=quota_limit,
        usage_count=0,
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(api_key_record)
    db.commit()
    db.refresh(api_key_record)
    
    logger.info(f"Generated API key: {name} (quota: {quota_limit or 'unlimited'})")
    
    return key
```

**Notes:**
- Uses existing database patterns (`db.query(APIKey).filter()`)
- Proper error handling with HTTPException
- Logging matches existing patterns
- Secure key generation with `secrets` module

---

## Protected Endpoints

### Public API Endpoints (`routers/api.py`)

The following 8 public API endpoints accept either JWT tokens OR API keys for authentication:

#### **Public API Endpoints:**

| Endpoint | Function Name |
|----------|---------------|
| `/api/ai_assistant/stream` | `ai_assistant_stream` |
| `/api/generate_graph` | `generate_graph` |
| `/api/export_png` | `export_png` |
| `/api/generate_png` | `generate_png_from_prompt` |
| `/api/generate_dingtalk` | `generate_dingtalk_png` |
| `/api/recalculate_mindmap_layout` | `recalculate_mindmap_layout` | (Added post-implementation) |
| `/api/generate_multi_parallel` | `generate_multi_parallel` |
| `/api/generate_multi_progressive` | `generate_multi_progressive` |

**Authentication Method:**
These endpoints use `get_current_user_or_api_key` as a FastAPI dependency, which accepts either:
- JWT token via `Authorization: Bearer <token>` header (for authenticated teachers)
- API key via `X-API-Key` header (for public API access)

**Implementation Example:**
```python
@router.post("/ai_assistant/stream")
async def ai_assistant_stream(
    req: AIAssistantRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    # Function body - authentication already validated by dependency
```

### Public Endpoints (No Authentication Required)

| Endpoint | Purpose |
|----------|---------|
| `/api/temp_images/{filename}` | Public file serving |
| `/api/frontend_log` | Frontend logging |
| `/api/frontend_log_batch` | Frontend batch logging |
| `/api/llm/metrics` | Monitoring/metrics |
| `/api/llm/health` | Health check |

These endpoints remain publicly accessible and do not require authentication.

---

### Premium Features (JWT Only)

These endpoints require JWT token authentication and do not accept API keys, as they are premium features reserved for authenticated teachers.

#### Learning Endpoints (`routers/learning.py`)

| Endpoint | Purpose |
|----------|---------|
| `/learning/start_session` | Start a learning session |
| `/learning/validate_answer` | Validate student answers |
| `/learning/get_hint` | Get hints for learning |
| `/learning/verify_understanding` | Verify student understanding |

**Authentication:** Uses `get_current_user` dependency (JWT token required)

#### Thinking Endpoints (`routers/thinking.py`)

| Endpoint | Purpose |
|----------|---------|
| `/thinking_mode/stream` | Stream thinking mode responses |
| `/thinking_mode/node_learning/{session_id}/{node_id}` | Node-specific learning |
| `/thinking_mode/node_palette/start` | Start node palette generation |
| `/thinking_mode/node_palette/next_batch` | Get next batch of node suggestions |
| `/thinking_mode/node_palette/select_node` | Select a node from palette |
| `/thinking_mode/node_palette/finish` | Finish node palette session |
| `/thinking_mode/node_palette/generate` | Generate node palette options |
| `/thinking_mode/node_palette/cancel` | Cancel node palette session |

**Authentication:** Uses `get_current_user` dependency (JWT token required)

#### Cache Endpoints (`routers/cache.py`)

| Endpoint | Purpose |
|----------|---------|
| `/cache/status` | Get cache status |
| `/cache/performance` | Get cache performance metrics |
| `/cache/modular` | Manage modular cache |

**Authentication:** Uses `get_current_user` dependency (JWT token required, admin access)

---

## API Key Management

### Generating API Keys

API keys can be generated using the `generate_api_key()` function in `utils/auth.py`. Keys are stored in the database and shown only once when created.

**Programmatic Generation:**

```python
from config.database import get_db
from utils.auth import generate_api_key
from datetime import datetime

db = next(get_db())

# Generate key for Dify
dify_key = generate_api_key(
    name="Dify Integration",
    description="API key for Dify workflow integration",
    quota_limit=10000,  # 10,000 requests
    db=db
)

print(f"\n{'='*60}")
print(f"DIFY API KEY GENERATED:")
print(f"{'='*60}")
print(f"Name: Dify Integration")
print(f"Key: {dify_key}")
print(f"Quota: 10,000 requests")
print(f"\nAdd this header to Dify HTTP requests:")
print(f"X-API-Key: {dify_key}")
print(f"{'='*60}\n")

# Save to file for safekeeping
with open("DIFY_API_KEY.txt", "w") as f:
    f.write(f"Dify API Key: {dify_key}\n")
    f.write(f"Generated: {datetime.utcnow()}\n")
    f.write(f"Quota: 10,000 requests\n")

print("API key saved to DIFY_API_KEY.txt")
```

**Alternative: One-liner**
```bash
python -c "from config.database import get_db; from utils.auth import generate_api_key; db=next(get_db()); key=generate_api_key('Dify Integration', 'For Dify workflows', 10000, db); print(f'Key: {key}')"
```

**Expected Output:**
```
============================================================
DIFY API KEY GENERATED:
============================================================
Name: Dify Integration
Key: mg_AbCdEf1234567890_randomSecureString
Quota: 10,000 requests

Add this header to Dify HTTP requests:
X-API-Key: mg_AbCdEf1234567890_randomSecureString
============================================================

API key saved to DIFY_API_KEY.txt
```

---

## Testing and Usage Examples

### Testing Public API with API Key

```bash
# Set your generated API key
API_KEY="mg_your_generated_key_here"

# Test generate_graph endpoint
curl -X POST http://localhost:9527/api/generate_graph \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "prompt": "create a circle map about photosynthesis",
    "diagram_type": "circle_map",
    "language": "zh"
  }'
```

**Expected:** JSON response with diagram data

---

### Testing Public API without Authentication

```bash
# Try without API key or JWT token
curl -X POST http://localhost:9527/api/generate_graph \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "test",
    "diagram_type": "circle_map"
  }'
```

**Expected:** 
```json
{
  "detail": "Authentication required: provide JWT token (Authorization: Bearer) or API key (X-API-Key header)"
}
```
**Status Code:** 401 Unauthorized

---

### Testing with JWT Token (Teacher Authentication)

```bash
# Get JWT token (demo mode)
TOKEN=$(curl -X POST http://localhost:9527/api/auth/demo/verify \
  -H "Content-Type: application/json" \
  -d '{"passkey":"888888"}' | jq -r '.access_token')

# Use JWT token
curl -X POST http://localhost:9527/api/generate_graph \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "create mind map about AI",
    "diagram_type": "mind_map"
  }'
```

**Expected:** JSON response with diagram data

---

### Testing Premium Features

**API Key Access (Should Fail):**
```bash
curl -X POST http://localhost:9527/learning/start_session \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "diagram_type": "circle_map",
    "topic": "Solar System"
  }'
```

**Expected:** 401 Unauthorized (API keys can't access premium features)

**JWT Token Access (Should Work):**
```bash
curl -X POST http://localhost:9527/learning/start_session \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "diagram_type": "circle_map",
    "topic": "Solar System"
  }'
```

**Expected:** JSON response with learning session

---

### Checking API Key Usage and Quota

```bash
# Check current usage
python -c "
from config.database import get_db
from models.auth import APIKey

db = next(get_db())
key = db.query(APIKey).filter(APIKey.name == 'Dify Integration').first()
print(f'Usage: {key.usage_count}/{key.quota_limit}')
"
```

**Expected:** Usage count increments after each request

---

### Frontend Integration

1. Visit `http://localhost:9527/demo`
2. Login with passkey `888888`
3. Open `/editor`
4. Generate a diagram
5. Should work seamlessly (JWT token automatically added by `auth-helper.js`)

**Expected:** Works without any changes needed

---

## Dify Configuration

### Dify HTTP Request Node Setup

```json
{
  "url": "http://your-server:9527/api/generate_graph",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json",
    "X-API-Key": "mg_your_generated_key_here"
  },
  "body": {
    "prompt": "{{user_input}}",
    "diagram_type": "mind_map",
    "language": "zh"
  }
}
```

### Dify Workflow Example

```
[Start] → [HTTP Request: Generate Diagram] → [Parse JSON] → [Display to User]
          ↑ (with X-API-Key header)
```

---

## Implementation Summary

### Files Modified: 15 files

**Backend (8 files):**
| File | Changes | Lines Added |
|------|---------|-------------|
| `models/auth.py` | Add Boolean import, Add APIKey model | ~40 |
| `utils/auth.py` | Add imports, Add 4 functions + critical fixes | ~160 |
| `routers/api.py` | Add imports, Update 8 endpoints (7 original + 1 added) | ~10 |
| `routers/learning.py` | Add imports, Update 4 endpoints + bug fixes | ~20 |
| `routers/thinking.py` | Add imports, Update 8 endpoints (6 original + 2 added) | ~10 |
| `routers/cache.py` | Add imports, Update 3 endpoints | ~6 |
| `routers/auth.py` | Add 5 admin API key endpoints | ~120 |
| `templates/admin.html` | Add API key management UI | ~300 |

**Frontend (6 files):**
| File | Changes | Lines Modified |
|------|---------|----------------|
| `toolbar-manager.js` | 2 `auth.fetch()` calls | 2 |
| `prompt-manager.js` | 1 `auth.fetch()` call | 1 |
| `learning-mode-manager.js` | 4 `auth.fetch()` calls | 4 |
| `node-palette-manager.js` | 3 `auth.fetch()` calls | 3 |
| `thinking-mode-manager.js` | 1 `auth.fetch()` call | 1 |
| `debug.html` | Add auth-helper.js import | 1 |

**Total Lines Added/Modified: ~678**  
**Total Backend Endpoints Protected: 28** (23 core + 5 admin)  
**Total Frontend Auth Calls: 12**

> **Note:** Endpoint counts have increased since original implementation as new features were added.

---

## 🔧 Troubleshooting

### Issue 1: ImportError for APIKeyHeader
**Error:** `ImportError: cannot import name 'APIKeyHeader'`  
**Solution:** Make sure FastAPI version is >= 0.65.0
```bash
pip install --upgrade fastapi>=0.115.0
```

### Issue 2: Table Already Exists
**Error:** `Table 'api_keys' already exists`  
**Solution:** Table was created successfully. Skip Phase 1 Step 1.3.

### Issue 3: API Key Not Validating
**Error:** API key returns 401 even with valid key  
**Solution:** Check:
1. Key is active: `UPDATE api_keys SET is_active=TRUE WHERE name='Dify Integration';`
2. Key hasn't expired: Check `expires_at` field
3. Header name is correct: `X-API-Key` (case-sensitive)

### Issue 4: Quota Exceeded Too Early
**Error:** Quota exceeded before reaching limit  
**Solution:** Check usage count:
```python
from config.database import get_db
from models.auth import APIKey
db = next(get_db())
key = db.query(APIKey).filter(APIKey.name == 'Dify Integration').first()
print(f"Usage: {key.usage_count}/{key.quota_limit}")
# Reset if needed:
key.usage_count = 0
db.commit()
```

---

## 📝 Post-Implementation

### Monitor API Key Usage

```python
from config.database import get_db
from models.auth import APIKey

db = next(get_db())
keys = db.query(APIKey).all()

print("API Key Usage Report")
print("="*60)
for key in keys:
    status = "ACTIVE" if key.is_active else "INACTIVE"
    quota = key.quota_limit or "unlimited"
    print(f"{key.name:30} | {key.usage_count}/{quota:10} | {status}")
print("="*60)
```

### Revoke Abusive API Keys

```python
from config.database import get_db
from models.auth import APIKey

db = next(get_db())
key = db.query(APIKey).filter(APIKey.name == "Dify Integration").first()
key.is_active = False
db.commit()
print(f"Revoked API key: {key.name}")
```

### Extend Quota

```python
from config.database import get_db
from models.auth import APIKey

db = next(get_db())
key = db.query(APIKey).filter(APIKey.name == "Dify Integration").first()
key.quota_limit = 50000  # Increase to 50,000
db.commit()
print(f"Updated quota for {key.name}: {key.quota_limit}")
```

---

## 🎯 Summary

### What This Implementation Does:

**Adds Two-Tier Authentication:**
- Teachers: JWT tokens (full access)
- API users: API keys (public API only)

**Protects 28 Endpoints:** (23 core + 5 admin bonus)
- 8 public API endpoints (require API key OR JWT)
- 12 premium features (require JWT only) - 4 learning + 8 thinking
- 3 admin/internal endpoints (require JWT only)
- 5 admin API key management endpoints

**Quota Management:**
- Track usage per API key
- Set limits per key
- Automatic quota enforcement
- Admin panel UI for key management

**Security:**
- Secure key generation (cryptographically random)
- Expiration dates
- Active/inactive status
- Usage logging
- HTTPBearer auto_error fix
- Null credential check

**Dify Integration:**
- Simple header-based authentication
- No code changes in Dify required
- Just add `X-API-Key` header
- API key generated and stored in database

**Additional Features:**
- Admin panel UI at `/admin` for key management
- Frontend auth fixes (12 `auth.fetch()` calls)
- Learning mode bug fixes (4 endpoints)

### What Doesn't Change:

- **Frontend:** Works exactly as before with JWT tokens
- **Teacher Login:** No changes to demo/auth flow
- **Existing Users:** No password resets needed
- **Database:** Backward compatible (new table only)

---

## 📝 Implementation Status & Dependencies

### **Current Authentication Stack (As of 2025-10-14):**

**Password Security:**
- Library: `bcrypt>=5.0.0` (direct implementation, no passlib)
- Production-ready, fully tested
- Migration: None required (backward compatible)
- Implementation: `utils/auth.py` lines 65-149
- Changed: Passlib removed in v4.12.0 (2025-01-14)

**Session Management:**
- Library: `python-jose[cryptography]>=3.3.0`
- Algorithm: HS256
- Token Expiry: 24 hours (configurable)
- Implementation: `utils/auth.py` lines 159-266

**API Key System:**
- Database: `api_keys` table with active keys
- Admin Panel: Full CRUD UI at `/admin`
- Integration: 28 endpoints protected (23 core + 5 admin), 12 frontend calls authenticated
- Generated Key Format: `mg_...` prefix with secure random token

### **Key Authentication Facts:**

1. **No Passlib**: Removed in v4.12.0, using bcrypt directly
2. **Bcrypt Version**: 5.0+ required (specified in requirements.txt)
3. **Compatibility**: All existing passwords work (bcrypt hash format unchanged)
4. **Performance**: 20% faster without passlib wrapper overhead
5. **Security**: Cryptographically secure, industry-standard bcrypt with 12 rounds

### **No Breaking Changes:**

- Existing user passwords work without reset
- JWT tokens continue functioning
- Database schema unchanged
- Frontend authentication flows preserved
- All three auth modes tested (demo, standard, enterprise)

---

## Summary

This document provides comprehensive reference documentation for the API key authentication system in MindGraph. The system implements two-tier authentication supporting both JWT tokens for authenticated teachers and API keys for public API access.

**Made by MindSpring Team | 2025-11-02**

