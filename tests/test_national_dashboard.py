"""Pure helpers for the national China-map dashboard."""

from services.monitoring.national_dashboard import (
    aggregate_map_locations,
    collect_unique_public_ips,
    count_connected_users,
    merge_city_flags,
)


def test_aggregate_skips_beijing_fallback_and_private_failures() -> None:
    """Failed lookups must not become a Beijing heat blob."""
    map_data, city_coords, _locations = aggregate_map_locations(
        [
            (
                "1.2.4.8",
                {
                    "province": "北京",
                    "city": "北京",
                    "lat": 39.9042,
                    "lng": 116.4074,
                    "country": "中国",
                    "is_fallback": True,
                },
                4,
            ),
            (
                "114.114.114.114",
                {
                    "province": "广东",
                    "city": "深圳",
                    "lat": 22.5431,
                    "lng": 114.0579,
                    "country": "中国",
                },
                2,
            ),
            ("10.0.0.5", None, 3),
        ]
    )
    names = {item["name"] for item in map_data}
    assert names == {"广东"}
    assert "北京" not in names
    assert "深圳" in city_coords
    assert "北京" not in city_coords


def test_collect_unique_public_ips_drops_docker_and_loopback() -> None:
    """Only public client IPs are geolocated; private peers still count as online."""
    users = [
        {"ip_address": "127.0.0.1"},
        {"ip_address": "172.18.0.5"},
        {"ip_address": "unknown"},
        {"ip_address": "8.8.8.8"},
        {"ip_address": "8.8.8.8"},
    ]
    ips, grouped = collect_unique_public_ips(users)
    assert ips == ["8.8.8.8"]
    assert len(grouped["8.8.8.8"]) == 2
    assert count_connected_users(users) == 3


def test_merge_city_flags_keeps_current_pins() -> None:
    """Active public-IP cities become scatter pins with real coordinates."""
    flags = merge_city_flags(
        [],
        {"深圳": [114.0579, 22.5431]},
        {"深圳": {"city": "深圳", "province": "广东", "lat": 22.5431, "lng": 114.0579}},
    )
    assert len(flags) == 1
    assert flags[0]["name"] == "深圳"
    assert flags[0]["value"] == [114.0579, 22.5431]


def test_merge_city_flags_drops_stale_isp_beijing_pins() -> None:
    """Old workers cached city=移动 at Beijing; those flags must not survive merge."""
    flags = merge_city_flags(
        [
            {
                "city": "移动",
                "timestamp": "2026-08-23T00:00:00+00:00",
                "lat": 39.9042,
                "lng": 116.4074,
            }
        ],
        {},
        {},
    )
    assert not flags
