"""Dialogs for adding/editing SWC ports and interfaces."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.parsers.arxml_parser import (
    ClientServerInterface,
    DataElementDef,
    PortDef,
    PortDirection,
    SenderReceiverInterface,
)


class PortDialog(QDialog):
    """Dialog for adding or editing a port."""

    def __init__(self, interface_names: list[str], port: PortDef | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑端口" if port else "添加端口")
        self.setMinimumWidth(400)
        self._interface_names = interface_names
        self._port = port
        self._setup_ui()

    def _setup_ui(self):
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("如: VehicleSpeed_P")
        if self._port:
            self.name_input.setText(self._port.name)
        form.addRow("端口名:", self.name_input)

        self.dir_combo = QComboBox()
        self.dir_combo.addItem("P-Port (Provided)", PortDirection.PROVIDED.value)
        self.dir_combo.addItem("R-Port (Required)", PortDirection.REQUIRED.value)
        if self._port and self._port.direction == PortDirection.REQUIRED:
            self.dir_combo.setCurrentIndex(1)
        form.addRow("方向:", self.dir_combo)

        self.iface_combo = QComboBox()
        self.iface_combo.setEditable(True)
        self.iface_combo.addItems(self._interface_names)
        if self._port:
            idx = self.iface_combo.findText(self._port.interface_ref)
            if idx >= 0:
                self.iface_combo.setCurrentIndex(idx)
            else:
                self.iface_combo.setEditText(self._port.interface_ref)
        form.addRow("接口引用:", self.iface_combo)

        layout = QVBoxLayout(self)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_port(self) -> PortDef:
        return PortDef(
            name=self.name_input.text().strip(),
            direction=PortDirection(self.dir_combo.currentData()),
            interface_ref=self.iface_combo.currentText().strip(),
        )


class InterfaceDialog(QDialog):
    """Dialog for adding/editing a Sender-Receiver or Client-Server interface."""

    def __init__(self, iface: SenderReceiverInterface | ClientServerInterface | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑接口" if iface else "新建接口")
        self.setMinimumSize(500, 400)
        self._iface = iface
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Type + name
        top_form = QFormLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItem("Sender-Receiver", "sr")
        self.type_combo.addItem("Client-Server", "cs")
        if isinstance(self._iface, ClientServerInterface):
            self.type_combo.setCurrentIndex(1)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        top_form.addRow("接口类型:", self.type_combo)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("如: I_VehicleSpeed")
        if self._iface:
            self.name_input.setText(self._iface.name)
        top_form.addRow("接口名:", self.name_input)
        layout.addLayout(top_form)

        # Tabs for elements/operations
        self.detail_tabs = QTabWidget()

        # SR: data elements
        self.sr_widget = QWidget()
        sr_layout = QVBoxLayout(self.sr_widget)
        self.elements_list = QListWidget()
        sr_layout.addWidget(self.elements_list)
        sr_btn_layout = QHBoxLayout()
        self.btn_add_element = QPushButton("添加数据元素")
        self.btn_remove_element = QPushButton("删除")
        self.btn_add_element.clicked.connect(self._on_add_element)
        self.btn_remove_element.clicked.connect(self._on_remove_element)
        sr_btn_layout.addWidget(self.btn_add_element)
        sr_btn_layout.addWidget(self.btn_remove_element)
        sr_btn_layout.addStretch()
        sr_layout.addLayout(sr_btn_layout)
        self.detail_tabs.addTab(self.sr_widget, "数据元素")

        # CS: operations
        self.cs_widget = QWidget()
        cs_layout = QVBoxLayout(self.cs_widget)
        self.ops_list = QListWidget()
        cs_layout.addWidget(self.ops_list)
        cs_btn_layout = QHBoxLayout()
        self.btn_add_op = QPushButton("添加操作")
        self.btn_remove_op = QPushButton("删除")
        self.btn_add_op.clicked.connect(self._on_add_op)
        self.btn_remove_op.clicked.connect(self._on_remove_op)
        cs_btn_layout.addWidget(self.btn_add_op)
        cs_btn_layout.addWidget(self.btn_remove_op)
        cs_btn_layout.addStretch()
        cs_layout.addLayout(cs_btn_layout)
        self.detail_tabs.addTab(self.cs_widget, "操作")

        layout.addWidget(self.detail_tabs)

        # Populate existing data
        if isinstance(self._iface, SenderReceiverInterface):
            for de in self._iface.data_elements:
                self.elements_list.addItem(f"{de.name} : {de.type_ref}")
        elif isinstance(self._iface, ClientServerInterface):
            for op in self._iface.operations:
                self.ops_list.addItem(op)

        self._on_type_changed(0)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_type_changed(self, index: int):
        is_sr = self.type_combo.currentData() == "sr"
        self.sr_widget.setEnabled(is_sr)
        self.cs_widget.setEnabled(not is_sr)

    def _on_add_element(self):
        name = f"DE_NewElement_{self.elements_list.count() + 1}"
        self.elements_list.addItem(f"{name} : uint8")

    def _on_remove_element(self):
        row = self.elements_list.currentRow()
        if row >= 0:
            self.elements_list.takeItem(row)

    def _on_add_op(self):
        name = f"Op_NewOperation_{self.ops_list.count() + 1}"
        self.ops_list.addItem(name)

    def _on_remove_op(self):
        row = self.ops_list.currentRow()
        if row >= 0:
            self.ops_list.takeItem(row)

    def _validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "错误", "接口名不能为空")
            return
        self.accept()

    def get_interface(self) -> SenderReceiverInterface | ClientServerInterface:
        name = self.name_input.text().strip()
        if self.type_combo.currentData() == "sr":
            elements = []
            for i in range(self.elements_list.count()):
                text = self.elements_list.item(i).text()
                parts = text.split(":", 1)
                de_name = parts[0].strip()
                type_ref = parts[1].strip() if len(parts) > 1 else "uint8"
                elements.append(DataElementDef(name=de_name, type_ref=type_ref))
            return SenderReceiverInterface(name=name, data_elements=elements)
        else:
            ops = [self.ops_list.item(i).text() for i in range(self.ops_list.count())]
            return ClientServerInterface(name=name, operations=ops)
