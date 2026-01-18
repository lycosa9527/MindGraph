#!/usr/bin/env python3
"""
Quick test script to check if IP 223.104.40.135 is readable.
"""

import asyncio
import sys
import importlib.util
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Direct module import to avoid dependency issues
def import_ip_geolocation():
    """Import ip_geolocation module directly."""
    module_path = project_root / "services" / "ip_geolocation.py"
    spec = importlib.util.spec_from_file_location("ip_geolocation", module_path)
    module = importlib.util.module_from_spec(spec)
    
    # Try to load, but handle import errors gracefully
    try:
        spec.loader.exec_module(module)
        return module
    except ImportError:
        # If redis_client import fails, try to mock it
        import types
        # Create a mock redis_client module
        mock_redis = types.ModuleType('redis_client')
        mock_redis.is_redis_available = lambda: False
        mock_redis.get_redis = lambda: None
        sys.modules['services.redis_client'] = mock_redis
        
        # Try again
        spec.loader.exec_module(module)
        return module


async def test_ip_lookup():
    """Test lookup for IP 223.104.40.135."""
    print("=" * 60)
    print("Testing IP Geolocation Lookup")
    print("=" * 60)
    
    # Import module
    print("\n1. Importing IP geolocation module...")
    try:
        ip_geo = import_ip_geolocation()
        print("   [OK] Module imported successfully")
    except Exception as e:
        print(f"   [FAIL] Failed to import module: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Check if ip2region is available
    print("\n2. Checking ip2region availability...")
    if not ip_geo.IP2REGION_AVAILABLE:
        print("   [FAIL] ip2region not installed")
        print("   Install with: pip install py-ip2region")
        return False
    print("   [OK] ip2region is available")
    
    # Check database files
    print("\n3. Checking database files...")
    if ip_geo.DB_FILE_PATH_V4.exists():
        file_size_mb = ip_geo.DB_FILE_PATH_V4.stat().st_size / 1024 / 1024
        print(f"   [OK] IPv4 database found: {ip_geo.DB_FILE_PATH_V4} ({file_size_mb:.2f} MB)")
    else:
        print(f"   [FAIL] IPv4 database not found: {ip_geo.DB_FILE_PATH_V4}")
        return False
    
    if ip_geo.DB_FILE_PATH_V6.exists():
        file_size_mb = ip_geo.DB_FILE_PATH_V6.stat().st_size / 1024 / 1024
        print(f"   [OK] IPv6 database found: {ip_geo.DB_FILE_PATH_V6} ({file_size_mb:.2f} MB)")
    else:
        print(f"   [WARN] IPv6 database not found: {ip_geo.DB_FILE_PATH_V6} (optional)")
    
    # Initialize service
    print("\n4. Initializing IP Geolocation Service...")
    try:
        service = ip_geo.IPGeolocationService()
        print("   [OK] Service initialized successfully")
    except Exception as e:
        print(f"   [FAIL] Failed to initialize service: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Check if databases are initialized
    print("\n5. Checking database initialization...")
    if service.searcher_v4:
        print("   [OK] IPv4 searcher initialized")
    else:
        print("   [FAIL] IPv4 searcher not initialized")
        return False
    
    if service.searcher_v6:
        print("   [OK] IPv6 searcher initialized")
    else:
        print("   [WARN] IPv6 searcher not initialized (optional)")
    
    # Test the specific IP from logs
    test_ip = "223.104.40.135"
    print(f"\n6. Testing lookup for IP: {test_ip}")
    print("-" * 60)
    
    try:
        location = await service.get_location(test_ip)
        
        if location:
            print("   [OK] Lookup successful!")
            print("\n   Location Details:")
            print(f"     Province: {location.get('province', 'N/A')}")
            print(f"     City: {location.get('city', 'N/A')}")
            print(f"     Country: {location.get('country', 'N/A')}")
            print(f"     Latitude: {location.get('lat', 'N/A')}")
            print(f"     Longitude: {location.get('lng', 'N/A')}")
            print(f"     Is Fallback: {location.get('is_fallback', False)}")
            
            if location.get('is_fallback'):
                print("\n   [WARN] Note: This is a fallback location (IP not found in database)")
                print("   The IP may not be in the database, or the database may need updating.")
            else:
                print("\n   [OK] IP found in database")
            
            return True
        else:
            print("   [FAIL] Lookup returned None")
            return False
            
    except Exception as e:
        print(f"   [FAIL] Lookup failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_ip_lookup())
    print("\n" + "=" * 60)
    if success:
        print("Test completed successfully!")
    else:
        print("Test failed!")
    print("=" * 60)
    sys.exit(0 if success else 1)
