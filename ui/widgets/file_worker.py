"""Background worker for file I/O operations to keep UI responsive."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QThread, Signal, QObject


class FileWorker(QThread):
    """Run a callable in a background thread and emit the result.

    IMPORTANT: caller must keep a reference to the worker (e.g. self._worker)
    so it is not garbage-collected before the thread finishes.

    Usage:
        self._worker = FileWorker(some_callable, arg1, arg2)
        self._worker.finished_ok.connect(on_success)
        self._worker.finished_err.connect(on_error)
        self._worker.start()
    """

    finished_ok = Signal(object)   # result from the callable
    finished_err = Signal(str)     # error message

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished_ok.emit(result)
        except Exception as exc:
            self.finished_err.emit(str(exc))
