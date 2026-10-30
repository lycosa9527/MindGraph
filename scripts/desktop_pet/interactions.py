"""Ten two-mascot scenes. Partners are fixed so the review set does not reshuffle."""

from __future__ import annotations

from typing import TypedDict

from scripts.desktop_pet.mascots import GREEN_SCREEN, mascot_by_slug


class PairScene(TypedDict):
    """One clip with two full-body mascots on the green screen."""

    id: str
    slug: str
    name: str
    left: str
    right: str
    prompt: str


PAIRS: tuple[PairScene, ...] = (
    {
        "id": "01",
        "slug": "one-cabinet",
        "name": "一台街机",
        "left": "black",
        "right": "white",
        "prompt": "两人共用一台矮街机。黑猫晚半拍地猛按，白猫只精确按一下就赢了，臭脸看着他。",
    },
    {
        "id": "02",
        "slug": "inspect-robot",
        "name": "检查机器人",
        "left": "black",
        "right": "siamese",
        "prompt": "黑猫把小机器人举给暹罗猫。暹罗猫穿实验服，围着它看一圈，在记录板上打勾。黑猫高兴得跳起来。",
    },
    {
        "id": "03",
        "slug": "lesson-arcade",
        "name": "教他玩",
        "left": "raven",
        "right": "black",
        "prompt": "乌鸦老师展开翅膀示范街机按钮。黑猫看了两秒才扑上去按，按得太重，街机晃，乌鸦用翅膀扶住。",
    },
    {
        "id": "04",
        "slug": "thesis",
        "name": "看发明",
        "left": "schnauzer",
        "right": "black",
        "prompt": "雪纳瑞教授端正地看黑猫递来的小发明，点一下头，把一枚星星贴纸贴到发明上。黑猫把发明举高。",
    },
    {
        "id": "05",
        "slug": "still-checking",
        "name": "还在查",
        "left": "white",
        "right": "siamese",
        "prompt": "白猫不耐烦地敲爪子。暹罗猫仍然低头检查一颗螺丝，查完才举起通过牌。白猫臭脸接过牌子。",
    },
    {
        "id": "06",
        "slug": "unimpressed",
        "name": "无动于衷",
        "left": "raven",
        "right": "white",
        "prompt": "乌鸦张开翅膀展示一本发光的大书。白猫看一眼，拨一下毛，把书轻轻推回去。",
    },
    {
        "id": "07",
        "slug": "tea-time",
        "name": "喝茶",
        "left": "white",
        "right": "schnauzer",
        "prompt": "雪纳瑞稳稳倒两杯茶。白猫先拿起杯子看杯沿，嫌弃地转一下杯子，才喝一口。",
    },
    {
        "id": "08",
        "slug": "lab-lesson",
        "name": "实验课",
        "left": "siamese",
        "right": "raven",
        "prompt": "暹罗猫按下测试台绿钮。乌鸦用翅膀指向亮起的灯，像在给全班讲。两人一起看向镜头。",
    },
    {
        "id": "09",
        "slug": "two-inspect",
        "name": "一起看",
        "left": "siamese",
        "right": "schnauzer",
        "prompt": "两人一左一右看同一台小机器。暹罗猫记录，雪纳瑞用短教鞭点一个零件。机器亮绿灯，两人同时点头。",
    },
    {
        "id": "10",
        "slug": "two-teachers",
        "name": "两位老师",
        "left": "raven",
        "right": "schnauzer",
        "prompt": "乌鸦和雪纳瑞并排对一本大书。乌鸦用翅膀翻页，雪纳瑞用爪子压住页角。讲完两人一起浅鞠躬。",
    },
)


def pair_by_id(raw: str) -> PairScene:
    """Resolve ``01`` or ``01-one-cabinet``."""
    key = raw.strip()
    for scene in PAIRS:
        if key in {scene["id"], f"{scene['id']}-{scene['slug']}"}:
            return scene
    raise KeyError(raw)


def pair_clip_id(scene: PairScene) -> str:
    """Filename stem such as ``01-one-cabinet``."""
    return f"{scene['id']}-{scene['slug']}"


def pair_prompt(scene: PairScene) -> str:
    """Both identities, then the shared scene, on a flat green field."""
    left = mascot_by_slug(scene["left"])
    right = mascot_by_slug(scene["right"])
    return (
        "画面里只有这两只角色，都全身入镜，不要第三只。"
        f"左边是{left['label']}：{left['identity']}{left['manner']}平时的衣服是{left['default_outfit']}"
        f"右边是{right['label']}：{right['identity']}{right['manner']}平时的衣服是{right['default_outfit']}"
        f"{scene['prompt']}{GREEN_SCREEN}"
    )
