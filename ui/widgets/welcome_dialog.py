"""First-launch welcome dialog with 3-step onboarding."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFileDialog, QListWidget, QListWidgetItem,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont

from config.settings import __version__


class WelcomeDialog(QDialog):
    """Welcome dialog shown on first launch.

    Steps:
        1. Welcome + quick overview
        2. Import a file (optional)
        3. Ready to go

    Emits file_selected(str) if the user picks a file in step 2.
    """

    file_selected = Signal(str)

    MODULE_INFO = [
        (".dbc",  "CAN开发",  "DBC 文件 → 信号浏览 → C/CAPL 代码生成"),
        (".arxml", "SWC开发",  "AUTOSAR SWC 可视化与 ARXML 编辑"),
        (".odx",  "诊断配置", "DTC 配置与 UDS 服务管理"),
        (".a2l",  "标定管理", "标定参数管理与 A2L 导出"),
    ]

    def __init__(self, recent_files: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用 VCU DevKit")
        self.setMinimumSize(560, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._recent_files = recent_files or []
        self._selected_file: str | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Page stack
        self._stack = QStackedWidget()
        self._stack.addWidget(self._page_welcome())
        self._stack.addWidget(self._page_import())
        self._stack.addWidget(self._page_ready())
        layout.addWidget(self._stack)

        # Navigation buttons
        nav = QHBoxLayout()
        nav.addStretch()
        self._prev_btn = QPushButton("上一步")
        self._prev_btn.clicked.connect(self._go_prev)
        self._prev_btn.setEnabled(False)
        nav.addWidget(self._prev_btn)

        self._next_btn = QPushButton("下一步")
        self._next_btn.setDefault(True)
        self._next_btn.clicked.connect(self._go_next)
        nav.addWidget(self._next_btn)

        self._skip_btn = QPushButton("跳过")
        self._skip_btn.clicked.connect(self.accept)
        nav.addWidget(self._skip_btn)
        layout.addLayout(nav)

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _page_welcome(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        title = QLabel(f"欢迎使用 VCU DevKit v{__version__}")
        title.setFont(QFont("", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("汽车 VCU 软件开发辅助工具")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666; font-size: 14px;")
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        desc = QLabel(
            "VCU DevKit 帮助您高效完成以下工作：\n\n"
            "  ●  CAN DBC 配置浏览、编辑与 C/CAPL 代码生成\n"
            "  ●  AUTOSAR SWC 设计与 ARXML 导入导出\n"
            "  ●  UDS 诊断服务与 DTC 配置管理\n"
            "  ●  标定参数管理与 A2L 文件导出\n"
            "  ●  测试用例自动生成与需求追溯矩阵\n\n"
            "支持拖放文件直接打开，或通过文件菜单导入。"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        return page

    def _page_import(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        label = QLabel("选择要打开的文件（可跳过）")
        label.setFont(QFont("", 12))
        layout.addWidget(label)

        # Recent files
        if self._recent_files:
            recent_label = QLabel("最近打开的文件：")
            layout.addWidget(recent_label)
            self._recent_list = QListWidget()
            for fp in self._recent_files[:5]:
                item = QListWidgetItem(Path(fp).name)
                item.setToolTip(fp)
                item.setData(Qt.UserRole, fp)
                self._recent_list.addItem(item)
            self._recent_list.itemDoubleClicked.connect(self._on_recent_selected)
            layout.addWidget(self._recent_list)

        # Browse button
        browse_btn = QPushButton("浏览文件...")
        browse_btn.clicked.connect(self._on_browse)
        layout.addWidget(browse_btn)

        # Supported formats hint
        hint = QLabel("支持格式：DBC (.dbc) | ARXML (.arxml) | ODX (.odx) | A2L (.a2l)")
        hint.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(hint)
        return page

    def _page_ready(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        ready = QLabel("一切就绪！")
        ready.setFont(QFont("", 16, QFont.Bold))
        ready.setAlignment(Qt.AlignCenter)
        layout.addWidget(ready)

        hint = QLabel(
            "您也可以随时通过以下方式打开文件：\n\n"
            "  ●  Ctrl+O 打开项目目录\n"
            "  ●  直接拖放文件到窗口\n"
            "  ●  使用顶部工具栏按钮\n"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return page

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go_prev(self):
        idx = self._stack.currentIndex() - 1
        if idx >= 0:
            self._stack.setCurrentIndex(idx)
            self._prev_btn.setEnabled(idx > 0)
            self._next_btn.setText("下一步")

    def _go_next(self):
        idx = self._stack.currentIndex() + 1
        if idx < self._stack.count():
            self._stack.setCurrentIndex(idx)
            self._prev_btn.setEnabled(True)
            if idx == self._stack.count() - 1:
                self._next_btn.setText("完成")
                self._next_btn.clicked.disconnect()
                self._next_btn.clicked.connect(self.accept)
        else:
            self.accept()

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "",
            "所有支持格式 (*.dbc *.arxml *.odx *.odx-d *.odx-c *.cdd *.a2l);;所有文件 (*)"
        )
        if path:
            self._selected_file = path
            self.file_selected.emit(path)
            self.accept()

    def _on_recent_selected(self, item: QListWidgetItem):
        fp = item.data(Qt.UserRole)
        if fp:
            self._selected_file = fp
            self.file_selected.emit(fp)
            self.accept()

    @property
    def selected_file(self) -> str | None:
        return self._selected_file
