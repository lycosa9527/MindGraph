"""CosyVoice v1 system voices (Aliyun Model Studio).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from services.tts.voices.types import BJ, COSY_V1, FAMILY_COSYVOICE, TtsVoice, make_voice

_V1 = (COSY_V1,)


def _cv(voice_id: str, name: str, scene: str, languages: tuple[str, ...]) -> TtsVoice:
    """CosyVoice v1 system voice (no SSML / instruct / timestamp)."""
    return make_voice(
        voice_id,
        name,
        scene,
        "",
        languages,
        family=FAMILY_COSYVOICE,
        models=_V1,
        regions=BJ,
    )


COSYVOICE_V1_VOICES: tuple[TtsVoice, ...] = (
    _cv("longwan", "龙婉", "语音助手", ("zh",)),
    _cv("longcheng", "龙橙", "语音助手", ("zh",)),
    _cv("longhua", "龙华", "语音助手", ("zh",)),
    _cv("longxiaochun", "龙小淳", "语音助手", ("zh", "en")),
    _cv("longxiaoxia", "龙小夏", "语音助手", ("zh",)),
    _cv("longxiaocheng", "龙小诚", "语音助手", ("zh", "en")),
    _cv("longxiaobai", "龙小白", "语音助手", ("zh",)),
    _cv("longlaotie", "龙老铁", "新闻播报", ("zh-dongbei",)),
    _cv("longshu", "龙书", "有声书", ("zh",)),
    _cv("longshuo", "龙硕", "新闻播报", ("zh",)),
    _cv("longjing", "龙婧", "新闻播报", ("zh",)),
    _cv("longmiao", "龙妙", "客服", ("zh",)),
    _cv("longyue", "龙悦", "诗词朗诵", ("zh",)),
    _cv("longyuan", "龙媛", "有声书", ("zh",)),
    _cv("longfei", "龙飞", "新闻播报", ("zh",)),
    _cv("longjielidou", "龙杰力豆", "新闻播报", ("zh", "en")),
    _cv("longtong", "龙彤", "有声书", ("zh",)),
    _cv("longxiang", "龙祥", "新闻播报", ("zh",)),
    _cv("loongstella", "Stella", "语音助手", ("zh", "en")),
    _cv("loongbella", "Bella", "语音助手", ("zh",)),
)
