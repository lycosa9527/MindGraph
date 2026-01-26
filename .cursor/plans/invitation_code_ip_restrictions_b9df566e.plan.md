---
name: Invitation Code IP Restrictions and Email Registration
overview: Add IP whitelist/blacklist functionality to invitation codes and support email-based registration for foreign countries. Invitation codes determine account type (phone for China, email for foreign), with IP restrictions blocking mainland China IPs when configured.
todos:
  - id: add_model_fields
    content: Add ip_restriction_enabled, block_mainland_china, and account_type fields to Organization model
    status: pending
  - id: add_user_email_field
    content: Add email field to User model and make phone nullable (mutually exclusive)
    status: pending
  - id: create_ip_check_helper
    content: Create utils/auth/ip_geolocation.py with is_ip_from_mainland_china() helper function
    status: pending
  - id: update_registration_models
    content: Update RegisterRequest and RegisterWithSMSRequest to support email field (optional, mutually exclusive with phone)
    status: pending
  - id: update_registration_logic
    content: Update registration endpoints to handle both phone and email based on invitation code account_type
    status: pending
  - id: update_validation
    content: Update validation logic - phone validation for phone accounts, email validation for email accounts
    status: pending
  - id: update_login
    content: Update login endpoints to support both phone and email login based on account type
    status: pending
  - id: add_error_messages
    content: Add ip_blocked_mainland_china and email-related error messages to models/messages.py
    status: pending
  - id: update_admin_endpoints
    content: Update organization admin endpoints to accept and save IP restriction and account_type settings
    status: pending
  - id: create_migration_script
    content: Create database migration script to add new columns to organizations and users tables
    status: pending
  - id: add_invitation_info_endpoint
    content: Create API endpoint to get invitation code info including account_type
    status: pending
  - id: update_frontend_registration
    content: Update frontend registration form to show phone or email based on account_type
    status: pending
  - id: update_frontend_login
    content: Update frontend login form to accept both phone and email
    status: pending
  - id: update_user_cache
    content: Update Redis user cache to support email lookups
    status: pending
  - id: optimize_org_cache_ip_restrictions
    content: Update redis_org_cache.py to cache IP restriction fields (ip_restriction_enabled, block_mainland_china, account_type)
    status: pending
  - id: add_postgresql_indexes
    content: Add PostgreSQL indexes for IP restriction queries (if using PostgreSQL)
    status: pending
  - id: performance_testing
    content: Test registration performance with PostgreSQL+Redis vs SQLite+Redis under concurrent load
    status: pending
isProject: false
---

# Invitation Code IP Restrictions and Email Registration Implementation

## Overview

Add IP restriction functionality to invitation codes and support email-based registration for foreign countries. Each invitation code determines the account type (phone-based for China, email-based for foreign countries). IP restrictions can block mainland China IPs when configured. Account type is determined by invitation code settings, and login method matches the account type.

## Architecture

### PostgreSQL+Redis Optimization for IP Separation

**Current State (SQLite + Redis):**

- Organization lookup: SQLite query (can be slow under concurrent load)
- IP geolocation: Redis cached (30-day TTL) ✅ Already efficient
- Registration flow: Sequential checks

**With PostgreSQL + Redis:**

1. **Faster Organization Lookups:**

   - PostgreSQL indexes on `invitation_code`, `ip_restriction_enabled`, `block_mainland_china`
   - Redis cache for organization data (already exists: `redis_org_cache.py`)
   - Query optimization: Filter organizations with IP restrictions enabled early

2. **Better Concurrent Registration Handling:**

   - PostgreSQL handles concurrent writes better than SQLite
   - No database-level locks blocking other registrations
   - Better connection pooling for high-traffic scenarios

3. **Enhanced Redis Caching Strategy:**

   - Cache organization IP restriction settings: `org:ip_restrictions:{org_id}`
   - Cache IP geolocation results (already implemented: 30-day TTL)
   - Two-level cache: Organization settings + IP location = fast decision

4. **Optimized Registration Flow:**
   ```
   Registration Request
   ↓
   Redis: Check org cache (invitation_code → org data)
   ↓ (cache miss)
   PostgreSQL: Query org with indexed invitation_code lookup
   ↓
   Redis: Cache org data (including ip_restriction_enabled, block_mainland_china)
   ↓
   If ip_restriction_enabled:
     Redis: Check IP geolocation cache (ip:location:{ip})
     ↓ (cache miss)
     Local DB: Lookup IP in ip2region database
     ↓
     Redis: Cache IP location (30-day TTL)
     ↓
     Check: country == "中国" && block_mainland_china == True
     ↓
     Block or Allow
   ```

5. **Database Indexes (PostgreSQL):**
   ```sql
   CREATE INDEX idx_org_invitation_code ON organizations(invitation_code);
   CREATE INDEX idx_org_ip_restrictions ON organizations(ip_restriction_enabled, block_mainland_china) 
     WHERE ip_restriction_enabled = true;
   CREATE INDEX idx_users_email ON users(email) WHERE email IS NOT NULL;
   CREATE INDEX idx_users_phone ON users(phone) WHERE phone IS NOT NULL;
   ```

6. **Performance Benefits:**

   - **Organization lookup**: ~1ms (Redis cache) vs ~10-50ms (SQLite query)
   - **IP geolocation**: ~0.5ms (Redis cache) vs ~5-10ms (local DB lookup)
   - **Concurrent registrations**: No blocking, better throughput
   - **Scalability**: PostgreSQL can handle 1000+ concurrent registrations

7. **Redis Key Schema Enhancement:**
   ```
   # Existing
   org:invitation:{invitation_code} → {org_id, name, code, ...}
   ip:location:{ip} → {province, city, country, ...}
   
   # New (for IP restrictions)
   org:ip_restrictions:{org_id} → {ip_restriction_enabled, block_mainland_china, account_type}
   org:by_invitation:{invitation_code} → {org_id, ip_restriction_enabled, block_mainland_china, account_type}
   ```

8. **Implementation Strategy:**

   - Update `services/redis/redis_org_cache.py` to cache IP restriction fields
   - Add Redis cache invalidation when org settings change
   - Use PostgreSQL partial indexes for organizations with IP restrictions enabled
   - Leverage PostgreSQL's better query planner for complex filters

### Data Model Changes

- **Organization Model** (`models/auth.py`): Add three new fields:
  - `ip_restriction_enabled` (Boolean, default=False): Whether IP restriction is enabled for this invitation code
  - `block_mainland_china` (Boolean, default=False): Whether to block mainland China IPs
  - `account_type` (String, default="phone"): Account type for this invitation code - "phone" or "email"
    - "phone": Requires phone number registration (for China users)
    - "email": Requires email registration (for foreign users)

- **User Model** (`models/auth.py`): Modify to support email:
  - `email` (String, nullable=True, unique=True, indexed): Email address for foreign users
  - `phone` (String, nullable=True): Make nullable (currently required) - mutually exclusive with email
  - Add constraint: user must have either phone OR email, not both

### IP Geolocation Check

- Use existing `IPGeolocationService` (`services/auth/ip_geolocation.py`) to detect if IP is from mainland China
- Check `country == "中国"` in the location result
- Create helper function `is_ip_from_mainland_china()` in `utils/auth/ip_geolocation.py` (new file)

### Registration Flow Updates

- **Registration Endpoints** (`routers/auth/registration.py`):
  - After invitation code validation and organization lookup
  - Before user creation
  - Check if organization has IP restrictions enabled
  - If enabled and `block_mainland_china=True`, check user's IP
  - Block registration with appropriate error message if IP is from mainland China

### Error Messages

- Add new error message: `ip_blocked_mainland_china` in `models/messages.py`
- Provide clear message explaining the restriction

### Login Flow Updates

- **Login Endpoints** (`routers/auth/login.py`):
  - Support both phone and email login
  - Detect account type by checking if identifier is phone format or email format
  - Query user by phone OR email based on identifier format
  - Login method matches account type (phone account = phone login, email account = email login)

### Admin Interface

- **Organization Admin** (`routers/auth/admin/organizations.py`):
  - Allow setting `ip_restriction_enabled`, `block_mainland_china`, and `account_type` when creating/updating organizations
  - Update request models to include these fields
  - Validate account_type is either "phone" or "email"

### Database Migration

- Create migration script to:
  - Add new columns to `organizations` table: `ip_restriction_enabled`, `block_mainland_china`, `account_type`
  - Set default values: `ip_restriction_enabled=False`, `block_mainland_china=False`, `account_type="phone"`
  - Add `email` column to `users` table (nullable, unique, indexed)
  - Make `phone` column nullable in `users` table
  - Add constraint: ensure each user has either phone OR email (not both, not neither)

## Implementation Details

### Files to Modify

1. **models/auth.py**

   - Add `ip_restriction_enabled`, `block_mainland_china`, and `account_type` columns to `Organization` model
   - Add `email` column to `User` model (nullable, unique, indexed)
   - Make `phone` nullable in `User` model
   - Add database constraint: user must have either phone OR email

2. **utils/auth/ip_geolocation.py** (new file)

   - Create `is_ip_from_mainland_china(ip: str) -> bool` helper function
   - Uses `IPGeolocationService` singleton to check IP location
   - Returns `True` if IP is from mainland China ("中国")

3. **models/requests_auth.py**

   - Update `RegisterRequest`:
     - Make `phone` optional
     - Add `email` field (optional)
     - Add validation: exactly one of phone or email required
   - Update `RegisterWithSMSRequest`:
     - Make `phone` optional
     - Add `email` field (optional)
     - Note: SMS registration may only work with phone (consider email verification alternative)
   - Add email validation helper function

4. **routers/auth/registration.py**

   - After organization lookup, check `org.account_type`:
     - If "phone": Validate phone is provided and matches format
     - If "email": Validate email is provided and matches format
   - Add IP check after organization lookup (around line 174)
   - Check `org.ip_restriction_enabled` and `org.block_mainland_china`
   - If restrictions enabled, call `is_ip_from_mainland_china(client_ip)`
   - Raise HTTPException with 403 status if blocked
   - Create user with phone OR email based on account_type

5. **routers/auth/login.py**

   - Update login logic to detect identifier type (phone vs email)
   - Query user by phone OR email based on identifier format
   - Support both login methods

6. **models/messages.py**

   - Add `ip_blocked_mainland_china` error message in both English and Chinese
   - Add `email_required` error message
   - Add `phone_or_email_required` error message
   - Add `invalid_email_format` error message

7. **routers/auth/admin/organizations.py**

   - Accept `ip_restriction_enabled`, `block_mainland_china`, and `account_type` in create/update endpoints
   - Validate `account_type` is "phone" or "email"
   - Save these fields

8. **Database Migration Script**

   - Create `scripts/add_ip_restriction_and_email_support.py`
   - Add columns to organizations table with default values
   - Add email column to users table
   - Make phone nullable in users table
   - Add constraint for phone/email mutual exclusivity

9. **Frontend Updates** (`frontend/src/components/auth/LoginModal.vue`)

   - Add API endpoint to check invitation code and get account_type
   - Update registration form to conditionally show phone OR email field based on account_type
   - Add email validation in frontend
   - Update registration form validation logic
   - Update login form to accept both phone and email (auto-detect type)

10. **Services Updates**

    - **services/redis/redis_user_cache.py**: Update to support email lookups
    - **services/redis/redis_org_cache.py**: 
      - Cache `account_type`, `ip_restriction_enabled`, `block_mainland_china` fields
      - Add cache key: `org:ip_restrictions:{org_id}` for fast IP restriction checks
      - Invalidate cache when org settings are updated
    - Consider email verification service (if not using SMS for email accounts)

11. **PostgreSQL Optimization** (if using PostgreSQL)

    - Add indexes on `organizations` table:
      - `invitation_code` (unique index, already exists)
      - Composite index: `(ip_restriction_enabled, block_mainland_china)` for filtering
      - Partial index: `WHERE ip_restriction_enabled = true` for faster queries
    - Add indexes on `users` table:
      - `email` (unique, where email IS NOT NULL)
      - `phone` (unique, where phone IS NOT NULL)
    - Use PostgreSQL's `EXPLAIN ANALYZE` to verify query performance

### Key Functions

```python
# utils/auth/ip_geolocation.py
async def is_ip_from_mainland_china(ip: str) -> bool:
    """Check if IP address is from mainland China."""
    # Use IPGeolocationService.get_location()
    # Return True if country == "中国"

# routers/auth/registration.py (or new endpoint)
async def get_invitation_code_info(invitation_code: str) -> Dict:
    """Get invitation code information including account_type."""
    # Lookup organization by invitation code
    # Return {account_type: "phone"|"email", ...}
```

### Frontend API Endpoint

- **New Endpoint**: `GET /api/auth/invitation-code/{code}/info`
  - Returns organization info including `account_type`
  - Frontend uses this to determine which form fields to show
  - Called when user enters invitation code

### Registration Flow (Optimized with PostgreSQL+Redis)

1. Validate captcha/SMS
2. Validate invitation code format
3. **Lookup organization by invitation code** (optimized):

   - Check Redis cache first: `org:by_invitation:{code}`
   - If cache miss: Query PostgreSQL with indexed `invitation_code` lookup
   - Cache result in Redis (including IP restriction fields)

4. **NEW**: Check organization's `account_type`:

   - If "phone": Require phone field, validate 11-digit Chinese mobile format
   - If "email": Require email field, validate email format (RFC 5322)

5. **NEW**: Check IP restrictions if enabled (optimized):

   - If `ip_restriction_enabled=True` and `block_mainland_china=True`:
     - Check Redis cache: `ip:location:{client_ip}` (30-day TTL)
     - If cache miss: Lookup in local ip2region database
     - Cache IP location result in Redis
     - Check: `country == "中国"` in cached/looked-up location
     - Block registration if IP is from mainland China

6. Create user account with phone OR email based on account_type

   - PostgreSQL handles concurrent writes efficiently
   - No database-level locks blocking other registrations

### Error Handling

- If IP is blocked: Return 403 with clear error message
- If geolocation service unavailable: Allow registration (fail open for availability)
- Log blocked attempts for monitoring

## Testing Considerations

### IP Restrictions

- Test with mainland China IP (localhost in DEBUG mode returns China location)
- Test with non-China IP
- Test with IP restriction disabled (should allow all)
- Test with geolocation service unavailable (should allow registration)

### Email Registration

- Test phone-based invitation code (requires phone, rejects email)
- Test email-based invitation code (requires email, rejects phone)
- Test registration with valid email format
- Test registration with invalid email format
- Test login with email account (email login)
- Test login with phone account (phone login)
- Test user uniqueness: email must be unique, phone must be unique
- Test mutual exclusivity: user cannot have both phone and email

### Frontend

- Test registration form shows phone field for phone-based invitation codes
- Test registration form shows email field for email-based invitation codes
- Test form validation updates based on account type
- Test login form accepts both phone and email
- Test invitation code lookup API returns account_type

## PostgreSQL+Redis Efficiency Summary

### Performance Improvements

**Organization Lookup:**

- **SQLite**: 10-50ms per query, blocks on concurrent writes
- **PostgreSQL + Redis**: ~1ms (cache hit), ~5-10ms (cache miss with indexed query)
- **Improvement**: 5-50x faster, no blocking

**IP Geolocation Check:**

- **Current**: Already optimized with Redis caching (30-day TTL)
- **PostgreSQL benefit**: Better concurrent handling when cache misses occur
- **Improvement**: Maintains ~0.5ms cache hit, better handling of cache misses

**Concurrent Registration Handling:**

- **SQLite**: Database-level locks, sequential writes under high load
- **PostgreSQL**: Row-level locking, concurrent writes, better connection pooling
- **Improvement**: Can handle 10-100x more concurrent registrations

**Overall Registration Flow:**

- **SQLite + Redis**: ~15-60ms per registration (under load)
- **PostgreSQL + Redis**: ~2-15ms per registration (under load)
- **Improvement**: 3-4x faster, scales better with concurrent users

### Key Optimizations

1. **Two-Level Caching**: Organization settings + IP location = fast decision
2. **Indexed Queries**: PostgreSQL indexes on invitation_code and IP restriction fields
3. **No Database Locks**: PostgreSQL handles concurrent writes without blocking
4. **Redis Cache Invalidation**: Smart cache updates when org settings change
5. **Early Filtering**: Query only organizations with IP restrictions enabled

### Migration Path

If migrating from SQLite to PostgreSQL:

1. Existing Redis caching continues to work (no changes needed)
2. Add PostgreSQL indexes during migration
3. Update `redis_org_cache.py` to cache IP restriction fields
4. Test performance improvements
5. Monitor cache hit rates and query performance