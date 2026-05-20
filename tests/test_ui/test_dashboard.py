"""Tests for ui.widgets.dashboard — Dashboard home page widget."""

import pytest
from unittest.mock import MagicMock

from PySide6.QtCore import Qt

from ui.widgets.dashboard import DashboardWidget


@pytest.fixture
def dashboard(qtbot):
    w = DashboardWidget()
    qtbot.addWidget(w)
    return w


@pytest.fixture
def dashboard_with_settings(qtbot):
    settings = MagicMock()
    settings.recent_files = [
        r"C:\project\test.dbc",
        r"C:\project\voltage.arxml",
        r"C:\project\cal.a2l",
    ]
    w = DashboardWidget(settings=settings)
    qtbot.addWidget(w)
    return w


class TestDashboardCreation:

    def test_create_without_settings(self, dashboard):
        assert dashboard is not None
        assert dashboard.settings is None

    def test_create_with_settings(self, dashboard_with_settings):
        assert dashboard_with_settings.settings is not None

    def test_has_recent_list(self, dashboard):
        assert hasattr(dashboard, "_recent_list")
        assert dashboard._recent_list.count() == 0

    def test_has_stats_labels(self, dashboard):
        assert "dbc" in dashboard._stats_labels
        assert "arxml" in dashboard._stats_labels
        assert "a2l" in dashboard._stats_labels

    def test_has_module_status_labels(self, dashboard):
        assert len(dashboard._module_status_labels) == 6


class TestDashboardStats:

    def test_update_stats_all(self, dashboard):
        dashboard.update_stats({"dbc": 3, "arxml": 2, "a2l": 1})
        assert dashboard._stats_labels["dbc"].text() == "3"
        assert dashboard._stats_labels["arxml"].text() == "2"
        assert dashboard._stats_labels["a2l"].text() == "1"

    def test_update_stats_partial(self, dashboard):
        dashboard.update_stats({"dbc": 5})
        assert dashboard._stats_labels["dbc"].text() == "5"
        assert dashboard._stats_labels["arxml"].text() == "—"
        assert dashboard._stats_labels["a2l"].text() == "—"

    def test_update_stats_empty(self, dashboard):
        dashboard.update_stats({})
        for lbl in dashboard._stats_labels.values():
            assert lbl.text() == "—"

    def test_update_stats_zero(self, dashboard):
        dashboard.update_stats({"dbc": 0})
        assert dashboard._stats_labels["dbc"].text() == "—"


class TestDashboardModuleStatus:

    def test_set_module_loaded(self, dashboard):
        dashboard.set_module_loaded(0, True)
        assert "已加载" in dashboard._module_status_labels[0].text()

    def test_set_module_unloaded(self, dashboard):
        dashboard.set_module_loaded(0, True)
        dashboard.set_module_loaded(0, False)
        assert "未加载" in dashboard._module_status_labels[0].text()

    def test_set_module_out_of_range(self, dashboard):
        # Should not raise
        dashboard.set_module_loaded(-1, True)
        dashboard.set_module_loaded(99, True)

    def test_all_modules_status(self, dashboard):
        for i in range(6):
            dashboard.set_module_loaded(i, True)
            assert "已加载" in dashboard._module_status_labels[i].text()


class TestDashboardRecentFiles:

    def test_recent_populated(self, dashboard_with_settings):
        assert dashboard_with_settings._recent_list.count() == 3

    def test_recent_item_data(self, dashboard_with_settings):
        item = dashboard_with_settings._recent_list.item(0)
        assert item.data(Qt.UserRole) == r"C:\project\test.dbc"

    def test_recent_item_tooltip(self, dashboard_with_settings):
        item = dashboard_with_settings._recent_list.item(1)
        assert item.toolTip() == r"C:\project\voltage.arxml"

    def test_recent_refresh(self, dashboard_with_settings):
        dashboard_with_settings.settings.recent_files = [r"C:\new.dbc"]
        dashboard_with_settings.refresh()
        assert dashboard_with_settings._recent_list.count() == 1

    def test_recent_no_settings(self, dashboard):
        dashboard._refresh_recent()
        assert dashboard._recent_list.count() == 0

    def test_open_file_signal(self, dashboard_with_settings, qtbot):
        item = dashboard_with_settings._recent_list.item(0)
        with qtbot.waitSignal(dashboard_with_settings.open_file_requested, timeout=1000) as blocker:
            dashboard_with_settings._on_recent_double_click(item)
        assert blocker.args == [r"C:\project\test.dbc"]


class TestDashboardSignals:

    def test_module_requested_signal(self, dashboard, qtbot):
        with qtbot.waitSignal(dashboard.module_requested, timeout=1000) as blocker:
            dashboard.module_requested.emit(1)
        assert blocker.args == [1]

    def test_open_file_requested_signal(self, dashboard, qtbot):
        with qtbot.waitSignal(dashboard.open_file_requested, timeout=1000) as blocker:
            dashboard.open_file_requested.emit(r"C:\test.dbc")
        assert blocker.args == [r"C:\test.dbc"]
