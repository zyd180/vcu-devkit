"""Dialog for adding/editing calibration parameters."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QDoubleSpinBox, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt


class ParamDialog(QDialog):
    """Dialog for adding or editing a calibration parameter."""

    def __init__(self, groups: list[str], swcs: list[str],
                 param_data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑标定参数" if param_data else "新建标定参数")
        self.setMinimumWidth(450)
        self._param = param_data
        self._groups = groups
        self._swcs = swcs
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("如: K_TorqueMaxLimit")
        if self._param:
            self.name_input.setText(self._param["name"])
            self.name_input.setReadOnly(True)
        form.addRow("参数名:", self.name_input)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["VALUE", "CURVE", "MAP", "ASCII", "CUBE", "VAL_BLK"])
        if self._param:
            idx = self.type_combo.findText(self._param.get("data_type", "VALUE"))
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
        form.addRow("数据类型:", self.type_combo)

        self.group_combo = QComboBox()
        self.group_combo.setEditable(True)
        self.group_combo.addItems(self._groups)
        if self._param and self._param.get("group_name"):
            self.group_combo.setCurrentText(self._param["group_name"])
        form.addRow("分组:", self.group_combo)

        self.swc_combo = QComboBox()
        self.swc_combo.setEditable(True)
        self.swc_combo.addItem("")
        self.swc_combo.addItems(self._swcs)
        if self._param and self._param.get("swc_name"):
            self.swc_combo.setCurrentText(self._param["swc_name"])
        form.addRow("关联SWC:", self.swc_combo)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("参数功能描述")
        if self._param:
            self.desc_input.setText(self._param.get("description", ""))
        form.addRow("描述:", self.desc_input)

        self.unit_input = QLineEdit()
        self.unit_input.setPlaceholderText("如: Nm, rpm, °C")
        if self._param:
            self.unit_input.setText(self._param.get("unit", ""))
        form.addRow("单位:", self.unit_input)

        self.default_spin = QDoubleSpinBox()
        self.default_spin.setRange(-1e9, 1e9)
        self.default_spin.setDecimals(4)
        if self._param and self._param.get("default_value") is not None:
            self.default_spin.setValue(self._param["default_value"])
        form.addRow("默认值:", self.default_spin)

        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-1e9, 1e9)
        self.min_spin.setDecimals(4)
        if self._param and self._param.get("min_value") is not None:
            self.min_spin.setValue(self._param["min_value"])
        form.addRow("最小值:", self.min_spin)

        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-1e9, 1e9)
        self.max_spin.setDecimals(4)
        if self._param and self._param.get("max_value") is not None:
            self.max_spin.setValue(self._param["max_value"])
        form.addRow("最大值:", self.max_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "错误", "参数名不能为空")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "data_type": self.type_combo.currentText(),
            "group_name": self.group_combo.currentText().strip() or None,
            "swc_name": self.swc_combo.currentText().strip() or None,
            "description": self.desc_input.text().strip(),
            "unit": self.unit_input.text().strip(),
            "default_value": self.default_spin.value(),
            "min_value": self.min_spin.value(),
            "max_value": self.max_spin.value(),
        }
