# IP2Region Database Setup

## Overview
The IP geolocation service uses a local database (ip2region) for IP lookups. No external API calls are made.

## Installation Options

### Option 1: Download Pre-built Database (Recommended)

1. Visit the ip2region repository: https://github.com/lionsoul2014/ip2region
2. Download the `ip2region.db` file from the `data/` directory
3. Place it in: `data/ip2region.db`

### Option 2: Build from Source

If the pre-built database is not available:

1. Clone the repository:
   ```bash
   git clone https://github.com/lionsoul2014/ip2region.git
   cd ip2region
   ```

2. Build the database:
   ```bash
   # Follow the repository's build instructions
   # The database file will be generated in the data/ directory
   ```

3. Copy the database file:
   ```bash
   cp data/ip2region.db /path/to/MG/data/ip2region.db
   ```

### Option 3: Use MaxMind GeoIP2 (Alternative)

If ip2region is not available, you can use MaxMind GeoIP2:

1. Install the package:
   ```bash
   pip install geoip2
   ```

2. Download the GeoLite2 database from MaxMind (requires free account)

3. Update `services/ip_geolocation.py` to use MaxMind instead

## Database Updates

The IP geolocation database should be updated monthly for accuracy:

1. Download the latest database file
2. Replace `data/ip2region.db`
3. The service will automatically reload the new database on next restart

## Verification

After setting up the database, verify it works:

```python
from services.ip_geolocation import get_geolocation_service

service = get_geolocation_service()
location = await service.get_location("8.8.8.8")
print(location)  # Should return location data
```

