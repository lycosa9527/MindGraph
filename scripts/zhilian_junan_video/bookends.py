"""Opening and closing lines over a real Junan school, shot like a drone."""

from __future__ import annotations

from typing import TypedDict


class BookendScene(TypedDict):
    """One bookend. Figure 3 is a real campus aerial, not a blank wall."""

    id: str
    slug: str
    name: str
    seconds: int
    prompt: str
    line: str
    filename: str
    source: str


# Wentian schoolyard aerial. The open flies in; the close pulls back out.
WENTIAN_AERIAL = "区展板文字及相片/4、第四板块：教育生态/2-1、文田中学进行武术特色大课间活动展示.jpg"
BOOKEND_SHELL = (
    "图1和图2只锁定同一只2D卡通黄色小龙的脸、蓝色学士帽、蓝腮红、圆滚滚体型和发光节点尾巴。"
    "图3是均安一所中学操场的无人机航拍，锁定教学楼、操场阵列、棕榈和光线。"
    "镜头要像无人机云台：平稳、连续、没有手持晃动。不要跳切，不要换到另一所学校。"
    "楼名、标语、旗帜、横幅上的字全部涂掉，不要重画半个字。"
    "画面里只有这一只小龙，贴在画面右下角。不要叠影，不要分身，不要飞过操场中心。"
    "小龙从第一帧就在，脸正对镜头，嘴能看清，整句口播期间嘴一张一合。"
    "不要迟到入画，不要侧脸或背对，不要话说完才张嘴，不要把句子拉慢。"
    "音频1是小龙的少年音色。他只说口播那一句，嘴型对准这句，语速像聊天。"
    "只有这一句人声。不要背景音乐，不要BGM，不要配乐，不要歌曲，不要哼唱。"
    "画面里绝对不要出现任何文字、字母、数字、汉字、水印、logo、校徽、字幕。"
    "一条连续镜头。"
)
BOOKEND_NEGATIVE = (
    "文字，乱码，字母，数字，汉字，logo，水印，校徽，字幕，楼名，标语，"
    "背景音乐，BGM，配乐，歌曲，哼唱，"
    "第二个龙，分身，叠影，残影，双胞胎，手持，晃动，抖动，换学校，真人龙，3D写实，快切"
)
BOOKEND_SCENES: tuple[BookendScene, ...] = (
    {
        "id": "b0",
        "slug": "hello",
        "name": "开篇",
        "seconds": 12,
        "filename": "01-开篇.mp4",
        "source": WENTIAN_AERIAL,
        "prompt": (
            "横向16:9，无人机从校门一侧平稳滑向操场，略微下降，云台稳定。"
            "小龙停在右下角对镜头挥一下手再把整句说完，不要跟着飞机满场飞。"
        ),
        "line": "大家好，我是启思龙。今天我带你们走一圈。从孩子手里的活看起，老师会坐过来，最后我们才出门。",
    },
    {
        "id": "b1",
        "slug": "so-long",
        "name": "收束",
        "seconds": 10,
        "filename": "19-收束.mp4",
        "source": WENTIAN_AERIAL,
        "prompt": (
            "横向16:9，同一座操场。无人机平稳拉高并向后退出，看见教学楼和操场，云台稳定。"
            "小龙仍停在右下角，两只爪合在胸前，把最后一句说完。不要飞走，不要换背景。"
        ),
        "line": "机器人看完，这一路就是均安。潜能致远，我盼每个孩子都闪闪发光。",
    },
)


def bookend_line(scene_id: str) -> str:
    """Spoken line for one bookend. Mouth sync uses this exact sentence."""
    for item in BOOKEND_SCENES:
        if item["id"] == scene_id:
            return item["line"]
    raise KeyError(scene_id)


def bookend_filename(scene_id: str) -> str:
    """Published mp4 name for a bookend."""
    for item in BOOKEND_SCENES:
        if item["id"] == scene_id:
            return item["filename"]
    raise KeyError(scene_id)
