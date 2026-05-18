"""Traceability Matrix main view — requirement tree + matrix + statistics."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QFileDialog, QLabel, QToolBar, QMessageBox,
    QTabWidget, QHeaderView, QAbstractItemView,
    QTableView, QStatusBar, QTextEdit, QProgressBar,
)
from PySide6.QtCore import Qt, Signal, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QAction, QColor

from modules.trace_matrix.controller import TraceMatrixController
from modules.trace_matrix.widgets.link_dialog import LinkDialog, RequirementDialog
from ui.widgets.tree_view import TreeView
from ui.widgets.file_worker import FileWorker
from ui.icons import icon_open, icon_save, icon_validate, icon_export_json, icon_export_excel, icon_add, icon_generate


# ── Table models ─────────────────────────────────────────────────────────────


class RequirementTableModel(QAbstractTableModel):
    """Table model for requirements."""

    HEADERS = ["需求ID", "标题", "模块", "来源", "链接数", "已验证"]
    KEYS = ["req_id", "title", "module_name", "source", "link_count", "verified_count"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []
        self._id_map: dict[int, int] = {}

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.BackgroundRole:
            row = self._rows[index.row()]
            if row.get("link_count", 0) == 0:
                return QColor("#FFEEF0")
            return QColor("#E6FFED")
        if role not in (Qt.DisplayRole, Qt.EditRole):
            return None
        row = self._rows[index.row()]
        key = self.KEYS[index.column()]
        return str(row.get(key, ""))

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


class MatrixTableModel(QAbstractTableModel):
    """Table model for traceability matrix view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers: list[str] = []
        self._rows: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.BackgroundRole:
            val = self._rows[index.row()].get(self._headers[index.column()], "")
            if val and val not in ("", "0"):
                return QColor("#C8E6C9")
            return None
        if role == Qt.DisplayRole:
            key = self._headers[index.column()]
            return str(self._rows[index.row()].get(key, ""))
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._headers[section]
            return str(section + 1)
        return None

    def load_matrix(self, matrix: dict):
        """Load traceability matrix data."""
        self.beginResetModel()
        # Collect all artifact types
        all_types: set[str] = set()
        for info in matrix.values():
            all_types.update(info["links"].keys())
        sorted_types = sorted(all_types)

        self._headers = ["需求ID", "标题"] + sorted_types + ["总计"]

        self._rows = []
        for req_id, info in sorted(matrix.items()):
            row = {"需求ID": req_id, "标题": info["title"]}
            total = 0
            for t in sorted_types:
                targets = info["links"].get(t, [])
                row[t] = ", ".join(targets) if targets else ""
                total += len(targets)
            row["总计"] = str(total)
            self._rows.append(row)
        self.endResetModel()


# ── Main view ────────────────────────────────────────────────────────────────


class TraceMatrixView(QWidget):
    """Traceability Matrix module main view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = TraceMatrixController()
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
        self.act_add_req = QAction(icon_add(), "新建需求", self)
        self.act_import_req = QAction(icon_open(), "导入需求", self)
        self.act_add_link = QAction(icon_add(), "添加链接", self)
        self.act_auto_match = QAction(icon_generate(), "自动匹配", self)
        self.act_export_json = QAction(icon_export_json(), "导出JSON", self)
        self.act_export_excel = QAction(icon_export_excel(), "导出Excel", self)

        toolbar.addAction(self.act_add_req)
        toolbar.addAction(self.act_import_req)
        toolbar.addSeparator()
        toolbar.addAction(self.act_add_link)
        toolbar.addAction(self.act_auto_match)
        toolbar.addSeparator()
        toolbar.addAction(self.act_export_json)
        toolbar.addAction(self.act_export_excel)

        layout.addWidget(toolbar)

        # ── Info bar with coverage ──
        info_layout = QHBoxLayout()
        self.info_label = QLabel("追溯矩阵")
        self.info_label.setStyleSheet(
            "background-color: #f8f9fa; border-left: 3px solid #1a73e8; "
            "padding: 6px 12px; font-size: 12px; color: #333;"
        )
        info_layout.addWidget(self.info_label, stretch=1)
        self.coverage_bar = QProgressBar()
        self.coverage_bar.setRange(0, 100)
        self.coverage_bar.setFixedWidth(200)
        self.coverage_bar.setFormat("覆盖率: %p%")
        info_layout.addWidget(self.coverage_bar)
        layout.addLayout(info_layout)

        # ── Main content ──
        splitter = QSplitter(Qt.Horizontal)

        # Left: module tree
        self.module_tree = TreeView()
        self.module_tree.setMinimumWidth(200)
        splitter.addWidget(self.module_tree)

        # Right: tabs
        self.tabs = QTabWidget()

        # Requirements table
        req_widget = QWidget()
        req_layout = QVBoxLayout(req_widget)
        self.req_model = RequirementTableModel()
        self.req_table = QTableView()
        self.req_table.setModel(self.req_model)
        self.req_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.req_table.setAlternatingRowColors(True)
        self.req_table.horizontalHeader().setStretchLastSection(True)
        self.req_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.req_table.verticalHeader().setVisible(False)
        self.req_table.doubleClicked.connect(self._on_req_double_click)
        req_layout.addWidget(self.req_table)

        req_btn_layout = QHBoxLayout()
        btn_edit = QPushButton("编辑需求")
        btn_del = QPushButton("删除需求")
        btn_links = QPushButton("管理链接")
        btn_edit.clicked.connect(self._on_edit_req)
        btn_del.clicked.connect(self._on_remove_req)
        btn_links.clicked.connect(self._on_manage_links)
        req_btn_layout.addWidget(btn_edit)
        req_btn_layout.addWidget(btn_del)
        req_btn_layout.addWidget(btn_links)
        req_btn_layout.addStretch()
        req_layout.addLayout(req_btn_layout)
        self.tabs.addTab(req_widget, "需求列表")

        # Matrix view
        matrix_widget = QWidget()
        matrix_layout = QVBoxLayout(matrix_widget)
        self.matrix_model = MatrixTableModel()
        self.matrix_table = QTableView()
        self.matrix_table.setModel(self.matrix_model)
        self.matrix_table.setAlternatingRowColors(True)
        self.matrix_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.matrix_table.verticalHeader().setVisible(True)
        matrix_layout.addWidget(self.matrix_table)
        self.tabs.addTab(matrix_widget, "追溯矩阵")

        # Statistics
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        self.stats_view = QTextEdit()
        self.stats_view.setReadOnly(True)
        stats_layout.addWidget(self.stats_view)
        self.tabs.addTab(stats_widget, "统计")

        # Gaps
        gaps_widget = QWidget()
        gaps_layout = QVBoxLayout(gaps_widget)
        self.gaps_view = QTextEdit()
        self.gaps_view.setReadOnly(True)
        gaps_layout.addWidget(self.gaps_view)
        self.tabs.addTab(gaps_widget, "追溯缺口")

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
        self.act_add_req.triggered.connect(self._on_add_req)
        self.act_import_req.triggered.connect(self._on_import_req)
        self.act_add_link.triggered.connect(self._on_add_link)
        self.act_auto_match.triggered.connect(self._on_auto_match)
        self.act_export_json.triggered.connect(self._on_export_json)
        self.act_export_excel.triggered.connect(self._on_export_excel)
        self.module_tree.item_selected.connect(self._on_module_selected)

    # ── Requirement operations ──────────────────────────────────────────────

    def _on_add_req(self):
        dialog = RequirementDialog(parent=self)
        if dialog.exec() != RequirementDialog.Accepted:
            return
        data = dialog.get_data()
        result = self.controller.add_requirement(**data)
        if result is None:
            QMessageBox.warning(self, "错误", "需求ID已存在")
            return
        self._refresh_all()
        self.status_bar.showMessage(f"已添加: {data['req_id']}", 3000)

    def _on_edit_req(self):
        selected = self.req_table.selectionModel().selectedRows()
        if not selected:
            return
        db_id = self.req_model.get_db_id(selected[0].row())
        if db_id is None:
            return
        req_data = self.controller.get_requirement_as_dict(db_id)
        if req_data is None:
            return
        dialog = RequirementDialog(req_data=req_data, parent=self)
        if dialog.exec() != RequirementDialog.Accepted:
            return
        data = dialog.get_data()
        self.controller.update_requirement(db_id, **data)
        self._refresh_all()
        self.status_bar.showMessage(f"已更新: {data['req_id']}", 3000)

    def _on_remove_req(self):
        selected = self.req_table.selectionModel().selectedRows()
        if not selected:
            return
        db_id = self.req_model.get_db_id(selected[0].row())
        if db_id is None:
            return
        self.controller.remove_requirement(db_id)
        self._refresh_all()
        self.status_bar.showMessage("已删除需求及其链接", 3000)

    def _on_req_double_click(self, index: QModelIndex):
        self._on_edit_req()

    def _on_import_req(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入需求", "", "JSON文件 (*.json);;所有文件 (*)"
        )
        if not path:
            return
        self.status_bar.showMessage("正在导入需求...")
        self._worker = FileWorker(self._do_import_req, Path(path))
        self._worker.finished_ok.connect(self._on_req_imported)
        self._worker.finished_err.connect(lambda err: QMessageBox.critical(self, "导入失败", err))
        self._worker.start()

    def _do_import_req(self, path: Path) -> str:
        data = json.loads(path.read_text(encoding="utf-8"))
        req_list = data.get("requirements", data if isinstance(data, list) else [])
        imported, skipped = self.controller.import_requirements(req_list)
        links_imported = 0
        for req_data in req_list:
            req_id = req_data.get("req_id", "")
            for link in req_data.get("links", []):
                if self.controller.add_link(
                    req_id, link.get("type", ""), link.get("target", ""),
                    link.get("target_id", ""), auto=link.get("auto_matched", False),
                ):
                    links_imported += 1
        return f"导入: {imported} 需求, {links_imported} 链接, {skipped} 跳过"

    def _on_req_imported(self, msg: str):
        self._refresh_all()
        self.status_bar.showMessage(msg, 5000)

    # ── Link operations ─────────────────────────────────────────────────────

    def _on_add_link(self):
        selected = self.req_table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择一个需求")
            return
        row_data = self.req_model.get_row(selected[0].row())
        req_id = row_data.get("req_id", "")
        if not req_id:
            return

        # Gather available artifacts (placeholder — in real use, query from other modules)
        artifacts = {
            "swc": self._get_artifact_list("swc"),
            "signal": self._get_artifact_list("signal"),
            "dtc": self._get_artifact_list("dtc"),
            "test_case": self._get_artifact_list("test_case"),
            "port": self._get_artifact_list("port"),
            "runnable": self._get_artifact_list("runnable"),
        }

        dialog = LinkDialog(req_id, artifacts, parent=self)
        if dialog.exec() != LinkDialog.Accepted:
            return
        link_type = dialog.get_link_type()
        target = dialog.get_target()
        if self.controller.add_link(req_id, link_type, target):
            self._refresh_all()
            self.status_bar.showMessage(f"已添加链接: {req_id} → {target}", 3000)
        else:
            QMessageBox.warning(self, "错误", "链接已存在或添加失败")

    def _on_manage_links(self):
        selected = self.req_table.selectionModel().selectedRows()
        if not selected:
            return
        row_data = self.req_model.get_row(selected[0].row())
        req_id = row_data.get("req_id", "")
        if not req_id:
            return
        links = self.controller.get_links_for_req(req_id)
        if not links:
            QMessageBox.information(self, "链接管理", f"需求 {req_id} 暂无链接。\n点击「添加链接」创建新链接。")
            return
        lines = [f"需求 {req_id} 的链接 ({len(links)}):\n"]
        for l in links:
            v = "✓" if l["verified"] else "○"
            a = "[自动]" if l["auto_matched"] else "[手动]"
            lines.append(f"  {v} [{l['type']}] → {l['target']} {a}")
        lines.append("\n点击「添加链接」创建新链接。")
        QMessageBox.information(self, "链接管理", "\n".join(lines))

    def _on_auto_match(self):
        artifacts = {
            "swc": self._get_artifact_list("swc"),
            "signal": self._get_artifact_list("signal"),
            "dtc": self._get_artifact_list("dtc"),
            "test_case": self._get_artifact_list("test_case"),
        }
        count = self.controller.auto_match_by_naming(artifacts)
        self._refresh_all()
        self.status_bar.showMessage(f"自动匹配完成: 新建 {count} 条链接", 5000)

    def _on_module_selected(self, name: str):
        """Filter requirements by module."""
        reqs = self.controller.get_requirements()
        filtered = [r for r in reqs if (r.module_name or "通用") == name]
        self._load_reqs_into_table(filtered)

    # ── Export ──────────────────────────────────────────────────────────────

    def _on_export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出追溯矩阵", "", "JSON文件 (*.json);;所有文件 (*)"
        )
        if not path:
            return
        ok, errs = self.controller.export_json(Path(path))
        if ok:
            self.status_bar.showMessage(f"已导出 → {path}", 5000)
        else:
            QMessageBox.warning(self, "导出失败", "\n".join(errs))

    def _on_export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出追溯矩阵", "", "Excel文件 (*.xlsx);;所有文件 (*)"
        )
        if not path:
            return
        ok, errs = self.controller.export_excel(Path(path))
        if ok:
            self.status_bar.showMessage(f"已导出 → {path}", 5000)
        else:
            QMessageBox.warning(self, "导出失败", "\n".join(errs))

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _get_artifact_list(self, artifact_type: str) -> list[str]:
        """Get available artifacts of a given type. Placeholder implementation."""
        # In production, this would query the other module controllers
        # For now, return what's in the existing links
        matrix = self.controller.get_matrix()
        targets = set()
        for info in matrix.values():
            for t in info["links"].get(artifact_type, []):
                targets.add(t)
        return sorted(targets)

    def _refresh_all(self):
        self._refresh_module_tree()
        self._refresh_req_table()
        self._refresh_matrix()
        self._refresh_stats()
        self._refresh_gaps()
        self._update_info_label()

    def _refresh_module_tree(self):
        self.module_tree.clear()
        reqs = self.controller.get_requirements()
        modules: dict[str, list] = {}
        for r in reqs:
            modules.setdefault(r.module_name or "通用", []).append(r)
        for mod, mod_reqs in sorted(modules.items()):
            parent = self.module_tree.add_top_level_item(f"{mod} ({len(mod_reqs)})")
            for r in mod_reqs:
                self.module_tree.add_child_item(parent, r.req_id)
        self.module_tree.tree.expandAll()

    def _refresh_req_table(self):
        reqs = self.controller.get_requirements()
        self._load_reqs_into_table(reqs)

    def _load_reqs_into_table(self, reqs: list):
        matrix = self.controller.get_matrix()
        rows = []
        id_map = {}
        for i, r in enumerate(reqs):
            info = matrix.get(r.req_id, {"link_count": 0, "verified_count": 0})
            rows.append({
                "req_id": r.req_id,
                "title": r.title,
                "module_name": r.module_name or "",
                "source": r.source,
                "link_count": info["link_count"],
                "verified_count": info["verified_count"],
            })
            id_map[i] = r.id
        self.req_model.load_data(rows, id_map)

    def _refresh_matrix(self):
        matrix = self.controller.get_matrix()
        self.matrix_model.load_matrix(matrix)

    def _refresh_stats(self):
        stats = self.controller.get_statistics()
        lines = [
            "追溯统计",
            "=" * 40,
            "",
            f"总需求数:     {stats['total_requirements']}",
            f"已追溯需求:   {stats['linked_requirements']}",
            f"未追溯需求:   {stats['unlinked_requirements']}",
            f"追溯覆盖率:   {stats['coverage_pct']:.1f}%",
            "",
            f"总链接数:     {stats['total_links']}",
            f"自动匹配:     {stats['auto_links']}",
            f"手动添加:     {stats['manual_links']}",
            f"已验证:       {stats['verified_links']}",
            "",
            "按类型分布:",
        ]
        for ltype, count in sorted(stats["links_by_type"].items()):
            lines.append(f"  {ltype}: {count}")
        self.stats_view.setPlainText("\n".join(lines))
        self.coverage_bar.setValue(int(stats["coverage_pct"]))

    def _refresh_gaps(self):
        gaps = self.controller.get_gaps()
        if not gaps:
            self.gaps_view.setPlainText("无追溯缺口 — 所有需求均已完整链接。")
            return
        lines = [f"追溯缺口 ({len(gaps)} 条需求)\n"]
        for gap in gaps:
            lines.append(f"  {gap['req_id']}: {gap['title']}")
            lines.append(f"    缺失: {', '.join(gap['missing'])}")
            if gap["existing_types"]:
                lines.append(f"    已有: {', '.join(gap['existing_types'])}")
            lines.append("")
        self.gaps_view.setPlainText("\n".join(lines))

    def _update_info_label(self):
        stats = self.controller.get_statistics()
        self.info_label.setText(
            f"需求: {stats['total_requirements']}  |  "
            f"已追溯: {stats['linked_requirements']}  |  "
            f"链接: {stats['total_links']}  |  "
            f"覆盖率: {stats['coverage_pct']:.1f}%"
        )


# Need json import at module level
import json
