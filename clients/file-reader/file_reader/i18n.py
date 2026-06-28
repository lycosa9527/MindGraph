"""Bilingual UI strings (English / Chinese) with system locale detection."""

from __future__ import annotations

import locale
import sys
from dataclasses import dataclass
from typing import Dict, Mapping

try:
    import ctypes
except ImportError:
    ctypes = None

SUPPORTED = ("en", "zh")

_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "app.title": "MindGraph File Reader",
        "header.not_signed_in": "Not signed in",
        "auth.title": "Connect account",
        "auth.server": "Server",
        "auth.token": "API token (mgat_)",
        "auth.phone": "Phone",
        "auth.connect": "Connect & save",
        "auth.clear": "Clear saved credentials",
        "auth.connecting": "Connecting…",
        "auth.saved": "Credentials saved (encrypted on this PC)",
        "auth.cleared": "Saved credentials removed from this PC.",
        "auth.clear_confirm_title": "Clear credentials?",
        "auth.clear_confirm_body": "Remove the saved API token and phone from this computer?",
        "auth.enter_credentials": "Enter API token and phone, then connect.",
        "packages.title": "Document Summary packages",
        "packages.overlay": "Connect your account to view packages",
        "packages.empty": "No packages yet — open Document Summary on a mind map to create one.",
        "packages.count": "{count} package(s)",
        "packages.sources": "{completed}/{total} sources",
        "packages.linked_diagram": " · linked diagram",
        "packages.selected": "Selected: {name}",
        "packages.untitled": "Untitled package",
        "live.title": "Live website sessions",
        "live.overlay": "Connect your account to detect open sessions on the website",
        "live.empty": (
            "Open Document Summary → Chat history on the website. "
            "When the pairing code appears, the live session shows here automatically."
        ),
        "live.badge": "LIVE",
        "live.waiting": "Waiting on website",
        "live.expires": "{minutes} min left",
        "live.count": "{count} live session(s)",
        "live.selected": "Linked to website session · {name}",
        "live.polling": "Watching for website sessions…",
        "live.diagram": "Diagram: {diagram}",
        "send.title": "Send chat export",
        "send.platform": "Platform",
        "send.wechat": "WeChat",
        "send.dingtalk": "DingTalk",
        "send.folder": "Export folder",
        "send.browse": "Browse",
        "send.chat_title": "Chat title",
        "send.default_title": "WeChat chat",
        "send.button": "Send to website session",
        "send.sending": "Sending…",
        "send.file_row": "{title} ({count} msgs)",
        "dialog.title": "MindGraph File Reader",
        "dialog.pick_session": "Select a live website session first.",
        "dialog.pick_file": "Select a chat export file first.",
        "notify.connected": "Connected as {name}",
        "notify.sent": "Sent! The website should show your chat history received.",
        "notify.sent_detail": "Document #{id} is indexing",
        "status.offline.primary": "Not connected",
        "status.offline.secondary": "Enter your API token and phone, then click Connect & save.",
        "status.connecting.primary": "Connecting to MindGraph…",
        "status.connecting.secondary": "Verifying your API token and account.",
        "status.connected.primary": "Connected as {name}",
        "status.connected.secondary": "Linked to {server} · watching for Document Summary sessions.",
        "status.wait_web.primary": "Waiting for a website pairing session",
        "status.wait_web.secondary": (
            "On MindGraph, open your mind map → Document Summary (File Center) → "
            "Chat history tab. A live session will appear here when the pairing code shows."
        ),
        "status.sessions.primary": "{count} live session(s) on the website",
        "status.sessions.secondary": "Click a session card above, then choose a chat export to send.",
        "status.session.primary": "Session selected · {package}",
        "status.session.secondary_diagram": "Diagram: {diagram} · pairing code {code}",
        "status.session.secondary_no_diagram": "No diagram linked · pairing code {code}",
        "status.ready.primary": "Ready to send · {file}",
        "status.ready.secondary": "{package} · Diagram: {diagram}",
        "status.ready.secondary_no_diagram": "{package} · no diagram linked",
        "status.sending.primary": "Sending chat export…",
        "status.sending.secondary": "Uploading to {package} on MindGraph.",
        "status.sent.primary": "Chat history received on MindGraph",
        "status.sent.secondary": "Document #{id} is indexing in Document Summary.",
        "status.sent.secondary_generic": "The website should show your chat history received.",
        "status.cleared.primary": "Credentials cleared",
        "status.cleared.secondary": "Sign in again when you want to send another export.",
        "error.credentials_encrypt_failed": "Could not encrypt credentials on this PC.",
        "error.missing_credentials": "API token and account phone are required.",
        "error.server_url_invalid": (
            "Server URL must be https:// on *.mindspringedu.com (or http://localhost for local dev)."
        ),
        "error.network": "Cannot reach the server. Check the URL and your network.",
        "error.auth_failed": "Sign-in failed. Check your API token and phone number.",
        "error.profile_failed": "Could not load your profile.",
        "error.feature_disabled": (
            "Knowledge Space is disabled on this server. "
            "Ask your admin to set FEATURE_KNOWLEDGE_SPACE=True and deploy the latest backend."
        ),
        "error.api_missing": (
            "This server does not support Document Summary yet. Deploy the latest MindGraph backend."
        ),
        "error.packages_failed": "Could not load packages: {detail}",
        "error.connection_failed": "Connection failed.",
        "error.pairing_failed": "Could not start pairing: {detail}",
        "error.upload_failed": "Upload failed: {detail}",
        "error.no_content": "No chat content to send.",
        "error.parse_file": "Could not read the export file: {detail}",
        "error.org_locked": "Your organization account is locked. Contact support.",
        "error.rate_limit": "Too many requests. Wait a few minutes and try again.",
        "error.server": "Server error ({status}). Try again later.",
        "error.unknown": "{detail}",
    },
    "zh": {
        "app.title": "MindGraph 文件读取工具",
        "header.not_signed_in": "未登录",
        "auth.title": "连接账户",
        "auth.server": "服务器",
        "auth.token": "API 令牌 (mgat_)",
        "auth.phone": "手机号",
        "auth.connect": "连接并保存",
        "auth.clear": "清除已保存凭据",
        "auth.connecting": "正在连接…",
        "auth.saved": "凭据已保存（已在本机加密）",
        "auth.cleared": "已从此电脑移除保存的凭据。",
        "auth.clear_confirm_title": "清除凭据？",
        "auth.clear_confirm_body": "是否从此电脑移除已保存的 API 令牌和手机号？",
        "auth.enter_credentials": "请输入 API 令牌和手机号后连接。",
        "packages.title": "文档总结资料包",
        "packages.overlay": "请先连接账户以查看资料包",
        "packages.empty": "暂无资料包 — 请在思维导图上打开「文档总结」创建一个。",
        "packages.count": "{count} 个资料包",
        "packages.sources": "{completed}/{total} 个来源",
        "packages.linked_diagram": " · 已关联导图",
        "packages.selected": "已选择：{name}",
        "packages.untitled": "未命名资料包",
        "live.title": "网站实时会话",
        "live.overlay": "连接账户以检测网站上打开的会话",
        "live.empty": "请在网站打开「文档总结 → 聊天记录」。配对码出现后，实时会话会自动显示在此。",
        "live.badge": "在线",
        "live.waiting": "网站等待上传",
        "live.expires": "剩余 {minutes} 分钟",
        "live.count": "{count} 个实时会话",
        "live.selected": "已关联网站会话 · {name}",
        "live.polling": "正在监听网站会话…",
        "live.diagram": "导图：{diagram}",
        "send.title": "发送聊天记录",
        "send.platform": "平台",
        "send.wechat": "微信",
        "send.dingtalk": "钉钉",
        "send.folder": "导出文件夹",
        "send.browse": "浏览",
        "send.chat_title": "聊天标题",
        "send.default_title": "微信聊天",
        "send.button": "发送到网站会话",
        "send.sending": "正在发送…",
        "send.file_row": "{title}（{count} 条消息）",
        "dialog.title": "MindGraph 文件读取工具",
        "dialog.pick_session": "请先选择一个网站实时会话。",
        "dialog.pick_file": "请先选择一个聊天导出文件。",
        "notify.connected": "已连接：{name}",
        "notify.sent": "已发送！网站上的文档总结应显示「已收到聊天记录」。",
        "notify.sent_detail": "文档 #{id} 正在索引",
        "status.offline.primary": "未连接",
        "status.offline.secondary": "请输入 API 令牌和手机号，然后点击「连接并保存」。",
        "status.connecting.primary": "正在连接 MindGraph…",
        "status.connecting.secondary": "正在验证 API 令牌和账户。",
        "status.connected.primary": "已连接：{name}",
        "status.connected.secondary": "已关联 {server} · 正在监听文档总结会话。",
        "status.wait_web.primary": "等待网站配对会话",
        "status.wait_web.secondary": (
            "请在 MindGraph 打开思维导图 → 文档总结（文件中心）→ "
            "聊天记录标签页。出现配对码后，实时会话会自动显示在上方。"
        ),
        "status.sessions.primary": "网站上有 {count} 个实时会话",
        "status.sessions.secondary": "请点击上方会话卡片，然后选择要发送的聊天导出文件。",
        "status.session.primary": "已选会话 · {package}",
        "status.session.secondary_diagram": "导图：{diagram} · 配对码 {code}",
        "status.session.secondary_no_diagram": "未关联导图 · 配对码 {code}",
        "status.ready.primary": "可以发送 · {file}",
        "status.ready.secondary": "{package} · 导图：{diagram}",
        "status.ready.secondary_no_diagram": "{package} · 未关联导图",
        "status.sending.primary": "正在发送聊天记录…",
        "status.sending.secondary": "正在上传到 MindGraph 的 {package}。",
        "status.sent.primary": "MindGraph 已收到聊天记录",
        "status.sent.secondary": "文档 #{id} 正在文档总结中索引。",
        "status.sent.secondary_generic": "网站应显示「已收到聊天记录」。",
        "status.cleared.primary": "凭据已清除",
        "status.cleared.secondary": "需要再次发送时，请重新登录。",
        "error.credentials_encrypt_failed": "无法在本机加密保存凭据。",
        "error.missing_credentials": "需要 API 令牌和账户手机号。",
        "error.server_url_invalid": (
            "服务器地址须为 https:// 且属于 *.mindspringedu.com（本地开发可使用 http://localhost）。"
        ),
        "error.network": "无法连接服务器，请检查地址和网络。",
        "error.auth_failed": "登录失败，请检查 API 令牌和手机号。",
        "error.profile_failed": "无法加载用户资料。",
        "error.feature_disabled": (
            "此服务器未启用知识空间。请联系管理员设置 FEATURE_KNOWLEDGE_SPACE=True 并部署最新后端。"
        ),
        "error.api_missing": "此服务器尚不支持文档总结，请部署最新 MindGraph 后端。",
        "error.packages_failed": "无法加载资料包：{detail}",
        "error.connection_failed": "连接失败。",
        "error.pairing_failed": "无法开始配对：{detail}",
        "error.upload_failed": "上传失败：{detail}",
        "error.no_content": "没有可发送的聊天内容。",
        "error.parse_file": "无法读取导出文件：{detail}",
        "error.org_locked": "您的机构账户已锁定，请联系支持。",
        "error.rate_limit": "请求过于频繁，请稍后再试。",
        "error.server": "服务器错误（{status}），请稍后重试。",
        "error.unknown": "{detail}",
    },
}


def detect_system_locale() -> str:
    """Pick zh for Chinese Windows/UI locale, otherwise en."""
    if sys.platform == "win32" and ctypes is not None:
        try:
            windll_obj = getattr(ctypes, "windll", None)
            if windll_obj is None:
                raise AttributeError("ctypes.windll unavailable")
            lang_id = windll_obj.kernel32.GetUserDefaultUILanguage()
            if (lang_id & 0x3FF) == 0x04:
                return "zh"
        except (OSError, AttributeError):
            pass
    try:
        loc = locale.getlocale()[0] or ""
    except (ValueError, locale.Error):
        loc = ""
    if loc.lower().startswith("zh"):
        return "zh"
    return "en"


@dataclass
class I18n:
    """Lightweight translator for the desktop UI."""

    locale: str

    @classmethod
    def auto(cls) -> "I18n":
        """Build translator from OS locale."""
        return cls(detect_system_locale())

    def translate(self, key: str, **kwargs: object) -> str:
        """Return localized string; falls back to English."""
        bucket = _STRINGS.get(self.locale) or _STRINGS["en"]
        template = bucket.get(key) or _STRINGS["en"].get(key) or key
        if kwargs:
            try:
                return template.format(**kwargs)
            except (KeyError, ValueError):
                return template
        return template

    def messages(self) -> Mapping[str, str]:
        """All strings for the active locale."""
        return _STRINGS.get(self.locale, _STRINGS["en"])
