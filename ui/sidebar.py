"""Sidebar navigation widget."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QFrame,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QIcon

_ICONS_DIR = Path(__file__).parent / "icons"


class Sidebar(QWidget):
    """Left sidebar with module navigation."""

    module_selected = Signal(int)

    MODULES = [
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
        header.setAlignment(Qt.AlignCenter)
        header.setFixedHeight(48)
        header.setStyleSheet(
            "background-color: #1a73e8; color: white; "
            "font-size: 16px; font-weight: bold;"
        )
        layout.addWidget(header)

        # Module list
        self.module_list = QListWidget()
        self.module_list.setIconSize(QSize(20, 20))
        self.module_list.setStyleSheet("""
            QListWidget {
                background-color: #f5f5f5;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 12px 16px;
                border-bottom: 1px solid #e0e0e0;
                font-size: 13px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1a73e8;
                border-left: 3px solid #1a73e8;
            }
            QListWidget::item:hover:!selected {
                background-color: #eeeeee;
            }
        """)

        for name, desc, icon_file in self.MODULES:
            icon_path = _ICONS_DIR / icon_file
            icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
            item = QListWidgetItem(icon, f"{name}\n{desc}")
            item.setSizeHint(QSize(220, 52))
            item.setToolTip(desc)
            self.module_list.addItem(item)

        self.module_list.currentRowChanged.connect(self.module_selected.emit)
        layout.addWidget(self.module_list)

        # Footer
        layout.addStretch()
        footer = QFrame()
        footer.setFrameShape(QFrame.HLine)
        footer.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(footer)

        version_label = QLabel("v0.1.0")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #999; font-size: 11px; padding: 8px;")
        layout.addWidget(version_label)
