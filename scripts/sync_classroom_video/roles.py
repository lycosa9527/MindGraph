"""Discover every green-screen mascot still under Pictures/mascots."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from scripts.sync_classroom_video.paths import MASCOTS_DIR, SKIP_FOLDERS, STILL_NAME


class RoleStill(TypedDict):
    """One keyed identity still used as a Wan reference image."""

    folder: str
    slug: str
    label: str
    lock: str
    still: Path


ROLE_META: dict[str, tuple[str, str, str]] = {
    "black-cat-mascot": (
        "black",
        "黑猫",
        "全身黑色短绒毛，圆滚滚短腿站立，大圆玻璃眼带高光，红白格子小围巾，短尾巴，粉色小鼻头。",
    ),
    "white-cat-mascot": (
        "white",
        "白猫",
        "雪白长毛，半眯绿色玻璃眼，粗黑上挑眼线，黑色细项圈加金色小爱心吊坠，耳上金环。",
    ),
    "siamese-cat-mascot": (
        "siamese",
        "暹罗猫",
        "楔形头，斜杏仁蓝眼，黑色圆框眼镜，奶油色身体，巧克力四肢和尾巴，浅薄荷细项圈。",
    ),
    "raven-teacher-mascot": (
        "raven",
        "乌鸦",
        "3D动画乌鸦吉祥物，直立短腿，橙色喙，深色羽毛，与猫同一画风，用翅膀做事。",
    ),
    "schnauzer-professor": (
        "mentor",
        "雪纳瑞导师",
        "3D动画雪纳瑞教授吉祥物，与猫同一画风，站立授课，不要写成真人。",
    ),
}


def discover_roles(root: Path | None = None) -> list[RoleStill]:
    """Return every folder that still has a front green-screen still."""
    base = root if root is not None else MASCOTS_DIR
    if not base.is_dir():
        raise RuntimeError(f"mascots folder missing: {base}")
    roles: list[RoleStill] = []
    for folder in sorted(path for path in base.iterdir() if path.is_dir()):
        if folder.name in SKIP_FOLDERS:
            continue
        still = folder / STILL_NAME
        if not still.is_file() or still.stat().st_size < 64:
            continue
        slug, label, lock = ROLE_META.get(
            folder.name,
            (folder.name, folder.name, "3D动画吉祥物，与其他角色同一画风。"),
        )
        roles.append(
            {
                "folder": folder.name,
                "slug": slug,
                "label": label,
                "lock": lock,
                "still": still,
            }
        )
    if not roles:
        raise RuntimeError(f"no green-screen stills in {base}")
    return roles


def identity_shell(roles: list[RoleStill]) -> str:
    """Lock each reference image as identity only, never the opening frame."""
    lines = [
        (
            "以下参考图只锁定角色脸、毛色、服装和体型，不是成片第一帧，"
            "不是分镜底板。禁止把参考图、绿幕、证件照、全身静帧接到视频开头。"
            "成片必须从极简教室第一镜直接开始。"
        )
    ]
    for index, role in enumerate(roles, start=1):
        lines.append(f"图{index}是{role['label']}：{role['lock']}")
    return "".join(lines)
