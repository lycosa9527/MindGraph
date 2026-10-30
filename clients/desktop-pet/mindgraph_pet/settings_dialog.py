"""Right-click Settings: the same phone and token check as the Chrome extension."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from mindgraph_pet.api import ApiError, verify
from mindgraph_pet.version_info import installed_version

PRESETS = (
    "mg.mindspringedu.com",
    "test.mindspringedu.com",
    "localhost:9527",
)
MASCOTS = ("black", "white", "raven", "schnauzer")


class SettingsDialog(QDialog):
    """Server, phone, token, mascot, login item, and update."""

    def __init__(self, server: str, phone: str, token: str, mascot: str, open_at_login: bool) -> None:
        super().__init__()
        self.setWindowTitle("设置")
        self.saved = False
        self._server = QComboBox()
        self._server.setEditable(True)
        self._server.addItems(PRESETS)
        self._server.setCurrentText(server or PRESETS[0])
        self._phone = QLineEdit(phone)
        self._phone.setPlaceholderText("用于 X-MG-Account 的手机号")
        self._token = QLineEdit(token)
        self._token.setEchoMode(QLineEdit.EchoMode.Password)
        self._token.setPlaceholderText("mgat_…")
        self._mascot = QComboBox()
        self._mascot.addItems(MASCOTS)
        if mascot in MASCOTS:
            self._mascot.setCurrentText(mascot)
        self._login = QCheckBox("开机启动")
        self._login.setChecked(open_at_login)
        self._status = QLabel(f"当前版本 {installed_version()}")
        self._update = QPushButton("更新")
        self._save = QPushButton("保存")
        self._save.clicked.connect(self._on_save)
        form = QFormLayout()
        form.addRow("服务器", self._server)
        form.addRow("账号（手机号）", self._phone)
        form.addRow("API 令牌", self._token)
        form.addRow("角色", self._mascot)
        form.addRow("", self._login)
        buttons = QHBoxLayout()
        buttons.addWidget(self._update)
        buttons.addWidget(self._save)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._status)
        layout.addLayout(buttons)

    def values(self) -> tuple[str, str, str, str, bool]:
        """Server, phone, token, mascot, open at login."""
        return (
            self._server.currentText().strip(),
            self._phone.text().strip(),
            self._token.text().strip(),
            self._mascot.currentText(),
            self._login.isChecked(),
        )

    def set_status(self, text: str) -> None:
        """Show verify or update progress."""
        self._status.setText(text)

    def update_button(self) -> QPushButton:
        """The parent wires the COS update check."""
        return self._update

    def _on_save(self) -> None:
        server, phone, token, _mascot, _login = self.values()
        self._status.setText("正在校验凭据…")
        self._save.setEnabled(False)
        try:
            verify(server, phone, token)
        except ApiError as exc:
            self._status.setText(_ERROR.get(exc.code, "出了点问题。请重试。"))
            self._save.setEnabled(True)
            return
        self.saved = True
        self._status.setText("已保存。")
        self.accept()


_ERROR = {
    "incomplete": "请填写全部字段。",
    "rejected": "手机号或 API 令牌不正确。",
    "network": "网络失败。请检查服务器地址。",
    "server": "MindGraph 服务器出错。请检查设置后重试。",
}
