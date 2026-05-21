"""Dialog for adding/editing UDS diagnostic services."""

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
    QVBoxLayout,
)


class ServiceDialog(QDialog):
    """Dialog for adding or editing a UDS diagnostic service."""

    def __init__(self, svc_data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑UDS服务" if svc_data else "新建UDS服务")
        self.setMinimumWidth(500)
        self._svc = svc_data
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.sid_input = QLineEdit()
        self.sid_input.setPlaceholderText("如: 0x22")
        if self._svc:
            self.sid_input.setText(self._svc["sid"])
        form.addRow("SID:", self.sid_input)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("如: ReadDataByIdentifier")
        if self._svc:
            self.name_input.setText(self._svc["service_name"])
        form.addRow("服务名:", self.name_input)

        self.security_combo = QComboBox()
        self.security_combo.addItems(["default", "Level 1", "Level 2", "Level 3", "Level 5"])
        self.security_combo.setEditable(True)
        if self._svc and self._svc.get("security_level"):
            self.security_combo.setCurrentText(self._svc["security_level"])
        form.addRow("安全等级:", self.security_combo)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("服务功能描述")
        if self._svc:
            self.desc_input.setText(self._svc.get("description", ""))
        form.addRow("描述:", self.desc_input)

        self.enabled_check = QCheckBox("启用")
        self.enabled_check.setChecked(True)
        if self._svc:
            self.enabled_check.setChecked(self._svc.get("enabled", True))
        form.addRow("", self.enabled_check)

        layout.addLayout(form)

        # Sub-functions
        layout.addWidget(QLabel("子功能 (Sub-Functions):"))
        self.sub_list = QListWidget()
        if self._svc:
            for sf in self._svc.get("sub_functions", []):
                self.sub_list.addItem(sf)
        layout.addWidget(self.sub_list)
        sub_btn_layout = QHBoxLayout()
        self.sub_input = QLineEdit()
        self.sub_input.setPlaceholderText("如: 0x01 DefaultSession")
        btn_add_sub = QPushButton("添加")
        btn_del_sub = QPushButton("删除")
        btn_add_sub.clicked.connect(lambda: self._add_item(self.sub_list, self.sub_input))
        btn_del_sub.clicked.connect(lambda: self._remove_item(self.sub_list))
        sub_btn_layout.addWidget(self.sub_input, stretch=1)
        sub_btn_layout.addWidget(btn_add_sub)
        sub_btn_layout.addWidget(btn_del_sub)
        layout.addLayout(sub_btn_layout)

        # NRC list
        layout.addWidget(QLabel("否定响应码 (NRC):"))
        self.nrc_list = QListWidget()
        if self._svc:
            for nrc in self._svc.get("nrc_list", []):
                self.nrc_list.addItem(nrc)
        layout.addWidget(self.nrc_list)
        nrc_btn_layout = QHBoxLayout()
        self.nrc_input = QLineEdit()
        self.nrc_input.setPlaceholderText("如: 0x12 subFunctionNotSupported")
        btn_add_nrc = QPushButton("添加")
        btn_del_nrc = QPushButton("删除")
        btn_add_nrc.clicked.connect(lambda: self._add_item(self.nrc_list, self.nrc_input))
        btn_del_nrc.clicked.connect(lambda: self._remove_item(self.nrc_list))
        nrc_btn_layout.addWidget(self.nrc_input, stretch=1)
        nrc_btn_layout.addWidget(btn_add_nrc)
        nrc_btn_layout.addWidget(btn_del_nrc)
        layout.addLayout(nrc_btn_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_item(self, list_widget: QListWidget, line_edit: QLineEdit):
        text = line_edit.text().strip()
        if text:
            list_widget.addItem(text)
            line_edit.clear()

    def _remove_item(self, list_widget: QListWidget):
        row = list_widget.currentRow()
        if row >= 0:
            list_widget.takeItem(row)

    def _validate_and_accept(self):
        if not self.sid_input.text().strip():
            QMessageBox.warning(self, "错误", "SID不能为空")
            return
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "错误", "服务名不能为空")
            return
        self.accept()

    def get_data(self) -> dict:
        subs = [self.sub_list.item(i).text() for i in range(self.sub_list.count())]
        nrcs = [self.nrc_list.item(i).text() for i in range(self.nrc_list.count())]
        return {
            "sid": self.sid_input.text().strip(),
            "service_name": self.name_input.text().strip(),
            "security_level": self.security_combo.currentText(),
            "description": self.desc_input.text().strip(),
            "enabled": self.enabled_check.isChecked(),
            "sub_functions": subs,
            "nrc_list": nrcs,
        }
