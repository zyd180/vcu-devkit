"""Sidebar navigation widget."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.settings import __version__

_ICONS_DIR = Path(__file__).parent / "icons"


class Sidebar(QWidget):
    """Left sidebar with module navigation."""

    module_selected = Signal(int)

    MODULES = [
        ("概览", "项目总览与快速操作", None),
        ("CAN开发", "DBC配置与代码生成", "can.svg"),
        ("SWC开发", "AUTOSAR SWC可视化", "swc.svg"),
        ("诊断配置", "UDS / DTC配置", "diag.svg"),
        ("标定管理", "参数管理与导出", "calib.svg"),
        ("测试生成", "用例生成与覆盖率", "test.svg"),
        ("需求追溯", "需求与工件追溯", "trace.svg"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("VCU DevKit")
        header.setObjectName("sidebar_header")
        header.setAlignment(Qt.AlignCenter)
        header.setFixedHeight(48)
        layout.addWidget(header)

        # Module list
        self.module_list = QListWidget()
        self.module_list.setObjectName("sidebar_list")
        self.module_list.setIconSize(QSize(20, 20))

        for name, desc, icon_file in self.MODULES:
            if icon_file:
                icon_path = _ICONS_DIR / icon_file
                icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
            else:
                icon = QIcon()
            item = QListWidgetItem(icon, f"{name}\n{desc}")
            item.setSizeHint(QSize(220, 52))
            item.setToolTip(desc)
            self.module_list.addItem(item)

        self.module_list.currentRowChanged.connect(self.module_selected.emit)
        layout.addWidget(self.module_list)

        # Footer
        layout.addStretch()
        footer = QFrame()
        footer.setObjectName("sidebar_footer")
        footer.setFrameShape(QFrame.HLine)
        layout.addWidget(footer)

        version_label = QLabel(f"v{__version__}")
        version_label.setObjectName("sidebar_version")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
