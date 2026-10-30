"""Identity locks for the five desktop-pet characters."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from scripts.cat_emoji.paths import (
    BLACK_DESKTOP_DIR,
    BLACK_STILL_FRONT,
    BLACK_STILL_THREE_QUARTER,
    MASCOTS_DIR,
    RAVEN_STILL_FRONT,
    RAVEN_STILL_THREE_QUARTER,
    SCHNAUZER_STILL_FRONT,
    SCHNAUZER_STILL_THREE_QUARTER,
    SIAMESE_DESKTOP_DIR,
    SIAMESE_STILL_FRONT,
    SIAMESE_STILL_THREE_QUARTER,
    WHITE_DESKTOP_DIR,
    WHITE_STILL_FRONT,
    WHITE_STILL_THREE_QUARTER,
)

RAVEN_DESKTOP_DIR = MASCOTS_DIR / "raven-teacher-mascot"
SCHNAUZER_DESKTOP_DIR = MASCOTS_DIR / "schnauzer-professor"

GREEN_SCREEN = (
    "固定机位，全身始终完整入镜，不要裁掉脚掌和尾巴。"
    "背景必须从第一帧到最后一帧保持均匀纯绿色绿幕 #00FF00，"
    "不要教室，不要地板，不要房间，不要渐变，不要地面阴影。"
    "不要说话，不要口型，不要字幕，不要水印，不要第二个角色。"
    "动作里写明的街机、玩偶、小车、小机器人留在角色身边，背景仍是绿幕。"
    "不要另加没写到的道具。"
)

NEGATIVE = (
    "教室,地板,房间,渐变背景,换背景,变形,换脸,裁脚,裁尾巴,文字水印,字幕,口型,说话,第二个角色,多余肢体,没写到的道具"
)


class Mascot(TypedDict):
    """One character: look, everyday clothes, and how they move."""

    slug: str
    label: str
    pictures_dir: Path
    front: Path
    three_quarter: Path
    identity: str
    manner: str
    default_outfit: str


MASCOTS: tuple[Mascot, ...] = (
    {
        "slug": "black",
        "label": "黑猫",
        "pictures_dir": BLACK_DESKTOP_DIR,
        "front": BLACK_STILL_FRONT,
        "three_quarter": BLACK_STILL_THREE_QUARTER,
        "identity": "同一只毛茸茸黑色小猫吉祥物，大圆玻璃眼，短爪子，粉色小鼻头，3D动画电影质感。",
        "manner": (
            "性格是慢性子的 STEM 工程师，爱打电子游戏。"
            "动作晚半拍，圆眼真诚，一旦明白就做得过头。"
            "玩游戏时整个人扑在街机上，动作要一眼看懂，可以出现这一镜写明的街机或小装置。"
        ),
        "default_outfit": "红白格子围巾，没有别的外套。",
    },
    {
        "slug": "white",
        "label": "白猫",
        "pictures_dir": WHITE_DESKTOP_DIR,
        "front": WHITE_STILL_FRONT,
        "three_quarter": WHITE_STILL_THREE_QUARTER,
        "identity": (
            "同一只雪白长毛雌性小猫吉祥物，半眯绿色玻璃眼，粗黑上挑眼线，细长睫毛，粉色小鼻头。短爪子，3D动画电影质感。"
        ),
        "manner": "动作快、准、不耐烦。表情从头到尾保持半眯眼、挑眉、拽拽的臭脸。不要甜笑，不要睁大无辜眼。",
        "default_outfit": "黑色细项圈加金色小爱心吊坠，每只耳朵外侧两枚金色小环。",
    },
    {
        "slug": "siamese",
        "label": "暹罗猫",
        "pictures_dir": SIAMESE_DESKTOP_DIR,
        "front": SIAMESE_STILL_FRONT,
        "three_quarter": SIAMESE_STILL_THREE_QUARTER,
        "identity": (
            "同一只暹罗重点色小猫吉祥物，楔形头，中等立耳，耳朵跟着头，不要放大，"
            "斜杏仁蓝眼，黑色圆框眼镜，奶油色身体，巧克力四肢和尾巴。短爪子，3D动画电影质感。"
        ),
        "manner": (
            "测试员。动作小而整齐，眼睛睁开，眉毛放松平展，嘴角明显上扬，看起来高兴。"
            "不要皱眉，不要臭脸，不要又圆又无辜。耳朵保持中等大小。"
        ),
        "default_outfit": "深海军蓝色细项圈，颜色要明显深蓝，不要绿色，不要薄荷色，不要浅绿。",
    },
    {
        "slug": "raven",
        "label": "乌鸦",
        "pictures_dir": RAVEN_DESKTOP_DIR,
        "front": RAVEN_STILL_FRONT,
        "three_quarter": RAVEN_STILL_THREE_QUARTER,
        "identity": "同一只3D动画乌鸦吉祥物，直立短腿，橙色喙，深色羽毛，棕色圆框眼镜，棕色脚，用翅膀做事。",
        "manner": "老师。从容，不慌，用翅膀把意思比划清楚。",
        "default_outfit": "黄色领结。",
    },
    {
        "slug": "schnauzer",
        "label": "雪纳瑞",
        "pictures_dir": SCHNAUZER_DESKTOP_DIR,
        "front": SCHNAUZER_STILL_FRONT,
        "three_quarter": SCHNAUZER_STILL_THREE_QUARTER,
        "identity": (
            "同一只3D动画雪纳瑞教授吉祥物，盐胡椒灰硬毛，方口吻，浓眉胡须，深棕圆框眼镜，短腿直立。不要写成真人。"
        ),
        "manner": "导师。站得直，动作稳，点头幅度小，不滑稽，不打闹。",
        "default_outfit": "海军蓝整套西装、白衬衫、深红领带。",
    },
)


def mascot_by_slug(slug: str) -> Mascot:
    """Return one character by the folder slug."""
    for mascot in MASCOTS:
        if mascot["slug"] == slug:
            return mascot
    raise KeyError(slug)


def clip_prompt(mascot: Mascot, action_prompt: str, costume: str = "") -> str:
    """Identity, manner, this shot's clothes, green screen, then the body action."""
    named = costume.strip()
    if named:
        clothes = f"这一镜换成这套衣服，不要穿平时的衣服：{named}。脸、毛色和体型保持这只角色。"
    else:
        clothes = f"这一镜穿平时的衣服：{mascot['default_outfit']}"
    return f"{mascot['identity']}{mascot['manner']}{clothes}{GREEN_SCREEN}{action_prompt}"
