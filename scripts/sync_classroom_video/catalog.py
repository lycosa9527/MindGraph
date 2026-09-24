"""Silent 16:9 classroom storyboard for Wan 3.0 video-prime."""

from __future__ import annotations

from typing import TypedDict

from scripts.sync_classroom_video.roles import RoleStill, identity_shell

RESOLUTION = "1080P"
RATIO = "16:9"
SET_LOCK = (
    "横向16:9，1080P，30fps，3D动画电影质感。"
    "极简教室：环形木桌、黑板、椅子、侧窗，暖黄顶光冷蓝窗光。"
    "五个角色必须同时保持身份：雪纳瑞导师、黑猫、白猫、戴眼镜的暹罗猫、乌鸦。"
    "不要人类身体，不要换脸，不要换毛色，不要合并角色。"
    "无对白无文字无字幕，角色嘴始终闭合。黑板、报纸、纸团、墙面、桌面只放抽象图形。"
)
NEGATIVE = (
    "绿幕,绿背景,参考静帧,证件照,全身站立开场,字幕,水印,可读文字,汉字,英文,数字,"
    "对话框,开口说话,人类身体,真人,换脸,换毛色,多余肢体,低分辨率,slideshow,jump cut"
)


class ClassroomClip(TypedDict):
    """One silent classroom beat."""

    id: str
    slug: str
    name: str
    seconds: int
    prompt: str


CLIPS: tuple[ClassroomClip, ...] = (
    {
        "id": "01",
        "slug": "sync-class",
        "name": "同步课堂 + 黑猫分心",
        "seconds": 18,
        "prompt": (
            "低角度缓慢推轨，前景桌面，背景黑板。导师在黑板画抽象节点。"
            "白猫、暹罗猫、乌鸦坐直，眼睛跟粉笔移动，头顶透明气泡同步脉动。"
            "黑猫装认真身体前倾，眼睛飘忽，头顶气泡快速切换烤鱼鸡腿、游戏手柄、枕头月亮，"
            "舔嘴流口水，虚空按键，打哈欠。乌鸦用翅膀推，黑猫惊醒假点头。"
            "导师停笔扫视，黑猫坐直。一条连续慢推镜头。"
        ),
    },
    {
        "id": "02",
        "slug": "empty-node",
        "name": "导师画导图留空",
        "seconds": 12,
        "prompt": (
            "黑板前中景缓慢横移。导师画中心圆、三条分支、三个空节点。"
            "白猫贴白圈点头，暹罗猫贴蓝圈看乌鸦，乌鸦贴黑圈用翅膀抚平。"
            "每贴一个头顶气泡亮。最后空节点被粉笔圈住停住。"
            "黑猫趴桌脸贴桌面，尾巴垂，眼睛慢慢看空节点。"
        ),
    },
    {
        "id": "03",
        "slug": "question-bubble",
        "name": "提问泡泡",
        "seconds": 8,
        "prompt": (
            "导师中景停笔，双手轻推吹出大泡泡，泡泡里旋转问号光斑，"
            "飘到桌中央碰黑猫鼻尖。黑猫吓后仰，爪子乱挥差点跌下椅子。"
            "所有人转头看它。导师抬手示意回答。"
        ),
    },
    {
        "id": "04a",
        "slug": "wrong-answers-a",
        "name": "瞎答前三击",
        "seconds": 10,
        "prompt": (
            "手持快切前三击。黑猫跳桌举鱼骨头自信咧嘴，红叉，白猫空白报纸啪打头缩脖。"
            "黑猫按空气手柄得意，红叉，啪，头歪。"
            "黑猫抱枕头懒洋洋，红叉，啪，棉絮飞。"
        ),
    },
    {
        "id": "04b",
        "slug": "wrong-answers-b",
        "name": "瞎答后两击",
        "seconds": 10,
        "prompt": (
            "手持快切后两击。黑猫乱画歪箭头，红叉，白猫空白报纸啪，黑猫转半圈粉笔脱手。"
            "黑猫举空白纸团从得意变心虚，红叉，啪，冒星趴桌。"
            "白猫收报纸呼气，暹罗猫捂嘴，乌鸦扶额，导师叹气。"
        ),
    },
    {
        "id": "05",
        "slug": "lightbulb",
        "name": "灯泡顿悟",
        "seconds": 10,
        "prompt": (
            "黑猫眼睛特写快速推近。头顶鱼、手柄、枕头气泡快速旋转碰撞后碎裂。"
            "黑猫瞳孔缩后放，耳朵竖起，胡须抖，灯泡叮亮。"
            "慢慢坐直，爪子抓桌沿，呼吸变快，盯住黑板空节点。背景虚化。"
        ),
    },
    {
        "id": "06",
        "slug": "fill-circle",
        "name": "黑猫填圈",
        "seconds": 12,
        "prompt": (
            "环绕镜头从黑猫到黑板。黑猫跳下椅子踉跄，走到黑板前，回头看导师，导师点头。"
            "黑猫在最后空节点画彩色圈，画得略歪，连接线发光。退后两步尾巴竖起。"
            "导图节点依次发光。白猫、暹罗猫、乌鸦睁大眼前倾。导师抱臂满意点头。"
        ),
    },
    {
        "id": "07",
        "slug": "table-run",
        "name": "绕桌跑",
        "seconds": 15,
        "prompt": (
            "稳定器环绕跟拍，最后慢动作。黑猫兴奋绕桌跑，跳上椅背，尾巴高竖耳朵后贴。"
            "白猫笑，暹罗猫拍手，乌鸦拍翅膀。导师黑板前微笑，粉笔灰飘。"
            "黑猫差点滑倒爪子撑桌继续跑，最后跳回座位喘气，"
            "头顶气泡与所有人同步发光。定格。"
        ),
    },
)


def clip_by_id(clip_id: str) -> ClassroomClip:
    """Look up 01 or 01-sync-class."""
    needle = clip_id.strip()
    for clip in CLIPS:
        packed = f"{clip['id']}-{clip['slug']}"
        if needle in (clip["id"], packed):
            return clip
    raise ValueError(f"Unknown classroom clip: {clip_id}")


def select_clips(raw_ids: str | None) -> list[ClassroomClip]:
    """Parse comma ids, or return the full storyboard."""
    if not raw_ids:
        return list(CLIPS)
    return [clip_by_id(item.strip()) for item in raw_ids.split(",") if item.strip()]


def clip_stem(clip: ClassroomClip) -> str:
    """Work-dir and desktop filename without suffix."""
    return f"{clip['id']}-{clip['slug']}"


def clip_prompt(clip: ClassroomClip, roles: list[RoleStill]) -> str:
    """Identity lock + classroom set + one beat."""
    return f"{identity_shell(roles)}{SET_LOCK}{clip['prompt']} 不要出现：{NEGATIVE}"
