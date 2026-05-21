"""Calibration Manager main view — parameter tree + table + editor."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTableView,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from modules.calib_manager.controller import CalibManagerController
from modules.calib_manager.widgets.param_dialog import ParamDialog
from ui.icons import icon_add, icon_export_a2l, icon_export_json, icon_load, icon_open, icon_save, icon_validate
from ui.widgets.file_worker import FileWorker
from ui.widgets.tree_view import TreeView

# ── Table model ──────────────────────────────────────────────────────────────


class ParamTableModel(QAbstractTableModel):
    """Table model for calibration parameters."""

    HEADERS = ["参数名", "类型", "分组", "SWC", "默认值", "最小值", "最大值", "单位", "描述"]
    KEYS = [
        "name",
        "data_type",
        "group_name",
        "swc_name",
        "default_value",
        "min_value",
        "max_value",
        "unit",
        "description",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []
        self._id_map: dict[int, int] = {}

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.EditRole):
            return None
        row = self._rows[index.row()]
        key = self.KEYS[index.column()]
        val = row.get(key, "")
        if val is None:
            return ""
        if isinstance(val, float):
            return f"{val:g}"
        return str(val)

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):
        return False  # editing via dialog only

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def load_data(self, rows: list[dict], id_map: dict[int, int] | None = None):
        self.beginResetModel()
        self._rows = rows
        self._id_map = id_map or {}
        self.endResetModel()

    def get_row(self, row: int) -> dict:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return {}

    def get_db_id(self, row: int) -> int | None:
        return self._id_map.get(row)


# ── Main view ────────────────────────────────────────────────────────────────


class CalibManagerView(QWidget):
    """Calibration Manager module main view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = CalibManagerController()
        self._selected_param_id: int | None = None
        self._setup_ui()
        self._connect_signals()
        self._refresh_all()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ──
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.act_load_a2l = QAction(icon_load(), "加载A2L", self)
        self.act_import_a2l = QAction(icon_open(), "导入A2L到DB", self)
        self.act_writeback_a2l = QAction(icon_save(), "回写A2L", self)
        self.act_load_dcm = QAction(icon_load(), "加载DCM", self)
        self.act_import_dcm = QAction(icon_open(), "导入DCM值", self)
        self.act_export_dcm = QAction(icon_save(), "导出DCM", self)
        self.act_add_param = QAction(icon_add(), "新建参数", self)
        self.act_export_json = QAction(icon_export_json(), "导出JSON", self)
        self.act_export_a2l = QAction(icon_export_a2l(), "导出A2L摘要", self)
        self.act_validate = QAction(icon_validate(), "校验", self)

        toolbar.addAction(self.act_load_a2l)
        toolbar.addAction(self.act_import_a2l)
        toolbar.addAction(self.act_writeback_a2l)
        toolbar.addSeparator()
        toolbar.addAction(self.act_load_dcm)
        toolbar.addAction(self.act_import_dcm)
        toolbar.addAction(self.act_export_dcm)
        toolbar.addSeparator()

        # Page selector
        toolbar.addWidget(QLabel(" 标定页: "))
        self.page_combo = QComboBox()
        self.page_combo.setMinimumWidth(120)
        toolbar.addWidget(self.page_combo)
        self.act_new_page = QAction("新建页", self)
        self.act_delete_page = QAction("删除页", self)
        toolbar.addAction(self.act_new_page)
        toolbar.addAction(self.act_delete_page)
        toolbar.addSeparator()

        toolbar.addAction(self.act_add_param)
        toolbar.addSeparator()
        toolbar.addAction(self.act_export_json)
        toolbar.addAction(self.act_export_a2l)
        toolbar.addAction(self.act_validate)

        layout.addWidget(toolbar)

        # ── Search bar ──
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索参数名或描述...")
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # ── Info bar ──
        self.info_label = QLabel("标定参数管理")
        self.info_label.setStyleSheet(
            "background-color: #f8f9fa; border-left: 3px solid #1a73e8; "
            "padding: 6px 12px; font-size: 12px; color: #333;"
        )
        layout.addWidget(self.info_label)

        # ── Main content: tree | tabs ──
        splitter = QSplitter(Qt.Horizontal)

        # Left: group tree
        self.group_tree = TreeView()
        self.group_tree.setMinimumWidth(200)
        splitter.addWidget(self.group_tree)

        # Right: tabs
        self.tabs = QTabWidget()

        # Parameter table tab
        param_widget = QWidget()
        param_layout = QVBoxLayout(param_widget)
        self.param_model = ParamTableModel()
        self.param_table = QTableView()
        self.param_table.setModel(self.param_model)
        self.param_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.param_table.setAlternatingRowColors(True)
        self.param_table.horizontalHeader().setStretchLastSection(True)
        self.param_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.param_table.verticalHeader().setVisible(False)
        self.param_table.doubleClicked.connect(self._on_param_double_click)
        param_layout.addWidget(self.param_table)

        param_btn_layout = QHBoxLayout()
        btn_edit = QPushButton("编辑参数")
        btn_del = QPushButton("删除参数")
        btn_edit.clicked.connect(self._on_edit_param)
        btn_del.clicked.connect(self._on_remove_param)
        param_btn_layout.addWidget(btn_edit)
        param_btn_layout.addWidget(btn_del)
        param_btn_layout.addStretch()
        param_layout.addLayout(param_btn_layout)
        self.tabs.addTab(param_widget, "参数列表")

        # A2L info tab
        a2l_widget = QWidget()
        a2l_layout = QVBoxLayout(a2l_widget)
        self.a2l_info = QTextEdit()
        self.a2l_info.setReadOnly(True)
        a2l_layout.addWidget(self.a2l_info)
        self.tabs.addTab(a2l_widget, "A2L信息")

        # Validation tab
        val_widget = QWidget()
        val_layout = QVBoxLayout(val_widget)
        self.val_output = QTextEdit()
        self.val_output.setReadOnly(True)
        val_layout.addWidget(self.val_output)
        self.tabs.addTab(val_widget, "校验结果")

        # Change history tab
        hist_widget = QWidget()
        hist_layout = QVBoxLayout(hist_widget)
        hist_btn = QPushButton("刷新历史")
        hist_btn.clicked.connect(self._on_refresh_history)
        hist_layout.addWidget(hist_btn)
        self.hist_output = QTextEdit()
        self.hist_output.setReadOnly(True)
        hist_layout.addWidget(self.hist_output)
        self.tabs.addTab(hist_widget, "变更历史")

        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 980])

        layout.addWidget(splitter, stretch=1)

        # ── Status bar ──
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        layout.addWidget(self.status_bar)

    def _connect_signals(self):
        self.act_load_a2l.triggered.connect(self._on_load_a2l)
        self.act_import_a2l.triggered.connect(self._on_import_a2l)
        self.act_writeback_a2l.triggered.connect(self._on_writeback_a2l)
        self.act_load_dcm.triggered.connect(self._on_load_dcm)
        self.act_import_dcm.triggered.connect(self._on_import_dcm)
        self.act_export_dcm.triggered.connect(self._on_export_dcm)
        self.act_add_param.triggered.connect(self._on_add_param)
        self.act_export_json.triggered.connect(self._on_export_json)
        self.act_export_a2l.triggered.connect(self._on_export_a2l)
        self.act_validate.triggered.connect(self._on_validate)
        self.act_new_page.triggered.connect(self._on_new_page)
        self.act_delete_page.triggered.connect(self._on_delete_page)
        self.page_combo.currentTextChanged.connect(self._on_page_changed)
        self.group_tree.item_selected.connect(self._on_group_selected)
        self.group_tree.child_selected.connect(self._on_tree_param_clicked)
        self.param_table.selectionModel().currentChanged.connect(self._on_param_selected)

    # ── A2L operations ─────────────────────────────────────────────────────

    def _on_load_a2l(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载A2L文件", "", "A2L文件 (*.a2l);;所有文件 (*)")
        if not path:
            return
        self.load_file(path)

    def load_file(self, path: str):
        """Programmatically load an A2L file (used by drag-drop)."""
        if not path:
            return
        self.status_bar.showMessage("正在加载A2L文件...")
        self._pending_a2l_path = path
        self._worker = FileWorker(self.controller.load_a2l, Path(path))
        self._worker.finished_ok.connect(self._on_a2l_loaded)
        self._worker.finished_err.connect(lambda err: QMessageBox.critical(self, "加载失败", err))
        self._worker.start()

    def _on_a2l_loaded(self, result: tuple):
        ok, errs = result
        if not ok:
            QMessageBox.critical(self, "加载失败", "\n".join(errs))
            return
        self._show_a2l_info()
        self.status_bar.showMessage(f"已加载A2L: {self._pending_a2l_path}", 5000)

    def _on_import_a2l(self):
        if self.controller.current_a2l is None:
            QMessageBox.information(self, "提示", "请先加载A2L文件")
            return
        imported, skipped = self.controller.import_a2l_to_db()
        self._refresh_all()
        self.status_bar.showMessage(f"导入完成: {imported} 参数, {skipped} 跳过", 5000)

    def _on_writeback_a2l(self):
        if self.controller.current_a2l is None:
            QMessageBox.information(self, "提示", "请先加载A2L文件")
            return
        reply = QMessageBox.question(
            self,
            "回写A2L",
            "将数据库中标定量的修改写回A2L文件。\n"
            f"原始文件: {self.controller.current_a2l.source_path}\n\n"
            '选择"另存为"可保存到新文件，不修改原文件。',
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if reply == QMessageBox.Cancel:
            return
        if reply == QMessageBox.Discard:
            # Overwrite original
            ok, errs = self.controller.writeback_a2l()
        else:
            # Save as
            path, _ = QFileDialog.getSaveFileName(self, "另存为A2L文件", "", "A2L文件 (*.a2l);;所有文件 (*)")
            if not path:
                return
            ok, errs = self.controller.writeback_a2l(Path(path))
        if ok:
            self.status_bar.showMessage("A2L回写完成", 5000)
        else:
            QMessageBox.warning(self, "回写失败", "\n".join(errs))

    def _show_a2l_info(self):
        a2l = self.controller.current_a2l
        if a2l is None:
            return
        lines = [
            f"A2L文件: {a2l.source_path}",
            f"CHARACTERISTIC: {len(a2l.characteristics)}",
            f"MEASUREMENT: {len(a2l.measurements)}",
            f"COMPU_METHOD: {len(a2l.compu_methods)}",
            "",
            "--- CHARACTERISTIC 列表 ---",
        ]
        for c in a2l.characteristics[:50]:
            lines.append(f"  {c.name} [{c.type}] addr=0x{c.address:X} [{c.unit}] {c.lower_limit}~{c.upper_limit}")
        if len(a2l.characteristics) > 50:
            lines.append(f"  ... 共 {len(a2l.characteristics)} 个")
        lines.append("")
        lines.append("--- MEASUREMENT 列表 ---")
        for m in a2l.measurements[:50]:
            lines.append(f"  {m.name} [{m.data_type}] [{m.unit}] {m.lower_limit}~{m.upper_limit}")
        if len(a2l.measurements) > 50:
            lines.append(f"  ... 共 {len(a2l.measurements)} 个")
        self.a2l_info.setPlainText("\n".join(lines))

    # ── DCM operations ──────────────────────────────────────────────────────

    def _on_load_dcm(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载DCM文件", "", "DCM文件 (*.dcm);;所有文件 (*)")
        if not path:
            return
        ok, errs = self.controller.load_dcm(Path(path))
        if ok:
            dcm = self.controller.current_dcm
            count = len(dcm.characteristics) if dcm else 0
            self.status_bar.showMessage(f"已加载DCM: {path} ({count} 参数)", 5000)
        else:
            QMessageBox.critical(self, "加载失败", "\n".join(errs))

    def _on_import_dcm(self):
        if self.controller.current_dcm is None:
            QMessageBox.information(self, "提示", "请先加载DCM文件")
            return
        matched, updated, not_found = self.controller.import_dcm_values()
        self._refresh_all()
        self.status_bar.showMessage(f"DCM导入完成: 匹配 {matched}, 更新 {updated}, 未找到 {not_found}", 5000)

    def _on_export_dcm(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出DCM文件", "", "DCM文件 (*.dcm);;所有文件 (*)")
        if not path:
            return
        ok, errs = self.controller.export_dcm(Path(path))
        if ok:
            self.status_bar.showMessage(f"已导出DCM → {path}", 5000)
        else:
            QMessageBox.warning(self, "导出失败", "\n".join(errs))

    # ── Parameter operations ───────────────────────────────────────────────

    def _on_add_param(self):
        groups = self.controller.get_groups()
        swcs = self.controller.get_swcs()
        dialog = ParamDialog(groups, swcs, parent=self)
        if dialog.exec() != ParamDialog.Accepted:
            return
        data = dialog.get_data()
        result = self.controller.add_param(**data)
        if result is None:
            QMessageBox.warning(self, "错误", "参数名已存在或创建失败")
            return
        self._refresh_all()
        self.status_bar.showMessage(f"已添加参数: {data['name']}", 3000)

    def _on_edit_param(self):
        selected = self.param_table.selectionModel().selectedRows()
        if not selected:
            self.status_bar.showMessage("请先选中一行参数", 3000)
            return
        db_id = self.param_model.get_db_id(selected[0].row())
        if db_id is None:
            self.status_bar.showMessage("无法获取参数ID", 3000)
            return
        param_data = self.controller.get_param_as_dict(db_id)
        if param_data is None:
            self.status_bar.showMessage(f"参数(ID={db_id})不存在", 3000)
            return
        groups = self.controller.get_groups()
        swcs = self.controller.get_swcs()
        dialog = ParamDialog(groups, swcs, param_data=param_data, parent=self)
        if dialog.exec() != ParamDialog.Accepted:
            return
        data = dialog.get_data()
        ok = self.controller.update_param(
            db_id,
            group_name=data["group_name"],
            swc_name=data["swc_name"],
            default_value=data["default_value"],
            min_value=data["min_value"],
            max_value=data["max_value"],
            unit=data["unit"],
            description=data["description"],
        )
        if ok:
            self._refresh_all()
            self.status_bar.showMessage(f"已更新参数: {data['name']}", 3000)
        else:
            QMessageBox.warning(self, "错误", f"保存失败: {data['name']}")

    def _on_remove_param(self):
        selected = self.param_table.selectionModel().selectedRows()
        if not selected:
            return
        db_id = self.param_model.get_db_id(selected[0].row())
        if db_id is None:
            return
        self.controller.remove_param(db_id)
        self._refresh_all()
        self.status_bar.showMessage("已删除参数", 3000)

    def _on_param_double_click(self, index: QModelIndex):
        self._on_edit_param()

    def _on_param_selected(self, current, previous):
        if not current.isValid():
            return
        db_id = self.param_model.get_db_id(current.row())
        if db_id is None:
            return
        self._selected_param_id = db_id

    def _on_refresh_history(self):
        if self._selected_param_id is not None:
            self._show_change_history(self._selected_param_id)
        else:
            self.hist_output.setPlainText("请先选中一个参数。")

    def _show_change_history(self, param_id: int):
        changes = self.controller.get_change_history(param_id)
        if not changes:
            self.hist_output.setPlainText("无变更记录。")
            return
        lines = [f"变更历史 ({len(changes)} 条记录)\n"]
        for c in changes:
            lines.append(f"  [{c.changed_at}] {c.changed_by or 'unknown'}")
            lines.append(f"    {c.old_value} → {c.new_value}")
            if c.reason:
                lines.append(f"    原因: {c.reason}")
            lines.append("")
        self.hist_output.setPlainText("\n".join(lines))

    def _on_search(self, keyword: str):
        if not keyword.strip():
            self._refresh_param_table()
            return
        results = self.controller.search_params(keyword.strip())
        rows = []
        id_map = {}
        for i, p in enumerate(results):
            rows.append(self._param_to_row(p))
            id_map[i] = p.id
        self.param_model.load_data(rows, id_map)

    def _on_group_selected(self, name: str):
        group_key = name.rstrip(")").rsplit(" (", 1)[0]
        if group_key == "未分组":
            params = [p for p in self.controller.get_params() if not p.group_name]
        else:
            params = self.controller.get_params(group=group_key)
        rows = []
        id_map = {}
        for i, p in enumerate(params[: self._TABLE_MAX_ROWS]):
            rows.append(self._param_to_row(p))
            id_map[i] = p.id
        self.param_model.load_data(rows, id_map)

    def _on_tree_param_clicked(self, name: str):
        """Click a parameter name in the group tree → open edit dialog."""
        p = self.controller.get_param_by_name(name)
        if p is None:
            return
        param_data = self.controller.get_param_as_dict(p.id)
        if param_data is None:
            return
        groups = self.controller.get_groups()
        swcs = self.controller.get_swcs()
        dialog = ParamDialog(groups, swcs, param_data=param_data, parent=self)
        if dialog.exec() != ParamDialog.Accepted:
            return
        data = dialog.get_data()
        ok = self.controller.update_param(
            p.id,
            group_name=data["group_name"],
            swc_name=data["swc_name"],
            default_value=data["default_value"],
            min_value=data["min_value"],
            max_value=data["max_value"],
            unit=data["unit"],
            description=data["description"],
        )
        if ok:
            self._refresh_all()
            self.status_bar.showMessage(f"已更新参数: {data['name']}", 3000)

    # ── Export / Validation ─────────────────────────────────────────────────

    def _on_export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出标定参数", "", "JSON文件 (*.json);;所有文件 (*)")
        if not path:
            return
        ok, errs = self.controller.export_json(Path(path))
        if ok:
            self.status_bar.showMessage(f"已导出 → {path}", 5000)
        else:
            QMessageBox.warning(self, "导出失败", "\n".join(errs))

    def _on_export_a2l(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出A2L摘要", "", "A2L文件 (*.a2l);;所有文件 (*)")
        if not path:
            return
        ok, errs = self.controller.export_a2l_summary(Path(path))
        if ok:
            self.status_bar.showMessage(f"已导出A2L摘要 → {path}", 5000)
        else:
            QMessageBox.warning(self, "导出失败", "\n".join(errs))

    def _on_validate(self):
        issues = self.controller.validate()
        self.val_output.clear()
        if not issues:
            self.val_output.setPlainText("校验通过，无问题。")
            self.status_bar.showMessage("校验通过", 5000)
            return
        lines = []
        for issue in issues:
            prefix = "✗" if issue["type"] == "error" else "⚠" if issue["type"] == "warning" else "ℹ"
            lines.append(f"{prefix} [{issue['rule']}] {issue['location']}: {issue['message']}")
        self.val_output.setPlainText("\n".join(lines))
        self.tabs.setCurrentIndex(2)
        self.status_bar.showMessage(f"校验完成: {len(issues)} 问题", 5000)

    # ── Page management ─────────────────────────────────────────────────────

    def _on_new_page(self):
        name, ok = QInputDialog.getText(self, "新建标定页", "页面名称:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if not self.controller.create_page(name):
            QMessageBox.warning(self, "错误", f"页面 '{name}' 已存在或名称无效")
            return
        self._refresh_pages()
        self.page_combo.setCurrentText(name)

    def _on_delete_page(self):
        page = self.controller.get_current_page()
        if page == "default":
            QMessageBox.information(self, "提示", "不能删除 default 页面")
            return
        reply = QMessageBox.question(
            self,
            "删除标定页",
            f"确定删除页面 '{page}' 及其所有参数？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        ok, msg = self.controller.delete_page(page)
        if ok:
            self._refresh_pages()
            self._refresh_all()
            self.status_bar.showMessage(msg, 5000)
        else:
            QMessageBox.warning(self, "删除失败", msg)

    def _on_page_changed(self, page: str):
        if not page:
            return
        self.controller.set_current_page(page)
        self._refresh_all()

    def _refresh_pages(self):
        current = self.page_combo.currentText()
        self.page_combo.blockSignals(True)
        self.page_combo.clear()
        pages = self.controller.list_pages()
        self.page_combo.addItems(pages)
        if current in pages:
            self.page_combo.setCurrentText(current)
        else:
            self.page_combo.setCurrentText(self.controller.get_current_page())
        self.page_combo.blockSignals(False)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _refresh_all(self):
        self._refresh_pages()
        self._refresh_group_tree()
        self._refresh_param_table()
        self._update_info_label()

    def _refresh_group_tree(self):
        self.group_tree.clear()
        groups = self.controller.get_params_by_group()
        for group_name, params in sorted(groups.items()):
            parent = self.group_tree.add_top_level_item(f"{group_name} ({len(params)})")
            for p in params:
                self.group_tree.add_child_item(parent, p.name)
        self.group_tree.tree.expandAll()

    _TABLE_MAX_ROWS = 1000

    def _refresh_param_table(self):
        params = self.controller.get_params()
        total = len(params)
        display = params[: self._TABLE_MAX_ROWS]
        rows = []
        id_map = {}
        for i, p in enumerate(display):
            rows.append(self._param_to_row(p))
            id_map[i] = p.id
        self.param_model.load_data(rows, id_map)
        if total > self._TABLE_MAX_ROWS:
            self.status_bar.showMessage(f"显示 {self._TABLE_MAX_ROWS} / {total} 条（使用搜索缩小范围）", 0)

    def _param_to_row(self, p) -> dict:
        return {
            "name": p.name,
            "data_type": p.data_type,
            "group_name": p.group_name or "",
            "swc_name": p.swc_name or "",
            "default_value": p.default_value,
            "min_value": p.min_value,
            "max_value": p.max_value,
            "unit": p.unit or "",
            "description": p.description or "",
        }

    def _update_info_label(self):
        params = self.controller.get_params()
        groups = self.controller.get_groups()
        swcs = self.controller.get_swcs()
        a2l_info = ""
        if self.controller.current_a2l:
            a2l_info = f"  |  A2L: {len(self.controller.current_a2l.characteristics)} chars"
        dcm_info = ""
        if self.controller.current_dcm:
            dcm_info = f"  |  DCM: {len(self.controller.current_dcm.characteristics)} params"
        self.info_label.setText(f"参数: {len(params)}  |  分组: {len(groups)}  |  SWC: {len(swcs)}{a2l_info}{dcm_info}")

    def filter(self, query: str) -> int:
        """Filter parameter table by query. Returns match count."""
        query_lower = query.lower()
        visible = 0
        for row in range(self.param_model.rowCount()):
            row_data = self.param_model.get_row(row)
            text = f"{row_data.get('name', '')} {row_data.get('description', '')}"
            match = not query or query_lower in text.lower()
            self.param_table.setRowHidden(row, not match)
            if match:
                visible += 1
        # Filter group tree
        tree = self.group_tree.tree
        for i in range(tree.topLevelItemCount()):
            parent = tree.topLevelItem(i)
            any_visible = False
            for j in range(parent.childCount()):
                child = parent.child(j)
                match = not query or query_lower in child.text(0).lower()
                child.setHidden(not match)
                if match:
                    any_visible = True
            parent.setHidden(not any_visible and query != "")
        return visible
