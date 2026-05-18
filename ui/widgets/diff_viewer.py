"""Diff viewer widget for displaying version differences."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter


class DiffHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for diff output."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []

        # Added lines (green)
        added_fmt = QTextCharFormat()
        added_fmt.setBackground(QColor("#e6ffed"))
        added_fmt.setForeground(QColor("#22863a"))
        self._rules.append((r"^\+.*$", added_fmt))

        # Removed lines (red)
        removed_fmt = QTextCharFormat()
        removed_fmt.setBackground(QColor("#ffeef0"))
        removed_fmt.setForeground(QColor("#cb2431"))
        self._rules.append((r"^-.*$", removed_fmt))

        # Modified lines (orange)
        modified_fmt = QTextCharFormat()
        modified_fmt.setBackground(QColor("#fff5b1"))
        modified_fmt.setForeground(QColor("#735c0f"))
        self._rules.append((r"^~.*$", modified_fmt))

        # Header lines
        header_fmt = QTextCharFormat()
        header_fmt.setFontWeight(QFont.Bold)
        header_fmt.setForeground(QColor("#6f42c1"))
        self._rules.append((r"^@@.*$", header_fmt))

    def highlightBlock(self, text: str):
        import re
        for pattern, fmt in self._rules:
            match = re.match(pattern, text)
            if match:
                self.setFormat(0, len(text), fmt)
                return


class DiffViewer(QWidget):
    """Widget for displaying file diff results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Diff")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #666;")
        header_layout.addWidget(self.summary_label)

        layout.addLayout(header_layout)

        # Diff content
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.highlighter = DiffHighlighter(self.text_edit.document())
        layout.addWidget(self.text_edit)

    def set_diff_content(self, title: str, summary: dict[str, int], content: str):
        """Set diff content for display."""
        self.title_label.setText(title)

        parts = []
        if summary.get("added", 0):
            parts.append(f"+{summary['added']} 新增")
        if summary.get("removed", 0):
            parts.append(f"-{summary['removed']} 删除")
        if summary.get("modified", 0):
            parts.append(f"~{summary['modified']} 修改")
        self.summary_label.setText("  |  ".join(parts) if parts else "无变更")

        self.text_edit.setPlainText(content)

    def clear(self):
        """Clear the diff display."""
        self.text_edit.clear()
        self.title_label.setText("Diff")
        self.summary_label.setText("")
