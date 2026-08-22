"""National data-center geo helpers — no Beijing fallback for unknown IPs."""

from services.auth.china_geo import (
    is_china_mappable,
    is_localhost_ip,
    is_mappable_client_ip,
    is_non_geo_label,
    is_private_or_reserved_ip,
    lookup_coordinates,
    normalize_city_name,
    normalize_province_name,
)


def test_normalize_province_from_city_in_province_field() -> None:
    """ip2region often puts 成都市 in the province column."""
    assert normalize_province_name("成都市", "成都市") == "四川"
    assert normalize_province_name("武汉市", "武昌区") == "湖北"
    assert normalize_province_name("南京市", "") == "江苏"
    assert normalize_province_name("广东省", "深圳市") == "广东"
    assert normalize_province_name("内蒙古自治区", "") == "内蒙古"


def test_chengdu_coordinates_are_not_beijing() -> None:
    """Unknown-suffix cities used to inherit Beijing lat/lng."""
    coords = lookup_coordinates("成都市", "成都市")
    assert coords is not None
    assert abs(coords["lat"] - 30.6624) < 0.01
    assert abs(coords["lng"] - 104.0633) < 0.01
    beijing = lookup_coordinates("北京", "北京")
    assert beijing is not None
    assert coords != beijing


def test_unknown_location_has_no_coordinates() -> None:
    """Do not invent Beijing when the city/province cannot be resolved."""
    assert lookup_coordinates("加利福尼亚", "洛杉矶") is None
    assert lookup_coordinates("", "") is None


def test_city_name_strips_shi_suffix() -> None:
    """Prefecture labels keep the short form used by coordinate tables."""
    assert normalize_city_name("深圳市") == "深圳"
    assert normalize_city_name("武汉") == "武汉"


def test_private_and_localhost_ips_are_not_mappable() -> None:
    """Docker / CGNAT / loopback leftovers must not become map pins."""
    assert is_localhost_ip("127.0.0.1")
    assert is_private_or_reserved_ip("10.0.0.8")
    assert is_private_or_reserved_ip("192.168.1.20")
    assert is_private_or_reserved_ip("172.18.0.5")
    assert is_private_or_reserved_ip("100.64.1.1")
    assert not is_mappable_client_ip("172.18.0.5")
    assert is_mappable_client_ip("8.8.8.8")


def test_mobile_isp_label_is_not_a_city() -> None:
    """China Mobile CGNAT often yields city=移动 and old code pinned that on Beijing."""
    assert is_non_geo_label("移动")
    assert is_non_geo_label("中国电信")
    assert normalize_city_name("移动") == ""
    assert normalize_province_name("移动", "移动") == ""
    assert lookup_coordinates("移动", "移动") is None
    assert not is_china_mappable(
        {"province": "移动", "city": "移动", "country": "中国", "lat": 39.9042, "lng": 116.4074}
    )


def test_fallback_and_foreign_locations_are_not_mappable() -> None:
    """Beijing fallbacks and foreign countries stay off the China map."""
    assert not is_china_mappable(
        {
            "province": "北京",
            "city": "北京",
            "country": "中国",
            "is_fallback": True,
        }
    )
    assert not is_china_mappable({"province": "", "city": "", "country": "美国"})
    assert is_china_mappable({"province": "广东", "city": "深圳", "country": "中国"})
