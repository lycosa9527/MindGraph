"""User-facing notices when generate_dingtalk library save is skipped."""

from __future__ import annotations

from typing import Literal, Optional

LibrarySaveSkipReason = Literal[
    "limit_reached",
    "unbound_staff",
    "no_user",
    "save_error",
]
NoticeAudience = Literal["dify", "dingtalk", "mindmate"]


def _use_english(language: str) -> bool:
    return (language or "zh").strip().lower().startswith("en")


def library_save_limit_notice(language: str) -> str:
    """Return user-facing notice when diagram library quota is full."""
    if _use_english(language):
        return "Diagram library is full. Delete old diagrams in MindGraph and try again."
    return "图库已满，请在 MindGraph 删除旧图后再试。"


def library_save_user_notice(
    reason: Optional[str],
    language: str,
    *,
    audience: NoticeAudience = "dify",
) -> str:
    """Return a short user-facing line for a library save skip reason."""
    if not reason:
        return ""
    if reason == "limit_reached":
        return library_save_limit_notice(language)
    use_en = _use_english(language)
    if reason == "unbound_staff":
        if audience == "dingtalk":
            if use_en:
                return (
                    "Diagram preview only — open MindGraph on the web, go to Account info "
                    "→ Link DingTalk, complete the QR bind, then regenerate to save and "
                    "edit in canvas."
                )
            return (
                "导图仅预览，未保存到图库。请在 MindGraph 网页「账户信息 → 绑定钉钉」"
                "完成绑定后重新生成，即可在画布中编辑。"
            )
        if use_en:
            return (
                "Diagram preview only — bind DingTalk in MindGraph account settings, "
                "then regenerate to save and edit in canvas."
            )
        return "导图仅预览，未保存到图库。请在 MindGraph 账户信息中绑定钉钉后重新生成，即可在画布中编辑。"
    if reason == "no_user":
        if audience == "mindmate":
            if use_en:
                return (
                    "Diagram preview only — could not save to your library automatically. "
                    "Try regenerating; if it persists, contact your administrator."
                )
            return "导图仅预览，未能自动保存到图库。请重新生成；若仍失败请联系管理员。"
        if audience == "dingtalk":
            if use_en:
                return (
                    "Diagram preview only — not saved to your library. "
                    "Please contact your school administrator to verify MindBot configuration."
                )
            return "导图仅预览，未保存到图库。请联系学校管理员检查 MindBot 配置。"
        if use_en:
            return (
                "Diagram preview only — sign in and ensure the Dify tool sends "
                "X-MG-Dify-User, then regenerate to save and edit in canvas."
            )
        return "导图仅预览，未保存到图库。请登录并确保 Dify 工具传递 X-MG-Dify-User 后重新生成，即可在画布中编辑。"
    if reason == "save_error":
        if audience == "mindmate":
            if use_en:
                return "Diagram preview only — library save failed. Please regenerate."
            return "导图仅预览，图库保存失败，请重新生成。"
        if use_en:
            return "Diagram preview only — library save failed. Please regenerate."
        return "导图仅预览，图库保存失败，请重新生成。"
    return ""


def library_save_skip_user_notice(reason: Optional[str], language: str) -> str:
    """Dify markdown notice (excludes limit_reached — use library_save_limit_notice)."""
    if not reason or reason == "limit_reached":
        return ""
    return library_save_user_notice(reason, language, audience="dify")
