"""Batch signal editing dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class BatchEditDialog(QDialog):
    """Dialog for batch-editing multiple signals at once.

    Only checked fields are applied to the selected signals.
    """

    def __init__(self, signal_names: list[str], parent=None):
        super().__init__(parent)
        self.signal_names = signal_names
        self.setWindowTitle(f"批量编辑 ({len(signal_names)} 个信号)")
        self.setMinimumWidth(420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Info
        info = QLabel(
            f"选中的信号: {', '.join(self.signal_names[:8])}"
            + (f" ... 等{len(self.signal_names)}个" if len(self.signal_names) > 8 else "")
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Editable fields
        fields_group = QGroupBox("要修改的属性（勾选后生效）")
        form = QFormLayout(fields_group)

        self.fields: dict[str, tuple[QCheckBox, object]] = {}

        # Byte order
        cb_byte_order = QCheckBox()
        combo_byte_order = QComboBox()
        combo_byte_order.addItems(["little_endian", "big_endian"])
        combo_byte_order.setEnabled(False)
        cb_byte_order.toggled.connect(combo_byte_order.setEnabled)
        row = QHBoxLayout()
        row.addWidget(cb_byte_order)
        row.addWidget(combo_byte_order)
        form.addRow("字节序:", row)
        self.fields["byte_order"] = (cb_byte_order, combo_byte_order)

        # Value type
        cb_vt = QCheckBox()
        combo_vt = QComboBox()
        combo_vt.addItems(["unsigned", "signed"])
        combo_vt.setEnabled(False)
        cb_vt.toggled.connect(combo_vt.setEnabled)
        row = QHBoxLayout()
        row.addWidget(cb_vt)
        row.addWidget(combo_vt)
        form.addRow("值类型:", row)
        self.fields["value_type"] = (cb_vt, combo_vt)

        # Factor
        cb_factor = QCheckBox()
        spin_factor = QDoubleSpinBox()
        spin_factor.setRange(-1e6, 1e6)
        spin_factor.setDecimals(6)
        spin_factor.setEnabled(False)
        cb_factor.toggled.connect(spin_factor.setEnabled)
        row = QHBoxLayout()
        row.addWidget(cb_factor)
        row.addWidget(spin_factor)
        form.addRow("Factor:", row)
        self.fields["factor"] = (cb_factor, spin_factor)

        # Offset
        cb_offset = QCheckBox()
        spin_offset = QDoubleSpinBox()
        spin_offset.setRange(-1e6, 1e6)
        spin_offset.setDecimals(6)
        spin_offset.setEnabled(False)
        cb_offset.toggled.connect(spin_offset.setEnabled)
        row = QHBoxLayout()
        row.addWidget(cb_offset)
        row.addWidget(spin_offset)
        form.addRow("Offset:", row)
        self.fields["offset"] = (cb_offset, spin_offset)

        # Unit
        cb_unit = QCheckBox()
        edit_unit = QLineEdit()
        edit_unit.setEnabled(False)
        cb_unit.toggled.connect(edit_unit.setEnabled)
        row = QHBoxLayout()
        row.addWidget(cb_unit)
        row.addWidget(edit_unit)
        form.addRow("单位:", row)
        self.fields["unit"] = (cb_unit, edit_unit)

        # Receivers
        cb_recv = QCheckBox()
        edit_recv = QLineEdit()
        edit_recv.setPlaceholderText("逗号分隔，如: BMS,MCU")
        edit_recv.setEnabled(False)
        cb_recv.toggled.connect(edit_recv.setEnabled)
        row = QHBoxLayout()
        row.addWidget(cb_recv)
        row.addWidget(edit_recv)
        form.addRow("接收方:", row)
        self.fields["receivers"] = (cb_recv, edit_recv)

        layout.addWidget(fields_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("应用")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(apply_btn)
        layout.addLayout(btn_layout)

    def _on_apply(self):
        """Validate and accept."""
        changes = self.get_changes()
        if not changes:
            return
        self.accept()

    def get_changes(self) -> dict[str, object]:
        """Return dict of field_name → new_value for checked fields."""
        result = {}
        for field_name, (checkbox, widget) in self.fields.items():
            if not checkbox.isChecked():
                continue
            if isinstance(widget, QComboBox):
                result[field_name] = widget.currentText()
            elif isinstance(widget, QDoubleSpinBox):
                result[field_name] = widget.value()
            elif isinstance(widget, QSpinBox):
                result[field_name] = widget.value()
            elif isinstance(widget, QLineEdit):
                result[field_name] = widget.text()
        return result
