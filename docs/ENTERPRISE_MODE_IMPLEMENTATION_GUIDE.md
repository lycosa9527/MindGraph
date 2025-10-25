# Enterprise Mode Implementation Guide
**Feature:** IP-Based Auto-Login for School Networks  
**Version:** 1.0  
**Date:** January 2025  
**Complexity:** Medium  
**Estimated Time:** 2-3 days

---

## Overview

### Feature Description

Implement enterprise mode for schools where:
- **Inside School Network:** Teachers auto-login based on fixed public IP (no login required)
- **From Home:** Teachers use standard username/password login
- **User Management:** Teachers register accounts tied to their organization
- **Security:** IP whitelist per organization, rate limiting, audit logging

### Use Cases

**Scenario 1: Teacher at School**
```
Teacher opens MindGraph → System detects school IP → Auto-login → Full access
```

**Scenario 2: Teacher at Home**
```
Teacher opens MindGraph → Login page → Enter credentials → Full access
```

**Scenario 3: Guest/Student at School**
```
Guest opens MindGraph → Login page (IP not registered) → Register or login
```

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                    Client Request                        │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              IP Detection Middleware                     │
│  - Extract client IP (X-Forwarded-For / X-Real-IP)     │
│  - Check IP whitelist for organization                  │
└───────────────────────┬─────────────────────────────────┘
                        │
           ┌────────────┴────────────┐
           │                         │
           ▼                         ▼
    IP Whitelisted?           Not Whitelisted
           │                         │
           ▼                         ▼
  ┌──────────────────┐      ┌──────────────────┐
  │  Auto-Login      │      │  Standard Login  │
  │  - Get org user  │      │  - Show form     │
  │  - Create session│      │  - Validate pwd  │
  │  - Set cookie    │      │  - Set cookie    │
  └──────────────────┘      └──────────────────┘
```

---

## Step-by-Step Implementation

## Phase 1: Database Schema (Day 1, Morning)

### Step 1.1: Add Organization IP Whitelist Table

**File:** `models/auth.py`

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime

# Add new table for IP whitelist
class OrganizationIPWhitelist(Base):
    """
    IP whitelist for organization-based auto-login.
    Allows teachers to auto-login when accessing from school network.
    """
    __tablename__ = 'organization_ip_whitelist'
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False, index=True)
    
    # IP address or CIDR range (e.g., "202.120.1.5" or "202.120.1.0/24")
    ip_address = Column(String(50), nullable=False, index=True)
    ip_type = Column(String(20), default='single')  # 'single', 'range', 'cidr'
    
    # Description for admin reference
    description = Column(String(200))  # e.g., "Main Campus Network", "Library Building"
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'))  # Admin who added this IP
    last_used_at = Column(DateTime)  # Track when this IP was last used for auto-login
    usage_count = Column(Integer, default=0)  # How many times this IP triggered auto-login
    
    # Relationships
    organization = relationship("Organization", back_populates="ip_whitelist")
    creator = relationship("User", foreign_keys=[created_by])
    
    # Composite index for fast lookup
    __table_args__ = (
        Index('idx_org_ip_active', 'organization_id', 'ip_address', 'is_active'),
    )
```

### Step 1.2: Update Organization Model

**File:** `models/auth.py`

```python
class Organization(Base):
    __tablename__ = 'organizations'
    
    # ... existing columns ...
    
    # NEW: Enterprise mode settings
    enterprise_mode_enabled = Column(Boolean, default=False)
    auto_login_enabled = Column(Boolean, default=False)  # Enable IP-based auto-login
    
    # NEW: Default role for auto-login users
    default_role = Column(String(20), default='teacher')  # 'teacher', 'student', 'viewer'
    
    # NEW: Relationships
    ip_whitelist = relationship("OrganizationIPWhitelist", back_populates="organization")
```

### Step 1.3: Add Auto-Login Audit Log

**File:** `models/auth.py`

```python
class AutoLoginLog(Base):
    """
    Audit log for IP-based auto-login events.
    Track who accessed from which IP and when.
    """
    __tablename__ = 'auto_login_logs'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False, index=True)
    
    # IP and network info
    ip_address = Column(String(50), nullable=False, index=True)
    user_agent = Column(Text)
    
    # Auto-login details
    matched_whitelist_id = Column(Integer, ForeignKey('organization_ip_whitelist.id'))
    login_time = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Session info
    session_id = Column(String(100))
    
    # Relationships
    user = relationship("User")
    organization = relationship("Organization")
    whitelist_entry = relationship("OrganizationIPWhitelist")
    
    __table_args__ = (
        Index('idx_autolog_date', 'login_time'),
        Index('idx_autolog_user_date', 'user_id', 'login_time'),
    )
```

### Step 1.4: Create Migration Script

**File:** `scripts/migrate_enterprise_mode.py`

```python
"""
Migration script for Enterprise Mode feature.
Adds IP whitelist and auto-login tables.
"""

from config.database import engine
from models.auth import Base
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

def migrate():
    """Run migration"""
    try:
        # Create new tables
        Base.metadata.create_all(bind=engine)
        logger.info("Created new tables: organization_ip_whitelist, auto_login_logs")
        
        # Add new columns to organizations table (if using SQLite)
        with engine.connect() as conn:
            # Check if columns exist first
            result = conn.execute(text("PRAGMA table_info(organizations)"))
            columns = [row[1] for row in result]
            
            if 'enterprise_mode_enabled' not in columns:
                # SQLite doesn't support ALTER TABLE ADD COLUMN with constraints
                # For production with PostgreSQL, use:
                # ALTER TABLE organizations ADD COLUMN enterprise_mode_enabled BOOLEAN DEFAULT FALSE;
                
                logger.info("Please run manual migration for organizations table:")
                logger.info("  ALTER TABLE organizations ADD COLUMN enterprise_mode_enabled BOOLEAN DEFAULT FALSE;")
                logger.info("  ALTER TABLE organizations ADD COLUMN auto_login_enabled BOOLEAN DEFAULT FALSE;")
                logger.info("  ALTER TABLE organizations ADD COLUMN default_role VARCHAR(20) DEFAULT 'teacher';")
        
        logger.info("Migration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    migrate()
```

**Run migration:**
```bash
python scripts/migrate_enterprise_mode.py
```

---

## Phase 2: IP Detection Service (Day 1, Afternoon)

### Step 2.1: Create IP Whitelist Service

**File:** `services/ip_whitelist_service.py`

```python
"""
IP Whitelist Service for Enterprise Mode
Handles IP detection and organization matching.
"""

import ipaddress
import logging
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from datetime import datetime

from models.auth import OrganizationIPWhitelist, Organization, User

logger = logging.getLogger(__name__)

class IPWhitelistService:
    """Service for IP whitelist management and matching"""
    
    @staticmethod
    def get_client_ip(request) -> str:
        """
        Extract client IP from request, handling proxy headers.
        
        Priority:
        1. X-Real-IP (Nginx)
        2. X-Forwarded-For (first IP in chain)
        3. request.client.host (direct connection)
        """
        # Check X-Real-IP header (most reliable with Nginx)
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            logger.debug(f"Client IP from X-Real-IP: {real_ip}")
            return real_ip
        
        # Check X-Forwarded-For (comma-separated list)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Get first IP in chain (original client)
            client_ip = forwarded_for.split(',')[0].strip()
            logger.debug(f"Client IP from X-Forwarded-For: {client_ip}")
            return client_ip
        
        # Fallback to direct connection
        client_ip = request.client.host
        logger.debug(f"Client IP from request.client: {client_ip}")
        return client_ip
    
    @staticmethod
    def check_ip_in_whitelist(
        ip_address: str,
        db: Session
    ) -> Optional[Tuple[OrganizationIPWhitelist, Organization]]:
        """
        Check if IP is in any organization's whitelist.
        
        Returns:
            Tuple of (whitelist_entry, organization) if found, None otherwise
        """
        try:
            # Query active whitelist entries
            entries = db.query(OrganizationIPWhitelist).filter(
                OrganizationIPWhitelist.is_active == True
            ).all()
            
            logger.debug(f"Checking IP {ip_address} against {len(entries)} whitelist entries")
            
            for entry in entries:
                if IPWhitelistService._ip_matches(ip_address, entry):
                    # Get organization
                    org = db.query(Organization).filter(
                        Organization.id == entry.organization_id,
                        Organization.enterprise_mode_enabled == True,
                        Organization.auto_login_enabled == True
                    ).first()
                    
                    if org:
                        logger.info(
                            f"IP {ip_address} matched whitelist entry {entry.id} "
                            f"for organization {org.name}"
                        )
                        return (entry, org)
            
            logger.debug(f"IP {ip_address} not found in any whitelist")
            return None
            
        except Exception as e:
            logger.error(f"Error checking IP whitelist: {e}")
            return None
    
    @staticmethod
    def _ip_matches(ip_address: str, entry: OrganizationIPWhitelist) -> bool:
        """
        Check if IP matches whitelist entry.
        Supports single IP, IP range, and CIDR notation.
        """
        try:
            client_ip = ipaddress.ip_address(ip_address)
            
            if entry.ip_type == 'single':
                # Exact match
                return ip_address == entry.ip_address
            
            elif entry.ip_type == 'cidr':
                # CIDR range (e.g., "202.120.1.0/24")
                network = ipaddress.ip_network(entry.ip_address, strict=False)
                return client_ip in network
            
            elif entry.ip_type == 'range':
                # IP range (stored as "202.120.1.1-202.120.1.50")
                start_ip, end_ip = entry.ip_address.split('-')
                start = ipaddress.ip_address(start_ip.strip())
                end = ipaddress.ip_address(end_ip.strip())
                return start <= client_ip <= end
            
            else:
                logger.warning(f"Unknown ip_type: {entry.ip_type}")
                return False
                
        except ValueError as e:
            logger.error(f"Invalid IP format: {e}")
            return False
    
    @staticmethod
    def get_or_create_org_user(
        organization: Organization,
        ip_address: str,
        db: Session
    ) -> Optional[User]:
        """
        Get or create a default user for auto-login.
        
        Strategy:
        1. Look for existing active user in organization with matching IP history
        2. If not found, create a generic "auto-login" user for this IP
        3. Return the user for session creation
        """
        # Try to find existing user from this IP
        from models.auth import AutoLoginLog
        
        recent_log = db.query(AutoLoginLog).filter(
            AutoLoginLog.organization_id == organization.id,
            AutoLoginLog.ip_address == ip_address
        ).order_by(AutoLoginLog.login_time.desc()).first()
        
        if recent_log and recent_log.user:
            user = db.query(User).filter(
                User.id == recent_log.user_id,
                User.is_active == True
            ).first()
            
            if user:
                logger.info(f"Found existing user {user.username} for IP {ip_address}")
                return user
        
        # No existing user, create generic auto-login user
        # Format: autologin_<org_code>_<ip_suffix>
        ip_suffix = ip_address.replace('.', '_')[-12:]  # Last 12 chars
        username = f"autologin_{organization.code}_{ip_suffix}"
        
        # Check if this username already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            logger.info(f"Found existing auto-login user: {username}")
            return existing_user
        
        # Create new auto-login user
        from utils.auth import get_password_hash
        
        new_user = User(
            username=username,
            phone=f"auto_{ip_suffix}",  # Dummy phone
            password_hash=get_password_hash("auto_login_no_password"),  # Placeholder
            organization_id=organization.id,
            role=organization.default_role,
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        try:
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            logger.info(f"Created new auto-login user: {username}")
            return new_user
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create auto-login user: {e}")
            return None
    
    @staticmethod
    def log_auto_login(
        user: User,
        organization: Organization,
        whitelist_entry: OrganizationIPWhitelist,
        ip_address: str,
        user_agent: str,
        session_id: str,
        db: Session
    ):
        """Log auto-login event for audit"""
        from models.auth import AutoLoginLog
        
        log_entry = AutoLoginLog(
            user_id=user.id,
            organization_id=organization.id,
            ip_address=ip_address,
            user_agent=user_agent,
            matched_whitelist_id=whitelist_entry.id,
            login_time=datetime.utcnow(),
            session_id=session_id
        )
        
        try:
            db.add(log_entry)
            
            # Update whitelist entry usage stats
            whitelist_entry.last_used_at = datetime.utcnow()
            whitelist_entry.usage_count = (whitelist_entry.usage_count or 0) + 1
            
            db.commit()
            logger.info(f"Logged auto-login for user {user.username} from IP {ip_address}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to log auto-login: {e}")

# Singleton instance
ip_whitelist_service = IPWhitelistService()
```

---

## Phase 3: Auto-Login Middleware (Day 2, Morning)

### Step 3.1: Create Auto-Login Middleware

**File:** `middleware/auto_login_middleware.py`

```python
"""
Auto-Login Middleware for Enterprise Mode
Handles IP-based authentication for whitelisted IPs.
"""

import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

from services.ip_whitelist_service import ip_whitelist_service
from config.database import SessionLocal
from utils.auth import create_access_token

logger = logging.getLogger(__name__)

class AutoLoginMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle IP-based auto-login.
    
    Flow:
    1. Extract client IP from request
    2. Check if IP is in organization whitelist
    3. If whitelisted and no existing auth:
       - Create/get user for this IP
       - Generate JWT token
       - Set authentication cookie
    4. Continue with request
    """
    
    # Paths that should skip auto-login check
    SKIP_PATHS = [
        '/static/',
        '/docs',
        '/redoc',
        '/openapi.json',
        '/health',
        '/api/auth/logout',  # Don't auto-login during logout
    ]
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request with auto-login logic"""
        
        # Skip auto-login for certain paths
        if any(request.url.path.startswith(path) for path in self.SKIP_PATHS):
            return await call_next(request)
        
        # Skip if user is already authenticated
        if request.cookies.get('access_token'):
            return await call_next(request)
        
        # Get client IP
        client_ip = ip_whitelist_service.get_client_ip(request)
        
        # Check if IP is whitelisted
        db = SessionLocal()
        try:
            result = ip_whitelist_service.check_ip_in_whitelist(client_ip, db)
            
            if result:
                whitelist_entry, organization = result
                logger.info(
                    f"Auto-login triggered for IP {client_ip} "
                    f"(org: {organization.name})"
                )
                
                # Get or create user for this IP
                user = ip_whitelist_service.get_or_create_org_user(
                    organization, client_ip, db
                )
                
                if user:
                    # Create JWT token
                    token = create_access_token(data={"sub": user.username})
                    
                    # Log auto-login event
                    user_agent = request.headers.get('User-Agent', '')
                    ip_whitelist_service.log_auto_login(
                        user=user,
                        organization=organization,
                        whitelist_entry=whitelist_entry,
                        ip_address=client_ip,
                        user_agent=user_agent,
                        session_id=token[:16],  # Use token prefix as session ID
                        db=db
                    )
                    
                    # Process request
                    response = await call_next(request)
                    
                    # Set authentication cookie
                    response.set_cookie(
                        key="access_token",
                        value=token,
                        httponly=True,
                        secure=True,  # HTTPS only
                        samesite="lax",
                        max_age=86400 * 7  # 7 days
                    )
                    
                    logger.info(f"Auto-login successful for user {user.username}")
                    return response
        
        except Exception as e:
            logger.error(f"Auto-login error: {e}")
        
        finally:
            db.close()
        
        # No auto-login, continue normally
        return await call_next(request)
```

### Step 3.2: Register Middleware in Main App

**File:** `main.py`

```python
# Add after existing middleware
from middleware.auto_login_middleware import AutoLoginMiddleware

# Register auto-login middleware (must be before auth middleware)
app.add_middleware(AutoLoginMiddleware)

logger.info("Auto-login middleware registered for enterprise mode")
```

---

## Phase 4: Admin Management API (Day 2, Afternoon)

### Step 4.1: Create IP Whitelist Admin Router

**File:** `routers/admin_ip_whitelist.py`

```python
"""
Admin API for IP Whitelist Management
Allows admins to manage organization IP whitelists.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime

from config.database import get_db
from models.auth import User, OrganizationIPWhitelist, Organization
from utils.auth import get_current_user, is_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/ip-whitelist", tags=["admin-ip-whitelist"])

# ============================================================================
# Request/Response Models
# ============================================================================

class IPWhitelistCreate(BaseModel):
    organization_id: int
    ip_address: str
    ip_type: str = 'single'  # 'single', 'range', 'cidr'
    description: str = None

class IPWhitelistUpdate(BaseModel):
    ip_address: str = None
    ip_type: str = None
    description: str = None
    is_active: bool = None

class IPWhitelistResponse(BaseModel):
    id: int
    organization_id: int
    organization_name: str
    ip_address: str
    ip_type: str
    description: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime = None
    usage_count: int
    
    class Config:
        from_attributes = True

# ============================================================================
# Admin Endpoints
# ============================================================================

@router.get("/list", response_model=List[IPWhitelistResponse])
async def list_ip_whitelist(
    organization_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all IP whitelist entries.
    Admin can see all, org admin can see their org only.
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    query = db.query(OrganizationIPWhitelist)
    
    # Filter by organization if specified
    if organization_id:
        query = query.filter(OrganizationIPWhitelist.organization_id == organization_id)
    
    entries = query.all()
    
    # Enrich with organization name
    result = []
    for entry in entries:
        org = db.query(Organization).filter(Organization.id == entry.organization_id).first()
        result.append({
            **entry.__dict__,
            'organization_name': org.name if org else 'Unknown'
        })
    
    return result

@router.post("/create", response_model=IPWhitelistResponse)
async def create_ip_whitelist(
    data: IPWhitelistCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new IP whitelist entry"""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Validate organization exists
    org = db.query(Organization).filter(Organization.id == data.organization_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Validate IP format based on type
    try:
        if data.ip_type == 'single':
            import ipaddress
            ipaddress.ip_address(data.ip_address)
        elif data.ip_type == 'cidr':
            import ipaddress
            ipaddress.ip_network(data.ip_address, strict=False)
        elif data.ip_type == 'range':
            # Validate range format: "IP1-IP2"
            if '-' not in data.ip_address:
                raise ValueError("Range must be in format: IP1-IP2")
            start, end = data.ip_address.split('-')
            import ipaddress
            ipaddress.ip_address(start.strip())
            ipaddress.ip_address(end.strip())
        else:
            raise ValueError("Invalid ip_type")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid IP format: {str(e)}"
        )
    
    # Create entry
    entry = OrganizationIPWhitelist(
        organization_id=data.organization_id,
        ip_address=data.ip_address,
        ip_type=data.ip_type,
        description=data.description,
        is_active=True,
        created_at=datetime.utcnow(),
        created_by=current_user.id,
        usage_count=0
    )
    
    try:
        db.add(entry)
        db.commit()
        db.refresh(entry)
        
        logger.info(
            f"Admin {current_user.username} added IP whitelist: "
            f"{data.ip_address} for org {org.name}"
        )
        
        return {
            **entry.__dict__,
            'organization_name': org.name
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create IP whitelist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create IP whitelist entry"
        )

@router.put("/{entry_id}", response_model=IPWhitelistResponse)
async def update_ip_whitelist(
    entry_id: int,
    data: IPWhitelistUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update IP whitelist entry"""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    entry = db.query(OrganizationIPWhitelist).filter(
        OrganizationIPWhitelist.id == entry_id
    ).first()
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP whitelist entry not found"
        )
    
    # Update fields
    if data.ip_address:
        entry.ip_address = data.ip_address
    if data.ip_type:
        entry.ip_type = data.ip_type
    if data.description is not None:
        entry.description = data.description
    if data.is_active is not None:
        entry.is_active = data.is_active
    
    try:
        db.commit()
        db.refresh(entry)
        
        org = db.query(Organization).filter(Organization.id == entry.organization_id).first()
        
        return {
            **entry.__dict__,
            'organization_name': org.name if org else 'Unknown'
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update IP whitelist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update IP whitelist entry"
        )

@router.delete("/{entry_id}")
async def delete_ip_whitelist(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete IP whitelist entry"""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    entry = db.query(OrganizationIPWhitelist).filter(
        OrganizationIPWhitelist.id == entry_id
    ).first()
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP whitelist entry not found"
        )
    
    try:
        db.delete(entry)
        db.commit()
        
        logger.info(f"Admin {current_user.username} deleted IP whitelist entry {entry_id}")
        
        return {"success": True, "message": "IP whitelist entry deleted"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete IP whitelist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete IP whitelist entry"
        )

@router.get("/stats/{organization_id}")
async def get_whitelist_stats(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get auto-login statistics for organization"""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    from models.auth import AutoLoginLog
    from sqlalchemy import func
    
    # Get total auto-logins
    total_logins = db.query(func.count(AutoLoginLog.id)).filter(
        AutoLoginLog.organization_id == organization_id
    ).scalar()
    
    # Get unique users
    unique_users = db.query(func.count(func.distinct(AutoLoginLog.user_id))).filter(
        AutoLoginLog.organization_id == organization_id
    ).scalar()
    
    # Get unique IPs
    unique_ips = db.query(func.count(func.distinct(AutoLoginLog.ip_address))).filter(
        AutoLoginLog.organization_id == organization_id
    ).scalar()
    
    # Get recent logins (last 24 hours)
    from datetime import timedelta
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_logins = db.query(func.count(AutoLoginLog.id)).filter(
        AutoLoginLog.organization_id == organization_id,
        AutoLoginLog.login_time >= yesterday
    ).scalar()
    
    return {
        "organization_id": organization_id,
        "total_auto_logins": total_logins,
        "unique_users": unique_users,
        "unique_ips": unique_ips,
        "recent_logins_24h": recent_logins
    }
```

### Step 4.2: Register Router

**File:** `main.py`

```python
from routers import admin_ip_whitelist

app.include_router(admin_ip_whitelist.router)
```

---

## Phase 5: Frontend UI (Day 3)

### Step 5.1: Add Admin UI for IP Whitelist Management

**File:** `templates/admin.html` (add new section)

```html
<!-- IP Whitelist Management Section -->
<div class="admin-section" id="ip-whitelist-section">
    <h2>IP Whitelist Management (Enterprise Mode)</h2>
    
    <!-- Organization Selector -->
    <div class="form-group">
        <label>Organization:</label>
        <select id="org-selector" onchange="loadIPWhitelist()">
            <option value="">All Organizations</option>
            <!-- Populated dynamically -->
        </select>
    </div>
    
    <!-- Add IP Button -->
    <button onclick="showAddIPModal()" class="btn-primary">Add IP Address</button>
    
    <!-- IP Whitelist Table -->
    <table id="ip-whitelist-table">
        <thead>
            <tr>
                <th>Organization</th>
                <th>IP Address</th>
                <th>Type</th>
                <th>Description</th>
                <th>Status</th>
                <th>Usage Count</th>
                <th>Last Used</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody id="ip-whitelist-tbody">
            <!-- Populated dynamically -->
        </tbody>
    </table>
</div>

<!-- Add/Edit IP Modal -->
<div id="ip-modal" class="modal" style="display:none;">
    <div class="modal-content">
        <span class="close" onclick="closeIPModal()">&times;</span>
        <h3 id="ip-modal-title">Add IP Address</h3>
        
        <form id="ip-form">
            <div class="form-group">
                <label>Organization:</label>
                <select id="ip-org-id" required>
                    <!-- Populated dynamically -->
                </select>
            </div>
            
            <div class="form-group">
                <label>IP Type:</label>
                <select id="ip-type" onchange="updateIPPlaceholder()">
                    <option value="single">Single IP</option>
                    <option value="cidr">CIDR Range</option>
                    <option value="range">IP Range</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>IP Address:</label>
                <input type="text" id="ip-address" placeholder="202.120.1.5" required>
                <small class="help-text">
                    Single: 202.120.1.5<br>
                    CIDR: 202.120.1.0/24<br>
                    Range: 202.120.1.1-202.120.1.50
                </small>
            </div>
            
            <div class="form-group">
                <label>Description:</label>
                <input type="text" id="ip-description" placeholder="Main Campus Network">
            </div>
            
            <div class="form-group">
                <label>
                    <input type="checkbox" id="ip-active" checked>
                    Active
                </label>
            </div>
            
            <div class="modal-actions">
                <button type="submit" class="btn-primary">Save</button>
                <button type="button" onclick="closeIPModal()" class="btn-secondary">Cancel</button>
            </div>
        </form>
    </div>
</div>

<script>
// IP Whitelist Management Functions
async function loadIPWhitelist() {
    const orgId = document.getElementById('org-selector').value;
    const url = orgId ? `/api/admin/ip-whitelist/list?organization_id=${orgId}` : '/api/admin/ip-whitelist/list';
    
    try {
        const response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${getAuthToken()}` }
        });
        
        if (response.ok) {
            const entries = await response.json();
            displayIPWhitelist(entries);
        }
    } catch (error) {
        console.error('Failed to load IP whitelist:', error);
    }
}

function displayIPWhitelist(entries) {
    const tbody = document.getElementById('ip-whitelist-tbody');
    tbody.innerHTML = '';
    
    entries.forEach(entry => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td>${entry.organization_name}</td>
            <td><code>${entry.ip_address}</code></td>
            <td><span class="badge">${entry.ip_type}</span></td>
            <td>${entry.description || '-'}</td>
            <td>${entry.is_active ? '✅ Active' : '⚠️ Inactive'}</td>
            <td>${entry.usage_count || 0}</td>
            <td>${entry.last_used_at ? new Date(entry.last_used_at).toLocaleString() : 'Never'}</td>
            <td>
                <button onclick="editIP(${entry.id})" class="btn-small">Edit</button>
                <button onclick="deleteIP(${entry.id})" class="btn-small btn-danger">Delete</button>
            </td>
        `;
    });
}

async function showAddIPModal() {
    document.getElementById('ip-modal-title').textContent = 'Add IP Address';
    document.getElementById('ip-form').reset();
    document.getElementById('ip-modal').style.display = 'block';
    
    // Load organizations
    await loadOrganizationsForIP();
}

async function loadOrganizationsForIP() {
    // Fetch organizations list
    const response = await fetch('/api/admin/organizations', {
        headers: { 'Authorization': `Bearer ${getAuthToken()}` }
    });
    
    if (response.ok) {
        const orgs = await response.json();
        const select = document.getElementById('ip-org-id');
        select.innerHTML = orgs.map(org => 
            `<option value="${org.id}">${org.name}</option>`
        ).join('');
    }
}

function updateIPPlaceholder() {
    const type = document.getElementById('ip-type').value;
    const input = document.getElementById('ip-address');
    
    const placeholders = {
        'single': '202.120.1.5',
        'cidr': '202.120.1.0/24',
        'range': '202.120.1.1-202.120.1.50'
    };
    
    input.placeholder = placeholders[type];
}

document.getElementById('ip-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const data = {
        organization_id: parseInt(document.getElementById('ip-org-id').value),
        ip_address: document.getElementById('ip-address').value,
        ip_type: document.getElementById('ip-type').value,
        description: document.getElementById('ip-description').value,
        is_active: document.getElementById('ip-active').checked
    };
    
    try {
        const response = await fetch('/api/admin/ip-whitelist/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getAuthToken()}`
            },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            alert('IP whitelist entry created successfully');
            closeIPModal();
            loadIPWhitelist();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
        }
    } catch (error) {
        alert('Failed to create IP whitelist entry');
    }
});

async function deleteIP(entryId) {
    if (!confirm('Are you sure you want to delete this IP whitelist entry?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/ip-whitelist/${entryId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${getAuthToken()}` }
        });
        
        if (response.ok) {
            alert('IP whitelist entry deleted');
            loadIPWhitelist();
        }
    } catch (error) {
        alert('Failed to delete IP whitelist entry');
    }
}

function closeIPModal() {
    document.getElementById('ip-modal').style.display = 'none';
}

// Load on page load
if (document.getElementById('ip-whitelist-section')) {
    loadIPWhitelist();
}
</script>
```

---

## Phase 6: Configuration & Testing (Day 3)

### Step 6.1: Environment Configuration

**File:** `.env`

```bash
# Enterprise Mode Configuration
ENTERPRISE_MODE_ENABLED=true

# IP Detection
# Set to true if behind reverse proxy (Nginx, Apache)
BEHIND_REVERSE_PROXY=true

# Trusted proxy IPs (comma-separated)
TRUSTED_PROXIES=127.0.0.1,::1

# Auto-login session duration (days)
AUTO_LOGIN_SESSION_DAYS=7
```

### Step 6.2: Test Scenarios

**File:** `tests/test_enterprise_mode.py`

```python
"""
Test cases for Enterprise Mode auto-login feature.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from config.database import SessionLocal
from models.auth import Organization, OrganizationIPWhitelist, User

client = TestClient(app)

@pytest.fixture
def setup_test_org(db_session):
    """Create test organization with IP whitelist"""
    org = Organization(
        code="TEST-001",
        name="Test School",
        invitation_code="TEST123",
        enterprise_mode_enabled=True,
        auto_login_enabled=True,
        default_role='teacher'
    )
    db_session.add(org)
    db_session.commit()
    
    # Add IP whitelist
    whitelist = OrganizationIPWhitelist(
        organization_id=org.id,
        ip_address="192.168.1.100",
        ip_type='single',
        description="Test IP",
        is_active=True
    )
    db_session.add(whitelist)
    db_session.commit()
    
    return org

def test_auto_login_from_whitelisted_ip(setup_test_org):
    """Test auto-login works from whitelisted IP"""
    response = client.get(
        "/",
        headers={"X-Real-IP": "192.168.1.100"}
    )
    
    assert response.status_code == 200
    assert 'access_token' in response.cookies

def test_no_auto_login_from_non_whitelisted_ip():
    """Test normal login flow from non-whitelisted IP"""
    response = client.get(
        "/",
        headers={"X-Real-IP": "1.2.3.4"}
    )
    
    assert response.status_code == 200
    assert 'access_token' not in response.cookies

def test_cidr_range_matching(setup_test_org):
    """Test CIDR range matching"""
    db = SessionLocal()
    
    # Add CIDR whitelist
    whitelist = OrganizationIPWhitelist(
        organization_id=setup_test_org.id,
        ip_address="10.0.0.0/24",
        ip_type='cidr',
        description="Test CIDR",
        is_active=True
    )
    db.add(whitelist)
    db.commit()
    
    # Test IPs in range
    for ip in ["10.0.0.1", "10.0.0.50", "10.0.0.254"]:
        response = client.get("/", headers={"X-Real-IP": ip})
        assert response.status_code == 200
        assert 'access_token' in response.cookies
    
    # Test IP out of range
    response = client.get("/", headers={"X-Real-IP": "10.0.1.1"})
    assert 'access_token' not in response.cookies
    
    db.close()
```

---

## Phase 7: Deployment Checklist

### Pre-Deployment

- [ ] Run database migration: `python scripts/migrate_enterprise_mode.py`
- [ ] Add test IP whitelist entries for pilot schools
- [ ] Test with school's actual public IP
- [ ] Configure Nginx to forward X-Real-IP header
- [ ] Set `BEHIND_REVERSE_PROXY=true` in production
- [ ] Test from both inside and outside school network
- [ ] Verify auto-login audit logs are working
- [ ] Load test with expected concurrent users

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:9527;
        
        # CRITICAL: Forward real client IP
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
    }
}
```

### Post-Deployment

- [ ] Monitor auto-login logs for first week
- [ ] Check false positive/negative rates
- [ ] Verify session persistence works
- [ ] Test teacher login from home
- [ ] Collect feedback from pilot schools
- [ ] Document any IP-specific issues
- [ ] Create admin training materials

---

## Usage Instructions

### For System Administrators

**1. Enable Enterprise Mode for Organization:**
```sql
UPDATE organizations 
SET enterprise_mode_enabled = TRUE, 
    auto_login_enabled = TRUE,
    default_role = 'teacher'
WHERE code = 'SCHOOL-001';
```

**2. Add School's Public IP:**
- Go to Admin Panel → IP Whitelist Management
- Click "Add IP Address"
- Select organization
- Enter school's public IP (get from: https://whatismyipaddress.com)
- Example: `202.120.1.5` or `202.120.1.0/24` for entire subnet
- Add description: "Main Campus Network"
- Save

**3. Test Auto-Login:**
- From school network: Open MindGraph → Should auto-login
- From home: Open MindGraph → Should show login page

### For Teachers

**First Time Setup (From School):**
1. Connect to school WiFi
2. Open MindGraph URL
3. Automatically logged in
4. Create diagrams as usual

**From Home:**
1. Open MindGraph URL
2. Click "Login"
3. Enter school-provided username/password
4. Login and use normally

### For School IT Staff

**Get School's Public IP:**
```bash
# From school network, visit:
curl https://api.ipify.org
# Or visit: https://whatismyipaddress.com
```

**Whitelist Entire School Network:**
- Use CIDR notation for IP range
- Example: `202.120.1.0/24` covers 202.120.1.1 to 202.120.1.254
- Consult your network admin for correct range

---

## Security Considerations

### 1. IP Spoofing Prevention
- Always use Nginx/reverse proxy
- Trust only proxy headers from trusted IPs
- Log all auto-login attempts with full headers

### 2. Rate Limiting
- Implement per-IP rate limits
- Prevent brute force through IP rotation
- Monitor unusual access patterns

### 3. Audit Logging
- Log every auto-login event
- Track IP changes for users
- Alert on suspicious activity (e.g., same IP from different orgs)

### 4. Session Security
- Use HTTPS only
- HttpOnly cookies
- Short session duration (7 days max)
- Implement session invalidation

### 5. Fallback Mechanisms
- Always allow manual login
- Don't block non-whitelisted IPs
- Provide clear error messages

---

## Troubleshooting

### Issue: Auto-login not working from school

**Check:**
1. Is organization's `enterprise_mode_enabled` = TRUE?
2. Is organization's `auto_login_enabled` = TRUE?
3. Is IP in whitelist and active?
4. Is Nginx forwarding X-Real-IP header?
5. Check logs: `grep "Auto-login" logs/app.log`

**Fix:**
```bash
# Check what IP server sees
curl -H "X-Real-IP: YOUR_SCHOOL_IP" http://localhost:9527/health

# Test IP matching
python -c "from services.ip_whitelist_service import ip_whitelist_service; \
           print(ip_whitelist_service.check_ip_in_whitelist('YOUR_SCHOOL_IP', db))"
```

### Issue: Teachers can't login from home

**Check:**
1. Do they have registered accounts?
2. Is standard login page accessible?
3. Are credentials correct?

**Fix:**
- Ensure `/api/auth/login` endpoint works
- Check if cookies are being set
- Verify password hash matches

### Issue: Wrong organization auto-login

**Check:**
1. Is IP whitelisted for multiple organizations?
2. Check `auto_login_logs` table for history

**Fix:**
- Remove duplicate IP entries
- Use more specific CIDR ranges
- Assign IP to correct organization only

---

## Monitoring & Analytics

### Key Metrics to Track

1. **Auto-Login Success Rate**
   ```sql
   SELECT 
       organization_id,
       COUNT(*) as total_logins,
       COUNT(DISTINCT user_id) as unique_users,
       COUNT(DISTINCT ip_address) as unique_ips
   FROM auto_login_logs
   WHERE login_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
   GROUP BY organization_id;
   ```

2. **Peak Usage Times**
   ```sql
   SELECT 
       HOUR(login_time) as hour,
       COUNT(*) as login_count
   FROM auto_login_logs
   WHERE login_time >= DATE_SUB(NOW(), INTERVAL 1 DAY)
   GROUP BY HOUR(login_time)
   ORDER BY hour;
   ```

3. **Most Active IPs**
   ```sql
   SELECT 
       ip_address,
       COUNT(*) as usage_count,
       MAX(login_time) as last_used
   FROM auto_login_logs
   GROUP BY ip_address
   ORDER BY usage_count DESC
   LIMIT 10;
   ```

### Dashboard Recommendations

Create admin dashboard showing:
- Total auto-logins today
- Active organizations using enterprise mode
- New IPs detected (potential additions to whitelist)
- Failed auto-login attempts
- Usage by time of day

---

## Future Enhancements

### Phase 2 Features (Future)

1. **MAC Address Binding**
   - Bind specific devices to auto-login
   - More secure than IP alone
   - Requires client-side component

2. **Geo-Location Verification**
   - Verify IP matches school's physical location
   - Alert on geographic anomalies
   - Use GeoIP database

3. **Time-Based Access**
   - Auto-login only during school hours
   - Configurable per organization
   - Weekend/holiday schedules

4. **Multi-Factor for Home Access**
   - Require 2FA when accessing from home
   - SMS or authenticator app
   - Optional per organization

5. **Self-Service IP Management**
   - Allow school IT staff to manage their own IPs
   - Approval workflow for new IPs
   - Automatic IP detection and suggestion

---

## Appendix A: Complete File Checklist

### New Files Created
- [ ] `models/auth.py` - Add 3 new tables
- [ ] `services/ip_whitelist_service.py` - IP matching service
- [ ] `middleware/auto_login_middleware.py` - Auto-login logic
- [ ] `routers/admin_ip_whitelist.py` - Admin API
- [ ] `scripts/migrate_enterprise_mode.py` - Database migration
- [ ] `tests/test_enterprise_mode.py` - Test suite

### Modified Files
- [ ] `main.py` - Register middleware and router
- [ ] `templates/admin.html` - Add IP management UI
- [ ] `.env` - Add enterprise mode config

### Configuration Files
- [ ] Nginx config - Forward X-Real-IP header
- [ ] `.env` - Enable enterprise mode

---

## Appendix B: SQL Schema Reference

```sql
-- organization_ip_whitelist table
CREATE TABLE organization_ip_whitelist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    ip_address VARCHAR(50) NOT NULL,
    ip_type VARCHAR(20) DEFAULT 'single',
    description VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    last_used_at DATETIME,
    usage_count INTEGER DEFAULT 0,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE INDEX idx_org_ip_active ON organization_ip_whitelist(organization_id, ip_address, is_active);

-- auto_login_logs table
CREATE TABLE auto_login_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    organization_id INTEGER NOT NULL,
    ip_address VARCHAR(50) NOT NULL,
    user_agent TEXT,
    matched_whitelist_id INTEGER,
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR(100),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (matched_whitelist_id) REFERENCES organization_ip_whitelist(id)
);

CREATE INDEX idx_autolog_date ON auto_login_logs(login_time);
CREATE INDEX idx_autolog_user_date ON auto_login_logs(user_id, login_time);
CREATE INDEX idx_autolog_ip ON auto_login_logs(ip_address);
```

---

**END OF GUIDE**

*This guide provides complete step-by-step instructions for implementing enterprise mode with IP-based auto-login. Follow each phase sequentially for successful deployment.*

*Estimated total implementation time: 2-3 days*  
*Testing time: 1 day*  
*Total: 3-4 days to production*


