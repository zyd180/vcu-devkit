"""Status bar widget."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt


class StatusBarWidget(QWidget):
    """Permanent widget in the status bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)

        self.project_label = QLabel("未加载项目")
        self.project_label.setStyleSheet("color: #666;")
        layout.addWidget(self.project_label)

        layout.addWidget(QLabel(" | "))

        self.files_label = QLabel("DBC: 0 | ARXML: 0 | ODX: 0 | A2L: 0")
        self.files_label.setStyleSheet("color: #666;")
        layout.addWidget(self.files_label)

    def set_project(self, path: str):
        """Update project path display."""
        import os
        name = os.path.basename(path)
        self.project_label.setText(f"项目: {name}")

    def set_file_counts(self, dbc: int = 0, arxml: int = 0, odx: int = 0, a2l: int = 0):
        """Update file count display."""
        self.files_label.setText(f"DBC: {dbc} | ARXML: {arxml} | ODX: {odx} | A2L: {a2l}")
