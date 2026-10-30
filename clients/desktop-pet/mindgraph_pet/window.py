"""Transparent always-on-top pet. Clicks miss the clear margin."""

from __future__ import annotations

import sys
import time
import webbrowser
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QContextMenuEvent, QIcon, QImage, QMouseEvent, QPaintEvent, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from mindgraph_pet.api import ApiError, normalize_origin, unread_summary, update_offer
from mindgraph_pet.credentials import load_preferences, load_secrets, save_preferences, save_secrets
from mindgraph_pet.player import clip_paths, load_clip
from mindgraph_pet.settings_dialog import MASCOTS, SettingsDialog
from mindgraph_pet.startup import set_open_at_login
from mindgraph_pet.updater import download, hash_matches, install_root, launch_swap
from mindgraph_pet.version_info import installed_version, is_newer

ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets"
CLIP_HOLD_SECONDS = 20


def _pixmap(image: Image.Image) -> QPixmap:
    raw = image.convert("RGBA").tobytes("raw", "RGBA")
    qimage = QImage(raw, image.width, image.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


class PetWindow(QWidget):
    """The mascot. Right-click opens Using MindMate, MindGraph, Settings, and Quit."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._prefs = load_preferences()
        self._phone, self._token = load_secrets()
        chosen = str(self._prefs.get("mascot") or "black")
        self._mascot = chosen if chosen in MASCOTS else "black"
        self._paths = clip_paths(self._mascot, ASSET_ROOT)
        self._index = 0
        self._pixmaps: list[QPixmap] = []
        self._frame_index = 0
        self._clip_started = time.monotonic()
        self._unread = 0
        self._drag: QPoint | None = None
        self._moved = False
        self._auth_failed = False
        self.resize(280, 360)
        self._restore_position()
        self._install_tray()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(83)
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._poll_unread)
        self._poll.start(20000)
        QTimer.singleShot(0, self._load_first)
        if not self._phone or not self._token:
            QTimer.singleShot(0, self._open_settings)
        else:
            QTimer.singleShot(0, self._poll_unread)

    def _install_tray(self) -> None:
        self._menu = QMenu(self)
        self._menu.addAction("Using MindMate", self._open_mindmate)
        self._menu.addAction("MindGraph", self._open_mindgraph)
        self._menu.addAction("Settings", self._open_settings)
        self._menu.addAction("Quit", QApplication.quit)
        self._tray = QSystemTrayIcon(self._fallback_icon(), self)
        self._tray.setToolTip("MindGraph")
        self._tray.setContextMenu(self._menu)
        self._tray.show()

    def _fallback_icon(self) -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.black)
        painter.drawEllipse(6, 6, 20, 20)
        painter.end()
        return QIcon(pixmap)

    def _update_tray_icon(self) -> None:
        if not self._pixmaps:
            self._tray.setIcon(self._fallback_icon())
            return
        self._tray.setIcon(QIcon(self._pixmaps[0].scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio)))

    def _restore_position(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        try:
            x_pos = int(self._prefs.get("x") or area.right() - self.width() - 40)
            y_pos = int(self._prefs.get("y") or area.bottom() - self.height() - 40)
        except ValueError:
            x_pos, y_pos = area.right() - self.width() - 40, area.bottom() - self.height() - 40
        x_pos = min(max(area.left(), x_pos), area.right() - 40)
        y_pos = min(max(area.top(), y_pos), area.bottom() - 40)
        self.move(x_pos, y_pos)

    def _load_first(self) -> None:
        self._load_index(0)

    def _load_index(self, index: int) -> None:
        """Decode one action and drop the previous frames."""
        count = len(self._paths)
        if count == 0:
            self._pixmaps = []
            self._frame_index = 0
            self.update()
            return
        for offset in range(count):
            chosen = (index + offset) % count
            try:
                clip = load_clip(self._paths[chosen])
            except (OSError, ValueError):
                continue
            self._index = chosen
            self._pixmaps = [_pixmap(frame) for frame in clip.frames]
            self._frame_index = 0
            self._clip_started = time.monotonic()
            self._update_tray_icon()
            self.update()
            return

    def _advance(self) -> None:
        if not self._pixmaps:
            return
        self._frame_index = (self._frame_index + 1) % len(self._pixmaps)
        if time.monotonic() - self._clip_started >= CLIP_HOLD_SECONDS and len(self._paths) > 1:
            self._load_index(self._index + 1)
            return
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the current frame and the unread count."""
        del event
        painter = QPainter(self)
        region = QRegion()
        if not self._pixmaps:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(Qt.GlobalColor.black)
            painter.drawEllipse(20, 20, 80, 80)
            region = QRegion(20, 20, 80, 80, QRegion.RegionType.Ellipse)
        else:
            pixmap = self._pixmaps[self._frame_index % len(self._pixmaps)]
            x_pos = max(0, (self.width() - pixmap.width()) // 2)
            y_pos = max(0, (self.height() - pixmap.height()) // 2)
            painter.drawPixmap(x_pos, y_pos, pixmap)
            region = QRegion(pixmap.mask()).translated(x_pos, y_pos)
        if self._unread > 0:
            painter.setBrush(Qt.GlobalColor.red)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawEllipse(self.width() - 36, 0, 32, 32)
            painter.drawText(self.width() - 36, 0, 32, 32, Qt.AlignmentFlag.AlignCenter, str(min(self._unread, 99)))
            region = region.united(QRegion(self.width() - 36, 0, 32, 32, QRegion.RegionType.Ellipse))
        self.setMask(region)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Start a drag, or remember a click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Move the pet when the press has traveled."""
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)
            self._moved = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """A short press plays the next scene. A drag keeps the new position."""
        if event.button() == Qt.MouseButton.LeftButton and not self._moved and self._paths:
            self._load_index(self._index + 1)
        if event.button() == Qt.MouseButton.LeftButton:
            self._prefs["x"] = str(self.x())
            self._prefs["y"] = str(self.y())
            save_preferences(self._prefs)
        self._drag = None
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Using MindMate, MindGraph, Settings, and Quit."""
        self._menu.exec(event.globalPos())

    def _server(self) -> str:
        return self._prefs.get("server") or "mg.mindspringedu.com"

    def _open_mindmate(self) -> None:
        if not self._ready():
            return
        origin = normalize_origin(self._server())
        code = ""
        rooms = self._prefs.get("unread_code") or ""
        if self._unread > 0 and rooms:
            code = rooms
        if code:
            webbrowser.open(f"{origin}/mindmate/seminar?code={code}")
        else:
            webbrowser.open(f"{origin}/mindmate")

    def _open_mindgraph(self) -> None:
        if not self._ready():
            return
        webbrowser.open(f"{normalize_origin(self._server())}/mindgraph")

    def _ready(self) -> bool:
        if self._phone and self._token:
            return True
        self._open_settings()
        return False

    def _open_settings(self) -> None:
        dialog = SettingsDialog(
            self._server(),
            self._phone,
            self._token,
            self._mascot,
            self._prefs.get("open_at_login") == "1",
        )
        dialog.update_button().clicked.connect(lambda: self._check_update(dialog))
        if dialog.exec() != dialog.DialogCode.Accepted or not dialog.saved:
            return
        server, phone, token, mascot, login = dialog.values()
        save_secrets(phone, token)
        self._phone, self._token = phone, token
        self._mascot = mascot
        self._paths = clip_paths(mascot, ASSET_ROOT)
        self._load_index(0)
        self._prefs["server"] = server
        self._prefs["mascot"] = mascot
        self._prefs["open_at_login"] = "1" if login else "0"
        save_preferences(self._prefs)
        login_error = set_open_at_login(login, Path(sys.executable))
        if login_error:
            dialog.set_status(login_error)
        self._auth_failed = False
        self._poll_unread()

    def _poll_unread(self) -> None:
        if not self._phone or not self._token:
            return
        try:
            summary = unread_summary(self._server(), self._phone, self._token)
        except ApiError as exc:
            if exc.code == "rejected":
                self._unread = 0
                self._auth_failed = True
            return
        self._auth_failed = False
        self._unread = int(summary.get("unread_count") or 0)
        rooms = summary.get("rooms")
        if isinstance(rooms, list) and rooms and isinstance(rooms[0], dict):
            self._prefs["unread_code"] = str(rooms[0].get("code") or "")
            save_preferences(self._prefs)
        self.update()

    def _check_update(self, dialog: SettingsDialog) -> None:
        platform = "mac" if sys.platform == "darwin" else "windows"
        try:
            offer = update_offer(self._server(), self._phone, self._token, platform)
        except ApiError as exc:
            dialog.set_status(_ERROR.get(exc.code, "出了点问题。请重试。"))
            return
        if offer is None or not is_newer(str(offer.get("version") or ""), installed_version()):
            dialog.set_status("已是最新")
            return
        dest = install_root() / "update.zip"
        try:
            download(str(offer["url"]), dest)
        except OSError:
            dialog.set_status("网络失败。请检查服务器地址。")
            return
        if not hash_matches(dest, str(offer.get("sha256") or "")):
            dest.unlink(missing_ok=True)
            dialog.set_status("更新文件校验失败。")
            return
        launch_swap(dest)
        QApplication.quit()


_ERROR = {
    "rejected": "手机号或 API 令牌不正确。",
    "network": "网络失败。请检查服务器地址。",
    "server": "MindGraph 服务器出错。请检查设置后重试。",
}


def main() -> None:
    """Show the pet. Developer entry from this folder: python -m mindgraph_pet."""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = PetWindow()
    window.show()
    raise SystemExit(app.exec())
