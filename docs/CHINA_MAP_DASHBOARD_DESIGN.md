# public dashboard

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
Create a public real-time dashboard that visualizes current user activity and system statistics. The dashboard will show:
- **Left Panel**: Key system statistics (connected users, registered users, token usage)
- **Center Panel**: Interactive China map heatmap showing which cities users are currently using the application from
- **Right Panel**: Real-time activity stream showing user actions (e.g., "User A has generated diagram A about topic A")

### Key Features
- Real-time location-based analytics showing current active users
- Interactive China map with city-level heatmap visualization
- Live user activity streaming panel
- System statistics display (users, tokens)
- Responsive 3-column layout
- Real-time updates via WebSocket or Server-Sent Events (SSE)

### User Access
- **Passkey-protected access** (similar to demo passkey modal)
- Accessible at: `/pub-dash` or `/public-dashboard`
- Users must enter a 6-digit passkey to access the dashboard
- Passkey stored in environment variable: `PUBLIC_DASHBOARD_PASSKEY`
- After successful passkey verification, users can view the dashboard
- Session stored in cookie (similar to demo mode)

---

## Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (HTML/JS)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Left Panel  │  │  China Map    │  │ Right Panel  │     │
│  │  Statistics  │  │  Heatmap      │  │ Activity     │     │
│  │  (Users/     │  │  (Current     │  │ Stream       │     │
│  │   Tokens)    │  │   Users)     │  │ (Real-time)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ↕ WebSocket/SSE
┌─────────────────────────────────────────────────────────────┐
│                    Backend API Layer                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  GET /api/public/stats                              │  │
│  │  GET /api/public/map-data                           │  │
│  │  WS /api/public/activity-stream                     │  │
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
  └── public_dashboard.py         # New router for public dashboard endpoints

services/
  ├── ip_geolocation.py           # IP to location lookup service
  └── activity_stream.py          # Real-time activity streaming service

templates/
  └── public_dashboard.html       # New HTML page for public dashboard

static/
  └── js/
      ├── echarts.min.js          # ECharts library (to be added)
      └── public-dashboard.js     # Frontend JavaScript for dashboard

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

### 4. Activity Tracking & Broadcasting
- **Source**: Diagram generation endpoints (e.g., `/api/generate_graph`)
- **Process**:
  1. When a user generates a diagram, capture the event
  2. Anonymize user identifier (use "User A", "User B", etc.)
  3. Extract: diagram type, topic/prompt
  4. Broadcast via WebSocket/SSE to all connected dashboard clients
  5. Store recent activities in Redis (last 100 items, TTL: 1 hour)

### 5. Frontend Visualization
- **Update Frequency**: Real-time via WebSocket or SSE
- **Method**: WebSocket connection for live updates
- **Display**: 
  - ECharts map with heatmap visualization showing current active users by city
  - Real-time activity stream panel showing user actions as they happen
  - Statistics panel updated in real-time

---

## Activity Tracking Integration

### Integration Points

The activity stream needs to capture events from diagram generation endpoints. Key integration points:

1. **Main Graph Generation Endpoint**
   - File: `routers/api/generate_graph.py` or similar
   - Hook: After successful diagram generation
   - Capture: user_id (anonymized), diagram_type, topic/prompt

2. **Activity Stream Service**
   - File: `services/activity_stream.py` (new)
   - Responsibilities:
     - Maintain WebSocket connections
     - Broadcast activity events to all connected clients
     - Manage connection lifecycle
     - Rate limiting per connection

3. **User Anonymization**
   - Map user IDs to anonymized identifiers (User A, User B, etc.)
   - Use consistent mapping stored in Redis
   - Format: `user:anon:{user_id} -> "User A"`

### Example Integration Code

```python
# In diagram generation endpoint
from services.activity_stream import ActivityStreamService

async def generate_graph(...):
    # ... existing diagram generation logic ...
    
    # After successful generation
    activity_service = ActivityStreamService()
    await activity_service.broadcast_activity(
        user_id=user_id,
        action="generated",
        diagram_type=diagram_type,  # e.g., "mindmap", "concept_map"
        topic=topic_or_prompt[:50]  # Truncate to 50 chars
    )
```

---

## Authentication Design

### Passkey Authentication Flow

The public dashboard uses passkey authentication similar to the demo passkey modal (`/demo`). Users must enter a 6-digit passkey to access the dashboard.

#### Flow Diagram

```
User visits /pub-dash
    ↓
Check dashboard_access_token cookie
    ↓
┌─────────────────┐
│ Cookie exists?   │
└─────────────────┘
    │
    ├─ Yes → Verify token → Valid? → Show Dashboard
    │                              └─ Invalid → Show Passkey Modal
    │
    └─ No → Show Passkey Modal
            ↓
        User enters 6-digit passkey
            ↓
        POST /api/auth/public-dashboard/verify
            ↓
        ┌─────────────────────┐
        │ Passkey valid?      │
        └─────────────────────┘
            │
            ├─ Yes → Create dashboard_access_token cookie
            │        → Redirect to dashboard
            │
            └─ No → Show error message
```

#### Step-by-Step Process

1. **User visits `/pub-dash`**
   - Backend checks for `dashboard_access_token` cookie
   - If cookie exists and is valid → Show dashboard directly
   - If cookie missing or invalid → Show passkey modal

2. **Passkey Modal** (`templates/public-dashboard-login.html`)
   - Similar UI to `/demo` passkey modal
   - User enters 6-digit passkey
   - Client-side validation: Must be exactly 6 digits
   - Calls `POST /api/auth/public-dashboard/verify` endpoint

3. **Backend Verification** (`/api/auth/public-dashboard/verify`)
   - Receives passkey from request body
   - Compares against `PUBLIC_DASHBOARD_PASSKEY` environment variable
   - If valid:
     - Generate simple dashboard session token (not full JWT)
     - Set cookie: `dashboard_access_token` with token
     - Cookie expiration: 24 hours (configurable)
     - Return success response
   - If invalid:
     - Return error response
     - Log failed attempt (for rate limiting)

4. **Session Management**
   - Dashboard session cookie: `dashboard_access_token`
   - Token format: Simple string token (e.g., `dashboard_<timestamp>_<random>`)
   - Cookie expiration: 24 hours (or configurable via env)
   - No user account required (just passkey verification)
   - Token stored in Redis with expiration matching cookie

5. **API Endpoint Protection**
   - All dashboard API endpoints check for `dashboard_access_token` cookie
   - If missing or invalid → Return 401 Unauthorized
   - If valid → Process request

#### Implementation Details

**Environment Variable:**
```bash
PUBLIC_DASHBOARD_PASSKEY=123456  # 6-digit passkey
```

**Cookie Settings:**
- Name: `dashboard_access_token`
- HttpOnly: `true` (prevent XSS)
- Secure: `true` (HTTPS only in production)
- SameSite: `Lax`
- Max-Age: 86400 seconds (24 hours)

**Rate Limiting:**
- Passkey verification attempts: 5 attempts per IP per 15 minutes
- Prevents brute force attacks
- Store attempts in Redis with TTL

**Token Storage:**
- Store token in Redis: `dashboard:session:{token}` → `{ip, created_at, expires_at}`
- Verify token exists and not expired on each request
- Auto-cleanup expired tokens

### Endpoint: Verify Public Dashboard Passkey
```
POST /api/auth/public-dashboard/verify
```

**Request:**
```json
{
  "passkey": "123456"
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Access granted",
  "dashboard_token": "dashboard_session_token_here"
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Invalid passkey"
}
```

**Implementation Notes:**
- Similar to `/api/auth/demo/verify` endpoint
- Check passkey against `PUBLIC_DASHBOARD_PASSKEY` env variable
- Generate simple session token (not full JWT, just dashboard access)
- Set cookie: `dashboard_access_token` with session token
- No user account creation needed

---

## Backend API Design

### Endpoint 1: Get Public Dashboard Statistics
```
GET /api/public/stats
```

**Authentication:** Dashboard session cookie (`dashboard_access_token`)

**Response:**
```json
{
  "timestamp": "2025-01-20T10:30:00+08:00",
  "connected_users": 45,
  "registered_users": 1250,
  "tokens_used_today": 15000,
  "total_tokens_used": 500000
}
```

**Implementation Notes:**
- `connected_users`: From `redis_activity_tracker.get_stats()['active_users_count']`
- `registered_users`: From `db.query(User).count()`
- `tokens_used_today`: From `TokenUsage` table filtered by today (Beijing time)
- `total_tokens_used`: From `TokenUsage` table sum of all successful requests

### Endpoint 2: Get Map Data (Current Active Users by City)
```
GET /api/public/map-data
```

**Authentication:** Dashboard session cookie (`dashboard_access_token`)

**Response:**
```json
{
  "series_data": [
    {
      "name": "北京",
      "value": [116.4074, 39.9042, 15]  // [lng, lat, active_user_count]
    },
    {
      "name": "上海",
      "value": [121.4737, 31.2304, 12]
    },
    {
      "name": "深圳",
      "value": [114.0579, 22.5431, 8]
    }
  ]
}
```

**Implementation Notes:**
- Get active sessions from `redis_activity_tracker.get_active_users()`
- Extract `ip_address` from each session
- Lookup location via `ip_geolocation.get_location(ip)` (with caching)
- Group by city and count active users per city
- Return coordinates and user count for ECharts scatter plot
- Note: `geo_json` can be loaded from static file on frontend

### Endpoint 3: Activity Stream (Server-Sent Events)
```
GET /api/public/activity-stream
```

**Authentication:** Dashboard session cookie (`dashboard_access_token`)

**Content-Type:** `text/event-stream`

**Message Format:**
```json
{
  "type": "activity",
  "timestamp": "2025-01-20T10:30:15+08:00",
  "user": "User A",
  "action": "generated",
  "diagram_type": "mindmap",
  "topic": "topic A",
  "city": "北京"
}
```

**Message Types:**
- `activity`: New user activity (diagram generation)
- `stats_update`: Statistics update (connected_users, tokens_used_today)
- `heartbeat`: Keep-alive ping

**Example Messages:**
- `{"type": "activity", "user": "User A", "action": "generated", "diagram_type": "mindmap", "topic": "topic A"}`
- `{"type": "activity", "user": "User B", "action": "generated", "diagram_type": "concept_map", "topic": "topic B"}`
- `{"type": "stats_update", "connected_users": 46, "tokens_used_today": 15025}`
- `{"type": "heartbeat", "timestamp": "2025-01-20T10:30:20+08:00"}`

**Implementation Notes:**
- Use SSE (Server-Sent Events) similar to `admin_realtime.py`
- Subscribe to activity events from `ActivityStreamService`
- Poll for stats updates every 5-10 seconds
- Send heartbeat every 30 seconds
- No rate limiting needed (public, but consider DoS protection)

---

## Frontend Implementation

### Page Layout

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Public Dashboard - Real-time Analytics</title>
    <link rel="stylesheet" href="/static/css/public-dashboard.css">
    <script src="/static/js/echarts.min.js"></script>
</head>
<body>
    <div class="public-dashboard">
        <!-- Left Panel: Statistics -->
        <div class="left-panel">
            <h2>Statistics</h2>
            <div class="stats-card">
                <h3>Connected Users</h3>
                <div id="connected-users" class="stat-value">-</div>
            </div>
            <div class="stats-card">
                <h3>Registered Users</h3>
                <div id="registered-users" class="stat-value">-</div>
            </div>
            <div class="stats-card">
                <h3>Tokens Used Today</h3>
                <div id="tokens-today" class="stat-value">-</div>
            </div>
            <div class="stats-card">
                <h3>Total Tokens Used</h3>
                <div id="total-tokens" class="stat-value">-</div>
            </div>
        </div>
        
        <!-- Center: China Map Heatmap -->
        <div class="center-panel">
            <h2>Current Users by City</h2>
            <div id="china-map" style="width: 100%; height: 800px;"></div>
        </div>
        
        <!-- Right Panel: Activity Stream -->
        <div class="right-panel">
            <h2>Live Activity</h2>
            <div id="activity-stream" class="activity-stream">
                <!-- Activity items will be appended here -->
            </div>
        </div>
    </div>
    
    <script src="/static/js/public-dashboard.js"></script>
</body>
</html>
```

### CSS Layout (3-column grid)

```css
.public-dashboard {
    display: grid;
    grid-template-columns: 25% 50% 25%;
    gap: 1rem;
    padding: 1rem;
    height: 100vh;
    background: #0f172a;
}

.left-panel, .right-panel {
    background: #1e293b;
    padding: 1rem;
    border-radius: 8px;
    overflow-y: auto;
    color: #e2e8f0;
}

.center-panel {
    background: #1e293b;
    padding: 1rem;
    border-radius: 8px;
    color: #e2e8f0;
}

.stats-card {
    background: #334155;
    padding: 1rem;
    margin-bottom: 1rem;
    border-radius: 6px;
}

.stat-value {
    font-size: 2rem;
    font-weight: bold;
    color: #60a5fa;
}

.activity-stream {
    max-height: 800px;
    overflow-y: auto;
}

.activity-item {
    background: #334155;
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    border-radius: 4px;
    border-left: 3px solid #3b82f6;
    font-size: 0.9rem;
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateX(-10px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}
```

## How ECharts and geoJSON Work Together

### What is ECharts?

**ECharts** (Apache ECharts) is a powerful JavaScript charting library that supports:
- Line charts, bar charts, pie charts
- **Geographic maps** (using geoJSON data)
- 3D visualizations
- Real-time data updates

### What is geoJSON?

**geoJSON** is a standard format for encoding geographic data structures using JSON. It defines:
- **Features**: Geographic objects (provinces, cities, countries)
- **Geometry**: Shapes (Polygon, MultiPolygon, Point, etc.)
- **Properties**: Metadata (name, code, etc.)
- **Coordinates**: Longitude/latitude points that define boundaries

**Example geoJSON structure:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "name": "北京",
        "cp": [116.4074, 39.9042],  // Center point [lng, lat]
        "adcode": "110000"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [116.1234, 39.5678],  // Boundary coordinates
            [116.2345, 39.6789],
            // ... more coordinates forming the province boundary
          ]
        ]
      }
    }
  ]
}
```

### How They Work Together

#### Step 1: Load geoJSON Data

The China geoJSON file contains the boundary coordinates for all provinces/cities. You can:
- **Option A**: Load from static file
```javascript
// Load geoJSON from static file
fetch('/static/data/china-geo.json')
    .then(response => response.json())
    .then(chinaGeoJSON => {
        // Register map with ECharts
        echarts.registerMap('china', chinaGeoJSON);
    });
```

- **Option B**: Load from API (if backend serves it)
```javascript
// Backend returns geoJSON in response
fetch('/api/public/map-data')
    .then(response => response.json())
    .then(data => {
        echarts.registerMap('china', data.geo_json);
        // Use data.series_data for scatter points
    });
```

#### Step 2: Register the Map

```javascript
// Register the geoJSON as a map named 'china'
echarts.registerMap('china', chinaGeoJSON);
```

This tells ECharts:
- The geographic boundaries (from geoJSON coordinates)
- The map name to reference later (`'china'`)
- Province/city names and properties

#### Step 3: Create the Base Map

```javascript
const option = {
    geo: {
        map: 'china',  // Reference the registered map
        roam: true,    // Allow zoom/pan
        itemStyle: {
            areaColor: '#1e293b',  // Background color for provinces
            borderColor: '#334155'   // Border color
        }
    }
};
```

The `geo` component renders the base map using the geoJSON boundaries.

#### Step 4: Add Data Points (Scatter Plot)

```javascript
series: [{
    type: 'scatter',
    coordinateSystem: 'geo',  // Use geographic coordinate system
    data: [
        {
            name: "北京",
            value: [116.4074, 39.9042, 15]  // [lng, lat, user_count]
        },
        {
            name: "上海",
            value: [121.4737, 31.2304, 12]
        }
    ]
}]
```

**Key Points:**
- `coordinateSystem: 'geo'` - Places points on the geographic map
- `value: [lng, lat, count]` - Longitude, Latitude, and data value
- ECharts automatically converts lat/lng to map coordinates

#### Step 5: Style the Data Points

```javascript
symbolSize: function(val) {
    // val is the value array: [lng, lat, user_count]
    return Math.sqrt(val[2]) * 3;  // Size based on user count
},
itemStyle: {
    color: function(params) {
        // Color intensity based on user count
        const max = Math.max(...mapData.map(d => d.value[2]));
        const ratio = params.value[2] / max;
        return echarts.color.lift('#ef4444', ratio);  // Red color, intensity based on ratio
    }
}
```

### Complete Example

```javascript
// 1. Initialize ECharts
const chart = echarts.init(document.getElementById('china-map'));

// 2. Load and register geoJSON
fetch('/static/data/china-geo.json')
    .then(response => response.json())
    .then(chinaGeoJSON => {
        echarts.registerMap('china', chinaGeoJSON);
        
        // 3. Fetch data points from API
        fetch('/api/public/map-data')
            .then(response => response.json())
            .then(data => {
                // 4. Configure chart
                const option = {
                    backgroundColor: '#1e293b',
                    geo: {
                        map: 'china',
                        roam: true,
                        itemStyle: {
                            areaColor: '#1e293b',
                            borderColor: '#334155'
                        }
                    },
                    series: [{
                        type: 'scatter',
                        coordinateSystem: 'geo',
                        data: data.series_data,  // [{name: "北京", value: [lng, lat, count]}]
                        symbolSize: function(val) {
                            return Math.sqrt(val[2]) * 3;
                        },
                        itemStyle: {
                            color: '#ef4444'
                        }
                    }]
                };
                
                // 5. Render chart
                chart.setOption(option);
            });
    });
```

### Data Flow Summary

```
1. Backend API (/api/public/map-data)
   ↓ Returns: {series_data: [{name: "北京", value: [116.4074, 39.9042, 15]}]}
   
2. Frontend loads geoJSON (static file or API)
   ↓ Contains: Province boundaries, names, center points
   
3. ECharts.registerMap('china', geoJSON)
   ↓ Registers geographic boundaries
   
4. chart.setOption({geo: {map: 'china'}, series: [{data: series_data}]})
   ↓ Renders base map + scatter points
   
5. Result: Interactive map with data points showing user distribution
```

### Key Concepts

- **geoJSON** = Geographic boundaries (the map shape)
- **Scatter data** = Data points with coordinates (the dots on the map)
- **coordinateSystem: 'geo'** = Tells ECharts to use geographic coordinates (lat/lng)
- **ECharts converts** lat/lng automatically to screen coordinates based on the geoJSON boundaries

### ECharts Map Configuration

```javascript
// Initialize ECharts map
const chart = echarts.init(document.getElementById('china-map'));

// Register China map geoJSON
echarts.registerMap('china', chinaGeoJSON);

// Configure heatmap for current active users
const option = {
    backgroundColor: '#1e293b',
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
        data: mapData,  // From API: [{name: "北京", value: [lng, lat, active_user_count]}]
        symbolSize: function(val) {
            return Math.sqrt(val[2]) * 3;  // Size based on active user count
        },
        itemStyle: {
            color: function(params) {
                // Color intensity based on active user count
                const max = Math.max(...mapData.map(d => d.value[2]));
                const ratio = params.value[2] / max;
                return echarts.color.lift(
                    echarts.color.parse('#ef4444'),
                    ratio
                );
            }
        },
        label: {
            show: true,
            formatter: '{b}\n{c[2]} users',
            position: 'right'
        }
    }],
    tooltip: {
        trigger: 'item',
        formatter: function(params) {
            return `${params.name}<br/>Active Users: ${params.value[2]}`;
        }
    }
};

chart.setOption(option);

// Update map data in real-time
function updateMapData(newData) {
    chart.setOption({
        series: [{
            data: newData
        }]
    });
}
```

### Activity Stream JavaScript

```javascript
// Connect to WebSocket for real-time activity stream
const ws = new WebSocket('ws://localhost:9527/api/public/activity-stream');
const activityStream = document.getElementById('activity-stream');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    if (data.type === 'activity') {
        addActivityItem(data);
    } else if (data.type === 'stats_update') {
        updateStats(data);
    }
};

function addActivityItem(data) {
    const item = document.createElement('div');
    item.className = 'activity-item';
    item.innerHTML = `
        <strong>${data.user}</strong> has generated 
        <strong>${data.diagram_type}</strong> about 
        <em>${data.topic}</em>
        <span class="timestamp">${new Date(data.timestamp).toLocaleTimeString()}</span>
    `;
    activityStream.insertBefore(item, activityStream.firstChild);
    
    // Keep only last 50 items
    while (activityStream.children.length > 50) {
        activityStream.removeChild(activityStream.lastChild);
    }
}

function updateStats(data) {
    if (data.connected_users !== undefined) {
        document.getElementById('connected-users').textContent = data.connected_users;
    }
    if (data.tokens_used_today !== undefined) {
        document.getElementById('tokens-today').textContent = data.tokens_used_today.toLocaleString();
    }
}
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
1. Create `services/ip_geolocation.py` (if not exists)
2. Implement IP lookup with caching
3. Add provider fallback logic
4. Test with sample IPs

### Phase 2: Activity Stream Service
1. Create `services/activity_stream.py`
2. Implement `ActivityStreamService` class:
   - Maintain list of SSE connections
   - `broadcast_activity()` method to send activity events
   - `add_connection()` / `remove_connection()` for SSE management
   - User anonymization mapping (User A, User B, etc.)
3. Store recent activities in Redis (last 100 items, TTL: 1 hour)

### Phase 3: Authentication & Backend API Endpoints
1. **Authentication:**
   - Add `PUBLIC_DASHBOARD_PASSKEY` to environment variables
   - Create `POST /api/auth/public-dashboard/verify` endpoint in `routers/auth/login.py`
   - Create dashboard session management (simple token, not full JWT)
   - Create passkey modal page: `templates/public-dashboard-login.html` (similar to `demo-login.html`)

2. **Backend API Endpoints:**
   - Create `routers/public_dashboard.py` with:
     - `GET /api/public/stats` - Returns statistics (requires dashboard session)
     - `GET /api/public/map-data` - Returns current active users by city (requires dashboard session)
     - `GET /api/public/activity-stream` - SSE endpoint (requires dashboard session)
   - Add dashboard session verification middleware/dependency

3. **Page Routes:**
   - Create `GET /pub-dash` route in `routers/pages.py`:
     - Check for `dashboard_access_token` cookie
     - If valid → Show dashboard
     - If invalid/missing → Show passkey modal

4. Register router in `main.py`: `app.include_router(public_dashboard.router)`

### Phase 4: Activity Tracking Integration
1. Update `routers/api/diagram_generation.py`:
   - After successful diagram generation, call `ActivityStreamService.broadcast_activity()`
   - Pass: user_id (for anonymization), diagram_type, topic/prompt
2. Update `routers/api/png_export.py` (if needed):
   - Similar activity tracking for PNG generation endpoints

### Phase 3: Data Aggregation & Activity Tracking
1. Extend activity tracker to store location data for active sessions
2. Create query to get current active users by city
3. Add location fields to user sessions
4. Implement activity stream service to capture and broadcast user actions:
   - Hook into diagram generation endpoints
   - Capture: user (anonymized), diagram type, topic
   - Broadcast via WebSocket/SSE
5. Implement statistics aggregation for dashboard metrics

### Phase 4: Frontend Dashboard
1. **Passkey Modal:**
   - Create `templates/public-dashboard-login.html` (similar to `demo-login.html`)
   - 6-digit passkey input
   - Call `/api/auth/public-dashboard/verify` endpoint
   - On success → Set cookie and redirect to dashboard

2. **Dashboard Page:**
   - Download ECharts library to `static/js/`
   - Download China geoJSON to `static/data/`
   - Create `templates/public_dashboard.html`
   - Create `static/js/public-dashboard.js`
   - Create `static/css/public-dashboard.css`
   - Implement map visualization showing current active users by city
   - Implement statistics panel (left) with real-time updates
   - Implement activity stream panel (right) with WebSocket connection
   - Add real-time update functionality for all components
   - Add CSS styling for modern, dark theme
   - Include dashboard session cookie in all API requests

### Phase 5: Integration & Testing
1. Add route in `routers/pages.py` for `/dashboard` or `/public-dashboard`
2. Integrate activity tracking hooks into diagram generation endpoints
3. Test WebSocket connection and real-time updates
4. Test with real user data
5. Performance optimization (connection pooling, caching)
6. Error handling and reconnection logic
7. Documentation

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

1. **Passkey Protection**: 
   - Dashboard requires 6-digit passkey (stored in `PUBLIC_DASHBOARD_PASSKEY` env variable)
   - Similar security model to demo passkey
   - Session cookie expires after 24 hours (configurable)

2. **Session Management**: 
   - Dashboard session token stored in cookie: `dashboard_access_token`
   - Token verification on all API endpoints
   - No user account required (just passkey verification)

3. **Data Privacy**: 
   - Only show anonymized usernames (e.g., "User A", "User B")
   - Do not expose real user IDs or personal information
   - IP addresses should be hashed/anonymized in logs

4. **Rate Limiting**: 
   - Passkey verification attempts: 5 attempts per IP per 15 minutes
   - WebSocket connections should be rate-limited
   - IP geolocation API calls should be rate-limited

5. **Caching**: Prevent cache poisoning with input validation

6. **DoS Protection**: 
   - Implement connection limits and rate limiting for WebSocket connections
   - Limit concurrent SSE connections per IP

7. **CORS**: Configure CORS appropriately if needed

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

- This is a **public dashboard** - no authentication required
- Real-time updates via WebSocket or Server-Sent Events
- Shows anonymized user activity (e.g., "User A", not real usernames)
- Map shows current active users by city, not historical data
- Activity stream shows recent user actions in real-time
- Follows existing code patterns and conventions
- Can be implemented incrementally (Phase 1 → Phase 5)
- No breaking changes to existing functionality
- Activity tracking hooks into existing diagram generation endpoints

---

---

## Endpoints Summary

### New Endpoints to Create

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/api/public/stats` | Get dashboard statistics (connected users, registered users, tokens) | No |
| GET | `/api/public/map-data` | Get current active users by city for map visualization | No |
| GET | `/api/public/activity-stream` | SSE stream for real-time activity updates | No |

### Files to Create

1. **`routers/public_dashboard.py`** - Public dashboard router with 3 endpoints (requires dashboard session)
2. **`services/activity_stream.py`** - Activity streaming service for broadcasting events
3. **`templates/public-dashboard-login.html`** - Passkey modal page (similar to `demo-login.html`)
4. **`templates/public_dashboard.html`** - Frontend HTML page
5. **`static/js/public-dashboard.js`** - Frontend JavaScript
6. **`static/css/public-dashboard.css`** - Frontend CSS

### Files to Modify

1. **`utils/auth.py`** - Add `PUBLIC_DASHBOARD_PASSKEY` constant and verification function
2. **`routers/auth/login.py`** - Add `POST /api/auth/public-dashboard/verify` endpoint
3. **`routers/pages.py`** - Add `GET /pub-dash` route with passkey check
4. **`main.py`** - Register `public_dashboard.router`
5. **`routers/api/diagram_generation.py`** - Add activity tracking hook after diagram generation
6. **`.env.example`** - Add `PUBLIC_DASHBOARD_PASSKEY` environment variable

### Dependencies

- **ECharts library** - Download to `static/js/echarts.min.js`
- **China geoJSON** - Download to `static/data/china-geo.json`
- **IP Geolocation Service** - Create `services/ip_geolocation.py` if not exists

---

**Document Version**: 2.0  
**Last Updated**: 2025-01-20  
**Status**: Public Dashboard Design - Real-time Analytics Framework


