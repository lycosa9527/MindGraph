# Complete Admin Panel Token Queries Audit

## All Tabs and Queries Checked

### 1. Dashboard Tab (`/api/auth/admin/stats`)

#### Stat Cards (4 cards):
1. ✅ **Total Users** - No token query
2. ✅ **Total Organizations** - No token query  
3. ✅ **Today Registrations** - Uses `today_start` (Beijing time)
4. ✅ **Total Tokens** - Uses `token_stats_by_org` (all time, no date filter)

#### Top 10 Schools Ranking:
- **Query**: `org_token_stats` (line 2596-2612)
- **Group by**: `Organization.id, Organization.name` ✅
- **Date filter**: None (all time)
- **Issue**: ✅ Already groups by Organization.id - CORRECT
- **Status**: ✅ No issues

---

### 2. Token Tracking Tab (`/api/auth/admin/token-stats`)

#### Stat Cards (4 cards):
1. ✅ **Today Token** - Line 2674-2681, uses `today_start` (Beijing time)
2. ✅ **Past Week Token** - Line 2708-2721, uses `week_ago` (Beijing time)
3. ✅ **Past Month Token** - Line 2726-2739, uses `month_ago` (Beijing time)
4. ✅ **Total Token** - Line 2742-2755, no date filter (all time)

#### Top 10 Users (All Time):
- **Query**: `top_users_query` (line 2758-2782)
- **Group by**: `User.id, User.phone, User.name, Organization.id, Organization.name` ✅ FIXED
- **Date filter**: None (all time)
- **Status**: ✅ Fixed - now groups by Organization.id

#### Top 10 Users (Today):
- **Query**: `top_users_today_query` (line 2800-2828)
- **Group by**: `User.id, User.phone, User.name, Organization.id, Organization.name` ✅ FIXED
- **Date filter**: `TokenUsage.created_at >= today_start` (Beijing time)
- **Status**: ✅ Fixed - now groups by Organization.id

---

### 3. Schools Tab (`/api/auth/admin/organizations`)

#### Organization List with Token Stats:
- **Query**: `org_token_stats` (line 1859-1875)
- **Group by**: `Organization.id, Organization.name` ✅
- **Date filter**: `TokenUsage.created_at >= week_ago` (Beijing time)
- **Status**: ✅ Already groups by Organization.id - CORRECT

---

### 4. Users Tab (`/api/auth/admin/users`)

#### User List with Token Stats:
- **Query**: `user_token_stats` (line 2164-2175)
- **Group by**: `TokenUsage.user_id` ✅
- **Date filter**: `TokenUsage.created_at >= week_ago` (Beijing time)
- **Status**: ✅ Correct - groups by user_id only

---

### 5. API Keys Tab (`/api/auth/admin/api_keys`)

#### API Keys List with Token Stats:
- **Query**: Per-key token stats (line 3105-3134)
- **Group by**: None (per key_id, no grouping needed)
- **Date filter**: None (all time)
- **Status**: ✅ Correct - no grouping issues

---

### 6. Trend Charts (`/api/auth/admin/stats/trends`)

#### All Metrics:
- **Users metric**: Groups by date ✅
- **Organizations metric**: Groups by date ✅
- **Registrations metric**: Groups by date ✅
- **Tokens metric**: Groups by date ✅
- **Date calculation**: Uses Beijing time ✅ FIXED
- **Status**: ✅ Fixed - uses Beijing time

---

## Summary of All Token Aggregation Queries

### Queries with GROUP BY:

1. **Dashboard - Top 10 Schools** (line 2596-2612)
   - Groups by: `Organization.id, Organization.name` ✅
   - Status: ✅ CORRECT

2. **Token Tab - Top 10 Users (All Time)** (line 2758-2782)
   - Groups by: `User.id, User.phone, User.name, Organization.id, Organization.name` ✅
   - Status: ✅ FIXED (added Organization.id)

3. **Token Tab - Top 10 Users (Today)** (line 2800-2828)
   - Groups by: `User.id, User.phone, User.name, Organization.id, Organization.name` ✅
   - Status: ✅ FIXED (added Organization.id)

4. **Schools Tab - Organization Token Stats** (line 1859-1875)
   - Groups by: `Organization.id, Organization.name` ✅
   - Status: ✅ CORRECT

5. **Users Tab - User Token Stats** (line 2164-2175)
   - Groups by: `TokenUsage.user_id` ✅
   - Status: ✅ CORRECT

### Queries WITHOUT GROUP BY (Simple Aggregations):

1. **Today Token Stats** (line 2674-2681) - `func.sum()` only ✅
2. **Week Token Stats** (line 2708-2721) - `func.sum()` only ✅
3. **Month Token Stats** (line 2726-2739) - `func.sum()` only ✅
4. **Total Token Stats** (line 2742-2755) - `func.sum()` only ✅
5. **Dashboard Week Token Stats** (line 2578-2585) - `func.sum()` only ✅
6. **API Keys Token Stats** (line 3105-3134) - Per key, no grouping ✅
7. **Trend Charts** (line 3016-3026) - Groups by date only ✅

---

## Potential Issues Found and Fixed

### ✅ FIXED: Grouping by Organization.name Only
- **Issue**: Top 10 users queries grouped by `Organization.name` only
- **Problem**: If multiple organizations have the same name, users would be incorrectly grouped together
- **Fix**: Added `Organization.id` to group_by clause
- **Location**: 
  - `routers/auth.py:2758-2782` (Top 10 users all time)
  - `routers/auth.py:2800-2828` (Top 10 users today)

### ✅ ADDED: Verification Logging
- **Location**: `routers/auth.py:2701-2706, 2853-2863`
- **Purpose**: Logs token count discrepancies for debugging
- **Checks**:
  - All tokens vs Authenticated users only
  - Top 10 sum vs Authenticated users total

---

## All Queries Verified ✅

All token aggregation queries have been checked:
- ✅ Correct grouping (no double counting)
- ✅ Correct date filters (Beijing time)
- ✅ Correct aggregation functions
- ✅ No missing group_by clauses
- ✅ Verification logging added

