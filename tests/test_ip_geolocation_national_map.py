"""IP geolocation must not invent Beijing for private or failed lookups."""

import pytest

from services.auth.ip_geolocation import IPGeolocationService


class _RegionSearcher:
    """Minimal ip2region searcher stand-in."""

    def __init__(self, region: str) -> None:
        self.region = region

    def search(self, _ip: str) -> str:
        """Return the canned ip2region region string."""
        return self.region


@pytest.mark.asyncio
async def test_get_location_returns_none_for_private_and_unknown() -> None:
    """Private and placeholder IPs never become a Beijing fallback pin."""
    service = IPGeolocationService()
    assert await service.get_location("10.1.2.3") is None
    assert await service.get_location("192.168.0.10") is None
    assert await service.get_location("unknown") is None
    assert await service.get_location("") is None


@pytest.mark.asyncio
async def test_get_location_chengdu_is_not_beijing(monkeypatch: pytest.MonkeyPatch) -> None:
    """City-as-province ip2region rows must resolve to Sichuan, not Beijing."""
    monkeypatch.setattr("services.auth.ip_geolocation.is_redis_available", lambda: False)
    service = IPGeolocationService()
    setattr(service, "searcher_v4", _RegionSearcher("中国|0|四川省|成都市|电信"))
    location = await service.get_location("1.2.4.8")
    assert location is not None
    assert location["province"] == "四川"
    assert location["city"] == "成都"
    assert location["lat"] != 39.9042
    assert location.get("is_fallback") is None


@pytest.mark.asyncio
async def test_get_location_mobile_isp_is_not_beijing(monkeypatch: pytest.MonkeyPatch) -> None:
    """ip2region city=移动 must not become a Beijing flag."""
    monkeypatch.setattr("services.auth.ip_geolocation.is_redis_available", lambda: False)
    service = IPGeolocationService()
    setattr(service, "searcher_v4", _RegionSearcher("中国|0|0|移动|0"))
    location = await service.get_location("223.104.38.38")
    assert location is not None
    assert location["city"] == ""
    assert location["province"] == ""
    assert location.get("lat") is None


@pytest.mark.asyncio
async def test_get_location_foreign_ip_is_not_beijing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Foreign lookups keep their country and do not inherit Beijing coordinates."""
    monkeypatch.setattr("services.auth.ip_geolocation.is_redis_available", lambda: False)
    service = IPGeolocationService()
    setattr(service, "searcher_v4", _RegionSearcher("美国|0|0|0|0"))
    location = await service.get_location("8.8.8.8")
    assert location is not None
    assert location["country"] == "美国"
    assert location["province"] == ""
    assert location.get("lat") is None
