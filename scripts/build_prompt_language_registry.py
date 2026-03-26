"""
Emit data/prompt_language_registry.json — single source for prompt output languages.

Run from repo root:
  python scripts/build_prompt_language_registry.py

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_OUT = _REPO / "data" / "prompt_language_registry.json"

# (code, englishName, nativeLabel, chinese_keywords_for_search)
# Codes: ISO 639-1 / BCP-47 / ISO 639-3 where needed; max length 32 for DB.
_RAW: list[tuple[str, str, str, list[str]]] = [
    ("zh", "Simplified Chinese", "简体中文", ["简体", "中文"]),
    ("zh-hant", "Traditional Chinese", "繁體中文", ["繁体", "繁體"]),
    ("en", "English", "English", ["英语"]),
    ("fr", "French", "Français", ["法语", "法文"]),
    ("es", "Spanish", "Español", ["西班牙语", "西语"]),
    ("ar", "Arabic (Modern Standard)", "العربية", ["阿拉伯语", "阿语"]),
    ("ru", "Russian", "Русский", ["俄语"]),
    ("pt", "Portuguese", "Português", ["葡萄牙语"]),
    ("de", "German", "Deutsch", ["德语", "德文"]),
    ("it", "Italian", "Italiano", ["意大利语"]),
    ("nl", "Dutch", "Nederlands", ["荷兰语"]),
    ("da", "Danish", "Dansk", ["丹麦语"]),
    ("ga", "Irish", "Gaeilge", ["爱尔兰语"]),
    ("cy", "Welsh", "Cymraeg", ["威尔士语"]),
    ("fi", "Finnish", "Suomi", ["芬兰语"]),
    ("is", "Icelandic", "Íslenska", ["冰岛语"]),
    ("sv", "Swedish", "Svenska", ["瑞典语"]),
    ("nn", "Norwegian Nynorsk", "Nynorsk", ["新挪威语", "尼诺斯克"]),
    ("nb", "Norwegian Bokmål", "Bokmål", ["书面挪威语", "布克莫尔"]),
    ("no", "Norwegian", "Norsk", ["挪威语"]),
    ("ja", "Japanese", "日本語", ["日语", "日文"]),
    ("ko", "Korean", "한국어", ["朝鲜语", "韩语", "韩文"]),
    ("vi", "Vietnamese", "Tiếng Việt", ["越南语"]),
    ("th", "Thai", "ไทย", ["泰语", "泰文"]),
    ("id", "Indonesian", "Bahasa Indonesia", ["印度尼西亚语", "印尼语"]),
    ("ms", "Malay", "Bahasa Melayu", ["马来语"]),
    ("my", "Burmese", "မြန်မာ", ["缅甸语"]),
    ("tl", "Tagalog", "Tagalog", ["他加禄语", "菲律宾语"]),
    ("km", "Khmer", "ខ្មែរ", ["高棉语", "柬埔寨"]),
    ("lo", "Lao", "ລາວ", ["老挝语"]),
    ("hi", "Hindi", "हिन्दी", ["印地语"]),
    ("bn", "Bengali", "বাংলা", ["孟加拉语"]),
    ("ur", "Urdu", "اردو", ["乌尔都语"]),
    ("ne", "Nepali", "नेपाली", ["尼泊尔语"]),
    ("he", "Hebrew", "עברית", ["希伯来语"]),
    ("tr", "Turkish", "Türkçe", ["土耳其语"]),
    ("fa", "Persian (Farsi)", "فارسی", ["波斯语", "伊朗"]),
    ("pl", "Polish", "Polski", ["波兰语"]),
    ("uk", "Ukrainian", "Українська", ["乌克兰语"]),
    ("cs", "Czech", "Čeština", ["捷克语"]),
    ("ro", "Romanian", "Română", ["罗马尼亚语"]),
    ("bg", "Bulgarian", "Български", ["保加利亚语"]),
    ("sk", "Slovak", "Slovenčina", ["斯洛伐克语"]),
    ("hu", "Hungarian", "Magyar", ["匈牙利语"]),
    ("sl", "Slovenian", "Slovenščina", ["斯洛文尼亚语"]),
    ("lv", "Latvian", "Latviešu", ["拉脱维亚语"]),
    ("et", "Estonian", "Eesti", ["爱沙尼亚语"]),
    ("lt", "Lithuanian", "Lietuvių", ["立陶宛语"]),
    ("be", "Belarusian", "Беларуская", ["白俄罗斯语"]),
    ("el", "Greek", "Ελληνικά", ["希腊语"]),
    ("hr", "Croatian", "Hrvatski", ["克罗地亚语"]),
    ("mk", "Macedonian", "Македонски", ["马其顿语", "北马其顿"]),
    ("mt", "Maltese", "Malti", ["马耳他语"]),
    ("sr", "Serbian", "Српски", ["塞尔维亚语"]),
    ("bs", "Bosnian", "Bosanski", ["波斯尼亚语"]),
    ("ka", "Georgian", "ქართული", ["格鲁吉亚语"]),
    ("hy", "Armenian", "Հայերեն", ["亚美尼亚语"]),
    ("az", "Azerbaijani (North)", "Azərbaycan", ["阿塞拜疆语", "北阿塞拜疆"]),
    ("kk", "Kazakh", "Қазақша", ["哈萨克语"]),
    ("uz", "Uzbek (Northern)", "Oʻzbek", ["乌兹别克语", "北乌兹别克"]),
    ("tg", "Tajik", "Тоҷикӣ", ["塔吉克语"]),
    ("sw", "Swahili", "Kiswahili", ["斯瓦西里语", "斯瓦希里"]),
    ("af", "Afrikaans", "Afrikaans", ["南非语"]),
    ("yue", "Cantonese", "粵語", ["粤语", "广东话", "香港"]),
    ("lb", "Luxembourgish", "Lëtzebuergesch", ["卢森堡语"]),
    ("li", "Limburgish", "Limburgs", ["林堡语"]),
    ("ca", "Catalan", "Català", ["加泰罗尼亚语"]),
    ("gl", "Galician", "Galego", ["加利西亚语"]),
    ("ast", "Asturian", "Asturianu", ["阿斯图里亚斯语"]),
    ("eu", "Basque", "Euskara", ["巴斯克语"]),
    ("oc", "Occitan", "Occitan", ["奥克语"]),
    ("vec", "Venetian", "Vèneto", ["威尼斯语"]),
    ("sc", "Sardinian", "Sardu", ["撒丁语"]),
    ("scn", "Sicilian", "Sicilianu", ["西西里语"]),
    ("fur", "Friulian", "Furlan", ["弗留利语"]),
    ("lmo", "Lombard", "Lombard", ["隆巴底语", "伦巴第"]),
    ("lij", "Ligurian", "Ligure", ["利古里亚语"]),
    ("fo", "Faroese", "Føroyskt", ["法罗语"]),
    ("sq", "Albanian (Tosk)", "Shqip", ["阿尔巴尼亚语", "托斯克"]),
    ("szl", "Silesian", "Ślōnski", ["西里西亚语"]),
    ("ba", "Bashkir", "Башҡортса", ["巴什基尔语"]),
    ("tt", "Tatar", "Татар", ["鞑靼语"]),
    ("acm", "Arabic (Mesopotamian)", "عراقي", ["美索不达米亚阿拉伯语", "伊拉克"]),
    ("ars", "Arabic (Najdi)", "نجدي", ["内志阿拉伯语", "沙特"]),
    ("arz", "Arabic (Egyptian)", "مصري", ["埃及阿拉伯语"]),
    ("apc", "Arabic (Levantine)", "شامي", ["黎凡特阿拉伯语", "叙利亚", "黎巴嫩"]),
    ("acq", "Arabic (Ta'izzi-Adeni)", "عدني", ["闪米特阿拉伯语", "也门"]),
    ("prs", "Dari", "دری", ["达里语", "阿富汗"]),
    ("aeb", "Arabic (Tunisian)", "تونسي", ["突尼斯阿拉伯语"]),
    ("ary", "Arabic (Moroccan)", "دارجة", ["摩洛哥阿拉伯语"]),
    ("kea", "Kabuverdianu", "Kabuverdianu", ["克里奥尔语", "佛得角"]),
    ("tpi", "Tok Pisin", "Tok Pisin", ["托克皮辛语", "巴布亚"]),
    ("ydd", "Yiddish (Eastern)", "יידיש", ["意第绪", "犹太"]),
    ("sd", "Sindhi", "سنڌي", ["信德语", "信德"]),
    ("si", "Sinhala", "සිංහල", ["僧伽罗语", "斯里兰卡"]),
    ("te", "Telugu", "తెలుగు", ["泰卢固语"]),
    ("pa", "Punjabi (Gurmukhi)", "ਪੰਜਾਬੀ", ["旁遮普语"]),
    ("ta", "Tamil", "தமிழ்", ["泰米尔语"]),
    ("gu", "Gujarati", "ગુજરાતી", ["古吉拉特语"]),
    ("ml", "Malayalam", "മലയാളം", ["马拉雅拉姆语"]),
    ("mr", "Marathi", "मराठी", ["马拉地语"]),
    ("mag", "Magahi", "मगही", ["马加拉语", "马加希"]),
    ("or", "Odia (Oriya)", "ଓଡ଼ିଆ", ["奥里亚语", "奥里亚"]),
    ("awa", "Awadhi", "अवधी", ["阿瓦德语"]),
    ("mai", "Maithili", "मैथिली", ["迈蒂利语"]),
    ("as", "Assamese", "অসমীয়া", ["阿萨姆语"]),
    ("hne", "Chhattisgarhi", "छत्तीसगढ़ी", ["切蒂斯格尔语"]),
    ("bho", "Bhojpuri", "भोजपुरी", ["比哈尔语", "博杰普尔"]),
    ("min", "Minangkabau", "Minangkabau", ["米南加保语"]),
    ("ban", "Balinese", "Basa Bali", ["巴厘语"]),
    ("jv", "Javanese", "Basa Jawa", ["爪哇语"]),
    ("bjn", "Banjar", "Banjar", ["班章语"]),
    ("sun", "Sundanese", "Basa Sunda", ["巽他语"]),
    ("ceb", "Cebuano", "Cebuano", ["宿务语"]),
    ("pag", "Pangasinan", "Pangasinan", ["邦阿西楠语"]),
    ("ilo", "Iloko", "Iloko", ["伊洛卡诺语"]),
    ("war", "Waray (Philippines)", "Waray", ["瓦莱语", "菲律宾"]),
    ("ht", "Haitian Creole", "Kreyòl ayisyen", ["海地语", "海地克里奥尔"]),
    ("pap", "Papiamento", "Papiamentu", ["帕皮阿门托语", "加勒比"]),
    ("br", "Breton", "Brezhoneg", ["布列塔尼语"]),
    ("gd", "Scottish Gaelic", "Gàidhlig", ["苏格兰盖尔语"]),
    ("gv", "Manx", "Gaelg", ["马恩语"]),
    ("kw", "Cornish", "Kernewek", ["康沃尔语"]),
    ("fy", "Western Frisian", "Frysk", ["西弗里西亚语", "弗里西"]),
    ("kn", "Kannada", "ಕನ್ನಡ", ["卡纳达语"]),
    ("kok", "Konkani", "कोंकणी", ["孔卡尼语"]),
    ("mni", "Manipuri", "ꯃꯤꯇꯩ ꯂꯣꯟ", ["曼尼普尔语"]),
    ("sat", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ", ["桑塔利语"]),
    ("bo", "Tibetan", "བོད་སྐད་", ["藏语"]),
    ("ug", "Uyghur", "ئۇيغۇرچە", ["维吾尔语"]),
    ("mn", "Mongolian", "Монгол", ["蒙古语"]),
    ("am", "Amharic", "አማርኛ", ["阿姆哈拉语"]),
    ("so", "Somali", "Soomaali", ["索马里语"]),
    ("zu", "Zulu", "isiZulu", ["祖鲁语"]),
    ("xh", "Xhosa", "isiXhosa", ["科萨语"]),
    ("st", "Southern Sotho", "Sesotho", ["南索托语"]),
    ("ts", "Tsonga", "Xitsonga", ["聪加语"]),
    ("tn", "Tswana", "Setswana", ["茨瓦纳语"]),
    ("ve", "Venda", "Tshivenda", ["文达语"]),
    ("ss", "Swati", "siSwati", ["斯瓦蒂语"]),
    ("nr", "Southern Ndebele", "isiNdebele", ["南恩德贝莱语"]),
    ("nso", "Northern Sotho", "Sesotho sa Leboa", ["北索托语"]),
    ("qu", "Quechua", "Runa Simi", ["克丘亚语"]),
    ("gn", "Guarani", "Avañe'ẽ", ["瓜拉尼语"]),
    ("ay", "Aymara", "Aymar aru", ["艾马拉语"]),
    ("wo", "Wolof", "Wolof", ["沃洛夫语"]),
    ("ha", "Hausa", "Hausa", ["豪萨语"]),
    ("yo", "Yoruba", "Yorùbá", ["约鲁巴语"]),
    ("ig", "Igbo", "Igbo", ["伊博语"]),
]


def _build_entries() -> list[dict[str, object]]:
    seen: set[str] = set()
    out: list[dict[str, object]] = []
    for code, eng, native, zh_kw in _RAW:
        lowered = code.lower().strip()
        if lowered in seen:
            raise ValueError(f"Duplicate language code: {code}")
        if len(lowered) > 32:
            raise ValueError(f"Code too long for DB (max 32): {code}")
        seen.add(lowered)
        search_terms = [lowered, eng.lower(), native.lower()]
        for z in zh_kw:
            search_terms.append(z)
        out.append(
            {
                "code": lowered,
                "englishName": eng,
                "nativeLabel": native,
                "search": search_terms,
            }
        )
    return out


def main() -> None:
    """Write JSON registry and print count."""
    entries = _build_entries()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    with _OUT.open("w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Wrote {len(entries)} languages to {_OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
