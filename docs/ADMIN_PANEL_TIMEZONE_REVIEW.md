# Admin Panel Timezone Review

## Overview
This document reviews all timestamp-related code in the admin panel to ensure consistent use of Beijing time (UTC+8) instead of UTC.

## Summary of Issues Found

### ✅ CORRECT Implementations

1. **Token Tracking Tab - "Today" Token Usage** (`routers/auth.py:get_token_stats_admin`)
   - ✅ Uses `get_beijing_today_start_utc()` for "today" calculations
   - ✅ Correctly converts Beijing time to UTC for database queries
   - ✅ Today stats filter: `TokenUsage.created_at >= today_start` (line 2678)
   - ✅ Top users today filter: `TokenUsage.created_at >= today_start` (line 2795)
   - Location: `routers/auth.py:2655-2687, 2779-2805`

2. **Dashboard Tab - Backend** (`routers/auth.py:get_stats_admin`)
   - Uses `get_beijing_now()` and `get_beijing_today_start_utc()` for date calculations
   - Correctly converts Beijing time to UTC for database queries
   - Location: `routers/auth.py:2557-2561`

3. **API Keys Tab - Frontend** (`templates/admin.html:loadAPIKeys`)
   - Uses `toLocaleString` with `timeZone: 'Asia/Shanghai'` for display
   - Location: `templates/admin.html:3341-3342`

### ❌ ISSUES Found

#### 1. Trend Charts Endpoint - Uses UTC Instead of Beijing Time
**Location**: `routers/auth.py:2833-3018` (`get_stats_trends_admin`)

**Issue**:
- Line 2855: Uses `datetime.now(timezone.utc)` instead of Beijing time
- Line 2856-2857: Calculates `start_date` using UTC
- This affects all trend charts (users, organizations, registrations, tokens)

**Impact**: 
- Trend charts show data grouped by UTC days instead of Beijing days
- "Today" in charts may not match Beijing "today"

**Fix Required**:
```python
# Current (WRONG):
now = datetime.now(timezone.utc)
start_date = now - timedelta(days=days)

# Should be:
beijing_now = get_beijing_now()
start_date = (beijing_now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
start_date_utc = start_date.astimezone(timezone.utc).replace(tzinfo=None)
```

**Frontend Issue**: `templates/admin.html:2173`
- Uses `toLocaleDateString` without timezone specification
- Should use Beijing timezone for date labels

---

#### 2. Users Tab - Registration Time Display Uses UTC
**Location**: 
- Backend: `routers/auth.py:2212` (`list_users_admin`)
- Frontend: `templates/admin.html:2861-2867` (`loadUsers`)

**Issue**:
- Backend returns `created_at` as ISO string (UTC)
- Frontend displays date using `new Date(user.created_at)` which interprets as UTC
- Then formats as `YYYY-MM-DD` without timezone conversion
- This means if a user registered at 2025-01-20 01:00 UTC, it shows as 2025-01-20, but in Beijing time it's actually 2025-01-20 09:00, so it should show 2025-01-20

**Impact**: 
- Registration dates may be off by one day for users who registered late at night UTC

**Fix Required**:
```javascript
// Current (WRONG):
const date = new Date(user.created_at);
const year = date.getFullYear();
const month = String(date.getMonth() + 1).padStart(2, '0');
const day = String(date.getDate()).padStart(2, '0');
return `${year}-${month}-${day}`;

// Should be:
const date = new Date(user.created_at);
// Convert to Beijing time
const beijingDate = new Date(date.toLocaleString('en-US', {timeZone: 'Asia/Shanghai'}));
const year = beijingDate.getFullYear();
const month = String(beijingDate.getMonth() + 1).padStart(2, '0');
const day = String(beijingDate.getDate()).padStart(2, '0');
return `${year}-${month}-${day}`;
```

---

#### 3. Schools Tab - Expiration Date Comparison Uses Local Time
**Location**: `templates/admin.html:2599-2601` (`loadSchools`)

**Issue**:
- Uses `new Date()` (local browser time) to compare with `expires_at` (UTC)
- Should use Beijing time for comparison

**Impact**: 
- Expiration status may be incorrect depending on browser timezone

**Fix Required**:
```javascript
// Current (WRONG):
const now = new Date();
const expiresAt = school.expires_at ? new Date(school.expires_at) : null;
const isExpired = expiresAt && expiresAt < now;

// Should be:
const now = new Date();
// Convert to Beijing time for comparison
const beijingNow = new Date(now.toLocaleString('en-US', {timeZone: 'Asia/Shanghai'}));
const expiresAt = school.expires_at ? new Date(school.expires_at) : null;
const isExpired = expiresAt && expiresAt < beijingNow;
```

**Backend Issue**: `routers/auth.py:1854-1855`
- Uses `datetime.now(timezone.utc)` for week_ago calculation
- Should use Beijing time for consistency

---

#### 4. Realtime Monitoring - Timestamps Use System Time (No Timezone)
**Location**: 
- Backend: `services/user_activity_tracker.py:111, 119, 207, 261, 350`
- Frontend: `templates/admin.html:4046-4047, 4098` (`formatTimeAgo`)

**Issue**:
- Backend uses `datetime.now()` without timezone (uses system timezone)
- Frontend `formatTimeAgo` uses `new Date()` and `toLocaleString()` without timezone specification
- Should use Beijing timezone consistently

**Impact**: 
- Realtime monitoring timestamps may be incorrect if server timezone is not Beijing

**Fix Required**:
- Backend: Import Beijing timezone functions and use `get_beijing_now()` instead of `datetime.now()`
- Frontend: Use `timeZone: 'Asia/Shanghai'` in `toLocaleString()` calls

---

#### 5. Users Tab - Token Stats Week Calculation Uses UTC
**Location**: `routers/auth.py:2158-2159` (`list_users_admin`)

**Issue**:
- Uses `datetime.now(timezone.utc)` and `week_ago = now - timedelta(days=7)`
- Should use Beijing time for consistency with other endpoints

**Impact**: 
- Token stats for "this week" may not align with Beijing week boundaries

**Fix Required**:
```python
# Current (WRONG):
now = datetime.now(timezone.utc)
week_ago = now - timedelta(days=7)

# Should be:
beijing_now = get_beijing_now()
week_ago = (beijing_now - timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
```

---

#### 6. Schools Tab - Token Stats Week Calculation Uses UTC
**Location**: `routers/auth.py:1854-1855` (`list_organizations_admin`)

**Issue**:
- Uses `datetime.now(timezone.utc)` and `week_ago = now - timedelta(days=7)`
- Should use Beijing time for consistency

**Fix Required**:
```python
# Current (WRONG):
now = datetime.now(timezone.utc)
week_ago = now - timedelta(days=7)

# Should be:
beijing_now = get_beijing_now()
week_ago = (beijing_now - timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
```

---

## Complete List of Files to Fix

### Backend Files:
1. `routers/auth.py`
   - Line 1854-1855: Schools tab week calculation
   - Line 2158-2159: Users tab week calculation  
   - Line 2855-2857: Trend charts endpoint

2. `services/user_activity_tracker.py`
   - Line 111: `datetime.now()` in start_session
   - Line 119: `datetime.now()` in start_session
   - Line 207: `datetime.now()` in record_activity
   - Line 261: `datetime.now()` in _log_activity
   - Line 350: `datetime.now()` in get_stats
   - Line 355: `datetime.now()` in _cleanup_stale_sessions

### Frontend Files:
1. `templates/admin.html`
   - Line 2173: Trend chart date labels
   - Line 2599-2601: Schools expiration comparison
   - Line 2861-2867: Users registration date display
   - Line 4046-4047: Realtime monitoring timestamp
   - Line 4098: formatTimeAgo function

---

## Testing Checklist

After fixes, verify:
- [ ] Token tracking "today" shows Beijing today's data
- [ ] Token tracking "past week" shows Beijing week's data
- [ ] Token tracking "past month" shows Beijing month's data
- [ ] Dashboard "today registrations" shows Beijing today's registrations
- [ ] Trend charts group data by Beijing days
- [ ] Users tab registration dates show Beijing dates
- [ ] Schools tab expiration status uses Beijing time
- [ ] API keys timestamps display in Beijing time (already correct)
- [ ] Realtime monitoring timestamps use Beijing time
- [ ] All rankings and leaderboards use Beijing time boundaries

---

## Notes

- Database timestamps are stored in UTC (correct)
- All date calculations should convert Beijing time to UTC for database queries
- All date displays should convert UTC to Beijing time for user display
- The `get_beijing_now()` and `get_beijing_today_start_utc()` functions are already available in `routers/auth.py`

