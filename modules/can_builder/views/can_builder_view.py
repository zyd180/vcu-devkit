"""CAN Builder main view — message tree + signal table + property panel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QFileDialog, QLabel, QToolBar, QMessageBox,
    QCheckBox, QGroupBox, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QHeaderView, QAbstractItemView,
    QTableView, QStatusBar,
)
from PySide6.QtCore import Qt, Signal, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QFont, QAction

from modules.can_builder.controller import CANBuilderController
from ui.widgets.tree_view import TreeView
from ui.widgets.table_editor import DataTableModel
from ui.widgets.property_panel import PropertyPanel
from ui.widgets.file_worker import FileWorker
from ui.icons import icon_open, icon_save, icon_diff, icon_validate, icon_generate, icon_add


class SignalTableModel(DataTableModel):
    """Table model for CAN signals."""

    HEADERS = [
        "信号名", "起始位", "位长", "字节序", "值类型",
        "Factor", "Offset", "最小值", "最大值", "单位", "接收方",
    ]
    KEYS = [
        "name", "start_bit", "bit_length", "byte_order", "value_type",
        "factor", "offset", "minimum", "maximum", "unit", "receivers",
    ]

    def __init__(self, parent=None):
        super().__init__(self.HEADERS, self.KEYS, parent)


class CANBuilderView(QWidget):
    """CAN Builder module main view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = CANBuilderController()
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ──
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.act_open = QAction(icon_open(), "打开DBC", self)
        self.act_open.setShortcut("Ctrl+D")
        self.act_save = QAction(icon_save(), "保存", self)
        self.act_diff = QAction(icon_diff(), "版本Diff", self)
        self.act_validate = QAction(icon_validate(), "校验", self)
        self.act_generate = QAction(icon_generate(), "生成代码", self)
        self.act_batch_edit = QAction(icon_add(), "批量编辑", self)

        toolbar.addAction(self.act_open)
        toolbar.addAction(self.act_save)
        toolbar.addSeparator()
        toolbar.addAction(self.act_diff)
        toolbar.addAction(self.act_validate)
        toolbar.addAction(self.act_batch_edit)
        toolbar.addSeparator()
        toolbar.addAction(self.act_generate)

        layout.addWidget(toolbar)

        # ── Status info bar ──
        self.info_label = QLabel("未加载DBC文件")
        self.info_label.setStyleSheet(
            "background-color: #f8f9fa; border-left: 3px solid #1a73e8; "
            "padding: 6px 12px; font-size: 12px; color: #333;"
        )
        layout.addWidget(self.info_label)

        # ── Main content: tree | table ──
        splitter = QSplitter(Qt.Horizontal)

        # Left: message tree
        self.msg_tree = TreeView()
        self.msg_tree.setMinimumWidth(220)
        splitter.addWidget(self.msg_tree)

        # Right: signal table + property panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Signal table
        self.signal_model = SignalTableModel()
        self.signal_table = QTableView()
        self.signal_table.setModel(self.signal_model)
        self.signal_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.signal_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.signal_table.setAlternatingRowColors(True)
        self.signal_table.horizontalHeader().setStretchLastSection(True)
        self.signal_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.signal_table.verticalHeader().setVisible(False)
        self.signal_table.setSortingEnabled(True)
        right_layout.addWidget(self.signal_table, stretch=3)

        # Property panel (bottom)
        self.prop_panel = PropertyPanel()
        self.prop_panel.setMaximumHeight(220)
        right_layout.addWidget(self.prop_panel, stretch=1)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 960])

        layout.addWidget(splitter, stretch=1)

        # ── Status bar ──
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        layout.addWidget(self.status_bar)

    def _connect_signals(self):
        self.act_open.triggered.connect(self._on_open_dbc)
        self.act_save.triggered.connect(self._on_save)
        self.act_diff.triggered.connect(self._on_diff)
        self.act_validate.triggered.connect(self._on_validate)
        self.act_generate.triggered.connect(self._on_generate)
        self.act_batch_edit.triggered.connect(self._on_batch_edit)
        self.msg_tree.item_selected.connect(self._on_message_selected)
        self.signal_table.selectionModel().currentChanged.connect(self._on_signal_selected)
        self.prop_panel.property_changed.connect(self._on_property_changed)

    # ── Slots ────────────────────────────────────────────────────────────

    def _on_open_dbc(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开DBC文件", "", "DBC文件 (*.dbc);;所有文件 (*)"
        )
        if not path:
            return
        self.load_file(path)

    def load_file(self, path: str):
        """Programmatically load a DBC file (used by drag-drop)."""
        if not path:
            return
        self.status_bar.showMessage("正在加载DBC文件...")
        self._pending_dbc_path = path
        self._worker = FileWorker(self.controller.load_dbc, Path(path))
        self._worker.finished_ok.connect(self._on_dbc_loaded)
        self._worker.finished_err.connect(lambda err: QMessageBox.critical(self, "加载失败", err))
        self._worker.start()

    def _on_dbc_loaded(self, result: tuple):
        success, errors = result
        if not success:
            QMessageBox.critical(self, "加载失败", "\n".join(errors))
            return
        path = self._pending_dbc_path
        self._refresh_message_tree()
        self.info_label.setText(
            f"已加载: {Path(path).name}  |  "
            f"报文: {len(self.controller.get_messages())}  |  "
            f"信号: {sum(len(m.signals) for m in self.controller.get_messages())}"
        )
        self.status_bar.showMessage(f"已加载 {path}", 5000)

    def _on_save(self):
        if self.controller.current_dbc is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存DBC", "", "JSON快照 (*.json);;所有文件 (*)"
        )
        if path:
            success, errors = self.controller.save_dbc(Path(path))
            if success:
                self.status_bar.showMessage(f"已保存 {path}", 5000)
            else:
                QMessageBox.warning(self, "保存失败", "\n".join(errors))

    def _on_diff(self):
        if self.controller.current_dbc is None:
            QMessageBox.information(self, "提示", "请先加载DBC文件")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择要对比的DBC文件", "", "DBC文件 (*.dbc);;所有文件 (*)"
        )
        if not path:
            return
        diff = self.controller.compare_with(Path(path))
        if diff is None:
            QMessageBox.warning(self, "对比失败", "无法加载对比文件")
            return
        self._show_diff_result(diff)

    def _on_validate(self):
        results = self.controller.validate()
        if not results:
            self.status_bar.showMessage("校验通过，无问题", 5000)
            return
        errors = [r for r in results if r.severity.value == "error"]
        warnings = [r for r in results if r.severity.value == "warning"]
        msg = f"校验完成: {len(errors)} 错误, {len(warnings)} 警告\n\n"
        for r in results[:20]:
            prefix = "✗" if r.severity.value == "error" else "⚠"
            msg += f"{prefix} [{r.rule_id}] {r.location}: {r.message}\n"
        QMessageBox.information(self, "校验结果", msg)

    def _on_generate(self):
        if self.controller.current_dbc is None:
            QMessageBox.information(self, "提示", "请先加载DBC文件")
            return
        from modules.can_builder.widgets.generate_dialog import GenerateDialog
        dialog = GenerateDialog(self, current_dir=str(self.controller.current_path.parent) if self.controller.current_path else "")
        if dialog.exec() != GenerateDialog.Accepted:
            return
        config = dialog.get_config()
        output_dir = Path(config.output_dir)
        output_files: list[str] = []
        errors: list[str] = []
        # C code
        if config.generate_c_pack or config.generate_c_signals or config.generate_c_messages:
            ok, errs = self.controller.generate_code(output_dir)
            if ok:
                output_files.append("C代码")
            else:
                errors.extend(errs)
        # CAPL
        if config.generate_capl:
            from core.generators.capl_generator import CAPLGenerator
            capl_gen = CAPLGenerator()
            result = capl_gen.generate(self.controller.current_dbc, output_dir)
            if result.success:
                output_files.append("CAPL")
            else:
                errors.extend(result.errors)
        # Diff report
        if config.generate_diff_report:
            output_files.append("变更报告(需要先执行Diff)")
        if errors:
            QMessageBox.warning(self, "生成部分失败", "\n".join(errors))
        elif output_files:
            self.status_bar.showMessage(f"已生成: {', '.join(output_files)} → {config.output_dir}", 5000)

    def _on_batch_edit(self):
        """Open batch edit dialog for selected signals."""
        selected = self.signal_table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择要编辑的信号")
            return
        signal_names = []
        for idx in selected:
            name = self.signal_model.get_row(idx.row()).get("name", "")
            if name:
                signal_names.append(name)

        from modules.can_builder.widgets.batch_edit_dialog import BatchEditDialog
        dialog = BatchEditDialog(signal_names, self)
        if dialog.exec() == BatchEditDialog.Accepted:
            changes = dialog.get_changes()
            if not changes:
                return
            current_msg = self._get_current_message_name()
            if not current_msg:
                return
            count = 0
            for sig_name in signal_names:
                if self.controller.update_signal(current_msg, sig_name, **changes):
                    count += 1
            self._load_signals_into_table(current_msg)
            self.status_bar.showMessage(f"已更新 {count} 个信号", 5000)

    def _on_property_changed(self, field_name: str, value):
        """Apply single property change from property panel to the selected signal."""
        current_msg = self._get_current_message_name()
        selected = self.signal_table.selectionModel().selectedRows()
        if not current_msg or not selected:
            return
        sig_name = self.signal_model.get_row(selected[0].row()).get("name", "")
        if not sig_name:
            return
        self.controller.update_signal(current_msg, sig_name, **{field_name: value})
        self._load_signals_into_table(current_msg)
        self.status_bar.showMessage(f"已更新 {sig_name}.{field_name}", 3000)

    def _on_message_selected(self, name: str):
        """When a message is selected in the tree, load its signals into the table."""
        msg = self.controller.get_message_by_name(name)
        if msg is None:
            return
        self._load_signals_into_table(msg.name)

    def _on_signal_selected(self, current, previous):
        """When a signal row is selected, show its properties."""
        if not current.isValid():
            return
        row = current.row()
        sig_name = self.signal_model.get_row(row).get("name", "")
        # Find which message is currently selected
        current_msg = self._get_current_message_name()
        if not current_msg or not sig_name:
            return
        props = self.controller.get_signal_as_dict(current_msg, sig_name)
        if props is None:
            return
        self._show_signal_properties(current_msg, sig_name, props)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _refresh_message_tree(self):
        self.msg_tree.clear()
        if self.controller.current_dbc is None:
            return
        # Group by sender
        sender_groups: dict[str, list] = {}
        for msg in self.controller.get_messages():
            sender = msg.sender or "Unknown"
            sender_groups.setdefault(sender, []).append(msg)

        for sender, messages in sorted(sender_groups.items()):
            parent = self.msg_tree.add_top_level_item(f"{sender} ({len(messages)})")
            for msg in messages:
                label = f"0x{msg.id:03X} {msg.name} [{len(msg.signals)}]"
                self.msg_tree.add_child_item(parent, msg.name)
        self.msg_tree.tree.expandAll()

    def _load_signals_into_table(self, msg_name: str):
        signals = self.controller.get_signals_for_message(msg_name)
        rows = []
        for sig in signals:
            rows.append({
                "name": sig.name,
                "start_bit": sig.start_bit,
                "bit_length": sig.bit_length,
                "byte_order": sig.byte_order,
                "value_type": sig.value_type,
                "factor": sig.factor,
                "offset": sig.offset,
                "minimum": sig.minimum,
                "maximum": sig.maximum,
                "unit": sig.unit,
                "receivers": ", ".join(sig.receivers),
            })
        self.signal_model.load_data(rows)
        self.status_bar.showMessage(f"报文 {msg_name}: {len(signals)} 个信号")

    def _get_current_message_name(self) -> str | None:
        """Get the currently selected message name from the tree."""
        indexes = self.msg_tree.tree.selectedIndexes()
        if not indexes:
            return None
        source_idx = self.msg_tree.proxy.mapToSource(indexes[0])
        item = self.msg_tree.model.itemFromIndex(source_idx)
        if item is None:
            return None
        text = item.text()
        # Tree stores message names directly as children
        if self.controller.get_message_by_name(text):
            return text
        return None

    def _show_signal_properties(self, msg_name: str, sig_name: str, props: dict):
        """Populate property panel with signal fields."""
        self.prop_panel.set_properties(
            f"{msg_name}.{sig_name}",
            [
                {"name": "name", "label": "信号名", "type": "text", "value": props["name"]},
                {"name": "start_bit", "label": "起始位", "type": "int", "value": props["start_bit"], "min": 0, "max": 511},
                {"name": "bit_length", "label": "位长", "type": "int", "value": props["bit_length"], "min": 1, "max": 64},
                {"name": "byte_order", "label": "字节序", "type": "combo", "value": props["byte_order"],
                 "options": ["little_endian", "big_endian"]},
                {"name": "value_type", "label": "值类型", "type": "combo", "value": props["value_type"],
                 "options": ["unsigned", "signed"]},
                {"name": "factor", "label": "Factor", "type": "float", "value": props["factor"],
                 "min": -1e6, "max": 1e6, "decimals": 6},
                {"name": "offset", "label": "Offset", "type": "float", "value": props["offset"],
                 "min": -1e6, "max": 1e6, "decimals": 6},
                {"name": "minimum", "label": "最小值", "type": "float", "value": props["minimum"],
                 "min": -1e6, "max": 1e6, "decimals": 6},
                {"name": "maximum", "label": "最大值", "type": "float", "value": props["maximum"],
                 "min": -1e6, "max": 1e6, "decimals": 6},
                {"name": "unit", "label": "单位", "type": "text", "value": props["unit"]},
                {"name": "comment", "label": "备注", "type": "text", "value": props["comment"]},
                {"name": "receivers", "label": "接收方", "type": "text", "value": props["receivers"]},
            ],
        )

    def _show_diff_result(self, diff):
        """Display diff results in a dialog."""
        from ui.widgets.diff_viewer import DiffViewer
        from PySide6.QtWidgets import QDialog, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("DBC版本对比")
        dialog.resize(800, 600)
        layout = QVBoxLayout(dialog)

        viewer = DiffViewer()
        lines = []
        for md in diff.message_diffs:
            lines.append(f"--- {md.message_name} ({md.diff_type.value}) ---")
            for sd in md.signal_diffs:
                prefix = {"added": "+", "removed": "-", "modified": "~"}.get(sd.diff_type.value, " ")
                lines.append(f"  {prefix} {sd.signal_name}")
                for field_name, (old, new) in sd.changes.items():
                    lines.append(f"      {field_name}: {old} → {new}")

        viewer.set_diff_content(
            f"{diff.old_version} → {diff.new_version}",
            diff.summary,
            "\n".join(lines),
        )
        layout.addWidget(viewer)

        dialog.exec()

    def filter(self, query: str) -> int:
        """Filter signal table by query. Returns match count."""
        query_lower = query.lower()
        visible = 0
        for row in range(self.signal_model.rowCount()):
            name = self.signal_model.data(self.signal_model.index(row, 0)) or ""
            match = not query or query_lower in str(name).lower()
            self.signal_table.setRowHidden(row, not match)
            if match:
                visible += 1
        # Also filter message tree
        tree = self.msg_tree.tree
        for i in range(tree.topLevelItemCount()):
            parent = tree.topLevelItem(i)
            any_child_visible = False
            for j in range(parent.childCount()):
                child = parent.child(j)
                match = not query or query_lower in child.text(0).lower()
                child.setHidden(not match)
                if match:
                    any_child_visible = True
            parent.setHidden(not any_child_visible and query != "")
        return visible
