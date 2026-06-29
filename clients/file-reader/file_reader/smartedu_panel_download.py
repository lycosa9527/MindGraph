"""Download picker dialog for the platform browser tab."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, List

from file_reader.i18n import I18n
from file_reader.platform_browser.download_prefs import remember_download_dir, resolve_download_dir
from file_reader.platform_browser.models import DetectedAsset
from file_reader.platform_browser.sites import detect_platform
from file_reader.theme import ACCENT, BG_CARD, BG_MUTED, FONT_BODY, TEXT_PRIMARY, TEXT_SECONDARY


def open_asset_download_dialog(
    parent: tk.Misc,
    i18n: I18n,
    assets: List[DetectedAsset],
    page_url: str,
    *,
    on_download: Callable[[List[DetectedAsset], Path], None],
) -> None:
    """Show a checkbox dialog for detected assets."""
    site = detect_platform(page_url)
    folder = resolve_download_dir(site)

    dialog = tk.Toplevel(parent)
    dialog.title(i18n.translate("smartedu.download_dialog_title"))
    dialog.configure(bg=BG_CARD)
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()

    pad = tk.Frame(dialog, bg=BG_CARD, padx=16, pady=14)
    pad.pack(fill="both", expand=True)

    title = assets[0].title if assets else i18n.translate("smartedu.download_dialog_title")
    tk.Label(
        pad,
        text=i18n.translate("smartedu.lesson", title=title),
        bg=BG_CARD,
        fg=TEXT_PRIMARY,
        font=FONT_BODY,
        anchor="w",
        justify="left",
    ).pack(fill="x", pady=(0, 8))

    folder_row = tk.Frame(pad, bg=BG_CARD)
    folder_row.pack(fill="x", pady=(0, 8))
    folder_var = tk.StringVar(value=str(folder))
    tk.Label(
        folder_row,
        text=i18n.translate("smartedu.download_folder_label"),
        bg=BG_CARD,
        fg=TEXT_SECONDARY,
        font=FONT_BODY,
        anchor="w",
    ).pack(fill="x")
    folder_entry = tk.Entry(
        folder_row,
        textvariable=folder_var,
        font=FONT_BODY,
        relief="flat",
        bg=BG_MUTED,
        fg=TEXT_PRIMARY,
        state="readonly",
        readonlybackground=BG_MUTED,
    )
    folder_entry.pack(fill="x", pady=(4, 4))

    def choose_folder() -> None:
        selected = filedialog.askdirectory(
            parent=dialog,
            title=i18n.translate("smartedu.download_folder_choose"),
            initialdir=folder_var.get(),
        )
        if selected:
            folder_var.set(selected)

    tk.Button(
        folder_row,
        text=i18n.translate("smartedu.download_folder_change"),
        font=FONT_BODY,
        relief="flat",
        bg=BG_MUTED,
        fg=TEXT_PRIMARY,
        padx=10,
        pady=4,
        command=choose_folder,
    ).pack(anchor="w")

    asset_vars: dict[str, tk.BooleanVar] = {}
    for asset in assets:
        var = tk.BooleanVar(value=asset.selected)
        asset_vars[asset.asset_id] = var
        tk.Checkbutton(
            pad,
            text=f"{asset.title} — {asset.format_label}",
            variable=var,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=FONT_BODY,
            selectcolor=BG_MUTED,
            activebackground=BG_CARD,
            anchor="w",
        ).pack(fill="x", pady=2)

    btn_row = tk.Frame(pad, bg=BG_CARD)
    btn_row.pack(fill="x", pady=(12, 0))

    def start_download() -> None:
        selected = [asset for asset in assets if asset_vars[asset.asset_id].get()]
        if not selected:
            messagebox.showwarning(
                i18n.translate("dialog.title"),
                i18n.translate("smartedu.error.no_assets"),
                parent=dialog,
            )
            return
        target = Path(folder_var.get()).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        remember_download_dir(site.site_id, target)
        dialog.destroy()
        on_download(selected, target)

    tk.Button(
        btn_row,
        text=i18n.translate("smartedu.browser_download"),
        font=FONT_BODY,
        relief="flat",
        bg=ACCENT,
        fg="#ffffff",
        padx=14,
        pady=8,
        command=start_download,
    ).pack(side="left")


def show_download_result(
    parent: tk.Misc,
    i18n: I18n,
    saved: List[Path],
    errors: List[str],
) -> None:
    """Display a download result message box."""
    if saved and not errors:
        messagebox.showinfo(
            i18n.translate("dialog.title"),
            i18n.translate("smartedu.status.done_primary", count=len(saved))
            + "\n"
            + i18n.translate("smartedu.status.done_secondary", folder=str(saved[0].parent)),
            parent=parent,
        )
        return
    if saved:
        detail = "; ".join(errors[:3])
        messagebox.showwarning(
            i18n.translate("dialog.title"),
            i18n.translate("smartedu.status.partial_primary", ok=len(saved)) + "\n" + detail,
            parent=parent,
        )
        return
    detail = "; ".join(errors[:2]) or i18n.translate("smartedu.status.failed")
    messagebox.showerror(i18n.translate("dialog.title"), detail, parent=parent)
