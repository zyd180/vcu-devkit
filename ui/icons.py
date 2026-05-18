"""Shared icon helpers for VCU DevKit."""

from pathlib import Path
from PySide6.QtGui import QIcon

_ICONS_DIR = Path(__file__).parent / "icons"


def get_svg_icon(name: str) -> QIcon:
    """Load an SVG icon from the icons directory."""
    path = _ICONS_DIR / name
    if path.exists():
        return QIcon(str(path))
    return QIcon()


# Custom SVG icons for toolbar actions
def icon_open() -> QIcon:
    return get_svg_icon("action_open.svg")

def icon_save() -> QIcon:
    return get_svg_icon("action_save.svg")

def icon_check() -> QIcon:
    return get_svg_icon("action_validate.svg")

def icon_generate() -> QIcon:
    return get_svg_icon("action_generate.svg")

def icon_export() -> QIcon:
    return get_svg_icon("action_export.svg")

def icon_diff() -> QIcon:
    return get_svg_icon("action_diff.svg")

def icon_add() -> QIcon:
    return get_svg_icon("action_add.svg")

def icon_remove() -> QIcon:
    return get_svg_icon("action_remove.svg")

def icon_validate() -> QIcon:
    return get_svg_icon("action_validate.svg")

def icon_clear() -> QIcon:
    return get_svg_icon("action_clear.svg")

def icon_load() -> QIcon:
    return get_svg_icon("action_load.svg")

def icon_search() -> QIcon:
    return get_svg_icon("action_search.svg")

def icon_export_json() -> QIcon:
    return get_svg_icon("action_export_json.svg")

def icon_export_excel() -> QIcon:
    return get_svg_icon("action_export_excel.svg")

def icon_export_arxml() -> QIcon:
    return get_svg_icon("action_export_arxml.svg")

def icon_export_a2l() -> QIcon:
    return get_svg_icon("action_export_a2l.svg")
