"""Main application window."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from config.settings import AppSettings
from ui.sidebar import Sidebar
from ui.widgets.status_bar import StatusBarWidget
from ui.widgets.welcome_dialog import WelcomeDialog


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
        # Show welcome dialog after window is visible (first launch only)
        if not self.settings.recent_files and not self.settings.last_project_dir:
            QTimer.singleShot(500, self._show_welcome)

    def _setup_window(self):
        """Configure window properties."""
        self._update_title()
        self.setMinimumSize(1200, 800)
        self.resize(1600, 1000)

    def _update_title(self):
        """Update window title with project name."""
        base = f"{self.settings.app_name} v{self.settings.version}"
        if self.settings.last_project_dir:
            project = Path(self.settings.last_project_dir).name
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

        # Recent files submenu
        self._recent_menu = file_menu.addMenu("最近文件(&R)")
        self._rebuild_recent_menu()

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
        open_btn.setToolTip("打开项目目录 (Ctrl+O)")
        open_btn.triggered.connect(self._on_open_project)
        toolbar.addAction(open_btn)

        save_btn = QAction("保存", self)
        save_btn.setToolTip("保存当前模块数据 (Ctrl+S)")
        save_btn.triggered.connect(self._on_save)
        toolbar.addAction(save_btn)

        toolbar.addSeparator()

        check_btn = QAction("校验", self)
        check_btn.setToolTip("校验当前配置的规则合规性 (F5)")
        check_btn.triggered.connect(self._on_check)
        toolbar.addAction(check_btn)

        generate_btn = QAction("生成", self)
        generate_btn.setToolTip("生成代码或导出文件 (F6)")
        generate_btn.triggered.connect(self._on_generate)
        toolbar.addAction(generate_btn)

        toolbar.addSeparator()

        self._export_btn = QAction("导出", self)
        self._export_btn.setToolTip("选择导出格式（C/CAPL/Excel/ARXML/A2L/JSON）")
        self._export_btn.triggered.connect(self._on_export)
        toolbar.addAction(self._export_btn)

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
            0: self._create_dashboard_view,
            1: self._create_can_view,
            2: self._create_swc_view,
            3: self._create_diag_view,
            4: self._create_calib_view,
            5: self._create_test_view,
            6: self._create_trace_view,
        }

        # Add placeholder widgets; real views created on first access
        for _ in range(7):
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

    def _create_dashboard_view(self):
        from ui.widgets.dashboard import DashboardWidget

        dashboard = DashboardWidget(settings=self.settings)
        dashboard.module_requested.connect(self._on_module_selected)
        dashboard.open_file_requested.connect(self._on_open_recent)
        return dashboard

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
        modules = ["概览", "CAN开发", "SWC开发", "诊断配置", "标定管理", "测试生成", "需求追溯"]
        if 0 <= index < len(modules):
            self.statusBar().showMessage(f"当前模块: {modules[index]}")

    def _on_open_project(self):
        """Open a project directory."""
        dir_path = QFileDialog.getExistingDirectory(self, "选择项目目录", self.settings.last_project_dir)
        if dir_path:
            self.settings.last_project_dir = dir_path
            self._update_title()
            self.statusBar().showMessage(f"已加载项目: {dir_path}")
            self.status_widget.set_project(dir_path)

    def _on_save(self):
        """Save current changes by delegating to the active module's controller."""
        view = self.page_stack.currentWidget()
        controller = getattr(view, "controller", None)
        if controller is None:
            self.statusBar().showMessage("当前模块没有可保存的数据", 3000)
            return

        try:
            # CAN Builder has save_dbc(); other modules may have export methods
            if hasattr(controller, "save_dbc"):
                controller.save_dbc()
                self.statusBar().showMessage("DBC 文件已保存", 3000)
            elif hasattr(controller, "export_arxml"):
                path, _ = QFileDialog.getSaveFileName(self, "保存 ARXML", "", "ARXML 文件 (*.arxml)")
                if path:
                    controller.export_arxml(path)
                    self.statusBar().showMessage(f"已保存: {path}", 3000)
            elif hasattr(controller, "export_json"):
                path, _ = QFileDialog.getSaveFileName(self, "保存 JSON", "", "JSON 文件 (*.json)")
                if path:
                    controller.export_json(path)
                    self.statusBar().showMessage(f"已保存: {path}", 3000)
            elif hasattr(controller, "export_excel"):
                path, _ = QFileDialog.getSaveFileName(self, "保存 Excel", "", "Excel 文件 (*.xlsx)")
                if path:
                    controller.export_excel(path)
                    self.statusBar().showMessage(f"已保存: {path}", 3000)
            else:
                self.statusBar().showMessage("当前模块不支持保存操作", 3000)
        except Exception as e:
            self.statusBar().showMessage(f"保存失败: {e}", 5000)

    def _on_check(self):
        """Run validation on the current module's data."""
        view = self.page_stack.currentWidget()
        controller = getattr(view, "controller", None)
        if controller is None or not hasattr(controller, "validate"):
            self.statusBar().showMessage("当前模块不支持校验", 3000)
            return

        try:
            result = controller.validate()
            if isinstance(result, list) and len(result) > 0 and hasattr(result[0], "severity"):
                errors = sum(1 for r in result if r.severity.value == "error")
                warnings = sum(1 for r in result if r.severity.value == "warning")
                info = sum(1 for r in result if r.severity.value == "info")
                if errors == 0 and warnings == 0:
                    self.statusBar().showMessage(f"校验通过 ({info} 条提示)", 3000)
                else:
                    self.statusBar().showMessage(f"校验完成: {errors} 个错误, {warnings} 个警告, {info} 条提示", 5000)
            elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
                errors = sum(1 for r in result if r.get("type") == "error")
                warnings = sum(1 for r in result if r.get("type") == "warning")
                self.statusBar().showMessage(f"校验完成: {errors} 个错误, {warnings} 个警告", 5000)
            elif isinstance(result, list):
                self.statusBar().showMessage("校验通过，无错误和警告", 3000)
            elif isinstance(result, dict):
                errors = result.get("errors", 0)
                warnings = result.get("warnings", 0)
                if errors == 0 and warnings == 0:
                    self.statusBar().showMessage("校验通过，无错误和警告", 3000)
                else:
                    self.statusBar().showMessage(f"校验完成: {errors} 个错误, {warnings} 个警告", 5000)
            else:
                self.statusBar().showMessage(f"校验完成: {result}", 5000)
        except Exception as e:
            self.statusBar().showMessage(f"校验失败: {e}", 5000)

    def _on_generate(self):
        """Generate code or export from the current module."""
        view = self.page_stack.currentWidget()
        controller = getattr(view, "controller", None)
        if controller is None:
            self.statusBar().showMessage("当前模块没有控制器", 3000)
            return

        try:
            if hasattr(controller, "generate_code"):
                # CAN Builder: generate C code
                output_dir = QFileDialog.getExistingDirectory(self, "选择代码输出目录")
                if output_dir:
                    controller.generate_code(output_dir)
                    self.statusBar().showMessage(f"代码已生成到: {output_dir}", 5000)
            elif hasattr(controller, "export_arxml"):
                path, _ = QFileDialog.getSaveFileName(self, "导出 ARXML", "", "ARXML 文件 (*.arxml)")
                if path:
                    controller.export_arxml(path)
                    self.statusBar().showMessage(f"已导出: {path}", 5000)
            elif hasattr(controller, "export_json"):
                path, _ = QFileDialog.getSaveFileName(self, "导出 JSON", "", "JSON 文件 (*.json)")
                if path:
                    controller.export_json(path)
                    self.statusBar().showMessage(f"已导出: {path}", 5000)
            elif hasattr(controller, "export_excel"):
                path, _ = QFileDialog.getSaveFileName(self, "导出 Excel", "", "Excel 文件 (*.xlsx)")
                if path:
                    controller.export_excel(path)
                    self.statusBar().showMessage(f"已导出: {path}", 5000)
            elif hasattr(controller, "export_a2l"):
                path, _ = QFileDialog.getSaveFileName(self, "导出 A2L", "", "A2L 文件 (*.a2l)")
                if path:
                    controller.export_a2l(path)
                    self.statusBar().showMessage(f"已导出: {path}", 5000)
            else:
                self.statusBar().showMessage("当前模块不支持代码生成/导出", 3000)
        except Exception as e:
            self.statusBar().showMessage(f"生成/导出失败: {e}", 5000)

    def _on_export(self):
        """Show export format menu and delegate to the current module's controller."""
        view = self.page_stack.currentWidget()
        controller = getattr(view, "controller", None)
        if controller is None:
            self.statusBar().showMessage("当前模块没有控制器", 3000)
            return

        # Build available export actions based on what the controller supports
        menu = QMenu(self)
        export_actions = []

        if hasattr(controller, "generate_code"):
            act = menu.addAction("导出 C 代码")
            export_actions.append(("generate_code", act, "C 代码", ""))
        if hasattr(controller, "generate_capl"):
            act = menu.addAction("导出 CAPL")
            export_actions.append(("generate_capl", act, "CAPL", ""))
        if hasattr(controller, "export_excel"):
            act = menu.addAction("导出 Excel")
            export_actions.append(("export_excel", act, "Excel", "Excel 文件 (*.xlsx)"))
        if hasattr(controller, "export_arxml"):
            act = menu.addAction("导出 ARXML")
            export_actions.append(("export_arxml", act, "ARXML", "ARXML 文件 (*.arxml)"))
        if hasattr(controller, "export_json"):
            act = menu.addAction("导出 JSON")
            export_actions.append(("export_json", act, "JSON", "JSON 文件 (*.json)"))
        if hasattr(controller, "export_a2l"):
            act = menu.addAction("导出 A2L")
            export_actions.append(("export_a2l", act, "A2L", "A2L 文件 (*.a2l)"))

        if not export_actions:
            self.statusBar().showMessage("当前模块不支持导出", 3000)
            return

        # Show menu at the export button position
        action = menu.exec(
            self._export_btn.parentWidget().mapToGlobal(self._export_btn.parentWidget().rect().bottomLeft())
        )
        if action is None:
            return

        # Find which action was triggered
        for method_name, act, label, filter_str in export_actions:
            if act is action:
                try:
                    if method_name == "generate_code":
                        # Code generation uses a directory chooser
                        output_dir = QFileDialog.getExistingDirectory(self, f"选择 {label} 输出目录")
                        if output_dir:
                            getattr(controller, method_name)(output_dir)
                            self.statusBar().showMessage(f"{label} 已导出到: {output_dir}", 5000)
                    else:
                        # File export uses a save file dialog
                        path, _ = QFileDialog.getSaveFileName(self, f"导出 {label}", "", filter_str)
                        if path:
                            getattr(controller, method_name)(path)
                            self.statusBar().showMessage(f"已导出: {path}", 5000)
                except Exception as e:
                    self.statusBar().showMessage(f"导出失败: {e}", 5000)
                break

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

    # ── Recent Files ──────────────────────────────────────────────────────────

    def _rebuild_recent_menu(self):
        """Rebuild the recent files submenu."""
        self._recent_menu.clear()
        if not self.settings.recent_files:
            action = self._recent_menu.addAction("（无最近文件）")
            action.setEnabled(False)
            return
        for fp in self.settings.recent_files:
            name = Path(fp).name
            action = self._recent_menu.addAction(name)
            action.setToolTip(fp)
            action.triggered.connect(lambda checked=False, p=fp: self._on_open_recent(p))

    def _on_open_recent(self, file_path: str):
        """Open a file from the recent files list."""
        if not Path(file_path).exists():
            self.statusBar().showMessage(f"文件不存在: {file_path}", 5000)
            self.settings.recent_files.remove(file_path)
            self._rebuild_recent_menu()
            return
        self._load_file(file_path)

    def _load_file(self, file_path: str):
        """Load a file into the appropriate module view."""
        ext = Path(file_path).suffix.lower()
        ext_module_map = {
            ".dbc": 0,
            ".arxml": 1,
            ".odx": 2,
            ".odx-d": 2,
            ".odx-c": 2,
            ".cdd": 2,
            ".a2l": 3,
        }
        module_index = ext_module_map.get(ext)
        if module_index is not None:
            self._ensure_view_loaded(module_index)
            self.page_stack.setCurrentIndex(module_index)
            self.sidebar.module_list.setCurrentRow(module_index)
            view = self.page_stack.widget(module_index)
            if hasattr(view, "load_file"):
                view.load_file(file_path)
            self.settings.add_recent_file(file_path)
            self._rebuild_recent_menu()
            self.statusBar().showMessage(f"已加载: {Path(file_path).name}", 5000)

    # ── Welcome Dialog ────────────────────────────────────────────────────────

    def _show_welcome(self):
        """Show the welcome/onboarding dialog."""
        dlg = WelcomeDialog(recent_files=self.settings.recent_files, parent=self)
        dlg.file_selected.connect(self._load_file)
        dlg.exec()

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
        supported = {".dbc", ".arxml", ".odx", ".odx-d", ".odx-c", ".cdd", ".a2l"}
        if ext in supported:
            self._load_file(file_path)
        elif ext == ".json":
            self.statusBar().showMessage(f"JSON文件请通过各模块的导入功能加载: {Path(file_path).name}", 5000)
        else:
            self.statusBar().showMessage(f"不支持的文件格式: {ext}", 5000)
