"""Dialog for adding traceability links."""

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
    QVBoxLayout,
)


class LinkDialog(QDialog):
    """Dialog for adding a traceability link from a requirement to an artifact."""

    def __init__(self, req_id: str, artifacts: dict[str, list[str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"添加追溯链接 — {req_id}")
        self.setMinimumWidth(450)
        self._artifacts = artifacts
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.type_combo = QComboBox()
        for link_type, targets in self._artifacts.items():
            self.type_combo.addItem(f"{link_type} ({len(targets)})", link_type)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("链接类型:", self.type_combo)

        layout.addLayout(form)

        layout.addWidget(QLabel("选择目标:"))
        self.target_list = QListWidget()
        self._populate_targets()
        layout.addWidget(self.target_list)

        # Manual target input
        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("或手动输入:"))
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("目标名称")
        manual_layout.addWidget(self.manual_input, stretch=1)
        layout.addLayout(manual_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_type_changed(self, index: int):
        self._populate_targets()

    def _populate_targets(self):
        self.target_list.clear()
        link_type = self.type_combo.currentData()
        targets = self._artifacts.get(link_type, [])
        for t in targets:
            self.target_list.addItem(t)

    def _validate_and_accept(self):
        if not self.get_target():
            QMessageBox.warning(self, "错误", "请选择或输入一个目标")
            return
        self.accept()

    def get_link_type(self) -> str:
        return self.type_combo.currentData() or ""

    def get_target(self) -> str:
        manual = self.manual_input.text().strip()
        if manual:
            return manual
        item = self.target_list.currentItem()
        return item.text() if item else ""


class RequirementDialog(QDialog):
    """Dialog for adding/editing a requirement."""

    def __init__(self, req_data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑需求" if req_data else "新建需求")
        self.setMinimumWidth(400)
        self._req = req_data
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.req_id_input = QLineEdit()
        self.req_id_input.setPlaceholderText("如: REQ_VCU_001")
        if self._req:
            self.req_id_input.setText(self._req["req_id"])
            self.req_id_input.setReadOnly(True)
        form.addRow("需求ID:", self.req_id_input)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("需求标题")
        if self._req:
            self.title_input.setText(self._req["title"])
        form.addRow("标题:", self.title_input)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("需求描述")
        if self._req:
            self.desc_input.setText(self._req.get("description", ""))
        form.addRow("描述:", self.desc_input)

        self.module_combo = QComboBox()
        self.module_combo.setEditable(True)
        self.module_combo.addItems(["CAN Builder", "SWC Designer", "诊断 Builder", "标定 Manager", "测试 Gen", "通用"])
        if self._req and self._req.get("module_name"):
            self.module_combo.setCurrentText(self._req["module_name"])
        form.addRow("所属模块:", self.module_combo)

        self.source_combo = QComboBox()
        self.source_combo.setEditable(True)
        self.source_combo.addItems(["feishu", "excel", "doors", "manual", "import"])
        if self._req and self._req.get("source"):
            self.source_combo.setCurrentText(self._req["source"])
        form.addRow("来源:", self.source_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        if not self.req_id_input.text().strip():
            QMessageBox.warning(self, "错误", "需求ID不能为空")
            return
        if not self.title_input.text().strip():
            QMessageBox.warning(self, "错误", "标题不能为空")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "req_id": self.req_id_input.text().strip(),
            "title": self.title_input.text().strip(),
            "description": self.desc_input.text().strip(),
            "module_name": self.module_combo.currentText().strip(),
            "source": self.source_combo.currentText().strip(),
        }
