"""Dialog for adding/editing DTC definitions."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class DTCDialog(QDialog):
    """Dialog for adding or editing a DTC definition."""

    def __init__(self, dtc_data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑DTC" if dtc_data else "新建DTC")
        self.setMinimumWidth(450)
        self._dtc = dtc_data
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("如: 0xD001 或 P0100")
        if self._dtc:
            self.code_input.setText(self._dtc["dtc_code"])
            self.code_input.setReadOnly(True)
        form.addRow("DTC编码:", self.code_input)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("故障描述")
        if self._dtc:
            self.desc_input.setText(self._dtc["description"])
        form.addRow("描述:", self.desc_input)

        self.severity_combo = QComboBox()
        self.severity_combo.addItems(["warning", "critical", "fault", "info"])
        if self._dtc and self._dtc.get("severity"):
            idx = self.severity_combo.findText(self._dtc["severity"])
            if idx >= 0:
                self.severity_combo.setCurrentIndex(idx)
        form.addRow("严重等级:", self.severity_combo)

        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["counter", "timer", "immediate", ""])
        self.strategy_combo.setEditable(True)
        if self._dtc and self._dtc.get("debounce_strategy"):
            self.strategy_combo.setCurrentText(self._dtc["debounce_strategy"])
        form.addRow("去抖策略:", self.strategy_combo)

        self.counter_spin = QSpinBox()
        self.counter_spin.setRange(0, 10000)
        if self._dtc and self._dtc.get("debounce_counter"):
            self.counter_spin.setValue(self._dtc["debounce_counter"])
        form.addRow("去抖计数:", self.counter_spin)

        self.time_spin = QSpinBox()
        self.time_spin.setRange(0, 60000)
        self.time_spin.setSuffix(" ms")
        if self._dtc and self._dtc.get("debounce_time_ms"):
            self.time_spin.setValue(self._dtc["debounce_time_ms"])
        form.addRow("去抖时间:", self.time_spin)

        self.obd_check = QCheckBox("OBD相关")
        if self._dtc:
            self.obd_check.setChecked(self._dtc.get("obd_related", False))
        form.addRow("", self.obd_check)

        layout.addLayout(form)

        # Snapshot DIDs
        layout.addWidget(QLabel("快照数据ID (Snapshot DIDs):"))
        self.snapshot_list = QListWidget()
        if self._dtc:
            for sid in self._dtc.get("snapshot_ids", []):
                self.snapshot_list.addItem(sid)
        layout.addWidget(self.snapshot_list)
        snap_btn_layout = QHBoxLayout()
        self.snap_input = QLineEdit()
        self.snap_input.setPlaceholderText("DID名称，如: VehicleSpeed")
        btn_add_snap = QPushButton("添加")
        btn_del_snap = QPushButton("删除")
        btn_add_snap.clicked.connect(self._add_snapshot)
        btn_del_snap.clicked.connect(self._remove_snapshot)
        snap_btn_layout.addWidget(self.snap_input, stretch=1)
        snap_btn_layout.addWidget(btn_add_snap)
        snap_btn_layout.addWidget(btn_del_snap)
        layout.addLayout(snap_btn_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_snapshot(self):
        text = self.snap_input.text().strip()
        if text:
            self.snapshot_list.addItem(text)
            self.snap_input.clear()

    def _remove_snapshot(self):
        row = self.snapshot_list.currentRow()
        if row >= 0:
            self.snapshot_list.takeItem(row)

    def _validate_and_accept(self):
        if not self.code_input.text().strip():
            QMessageBox.warning(self, "错误", "DTC编码不能为空")
            return
        if not self.desc_input.text().strip():
            QMessageBox.warning(self, "错误", "描述不能为空")
            return
        self.accept()

    def get_data(self) -> dict:
        snapshots = [self.snapshot_list.item(i).text() for i in range(self.snapshot_list.count())]
        return {
            "dtc_code": self.code_input.text().strip(),
            "description": self.desc_input.text().strip(),
            "severity": self.severity_combo.currentText(),
            "debounce_strategy": self.strategy_combo.currentText() or None,
            "debounce_counter": self.counter_spin.value() or None,
            "debounce_time_ms": self.time_spin.value() or None,
            "obd_related": self.obd_check.isChecked(),
            "snapshot_ids": snapshots,
        }
