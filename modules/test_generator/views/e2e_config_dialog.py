"""E2E / Counter per-message configuration dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from modules.test_generator.controller import (
    COUNTER_SPECS,
    E2E_PROFILE_SPECS,
    CounterAlgorithm,
    E2EConfig,
    E2EProfile,
)


class E2EConfigDialog(QDialog):
    """Dialog for configuring E2E protection and counter validation per message."""

    def __init__(self, configs: list[E2EConfig], signals_by_msg: dict[str, list[str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("E2E / 计数器 配置")
        self.setMinimumSize(900, 500)
        self.configs = configs
        self.signals_by_msg = signals_by_msg
        self._setup_ui()
        self._load_configs()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header info
        info = QLabel("为每条报文配置 E2E 保护算法和计数器验证算法。支持从 DBC 信号名称自动识别。")
        info.setStyleSheet("color: #666; padding: 4px 0;")
        layout.addWidget(info)

        # Quick actions
        btn_layout = QHBoxLayout()
        btn_enable_all_e2e = QPushButton("全部启用 E2E")
        btn_enable_all_cnt = QPushButton("全部启用计数器")
        btn_disable_all = QPushButton("全部禁用")
        btn_enable_all_e2e.clicked.connect(lambda: self._toggle_all("e2e", True))
        btn_enable_all_cnt.clicked.connect(lambda: self._toggle_all("counter", True))
        btn_disable_all.clicked.connect(lambda: self._toggle_all("all", False))
        btn_layout.addWidget(btn_enable_all_e2e)
        btn_layout.addWidget(btn_enable_all_cnt)
        btn_layout.addWidget(btn_disable_all)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["报文名称", "ID", "启用 E2E", "E2E Profile", "CRC 信号", "启用计数器", "计数器算法"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table, stretch=1)

        # Detail group — shows profile specs
        detail_group = QGroupBox("当前选中 Profile 详情")
        self.detail_layout = QVBoxLayout(detail_group)
        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_layout.addWidget(self.detail_label)
        layout.addWidget(detail_group)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.table.currentCellChanged.connect(self._on_selection_changed)

    def _load_configs(self):
        self.table.setRowCount(len(self.configs))
        self._combo_refs: list[dict] = []  # store widget refs per row

        for row, cfg in enumerate(self.configs):
            sigs = self.signals_by_msg.get(cfg.message_name, [])

            # Message name (read-only)
            name_item = QTableWidgetItem(cfg.message_name)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 0, name_item)

            # Message ID (read-only)
            id_item = QTableWidgetItem(f"0x{cfg.message_id:03X}")
            id_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 1, id_item)

            # E2E enabled checkbox
            chk_e2e = QCheckBox()
            chk_e2e.setChecked(cfg.e2e_enabled)
            self.table.setCellWidget(row, 2, chk_e2e)

            # E2E Profile combo
            profile_combo = QComboBox()
            for p in E2EProfile:
                profile_combo.addItem(p.value, p)
            idx = list(E2EProfile).index(cfg.e2e_profile)
            profile_combo.setCurrentIndex(idx)
            profile_combo.currentIndexChanged.connect(lambda i, r=row: self._on_profile_changed(r))
            self.table.setCellWidget(row, 3, profile_combo)

            # CRC signal combo
            crc_combo = QComboBox()
            crc_combo.addItem("(无)", "")
            for s in sigs:
                crc_combo.addItem(s, s)
            if cfg.crc_signal:
                idx = crc_combo.findData(cfg.crc_signal)
                if idx >= 0:
                    crc_combo.setCurrentIndex(idx)
            self.table.setCellWidget(row, 4, crc_combo)

            # Counter enabled checkbox
            chk_cnt = QCheckBox()
            chk_cnt.setChecked(cfg.counter_enabled)
            self.table.setCellWidget(row, 5, chk_cnt)

            # Counter algorithm combo
            algo_combo = QComboBox()
            for a in CounterAlgorithm:
                label = f"{a.value} ({COUNTER_SPECS[a]['max'] + 1}个值, {COUNTER_SPECS[a]['bits']}-bit)"
                algo_combo.addItem(label, a)
            idx = list(CounterAlgorithm).index(cfg.counter_algorithm)
            algo_combo.setCurrentIndex(idx)
            self.table.setCellWidget(row, 6, algo_combo)

            self._combo_refs.append(
                {
                    "chk_e2e": chk_e2e,
                    "profile_combo": profile_combo,
                    "crc_combo": crc_combo,
                    "chk_cnt": chk_cnt,
                    "algo_combo": algo_combo,
                }
            )

    def _on_profile_changed(self, row: int):
        combo = self._combo_refs[row]["profile_combo"]
        profile = combo.currentData()
        if profile and profile in E2E_PROFILE_SPECS:
            spec = E2E_PROFILE_SPECS[profile]
            self.detail_label.setText(
                f"Profile: {profile.value}\n"
                f"CRC 算法: {spec['crc']}\n"
                f"计数器范围: 0-{spec['counter_max']} ({spec['counter_bits']}-bit)\n"
                f"DataID 模式: {spec['data_id_mode']}"
            )

    def _on_selection_changed(self, row, _col, _prev_row, _prev_col):
        if 0 <= row < len(self._combo_refs):
            profile = self._combo_refs[row]["profile_combo"].currentData()
            if profile and profile in E2E_PROFILE_SPECS:
                spec = E2E_PROFILE_SPECS[profile]
                self.detail_label.setText(
                    f"Profile: {profile.value}\n"
                    f"CRC 算法: {spec['crc']}\n"
                    f"计数器范围: 0-{spec['counter_max']} ({spec['counter_bits']}-bit)\n"
                    f"DataID 模式: {spec['data_id_mode']}"
                )

    def _toggle_all(self, mode: str, enabled: bool):
        for row, refs in enumerate(self._combo_refs):
            if mode in ("e2e", "all"):
                refs["chk_e2e"].setChecked(enabled)
            if mode in ("counter", "all"):
                refs["chk_cnt"].setChecked(enabled)

    def _on_accept(self):
        # Write widget state back to configs
        for row, refs in enumerate(self._combo_refs):
            cfg = self.configs[row]
            cfg.e2e_enabled = refs["chk_e2e"].isChecked()
            cfg.e2e_profile = refs["profile_combo"].currentData()
            cfg.crc_signal = refs["crc_combo"].currentData() or ""
            cfg.counter_enabled = refs["chk_cnt"].isChecked()
            cfg.counter_algorithm = refs["algo_combo"].currentData()
        self.accept()

    def get_configs(self) -> list[E2EConfig]:
        return self.configs
