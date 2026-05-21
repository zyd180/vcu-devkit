"""Dialog for adding/editing SWC runnables."""

from __future__ import annotations

from PySide6.QtWidgets import (
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

from core.parsers.arxml_parser import RunnableDef


class RunnableDialog(QDialog):
    """Dialog for adding or editing a runnable entity."""

    def __init__(self, runnable: RunnableDef | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑Runnable" if runnable else "添加Runnable")
        self.setMinimumWidth(450)
        self._runnable = runnable
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Basic info
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("如: RE_TorqueCalc")
        if self._runnable:
            self.name_input.setText(self._runnable.name)
        form.addRow("名称:", self.name_input)

        self.trigger_combo = QComboBox()
        self.trigger_combo.addItem("周期触发", True)
        self.trigger_combo.addItem("事件触发", False)
        if self._runnable and self._runnable.period_ms is None:
            self.trigger_combo.setCurrentIndex(1)
        self.trigger_combo.currentIndexChanged.connect(self._on_trigger_changed)
        form.addRow("触发类型:", self.trigger_combo)

        self.period_spin = QSpinBox()
        self.period_spin.setRange(1, 60000)
        self.period_spin.setSuffix(" ms")
        if self._runnable and self._runnable.period_ms is not None:
            self.period_spin.setValue(self._runnable.period_ms)
        else:
            self.period_spin.setValue(10)
        form.addRow("周期:", self.period_spin)

        self.msi_spin = QSpinBox()
        self.msi_spin.setRange(0, 60000)
        self.msi_spin.setSuffix(" ms")
        if self._runnable:
            self.msi_spin.setValue(self._runnable.min_start_interval)
        form.addRow("最小启动间隔:", self.msi_spin)

        layout.addLayout(form)

        # Data read access
        layout.addWidget(QLabel("数据读取访问 (Data Read Access):"))
        self.read_list = QListWidget()
        if self._runnable:
            for r in self._runnable.data_read_access:
                self.read_list.addItem(r)
        layout.addWidget(self.read_list)
        read_btn_layout = QHBoxLayout()
        self.read_input = QLineEdit()
        self.read_input.setPlaceholderText("数据元素名")
        btn_add_read = QPushButton("添加")
        btn_del_read = QPushButton("删除")
        btn_add_read.clicked.connect(lambda: self._add_list_item(self.read_list, self.read_input))
        btn_del_read.clicked.connect(lambda: self._remove_list_item(self.read_list))
        read_btn_layout.addWidget(self.read_input, stretch=1)
        read_btn_layout.addWidget(btn_add_read)
        read_btn_layout.addWidget(btn_del_read)
        layout.addLayout(read_btn_layout)

        # Data write access
        layout.addWidget(QLabel("数据写入访问 (Data Write Access):"))
        self.write_list = QListWidget()
        if self._runnable:
            for w in self._runnable.data_write_access:
                self.write_list.addItem(w)
        layout.addWidget(self.write_list)
        write_btn_layout = QHBoxLayout()
        self.write_input = QLineEdit()
        self.write_input.setPlaceholderText("数据元素名")
        btn_add_write = QPushButton("添加")
        btn_del_write = QPushButton("删除")
        btn_add_write.clicked.connect(lambda: self._add_list_item(self.write_list, self.write_input))
        btn_del_write.clicked.connect(lambda: self._remove_list_item(self.write_list))
        write_btn_layout.addWidget(self.write_input, stretch=1)
        write_btn_layout.addWidget(btn_add_write)
        write_btn_layout.addWidget(btn_del_write)
        layout.addLayout(write_btn_layout)

        # Server call points
        layout.addWidget(QLabel("服务调用点 (Server Call Points):"))
        self.call_list = QListWidget()
        if self._runnable:
            for c in self._runnable.server_call_points:
                self.call_list.addItem(c)
        layout.addWidget(self.call_list)
        call_btn_layout = QHBoxLayout()
        self.call_input = QLineEdit()
        self.call_input.setPlaceholderText("操作名")
        btn_add_call = QPushButton("添加")
        btn_del_call = QPushButton("删除")
        btn_add_call.clicked.connect(lambda: self._add_list_item(self.call_list, self.call_input))
        btn_del_call.clicked.connect(lambda: self._remove_list_item(self.call_list))
        call_btn_layout.addWidget(self.call_input, stretch=1)
        call_btn_layout.addWidget(btn_add_call)
        call_btn_layout.addWidget(btn_del_call)
        layout.addLayout(call_btn_layout)

        self._on_trigger_changed(self.trigger_combo.currentIndex())

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_trigger_changed(self, index: int):
        is_periodic = self.trigger_combo.currentData()
        self.period_spin.setEnabled(is_periodic)

    def _add_list_item(self, list_widget: QListWidget, line_edit: QLineEdit):
        text = line_edit.text().strip()
        if text:
            list_widget.addItem(text)
            line_edit.clear()

    def _remove_list_item(self, list_widget: QListWidget):
        row = list_widget.currentRow()
        if row >= 0:
            list_widget.takeItem(row)

    def _validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "错误", "名称不能为空")
            return
        self.accept()

    def get_runnable(self) -> RunnableDef:
        is_periodic = self.trigger_combo.currentData()
        reads = [self.read_list.item(i).text() for i in range(self.read_list.count())]
        writes = [self.write_list.item(i).text() for i in range(self.write_list.count())]
        calls = [self.call_list.item(i).text() for i in range(self.call_list.count())]
        return RunnableDef(
            name=self.name_input.text().strip(),
            period_ms=self.period_spin.value() if is_periodic else None,
            min_start_interval=self.msi_spin.value(),
            data_read_access=reads,
            data_write_access=writes,
            server_call_points=calls,
        )
