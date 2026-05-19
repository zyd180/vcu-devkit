"""Main application window."""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStatusBar, QMenuBar, QMenu, QFileDialog, QMessageBox,
    QLabel, QStackedWidget, QSplitter, QToolBar, QApplication,
    QLineEdit,
)
from PySide6.QtCore import Qt, QSize, QMimeData
from PySide6.QtGui import QAction, QKeySequence, QDragEnterEvent, QDropEvent

from config.settings import AppSettings
from ui.sidebar import Sidebar
from ui.widgets.status_bar import StatusBarWidget


class MainWindow(QMainWindow):
    """VCU DevKit main window."""

    def __init__(self, settings: AppSettings):
        super().__init__()
        self.settings = settings
        self._setup_window()
        self._create_menus()
        self._create_toolbar()
        self._create_sidebar()
        self._create_central_area()
        self._create_status_bar()
        self.setAcceptDrops(True)

    def _setup_window(self):
        """Configure window properties."""
        self._update_title()
        self.setMinimumSize(1200, 800)
        self.resize(1600, 1000)

    def _update_title(self):
        """Update window title with project name."""
        import os
        base = f"{self.settings.app_name} v{self.settings.version}"
        if self.settings.last_project_dir:
            project = os.path.basename(self.settings.last_project_dir)
            self.setWindowTitle(f"[{project}] {base}")
        else:
            self.setWindowTitle(base)

    def _create_menus(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("文件(&F)")

        open_project_action = QAction("打开项目(&O)", self)
        open_project_action.setShortcut(QKeySequence("Ctrl+O"))
        open_project_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_project_action)

        file_menu.addSeparator()

        save_action = QAction("保存(&S)", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._on_save)
        file_menu.addAction(save_action)

        save_all_action = QAction("全部保存", self)
        save_all_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        file_menu.addAction(save_all_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("编辑(&E)")
        undo_action = QAction("撤销(&U)", self)
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        edit_menu.addAction(undo_action)
        redo_action = QAction("重做(&R)", self)
        redo_action.setShortcut(QKeySequence("Ctrl+Y"))
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        find_action = QAction("搜索(&F)", self)
        find_action.setShortcut(QKeySequence("Ctrl+F"))
        find_action.triggered.connect(lambda: self._search_box.setFocus())
        edit_menu.addAction(find_action)

        # Tools menu
        tools_menu = menubar.addMenu("工具(&T)")

        check_action = QAction("校验当前配置", self)
        check_action.setShortcut(QKeySequence("F5"))
        check_action.triggered.connect(self._on_check)
        tools_menu.addAction(check_action)

        generate_action = QAction("生成代码", self)
        generate_action.setShortcut(QKeySequence("F6"))
        generate_action.triggered.connect(self._on_generate)
        tools_menu.addAction(generate_action)

        tools_menu.addSeparator()

        theme_light = QAction("浅色主题", self)
        theme_light.triggered.connect(lambda: self._on_switch_theme("light"))
        tools_menu.addAction(theme_light)

        theme_dark = QAction("暗色主题", self)
        theme_dark.triggered.connect(lambda: self._on_switch_theme("dark"))
        tools_menu.addAction(theme_dark)

        # Help menu
        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self):
        """Create main toolbar."""
        toolbar = QToolBar("主工具栏")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_btn = QAction("打开项目", self)
        open_btn.triggered.connect(self._on_open_project)
        toolbar.addAction(open_btn)

        save_btn = QAction("保存", self)
        save_btn.triggered.connect(self._on_save)
        toolbar.addAction(save_btn)

        toolbar.addSeparator()

        check_btn = QAction("校验", self)
        check_btn.triggered.connect(self._on_check)
        toolbar.addAction(check_btn)

        generate_btn = QAction("生成", self)
        generate_btn.triggered.connect(self._on_generate)
        toolbar.addAction(generate_btn)

        toolbar.addSeparator()

        export_btn = QAction("导出", self)
        toolbar.addAction(export_btn)

        # Global search
        toolbar.addSeparator()
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("搜索信号/DTC/参数...")
        self._search_box.setMinimumWidth(200)
        self._search_box.setClearButtonEnabled(True)
        self._search_box.textChanged.connect(self._on_global_search)
        toolbar.addWidget(self._search_box)

    def _create_sidebar(self):
        """Create sidebar navigation."""
        self.sidebar = Sidebar()
        self.sidebar.module_selected.connect(self._on_module_selected)

    def _create_central_area(self):
        """Create central content area with sidebar and stacked pages."""
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.page_stack = QStackedWidget()
        self._loaded_views: dict[int, QWidget] = {}
        self._view_factories = {
            0: self._create_can_view,
            1: self._create_swc_view,
            2: self._create_diag_view,
            3: self._create_calib_view,
            4: self._create_test_view,
            5: self._create_trace_view,
        }

        # Add placeholder widgets; real views created on first access
        for _ in range(6):
            self.page_stack.addWidget(QWidget())

        # Splitter: sidebar | content
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.page_stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 1360])

        main_layout.addWidget(splitter)
        self.setCentralWidget(central_widget)

    def _ensure_view_loaded(self, index: int):
        """Lazily instantiate a module view on first access."""
        if index in self._loaded_views:
            return
        factory = self._view_factories.get(index)
        if factory is None:
            return
        view = factory()
        self._loaded_views[index] = view
        old = self.page_stack.widget(index)
        self.page_stack.removeWidget(old)
        old.deleteLater()
        self.page_stack.insertWidget(index, view)

    def _create_can_view(self):
        from modules.can_builder.views.can_builder_view import CANBuilderView
        return CANBuilderView()

    def _create_swc_view(self):
        from modules.swc_designer.views.swc_designer_view import SWCDesignerView
        return SWCDesignerView()

    def _create_diag_view(self):
        from modules.diag_builder.views.diag_builder_view import DiagBuilderView
        return DiagBuilderView()

    def _create_calib_view(self):
        from modules.calib_manager.views.calib_manager_view import CalibManagerView
        return CalibManagerView()

    def _create_test_view(self):
        from modules.test_generator.views.test_generator_view import TestGeneratorView
        return TestGeneratorView()

    def _create_trace_view(self):
        from modules.trace_matrix.views.trace_matrix_view import TraceMatrixView
        return TraceMatrixView()

    def _create_status_bar(self):
        """Create status bar."""
        self.status_widget = StatusBarWidget()
        self.statusBar().addPermanentWidget(self.status_widget)
        self.statusBar().showMessage("就绪")

    # ---- Slots ----

    def _on_module_selected(self, index: int):
        """Handle sidebar module selection."""
        self._ensure_view_loaded(index)
        self.page_stack.setCurrentIndex(index)
        modules = ["CAN开发", "SWC开发", "诊断配置", "标定管理", "测试生成", "需求追溯"]
        if 0 <= index < len(modules):
            self.statusBar().showMessage(f"当前模块: {modules[index]}")

    def _on_open_project(self):
        """Open a project directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择项目目录", self.settings.last_project_dir
        )
        if dir_path:
            self.settings.last_project_dir = dir_path
            self._update_title()
            self.statusBar().showMessage(f"已加载项目: {dir_path}")
            self.status_widget.set_project(dir_path)

    def _on_save(self):
        """Save current changes."""
        self.statusBar().showMessage("已保存", 3000)

    def _on_check(self):
        """Run validation checks."""
        self.statusBar().showMessage("正在校验...", 5000)

    def _on_generate(self):
        """Generate code."""
        self.statusBar().showMessage("正在生成代码...", 5000)

    def _on_switch_theme(self, theme: str):
        """Switch application theme."""
        qss_path = Path(__file__).parent / "themes" / f"{theme}.qss"
        if qss_path.exists():
            self.settings.theme = theme
            QApplication.instance().setStyleSheet(qss_path.read_text(encoding="utf-8"))
            self.statusBar().showMessage(f"已切换到{'暗色' if theme == 'dark' else '浅色'}主题", 3000)

    def _on_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "关于 VCU DevKit",
            f"<h3>VCU DevKit v{self.settings.version}</h3>"
            "<p>汽车VCU软件开发辅助工具</p>"
            "<p>Vector工具链的效率放大器</p>",
        )

    def closeEvent(self, event):
        """Handle window close."""
        self.settings.save()
        event.accept()

    # ── Global Search ──────────────────────────────────────────────────────

    def _on_global_search(self, query: str):
        """Filter current module's content by search query."""
        current = self.page_stack.currentWidget()
        if hasattr(current, "filter"):
            count = current.filter(query)
            if query:
                self.statusBar().showMessage(f"搜索 '{query}': {count} 条匹配", 3000)
            else:
                self.statusBar().showMessage("就绪")

    # ── Drag & Drop ────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return
        file_path = urls[0].toLocalFile()
        ext = Path(file_path).suffix.lower()

        # Route by extension to the appropriate module
        if ext == ".dbc":
            self.page_stack.setCurrentIndex(0)
            self.sidebar.module_list.setCurrentRow(0)
            self._can_view.load_file(file_path)
            self.statusBar().showMessage(f"已拖入: {Path(file_path).name}", 5000)
        elif ext == ".arxml":
            self.page_stack.setCurrentIndex(1)
            self.sidebar.module_list.setCurrentRow(1)
            self._swc_view.load_file(file_path)
            self.statusBar().showMessage(f"已拖入: {Path(file_path).name}", 5000)
        elif ext in (".odx", ".odx-d", ".odx-c", ".cdd"):
            self.page_stack.setCurrentIndex(2)
            self.sidebar.module_list.setCurrentRow(2)
            self._diag_view.load_file(file_path)
            self.statusBar().showMessage(f"已拖入: {Path(file_path).name}", 5000)
        elif ext == ".a2l":
            self.page_stack.setCurrentIndex(3)
            self.sidebar.module_list.setCurrentRow(3)
            self._calib_view.load_file(file_path)
            self.statusBar().showMessage(f"已拖入: {Path(file_path).name}", 5000)
        elif ext == ".json":
            self.statusBar().showMessage(f"JSON文件请通过各模块的导入功能加载: {Path(file_path).name}", 5000)
        else:
            self.statusBar().showMessage(f"不支持的文件格式: {ext}", 5000)
