"""Qwen-TTS realtime and non-realtime system voices.

Snapshot model ids (``-YYYY-MM-DD`` / ``-latest``) normalize to these families.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from services.tts.voices.types import (
    BJ,
    FAMILY_QWEN_TTS,
    QWEN3_FLASH,
    QWEN3_FLASH_RT,
    QWEN3_INSTRUCT,
    QWEN3_INSTRUCT_RT,
    QWEN_TTS,
    QWEN_TTS_RT,
    TtsVoice,
    make_voice,
)

_LANGS = ("zh", "en", "fr", "de", "ru", "it", "es", "pt", "ja", "ko")

# Cherry / Serena / Ethan / Chelsie: full instruct + flash + legacy Qwen-TTS.
_FULL = (
    QWEN3_INSTRUCT_RT,
    QWEN3_FLASH_RT,
    QWEN_TTS_RT,
    QWEN3_INSTRUCT,
    QWEN3_FLASH,
    QWEN_TTS,
)
# Momo … Stella: instruct + flash (no legacy qwen-tts-realtime / qwen-tts).
_INSTRUCT = (
    QWEN3_INSTRUCT_RT,
    QWEN3_FLASH_RT,
    QWEN3_INSTRUCT,
    QWEN3_FLASH,
)
# Jennifer … Radio Gol: flash only.
_FLASH_ONLY = (QWEN3_FLASH_RT, QWEN3_FLASH)
# Dialect voices on flash; some also on qwen-tts-latest.
_DIALECT = (QWEN3_FLASH_RT, QWEN3_FLASH)
_DIALECT_QWEN = (QWEN3_FLASH_RT, QWEN3_FLASH, QWEN_TTS)


def _qt(
    voice_id: str,
    name: str,
    trait: str,
    *,
    models: tuple[str, ...],
    languages: tuple[str, ...] = _LANGS,
) -> TtsVoice:
    """Qwen-TTS system voice (realtime + non-realtime families)."""
    return make_voice(
        voice_id,
        name,
        "Qwen-TTS",
        trait,
        languages,
        family=FAMILY_QWEN_TTS,
        models=models,
        regions=BJ,
    )


QWEN_TTS_VOICES: tuple[TtsVoice, ...] = (
    _qt("Cherry", "芊悦", "阳光积极、亲切自然小姐姐", models=_FULL),
    _qt("Serena", "苏瑶", "温柔小姐姐", models=_FULL),
    _qt("Ethan", "晨煦", "阳光温暖活力朝气", models=_FULL),
    _qt("Chelsie", "千雪", "二次元虚拟女友", models=_FULL),
    _qt("Momo", "茉兔", "撒娇搞怪", models=_INSTRUCT),
    _qt("Vivian", "十三", "拽拽的可爱小暴躁", models=_INSTRUCT),
    _qt("Moon", "月白", "率性帅气", models=_INSTRUCT),
    _qt("Maia", "四月", "知性与温柔", models=_INSTRUCT),
    _qt("Kai", "凯", "沉稳男声", models=_INSTRUCT),
    _qt("Nofish", "不吃鱼", "不会翘舌音的设计师", models=_INSTRUCT),
    _qt("Bella", "萌宝", "小萝莉", models=_INSTRUCT),
    _qt("Jennifer", "詹妮弗", "电影质感美语女声", models=_FLASH_ONLY),
    _qt("Ryan", "甜茶", "节奏张力男声", models=_FLASH_ONLY),
    _qt("Katerina", "卡捷琳娜", "御姐音色", models=_FLASH_ONLY),
    _qt("Aiden", "艾登", "美语大男孩", models=_FLASH_ONLY),
    _qt("Eldric Sage", "沧明子", "沉稳睿智老者", models=_INSTRUCT),
    _qt("Mia", "乖小妹", "温顺乖巧", models=_INSTRUCT),
    _qt("Mochi", "沙小弥", "聪明伶俐的小大人", models=_INSTRUCT),
    _qt("Bellona", "燕铮莺", "洪亮江湖女声", models=_INSTRUCT),
    _qt("Vincent", "田叔", "沙哑烟嗓", models=_INSTRUCT),
    _qt("Bunny", "萌小姬", "萌属性小萝莉", models=_INSTRUCT),
    _qt("Neil", "阿闻", "专业新闻主持人", models=_INSTRUCT),
    _qt("Elias", "墨讲师", "叙事型讲师", models=_INSTRUCT),
    _qt("Arthur", "徐大爷", "质朴说书男", models=_INSTRUCT),
    _qt("Nini", "邻家妹妹", "软糯女声", models=_INSTRUCT),
    _qt("Seren", "小婉", "助眠舒缓", models=_INSTRUCT),
    _qt("Pip", "顽屁小孩", "调皮童真", models=_INSTRUCT),
    _qt("Stella", "少女阿月", "迷糊少女音", models=_INSTRUCT),
    _qt("Bodega", "博德加", "热情西班牙大叔", models=_FLASH_ONLY),
    _qt("Sonrisa", "索尼莎", "热情拉美大姐", models=_FLASH_ONLY),
    _qt("Alek", "阿列克", "沉稳俄语男", models=_FLASH_ONLY),
    _qt("Dolce", "多尔切", "慵懒意大利大叔", models=_FLASH_ONLY),
    _qt("Sohee", "素熙", "温柔韩国欧尼", models=_FLASH_ONLY),
    _qt("Ono Anna", "小野杏", "鬼灵精怪青梅竹马", models=_FLASH_ONLY),
    _qt("Lenn", "莱恩", "德国青年", models=_FLASH_ONLY),
    _qt("Emilien", "埃米尔安", "浪漫法国大哥哥", models=_FLASH_ONLY),
    _qt("Andre", "安德雷", "磁性沉稳男", models=_FLASH_ONLY),
    _qt("Radio Gol", "拉迪奥·戈尔", "足球解说", models=_FLASH_ONLY),
    _qt("Jada", "上海-阿珍", "沪上阿姐", models=_DIALECT_QWEN, languages=("zh-shanghai",) + _LANGS[1:]),
    _qt("Dylan", "北京-晓东", "北京胡同少年", models=_DIALECT_QWEN, languages=("zh-beijing",) + _LANGS[1:]),
    _qt("Li", "南京-老李", "耐心瑜伽老师", models=_DIALECT, languages=("zh-nanjing",) + _LANGS[1:]),
    _qt("Marcus", "陕西-秦川", "老陕男声", models=_DIALECT, languages=("zh-shaanxi",) + _LANGS[1:]),
    _qt("Roy", "闽南-阿杰", "台湾哥仔", models=_DIALECT, languages=("zh-min",) + _LANGS[1:]),
    _qt("Peter", "天津-李彼得", "天津捧哏", models=_DIALECT, languages=("zh-tianjin",) + _LANGS[1:]),
    _qt("Sunny", "四川-晴儿", "川妹子", models=_DIALECT_QWEN, languages=("zh-sichuan",) + _LANGS[1:]),
    _qt("Eric", "四川-程川", "成都男子", models=_DIALECT, languages=("zh-sichuan",) + _LANGS[1:]),
    _qt("Rocky", "粤语-阿强", "幽默港男", models=_DIALECT, languages=("zh-yue",) + _LANGS[1:]),
    _qt("Kiki", "粤语-阿清", "甜美港妹", models=_DIALECT, languages=("zh-yue",) + _LANGS[1:]),
)
