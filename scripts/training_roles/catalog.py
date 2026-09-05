"""Role clip prompts. Ids must stay aligned with frontend and COS catalog."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from services.features.training.roles.catalog import TRAINING_ROLE_IDS


class RoleAction(TypedDict):
    """One I2V clip definition."""

    id: str
    slug: str
    name: str
    prompt: str
    keep_existing: NotRequired[str]


SHELL = (
    "固定机位，全身始终完整入镜，不要裁掉脚掌和尾巴。"
    "同一只毛茸茸黑色小猫吉祥物，大圆玻璃眼，红白格子围巾，短爪子，3D可爱动画电影质感。"
    "背景必须一直保持均匀纯绿色绿幕 #00FF00，不要教室、不要桌椅、不要地板场景、不要文字水印。"
    "两只爪子空着，不要出现教鞭、木棍、指挥棒或任何手持道具。"
    "不要凭空变出书本、积木、本子、玻璃、灯具、望远镜等实物。可以做无实物手势。"
    "动作夸张可爱。不要说话，不要变形，不要新增角色。"
)
NEGATIVE = (
    "教室,桌子,变形,换脸,裁脚,裁尾巴,文字水印,背景变成房间,多余肢体,多余手臂,翅膀状爪子,第二个角色,"
    "书本,积木,笔记本,玻璃板,台灯,望远镜实物,灯泡道具,教鞭,木棍,指挥棒,手持道具"
)

ROLE_ACTIONS: tuple[RoleAction, ...] = (
    {
        "id": "01",
        "slug": "look-here",
        "name": "看这里",
        "prompt": (
            "课堂开场引导。身体微微前倾，一只爪子掌心向上划出一个舒展的半圆弧线，"
            "像请看这边，头跟着转向镜头，节奏慢、动作舒展。"
        ),
    },
    {
        "id": "02",
        "slug": "listen",
        "name": "竖起耳朵听",
        "prompt": (
            "聆听重点。身体略微侧倾，一只爪子放到耳廓后方做收音姿势，"
            "两只耳朵竖起轻轻抖动，眼睛睁大，胸腔轻微起伏，表情好奇。"
        ),
    },
    {
        "id": "03",
        "slug": "raise-hand",
        "name": "举手回答",
        "prompt": (
            "激励参与。一只爪子高高举过头顶，另一只爪子空着垂在身侧，身体向上挺起，眼神期待地看着镜头，尾巴轻轻摆。"
        ),
    },
    {
        "id": "04",
        "slug": "secret",
        "name": "悄悄话",
        "prompt": (
            "保密冷知识。一只爪子尖竖在嘴唇前做嘘声，另一只手背在身后，"
            "身体稍稍蹲一点，偷偷摸摸但可爱，眼睛左右瞄一下再看镜头。"
        ),
    },
    {
        "id": "05",
        "slug": "open-book",
        "name": "翻书",
        "prompt": (
            "开启新课。双手在胸前做翻开书页的空动作，没有真实书本出现，翻开后身体稍稍后仰，微笑，轻轻吸一口气。"
        ),
    },
    {
        "id": "06",
        "slug": "eureka",
        "name": "灯泡亮了",
        "prompt": (
            "顿悟。一只爪子握拳轻轻敲一下脑袋，然后爪子张开看向镜头，"
            "眼睛一下子睁大发亮，身体轻轻后仰，尾巴弹一下。不要出现真实灯泡。"
        ),
    },
    {
        "id": "07",
        "slug": "build-blocks",
        "name": "搭建积木",
        "prompt": (
            "逻辑组合。双手在身前做拿起、对齐、往下按的空动作，没有真实积木，按下去时身体轻轻一抖，再满意地点头。"
        ),
    },
    {
        "id": "08",
        "slug": "zoom",
        "name": "变大缩小",
        "prompt": (
            "聚焦远近。两只爪子始终贴在身体两侧，不要举起，不要交叉，"
            "不要变出第三只手臂，不要翅膀状大爪子。"
            "身体先轻轻向前探，头靠近镜头停一下，再慢慢退回原位。"
            "始终只有两只前爪和两只后腿，不要变形。"
        ),
    },
    {
        "id": "09",
        "slug": "orbit",
        "name": "旋转视角",
        "prompt": (
            "三维观察。始终面向镜头，上身只转四分之一圈，"
            "一只空爪子在身前画一个小圆，像展示一个看不见的立体物。"
            "不要转过身，不要出现真实物体，不要出现教鞭。"
        ),
    },
    {
        "id": "10",
        "slug": "erase",
        "name": "擦除重来",
        "prompt": (
            "纠错。先举起一只爪子做停止手势，表情调皮，"
            "再换另一只爪子在空气中左右平移擦拭，不要出现玻璃。擦完眨眨眼看镜头。"
        ),
    },
    {
        "id": "11",
        "slug": "clap",
        "name": "鼓掌欢呼",
        "prompt": ("表扬。双手在胸前快速鼓掌，身体轻轻跳两下左右摇摆，眯眼笑，尾巴开心乱晃。"),
    },
    {
        "id": "12",
        "slug": "cheer",
        "name": "加油握拳",
        "prompt": ("打气。双臂弯曲，两只小拳头在胸前下压发力，表情坚定可爱，再抬起一个拳头向前轻轻挥一下。"),
    },
    {
        "id": "13",
        "slug": "pat-head",
        "name": "摸摸头",
        "prompt": ("安慰。一只爪子轻轻抬起，温柔地摸自己头顶两下，表情柔软，身体微微前倾，动作慢。"),
    },
    {
        "id": "14",
        "slug": "take-notes",
        "name": "记笔记",
        "prompt": (
            "强调重点。一只爪子在身前摊开当本子，另一只空爪子当笔写几下，"
            "不要出现真实本子，不要出现教鞭，眼神看向爪子，写完点头。"
        ),
    },
    {
        "id": "15",
        "slug": "countdown",
        "name": "倒计时",
        "prompt": ("限时练习。眼睛看向自己的手腕，手腕上没有表，另一只爪子快速轻轻敲手腕，身体微微焦急地左右晃。"),
    },
    {
        "id": "16",
        "slug": "pace-think",
        "name": "思考踱步",
        "prompt": ("过渡消化。双手背在身后，头微微扬起做沉思状，只在原地左右小步踏步，不要走开，尾巴慢慢摆。"),
    },
    {
        "id": "17",
        "slug": "telescope",
        "name": "望远镜观察",
        "prompt": (
            "聚焦细节。两只爪子握拳叠在眼前假装望远镜，不要出现真实望远镜，身体前倾，左右慢慢扫描，最后放下爪子眨眨眼。"
        ),
    },
    {
        "id": "18",
        "slug": "magic-light",
        "name": "魔法点亮",
        "prompt": (
            "揭示答案。一只爪子掌心朝上托在胸前，爪子从握拢到依次张开，"
            "眼睛亮起来微笑看镜头。不要出现灯，不要改变绿幕亮度。"
        ),
    },
    {
        "id": "19",
        "slug": "drink-ink",
        "name": "喝饱墨水",
        "prompt": (
            "吸收知识。先做一个很大的吞咽动作，喉头动一下，圆肚子轻轻鼓起，再打一个满足的小嗝，眯眼享受，尾巴卷一下。"
        ),
    },
    {
        "id": "20",
        "slug": "dismiss",
        "name": "放学休息",
        "keep_existing": "true",
        "prompt": ("下课结束。先双臂向上伸展做大大的懒腰并打个小哈欠，再单手挥手道别，身体重心后移，表情放松。"),
    },
)


def role_clip_id(action: RoleAction) -> str:
    """Frontend / COS id, e.g. 11-clap."""
    return f"{action['id']}-{action['slug']}"


def action_by_id(action_id: str) -> RoleAction:
    """Look up a clip by 01 or 01-look-here."""
    needle = action_id.strip()
    for action in ROLE_ACTIONS:
        if action["id"] == needle or role_clip_id(action) == needle:
            return action
    raise ValueError(f"Unknown role action: {action_id}")


def catalog_ids() -> tuple[str, ...]:
    """Packed ids in prompt order."""
    return tuple(role_clip_id(action) for action in ROLE_ACTIONS)


def assert_catalog_aligned() -> None:
    """Fail if Wan prompts drift from the shipped COS/frontend list."""
    if catalog_ids() != TRAINING_ROLE_IDS:
        raise RuntimeError("scripts.training_roles.catalog drifted from TRAINING_ROLE_IDS")
