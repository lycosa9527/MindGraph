# China Map Location Analytics Dashboard - Framework Design

## Table of Contents
1. [Feature Overview](#feature-overview)
2. [Architecture Design](#architecture-design)
3. [Data Flow](#data-flow)
4. [Backend API Design](#backend-api-design)
5. [Frontend Implementation](#frontend-implementation)
6. [IP Geolocation Integration](#ip-geolocation-integration)
7. [Data Storage Strategy](#data-storage-strategy)
8. [Implementation Plan](#implementation-plan)
9. [Dependencies](#dependencies)

---

## Feature Overview

### Purpose
Create a separate admin dashboard page that visualizes user distribution and token usage across China using an interactive heatmap. The dashboard will show:
- **Left Panel**: User statistics by province/city
- **Center Panel**: Interactive China map with heatmap visualization
- **Right Panel**: Token usage statistics by province/city

### Key Features
- Real-time location-based analytics
- Interactive China map with province-level heatmap
- User count visualization by location
- Token usage visualization by location
- Responsive 3-column layout
- Auto-refresh capability

### User Access
- Admin-only access (same authentication as existing admin panel)
- Separate HTML page: `/admin/location-analytics` or `/admin/map`

---

## Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (HTML/JS)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Left Panel  │  │  China Map    │  │ Right Panel  │     │
│  │  User Stats  │  │  (ECharts)    │  │ Token Stats  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP/SSE
┌─────────────────────────────────────────────────────────────┐
│                    Backend API Layer                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /api/auth/admin/stats/location                      │  │
│  │  /api/auth/admin/stats/users-by-location             │  │
│  │  /api/auth/admin/stats/tokens-by-location            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Redis      │  │   SQLite     │  │  IP Geo      │     │
│  │  Activity    │  │   Users/     │  │  Service     │     │
│  │  Tracker     │  │   Tokens     │  │  (External)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Component Structure

```
routers/
  └── admin_location.py          # New router for location analytics endpoints

services/
  └── ip_geolocation.py           # IP to location lookup service

templates/
  └── admin_location.html         # New HTML page for location dashboard

static/
  └── js/
      ├── echarts.min.js          # ECharts library (to be added)
      └── admin-location.js       # Frontend JavaScript for dashboard

static/
  └── data/
      └── china-geo.json          # China map geoJSON (to be added)
```

---

## Data Flow

### 1. IP Address Collection
- **Source**: `utils/auth.py` - `get_client_ip()` function
- **Storage**: `services/redis_activity_tracker.py` - Session `ip_address` field
- **When**: On user login and session creation

### 2. IP to Location Conversion
- **Service**: `services/ip_geolocation.py`
- **Process**: 
  1. Check Redis cache for IP → location mapping
  2. If not cached, call external geolocation API
  3. Store result in Redis (TTL: 30 days)
  4. Return province, city, coordinates

### 3. Location Data Aggregation
- **Source**: Redis activity tracker sessions + SQLite token usage
- **Process**:
  1. Query active sessions with IP addresses
  2. Lookup location for each IP
  3. Group by province/city
  4. Count users per location
  5. Sum token usage per location
  6. Return aggregated data

### 4. Frontend Visualization
- **Update Frequency**: Every 30-60 seconds (configurable)
- **Method**: Polling or SSE (Server-Sent Events)
- **Display**: ECharts map with heatmap visualization

---

## Backend API Design

### Endpoint 1: Get Location Statistics
```
GET /api/auth/admin/stats/location
```

**Response:**
```json
{
  "timestamp": "2025-01-20T10:30:00+08:00",
  "total_users": 1250,
  "total_tokens": 500000,
  "provinces": [
    {
      "name": "北京",
      "code": "110000",
      "user_count": 150,
      "token_usage": 50000,
      "cities": [
        {
          "name": "北京",
          "user_count": 150,
          "token_usage": 50000
        }
      ]
    },
    {
      "name": "上海",
      "code": "310000",
      "user_count": 120,
      "token_usage": 45000,
      "cities": [...]
    }
  ]
}
```

### Endpoint 2: Get Users by Location
```
GET /api/auth/admin/stats/users-by-location
Query Params:
  - province (optional): Filter by province code
  - city (optional): Filter by city name
  - limit (optional): Max results (default: 50)
```

**Response:**
```json
{
  "locations": [
    {
      "province": "北京",
      "city": "北京",
      "user_count": 150,
      "active_users": 45,
      "coordinates": [116.4074, 39.9042]
    }
  ],
  "total": 1250
}
```

### Endpoint 3: Get Tokens by Location
```
GET /api/auth/admin/stats/tokens-by-location
Query Params:
  - province (optional): Filter by province code
  - city (optional): Filter by city name
  - days (optional): Time range in days (default: 30)
```

**Response:**
```json
{
  "locations": [
    {
      "province": "北京",
      "city": "北京",
      "total_tokens": 50000,
      "today_tokens": 1500,
      "week_tokens": 10000,
      "month_tokens": 50000,
      "coordinates": [116.4074, 39.9042]
    }
  ],
  "total_tokens": 500000
}
```

### Endpoint 4: Get Map Data (for ECharts)
```
GET /api/auth/admin/stats/map-data
```

**Response:**
```json
{
  "series_data": [
    {
      "name": "北京",
      "value": [116.4074, 39.9042, 50000]  // [lng, lat, token_usage]
    },
    {
      "name": "上海",
      "value": [121.4737, 31.2304, 45000]
    }
  ],
  "geo_json": "..." // China geoJSON (or reference to static file)
}
```

---

## Frontend Implementation

### Page Layout

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Location Analytics Dashboard</title>
    <link rel="stylesheet" href="/static/css/admin.css">
    <script src="/static/js/echarts.min.js"></script>
</head>
<body>
    <div class="location-dashboard">
        <!-- Left Panel: User Stats -->
        <div class="left-panel">
            <h2>用户统计</h2>
            <div class="stats-card">
                <h3>总用户数</h3>
                <div id="total-users">-</div>
            </div>
            <div class="stats-card">
                <h3>按省份</h3>
                <div id="users-by-province"></div>
            </div>
            <div class="stats-card">
                <h3>活跃用户</h3>
                <div id="active-users">-</div>
            </div>
        </div>
        
        <!-- Center: China Map -->
        <div class="center-panel">
            <div id="china-map" style="width: 100%; height: 800px;"></div>
        </div>
        
        <!-- Right Panel: Token Stats -->
        <div class="right-panel">
            <h2>Token统计</h2>
            <div class="stats-card">
                <h3>总Token使用</h3>
                <div id="total-tokens">-</div>
            </div>
            <div class="stats-card">
                <h3>按省份</h3>
                <div id="tokens-by-province"></div>
            </div>
            <div class="stats-card">
                <h3>今日使用</h3>
                <div id="today-tokens">-</div>
            </div>
        </div>
    </div>
    
    <script src="/static/js/admin-location.js"></script>
</body>
</html>
```

### CSS Layout (3-column grid)

```css
.location-dashboard {
    display: grid;
    grid-template-columns: 25% 50% 25%;
    gap: 1rem;
    padding: 1rem;
    height: 100vh;
}

.left-panel, .right-panel {
    background: var(--card-bg);
    padding: 1rem;
    border-radius: 8px;
    overflow-y: auto;
}

.center-panel {
    background: var(--card-bg);
    padding: 1rem;
    border-radius: 8px;
}
```

### ECharts Map Configuration

```javascript
// Initialize ECharts map
const chart = echarts.init(document.getElementById('china-map'));

// Register China map geoJSON
echarts.registerMap('china', chinaGeoJSON);

// Configure heatmap
const option = {
    geo: {
        map: 'china',
        roam: true,  // Enable zoom/pan
        itemStyle: {
            areaColor: '#1e293b',
            borderColor: '#334155'
        },
        emphasis: {
            itemStyle: {
                areaColor: '#3b82f6'
            }
        }
    },
    series: [{
        type: 'scatter',
        coordinateSystem: 'geo',
        data: mapData,  // From API
        symbolSize: function(val) {
            return Math.sqrt(val[2]) / 10;  // Size based on token usage
        },
        itemStyle: {
            color: function(params) {
                // Color intensity based on token usage
                const max = Math.max(...mapData.map(d => d.value[2]));
                const ratio = params.value[2] / max;
                return echarts.color.lift(
                    echarts.color.parse('#ef4444'),
                    ratio
                );
            }
        }
    }],
    tooltip: {
        trigger: 'item',
        formatter: function(params) {
            return `${params.name}<br/>用户: ${params.value[3]}<br/>Token: ${params.value[2]}`;
        }
    }
};

chart.setOption(option);
```

---

## IP Geolocation Integration

### Service: `services/ip_geolocation.py`

**Features:**
- IP to location lookup
- Redis caching (30-day TTL)
- Support for multiple geolocation providers
- Fallback mechanism

**Providers (Priority Order):**
1. **ip-api.com** (Free tier: 45 requests/minute)
   - Good China coverage
   - Returns: country, regionName (province), city, lat, lon
   - No API key required

2. **ipapi.co** (Free tier: 1000 requests/day)
   - Good global coverage
   - Returns: country_name, region, city, latitude, longitude
   - Requires API key for higher limits

3. **MaxMind GeoIP2** (Local database)
   - No API calls
   - Requires database file download
   - Good for high-volume scenarios

**Implementation Pattern:**
```python
class IPGeolocationService:
    def __init__(self):
        self.redis_client = get_redis()
        self.cache_prefix = "ip:location:"
        self.cache_ttl = 30 * 24 * 3600  # 30 days
    
    async def get_location(self, ip: str) -> Optional[Dict]:
        # 1. Check Redis cache
        cached = self._get_from_cache(ip)
        if cached:
            return cached
        
        # 2. Call geolocation API
        location = await self._lookup_ip(ip)
        
        # 3. Store in cache
        if location:
            self._store_in_cache(ip, location)
        
        return location
    
    def _lookup_ip(self, ip: str) -> Dict:
        # Try providers in order
        # Return: {province, city, lat, lng, country}
        pass
```

---

## Data Storage Strategy

### Redis Cache Structure

```
ip:location:{ip_address} -> {
    "province": "北京",
    "city": "北京",
    "province_code": "110000",
    "lat": 39.9042,
    "lng": 116.4074,
    "country": "CN",
    "lookup_time": "2025-01-20T10:30:00+08:00"
}
TTL: 30 days

location:stats:{province_code} -> {
    "user_count": 150,
    "token_usage": 50000,
    "last_updated": "2025-01-20T10:30:00+08:00"
}
TTL: 1 hour
```

### SQLite Schema Extensions

**Option 1: Add location fields to existing tables**
```sql
ALTER TABLE users ADD COLUMN last_location_province VARCHAR(50);
ALTER TABLE users ADD COLUMN last_location_city VARCHAR(50);
ALTER TABLE users ADD COLUMN last_location_lookup_at DATETIME;
```

**Option 2: Create location tracking table**
```sql
CREATE TABLE user_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    ip_address VARCHAR(45),
    province VARCHAR(50),
    city VARCHAR(50),
    latitude REAL,
    longitude REAL,
    lookup_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_user_locations_user_id ON user_locations(user_id);
CREATE INDEX idx_user_locations_province ON user_locations(province);
CREATE INDEX idx_user_locations_city ON user_locations(city);
```

---

## Implementation Plan

### Phase 1: IP Geolocation Service
1. ✅ Create `services/ip_geolocation.py`
2. ✅ Implement IP lookup with caching
3. ✅ Add provider fallback logic
4. ✅ Test with sample IPs

### Phase 2: Backend API Endpoints
1. ✅ Create `routers/admin_location.py`
2. ✅ Implement `/api/auth/admin/stats/location`
3. ✅ Implement `/api/auth/admin/stats/users-by-location`
4. ✅ Implement `/api/auth/admin/stats/tokens-by-location`
5. ✅ Implement `/api/auth/admin/stats/map-data`
6. ✅ Add admin authentication checks
7. ✅ Register router in `main.py`

### Phase 3: Data Aggregation
1. ✅ Extend activity tracker to store location data
2. ✅ Create location aggregation queries
3. ✅ Add location fields to user sessions
4. ✅ Implement token usage grouping by location

### Phase 4: Frontend Dashboard
1. ✅ Download ECharts library to `static/js/`
2. ✅ Download China geoJSON to `static/data/`
3. ✅ Create `templates/admin_location.html`
4. ✅ Create `static/js/admin-location.js`
5. ✅ Implement map visualization
6. ✅ Implement left/right panels
7. ✅ Add auto-refresh functionality
8. ✅ Add CSS styling

### Phase 5: Integration & Testing
1. ✅ Add route in `routers/pages.py` for `/admin/location-analytics`
2. ✅ Test with real user data
3. ✅ Performance optimization
4. ✅ Error handling
5. ✅ Documentation

---

## Dependencies

### Python Packages
- **httpx** (already in requirements.txt) - For geolocation API calls
- **redis** (already in requirements.txt) - For caching
- **No new packages required** ✅

### JavaScript Libraries
- **ECharts 5.x** - To be added to `static/js/echarts.min.js`
  - Download: https://echarts.apache.org/zh/download.html
  - Size: ~800KB minified
  - License: Apache 2.0

### Data Files
- **China geoJSON** - To be added to `static/data/china-geo.json`
  - Source: https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json
  - Or: ECharts map data repository
  - Size: ~500KB

### External Services
- **IP Geolocation API** (free tier sufficient)
  - ip-api.com: 45 requests/minute (free)
  - ipapi.co: 1000 requests/day (free)
  - MaxMind GeoIP2: Local database (optional)

---

## Security Considerations

1. **Admin Authentication**: All endpoints require admin role check
2. **Rate Limiting**: IP geolocation API calls should be rate-limited
3. **Data Privacy**: IP addresses should be hashed/anonymized in logs
4. **Caching**: Prevent cache poisoning with input validation
5. **CORS**: No CORS needed (same-origin admin panel)

---

## Performance Considerations

1. **Caching Strategy**: 
   - IP → Location: 30-day cache
   - Location stats: 1-hour cache
   - Reduces API calls significantly

2. **Aggregation Frequency**:
   - Real-time: Every 30-60 seconds
   - Background: Pre-aggregate hourly

3. **Database Optimization**:
   - Index on location fields
   - Batch IP lookups
   - Use Redis for hot data

4. **Frontend Optimization**:
   - Lazy load ECharts library
   - Debounce map interactions
   - Virtual scrolling for long lists

---

## Future Enhancements

1. **Time Range Selection**: Filter by date range
2. **City-Level Detail**: Click province to see cities
3. **Export Functionality**: Export data as CSV/Excel
4. **Historical Trends**: Show location trends over time
5. **Comparison Mode**: Compare two time periods
6. **Mobile Responsive**: Optimize for mobile devices
7. **World Map Option**: Expand beyond China

---

## Notes

- This dashboard is separate from the main admin panel
- Uses existing authentication system
- Follows existing code patterns and conventions
- Can be implemented incrementally (Phase 1 → Phase 5)
- No breaking changes to existing functionality

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-20  
**Status**: Framework Design - Ready for Implementation


