"""Local scratch and Desktop folders for 智联均安 Wan 3.0 clips."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
WORK_DIR = PACKAGE_DIR / ".work"
TASKS_PATH = WORK_DIR / "tasks.json"
AGENT_REF_DIR = WORK_DIR / "agent-ref"
DESKTOP_DIR = Path("/mnt/c/Users/roywa/Desktop/均安宣传片")
OLD_AI_DIR = DESKTOP_DIR / "AI空镜-旧版"
AGENT_DIR = DESKTOP_DIR / "AI吉祥物"
TRAVEL_DIR = DESKTOP_DIR / "AI吉祥物-穿景"
INTRO_DIR = DESKTOP_DIR / "AI吉祥物-自我介绍"
SPEECH_DIR = DESKTOP_DIR / "AI分镜-演讲稿"
SPEECH_SOURCE = DESKTOP_DIR / "纯演讲稿_v2.mp4"
SCENE_REF_DIR = WORK_DIR / "scene-ref"
AGENT_SOURCE = DESKTOP_DIR / "微信视频2026-09-20_102908_167.mp4"
