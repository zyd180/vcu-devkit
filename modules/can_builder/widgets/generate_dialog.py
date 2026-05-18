"""Code generation configuration dialog."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QPushButton, QLabel, QLineEdit,
    QFileDialog, QFormLayout, QComboBox,
)
from PySide6.QtCore import Qt


@dataclass
class GenerateConfig:
    """Configuration for code generation."""
    output_dir: str = ""
    generate_c_pack: bool = True
    generate_c_signals: bool = True
    generate_c_messages: bool = True
    generate_capl: bool = True
    generate_diff_report: bool = False
    capl_filename: str = "vcu_node.can"


class GenerateDialog(QDialog):
    """Dialog for configuring code generation options."""

    def __init__(self, parent=None, current_dir: str = ""):
        super().__init__(parent)
        self.setWindowTitle("生成代码")
        self.setMinimumWidth(480)
        self._current_dir = current_dir
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Output directory
        dir_group = QGroupBox("输出目录")
        dir_layout = QHBoxLayout(dir_group)
        self.dir_edit = QLineEdit(self._current_dir)
        self.dir_edit.setPlaceholderText("选择输出目录...")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_dir)
        dir_layout.addWidget(self.dir_edit)
        dir_layout.addWidget(browse_btn)
        layout.addWidget(dir_group)

        # C code options
        c_group = QGroupBox("C代码产物")
        c_layout = QVBoxLayout(c_group)
        self.chk_pack = QCheckBox("can_pack.h — Pack/Unpack函数")
        self.chk_pack.setChecked(True)
        self.chk_signals = QCheckBox("can_signals.h — 信号变量映射")
        self.chk_signals.setChecked(True)
        self.chk_messages = QCheckBox("can_messages.h — 报文ID定义")
        self.chk_messages.setChecked(True)
        c_layout.addWidget(self.chk_pack)
        c_layout.addWidget(self.chk_signals)
        c_layout.addWidget(self.chk_messages)
        layout.addWidget(c_group)

        # CAPL options
        capl_group = QGroupBox("CAPL产物")
        capl_layout = QVBoxLayout(capl_group)
        self.chk_capl = QCheckBox("vcu_node.can — CANoe网络节点")
        self.chk_capl.setChecked(True)
        capl_layout.addWidget(self.chk_capl)

        name_layout = QFormLayout()
        self.capl_name_edit = QLineEdit("vcu_node.can")
        name_layout.addRow("文件名:", self.capl_name_edit)
        capl_layout.addLayout(name_layout)
        layout.addWidget(capl_group)

        # Report options
        report_group = QGroupBox("报告产物")
        report_layout = QVBoxLayout(report_group)
        self.chk_diff_report = QCheckBox("变更报告 (.xlsx)")
        report_layout.addWidget(self.chk_diff_report)
        layout.addWidget(report_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        gen_btn = QPushButton("生成")
        gen_btn.setDefault(True)
        gen_btn.clicked.connect(self._on_generate)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(gen_btn)
        layout.addLayout(btn_layout)

    def _browse_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择输出目录", self.dir_edit.text()
        )
        if dir_path:
            self.dir_edit.setText(dir_path)

    def _on_generate(self):
        if not self.dir_edit.text():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请先选择输出目录")
            return
        self.accept()

    def get_config(self) -> GenerateConfig:
        return GenerateConfig(
            output_dir=self.dir_edit.text(),
            generate_c_pack=self.chk_pack.isChecked(),
            generate_c_signals=self.chk_signals.isChecked(),
            generate_c_messages=self.chk_messages.isChecked(),
            generate_capl=self.chk_capl.isChecked(),
            generate_diff_report=self.chk_diff_report.isChecked(),
            capl_filename=self.capl_name_edit.text(),
        )
