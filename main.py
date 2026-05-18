"""VCU DevKit - 汽车VCU软件开发辅助工具"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow
from config.settings import AppSettings


def load_stylesheet(theme: str = "light") -> str:
    """Load QSS stylesheet."""
    qss_path = Path(__file__).parent / "ui" / "themes" / f"{theme}.qss"
    if qss_path.exists():
        return qss_path.read_text(encoding="utf-8")
    return ""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("VCU DevKit")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("VCU Team")

    settings = AppSettings()
    settings.load()

    stylesheet = load_stylesheet(settings.theme)
    if stylesheet:
        app.setStyleSheet(stylesheet)

    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
