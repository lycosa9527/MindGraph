"""Siamese tester-cat identity. Stills first; action clips stay separate later."""

from __future__ import annotations

from typing import TypedDict


class StillShot(TypedDict):
    """One green-screen still pose."""

    id: str
    slug: str
    name: str
    prompt: str


SHELL = (
    "图1只锁定3D吉祥物画风和短腿圆身子，不要抄它的圆脸、大圆眼和围巾。"
    "现在只画一只新角色：暹罗重点色测试员小猫，比图1再小一圈，大约七八成高，"
    "头顶、两侧和脚下都留出更多均匀绿幕，不要画成幼崽，只是体型略小。"
    "脸必须和白猫黑猫都不同：暹罗楔形头，脸更长，从耳根到下巴是柔和三角形，"
    "不是圆苹果脸，不是短口鼻，不是白猫那张圆脸轮廓。"
    "耳朵更大、耳根更宽、更立、更靠外，深巧克力褐色。"
    "眼睛是斜杏仁形明亮蓝眼，睁开认真看镜头，不要半眯，不要又圆又无辜，不要绿色眼。"
    "鼻梁稍长，口鼻更利落，深色V形脸罩包住口鼻，身体中间保持浅奶油色。"
    "没有眼线，没有眼影，没有挑眉，没有拽笑。眉毛只在眉心轻轻皱一下。"
    "戴一副稳稳的黑色小圆框眼镜，镜片透明，不要绿框，不要墨镜。"
    "身体是暖象牙／浅奶油色，四爪和尾巴也是深巧克力褐色。"
    "一条浅薄荷色细项圈，不要围巾，不要爱心吊坠，不要耳环。"
    "两只爪子空着垂在身侧，不要手持道具，不要教鞭，不要放大镜，不要徽章文字。"
    "背景必须一直保持均匀纯绿色绿幕 #00FF00，不要教室、不要桌椅、不要地板场景、不要文字水印。"
    "不要人类身体，不要第二个角色，不要换毛色，不要粉色，不要荧光粉，不要洋红。"
    "不要全身一种颜色，不要纯白长毛，不要纯黑，不要写实瘦长暹罗。"
    "全身始终完整入镜，不要裁掉脚掌和尾巴。"
)
NEGATIVE = (
    "教室,桌子,变形,换脸,裁脚,裁尾巴,文字水印,人类身体,真人,第二个角色,"
    "手持道具,教鞭,放大镜,徽章文字,粉色,草莓粉,珊瑚粉,荧光粉,洋红,"
    "绿框眼镜,墨镜,围巾,爱心吊坠,纯白长毛,纯黑全身,全身一种颜色,"
    "圆苹果脸,白猫脸,短口鼻,半眯眼,挑眉,拽笑,眼线,眼影,绿眼睛,"
    "又圆又无辜的大眼,写实瘦长暹罗,臭脸,无辜发呆,幼崽,巨大角色,背景变成房间"
)
STILL_SHOTS: tuple[StillShot, ...] = (
    {
        "id": "2",
        "slug": "front",
        "name": "正面站立",
        "prompt": (
            "正面全身站立，面向镜头，双臂自然垂在身侧，深色尾巴从身侧可见。"
            "黑色圆框眼镜正对镜头，楔形长脸和斜杏仁蓝眼清楚。表情认真专注。固定机位，一只猫。"
        ),
    },
    {
        "id": "1",
        "slug": "three-quarter",
        "name": "四分之三侧站",
        "prompt": (
            "四分之三侧面全身站立，头仍看向镜头，身体略右转，深巧克力色尾巴向上弯。"
            "同一只戴眼镜的暹罗重点色小猫，黑色圆框眼镜仍然戴稳。固定机位，一只猫。"
        ),
    },
)


def shot_by_id(shot_id: str) -> StillShot:
    """Look up a still by 1, 2, front, or three-quarter."""
    needle = shot_id.strip().lower()
    for shot in STILL_SHOTS:
        if needle in {shot["id"], shot["slug"], f"{shot['id']}-{shot['slug']}"}:
            return shot
    raise ValueError(f"Unknown siamese-cat still: {shot_id}")
