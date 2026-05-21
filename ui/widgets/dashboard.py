"""Dashboard home page widget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DashboardWidget(QWidget):
    """Application home page — recent files, stats, quick actions."""

    open_file_requested = Signal(str)  # file path
    module_requested = Signal(int)  # module index (0-5)

    _EXT_MODULE_MAP = {
        ".dbc": 0,
        ".arxml": 1,
        ".odx": 2,
        ".cdd": 2,
        ".a2l": 3,
        ".json": -1,
    }

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._setup_ui()
        self._refresh_recent()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        # Title
        title = QLabel("VCU DevKit")
        title.setObjectName("dashboard_title")
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("汽车VCU软件开发辅助工具")
        subtitle.setObjectName("dashboard_subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        root.addWidget(subtitle)

        root.addSpacing(12)

        # Top row: 3 columns
        top = QHBoxLayout()
        top.setSpacing(16)
        top.addWidget(self._create_recent_group())
        top.addWidget(self._create_stats_group())
        top.addWidget(self._create_actions_group())
        root.addLayout(top)

        # Bottom: module status
        root.addWidget(self._create_module_status())

        root.addStretch()

    # ── Recent files ──────────────────────────────────────────────────────

    def _create_recent_group(self) -> QGroupBox:
        group = QGroupBox("最近文件")
        layout = QVBoxLayout(group)
        self._recent_list = QListWidget()
        self._recent_list.setMinimumHeight(140)
        self._recent_list.itemDoubleClicked.connect(self._on_recent_double_click)
        layout.addWidget(self._recent_list)
        return group

    def _refresh_recent(self):
        self._recent_list.clear()
        if not self.settings:
            return
        for fp in self.settings.recent_files[:8]:
            p = Path(fp)
            item = QListWidgetItem(f"{p.name}  —  {p.parent}")
            item.setData(Qt.UserRole, fp)
            item.setToolTip(fp)
            self._recent_list.addItem(item)

    def _on_recent_double_click(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path:
            self.open_file_requested.emit(path)

    # ── Stats ─────────────────────────────────────────────────────────────

    def _create_stats_group(self) -> QGroupBox:
        group = QGroupBox("项目统计")
        layout = QVBoxLayout(group)
        self._stats_labels: dict[str, QLabel] = {}
        for key, label in [("dbc", "DBC 文件"), ("arxml", "ARXML 文件"), ("a2l", "A2L 文件")]:
            row = QHBoxLayout()
            name = QLabel(label)
            val = QLabel("—")
            val.setAlignment(Qt.AlignRight)
            row.addWidget(name)
            row.addWidget(val)
            layout.addLayout(row)
            self._stats_labels[key] = val
        layout.addStretch()
        return group

    def update_stats(self, counts: dict[str, int]):
        for key, lbl in self._stats_labels.items():
            n = counts.get(key, 0)
            lbl.setText(str(n) if n else "—")

    # ── Quick actions ─────────────────────────────────────────────────────

    def _create_actions_group(self) -> QGroupBox:
        group = QGroupBox("快速操作")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        btns = [
            ("打开 DBC 文件", 0),
            ("新建 SWC 项目", 1),
            ("打开 A2L 文件", 3),
        ]
        for text, mod_idx in btns:
            btn = QPushButton(text)
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda checked=False, idx=mod_idx: self.module_requested.emit(idx))
            layout.addWidget(btn)
        layout.addStretch()
        return group

    # ── Module status ─────────────────────────────────────────────────────

    def _create_module_status(self) -> QGroupBox:
        group = QGroupBox("模块状态")
        grid = QGridLayout(group)
        grid.setSpacing(12)
        modules = ["CAN开发", "SWC开发", "诊断配置", "标定管理", "测试生成", "需求追溯"]
        self._module_status_labels: list[QLabel] = []
        for i, name in enumerate(modules):
            row, col = divmod(i, 3)
            lbl = QLabel(f"{name}:  未加载")
            lbl.setMinimumWidth(200)
            grid.addWidget(lbl, row, col)
            self._module_status_labels.append(lbl)
        return group

    def set_module_loaded(self, index: int, loaded: bool):
        if 0 <= index < len(self._module_status_labels):
            name = ["CAN开发", "SWC开发", "诊断配置", "标定管理", "测试生成", "需求追溯"][index]
            status = "已加载" if loaded else "未加载"
            self._module_status_labels[index].setText(f"{name}:  {status}")

    # ── Public refresh ────────────────────────────────────────────────────

    def refresh(self):
        """Call when settings or project state changes."""
        self._refresh_recent()
