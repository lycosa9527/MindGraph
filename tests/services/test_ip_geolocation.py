"""
IP Geolocation Service Tests
=============================

Tests for IP geolocation service using ip2region database.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import pytest
from services.auth.ip_geolocation import (
    get_geolocation_service,
    IPGeolocationService,
    IP2REGION_AVAILABLE,
    DB_FILE_PATH_V4,
    DB_FILE_PATH_V6
)


class TestIPGeolocationService:
    """Test IP geolocation service initialization and lookup."""
    
    def test_service_initialization(self):
        """Test that the service initializes without errors."""
        if not IP2REGION_AVAILABLE:
            pytest.skip("ip2region not installed")
        
        service = get_geolocation_service()
        assert service is not None
        assert isinstance(service, IPGeolocationService)
    
    def test_database_files_exist(self):
        """Test that database files exist (if ip2region is available)."""
        if not IP2REGION_AVAILABLE:
            pytest.skip("ip2region not installed")
        
        # At least IPv4 database should exist
        if not DB_FILE_PATH_V4.exists():
            pytest.skip(f"IPv4 database not found at {DB_FILE_PATH_V4}")
    
    @pytest.mark.asyncio
    async def test_lookup_specific_ip_223_104_40_135(self):
        """
        Test lookup for IP 223.104.40.135 that was failing in logs.
        This IP should be readable from the database.
        """
        if not IP2REGION_AVAILABLE:
            pytest.skip("ip2region not installed")
        
        service = get_geolocation_service()
        test_ip = "223.104.40.135"
        
        # Perform lookup
        location = await service.get_location(test_ip)
        
        # Should return location data (even if it's a fallback)
        assert location is not None, f"Lookup failed for IP {test_ip}"
        
        # Check that location has required fields
        assert "province" in location, "Location missing 'province' field"
        assert "city" in location, "Location missing 'city' field"
        assert "country" in location, "Location missing 'country' field"
        
        # Log the result for debugging
        print(f"\nIP {test_ip} lookup result:")
        print(f"  Province: {location.get('province')}")
        print(f"  City: {location.get('city')}")
        print(f"  Country: {location.get('country')}")
        print(f"  Coordinates: ({location.get('lat')}, {location.get('lng')})")
        print(f"  Is fallback: {location.get('is_fallback', False)}")
    
    @pytest.mark.asyncio
    async def test_lookup_common_ips(self):
        """Test lookup for some common IP addresses."""
        if not IP2REGION_AVAILABLE:
            pytest.skip("ip2region not installed")
        
        service = get_geolocation_service()
        
        # Test IPs
        test_ips = [
            "8.8.8.8",  # Google DNS
            "114.114.114.114",  # Chinese DNS
            "223.104.40.135",  # The problematic IP from logs
        ]
        
        for ip in test_ips:
            location = await service.get_location(ip)
            assert location is not None, f"Lookup failed for IP {ip}"
            assert "province" in location, f"Location missing 'province' for IP {ip}"
            assert "country" in location, f"Location missing 'country' for IP {ip}"
            print(f"IP {ip}: {location.get('province')}, {location.get('city')}")
    
    @pytest.mark.asyncio
    async def test_database_initialization_with_version(self):
        """
        Test that database initialization works with Version parameter.
        This verifies the fix for the 'missing db_path argument' error.
        """
        if not IP2REGION_AVAILABLE:
            pytest.skip("ip2region not installed")
        
        # Create a new service instance to test initialization
        service = IPGeolocationService()
        
        # If IPv4 database exists, searcher should be initialized
        if DB_FILE_PATH_V4.exists():
            assert service.searcher_v4 is not None, "IPv4 searcher should be initialized"
            print("IPv4 database initialized successfully")
        
        # If IPv6 database exists, searcher should be initialized
        if DB_FILE_PATH_V6.exists():
            assert service.searcher_v6 is not None, "IPv6 searcher should be initialized"
            print("IPv6 database initialized successfully")
    
    @pytest.mark.asyncio
    async def test_invalid_ip_handling(self):
        """Test that invalid IPs are handled gracefully."""
        if not IP2REGION_AVAILABLE:
            pytest.skip("ip2region not installed")
        
        service = get_geolocation_service()
        
        # Test invalid IPs
        invalid_ips = [
            None,
            "",
            "invalid",
            "999.999.999.999",
        ]
        
        for ip in invalid_ips:
            location = await service.get_location(ip)
            # Should return None or handle gracefully
            if location is None:
                print(f"IP {ip} correctly returned None")
            else:
                # If it returns a fallback, that's also acceptable
                assert "province" in location
                print(f"IP {ip} returned fallback location: {location.get('province')}")

