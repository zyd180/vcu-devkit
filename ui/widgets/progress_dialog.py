"""Modal progress dialog for long-running operations."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout


class ProgressDialog(QDialog):
    """Non-modal progress dialog with cancel support.

    Usage:
        dlg = ProgressDialog("正在解析 DBC 文件...", parent=self)
        worker.finished_ok.connect(lambda r: (dlg.close(), on_done(r)))
        worker.finished_err.connect(lambda e: (dlg.close(), on_error(e)))
        dlg.cancelled.connect(worker.terminate)
        dlg.show()
    """

    cancelled = Signal()

    def __init__(self, message: str = "处理中...", parent=None, cancellable: bool = True):
        super().__init__(parent)
        self.setWindowTitle("请稍候")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(360)
        self._setup_ui(message, cancellable)

    def _setup_ui(self, message: str, cancellable: bool):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._label = QLabel(message)
        layout.addWidget(self._label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate by default
        layout.addWidget(self._progress)

        if cancellable:
            self._cancel_btn = QPushButton("取消")
            self._cancel_btn.clicked.connect(self._on_cancel)
            layout.addWidget(self._cancel_btn)

    def set_message(self, message: str):
        self._label.setText(message)

    def set_progress(self, value: int, maximum: int = 100):
        self._progress.setRange(0, maximum)
        self._progress.setValue(value)

    def _on_cancel(self):
        self.cancelled.emit()
        self.reject()
