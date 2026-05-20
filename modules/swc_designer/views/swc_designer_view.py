"""SWC Designer main view — SWC tree + port/runnable editors."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QFileDialog, QLabel, QToolBar, QMessageBox,
    QTabWidget, QHeaderView, QAbstractItemView,
    QTableView, QStatusBar, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, Signal, QModelIndex
from PySide6.QtGui import QAction, QFont

from modules.swc_designer.controller import SWCDesignerController
from modules.swc_designer.widgets.port_dialog import PortDialog, InterfaceDialog
from modules.swc_designer.widgets.runnable_dialog import RunnableDialog
from core.parsers.arxml_parser import (
    SWCDef, PortDef, RunnableDef, PortDirection,
    SenderReceiverInterface, ClientServerInterface,
)
from ui.widgets.tree_view import TreeView
from ui.widgets.property_panel import PropertyPanel
from ui.widgets.table_editor import DataTableModel
from ui.widgets.file_worker import FileWorker
from ui.icons import icon_open, icon_save, icon_validate, icon_export_arxml, icon_add, icon_remove, icon_generate


# ── Template dialog ──────────────────────────────────────────────────────────


class TemplateDialog(QDialog):
    """Dialog for selecting an SWC template."""

    def __init__(self, controller: SWCDesignerController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("SWC模板库")
        self.setMinimumSize(500, 400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Category filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("分类:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("全部")
        for cat in self.controller.get_template_categories():
            self.category_combo.addItem(cat)
        self.category_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.category_combo, stretch=1)
        layout.addLayout(filter_layout)

        # Template list
        self.template_list = QListWidget()
        self._populate_templates()
        layout.addWidget(self.template_list)

        # Instance name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("实例名称:"))
        self.instance_name_input = QLineEdit()
        self.instance_name_input.setPlaceholderText("留空则使用模板名")
        name_layout.addWidget(self.instance_name_input, stretch=1)
        layout.addLayout(name_layout)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_templates(self, category: str = "全部"):
        self.template_list.clear()
        categories = self.controller.get_template_categories()
        for cat, names in categories.items():
            if category != "全部" and cat != category:
                continue
            for name in names:
                tpl = self.controller.get_template(name)
                if tpl:
                    item = QListWidgetItem(f"[{cat}] {name} — {tpl.description.split('|')[-1].strip() if '|' in tpl.description else tpl.description}")
                    item.setData(Qt.UserRole, name)
                    self.template_list.addItem(item)

    def _on_filter_changed(self, text: str):
        self._populate_templates(text)

    def get_selected_template(self) -> tuple[str | None, str | None]:
        """Return (template_name, instance_name)."""
        item = self.template_list.currentItem()
        if item is None:
            return None, None
        tpl_name = item.data(Qt.UserRole)
        instance_name = self.instance_name_input.text().strip() or None
        return tpl_name, instance_name


# ── Add SWC dialog ───────────────────────────────────────────────────────────


class AddSWCDialog(QDialog):
    """Dialog for creating a new SWC from scratch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建SWC")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("如: SwcPowerManager")
        form.addRow("SWC名称:", self.name_input)

        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "ApplicationSoftwareComponent",
            "ServiceComponent",
            "ComplexDeviceDriver",
            "SensorActuatorSoftwareComponent",
            "EcuAbstractionSoftwareComponent",
        ])
        form.addRow("组件类型:", self.category_combo)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("组件功能描述")
        form.addRow("描述:", self.desc_input)

        layout = QVBoxLayout(self)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_swc_info(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "category": self.category_combo.currentText(),
            "description": self.desc_input.text().strip(),
        }



# ── Main view ────────────────────────────────────────────────────────────────


class SWCDesignerView(QWidget):
    """SWC Designer module main view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = SWCDesignerController()
        self._current_swc_name: str | None = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ──
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.act_open = QAction(icon_open(), "打开ARXML", self)
        self.act_open.setShortcut("Ctrl+Shift+A")
        self.act_new = QAction(icon_add(), "新建项目", self)
        self.act_save = QAction(icon_save(), "保存JSON", self)
        self.act_add_swc = QAction(icon_add(), "新建SWC", self)
        self.act_from_template = QAction(icon_generate(), "从模板创建", self)
        self.act_remove_swc = QAction(icon_remove(), "删除SWC", self)
        self.act_validate = QAction(icon_validate(), "校验", self)
        self.act_export_arxml = QAction(icon_export_arxml(), "导出ARXML", self)

        toolbar.addAction(self.act_open)
        toolbar.addAction(self.act_new)
        toolbar.addAction(self.act_save)
        toolbar.addAction(self.act_export_arxml)
        toolbar.addSeparator()
        toolbar.addAction(self.act_add_swc)
        toolbar.addAction(self.act_from_template)
        toolbar.addAction(self.act_remove_swc)
        toolbar.addSeparator()
        toolbar.addAction(self.act_validate)

        layout.addWidget(toolbar)

        # ── Info bar ──
        self.info_label = QLabel("未加载ARXML — 点击「新建项目」或「打开ARXML」开始")
        self.info_label.setStyleSheet(
            "background-color: #f8f9fa; border-left: 3px solid #1a73e8; "
            "padding: 6px 12px; font-size: 12px; color: #333;"
        )
        layout.addWidget(self.info_label)

        # ── Main content: tree | detail ──
        splitter = QSplitter(Qt.Horizontal)

        # Left: SWC tree
        self.swc_tree = TreeView()
        self.swc_tree.setMinimumWidth(240)
        splitter.addWidget(self.swc_tree)

        # Right: detail tabs
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # SWC info panel
        self.swc_info_label = QLabel("选择一个SWC查看详情")
        self.swc_info_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 8px; "
            "background-color: #f5f5f5; border-bottom: 1px solid #ddd;"
        )
        right_layout.addWidget(self.swc_info_label)

        # Tabs: Ports | Runnables | Properties
        self.tabs = QTabWidget()

        # Ports tab
        ports_widget = QWidget()
        ports_layout = QVBoxLayout(ports_widget)
        self.port_model = DataTableModel(
            headers=["端口名", "方向", "接口引用"],
            keys=["name", "direction", "interface_ref"],
        )
        self.port_table = QTableView()
        self.port_table.setModel(self.port_model)
        self.port_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.port_table.setAlternatingRowColors(True)
        self.port_table.horizontalHeader().setStretchLastSection(True)
        self.port_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.port_table.verticalHeader().setVisible(False)
        self.port_table.doubleClicked.connect(self._on_port_double_click)
        ports_layout.addWidget(self.port_table)

        port_btn_layout = QHBoxLayout()
        self.btn_add_port = QPushButton("添加端口")
        self.btn_add_port.setProperty("class", "primary")
        self.btn_remove_port = QPushButton("删除端口")
        self.btn_remove_port.setProperty("class", "danger")
        port_btn_layout.addWidget(self.btn_add_port)
        port_btn_layout.addWidget(self.btn_remove_port)
        port_btn_layout.addStretch()
        ports_layout.addLayout(port_btn_layout)
        self.tabs.addTab(ports_widget, "端口")

        # Runnables tab
        runs_widget = QWidget()
        runs_layout = QVBoxLayout(runs_widget)
        self.runnable_model = DataTableModel(
            headers=["Runnable名", "周期(ms)", "触发类型", "数据读取", "数据写入", "服务调用"],
            keys=["name", "period_ms", "trigger", "data_read", "data_write", "server_call"],
        )
        self.runnable_table = QTableView()
        self.runnable_table.setModel(self.runnable_model)
        self.runnable_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.runnable_table.setAlternatingRowColors(True)
        self.runnable_table.horizontalHeader().setStretchLastSection(True)
        self.runnable_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.runnable_table.verticalHeader().setVisible(False)
        self.runnable_table.doubleClicked.connect(self._on_runnable_double_click)
        runs_layout.addWidget(self.runnable_table)

        run_btn_layout = QHBoxLayout()
        self.btn_add_runnable = QPushButton("添加Runnable")
        self.btn_add_runnable.setProperty("class", "primary")
        self.btn_remove_runnable = QPushButton("删除Runnable")
        self.btn_remove_runnable.setProperty("class", "danger")
        run_btn_layout.addWidget(self.btn_add_runnable)
        run_btn_layout.addWidget(self.btn_remove_runnable)
        run_btn_layout.addStretch()
        runs_layout.addLayout(run_btn_layout)
        self.tabs.addTab(runs_widget, "Runnable")

        # Interfaces tab
        ifaces_widget = QWidget()
        ifaces_layout = QVBoxLayout(ifaces_widget)
        self.iface_model = DataTableModel(
            headers=["接口名", "类型", "数据元素/操作"],
            keys=["name", "type", "details"],
        )
        self.iface_table = QTableView()
        self.iface_table.setModel(self.iface_model)
        self.iface_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.iface_table.setAlternatingRowColors(True)
        self.iface_table.horizontalHeader().setStretchLastSection(True)
        self.iface_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.iface_table.verticalHeader().setVisible(False)
        self.iface_table.doubleClicked.connect(self._on_interface_double_click)
        ifaces_layout.addWidget(self.iface_table)

        iface_btn_layout = QHBoxLayout()
        self.btn_add_iface = QPushButton("新建接口")
        self.btn_add_iface.setProperty("class", "primary")
        self.btn_edit_iface = QPushButton("编辑接口")
        self.btn_remove_iface = QPushButton("删除接口")
        self.btn_remove_iface.setProperty("class", "danger")
        self.btn_add_iface.clicked.connect(self._on_add_interface)
        self.btn_edit_iface.clicked.connect(self._on_edit_interface)
        self.btn_remove_iface.clicked.connect(self._on_remove_interface)
        iface_btn_layout.addWidget(self.btn_add_iface)
        iface_btn_layout.addWidget(self.btn_edit_iface)
        iface_btn_layout.addWidget(self.btn_remove_iface)
        iface_btn_layout.addStretch()
        ifaces_layout.addLayout(iface_btn_layout)
        self.tabs.addTab(ifaces_widget, "接口")

        # Properties tab
        self.prop_panel = PropertyPanel()
        self.tabs.addTab(self.prop_panel, "属性")

        right_layout.addWidget(self.tabs, stretch=1)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 940])

        layout.addWidget(splitter, stretch=1)

        # ── Status bar ──
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        layout.addWidget(self.status_bar)

    def _connect_signals(self):
        self.act_open.triggered.connect(self._on_open_arxml)
        self.act_new.triggered.connect(self._on_new_project)
        self.act_save.triggered.connect(self._on_save)
        self.act_add_swc.triggered.connect(self._on_add_swc)
        self.act_from_template.triggered.connect(self._on_from_template)
        self.act_remove_swc.triggered.connect(self._on_remove_swc)
        self.act_validate.triggered.connect(self._on_validate)
        self.act_export_arxml.triggered.connect(self._on_export_arxml)
        self.swc_tree.item_selected.connect(self._on_swc_selected)
        self.btn_add_port.clicked.connect(self._on_add_port)
        self.btn_remove_port.clicked.connect(self._on_remove_port)
        self.btn_add_runnable.clicked.connect(self._on_add_runnable)
        self.btn_remove_runnable.clicked.connect(self._on_remove_runnable)
        self.prop_panel.property_changed.connect(self._on_property_changed)

    # ── File operations ─────────────────────────────────────────────────────

    def _on_open_arxml(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开ARXML文件", "", "ARXML文件 (*.arxml);;所有文件 (*)"
        )
        if not path:
            return
        self.load_file(path)

    def load_file(self, path: str):
        """Programmatically load an ARXML file (used by drag-drop)."""
        if not path:
            return
        self.status_bar.showMessage("正在加载ARXML文件...")
        self._pending_arxml_path = path
        self._worker = FileWorker(self.controller.load_arxml, Path(path))
        self._worker.finished_ok.connect(self._on_arxml_loaded)
        self._worker.finished_err.connect(lambda err: QMessageBox.critical(self, "加载失败", err))
        self._worker.start()

    def _on_arxml_loaded(self, result: tuple):
        success, errors = result
        if not success:
            QMessageBox.critical(self, "加载失败", "\n".join(errors))
            return
        self._refresh_swc_tree()
        self._refresh_interface_table()
        self._update_info_label()
        self.status_bar.showMessage(f"已加载 {self._pending_arxml_path}", 5000)

    def _on_new_project(self):
        self.controller.new_project()
        self._refresh_swc_tree()
        self._update_info_label()
        self.status_bar.showMessage("已创建新项目", 3000)

    def _on_save(self):
        if self.controller.current_data is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存JSON", "", "JSON文件 (*.json);;所有文件 (*)"
        )
        if path:
            success, errors = self.controller.save_json(Path(path))
            if success:
                self.status_bar.showMessage(f"已保存 {path}", 5000)
            else:
                QMessageBox.warning(self, "保存失败", "\n".join(errors))

    # ── SWC operations ──────────────────────────────────────────────────────

    def _on_add_swc(self):
        if self.controller.current_data is None:
            QMessageBox.information(self, "提示", "请先新建项目或打开ARXML文件")
            return
        dialog = AddSWCDialog(self)
        if dialog.exec() != AddSWCDialog.Accepted:
            return
        info = dialog.get_swc_info()
        if not info["name"]:
            QMessageBox.warning(self, "错误", "SWC名称不能为空")
            return
        swc = SWCDef(
            name=info["name"],
            category=info["category"],
            description=info["description"],
        )
        if not self.controller.add_swc(swc):
            QMessageBox.warning(self, "错误", f"SWC '{info['name']}' 已存在")
            return
        self._refresh_swc_tree()
        self._update_info_label()
        self.status_bar.showMessage(f"已添加 SWC: {info['name']}", 3000)

    def _on_from_template(self):
        if self.controller.current_data is None:
            QMessageBox.information(self, "提示", "请先新建项目或打开ARXML文件")
            return
        dialog = TemplateDialog(self.controller, self)
        if dialog.exec() != TemplateDialog.Accepted:
            return
        tpl_name, instance_name = dialog.get_selected_template()
        if tpl_name is None:
            return
        swc = self.controller.create_swc_from_template(tpl_name, instance_name)
        if swc is None:
            QMessageBox.warning(self, "错误", f"模板 '{tpl_name}' 不存在")
            return
        if not self.controller.add_swc(swc):
            QMessageBox.warning(self, "错误", f"SWC '{swc.name}' 已存在")
            return
        self._refresh_swc_tree()
        self._update_info_label()
        self.status_bar.showMessage(f"已从模板创建 SWC: {swc.name}", 3000)

    def _on_remove_swc(self):
        if self._current_swc_name is None:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 SWC '{self._current_swc_name}' 吗？",
        )
        if reply != QMessageBox.Yes:
            return
        self.controller.remove_swc(self._current_swc_name)
        self._current_swc_name = None
        self._refresh_swc_tree()
        self._update_info_label()
        self._clear_detail()
        self.status_bar.showMessage("已删除SWC", 3000)

    def _on_export_arxml(self):
        if self.controller.current_data is None:
            QMessageBox.information(self, "提示", "请先新建项目或打开ARXML文件")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出ARXML", "", "ARXML文件 (*.arxml);;所有文件 (*)"
        )
        if not path:
            return
        result = self.controller.save_arxml(Path(path))
        if result.success:
            self.status_bar.showMessage(f"已导出 ARXML → {path}", 5000)
        else:
            QMessageBox.warning(self, "导出失败", "\n".join(result.errors))

    def _on_validate(self):
        results = self.controller.validate()
        if not results:
            self.status_bar.showMessage("校验通过", 5000)
            return
        errors = [r for r in results if r.severity.value == "error"]
        warnings = [r for r in results if r.severity.value == "warning"]
        msg = f"校验完成: {len(errors)} 错误, {len(warnings)} 警告\n\n"
        for r in results[:20]:
            prefix = "✗" if r.severity.value == "error" else "⚠"
            msg += f"{prefix} [{r.rule_id}] {r.location}: {r.message}\n"
        QMessageBox.information(self, "校验结果", msg)

    # ── SWC selection ───────────────────────────────────────────────────────

    def _on_swc_selected(self, name: str):
        swc = self.controller.get_swc_by_name(name)
        if swc is None:
            return
        self._current_swc_name = name
        self._show_swc_detail(swc)

    def _show_swc_detail(self, swc: SWCDef):
        self.swc_info_label.setText(
            f"SWC: {swc.name}  |  类型: {swc.category}  |  "
            f"端口: {len(swc.ports)}  |  Runnable: {len(swc.runnables)}"
        )

        # Load ports
        port_rows = []
        for p in swc.ports:
            port_rows.append({
                "name": p.name,
                "direction": p.direction.value,
                "interface_ref": p.interface_ref,
            })
        self.port_model.load_data(port_rows)

        # Load runnables
        run_rows = []
        for r in swc.runnables:
            run_rows.append({
                "name": r.name,
                "period_ms": str(r.period_ms) if r.period_ms is not None else "事件触发",
                "trigger": "周期" if r.period_ms is not None else "事件",
                "data_read": ", ".join(r.data_read_access) if r.data_read_access else "-",
                "data_write": ", ".join(r.data_write_access) if r.data_write_access else "-",
                "server_call": ", ".join(r.server_call_points) if r.server_call_points else "-",
            })
        self.runnable_model.load_data(run_rows)

        # Load properties
        desc_parts = swc.description.split("|") if "|" in swc.description else [swc.description, ""]
        self.prop_panel.set_properties(
            swc.name,
            [
                {"name": "name", "label": "SWC名称", "type": "text", "value": swc.name},
                {"name": "category", "label": "组件类型", "type": "combo", "value": swc.category,
                 "options": ["ApplicationSoftwareComponent", "ServiceComponent",
                             "ComplexDeviceDriver", "SensorActuatorSoftwareComponent",
                             "EcuAbstractionSoftwareComponent"]},
                {"name": "description", "label": "描述", "type": "text",
                 "value": desc_parts[-1].strip() if len(desc_parts) > 1 else desc_parts[0].strip()},
            ],
        )

    def _clear_detail(self):
        self.swc_info_label.setText("选择一个SWC查看详情")
        self.port_model.load_data([])
        self.runnable_model.load_data([])
        self.prop_panel.clear()

    # ── Port operations ─────────────────────────────────────────────────────

    def _on_add_port(self):
        if self._current_swc_name is None:
            return
        iface_names = self.controller.get_interface_names()
        dialog = PortDialog(iface_names, parent=self)
        if dialog.exec() != PortDialog.Accepted:
            return
        port = dialog.get_port()
        if not port.name:
            QMessageBox.warning(self, "错误", "端口名不能为空")
            return
        if not self.controller.add_port(self._current_swc_name, port):
            QMessageBox.warning(self, "错误", "端口名已存在")
            return
        swc = self.controller.get_swc_by_name(self._current_swc_name)
        if swc:
            self._show_swc_detail(swc)
        self.status_bar.showMessage(f"已添加端口 {port.name}", 3000)

    def _on_remove_port(self):
        if self._current_swc_name is None:
            return
        selected = self.port_table.selectionModel().selectedRows()
        if not selected:
            return
        port_name = self.port_model.get_row(selected[0].row()).get("name", "")
        if not port_name:
            return
        self.controller.remove_port(self._current_swc_name, port_name)
        swc = self.controller.get_swc_by_name(self._current_swc_name)
        if swc:
            self._show_swc_detail(swc)
        self.status_bar.showMessage(f"已删除端口 {port_name}", 3000)

    # ── Runnable operations ─────────────────────────────────────────────────

    def _on_add_runnable(self):
        if self._current_swc_name is None:
            return
        dialog = RunnableDialog(parent=self)
        if dialog.exec() != RunnableDialog.Accepted:
            return
        runnable = dialog.get_runnable()
        if not runnable.name:
            QMessageBox.warning(self, "错误", "名称不能为空")
            return
        if not self.controller.add_runnable(self._current_swc_name, runnable):
            QMessageBox.warning(self, "错误", "Runnable名已存在")
            return
        swc = self.controller.get_swc_by_name(self._current_swc_name)
        if swc:
            self._show_swc_detail(swc)
        self.status_bar.showMessage(f"已添加Runnable {runnable.name}", 3000)

    def _on_remove_runnable(self):
        if self._current_swc_name is None:
            return
        selected = self.runnable_table.selectionModel().selectedRows()
        if not selected:
            return
        run_name = self.runnable_model.get_row(selected[0].row()).get("name", "")
        if not run_name:
            return
        self.controller.remove_runnable(self._current_swc_name, run_name)
        swc = self.controller.get_swc_by_name(self._current_swc_name)
        if swc:
            self._show_swc_detail(swc)
        self.status_bar.showMessage(f"已删除Runnable {run_name}", 3000)

    # ── Property changes ────────────────────────────────────────────────────

    def _on_property_changed(self, field_name: str, value):
        if self._current_swc_name is None:
            return
        swc = self.controller.get_swc_by_name(self._current_swc_name)
        if swc is None:
            return
        if field_name == "name" and value and value != swc.name:
            # Rename: remove old, add new
            old_name = swc.name
            swc.name = value
            self._current_swc_name = value
            self._refresh_swc_tree()
            self._update_info_label()
        elif field_name == "category":
            swc.category = value
        elif field_name == "description":
            swc.description = value
        self.status_bar.showMessage(f"已更新 {field_name}", 3000)

    # ── Port editing ────────────────────────────────────────────────────────

    def _on_port_double_click(self, index: QModelIndex):
        """Edit a port on double-click."""
        if self._current_swc_name is None:
            return
        row_data = self.port_model.get_row(index.row())
        port_name = row_data.get("name", "")
        if not port_name:
            return
        swc = self.controller.get_swc_by_name(self._current_swc_name)
        if swc is None:
            return
        # Find port
        port = None
        for p in swc.ports:
            if p.name == port_name:
                port = p
                break
        if port is None:
            return
        iface_names = self.controller.get_interface_names()
        dialog = PortDialog(iface_names, port=port, parent=self)
        if dialog.exec() != PortDialog.Accepted:
            return
        new_port = dialog.get_port()
        if not new_port.name:
            return
        # Remove old, add new (name may have changed)
        self.controller.remove_port(self._current_swc_name, port_name)
        self.controller.add_port(self._current_swc_name, new_port)
        self._show_swc_detail(swc)
        self.status_bar.showMessage(f"已更新端口 {new_port.name}", 3000)

    # ── Runnable editing ─────────────────────────────────────────────────────

    def _on_runnable_double_click(self, index: QModelIndex):
        """Edit a runnable on double-click."""
        if self._current_swc_name is None:
            return
        row_data = self.runnable_model.get_row(index.row())
        run_name = row_data.get("name", "")
        if not run_name:
            return
        swc = self.controller.get_swc_by_name(self._current_swc_name)
        if swc is None:
            return
        runnable = None
        for r in swc.runnables:
            if r.name == run_name:
                runnable = r
                break
        if runnable is None:
            return
        dialog = RunnableDialog(runnable=runnable, parent=self)
        if dialog.exec() != RunnableDialog.Accepted:
            return
        new_run = dialog.get_runnable()
        # Remove old, add new
        self.controller.remove_runnable(self._current_swc_name, run_name)
        self.controller.add_runnable(self._current_swc_name, new_run)
        self._show_swc_detail(swc)
        self.status_bar.showMessage(f"已更新Runnable {new_run.name}", 3000)

    # ── Interface operations ────────────────────────────────────────────────

    def _on_add_interface(self):
        dialog = InterfaceDialog(parent=self)
        if dialog.exec() != InterfaceDialog.Accepted:
            return
        iface = dialog.get_interface()
        if not iface.name:
            QMessageBox.warning(self, "错误", "接口名不能为空")
            return
        if not self.controller.add_interface(iface):
            QMessageBox.warning(self, "错误", f"接口 '{iface.name}' 已存在")
            return
        self._refresh_interface_table()
        self.status_bar.showMessage(f"已添加接口 {iface.name}", 3000)

    def _on_edit_interface(self):
        selected = self.iface_table.selectionModel().selectedRows()
        if not selected:
            return
        iface_name = self.iface_model.get_row(selected[0].row()).get("name", "")
        if not iface_name:
            return
        iface = self.controller.get_interface_by_name(iface_name)
        if iface is None:
            return
        dialog = InterfaceDialog(iface=iface, parent=self)
        if dialog.exec() != InterfaceDialog.Accepted:
            return
        new_iface = dialog.get_interface()
        self.controller.update_interface(iface_name, new_iface)
        self._refresh_interface_table()
        self.status_bar.showMessage(f"已更新接口 {new_iface.name}", 3000)

    def _on_remove_interface(self):
        selected = self.iface_table.selectionModel().selectedRows()
        if not selected:
            return
        iface_name = self.iface_model.get_row(selected[0].row()).get("name", "")
        if not iface_name:
            return
        self.controller.remove_interface(iface_name)
        self._refresh_interface_table()
        self.status_bar.showMessage(f"已删除接口 {iface_name}", 3000)

    def _on_interface_double_click(self, index: QModelIndex):
        self._on_edit_interface()

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _refresh_interface_table(self):
        rows = []
        for iface in self.controller.get_interfaces():
            if isinstance(iface, SenderReceiverInterface):
                details = ", ".join(f"{de.name}:{de.type_ref}" for de in iface.data_elements)
                rows.append({"name": iface.name, "type": "Sender-Receiver", "details": details})
            elif isinstance(iface, ClientServerInterface):
                details = ", ".join(iface.operations)
                rows.append({"name": iface.name, "type": "Client-Server", "details": details})
        self.iface_model.load_data(rows)

    def _refresh_swc_tree(self):
        self.swc_tree.clear()
        if self.controller.current_data is None:
            return
        # Group by category
        cat_groups: dict[str, list] = {}
        for swc in self.controller.get_swcs():
            cat_groups.setdefault(swc.category, []).append(swc)

        for cat, swcs in sorted(cat_groups.items()):
            parent = self.swc_tree.add_top_level_item(f"{cat} ({len(swcs)})")
            for swc in swcs:
                port_count = len(swc.ports)
                run_count = len(swc.runnables)
                label = f"{swc.name}  [P:{port_count} R:{run_count}]"
                self.swc_tree.add_child_item(parent, swc.name)
        self.swc_tree.tree.expandAll()

    def _update_info_label(self):
        swcs = self.controller.get_swcs()
        ifaces = self.controller.get_interfaces()
        total_ports = sum(len(s.ports) for s in swcs)
        total_runs = sum(len(s.runnables) for s in swcs)
        self.info_label.setText(
            f"SWC: {len(swcs)}  |  端口: {total_ports}  |  "
            f"Runnable: {total_runs}  |  接口: {len(ifaces)}"
        )
