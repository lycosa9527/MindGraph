"""Dragon travel plates through the earlier empty-shot environments."""

from __future__ import annotations

from typing import TypedDict


class TravelScene(TypedDict):
    """One dragon journey clip. Gesture changes every shot."""

    id: str
    slug: str
    name: str
    seconds: int
    prompt: str
    source: str


TRAVEL_SECONDS = 5
TRAVEL_SHELL = (
    "图1和图2只锁定同一只2D卡通黄色小龙的脸、蓝色学士帽、蓝腮红、圆滚滚体型和发光节点尾巴。"
    "身体姿态必须和参考图不同：不要一直捧书立正，这一镜换成新的走路、飞翔、挥手、鞠躬或侧身。"
    "图3只锁定场景环境、建筑、光线和空间，不是成片第一帧，不要把图3当静帧证件照接到开头。"
    "不要换脸，不要换配色，不要第二个角色，不要写成真人。"
    "画面里绝对不要出现任何文字、字母、数字、水印、logo、校徽、字幕。"
)
TRAVEL_SCENES: tuple[TravelScene, ...] = (
    {
        "id": "d00",
        "slug": "studio-wave",
        "name": "演播厅·挥手走进",
        "seconds": TRAVEL_SECONDS,
        "source": "00-studio-bg.mp4",
        "prompt": (
            "横向16:9，小龙从画面左侧走进深蓝演播厅，举起一只小爪挥手，微微鞠躬，"
            "再走到中心偏右半身位停下，尾巴轻轻摆，镜头缓慢跟拍，无文字。"
        ),
    },
    {
        "id": "d01",
        "slug": "campus-walk",
        "name": "主楼·银杏路上走来",
        "seconds": TRAVEL_SECONDS,
        "source": "01-campus-dawn.mp4",
        "prompt": (
            "横向16:9，小龙在银杏大道上小跑走来，短腿迈步，抬头看远处主楼，"
            "落叶轻飘，镜头低角度缓慢推进，无旗帜，无校名，无文字。"
        ),
    },
    {
        "id": "d02",
        "slug": "classroom-point",
        "name": "智慧课堂·侧飞指向",
        "seconds": TRAVEL_SECONDS,
        "source": "02-digital-classroom.mp4",
        "prompt": (
            "横向16:9，小龙在巨幕前侧身飞过，一只爪指向屏幕上的无字光网，"
            "身体拉长呈飞行姿态，不捧书，镜头缓慢横移，屏幕不要文字。"
        ),
    },
    {
        "id": "d03",
        "slug": "cosmos-rise",
        "name": "金句空间·沿光柱升",
        "seconds": TRAVEL_SECONDS,
        "source": "03-quote-threshold.mp4",
        "prompt": (
            "横向16:9，小龙伸展身体沿着金色光柱向上飞，回头看巨大透明大脑，"
            "四肢张开，不是站立捧书，镜头从低到高跟随，节点无文字。"
        ),
    },
    {
        "id": "d04",
        "slug": "teacher-offer",
        "name": "讲台·侧身递书",
        "seconds": TRAVEL_SECONDS,
        "source": "04-quote-teachers.mp4",
        "prompt": (
            "横向16:9，小龙侧立在讲台边，双手把蓝书向上递出，身体前倾，"
            "教师只保留虚化背影，镜头缓慢环绕，屏幕与书上都不要文字。"
        ),
    },
    {
        "id": "d05",
        "slug": "junan-fly",
        "name": "均安校园·贴河低飞",
        "seconds": TRAVEL_SECONDS,
        "source": "05a-junan-campus.mp4",
        "prompt": (
            "横向16:9，小龙贴着河面低飞，身体平伸，抬头看白墙校园，镜头从河面拉升跟随，温暖清晨，无校名，无文字。"
        ),
    },
    {
        "id": "d06",
        "slug": "platform-hop",
        "name": "平台光网·跳点",
        "seconds": TRAVEL_SECONDS,
        "source": "06-mind-platform.mp4",
        "prompt": (
            "横向16:9，小龙在深蓝无字光点地图上轻轻跳到下一个发光节点，落地蹲一下再抬头，镜头微距拉远，界面不要文字。"
        ),
    },
    {
        "id": "d08",
        "slug": "signing-paw",
        "name": "签约桌·落爪",
        "seconds": TRAVEL_SECONDS,
        "source": "08-signing.mp4",
        "prompt": (
            "横向16:9，小龙爬上桌面，一只爪轻轻按在红色封皮上，身体前倾，"
            "抬头微笑，封皮和桌牌都是纯色无字，镜头缓慢推近。"
        ),
    },
    {
        "id": "d09",
        "slug": "network-soar",
        "name": "夜景光网·穿线",
        "seconds": TRAVEL_SECONDS,
        "source": "09c-junan-model.mp4",
        "prompt": ("横向16:9，小龙沿着校园夜景金色连线向前飞，身体拉直，尾巴当舵，镜头升高跟随，无文字，无logo。"),
    },
    {
        "id": "d10",
        "slug": "closing-bow",
        "name": "收束·聚光鞠躬",
        "seconds": TRAVEL_SECONDS,
        "source": "10-closing.mp4",
        "prompt": (
            "横向16:9，金色光粒汇向小龙，它双手合在胸前轻轻鞠躬，再抬头点头，左右留标识安全区，镜头极缓慢推近，无文字。"
        ),
    },
    {
        "id": "dt1",
        "slug": "vein-ride",
        "name": "转场·乘光脉",
        "seconds": TRAVEL_SECONDS,
        "source": "t1-gold-vein.mp4",
        "prompt": (
            "横向16:9，小龙顺着金色光脉往前冲，身体几乎平贴光带，"
            "短腿向后，镜头跟随平稳推进，沿途导图只有圆点连线，无文字。"
        ),
    },
)
