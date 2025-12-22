# Admin Panel Queries Timezone Audit

## Overview
Complete audit of all admin panel queries, rankings, and top 10s to ensure Beijing time (UTC+8) is used consistently.

## Dashboard Tab Queries

### ✅ Stat Cards (4 cards)
1. **Total Users** (`/api/auth/admin/stats`)
   - Query: `db.query(User).count()`
   - Date filter: None (all time)
   - Status: ✅ No timezone needed

2. **Total Organizations** (`/api/auth/admin/stats`)
   - Query: `db.query(Organization).count()`
   - Date filter: None (all time)
   - Status: ✅ No timezone needed

3. **Today Registrations** (`/api/auth/admin/stats`)
   - Query: `db.query(User).filter(User.created_at >= today_start).count()`
   - Date filter: `today_start = get_beijing_today_start_utc()`
   - Status: ✅ Uses Beijing time

4. **Total Tokens** (`/api/auth/admin/stats`)
   - Query: Token stats from `token_stats_by_org` (all time)
   - Date filter: None (all time)
   - Status: ✅ No timezone needed

### ✅ Top 10 Schools Ranking
- **Endpoint**: `/api/auth/admin/stats`
- **Query**: `org_token_stats` - Per-organization TOTAL token usage (all time)
- **Location**: `routers/auth.py:2594-2624`
- **Date filter**: None (all time)
- **Status**: ✅ No timezone needed (all-time ranking)

## Token Tracking Tab Queries

### ✅ Stat Cards (4 cards)
1. **Today Token** (`/api/auth/admin/token-stats`)
   - Query: `TokenUsage.created_at >= today_start`
   - Date filter: `today_start = get_beijing_today_start_utc()`
   - Location: `routers/auth.py:2672-2687`
   - Status: ✅ Uses Beijing time

2. **Past Week Token** (`/api/auth/admin/token-stats`)
   - Query: `TokenUsage.created_at >= week_ago`
   - Date filter: `week_ago = (beijing_now - timedelta(days=7)).astimezone(timezone.utc)`
   - Location: `routers/auth.py:2701-2714`
   - Status: ✅ Uses Beijing time

3. **Past Month Token** (`/api/auth/admin/token-stats`)
   - Query: `TokenUsage.created_at >= month_ago`
   - Date filter: `month_ago = (beijing_now - timedelta(days=30)).astimezone(timezone.utc)`
   - Location: `routers/auth.py:2727-2740`
   - Status: ✅ Uses Beijing time

4. **Total Token** (`/api/auth/admin/token-stats`)
   - Query: All token usage (no date filter)
   - Date filter: None (all time)
   - Location: `routers/auth.py:2742-2755`
   - Status: ✅ No timezone needed

### ✅ Top 10 Users Rankings
1. **Top 10 Users (All Time)** (`/api/auth/admin/token-stats`)
   - Query: `top_users_query` - All time token usage
   - Location: `routers/auth.py:2757-2782`
   - Date filter: None (all time)
   - Status: ✅ No timezone needed

2. **Top 10 Users (Today)** (`/api/auth/admin/token-stats`)
   - Query: `top_users_today_query` - Today's token usage
   - Location: `routers/auth.py:2797-2828`
   - Date filter: `TokenUsage.created_at >= today_start` (Beijing time)
   - Status: ✅ Uses Beijing time

## Trend Charts Endpoint

### ✅ All Metrics (`/api/auth/admin/stats/trends`)
- **Location**: `routers/auth.py:2856-3034`
- **Metrics**: users, organizations, registrations, tokens
- **Date calculation**: Uses `get_beijing_now()` and converts to UTC for DB queries
- **Date mapping**: Maps UTC dates back to Beijing dates for display
- **Status**: ✅ Uses Beijing time (FIXED)

## Users Tab Queries

### ✅ User List (`/api/auth/admin/users`)
- **Query**: Paginated user list
- **Ordering**: `order_by(User.created_at.desc())`
- **Date filter**: None (just ordering)
- **Token stats**: Uses `week_ago` calculated from Beijing time
- **Location**: `routers/auth.py:2106-2224`
- **Status**: ✅ Week calculation uses Beijing time (FIXED)

## Schools Tab Queries

### ✅ Organization List (`/api/auth/admin/organizations`)
- **Query**: All organizations with token stats
- **Token stats**: Uses `week_ago` calculated from Beijing time
- **Location**: `routers/auth.py:1834-1905`
- **Status**: ✅ Week calculation uses Beijing time (FIXED)

## API Keys Tab Queries

### ✅ API Keys List (`/api/auth/admin/api_keys`)
- **Query**: All API keys with token stats
- **Token stats**: All time (no date filter)
- **Timestamp conversion**: Converts UTC to Beijing time for display
- **Location**: `routers/auth.py:3077-3169`
- **Status**: ✅ Timestamps converted to Beijing time

## Summary

### Queries with Date Filters (All Use Beijing Time ✅)
1. Today registrations
2. Today token usage
3. Past week token usage
4. Past month token usage
5. Top 10 users today
6. Trend charts (all metrics)

### Queries Without Date Filters (No Timezone Needed ✅)
1. Total users count
2. Total organizations count
3. Total tokens (all time)
4. Top 10 schools ranking (all time)
5. Top 10 users ranking (all time)
6. User list (just ordering, no date filter)
7. Organization list (no date filter)
8. API keys token stats (all time)

### Frontend Display (All Use Beijing Time ✅)
1. User registration dates - Converts UTC to Beijing time
2. School expiration dates - Uses Beijing time for comparison
3. API key timestamps - Converts UTC to Beijing time
4. Trend chart date labels - Uses Beijing timezone
5. Realtime monitoring timestamps - Uses Beijing timezone

## Conclusion

✅ **All admin panel queries are correctly using Beijing time where needed.**

- Date-filtered queries use `get_beijing_now()` and `get_beijing_today_start_utc()`
- All-time queries don't need timezone conversion
- Frontend displays convert UTC timestamps to Beijing time
- All rankings and top 10s are consistent with Beijing time boundaries

