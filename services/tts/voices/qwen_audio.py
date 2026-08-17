"""Qwen-Audio-TTS system voices (plus / flash).

Base (cloned) timbres are listed in Aliyun Excel downloads, not here.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from services.tts.voices.types import (
    BJ,
    FAMILY_QWEN_AUDIO,
    QWEN_AUDIO_FLASH,
    QWEN_AUDIO_PLUS,
    ZH_EN,
    TtsVoice,
    make_voice,
)


def _qa(
    voice_id: str,
    name: str,
    scene: str,
    trait: str,
    *,
    models: tuple[str, ...],
    age: str,
    languages: tuple[str, ...] = ZH_EN,
) -> TtsVoice:
    """Qwen-Audio-TTS system voice."""
    return make_voice(
        voice_id,
        name,
        scene,
        trait,
        languages,
        family=FAMILY_QWEN_AUDIO,
        models=models,
        age=age,
        regions=BJ,
    )


_PLUS = (QWEN_AUDIO_PLUS,)
_FLASH = (QWEN_AUDIO_FLASH,)

QWEN_AUDIO_VOICES: tuple[TtsVoice, ...] = (
    _qa("longanlingxin", "龙安灵心", "社交陪伴", "知心温暖音", models=_PLUS, age="25"),
    _qa("longanlufeng", "龙安鲁风", "社交陪伴", "明亮开朗音", models=_PLUS, age="25"),
    _qa("longanfengyue", "龙安风悦", "社交陪伴", "自然亲切音", models=_FLASH, age="30"),
    _qa("longanyuanfei", "龙安元妃", "社交陪伴", "高傲妃子音", models=_FLASH, age="30"),
    _qa("longanlingxi", "龙安灵希", "社交陪伴", "可爱甜美音", models=_FLASH, age="25"),
    _qa("longanxiaoxin", "龙安小昕", "社交陪伴", "亲切活泼音", models=_FLASH, age="22"),
    _qa("longanhuan_v3.6", "龙安欢", "社交陪伴", "", models=_FLASH, age="25"),
    _qa("longjielidou_v3.6", "龙杰力豆", "儿童陪伴", "天真男童", models=_FLASH, age="5"),
    _qa("longpaopao_v3.6", "龙泡泡", "儿童陪伴", "软糯可爱音", models=_FLASH, age="5"),
    _qa("longhuohuo_v3.6", "龙火火", "角色音", "顽皮少年音", models=_FLASH, age="8"),
    _qa("longchuanshu_v3.6", "龙川叔", "角色音", "川普大叔音", models=_FLASH, age="40"),
    _qa("loongmary", "loongmary", "社交陪伴", "温暖英音", models=_FLASH, age="20", languages=("en",)),
    _qa("loongeva_v3.6", "loongeva", "社交陪伴", "高智美音", models=_FLASH, age="28", languages=("en",)),
    _qa("loongjohn", "loongJohn", "社交陪伴", "沉稳亲切美音", models=_FLASH, age="28", languages=("en",)),
)
