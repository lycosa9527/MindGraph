# 🔐 Security Implementation Plan - API Key Authentication

**Last Updated:** 2025-01-13  
**Status:** Ready to Implement  
**Estimated Time:** 1.5 - 2 hours  
**Approach:** Header-based API keys (Industry Standard)

---

## 🎯 Architecture Overview

### **Your Application Design:**
```
┌─────────────────────────────────────────┐
│  Public API (Require API Key)           │
│  - /api/generate_graph                  │
│  - /api/export_png                      │
│  - /api/generate_png                    │
│  - For Dify & API consumers             │
│  - Header: X-API-Key required           │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Premium Features (Require JWT Auth)    │
│  - /learning/* (teachers only)          │
│  - /thinking/* (teachers only)          │
│  - /editor page                         │
│  - /admin panel                         │
│  - Authorization: Bearer TOKEN          │
└─────────────────────────────────────────┘
```

### **Authentication Levels:**
1. **Teachers (Highest)** - JWT token, unlimited access, premium features
2. **API Keys (Medium)** - Header-based, quotas, public API only
3. **Anonymous (Blocked)** - No access

---

## 📋 IMPLEMENTATION CHECKLIST

### ☐ **Phase 1: Database Setup** (15 minutes)

#### **Step 1.1: Update Imports**

**File:** `models/auth.py`  
**Line 10 - Add `Boolean` to imports:**

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
```

---

#### **Step 1.2: Create API Key Model**

**File:** `models/auth.py`  
**Add after the `User` model (line 62):**

```python
class APIKey(Base):
    """API Key model for public API access (Dify, partners, etc.)"""
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

---

#### **Step 1.3: Create Database Table**

**Terminal command:**
```bash
python -c "from models.auth import Base; from config.database import engine; Base.metadata.create_all(engine)"
```

**Or manually via SQL:**
```sql
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY,
    key VARCHAR UNIQUE NOT NULL,
    name VARCHAR NOT NULL,
    description VARCHAR,
    quota_limit INTEGER,
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    organization_id INTEGER,
    FOREIGN KEY(organization_id) REFERENCES organizations(id)
);

CREATE UNIQUE INDEX ix_api_keys_key ON api_keys(key);
```

---

### ☐ **Phase 2: Authentication Functions** (20 minutes)

#### **Step 2.1: Add Imports to `utils/auth.py`**

**File:** `utils/auth.py`  
**Line 18 - Add `APIKeyHeader` to imports:**

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
```

**Line 21 - Add `APIKey` to imports:**

```python
from models.auth import User, Organization, APIKey
```

---

#### **Step 2.2: Add API Key Security Scheme**

**File:** `utils/auth.py`  
**After line 78 (after `security = HTTPBearer()`):**

```python
# API Key security scheme for public API
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
```

---

#### **Step 2.3: Add API Key Validation Functions**

**File:** `utils/auth.py`  
**Add at the end of the file (after `is_admin()` function):**

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

---

### ☐ **Phase 3: Update Public API Endpoints** (30 minutes)

#### **Step 3.1: Update `routers/api.py` Imports**

**File:** `routers/api.py`  
**Line 22 - Add `Depends` to imports:**

```python
from fastapi import APIRouter, HTTPException, status, Depends
```

**Add after line 36:**

```python
from typing import Optional
from models.auth import User
from utils.auth import get_current_user_or_api_key
```

---

#### **Step 3.2: Update Public API Endpoints**

**File:** `routers/api.py`  
**Add `current_user: Optional[User] = Depends(get_current_user_or_api_key)` to these endpoints:**

**Add to these 7 functions:**

| Line | Function | Change |
|------|----------|--------|
| 56 | `ai_assistant_stream` | Add `current_user: Optional[User] = Depends(get_current_user_or_api_key)` |
| 139 | `generate_graph` | Add `current_user: Optional[User] = Depends(get_current_user_or_api_key)` |
| 200 | `export_png` | Add `current_user: Optional[User] = Depends(get_current_user_or_api_key)` |
| 606 | `generate_png_from_prompt` | Add `current_user: Optional[User] = Depends(get_current_user_or_api_key)` |
| 666 | `generate_dingtalk_png` | Add `current_user: Optional[User] = Depends(get_current_user_or_api_key)` |
| 879 | `generate_multi_parallel` | Add `current_user: Optional[User] = Depends(get_current_user_or_api_key)` |
| 1067 | `generate_multi_progressive` | Add `current_user: Optional[User] = Depends(get_current_user_or_api_key)` |

**Example (apply to all 7):**
```python
async def ai_assistant_stream(
    req: AIAssistantRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)  # ← ADD THIS
):
```

**Note:** Keep these endpoints **WITHOUT** authentication (public):
- `serve_temp_image` - Public file serving
- `frontend_log` - Frontend logging
- `frontend_log_batch` - Frontend logging
- `get_llm_metrics` - Monitoring
- `llm_health_check` - Health check

---

### ☐ **Phase 4: Protect Premium Features** (20 minutes)

#### **Step 4.1: Update `routers/learning.py`**

**Add imports:**
```python
from models.auth import User
from utils.auth import get_current_user
from fastapi import Depends
```

**Add to ALL 4 endpoints:**
```python
current_user: User = Depends(get_current_user)  # Requires JWT, no API key
```

**Endpoints:**
- Line 91: `start_session`
- Line 159: `validate_answer`
- Line 267: `get_hint`
- Line 331: `verify_understanding`

---

#### **Step 4.2: Update `routers/thinking.py`**

**Add imports:**
```python
from models.auth import User
from utils.auth import get_current_user
from fastapi import Depends
```

**Add to ALL 6 endpoints:**
```python
current_user: User = Depends(get_current_user)  # Requires JWT, no API key
```

**Endpoints:**
- Line 32: `thinking_mode_stream`
- Line 98: `get_node_learning_material`
- Line 139: `start_node_palette`
- Line 212: `get_next_batch`
- Line 267: `log_node_selection`
- Line 287: `log_finish_selection`

---

#### **Step 4.3: Update `routers/cache.py`**

**Add imports:**
```python
from models.auth import User
from utils.auth import get_current_user
from fastapi import Depends
```

**Add to ALL 3 endpoints:**
```python
current_user: User = Depends(get_current_user)  # Admin/internal only
```

**Endpoints:**
- Line 27: `get_cache_status`
- Line 79: `get_cache_performance`
- Line 133: `get_modular_cache_status`

---

### ☐ **Phase 5: Generate API Keys** (5 minutes)

#### **Step 5.1: Create Dify API Key**

**Run in Python shell:**
```python
from config.database import get_db
from utils.auth import generate_api_key

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
```

---

### ☐ **Phase 6: Testing** (20 minutes)

#### **Test 1: Public API with API Key (Should Work)**

```bash
# Get your Dify API key from Phase 5
API_KEY="mg_your_generated_key_here"

# Test generate_graph
curl -X POST http://localhost:9527/api/generate_graph \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "prompt": "create a circle map about plants",
    "diagram_type": "circle_map"
  }'

# Should return diagram JSON ✅
```

---

#### **Test 2: Public API without Auth (Should Fail)**

```bash
# Try without API key or token
curl -X POST http://localhost:9527/api/generate_graph \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "test",
    "diagram_type": "circle_map"
  }'

# Expected: 401 Unauthorized ✅
```

---

#### **Test 3: Teacher with JWT (Should Work)**

```bash
# Get JWT token
TOKEN=$(curl -X POST http://localhost:9527/api/auth/demo/verify \
  -H "Content-Type: application/json" \
  -d '{"passkey":"888888"}' | jq -r '.access_token')

# Use token
curl -X POST http://localhost:9527/api/generate_graph \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "test circle map",
    "diagram_type": "circle_map"
  }'

# Should work ✅
```

---

#### **Test 4: Premium Features (Learning Mode)**

```bash
# Try with API key (should fail - premium feature)
curl -X POST http://localhost:9527/learning/start_session \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{...}'

# Expected: 401 Unauthorized (API keys can't access premium) ✅

# Try with JWT token (should work)
curl -X POST http://localhost:9527/learning/start_session \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...}'

# Should work ✅
```

---

#### **Test 5: Frontend Integration**

1. Visit `http://localhost:9527/demo`
2. Login with passkey `888888`
3. Open `/editor`
4. Generate a diagram
5. Should work seamlessly (JWT token automatically added by `auth-helper.js`)

---

### ☐ **Phase 7: Dify Configuration** (10 minutes)

#### **Dify HTTP Request Node Setup:**

```javascript
{
  "url": "http://your-server:9527/api/generate_graph",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json",
    "X-API-Key": "mg_your_generated_key_here"  // ← Add this header
  },
  "body": {
    "prompt": "{{user_input}}",
    "diagram_type": "mind_map",
    "language": "zh"
  }
}
```

---

## 📊 Progress Tracking

### **Public API Endpoints (Require API Key):**
- [ ] /api/ai_assistant/stream
- [ ] /api/generate_graph
- [ ] /api/export_png
- [ ] /api/generate_png
- [ ] /api/generate_dingtalk
- [ ] /api/generate_multi_parallel
- [ ] /api/generate_multi_progressive

### **Premium Features (Require JWT):**
- [ ] /learning/start_session
- [ ] /learning/validate_answer
- [ ] /learning/get_hint
- [ ] /learning/verify_understanding
- [ ] /thinking/stream
- [ ] /thinking/node_learning
- [ ] /thinking/node_palette/start
- [ ] /thinking/node_palette/next_batch
- [ ] /thinking/node_palette/select_node
- [ ] /thinking/node_palette/finish

### **Internal/Monitoring (Require JWT):**
- [ ] /cache/status
- [ ] /cache/performance
- [ ] /cache/modular

---

## 🎯 Final Checklist

- [ ] API key model added to `models/auth.py`
- [ ] Database table created
- [ ] API key functions added to `utils/auth.py`
- [ ] Public API endpoints updated (7 endpoints)
- [ ] Premium features protected (10 endpoints)
- [ ] Cache endpoints protected (3 endpoints)
- [ ] Dify API key generated
- [ ] All tests passing
- [ ] Dify configured with API key
- [ ] Frontend still works with JWT

---

## 📝 Post-Implementation

### **Monitor API Key Usage:**
```python
# Check usage stats
from config.database import get_db
from models.auth import APIKey

db = next(get_db())
keys = db.query(APIKey).all()

for key in keys:
    print(f"{key.name}: {key.usage_count}/{key.quota_limit or 'unlimited'}")
```

### **Revoke Abusive Keys:**
```python
key = db.query(APIKey).filter(APIKey.name == "Dify Integration").first()
key.is_active = False
db.commit()
```

---

**Status:** READY TO IMPLEMENT  
**Time Estimate:** 1.5 - 2 hours  
**Risk:** LOW - Well-defined changes  

---

## 📖 Quick Reference - Files to Modify

### **Files to Edit: 6 files**

1. **`models/auth.py`**
   - Add `Boolean` import
   - Add `APIKey` model

2. **`utils/auth.py`**
   - Add `APIKeyHeader` import
   - Add `APIKey` import
   - Add `api_key_header` security scheme
   - Add 4 new functions

3. **`routers/api.py`**
   - Add imports (`Depends`, `Optional`, `User`, `get_current_user_or_api_key`)
   - Update 7 endpoints

4. **`routers/learning.py`**
   - Add imports (`Depends`, `User`, `get_current_user`)
   - Update 4 endpoints

5. **`routers/thinking.py`**
   - Add imports (`Depends`, `User`, `get_current_user`)
   - Update 6 endpoints

6. **`routers/cache.py`**
   - Add imports (`Depends`, `User`, `get_current_user`)
   - Update 3 endpoints

**Total Endpoints Protected: 20 endpoints**

---

## 🔍 Verification Checklist

Before implementing, verify:
- [ ] Read complete code review: `docs/CODE_REVIEW_API_KEY_IMPLEMENTATION.md`
- [ ] Understand all 7 critical issues found
- [ ] Backed up database: `cp mindgraph.db mindgraph.db.backup`
- [ ] Environment ready: Python environment activated
- [ ] `.env` file configured with JWT_SECRET_KEY

After implementing:
- [ ] Database table created successfully
- [ ] All imports added without errors
- [ ] All 20 endpoints protected
- [ ] Dify API key generated
- [ ] All 6 test scenarios passing
- [ ] Frontend still works with JWT

---

Made by MindSpring Team
