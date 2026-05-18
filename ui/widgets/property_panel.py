"""Property panel for editing selected item properties."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QLabel, QGroupBox,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal


class PropertyPanel(QWidget):
    """Property editor panel that shows editable fields for a selected item."""

    property_changed = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fields: dict[str, QWidget] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.title_label = QLabel("属性")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 4px;")
        layout.addWidget(self.title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        self.form_widget = QWidget()
        self.form_layout = QFormLayout(self.form_widget)
        self.form_layout.setLabelAlignment(Qt.AlignRight)
        self.form_layout.setSpacing(8)

        scroll.setWidget(self.form_widget)
        layout.addWidget(scroll)

    def clear(self):
        """Clear all property fields."""
        self._fields.clear()
        while self.form_layout.rowCount():
            self.form_layout.removeRow(0)

    def set_properties(self, title: str, fields: list[dict]):
        """
        Set property fields.

        fields: list of dicts with keys:
            - name: str (field identifier)
            - label: str (display label)
            - type: "text" | "int" | "float" | "combo" | "bool"
            - value: current value
            - options: list (for combo type)
            - min/max: number (for int/float type)
        """
        self.clear()
        self.title_label.setText(title)

        for field_def in fields:
            name = field_def["name"]
            label = field_def["label"]
            ftype = field_def.get("type", "text")
            value = field_def.get("value", "")

            widget = self._create_field_widget(ftype, field_def)
            if widget is not None:
                self._fields[name] = widget
                self.form_layout.addRow(label + ":", widget)

    def _create_field_widget(self, ftype: str, field_def: dict) -> QWidget | None:
        """Create appropriate widget for field type."""
        value = field_def.get("value", "")

        if ftype == "text":
            widget = QLineEdit(str(value))
            widget.editingFinished.connect(lambda n=field_def["name"], w=widget: self.property_changed.emit(n, w.text()))
            return widget

        if ftype == "int":
            widget = QSpinBox()
            widget.setMinimum(field_def.get("min", -999999))
            widget.setMaximum(field_def.get("max", 999999))
            widget.setValue(int(value) if value else 0)
            widget.editingFinished.connect(lambda n=field_def["name"], w=widget: self.property_changed.emit(n, w.value()))
            return widget

        if ftype == "float":
            widget = QDoubleSpinBox()
            widget.setMinimum(field_def.get("min", -999999.0))
            widget.setMaximum(field_def.get("max", 999999.0))
            widget.setDecimals(field_def.get("decimals", 2))
            widget.setValue(float(value) if value else 0.0)
            widget.editingFinished.connect(lambda n=field_def["name"], w=widget: self.property_changed.emit(n, w.value()))
            return widget

        if ftype == "combo":
            widget = QComboBox()
            options = field_def.get("options", [])
            widget.addItems(options)
            if value in options:
                widget.setCurrentText(str(value))
            widget.currentTextChanged.connect(lambda v, n=field_def["name"]: self.property_changed.emit(n, v))
            return widget

        if ftype == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(value))
            widget.toggled.connect(lambda v, n=field_def["name"]: self.property_changed.emit(n, v))
            return widget

        return None

    def get_value(self, name: str) -> object:
        """Get current value of a field."""
        widget = self._fields.get(name)
        if widget is None:
            return None
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        return None

    def get_all_values(self) -> dict[str, object]:
        """Get all field values."""
        return {name: self.get_value(name) for name in self._fields}
