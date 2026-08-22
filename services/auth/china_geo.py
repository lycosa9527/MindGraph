"""
China admin-division helpers for the national data-center map.

Normalizes ip2region province/city strings to ECharts feature names and
looks up coordinates. Unknown or non-China locations must not fall back
to Beijing — that is how every pin used to pile on the capital.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import ipaddress
from typing import Dict, FrozenSet, Mapping, Optional

# ECharts china-geo.json feature names (no 省 / 市 / 自治区 suffix).
PROVINCE_NAMES: FrozenSet[str] = frozenset(
    {
        "北京",
        "天津",
        "上海",
        "重庆",
        "河北",
        "山西",
        "辽宁",
        "吉林",
        "黑龙江",
        "江苏",
        "浙江",
        "安徽",
        "福建",
        "江西",
        "山东",
        "河南",
        "湖北",
        "湖南",
        "广东",
        "海南",
        "四川",
        "贵州",
        "云南",
        "陕西",
        "甘肃",
        "青海",
        "台湾",
        "内蒙古",
        "广西",
        "西藏",
        "宁夏",
        "新疆",
        "香港",
        "澳门",
    }
)

PROVINCE_ALIASES: Dict[str, str] = {
    "北京市": "北京",
    "天津市": "天津",
    "上海市": "上海",
    "重庆市": "重庆",
    "内蒙古自治区": "内蒙古",
    "广西壮族自治区": "广西",
    "西藏自治区": "西藏",
    "宁夏回族自治区": "宁夏",
    "新疆维吾尔自治区": "新疆",
    "香港特别行政区": "香港",
    "澳门特别行政区": "澳门",
    "台湾省": "台湾",
}

# Prefecture-level and common city names → province (with or without 市).
CITY_TO_PROVINCE: Dict[str, str] = {
    "北京": "北京",
    "上海": "上海",
    "天津": "天津",
    "重庆": "重庆",
    "石家庄": "河北",
    "唐山": "河北",
    "秦皇岛": "河北",
    "邯郸": "河北",
    "邢台": "河北",
    "保定": "河北",
    "张家口": "河北",
    "承德": "河北",
    "沧州": "河北",
    "廊坊": "河北",
    "衡水": "河北",
    "太原": "山西",
    "大同": "山西",
    "阳泉": "山西",
    "长治": "山西",
    "晋城": "山西",
    "朔州": "山西",
    "晋中": "山西",
    "运城": "山西",
    "忻州": "山西",
    "临汾": "山西",
    "吕梁": "山西",
    "呼和浩特": "内蒙古",
    "包头": "内蒙古",
    "乌海": "内蒙古",
    "赤峰": "内蒙古",
    "通辽": "内蒙古",
    "鄂尔多斯": "内蒙古",
    "呼伦贝尔": "内蒙古",
    "巴彦淖尔": "内蒙古",
    "乌兰察布": "内蒙古",
    "兴安盟": "内蒙古",
    "锡林郭勒盟": "内蒙古",
    "阿拉善盟": "内蒙古",
    "沈阳": "辽宁",
    "大连": "辽宁",
    "鞍山": "辽宁",
    "抚顺": "辽宁",
    "本溪": "辽宁",
    "丹东": "辽宁",
    "锦州": "辽宁",
    "营口": "辽宁",
    "阜新": "辽宁",
    "辽阳": "辽宁",
    "盘锦": "辽宁",
    "铁岭": "辽宁",
    "朝阳": "辽宁",
    "葫芦岛": "辽宁",
    "长春": "吉林",
    "吉林": "吉林",
    "四平": "吉林",
    "辽源": "吉林",
    "通化": "吉林",
    "白山": "吉林",
    "松原": "吉林",
    "白城": "吉林",
    "延边": "吉林",
    "哈尔滨": "黑龙江",
    "齐齐哈尔": "黑龙江",
    "鸡西": "黑龙江",
    "鹤岗": "黑龙江",
    "双鸭山": "黑龙江",
    "大庆": "黑龙江",
    "伊春": "黑龙江",
    "佳木斯": "黑龙江",
    "七台河": "黑龙江",
    "牡丹江": "黑龙江",
    "黑河": "黑龙江",
    "绥化": "黑龙江",
    "大兴安岭": "黑龙江",
    "南京": "江苏",
    "无锡": "江苏",
    "徐州": "江苏",
    "常州": "江苏",
    "苏州": "江苏",
    "南通": "江苏",
    "连云港": "江苏",
    "淮安": "江苏",
    "盐城": "江苏",
    "扬州": "江苏",
    "镇江": "江苏",
    "泰州": "江苏",
    "宿迁": "江苏",
    "杭州": "浙江",
    "宁波": "浙江",
    "温州": "浙江",
    "嘉兴": "浙江",
    "湖州": "浙江",
    "绍兴": "浙江",
    "金华": "浙江",
    "衢州": "浙江",
    "舟山": "浙江",
    "台州": "浙江",
    "丽水": "浙江",
    "合肥": "安徽",
    "芜湖": "安徽",
    "蚌埠": "安徽",
    "淮南": "安徽",
    "马鞍山": "安徽",
    "淮北": "安徽",
    "铜陵": "安徽",
    "安庆": "安徽",
    "黄山": "安徽",
    "滁州": "安徽",
    "阜阳": "安徽",
    "宿州": "安徽",
    "六安": "安徽",
    "亳州": "安徽",
    "池州": "安徽",
    "宣城": "安徽",
    "福州": "福建",
    "厦门": "福建",
    "莆田": "福建",
    "三明": "福建",
    "泉州": "福建",
    "漳州": "福建",
    "南平": "福建",
    "龙岩": "福建",
    "宁德": "福建",
    "南昌": "江西",
    "景德镇": "江西",
    "萍乡": "江西",
    "九江": "江西",
    "新余": "江西",
    "鹰潭": "江西",
    "赣州": "江西",
    "吉安": "江西",
    "宜春": "江西",
    "抚州": "江西",
    "上饶": "江西",
    "济南": "山东",
    "青岛": "山东",
    "淄博": "山东",
    "枣庄": "山东",
    "东营": "山东",
    "烟台": "山东",
    "潍坊": "山东",
    "济宁": "山东",
    "泰安": "山东",
    "威海": "山东",
    "日照": "山东",
    "临沂": "山东",
    "德州": "山东",
    "聊城": "山东",
    "滨州": "山东",
    "菏泽": "山东",
    "郑州": "河南",
    "开封": "河南",
    "洛阳": "河南",
    "平顶山": "河南",
    "安阳": "河南",
    "鹤壁": "河南",
    "新乡": "河南",
    "焦作": "河南",
    "濮阳": "河南",
    "许昌": "河南",
    "漯河": "河南",
    "三门峡": "河南",
    "南阳": "河南",
    "商丘": "河南",
    "信阳": "河南",
    "周口": "河南",
    "驻马店": "河南",
    "济源": "河南",
    "武汉": "湖北",
    "黄石": "湖北",
    "十堰": "湖北",
    "宜昌": "湖北",
    "襄阳": "湖北",
    "鄂州": "湖北",
    "荆门": "湖北",
    "孝感": "湖北",
    "荆州": "湖北",
    "黄冈": "湖北",
    "咸宁": "湖北",
    "随州": "湖北",
    "恩施": "湖北",
    "仙桃": "湖北",
    "潜江": "湖北",
    "天门": "湖北",
    "神农架": "湖北",
    "长沙": "湖南",
    "株洲": "湖南",
    "湘潭": "湖南",
    "衡阳": "湖南",
    "邵阳": "湖南",
    "岳阳": "湖南",
    "常德": "湖南",
    "张家界": "湖南",
    "益阳": "湖南",
    "郴州": "湖南",
    "永州": "湖南",
    "怀化": "湖南",
    "娄底": "湖南",
    "湘西": "湖南",
    "广州": "广东",
    "韶关": "广东",
    "深圳": "广东",
    "珠海": "广东",
    "汕头": "广东",
    "佛山": "广东",
    "江门": "广东",
    "湛江": "广东",
    "茂名": "广东",
    "肇庆": "广东",
    "惠州": "广东",
    "梅州": "广东",
    "汕尾": "广东",
    "河源": "广东",
    "阳江": "广东",
    "清远": "广东",
    "东莞": "广东",
    "中山": "广东",
    "潮州": "广东",
    "揭阳": "广东",
    "云浮": "广东",
    "南宁": "广西",
    "柳州": "广西",
    "桂林": "广西",
    "梧州": "广西",
    "北海": "广西",
    "防城港": "广西",
    "钦州": "广西",
    "贵港": "广西",
    "玉林": "广西",
    "百色": "广西",
    "贺州": "广西",
    "河池": "广西",
    "来宾": "广西",
    "崇左": "广西",
    "海口": "海南",
    "三亚": "海南",
    "三沙": "海南",
    "儋州": "海南",
    "成都": "四川",
    "自贡": "四川",
    "攀枝花": "四川",
    "泸州": "四川",
    "德阳": "四川",
    "绵阳": "四川",
    "广元": "四川",
    "遂宁": "四川",
    "内江": "四川",
    "乐山": "四川",
    "南充": "四川",
    "眉山": "四川",
    "宜宾": "四川",
    "广安": "四川",
    "达州": "四川",
    "雅安": "四川",
    "巴中": "四川",
    "资阳": "四川",
    "阿坝": "四川",
    "甘孜": "四川",
    "凉山": "四川",
    "贵阳": "贵州",
    "六盘水": "贵州",
    "遵义": "贵州",
    "安顺": "贵州",
    "毕节": "贵州",
    "铜仁": "贵州",
    "黔西南": "贵州",
    "黔东南": "贵州",
    "黔南": "贵州",
    "昆明": "云南",
    "曲靖": "云南",
    "玉溪": "云南",
    "保山": "云南",
    "昭通": "云南",
    "丽江": "云南",
    "普洱": "云南",
    "临沧": "云南",
    "楚雄": "云南",
    "红河": "云南",
    "文山": "云南",
    "西双版纳": "云南",
    "大理": "云南",
    "德宏": "云南",
    "怒江": "云南",
    "迪庆": "云南",
    "拉萨": "西藏",
    "日喀则": "西藏",
    "昌都": "西藏",
    "林芝": "西藏",
    "山南": "西藏",
    "那曲": "西藏",
    "阿里": "西藏",
    "西安": "陕西",
    "铜川": "陕西",
    "宝鸡": "陕西",
    "咸阳": "陕西",
    "渭南": "陕西",
    "延安": "陕西",
    "汉中": "陕西",
    "榆林": "陕西",
    "安康": "陕西",
    "商洛": "陕西",
    "兰州": "甘肃",
    "嘉峪关": "甘肃",
    "金昌": "甘肃",
    "白银": "甘肃",
    "天水": "甘肃",
    "武威": "甘肃",
    "张掖": "甘肃",
    "平凉": "甘肃",
    "酒泉": "甘肃",
    "庆阳": "甘肃",
    "定西": "甘肃",
    "陇南": "甘肃",
    "临夏": "甘肃",
    "甘南": "甘肃",
    "西宁": "青海",
    "海东": "青海",
    "海北": "青海",
    "黄南": "青海",
    "海南州": "青海",
    "果洛": "青海",
    "玉树": "青海",
    "海西": "青海",
    "银川": "宁夏",
    "石嘴山": "宁夏",
    "吴忠": "宁夏",
    "固原": "宁夏",
    "中卫": "宁夏",
    "乌鲁木齐": "新疆",
    "克拉玛依": "新疆",
    "吐鲁番": "新疆",
    "哈密": "新疆",
    "昌吉": "新疆",
    "博尔塔拉": "新疆",
    "巴音郭楞": "新疆",
    "阿克苏": "新疆",
    "克孜勒苏": "新疆",
    "喀什": "新疆",
    "和田": "新疆",
    "伊犁": "新疆",
    "塔城": "新疆",
    "阿勒泰": "新疆",
    "石河子": "新疆",
    "香港": "香港",
    "澳门": "澳门",
    "台北": "台湾",
    "高雄": "台湾",
    "台中": "台湾",
    "台南": "台湾",
}

PROVINCE_COORDINATES: Dict[str, Dict[str, float]] = {
    "北京": {"lat": 39.9042, "lng": 116.4074},
    "上海": {"lat": 31.2304, "lng": 121.4737},
    "天津": {"lat": 39.3434, "lng": 117.3616},
    "重庆": {"lat": 29.5630, "lng": 106.5516},
    "广东": {"lat": 23.1291, "lng": 113.2644},
    "江苏": {"lat": 32.0603, "lng": 118.7969},
    "浙江": {"lat": 30.2741, "lng": 120.1551},
    "山东": {"lat": 36.6512, "lng": 117.1201},
    "四川": {"lat": 30.6624, "lng": 104.0633},
    "湖北": {"lat": 30.5928, "lng": 114.3055},
    "河南": {"lat": 34.7466, "lng": 113.6254},
    "湖南": {"lat": 28.2278, "lng": 112.9388},
    "河北": {"lat": 38.0428, "lng": 114.5149},
    "安徽": {"lat": 31.8206, "lng": 117.2272},
    "福建": {"lat": 26.0745, "lng": 119.2965},
    "辽宁": {"lat": 41.8057, "lng": 123.4315},
    "陕西": {"lat": 34.3416, "lng": 108.9398},
    "江西": {"lat": 28.6820, "lng": 115.8579},
    "云南": {"lat": 25.0389, "lng": 102.7183},
    "广西": {"lat": 22.8170, "lng": 108.3669},
    "山西": {"lat": 37.8706, "lng": 112.5489},
    "内蒙古": {"lat": 40.8414, "lng": 111.7519},
    "黑龙江": {"lat": 45.7731, "lng": 126.6849},
    "吉林": {"lat": 43.8171, "lng": 125.3235},
    "贵州": {"lat": 26.6470, "lng": 106.6302},
    "新疆": {"lat": 43.8256, "lng": 87.6168},
    "甘肃": {"lat": 36.0611, "lng": 103.8343},
    "海南": {"lat": 20.0444, "lng": 110.1999},
    "宁夏": {"lat": 38.4872, "lng": 106.2309},
    "青海": {"lat": 36.6171, "lng": 101.7782},
    "西藏": {"lat": 29.6626, "lng": 91.1160},
    "台湾": {"lat": 25.0330, "lng": 121.5654},
    "香港": {"lat": 22.3193, "lng": 114.1694},
    "澳门": {"lat": 22.1987, "lng": 113.5439},
}

CITY_COORDINATES: Dict[str, Dict[str, float]] = {
    "深圳": {"lat": 22.5431, "lng": 114.0579},
    "广州": {"lat": 23.1291, "lng": 113.2644},
    "杭州": {"lat": 30.2741, "lng": 120.1551},
    "南京": {"lat": 32.0603, "lng": 118.7969},
    "成都": {"lat": 30.6624, "lng": 104.0633},
    "武汉": {"lat": 30.5928, "lng": 114.3055},
    "西安": {"lat": 34.3416, "lng": 108.9398},
    "苏州": {"lat": 31.2989, "lng": 120.5853},
    "郑州": {"lat": 34.7466, "lng": 113.6254},
    "长沙": {"lat": 28.2278, "lng": 112.9388},
    "青岛": {"lat": 36.0671, "lng": 120.3826},
    "厦门": {"lat": 24.4798, "lng": 118.0894},
    "宁波": {"lat": 29.8683, "lng": 121.5440},
    "东莞": {"lat": 23.0207, "lng": 113.7518},
    "佛山": {"lat": 23.0215, "lng": 113.1214},
    "沈阳": {"lat": 41.8057, "lng": 123.4315},
    "大连": {"lat": 38.9140, "lng": 121.6147},
    "哈尔滨": {"lat": 45.7731, "lng": 126.6849},
    "长春": {"lat": 43.8171, "lng": 125.3235},
    "昆明": {"lat": 25.0389, "lng": 102.7183},
    "福州": {"lat": 26.0745, "lng": 119.2965},
    "合肥": {"lat": 31.8206, "lng": 117.2272},
    "济南": {"lat": 36.6512, "lng": 117.1201},
    "石家庄": {"lat": 38.0428, "lng": 114.5149},
    "南昌": {"lat": 28.6820, "lng": 115.8579},
    "太原": {"lat": 37.8706, "lng": 112.5489},
    "南宁": {"lat": 22.8170, "lng": 108.3669},
    "贵阳": {"lat": 26.6470, "lng": 106.6302},
    "乌鲁木齐": {"lat": 43.8256, "lng": 87.6168},
    "兰州": {"lat": 36.0611, "lng": 103.8343},
    "海口": {"lat": 20.0444, "lng": 110.1999},
    "银川": {"lat": 38.4872, "lng": 106.2309},
    "西宁": {"lat": 36.6171, "lng": 101.7782},
    "拉萨": {"lat": 29.6626, "lng": 91.1160},
    "呼和浩特": {"lat": 40.8414, "lng": 111.7519},
}

_ADMIN_SUFFIXES = (
    "特别行政区",
    "维吾尔自治区",
    "壮族自治区",
    "回族自治区",
    "自治区",
    "自治州",
    "地区",
    "盟",
    "省",
    "市",
)

_CHINA_COUNTRY_NAMES = frozenset({"中国", "中华人民共和国", "CN", "China", "CHN"})
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")
# ip2region often puts the ISP in the city/province slot for mobile CGNAT
# (the test-server log: city=移动 at Beijing 39.9042,116.4074).
_NON_GEO_LABELS = frozenset(
    {
        "移动",
        "电信",
        "联通",
        "铁通",
        "鹏博士",
        "教育网",
        "科技网",
        "广电",
        "广电网",
        "长城",
        "长城宽带",
        "方正宽带",
        "阿里云",
        "腾讯云",
        "华为云",
        "内网IP",
        "本机地址",
        "CZ88",
        "0",
    }
)
_NON_GEO_PREFIXES = ("中国移动", "中国电信", "中国联通", "中国铁通")


def is_non_geo_label(name: str) -> bool:
    """True for ISP / cloud / intranet tokens that are not a city or province."""
    cleaned = (name or "").strip()
    if not cleaned or cleaned in _NON_GEO_LABELS:
        return True
    return cleaned.startswith(_NON_GEO_PREFIXES)


def strip_admin_suffix(name: str) -> str:
    """Strip 省/市/自治区-style suffixes used by ip2region."""
    cleaned = (name or "").strip()
    if not cleaned:
        return ""
    for suffix in _ADMIN_SUFFIXES:
        if cleaned.endswith(suffix) and len(cleaned) > len(suffix):
            return cleaned[: -len(suffix)]
    return cleaned


def _lookup_city_province(city: str) -> Optional[str]:
    """Resolve a city label (with or without 市) to a province name."""
    if not city:
        return None
    if city in CITY_TO_PROVINCE:
        return CITY_TO_PROVINCE[city]
    stripped = strip_admin_suffix(city)
    if stripped in CITY_TO_PROVINCE:
        return CITY_TO_PROVINCE[stripped]
    with_shi = f"{stripped}市"
    if with_shi in CITY_TO_PROVINCE:
        return CITY_TO_PROVINCE[with_shi]
    return None


def normalize_province_name(province: str, city: str = "") -> str:
    """Normalize a province (or city-in-province-field) to an ECharts name."""
    raw = (province or "").strip()
    if is_non_geo_label(raw):
        raw = ""
    if not raw:
        city_province = _lookup_city_province(city)
        return city_province or ""
    if raw in PROVINCE_NAMES:
        return raw
    if raw in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[raw]
    stripped = strip_admin_suffix(raw)
    if stripped in PROVINCE_NAMES:
        return stripped
    if stripped in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[stripped]
    city_from_province = _lookup_city_province(raw) or _lookup_city_province(stripped)
    if city_from_province:
        return city_from_province
    return _lookup_city_province(city) or ""


def normalize_city_name(city: str) -> str:
    """Normalize a city label for coordinate lookup and map flags."""
    raw = (city or "").strip()
    if is_non_geo_label(raw):
        return ""
    if not raw:
        return ""
    stripped = strip_admin_suffix(raw)
    if stripped in CITY_COORDINATES or stripped in CITY_TO_PROVINCE:
        return stripped
    return stripped or raw


def lookup_coordinates(province: str, city: str = "") -> Optional[Dict[str, float]]:
    """Return lat/lng for a normalized city or province, or None if unknown."""
    city_name = normalize_city_name(city)
    if city_name in CITY_COORDINATES:
        return dict(CITY_COORDINATES[city_name])
    province_name = normalize_province_name(province, city_name)
    if province_name in PROVINCE_COORDINATES:
        return dict(PROVINCE_COORDINATES[province_name])
    return None


def is_china_country(country: str) -> bool:
    """True when the ip2region country field is China."""
    return (country or "").strip() in _CHINA_COUNTRY_NAMES


def is_china_mappable(location: Mapping[str, object]) -> bool:
    """True when a lookup can be plotted on the China map (no Beijing fake)."""
    if location.get("is_fallback") or location.get("is_debug_localhost"):
        return False
    country = str(location.get("country") or "")
    if country and not is_china_country(country):
        return False
    province = str(location.get("province") or "")
    return bool(province) and province in PROVINCE_NAMES


def is_localhost_ip(ip_address: str) -> bool:
    """True for loopback / placeholder local addresses."""
    if not ip_address:
        return False
    ip_lower = ip_address.lower().strip()
    if ip_lower in ("localhost", "::1", "::", "0.0.0.0"):
        return True
    if ip_lower.startswith("127."):
        return True
    return ip_lower.startswith("::ffff:127.")


def is_unknown_ip(ip_address: str) -> bool:
    """True when the activity tracker stored no usable client IP."""
    return not ip_address or ip_address.strip().lower() in {"unknown", "none"}


def is_private_or_reserved_ip(ip_address: str) -> bool:
    """True for RFC1918, loopback, link-local, CGNAT, and other non-public IPs."""
    if is_unknown_ip(ip_address) or is_localhost_ip(ip_address):
        return True
    candidate = ip_address.strip()
    if candidate.startswith("::ffff:"):
        candidate = candidate[7:]
    try:
        parsed = ipaddress.ip_address(candidate)
    except ValueError:
        return True
    if parsed.is_private or parsed.is_loopback or parsed.is_link_local:
        return True
    if parsed.is_multicast or parsed.is_unspecified:
        return True
    return parsed.version == 4 and parsed in _CGNAT_NETWORK


def is_mappable_client_ip(ip_address: str) -> bool:
    """Public unicast IPs only — private/proxy leftovers must not become map pins."""
    return not is_unknown_ip(ip_address) and not is_private_or_reserved_ip(ip_address)
