"""Tree view widget with filtering support."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QLineEdit, QPushButton,
)
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem


class FilterProxyModel(QSortFilterProxyModel):
    """Filter proxy for tree model."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def filterAcceptsRow(self, source_row, source_parent):
        """Show parent items when any child matches."""
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        if model.hasChildren(index):
            for i in range(model.rowCount(index)):
                child_index = model.index(i, 0, index)
                text = model.data(child_index) or ""
                if self.filterRegularExpression().match(text).hasMatch():
                    return True
            return False
        text = model.data(index) or ""
        return self.filterRegularExpression().match(text).hasMatch()


class TreeView(QWidget):
    """Tree view with search filtering."""

    item_selected = Signal(str)
    child_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = QStandardItemModel()
        self.proxy = FilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索...")
        self.search_input.textChanged.connect(self._on_filter)
        search_layout.addWidget(self.search_input)

        self.expand_btn = QPushButton("展开")
        self.expand_btn.setFixedWidth(60)
        self.expand_btn.clicked.connect(self._on_expand_all)
        search_layout.addWidget(self.expand_btn)

        self.collapse_btn = QPushButton("折叠")
        self.collapse_btn.setFixedWidth(60)
        self.collapse_btn.clicked.connect(self._on_collapse_all)
        search_layout.addWidget(self.collapse_btn)

        layout.addLayout(search_layout)

        # Tree
        self.tree = QTreeView()
        self.tree.setModel(self.proxy)
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.clicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

    def _on_filter(self, text: str):
        """Filter tree items."""
        self.proxy.setFilterFixedString(text)
        if text:
            self.tree.expandAll()

    def _on_expand_all(self):
        self.tree.expandAll()

    def _on_collapse_all(self):
        self.tree.collapseAll()

    def _on_item_clicked(self, index):
        """Handle item click."""
        source_index = self.proxy.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        if item:
            if item.parent() is not None:
                self.child_selected.emit(item.text())
            else:
                self.item_selected.emit(item.text())

    def add_top_level_item(self, name: str, icon=None) -> QStandardItem:
        """Add a top-level tree item."""
        item = QStandardItem(name)
        if icon:
            item.setIcon(icon)
        item.setEditable(False)
        self.model.appendRow(item)
        return item

    def add_child_item(self, parent: QStandardItem, name: str) -> QStandardItem:
        """Add a child item to a parent."""
        item = QStandardItem(name)
        item.setEditable(False)
        parent.appendRow(item)
        return item

    def clear(self):
        """Clear all items."""
        self.model.clear()
