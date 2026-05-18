"""Code editor widget with syntax highlighting."""

from PySide6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import (
    QFont, QColor, QPainter, QSyntaxHighlighter,
    QTextCharFormat, QTextFormat,
)


class LineNumberArea(QWidget):
    """Line number gutter for the code editor."""

    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class CodeHighlighter(QSyntaxHighlighter):
    """Simple C/C++ syntax highlighter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []

        # Keywords
        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(QColor("#0000ff"))
        keyword_fmt.setFontWeight(QFont.Bold)
        keywords = [
            "void", "int", "uint8_t", "uint16_t", "uint32_t", "int8_t", "int16_t", "int32_t",
            "float", "double", "char", "static", "inline", "const", "typedef", "struct", "enum",
            "if", "else", "for", "while", "switch", "case", "return", "include", "define",
        ]
        for kw in keywords:
            self._rules.append((rf"\b{kw}\b", keyword_fmt))

        # Preprocessor
        preproc_fmt = QTextCharFormat()
        preproc_fmt.setForeground(QColor("#9b2397"))
        self._rules.append((r"^#\w+.*$", preproc_fmt))

        # Comments
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6a9955"))
        self._rules.append((r"//[^\n]*", comment_fmt))

        # Strings
        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#a31515"))
        self._rules.append((r'"[^"]*"', string_fmt))

        # Numbers
        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor("#098658"))
        self._rules.append((r"\b\d+\.?\d*[fFuUlL]?\b", number_fmt))

    def highlightBlock(self, text: str):
        import re
        for pattern, fmt in self._rules:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class CodeEditor(QPlainTextEdit):
    """Code editor with line numbers and syntax highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 11))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.highlighter = CodeHighlighter(self.document())

        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._update_line_number_area_width(0)

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#999"))
                painter.drawText(
                    0, top, self.line_number_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1
        painter.end()
