"""Diagnostic Builder main view — DTC tree + UDS service editor + snapshots."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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

from modules.diag_builder.controller import DiagBuilderController
from modules.diag_builder.widgets.dtc_dialog import DTCDialog
from modules.diag_builder.widgets.service_dialog import ServiceDialog
from ui.icons import icon_add, icon_export_json, icon_load, icon_open, icon_validate
from ui.widgets.file_worker import FileWorker
from ui.widgets.tree_view import TreeView

# ── Table models ─────────────────────────────────────────────────────────────


class DTCTableModel(QAbstractTableModel):
    """Table model for DTC definitions."""

    HEADERS = ["DTC编码", "描述", "严重等级", "去抖策略", "OBD", "快照DIDs"]
    KEYS = ["dtc_code", "description", "severity", "debounce_strategy", "obd_related", "snapshots"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []
        self._id_map: dict[int, int] = {}  # row → db id

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
        if key == "obd_related":
            return "是" if val else "否"
        if isinstance(val, list):
            return ", ".join(val)
        return str(val) if val is not None else ""

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


class ServiceTableModel(QAbstractTableModel):
    """Table model for UDS services."""

    HEADERS = ["SID", "服务名", "安全等级", "子功能", "描述", "状态"]
    KEYS = ["sid", "service_name", "security_level", "sub_functions", "description", "enabled"]

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
        if key == "sub_functions" and isinstance(val, list):
            return ", ".join(val)
        if key == "enabled":
            return "启用" if val else "禁用"
        return str(val) if val is not None else ""

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


class DiagBuilderView(QWidget):
    """Diagnostic Builder module main view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = DiagBuilderController()
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
        self.act_add_dtc = QAction(icon_add(), "新建DTC", self)
        self.act_import_dtcs = QAction(icon_open(), "导入DTC", self)
        self.act_add_service = QAction(icon_add(), "新建UDS服务", self)
        self.act_load_standard = QAction(icon_load(), "加载标准服务", self)
        self.act_export = QAction(icon_export_json(), "导出JSON", self)
        self.act_import_json = QAction(icon_open(), "导入JSON", self)
        self.act_import_odx = QAction(icon_open(), "导入ODX", self)
        self.act_validate = QAction(icon_validate(), "校验", self)

        toolbar.addAction(self.act_add_dtc)
        toolbar.addAction(self.act_import_dtcs)
        toolbar.addSeparator()
        toolbar.addAction(self.act_add_service)
        toolbar.addAction(self.act_load_standard)
        toolbar.addSeparator()
        toolbar.addAction(self.act_export)
        toolbar.addAction(self.act_import_json)
        toolbar.addAction(self.act_import_odx)
        toolbar.addAction(self.act_validate)

        layout.addWidget(toolbar)

        # ── Info bar ──
        self.info_label = QLabel("诊断配置")
        self.info_label.setStyleSheet(
            "background-color: #f8f9fa; border-left: 3px solid #1a73e8; "
            "padding: 6px 12px; font-size: 12px; color: #333;"
        )
        layout.addWidget(self.info_label)

        # ── Main content: tree | tabs ──
        splitter = QSplitter(Qt.Horizontal)

        # Left: DTC tree by severity
        self.dtc_tree = TreeView()
        self.dtc_tree.setMinimumWidth(220)
        splitter.addWidget(self.dtc_tree)

        # Right: tabs
        self.tabs = QTabWidget()

        # DTC table tab
        dtc_widget = QWidget()
        dtc_layout = QVBoxLayout(dtc_widget)
        self.dtc_model = DTCTableModel()
        self.dtc_table = QTableView()
        self.dtc_table.setModel(self.dtc_model)
        self.dtc_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dtc_table.setAlternatingRowColors(True)
        self.dtc_table.horizontalHeader().setStretchLastSection(True)
        self.dtc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.dtc_table.verticalHeader().setVisible(False)
        self.dtc_table.doubleClicked.connect(self._on_dtc_double_click)
        dtc_layout.addWidget(self.dtc_table)

        dtc_btn_layout = QHBoxLayout()
        btn_edit_dtc = QPushButton("编辑DTC")
        btn_del_dtc = QPushButton("删除DTC")
        btn_edit_dtc.clicked.connect(self._on_edit_dtc)
        btn_del_dtc.clicked.connect(self._on_remove_dtc)
        dtc_btn_layout.addWidget(btn_edit_dtc)
        dtc_btn_layout.addWidget(btn_del_dtc)
        dtc_btn_layout.addStretch()
        dtc_layout.addLayout(dtc_btn_layout)
        self.tabs.addTab(dtc_widget, "DTC列表")

        # UDS services tab
        svc_widget = QWidget()
        svc_layout = QVBoxLayout(svc_widget)
        self.svc_model = ServiceTableModel()
        self.svc_table = QTableView()
        self.svc_table.setModel(self.svc_model)
        self.svc_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.svc_table.setAlternatingRowColors(True)
        self.svc_table.horizontalHeader().setStretchLastSection(True)
        self.svc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.svc_table.verticalHeader().setVisible(False)
        self.svc_table.doubleClicked.connect(self._on_service_double_click)
        svc_layout.addWidget(self.svc_table)

        svc_btn_layout = QHBoxLayout()
        btn_edit_svc = QPushButton("编辑服务")
        btn_del_svc = QPushButton("删除服务")
        btn_edit_svc.clicked.connect(self._on_edit_service)
        btn_del_svc.clicked.connect(self._on_remove_service)
        svc_btn_layout.addWidget(btn_edit_svc)
        svc_btn_layout.addWidget(btn_del_svc)
        svc_btn_layout.addStretch()
        svc_layout.addLayout(svc_btn_layout)
        self.tabs.addTab(svc_widget, "UDS服务")

        # Snapshot tab
        snap_widget = QWidget()
        snap_layout = QVBoxLayout(snap_widget)
        self.snap_info = QTextEdit()
        self.snap_info.setReadOnly(True)
        snap_layout.addWidget(self.snap_info)
        self.tabs.addTab(snap_widget, "快照配置")

        # Validation tab
        val_widget = QWidget()
        val_layout = QVBoxLayout(val_widget)
        self.val_output = QTextEdit()
        self.val_output.setReadOnly(True)
        val_layout.addWidget(self.val_output)
        self.tabs.addTab(val_widget, "校验结果")

        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 960])

        layout.addWidget(splitter, stretch=1)

        # ── Status bar ──
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        layout.addWidget(self.status_bar)

    def _connect_signals(self):
        self.act_add_dtc.triggered.connect(self._on_add_dtc)
        self.act_import_dtcs.triggered.connect(self._on_import_dtcs)
        self.act_add_service.triggered.connect(self._on_add_service)
        self.act_load_standard.triggered.connect(self._on_load_standard)
        self.act_export.triggered.connect(self._on_export)
        self.act_import_json.triggered.connect(self._on_import_json)
        self.act_import_odx.triggered.connect(self._on_import_odx)
        self.act_validate.triggered.connect(self._on_validate)
        self.dtc_tree.item_selected.connect(self._on_dtc_tree_selected)

    # ── DTC operations ─────────────────────────────────────────────────────

    def _on_add_dtc(self):
        dialog = DTCDialog(parent=self)
        if dialog.exec() != DTCDialog.Accepted:
            return
        data = dialog.get_data()
        result = self.controller.add_dtc(
            dtc_code=data["dtc_code"],
            description=data["description"],
            severity=data["severity"],
            debounce_strategy=data["debounce_strategy"],
            debounce_counter=data["debounce_counter"],
            debounce_time_ms=data["debounce_time_ms"],
            obd_related=data["obd_related"],
        )
        if result is None:
            QMessageBox.warning(self, "错误", "DTC编码已存在或创建失败")
            return
        if data["snapshot_ids"]:
            result.set_snapshot_ids(data["snapshot_ids"])
            result.save()
        self._refresh_all()
        self.status_bar.showMessage(f"已添加DTC: {data['dtc_code']}", 3000)

    def _on_edit_dtc(self):
        selected = self.dtc_table.selectionModel().selectedRows()
        if not selected:
            return
        db_id = self.dtc_model.get_db_id(selected[0].row())
        if db_id is None:
            return
        dtc_data = self.controller.get_dtc_as_dict(db_id)
        if dtc_data is None:
            return
        dialog = DTCDialog(dtc_data=dtc_data, parent=self)
        if dialog.exec() != DTCDialog.Accepted:
            return
        data = dialog.get_data()
        self.controller.update_dtc(
            db_id,
            description=data["description"],
            severity=data["severity"],
            debounce_strategy=data["debounce_strategy"],
            debounce_counter=data["debounce_counter"],
            debounce_time_ms=data["debounce_time_ms"],
            obd_related=data["obd_related"],
        )
        from core.db.models import DTCDefinition

        dtc = DTCDefinition.get_by_id(db_id)
        dtc.set_snapshot_ids(data["snapshot_ids"])
        dtc.save()
        self._refresh_all()
        self.status_bar.showMessage(f"已更新DTC: {data['dtc_code']}", 3000)

    def _on_remove_dtc(self):
        selected = self.dtc_table.selectionModel().selectedRows()
        if not selected:
            return
        db_id = self.dtc_model.get_db_id(selected[0].row())
        if db_id is None:
            return
        self.controller.remove_dtc(db_id)
        self._refresh_all()
        self.status_bar.showMessage("已删除DTC", 3000)

    def _on_dtc_double_click(self, index: QModelIndex):
        self._on_edit_dtc()

    def _on_import_dtcs(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入DTC列表", "", "JSON文件 (*.json);;CSV文件 (*.csv);;所有文件 (*)"
        )
        if not path:
            return
        try:
            import json

            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(data, list):
                imported, skipped = self.controller.import_dtcs_from_list(data)
            elif isinstance(data, dict) and "dtcs" in data:
                imported, skipped = self.controller.import_dtcs_from_list(data["dtcs"])
            else:
                QMessageBox.warning(self, "格式错误", "JSON格式不识别")
                return
            self._refresh_all()
            self.status_bar.showMessage(f"导入完成: {imported} 成功, {skipped} 跳过", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))

    def _on_dtc_tree_selected(self, name: str):
        """Select DTC from tree and highlight in table."""
        for row in range(self.dtc_model.rowCount()):
            if self.dtc_model.get_row(row).get("dtc_code") == name:
                self.dtc_table.selectRow(row)
                return

    # ── UDS Service operations ─────────────────────────────────────────────

    def _on_add_service(self):
        dialog = ServiceDialog(parent=self)
        if dialog.exec() != ServiceDialog.Accepted:
            return
        data = dialog.get_data()
        svc = self.controller.add_service(
            sid=data["sid"],
            service_name=data["service_name"],
            security_level=data["security_level"],
            description=data["description"],
            enabled=data["enabled"],
        )
        if svc is None:
            QMessageBox.warning(self, "错误", "SID已存在或创建失败")
            return
        svc.set_sub_functions(data["sub_functions"])
        svc.set_nrc_list(data["nrc_list"])
        svc.save()
        self._refresh_all()
        self.status_bar.showMessage(f"已添加服务: {data['service_name']}", 3000)

    def _on_edit_service(self):
        selected = self.svc_table.selectionModel().selectedRows()
        if not selected:
            return
        db_id = self.svc_model.get_db_id(selected[0].row())
        if db_id is None:
            return
        svc_data = self.controller.get_service_as_dict(db_id)
        if svc_data is None:
            return
        dialog = ServiceDialog(svc_data=svc_data, parent=self)
        if dialog.exec() != ServiceDialog.Accepted:
            return
        data = dialog.get_data()
        self.controller.update_service(
            db_id,
            sid=data["sid"],
            service_name=data["service_name"],
            security_level=data["security_level"],
            description=data["description"],
            enabled=data["enabled"],
        )
        from core.db.models import DiagService

        svc = DiagService.get_by_id(db_id)
        svc.set_sub_functions(data["sub_functions"])
        svc.set_nrc_list(data["nrc_list"])
        svc.save()
        self._refresh_all()
        self.status_bar.showMessage(f"已更新服务: {data['service_name']}", 3000)

    def _on_remove_service(self):
        selected = self.svc_table.selectionModel().selectedRows()
        if not selected:
            return
        db_id = self.svc_model.get_db_id(selected[0].row())
        if db_id is None:
            return
        self.controller.remove_service(db_id)
        self._refresh_all()
        self.status_bar.showMessage("已删除服务", 3000)

    def _on_service_double_click(self, index: QModelIndex):
        self._on_edit_service()

    def _on_load_standard(self):
        """Load standard UDS services."""
        reply = QMessageBox.question(
            self,
            "加载标准服务",
            "将加载13个标准UDS服务（0x10~0x85），已有服务不会重复添加。\n继续？",
        )
        if reply != QMessageBox.Yes:
            return
        count = 0
        for std in self.controller.get_standard_services():
            if not self.controller.get_service_by_sid(std["sid"]):
                svc = self.controller.add_service(
                    sid=std["sid"],
                    service_name=std["name"],
                    description=std["desc"],
                )
                if svc:
                    svc.set_sub_functions(std["sub"])
                    svc.save()
                    count += 1
        self._refresh_all()
        self.status_bar.showMessage(f"已加载 {count} 个标准服务", 5000)

    # ── Export / Import ─────────────────────────────────────────────────────

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出诊断配置", "", "JSON文件 (*.json);;所有文件 (*)")
        if not path:
            return
        ok, errs = self.controller.export_json(Path(path))
        if ok:
            self.status_bar.showMessage(f"已导出 → {path}", 5000)
        else:
            QMessageBox.warning(self, "导出失败", "\n".join(errs))

    def _on_import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入诊断配置", "", "JSON文件 (*.json);;所有文件 (*)")
        if not path:
            return
        self._start_json_import(path)

    def _on_json_imported(self, result: tuple):
        ok, msgs = result
        if ok:
            self._refresh_all()
            self.status_bar.showMessage(msgs[0] if msgs else "导入完成", 5000)
        else:
            QMessageBox.warning(self, "导入失败", "\n".join(msgs))

    def _on_import_odx(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入ODX/CDD文件", "", "ODX/CDD (*.odx *.odx-d *.odx-c *.cdd);;所有文件 (*)"
        )
        if not path:
            return
        self._start_odx_import(path)

    def _start_odx_import(self, path: str):
        self.status_bar.showMessage("正在导入ODX文件...")
        self._odx_worker = FileWorker(self.controller.import_odx, Path(path))
        self._odx_worker.finished_ok.connect(self._on_odx_imported)
        self._odx_worker.finished_err.connect(lambda err: QMessageBox.warning(self, "导入失败", err))
        self._odx_worker.start()

    def load_file(self, path: str):
        """Programmatically load a diagnostic file (used by drag-drop)."""
        ext = Path(path).suffix.lower()
        if ext in (".odx", ".odx-d", ".odx-c", ".cdd"):
            self._start_odx_import(path)
        elif ext == ".json":
            self._start_json_import(path)

    def _start_json_import(self, path: str):
        self.status_bar.showMessage("正在导入诊断配置...")
        self._json_worker = FileWorker(self.controller.import_json, Path(path))
        self._json_worker.finished_ok.connect(self._on_json_imported)
        self._json_worker.finished_err.connect(lambda err: QMessageBox.warning(self, "导入失败", err))
        self._json_worker.start()

    def _on_odx_imported(self, result: tuple):
        ok, msgs = result
        if ok:
            self._refresh_all()
            self.status_bar.showMessage(msgs[0] if msgs else "ODX导入完成", 5000)
        else:
            QMessageBox.warning(self, "导入失败", "\n".join(msgs))

    # ── Validation ─────────────────────────────────────────────────────────

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
        self.tabs.setCurrentIndex(3)  # Switch to validation tab
        self.status_bar.showMessage(f"校验完成: {len(issues)} 问题", 5000)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _refresh_all(self):
        self._refresh_dtc_tree()
        self._refresh_dtc_table()
        self._refresh_service_table()
        self._refresh_snapshots()
        self._update_info_label()

    def _refresh_dtc_tree(self):
        self.dtc_tree.clear()
        categories = self.controller.get_dtc_categories()
        for sev, dtcs in sorted(categories.items()):
            parent = self.dtc_tree.add_top_level_item(f"{sev} ({len(dtcs)})")
            for dtc in sorted(dtcs, key=lambda d: d.dtc_code):
                self.dtc_tree.add_child_item(parent, dtc.dtc_code)
        self.dtc_tree.tree.expandAll()

    def _refresh_dtc_table(self):
        dtcs = self.controller.get_dtcs()
        rows = []
        id_map = {}
        for i, dtc in enumerate(dtcs):
            rows.append(
                {
                    "dtc_code": dtc.dtc_code,
                    "description": dtc.description,
                    "severity": dtc.severity or "",
                    "debounce_strategy": dtc.debounce_strategy or "",
                    "obd_related": dtc.obd_related,
                    "snapshots": dtc.get_snapshot_ids(),
                }
            )
            id_map[i] = dtc.id
        self.dtc_model.load_data(rows, id_map)

    def _refresh_service_table(self):
        svcs = self.controller.get_services()
        rows = []
        id_map = {}
        for i, svc in enumerate(svcs):
            rows.append(
                {
                    "sid": svc.sid,
                    "service_name": svc.service_name,
                    "security_level": svc.security_level,
                    "sub_functions": svc.get_sub_functions(),
                    "description": svc.description or "",
                    "enabled": svc.enabled,
                }
            )
            id_map[i] = svc.id
        self.svc_model.load_data(rows, id_map)

    def _refresh_snapshots(self):
        configs = self.controller.get_snapshot_configs()
        if not configs:
            self.snap_info.setPlainText("暂无快照配置。\n\n在DTC编辑中添加Snapshot DID即可配置快照数据。")
            return
        lines = ["快照数据配置 (Snapshot DIDs)\n"]
        lines.append(f"共 {len(configs)} 个DID被引用:\n")
        for cfg in configs:
            lines.append(f"  DID: {cfg['did']}")
            lines.append(f"    关联DTC ({cfg['dtc_count']}): {', '.join(cfg['dtcs'])}")
            lines.append("")
        self.snap_info.setPlainText("\n".join(lines))

    def _update_info_label(self):
        dtcs = self.controller.get_dtcs()
        svcs = self.controller.get_services()
        snaps = self.controller.get_snapshot_configs()
        self.info_label.setText(f"DTC: {len(dtcs)}  |  UDS服务: {len(svcs)}  |  快照DID: {len(snaps)}")

    def filter(self, query: str) -> int:
        """Filter DTC and service tables by query. Returns match count."""
        query_lower = query.lower()
        visible = 0
        # Filter DTC table
        for row in range(self.dtc_model.rowCount()):
            row_data = self.dtc_model.get_row(row)
            text = f"{row_data.get('dtc_code', '')} {row_data.get('description', '')}"
            match = not query or query_lower in text.lower()
            self.dtc_table.setRowHidden(row, not match)
            if match:
                visible += 1
        # Filter service table
        for row in range(self.svc_model.rowCount()):
            row_data = self.svc_model.get_row(row)
            text = f"{row_data.get('sid', '')} {row_data.get('service_name', '')} {row_data.get('description', '')}"
            match = not query or query_lower in text.lower()
            self.svc_table.setRowHidden(row, not match)
            if match:
                visible += 1
        # Filter DTC tree
        tree = self.dtc_tree.tree
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
