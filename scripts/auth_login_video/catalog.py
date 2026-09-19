"""Four cinema login concepts. Action stays on the left of a 16:9 frame."""

from __future__ import annotations

from typing import TypedDict

from scripts.training_roles.wan_client import HAPPYHORSE_T2V, WAN3_VIDEO_PRIME

CAT_LOCK = (
    "同一只3D动画电影质感的黑色小猫吉祥物：全身黑色短绒毛，圆滚滚短腿站立，"
    "大圆玻璃眼带高光，红白格子小围巾，短尾巴，粉色小鼻头。不要人类身体，不要写成真人。"
    "不要换脸，不要换毛色，不要换围巾，不要第二个角色。"
)
LAYOUT = (
    "横向16:9电影宽银幕，1080P，30fps。主体动作始终集中在画面左侧约60%，"
    "右侧约40%逐渐变暗、柔化、留空，给登录卡片让位。不要字幕，不要可读汉字数字英文，"
    "不要水印，不要绿幕，不要UI截图，不要对话框。"
)
NEGATIVE = (
    "绿幕,绿背景,参考静帧,证件照,全身站立开场,字幕,水印,可读文字,汉字,英文,数字,"
    "对话框,气泡,人类身体,真人,换脸,换毛色,第二个角色,第二个猫,变形,多余肢体,"
    "低分辨率,抖动,slideshow,jump cut"
)


class LoginConcept(TypedDict):
    """One login-hero storyboard."""

    id: str
    slug: str
    name: str
    wan_seconds: int
    horse_seconds: int
    prompt: str


CONCEPTS: tuple[LoginConcept, ...] = (
    {
        "id": "01",
        "slug": "awaken-cosmos",
        "name": "AI觉醒·知识宇宙",
        "wan_seconds": 18,
        "horse_seconds": 15,
        "prompt": (
            "深空蓝加霓虹青紫，体积光，全息投影，像创战纪遇上星际穿越。"
            "镜头一：极特写琥珀猫眼在黑暗中缓缓睁开，瞳孔里倒映旋转的数据流和立体思维导图，"
            "猫脸被屏幕蓝光映亮，毛发根根分明，微距浅景深。"
            "镜头二：低角度仰拍，黑猫蹲在一本巨大发光全息书上，书页翻动，光粒子上升，"
            "猫突然跃起，镜头跟随猫爪快速上摇，爪尖划出发光轨迹，动态模糊。"
            "镜头三：升格慢动作360度环绕，猫在空中转身，尾巴扫过，AI扫描波从身上扩散，"
            "漂浮的书本、公式、灯泡、齿轮被扫描后自动连线成一张3D思维导图。"
            "镜头四：猫落在全息桌上，爪尖轻点一个节点，导图爆炸式生长，分支如神经突触延伸，"
            "镜头急速拉远再猛推近。"
            "镜头五：猫坐在全息图中央像一位小教授，转头看向画面右侧，"
            "思维导图收缩成一枚发光标志，右侧羽化渐隐。"
            "一条连续流畅的3D电影短片，不要定格拼图。"
        ),
    },
    {
        "id": "02",
        "slug": "mind-leap",
        "name": "思维跃迁",
        "wan_seconds": 17,
        "horse_seconds": 15,
        "prompt": (
            "赛博朋克加学术，冷暖对比，速度线，像蜘蛛侠平行宇宙的动感。"
            "镜头一：极特写猫眼，瞳孔里是旋转的3D思维导图，镜头急速拉远，"
            "黑猫站在巨大悬浮思维导图中央，周围漂浮书本和公式，动态模糊。"
            "镜头二：低角度跟拍，猫在流动数据网格上奔跑，爪踏过节点亮起，"
            "镜头紧贴地面横移穿过一座全息书架。"
            "镜头三：升格空中慢动作，猫跃过断层并转身，周围漂浮书本、铅笔、齿轮、灯泡，"
            "AI光效像激光从猫身射出连接这些元素。"
            "镜头四：快速旋转环绕，猫落地尾巴一甩，所有元素汇聚成发光3D思维导图，"
            "分支自动生成并智能补全。"
            "镜头五：猫坐在导图顶端像王座，看向右侧，导图逐渐化为柔和背景，右侧渐隐。"
            "一条连续流畅的3D电影短片，不要定格拼图。"
        ),
    },
    {
        "id": "03",
        "slug": "study-light",
        "name": "学习之光·AI协奏",
        "wan_seconds": 18,
        "horse_seconds": 15,
        "prompt": (
            "暖金加科技蓝，体积光，粒子，像超能陆战队的温暖科技感。"
            "镜头一：中景，黑猫趴在书桌上睡觉，周围书本堆叠，一本书自动翻开，"
            "发光粒子飘出，猫耳朵一动睁眼，固定浅景深。"
            "镜头二：猫好奇追着光粒子快速穿过书架，粒子汇聚成一个AI光球，猫伸爪触碰。"
            "镜头三：光球炸开变成全息思维导图，节点自动生成，连线如神经突触，"
            "镜头快速推近一个节点再拉远展示全貌。"
            "镜头四：缓慢环绕中景，猫坐在导图前用爪子拖拽一个节点，AI自动补全分支，"
            "发光线条延伸。"
            "镜头五：猫满意地眨眼，看向右侧，导图缩成柔和装饰，右侧羽化渐显。"
            "一条连续流畅的3D电影短片，不要定格拼图。"
        ),
    },
    {
        "id": "04",
        "slug": "ai-lab",
        "name": "猫的AI实验室",
        "wan_seconds": 19,
        "horse_seconds": 15,
        "prompt": (
            "明亮实验室加全息屏幕，3D皮克斯质感，像神偷奶爸的幽默科技。"
            "镜头一：中景，黑猫戴着小护目镜坐在控制台前，按下大按钮，全息屏幕亮起，"
            "快速推近按钮再拉远。"
            "镜头二：俯拍转正拍，全息投影从桌面升起显示杂乱知识点，猫歪头，爪子一挥，"
            "AI扫描线扫过，知识点自动分类连线。"
            "镜头三：环绕跟拍，猫在多个全息屏幕间跳跃，每次触碰都生成新的思维导图分支，"
            "镜头快速掠过屏幕。"
            "镜头四：快速拉远，所有屏幕汇聚成巨大3D思维导图，猫站在中央，尾巴指向右侧。"
            "镜头五：导图化为柔和背景，猫回头看向右侧，画面羽化渐隐。"
            "一条连续流畅的3D电影短片，不要定格拼图。"
        ),
    },
)

WAN_SHELL = (
    f"{CAT_LOCK}图1和图2只用于锁定同一只黑猫的脸、围巾和体型，不是成片第一帧，"
    "不是分镜底板。禁止把参考图、绿幕、证件照、全身静帧接到视频开头。"
    f"成片必须从电影场景第一镜直接开始，绝对不要出现绿幕。{LAYOUT}"
)
HORSE_SHELL = f"{CAT_LOCK}{LAYOUT}"


def concept_by_id(concept_id: str) -> LoginConcept:
    """Look up a concept by 01 or 01-awaken-cosmos."""
    needle = concept_id.strip()
    for concept in CONCEPTS:
        packed = f"{concept['id']}-{concept['slug']}"
        if needle in (concept["id"], packed):
            return concept
    raise ValueError(f"Unknown login concept: {concept_id}")


def clip_stem(concept: LoginConcept, model: str) -> str:
    """Work-dir filename without suffix."""
    short = "wan3" if model == WAN3_VIDEO_PRIME else "horse"
    return f"{concept['id']}-{concept['slug']}-{short}"


def desktop_original_name(concept: LoginConcept) -> str:
    """Pictures/mascots master: 01-awaken-cosmos-original.mp4."""
    return f"{concept['id']}-{concept['slug']}-original.mp4"


def desktop_reencode_name(concept: LoginConcept) -> str:
    """Pictures/mascots CRF 18 encode: 01-awaken-cosmos-reencode.mp4."""
    return f"{concept['id']}-{concept['slug']}-reencode.mp4"


def clip_public_id(concept: LoginConcept) -> str:
    """Public clip id used by /auth and COS: 01-awaken-cosmos."""
    return f"{concept['id']}-{concept['slug']}"


def hero_object_name(concept: LoginConcept) -> str:
    """COS object filename: 01-awaken-cosmos.mp4."""
    return f"{clip_public_id(concept)}.mp4"


def public_clip_ids() -> tuple[str, ...]:
    """Four login-hero ids in rotation order."""
    return tuple(clip_public_id(concept) for concept in CONCEPTS)


def clip_duration(concept: LoginConcept, model: str) -> int:
    """HappyHorse maxes at 15s; Wan 3.0 can hold the full storyboard."""
    if model == HAPPYHORSE_T2V:
        return concept["horse_seconds"]
    return concept["wan_seconds"]


def clip_prompt(concept: LoginConcept, model: str) -> str:
    """Full prompt: identity lock + cinema layout + shot list."""
    shell = WAN_SHELL if model == WAN3_VIDEO_PRIME else HORSE_SHELL
    return f"{shell}{concept['prompt']} 不要出现：{NEGATIVE}"
