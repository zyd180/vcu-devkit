"""Editable table widget for data display and editing."""

from PySide6.QtWidgets import (
    QTableView, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor


class DataTableModel(QAbstractTableModel):
    """Generic table model backed by a list of dicts."""

    def __init__(self, headers: list[str], keys: list[str], parent=None):
        super().__init__(parent)
        self._headers = headers
        self._keys = keys
        self._data: list[dict] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._data[index.row()]
        key = self._keys[index.column()]
        if role in (Qt.DisplayRole, Qt.EditRole):
            val = row.get(key, "")
            return str(val) if val is not None else ""
        if role == Qt.BackgroundRole:
            if row.get("_diff_type") == "added":
                return QColor("#e8f5e9")
            if row.get("_diff_type") == "removed":
                return QColor("#ffebee")
            if row.get("_diff_type") == "modified":
                return QColor("#fff3e0")
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False
        key = self._keys[index.column()]
        self._data[index.row()][key] = value
        self.dataChanged.emit(index, index)
        return True

    def load_data(self, data: list[dict]):
        """Load data from list of dicts."""
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_row(self, row: int) -> dict:
        """Get a single row as dict."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return {}

    def add_row(self, row_data: dict):
        """Add a new row."""
        self.beginInsertRows(QModelIndex(), len(self._data), len(self._data))
        self._data.append(row_data)
        self.endInsertRows()

    def remove_row(self, row: int):
        """Remove a row."""
        if 0 <= row < len(self._data):
            self.beginRemoveRows(QModelIndex(), row, row)
            self._data.pop(row)
            self.endRemoveRows()


class TableEditor(QWidget):
    """Editable table with search and toolbar."""

    row_selected = Signal(int)

    def __init__(self, headers: list[str], keys: list[str], parent=None):
        super().__init__(parent)
        self.model = DataTableModel(headers, keys)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索...")
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input)

        self.add_btn = QPushButton("+ 添加")
        self.add_btn.setFixedWidth(80)
        search_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("- 删除")
        self.remove_btn.setFixedWidth(80)
        search_layout.addWidget(self.remove_btn)

        layout.addLayout(search_layout)

        # Table
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setVisible(False)

        self.table.selectionModel().currentChanged.connect(self._on_row_selected)
        layout.addWidget(self.table)

    def _on_search(self, text: str):
        """Filter table rows by search text."""
        for row in range(self.model.rowCount()):
            match = False
            for col in range(self.model.columnCount()):
                index = self.model.index(row, col)
                cell = self.model.data(index, Qt.DisplayRole) or ""
                if text.lower() in cell.lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def _on_row_selected(self, current, previous):
        """Emit row selected signal."""
        if current.isValid():
            self.row_selected.emit(current.row())

    def load_data(self, data: list[dict]):
        """Load data into table."""
        self.model.load_data(data)
