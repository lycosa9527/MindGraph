"""Right-side WeChat probe panel with Start button and detailed status."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Dict, Literal, Optional

from file_reader.i18n import I18n
from file_reader.theme import (
    ACCENT,
    ACCENT_HOVER,
    BG_CARD,
    BORDER,
    ERROR,
    FONT_BODY,
    FONT_CAPTION,
    TEXT_MUTED,
    TEXT_PRIMARY,
)
from file_reader.dingtalk.local import DingTalkLocalStatus
from file_reader.dingtalk.probe import DingTalkProbeReport
from file_reader.wechat.debug_log import debug_log_path_display
from file_reader.wechat.local import WeChatLocalStatus
from file_reader.wechat.probe import WeChatProbeReport
from file_reader.wecom.debug_log import debug_log_path_display as wecom_debug_log_path_display
from file_reader.wecom.local import WeComLocalStatus
from file_reader.wecom.probe import WeComProbeReport

_LineKind = Literal["heading", "bullet", "step", "muted", "error"]


@dataclass(frozen=True)
class _DetailLine:
    text: str
    kind: _LineKind = "bullet"


class PlatformStatusPanel(tk.Frame):
    """WeChat / DingTalk local client readiness and manual key probe."""

    def __init__(
        self,
        master: tk.Misc,
        i18n: I18n,
        *,
        on_wechat_start: Optional[Callable[[], None]] = None,
        on_dingtalk_start: Optional[Callable[[], None]] = None,
        on_wecom_start: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(master, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1, width=268)
        self.pack_propagate(False)
        self._i18n = i18n
        self._platform = "wechat"
        self._on_wechat_start = on_wechat_start
        self._on_dingtalk_start = on_dingtalk_start
        self._on_wecom_start = on_wecom_start
        self._probing = False
        self._saved_keys_available = False
        self._probe_tokens: Dict[str, int] = {"wechat": 0, "dingtalk": 0, "wecom": 0}

        inner = tk.Frame(self, bg=BG_CARD, padx=14, pady=14)
        inner.pack(fill="both", expand=True)

        self._start_btn = tk.Button(
            inner,
            text="",
            command=self._handle_start,
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT_HOVER,
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=8,
            font=FONT_BODY,
            cursor="hand2",
        )
        self._start_btn.pack(fill="x", pady=(0, 10))

        self._detail = tk.Text(
            inner,
            height=12,
            wrap="word",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=FONT_CAPTION,
            relief="flat",
            highlightthickness=0,
            padx=0,
            pady=0,
        )
        self._detail.pack(fill="both", expand=True)
        self._detail.tag_configure("heading", font=(FONT_CAPTION[0], FONT_CAPTION[1], "bold"))
        self._detail.tag_configure("muted", foreground=TEXT_MUTED)
        self._detail.tag_configure("error", foreground=ERROR)
        self._detail.configure(state="disabled")

        self._hint = tk.Label(
            inner,
            bg=BG_CARD,
            fg=TEXT_MUTED,
            font=FONT_CAPTION,
            anchor="w",
            justify="left",
            wraplength=220,
        )
        self._hint.pack(fill="x", pady=(10, 0))
        self.apply_texts()

    def apply_texts(self) -> None:
        """Refresh static labels for locale."""
        self._refresh_start_button()
        if self._platform == "dingtalk":
            self._hint.configure(text=self._i18n.translate("platform.hint.dingtalk_connecting"))
        elif self._platform == "wecom":
            if self._saved_keys_available:
                self._hint.configure(text=self._i18n.translate("platform.hint.wecom_cached"))
            else:
                self._hint.configure(text=self._i18n.translate("platform.hint.wecom_connecting"))
        elif self._saved_keys_available:
            self._hint.configure(text=self._i18n.translate("platform.hint.wechat_cached"))
        else:
            self._hint.configure(text=self._i18n.translate("platform.hint"))

    def _start_button_key(self) -> str:
        if self._platform == "dingtalk":
            if self._probing:
                return "platform.dingtalk.starting"
            return "platform.dingtalk.start"
        if self._platform == "wecom":
            if self._probing:
                if self._saved_keys_available:
                    return "platform.wecom.reading"
                return "platform.wecom.starting"
            if self._saved_keys_available:
                return "platform.wecom.read_db"
            return "platform.wecom.start"
        if self._probing:
            if self._saved_keys_available:
                return "platform.wechat.reading"
            return "platform.wechat.starting"
        if self._saved_keys_available:
            return "platform.wechat.read_db"
        return "platform.wechat.start"

    def _refresh_start_button(self) -> None:
        if self._platform in ("dingtalk", "wechat", "wecom"):
            self._start_btn.configure(text=self._i18n.translate(self._start_button_key()))
            self._start_btn.pack(fill="x", pady=(0, 10), before=self._detail)
        else:
            self._start_btn.pack_forget()

    def _handle_start(self) -> None:
        if self._probing:
            return
        if self._platform == "wechat" and self._on_wechat_start is not None:
            self._on_wechat_start()
            return
        if self._platform == "dingtalk" and self._on_dingtalk_start is not None:
            self._on_dingtalk_start()
            return
        if self._platform == "wecom" and self._on_wecom_start is not None:
            self._on_wecom_start()

    def set_platform(self, platform: str) -> None:
        """Switch between wechat, dingtalk, and wecom display mode."""
        self._platform = platform
        self._probing = False
        self._saved_keys_available = False
        if platform == "dingtalk":
            self._refresh_start_button()
            self._hint.configure(text=self._i18n.translate("platform.hint.dingtalk_connecting"))
            return
        if platform == "wecom":
            self._refresh_start_button()
            self._hint.configure(text=self._i18n.translate("platform.hint.wecom_connecting"))
            return
        self._refresh_start_button()
        self._hint.configure(text=self._i18n.translate("platform.hint"))

    def set_dingtalk_hint(self, hint_key: str, **params: object) -> None:
        """Update the footer hint for DingTalk mode."""
        if self._platform == "dingtalk":
            self._hint.configure(text=self._i18n.translate(hint_key, **params))

    def set_dingtalk_status(self, status: DingTalkLocalStatus) -> None:
        """Update DingTalk detection rows (no DB decrypt)."""
        if self._platform != "dingtalk" or self._probing:
            return
        self._refresh_start_button()
        self._hint.configure(text=self._dingtalk_footer_hint(status))
        self._set_detail_lines(self._dingtalk_idle_lines(status))

    def set_dingtalk_probing(self, status: DingTalkLocalStatus) -> None:
        """Show in-progress DingTalk DB read."""
        if self._platform != "dingtalk":
            return
        self._probing = True
        self._start_btn.configure(state="disabled")
        self._refresh_start_button()
        self._hint.configure(text=self._i18n.translate("platform.hint.dingtalk_connecting"))
        self._set_detail_lines(self._dingtalk_probing_lines(status))

    def set_dingtalk_probe_result(
        self,
        status: DingTalkLocalStatus,
        report: Optional[DingTalkProbeReport],
    ) -> None:
        """Show completed DingTalk probe outcome."""
        if self._platform != "dingtalk":
            return
        self._probing = False
        self._start_btn.configure(state="normal")
        self._refresh_start_button()
        if report is not None and report.success:
            self._hint.configure(text=self._i18n.translate("platform.hint.dingtalk_live"))
            self._set_detail_lines(self._dingtalk_success_lines(status, report))
            return
        if report is not None and not report.success:
            self._hint.configure(text=self._i18n.translate("platform.hint.dingtalk_failed"))
            self._set_detail_lines(self._dingtalk_failure_lines(status, report))
            return
        self._hint.configure(text=self._dingtalk_footer_hint(status))
        self._set_detail_lines(self._dingtalk_idle_lines(status))

    def _dingtalk_footer_hint(self, status: DingTalkLocalStatus) -> str:
        if status.unlock_ready:
            return self._i18n.translate("platform.hint.dingtalk_ready")
        return self._i18n.translate("platform.dingtalk.hint")

    def _dingtalk_status_section(self, status: DingTalkLocalStatus) -> list[_DetailLine]:
        lines: list[_DetailLine] = [
            _DetailLine(self._i18n.translate("platform.dingtalk.section_status"), "heading"),
        ]
        if status.process_running:
            lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.status_open"), "bullet"))
        else:
            lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.status_closed"), "bullet"))

        if status.data_root is not None:
            folder = status.account_folder_id or status.data_root.name
            lines.append(
                _DetailLine(
                    self._i18n.translate("platform.dingtalk.status_account", folder=folder),
                    "bullet",
                )
            )
            version = status.storage_version or "?"
            lines.append(
                _DetailLine(
                    self._i18n.translate("platform.dingtalk.status_version", version=version),
                    "bullet",
                )
            )
        else:
            lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.not_logged_in"), "bullet"))

        if status.real_uid:
            lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.status_uid_found"), "bullet"))
        else:
            lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.uid_missing"), "error"))

        if status.storage_version == "v3" and not status.salt_present:
            lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.salt_missing"), "error"))

        if not status.db_present:
            lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.db_missing"), "error"))

        return lines

    def _dingtalk_connect_steps(self) -> list[_DetailLine]:
        return [
            _DetailLine(self._i18n.translate("platform.dingtalk.section_next"), "heading"),
            _DetailLine(self._i18n.translate("platform.dingtalk.step_connect"), "step"),
            _DetailLine(self._i18n.translate("platform.dingtalk.step_read_db"), "step"),
            _DetailLine(self._i18n.translate("platform.dingtalk.step_pick_chat"), "step"),
        ]

    def _dingtalk_idle_lines(self, status: DingTalkLocalStatus) -> list[_DetailLine]:
        lines = self._dingtalk_status_section(status)
        if status.unlock_ready:
            lines.extend(self._dingtalk_connect_steps())
        return lines

    def _dingtalk_probing_lines(self, status: DingTalkLocalStatus) -> list[_DetailLine]:
        lines = self._dingtalk_status_section(status)
        lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.section_working"), "heading"))
        lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.probing_read_db"), "bullet"))
        return lines

    def _dingtalk_success_lines(
        self,
        status: DingTalkLocalStatus,
        report: DingTalkProbeReport,
    ) -> list[_DetailLine]:
        lines = self._dingtalk_status_section(status)
        lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.section_done"), "heading"))
        lines.append(
            _DetailLine(
                self._i18n.translate(
                    "platform.dingtalk.success",
                    count=report.session_count,
                    seconds=f"{report.duration_sec:.1f}",
                ),
                "bullet",
            )
        )
        lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.step_pick_chat"), "step"))
        lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.step_upload"), "step"))
        return lines

    def _dingtalk_failure_lines(
        self,
        status: DingTalkLocalStatus,
        report: DingTalkProbeReport,
    ) -> list[_DetailLine]:
        lines = self._dingtalk_status_section(status)
        lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.section_problem"), "heading"))
        lines.append(_DetailLine(self._i18n.translate("platform.dingtalk.decrypt_failed"), "error"))
        if report.error:
            lines.append(_DetailLine(report.error[:160], "error"))
        lines.extend(self._dingtalk_connect_steps())
        return lines

    def set_wecom_hint(self, hint_key: str, **params: object) -> None:
        """Update the footer hint for WeCom mode."""
        if self._platform == "wecom":
            self._hint.configure(text=self._i18n.translate(hint_key, **params))

    def set_wecom_status(
        self,
        status: WeComLocalStatus,
        *,
        saved_keys_available: bool = False,
    ) -> None:
        """Update WeCom detection rows (no DB decrypt)."""
        if self._platform != "wecom" or self._probing:
            return
        self._saved_keys_available = saved_keys_available
        self._refresh_start_button()
        self._hint.configure(text=self._wecom_footer_hint(status, saved_keys_available=saved_keys_available))
        self._set_detail_lines(self._wecom_idle_lines(status, saved_keys_available=saved_keys_available))

    def set_wecom_probing(
        self,
        status: WeComLocalStatus,
        *,
        saved_keys_available: bool = False,
    ) -> None:
        """Show in-progress WeCom DB read."""
        if self._platform != "wecom":
            return
        self._probing = True
        self._saved_keys_available = saved_keys_available
        self._start_btn.configure(state="disabled")
        self._refresh_start_button()
        self._hint.configure(text=self._wecom_probing_footer(saved_keys_available=saved_keys_available))
        self._set_detail_lines(self._wecom_probing_lines(status, saved_keys_available=saved_keys_available))

    def set_wecom_probe_result(
        self,
        status: WeComLocalStatus,
        report: Optional[WeComProbeReport],
        *,
        saved_keys_available: bool = False,
    ) -> None:
        """Show completed WeCom probe outcome."""
        if self._platform != "wecom":
            return
        self._probing = False
        self._saved_keys_available = saved_keys_available
        self._start_btn.configure(state="normal")
        self._refresh_start_button()
        if report is not None and report.success:
            self._hint.configure(text=self._i18n.translate("platform.hint.wecom_live"))
            self._set_detail_lines(self._wecom_success_lines(status, report))
            return
        if report is not None and not report.success:
            self._hint.configure(text=self._i18n.translate("platform.hint.wecom_failed"))
            self._set_detail_lines(self._wecom_failure_lines(status, report))
            return
        self._hint.configure(text=self._wecom_footer_hint(status, saved_keys_available=saved_keys_available))
        self._set_detail_lines(self._wecom_idle_lines(status, saved_keys_available=saved_keys_available))

    def _wecom_footer_hint(self, status: WeComLocalStatus, *, saved_keys_available: bool) -> str:
        if saved_keys_available:
            return self._i18n.translate("platform.hint.wecom_cached")
        if status.unlock_ready:
            return self._i18n.translate("platform.hint.wecom_ready")
        return self._i18n.translate("platform.wecom.hint")

    def _wecom_probing_footer(self, *, saved_keys_available: bool) -> str:
        if saved_keys_available:
            return self._i18n.translate("platform.hint.wecom_cached")
        return self._i18n.translate("platform.hint.wecom_connecting")

    def _wecom_status_section(self, status: WeComLocalStatus) -> list[_DetailLine]:
        lines: list[_DetailLine] = [
            _DetailLine(self._i18n.translate("platform.wecom.section_status"), "heading"),
        ]
        if status.process_running:
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.status_open"), "bullet"))
        else:
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.status_closed"), "bullet"))

        if status.data_root is not None:
            label = status.account_label or status.data_root.name
            lines.append(
                _DetailLine(
                    self._i18n.translate("platform.wecom.status_account", folder=label),
                    "bullet",
                )
            )
            lines.append(
                _DetailLine(
                    self._i18n.translate(
                        "platform.wecom.status_db_count",
                        count=status.encrypted_db_count,
                    ),
                    "bullet",
                )
            )
        else:
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.not_logged_in"), "bullet"))

        if not status.local_dbs_present:
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.db_missing"), "error"))
        elif not status.process_running:
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.process_missing"), "error"))

        return lines

    def _wecom_connect_steps(self, *, saved_keys_available: bool) -> list[_DetailLine]:
        lines = [_DetailLine(self._i18n.translate("platform.wecom.section_next"), "heading")]
        if saved_keys_available:
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.status_keys_saved"), "bullet"))
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.step_auto_load"), "step"))
        else:
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.step_admin"), "step"))
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.step_connect"), "step"))
        lines.append(_DetailLine(self._i18n.translate("platform.wecom.step_read_db"), "step"))
        lines.append(_DetailLine(self._i18n.translate("platform.wecom.step_pick_chat"), "step"))
        return lines

    def _wecom_idle_lines(
        self,
        status: WeComLocalStatus,
        *,
        saved_keys_available: bool,
    ) -> list[_DetailLine]:
        lines = self._wecom_status_section(status)
        if status.local_dbs_present:
            lines.extend(self._wecom_connect_steps(saved_keys_available=saved_keys_available))
        return lines

    def _wecom_probing_lines(
        self,
        status: WeComLocalStatus,
        *,
        saved_keys_available: bool,
    ) -> list[_DetailLine]:
        lines = self._wecom_status_section(status)
        lines.append(_DetailLine(self._i18n.translate("platform.wecom.section_working"), "heading"))
        if saved_keys_available:
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.probing_read_db"), "bullet"))
        else:
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.probing_scan_keys"), "bullet"))
        return lines

    def _wecom_success_lines(
        self,
        status: WeComLocalStatus,
        report: WeComProbeReport,
    ) -> list[_DetailLine]:
        lines = self._wecom_status_section(status)
        lines.append(_DetailLine(self._i18n.translate("platform.wecom.section_done"), "heading"))
        if report.from_cache:
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.success_cached"), "bullet"))
        else:
            lines.append(
                _DetailLine(
                    self._i18n.translate(
                        "platform.wecom.success",
                        count=report.session_count,
                        seconds=f"{report.duration_sec:.1f}",
                    ),
                    "bullet",
                )
            )
        lines.append(_DetailLine(self._i18n.translate("platform.wecom.step_pick_chat"), "step"))
        lines.append(_DetailLine(self._i18n.translate("platform.wecom.step_upload"), "step"))
        if not report.from_cache:
            lines.append(_DetailLine(self._i18n.translate("platform.wecom.status_keys_saved"), "muted"))
        return lines

    def _wecom_failure_lines(
        self,
        status: WeComLocalStatus,
        report: WeComProbeReport,
    ) -> list[_DetailLine]:
        lines = self._wecom_status_section(status)
        lines.append(_DetailLine(self._i18n.translate("platform.wecom.section_problem"), "heading"))
        lines.append(_DetailLine(self._i18n.translate("platform.wecom.keys_failed"), "error"))
        if report.error:
            detail = self._wecom_failure_detail(report.error)
            if detail:
                lines.append(_DetailLine(detail, "error"))
        lines.extend(self._wecom_connect_steps(saved_keys_available=False))
        lines.append(
            _DetailLine(
                self._i18n.translate("platform.wecom.log_help", path=wecom_debug_log_path_display()),
                "muted",
            )
        )
        return lines

    def _wecom_failure_detail(self, error: str) -> str:
        key_map = {
            "wxwork_not_running": "platform.wecom.process_missing",
            "keys_not_found": "platform.wecom.keys_not_found",
            "wxwork_process_open_failed": "platform.wecom.admin_required",
            "db_missing": "platform.wecom.db_missing",
        }
        for token, i18n_key in key_map.items():
            if token in error:
                return self._i18n.translate(i18n_key)
        return error[:160]

    def is_probing(self) -> bool:
        """True while a live DB read is in progress on this panel."""
        return self._probing

    def clear_probing(self) -> None:
        """Reset in-progress UI so idle status can be shown again."""
        self._probing = False
        self._start_btn.configure(state="normal")
        self._refresh_start_button()

    def abandon_probes(self) -> None:
        """Invalidate in-flight probe callbacks and reset the start button."""
        for key in self._probe_tokens:
            self._probe_tokens[key] += 1
        self.clear_probing()

    def probe_token(self, platform: str) -> int:
        """Return the generation token to capture before starting a background probe."""
        return self._probe_tokens.get(platform, 0)

    def probe_stale(self, platform: str, probe_token: int) -> bool:
        """True when a probe callback belongs to an abandoned generation."""
        return probe_token != self._probe_tokens.get(platform, -1)

    def set_wechat_hint(self, hint_key: str, **params: object) -> None:
        """Update the footer hint for WeChat mode."""
        if self._platform == "wechat":
            self._hint.configure(text=self._i18n.translate(hint_key, **params))

    def set_wechat_status(
        self,
        status: WeChatLocalStatus,
        *,
        saved_keys_available: bool = False,
    ) -> None:
        """Update detection rows (no key extraction)."""
        if self._platform != "wechat" or self._probing:
            return
        self._saved_keys_available = saved_keys_available
        self._refresh_start_button()
        self._hint.configure(text=self._footer_hint(status, saved_keys_available=saved_keys_available))
        self._set_detail_lines(self._idle_lines(status, saved_keys_available=saved_keys_available))

    def set_wechat_probing(
        self,
        status: WeChatLocalStatus,
        *,
        saved_keys_available: bool = False,
    ) -> None:
        """Show in-progress probe state."""
        if self._platform != "wechat":
            return
        self._probing = True
        self._saved_keys_available = saved_keys_available
        self._start_btn.configure(state="disabled")
        self._refresh_start_button()
        self._hint.configure(text=self._probing_footer(status, saved_keys_available=saved_keys_available))
        self._set_detail_lines(self._probing_lines(status, saved_keys_available=saved_keys_available))

    def set_wechat_probe_result(
        self,
        status: WeChatLocalStatus,
        report: Optional[WeChatProbeReport],
        *,
        saved_keys_available: bool = False,
    ) -> None:
        """Show completed probe outcome."""
        if self._platform != "wechat":
            return
        self._probing = False
        self._saved_keys_available = saved_keys_available
        self._start_btn.configure(state="normal")
        self._refresh_start_button()
        if report is not None and report.success:
            self._hint.configure(text=self._i18n.translate("platform.hint.wechat_live"))
            self._set_detail_lines(self._success_lines(status, report))
            return
        if report is not None and not report.success:
            self._hint.configure(text=self._i18n.translate("platform.hint.wechat_failed"))
            self._set_detail_lines(self._failure_lines(status, report, saved_keys_available=saved_keys_available))
            return
        self._hint.configure(text=self._footer_hint(status, saved_keys_available=saved_keys_available))
        self._set_detail_lines(self._idle_lines(status, saved_keys_available=saved_keys_available))

    def _footer_hint(self, status: WeChatLocalStatus, *, saved_keys_available: bool) -> str:
        if saved_keys_available:
            return self._i18n.translate("platform.hint.wechat_cached")
        if status.requires_wx_key_hook:
            return self._i18n.translate("platform.hint.wechat_hook")
        return self._i18n.translate("platform.hint")

    def _probing_footer(self, status: WeChatLocalStatus, *, saved_keys_available: bool) -> str:
        if saved_keys_available:
            return self._i18n.translate("platform.hint.wechat_cached")
        if status.requires_wx_key_hook:
            return self._i18n.translate("platform.hint.wechat_hook_active")
        return self._i18n.translate("platform.hint.wechat_connecting")

    def _status_section(self, status: WeChatLocalStatus) -> list[_DetailLine]:
        lines: list[_DetailLine] = [
            _DetailLine(self._i18n.translate("platform.wechat.section_status"), "heading"),
        ]
        version = status.weixin_version or self._i18n.translate("platform.wechat.version_unknown")
        if status.process_running:
            lines.append(
                _DetailLine(
                    self._i18n.translate("platform.wechat.status_wechat_open", version=version),
                    "bullet",
                )
            )
        else:
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.status_wechat_closed"), "bullet"))

        if status.wxid:
            lines.append(
                _DetailLine(
                    self._i18n.translate("platform.wechat.status_account", user=status.wxid),
                    "bullet",
                )
            )
            if status.db_count > 0:
                lines.append(_DetailLine(self._i18n.translate("platform.wechat.status_chats_found"), "bullet"))
        else:
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.not_logged_in"), "bullet"))

        if status.db_count == 0:
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.db_missing"), "error"))

        return lines

    def _first_time_hook_steps(self) -> list[_DetailLine]:
        return [
            _DetailLine(self._i18n.translate("platform.wechat.section_next"), "heading"),
            _DetailLine(self._i18n.translate("platform.wechat.step_admin"), "step"),
            _DetailLine(self._i18n.translate("platform.wechat.step_connect"), "step"),
            _DetailLine(self._i18n.translate("platform.wechat.step_logout"), "step"),
            _DetailLine(self._i18n.translate("platform.wechat.step_login"), "step"),
        ]

    def _simple_connect_steps(self) -> list[_DetailLine]:
        return [
            _DetailLine(self._i18n.translate("platform.wechat.section_next"), "heading"),
            _DetailLine(self._i18n.translate("platform.wechat.step_connect_simple"), "step"),
            _DetailLine(self._i18n.translate("platform.wechat.step_browse"), "step"),
        ]

    def _cached_steps(self) -> list[_DetailLine]:
        return [
            _DetailLine(self._i18n.translate("platform.wechat.section_next"), "heading"),
            _DetailLine(self._i18n.translate("platform.wechat.status_keys_saved"), "bullet"),
            _DetailLine(self._i18n.translate("platform.wechat.step_auto_load"), "step"),
            _DetailLine(self._i18n.translate("platform.wechat.step_read_db"), "step"),
            _DetailLine(self._i18n.translate("platform.wechat.step_pick_chat"), "step"),
        ]

    def _pick_chat_steps(self) -> list[_DetailLine]:
        return [
            _DetailLine(self._i18n.translate("platform.wechat.section_next"), "heading"),
            _DetailLine(self._i18n.translate("platform.wechat.step_pick_chat"), "step"),
            _DetailLine(self._i18n.translate("platform.wechat.step_upload"), "step"),
        ]

    def _idle_lines(self, status: WeChatLocalStatus, *, saved_keys_available: bool) -> list[_DetailLine]:
        lines = self._status_section(status)
        if saved_keys_available:
            lines.extend(self._cached_steps())
        elif status.requires_wx_key_hook:
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.status_not_connected"), "bullet"))
            lines.extend(self._first_time_hook_steps())
        else:
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.status_not_connected"), "bullet"))
            lines.extend(self._simple_connect_steps())
        return lines

    def _probing_lines(self, status: WeChatLocalStatus, *, saved_keys_available: bool) -> list[_DetailLine]:
        lines = self._status_section(status)
        lines.append(_DetailLine(self._i18n.translate("platform.wechat.section_working"), "heading"))
        if saved_keys_available:
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.probing_read_db"), "bullet"))
            return lines
        if status.requires_wx_key_hook:
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.wait_hook"), "bullet"))
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.wait_hook_detail"), "step"))
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.step_logout_now"), "step"))
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.step_login_now"), "step"))
            return lines
        lines.append(_DetailLine(self._i18n.translate("platform.wechat.probing_generic"), "bullet"))
        lines.append(_DetailLine(self._i18n.translate("platform.wechat.step_browse"), "step"))
        return lines

    def _success_lines(self, status: WeChatLocalStatus, report: WeChatProbeReport) -> list[_DetailLine]:
        lines = self._status_section(status)
        lines.append(_DetailLine(self._i18n.translate("platform.wechat.section_done"), "heading"))
        if report.from_cache:
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.success_cached"), "bullet"))
        else:
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.success"), "bullet"))
        lines.append(_DetailLine(self._i18n.translate("platform.wechat.status_connected"), "bullet"))
        lines.extend(self._pick_chat_steps())
        if not report.from_cache:
            lines.append(_DetailLine(self._i18n.translate("platform.wechat.status_keys_saved"), "muted"))
        return lines

    def _failure_lines(
        self,
        status: WeChatLocalStatus,
        report: WeChatProbeReport,
        *,
        saved_keys_available: bool = False,
    ) -> list[_DetailLine]:
        lines = self._status_section(status)
        lines.append(_DetailLine(self._i18n.translate("platform.wechat.section_problem"), "heading"))
        lines.append(_DetailLine(self._i18n.translate("platform.wechat.keys_failed"), "error"))
        detail = self._failure_detail(report)
        if detail:
            lines.append(_DetailLine(detail, "error"))
        if saved_keys_available:
            lines.extend(self._cached_steps())
        elif status.requires_wx_key_hook:
            lines.extend(self._first_time_hook_steps())
        else:
            lines.extend(self._simple_connect_steps())
        lines.append(
            _DetailLine(
                self._i18n.translate("platform.wechat.log_help", path=debug_log_path_display()),
                "muted",
            )
        )
        return lines

    def _failure_detail(self, report: WeChatProbeReport) -> str:
        if report.error and "wx_key.dll" in report.error.lower():
            if "not found" in report.error.lower():
                return self._i18n.translate("error.wechat_wx_key_dll_missing")
            return self._i18n.translate("error.wechat_wx_key_hook_failed")
        variant = report.crypto_variant or ""
        key_map = {
            "v3": "error.wechat_keys_v3_short",
            "v4": "error.wechat_keys_v4_short",
            "v4.1": "error.wechat_keys_v41_hook_short",
        }
        key = key_map.get(variant, "")
        if key:
            return self._i18n.translate(key)
        if report.error:
            return report.error[:160]
        return ""

    def _set_detail_lines(self, entries: list[_DetailLine]) -> None:
        self._detail.configure(state="normal")
        self._detail.delete("1.0", tk.END)
        for entry in entries:
            tag: tuple[str, ...]
            prefix = ""
            if entry.kind == "heading":
                tag = ("heading",)
            elif entry.kind == "step":
                tag = ()
            elif entry.kind == "muted":
                tag = ("muted",)
            elif entry.kind == "error":
                tag = ("error",)
            else:
                tag = ()
                prefix = "• "
            self._detail.insert(tk.END, prefix, tag)
            self._detail.insert(tk.END, entry.text + "\n", tag)
        self._detail.configure(state="disabled", fg=TEXT_PRIMARY)
