"""Test Generator main view — DBC-based test case generation and management."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
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

from modules.test_generator.controller import (
    TestCase,
    TestGeneratorController,
    TestMethod,
)
from modules.test_generator.views.e2e_config_dialog import E2EConfigDialog
from ui.icons import icon_clear, icon_export_excel, icon_export_json, icon_generate, icon_open
from ui.widgets.file_worker import FileWorker
from ui.widgets.table_editor import DataTableModel
from ui.widgets.tree_view import TreeView

# ── Main view ────────────────────────────────────────────────────────────────


class TestGeneratorView(QWidget):
    """Test Generator module main view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = TestGeneratorController()
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ──
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.act_load_dbc = QAction(icon_open(), "加载DBC", self)
        self.act_generate = QAction(icon_generate(), "生成测试用例", self)
        self.act_export_json = QAction(icon_export_json(), "导出JSON", self)
        self.act_export_excel = QAction(icon_export_excel(), "导出Excel", self)
        self.act_clear = QAction(icon_clear(), "清空用例", self)

        toolbar.addAction(self.act_load_dbc)
        toolbar.addSeparator()
        toolbar.addAction(self.act_generate)
        toolbar.addSeparator()
        toolbar.addAction(self.act_export_json)
        toolbar.addAction(self.act_export_excel)
        toolbar.addAction(self.act_clear)

        layout.addWidget(toolbar)

        # ── Info bar ──
        self.info_label = QLabel("测试用例生成器 — 加载DBC后自动生成测试用例")
        self.info_label.setStyleSheet(
            "background-color: #f8f9fa; border-left: 3px solid #1a73e8; "
            "padding: 6px 12px; font-size: 12px; color: #333;"
        )
        layout.addWidget(self.info_label)

        # ── Main content ──
        splitter = QSplitter(Qt.Horizontal)

        # Left: category tree + generation options
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # Generation options
        options_group = QGroupBox("测试方法")
        opt_layout = QVBoxLayout(options_group)
        self.chk_boundary = QCheckBox("边界值测试 (Boundary Value)")
        self.chk_boundary.setChecked(True)
        self.chk_normal = QCheckBox("正常范围测试 (Normal Range)")
        self.chk_normal.setChecked(True)
        self.chk_error = QCheckBox("错误注入测试 (Error Injection)")
        self.chk_timeout = QCheckBox("信号超时测试 (Signal Timeout)")
        self.chk_e2e = QCheckBox("E2E保护测试 (E2E Protection)")
        self.chk_counter = QCheckBox("计数器测试 (Counter Validation)")
        opt_layout.addWidget(self.chk_boundary)
        opt_layout.addWidget(self.chk_normal)
        opt_layout.addWidget(self.chk_error)
        opt_layout.addWidget(self.chk_timeout)
        opt_layout.addWidget(self.chk_e2e)
        opt_layout.addWidget(self.chk_counter)
        left_layout.addWidget(options_group)

        # Category tree
        self.category_tree = TreeView()
        self.category_tree.setMinimumWidth(180)
        left_layout.addWidget(self.category_tree, stretch=1)

        splitter.addWidget(left_widget)

        # Right: tabs
        self.tabs = QTabWidget()

        # Test case table tab
        tc_widget = QWidget()
        tc_layout = QVBoxLayout(tc_widget)
        self.tc_model = DataTableModel(
            headers=["用例ID", "名称", "分类", "方法", "关联信号", "关联报文", "优先级", "状态"],
            keys=["id", "name", "category", "method", "signal_name", "message_name", "priority", "status"],
        )
        self.tc_table = QTableView()
        self.tc_table.setModel(self.tc_model)
        self.tc_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tc_table.setAlternatingRowColors(True)
        self.tc_table.horizontalHeader().setStretchLastSection(True)
        self.tc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tc_table.verticalHeader().setVisible(False)
        self.tc_table.doubleClicked.connect(self._on_tc_double_click)
        tc_layout.addWidget(self.tc_table)

        tc_btn_layout = QHBoxLayout()
        btn_view = QPushButton("查看详情")
        btn_view.setProperty("class", "primary")
        btn_pass = QPushButton("标记通过")
        btn_fail = QPushButton("标记失败")
        btn_del = QPushButton("删除")
        btn_del.setProperty("class", "danger")
        btn_view.clicked.connect(self._on_view_tc)
        btn_pass.clicked.connect(lambda: self._update_status("passed"))
        btn_fail.clicked.connect(lambda: self._update_status("failed"))
        btn_del.clicked.connect(self._on_remove_tc)
        tc_btn_layout.addWidget(btn_view)
        tc_btn_layout.addWidget(btn_pass)
        tc_btn_layout.addWidget(btn_fail)
        tc_btn_layout.addWidget(btn_del)
        tc_btn_layout.addStretch()
        tc_layout.addLayout(tc_btn_layout)
        self.tabs.addTab(tc_widget, "测试用例")

        # Coverage tab
        cov_widget = QWidget()
        cov_layout = QVBoxLayout(cov_widget)
        self.coverage_bar = QProgressBar()
        self.coverage_bar.setRange(0, 100)
        self.coverage_bar.setFormat("信号覆盖率: %p%")
        cov_layout.addWidget(self.coverage_bar)
        self.coverage_label = QLabel("")
        cov_layout.addWidget(self.coverage_label)
        self.coverage_detail = QTextEdit()
        self.coverage_detail.setReadOnly(True)
        cov_layout.addWidget(self.coverage_detail, stretch=1)
        self.tabs.addTab(cov_widget, "覆盖率")

        # Detail tab
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        detail_layout.addWidget(self.detail_view)
        self.tabs.addTab(detail_widget, "用例详情")

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
        self.act_load_dbc.triggered.connect(self._on_load_dbc)
        self.act_generate.triggered.connect(self._on_generate)
        self.act_export_json.triggered.connect(self._on_export_json)
        self.act_export_excel.triggered.connect(self._on_export_excel)
        self.act_clear.triggered.connect(self._on_clear)
        self.category_tree.item_selected.connect(self._on_category_selected)

    # ── Slots ───────────────────────────────────────────────────────────────

    def _on_load_dbc(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开DBC文件", "", "DBC文件 (*.dbc);;所有文件 (*)")
        if not path:
            return
        self.status_bar.showMessage("正在加载DBC文件...")
        self._pending_dbc_path = path
        self._worker = FileWorker(self.controller.load_dbc, Path(path))
        self._worker.finished_ok.connect(self._on_dbc_loaded)
        self._worker.finished_err.connect(lambda err: QMessageBox.critical(self, "加载失败", err))
        self._worker.start()

    def _on_dbc_loaded(self, result: tuple):
        ok, errs = result
        if not ok:
            QMessageBox.critical(self, "加载失败", "\n".join(errs))
            return
        path = self._pending_dbc_path
        msgs = self.controller.current_dbc.messages if self.controller.current_dbc else []
        sig_count = sum(len(m.signals) for m in msgs)
        self.info_label.setText(f"已加载: {Path(path).name}  |  报文: {len(msgs)}  |  信号: {sig_count}")
        self.status_bar.showMessage(f"已加载 {path}", 5000)

    def _on_generate(self):
        signal_methods = []
        if self.chk_boundary.isChecked():
            signal_methods.append(TestMethod.BOUNDARY_VALUE)
        if self.chk_normal.isChecked():
            signal_methods.append(TestMethod.NORMAL_RANGE)
        if self.chk_error.isChecked():
            signal_methods.append(TestMethod.ERROR_INJECTION)
        if self.chk_timeout.isChecked():
            signal_methods.append(TestMethod.SIGNAL_TIMEOUT)

        want_e2e = self.chk_e2e.isChecked()
        want_counter = self.chk_counter.isChecked()

        if not signal_methods and not want_e2e and not want_counter:
            QMessageBox.information(self, "提示", "请至少选择一种测试方法")
            return

        count = 0
        if signal_methods:
            count += self.controller.generate_signal_tests(signal_methods)

        if want_e2e or want_counter:
            if not self.controller.current_dbc:
                QMessageBox.information(self, "提示", "请先加载 DBC 文件")
                return
            # Auto-detect E2E configs from DBC
            configs = self.controller.auto_detect_e2e()
            if not configs:
                # No E2E signals detected, create configs with both enabled
                from modules.test_generator.controller import E2EConfig

                configs = [
                    E2EConfig(message_name=m.name, message_id=m.id, e2e_enabled=want_e2e, counter_enabled=want_counter)
                    for m in self.controller.current_dbc.messages
                ]
            else:
                for cfg in configs:
                    cfg.e2e_enabled = want_e2e
                    cfg.counter_enabled = want_counter

            # Build signal lookup for dialog
            signals_by_msg: dict[str, list[str]] = {}
            for m in self.controller.current_dbc.messages:
                signals_by_msg[m.name] = [s.name for s in m.signals]

            # Show config dialog
            dlg = E2EConfigDialog(configs, signals_by_msg, self)
            if dlg.exec() != E2EConfigDialog.Accepted:
                return

            configs = dlg.get_configs()
            count += self.controller.generate_message_tests(configs=configs)

        self._refresh_all()
        self.status_bar.showMessage(f"已生成 {count} 个测试用例", 5000)

    def _on_export_json(self):
        if not self.controller.get_test_cases():
            QMessageBox.information(self, "提示", "暂无测试用例")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出测试用例", "", "JSON文件 (*.json);;所有文件 (*)")
        if not path:
            return
        ok, errs = self.controller.export_json(Path(path))
        if ok:
            self.status_bar.showMessage(f"已导出 → {path}", 5000)
        else:
            QMessageBox.warning(self, "导出失败", "\n".join(errs))

    def _on_export_excel(self):
        if not self.controller.get_test_cases():
            QMessageBox.information(self, "提示", "暂无测试用例")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出测试用例", "", "Excel文件 (*.xlsx);;所有文件 (*)")
        if not path:
            return
        ok, errs = self.controller.export_excel(Path(path))
        if ok:
            self.status_bar.showMessage(f"已导出 → {path}", 5000)
        else:
            QMessageBox.warning(self, "导出失败", "\n".join(errs))

    def _on_clear(self):
        if not self.controller.get_test_cases():
            return
        reply = QMessageBox.question(self, "确认", "清空所有测试用例？")
        if reply == QMessageBox.Yes:
            self.controller.clear_cases()
            self._refresh_all()
            self.status_bar.showMessage("已清空", 3000)

    def _on_tc_double_click(self, index: QModelIndex):
        row_data = self.tc_model.get_row(index.row())
        self._show_tc_detail(row_data.get("id", ""))

    def _on_view_tc(self):
        selected = self.tc_table.selectionModel().selectedRows()
        if not selected:
            return
        row_data = self.tc_model.get_row(selected[0].row())
        self._show_tc_detail(row_data.get("id", ""))

    def _on_remove_tc(self):
        selected = self.tc_table.selectionModel().selectedRows()
        if not selected:
            return
        tc_id = self.tc_model.get_row(selected[0].row()).get("id", "")
        self.controller.remove_test_case(tc_id)
        self._refresh_all()
        self.status_bar.showMessage(f"已删除 {tc_id}", 3000)

    def _update_status(self, status: str):
        selected = self.tc_table.selectionModel().selectedRows()
        if not selected:
            return
        tc_id = self.tc_model.get_row(selected[0].row()).get("id", "")
        self.controller.update_status(tc_id, status)
        self._refresh_all()
        self.status_bar.showMessage(f"{tc_id} → {status}", 3000)

    def _on_category_selected(self, name: str):
        """Filter test cases by category."""
        cats = self.controller.get_cases_by_category()
        if name not in cats:
            # Try to match partial (tree shows "name (count)")
            for cat_name in cats:
                if name.startswith(cat_name):
                    name = cat_name
                    break
            else:
                return
        cases = cats.get(name, [])
        self._load_cases_into_table(cases)

    def _show_tc_detail(self, tc_id: str):
        for tc in self.controller.get_test_cases():
            if tc.id == tc_id:
                lines = [
                    f"用例ID: {tc.id}",
                    f"名称: {tc.name}",
                    f"分类: {tc.category}",
                    f"方法: {tc.method}",
                    f"优先级: {tc.priority}",
                    f"状态: {tc.status}",
                    f"关联信号: {tc.signal_name}",
                    f"关联报文: {tc.message_name}",
                    f"输入值: {tc.input_value}",
                    "",
                    "描述:",
                    tc.description,
                    "",
                    "测试步骤:",
                ]
                for i, step in enumerate(tc.steps, 1):
                    lines.append(f"  {i}. {step}")
                lines.append("")
                lines.append("预期结果:")
                for i, result in enumerate(tc.expected_results, 1):
                    lines.append(f"  {i}. {result}")
                self.detail_view.setPlainText("\n".join(lines))
                self.tabs.setCurrentIndex(2)
                return

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _refresh_all(self):
        self._refresh_category_tree()
        self._refresh_table()
        self._refresh_coverage()
        self._update_info_label()

    def _refresh_category_tree(self):
        self.category_tree.clear()
        cats = self.controller.get_cases_by_category()
        for cat_name, cases in sorted(cats.items()):
            self.category_tree.add_top_level_item(f"{cat_name} ({len(cases)})")
        self.category_tree.tree.expandAll()

    def _refresh_table(self):
        self._load_cases_into_table(self.controller.get_test_cases())

    def _load_cases_into_table(self, cases: list[TestCase]):
        rows = []
        for tc in cases:
            rows.append(
                {
                    "id": tc.id,
                    "name": tc.name,
                    "category": tc.category,
                    "method": tc.method,
                    "signal_name": tc.signal_name,
                    "message_name": tc.message_name,
                    "priority": tc.priority,
                    "status": tc.status,
                }
            )
        self.tc_model.load_data(rows)

    def _refresh_coverage(self):
        cov = self.controller.get_coverage()
        pct = int(cov["coverage"])
        self.coverage_bar.setValue(pct)
        self.coverage_label.setText(
            f"信号: {cov['covered']}/{cov['total_signals']} 已覆盖  |  测试用例: {cov['total_cases']}"
        )
        # Show uncovered signals
        if self.controller.current_dbc:
            covered = set()
            for tc in self.controller.get_test_cases():
                if tc.signal_name:
                    covered.add(tc.signal_name)
            uncovered = []
            for msg in self.controller.current_dbc.messages:
                for sig in msg.signals:
                    if sig.name not in covered:
                        uncovered.append(f"{msg.name}.{sig.name}")
            if uncovered:
                self.coverage_detail.setPlainText(f"未覆盖信号 ({len(uncovered)}):\n\n" + "\n".join(uncovered[:100]))
            else:
                self.coverage_detail.setPlainText("所有信号已覆盖！")

    def _update_info_label(self):
        cases = self.controller.get_test_cases()
        cov = self.controller.get_coverage()
        self.info_label.setText(f"测试用例: {len(cases)}  |  信号覆盖率: {cov['coverage']:.1f}%")
