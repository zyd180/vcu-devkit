"""Code editor widget with syntax highlighting."""

import re

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

    _BLOCK_START = re.compile(r"/\*")
    _BLOCK_END = re.compile(r"\*/")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = []

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
            self._rules.append((re.compile(rf"\b{kw}\b"), keyword_fmt))

        # Preprocessor
        preproc_fmt = QTextCharFormat()
        preproc_fmt.setForeground(QColor("#9b2397"))
        self._rules.append((re.compile(r"^#\w+.*$"), preproc_fmt))

        # Single-line comments
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6a9955"))
        self._comment_fmt = comment_fmt
        self._rules.append((re.compile(r"//[^\n]*"), comment_fmt))

        # Block comment pattern
        self._block_comment_fmt = QTextCharFormat()
        self._block_comment_fmt.setForeground(QColor("#6a9955"))

        # Strings
        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#a31515"))
        self._rules.append((re.compile(r'"[^"]*"'), string_fmt))

        # Numbers
        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor("#098658"))
        self._rules.append((re.compile(r"\b\d+\.?\d*[fFuUlL]?\b"), number_fmt))

    def highlightBlock(self, text: str):
        # Block comment state machine
        state = self.previousBlockState()
        if state == 1:
            # Inside a block comment from the previous line
            end = self._BLOCK_END.search(text)
            if end:
                self.setFormat(0, end.end(), self._block_comment_fmt)
                start_pos = end.end()
            else:
                self.setFormat(0, len(text), self._block_comment_fmt)
                self.setCurrentBlockState(1)
                return
        else:
            start_pos = 0

        # Find block comment starts in the remaining text
        remaining = text[start_pos:]
        offset = start_pos
        while remaining:
            start = self._BLOCK_START.search(remaining)
            if not start:
                break
            # Apply single-line rules before the block comment
            self._apply_rules(text[offset:offset + start.start()], offset)
            # Find end of block comment
            after_start = remaining[start.end():]
            end = self._BLOCK_END.search(after_start)
            if end:
                comment_end = offset + start.start()
                comment_len = start.end() - start.start() + end.end()
                self.setFormat(comment_end, comment_len, self._block_comment_fmt)
                offset = comment_end + comment_len
                remaining = text[offset:]
            else:
                # Block comment extends to next line
                self.setFormat(offset + start.start(), len(text) - offset - start.start(), self._block_comment_fmt)
                self.setCurrentBlockState(1)
                return

        # Apply single-line rules to remaining text
        self._apply_rules(text[offset:], offset)

    def _apply_rules(self, text: str, offset: int):
        """Apply single-line highlight rules to a text segment."""
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(offset + match.start(), match.end() - match.start(), fmt)


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
