"""Tests for A2L → calibration DB import pipeline."""

import pytest
from pathlib import Path

from core.parsers.a2l_parser import A2LParser
from core.db.manager import DatabaseManager
from modules.calib_manager.controller import CalibManagerController


# ── Realistic A2L content ─────────────────────────────────────────────────────

A2L_FULL = """\
ASAP2_VERSION 1 71
/begin PROJECT VCU_Project "VCU Calibration"
  /begin HEADER "VCU Calibration Data"
    VERSION "1.0"
  /end HEADER

  /begin MODULE VCU_Module "VCU"

    /begin COMPU_METHOD CM_Linear "Linear conversion" RAT_FUNC "%8.2" "rpm"
      COEFFS 0 1 0 0 0 1
    /end COMPU_METHOD

    /begin COMPU_METHOD CM_Identical "No conversion" IDENTICAL "%8.2" ""
    /end COMPU_METHOD

    /begin CHARACTERISTIC EngSpeed "Engine Speed" VALUE 0x1000 RL_Speed 0.0 5000.0
      COMPU_METHOD CM_Linear
      UNIT "rpm"
      LONG-NAME "Engine rotational speed"
      LOWER_LIMIT 0.0
      UPPER_LIMIT 8000.0
    /end CHARACTERISTIC

    /begin CHARACTERISTIC ThrottlePos "Throttle Position" VALUE 0x1004 RL_Pct 0.0 100.0
      COMPU_METHOD CM_Identical
      UNIT "%"
      LOWER_LIMIT 0.0 UPPER_LIMIT 100.0
    /end CHARACTERISTIC

    /begin CHARACTERISTIC BatteryVolt "Battery Voltage" VALUE 0x1008 RL_Volt 0.0 18.0
      UNIT "V"
      LOWER_LIMIT 0.0
      UPPER_LIMIT 18.0
    /end CHARACTERISTIC

    /begin MEASUREMENT HV_Voltage "HV Bus Voltage" UWORD CM_Linear 0 0.0 0.0 1000.0
      UNIT "V"
      ECU_ADDRESS 0x2000
    /end MEASUREMENT

    /begin MEASUREMENT MotorSpeed "Motor Speed" SWORD CM_Linear 0 0.0 -10000.0 10000.0
      UNIT "rpm"
    /end MEASUREMENT

  /end MODULE
/end PROJECT
"""

A2L_INLINE = """\
/begin CHARACTERISTIC Param1 "Inline Param" VALUE 0x1000 RL1 0 0 100
/end CHARACTERISTIC
/begin CHARACTERISTIC Param2 "Another Param" VALUE 0x2000 RL2 0 0 200
/end CHARACTERISTIC
"""

A2L_MULTI_LINE = """\
/begin CHARACTERISTIC
    EngSpeed "Engine Speed" VALUE 0x1000 RL_Speed
    LOWER_LIMIT 0.0
    UPPER_LIMIT 8000.0
/end CHARACTERISTIC
"""

A2L_LIMITS_SAME_LINE = """\
/begin CHARACTERISTIC
    ThrottlePos "Throttle" VALUE 0x1004 RL_Pct
    LOWER_LIMIT 0.0 UPPER_LIMIT 100.0
/end CHARACTERISTIC
"""

A2L_NO_LIMITS = """\
/begin CHARACTERISTIC
    SomeParam "No Limits" VALUE 0x3000 RL_Default
/end CHARACTERISTIC
"""


@pytest.fixture
def parser():
    return A2LParser()


@pytest.fixture
def db_manager(tmp_path):
    db_path = tmp_path / "test.db"
    mgr = DatabaseManager(db_path)
    mgr.init()
    yield mgr
    DatabaseManager._initialized_paths.discard(str(db_path))


@pytest.fixture
def controller(db_manager):
    return CalibManagerController(db_manager=db_manager)


@pytest.fixture
def a2l_file(tmp_path):
    f = tmp_path / "test.a2l"
    f.write_text(A2L_FULL, encoding="utf-8")
    return f


# ── Parser tests ──────────────────────────────────────────────────────────────


class TestA2LParserFormats:

    def test_full_a2l_characteristics(self, parser):
        result = parser.parse_string(A2L_FULL)
        assert result.success
        assert len(result.data.characteristics) == 3

    def test_full_a2l_measurements(self, parser):
        result = parser.parse_string(A2L_FULL)
        assert len(result.data.measurements) == 2

    def test_full_a2l_compu_methods(self, parser):
        result = parser.parse_string(A2L_FULL)
        assert len(result.data.compu_methods) == 2

    def test_full_a2l_names(self, parser):
        result = parser.parse_string(A2L_FULL)
        names = [c.name for c in result.data.characteristics]
        assert "EngSpeed" in names
        assert "ThrottlePos" in names
        assert "BatteryVolt" in names

    def test_full_a2l_limits(self, parser):
        result = parser.parse_string(A2L_FULL)
        eng = next(c for c in result.data.characteristics if c.name == "EngSpeed")
        assert eng.lower_limit == 0.0
        assert eng.upper_limit == 8000.0

    def test_full_a2l_unit(self, parser):
        result = parser.parse_string(A2L_FULL)
        eng = next(c for c in result.data.characteristics if c.name == "EngSpeed")
        assert eng.unit == "rpm"

    def test_full_a2l_description(self, parser):
        result = parser.parse_string(A2L_FULL)
        eng = next(c for c in result.data.characteristics if c.name == "EngSpeed")
        assert "Engine" in eng.description

    def test_inline_format(self, parser):
        result = parser.parse_string(A2L_INLINE)
        assert result.success
        assert len(result.data.characteristics) == 2
        assert result.data.characteristics[0].name == "Param1"

    def test_multi_line_limits(self, parser):
        result = parser.parse_string(A2L_MULTI_LINE)
        assert result.success
        assert len(result.data.characteristics) == 1
        char = result.data.characteristics[0]
        assert char.name == "EngSpeed"
        assert char.lower_limit == 0.0
        assert char.upper_limit == 8000.0

    def test_limits_same_line(self, parser):
        result = parser.parse_string(A2L_LIMITS_SAME_LINE)
        assert result.success
        assert len(result.data.characteristics) == 1
        char = result.data.characteristics[0]
        assert char.lower_limit == 0.0
        assert char.upper_limit == 100.0

    def test_no_limits(self, parser):
        result = parser.parse_string(A2L_NO_LIMITS)
        assert result.success
        assert len(result.data.characteristics) == 1
        assert result.data.characteristics[0].lower_limit == 0.0
        assert result.data.characteristics[0].upper_limit == 0.0


# ── Controller import tests ───────────────────────────────────────────────────


class TestCalibImport:

    def test_load_a2l(self, controller, a2l_file):
        ok, errs = controller.load_a2l(a2l_file)
        assert ok
        assert controller.current_a2l is not None
        assert len(controller.current_a2l.characteristics) == 3

    def test_load_nonexistent(self, controller):
        ok, errs = controller.load_a2l(Path("/nonexistent.a2l"))
        assert not ok
        assert len(errs) > 0

    def test_import_without_load(self, controller):
        imported, skipped = controller.import_a2l_to_db()
        assert imported == 0
        assert skipped == 0

    def test_import_creates_records(self, controller, a2l_file):
        controller.load_a2l(a2l_file)
        imported, skipped = controller.import_a2l_to_db()
        assert imported == 3
        assert skipped == 0

    def test_import_records_have_names(self, controller, a2l_file):
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()
        params = controller.get_params()
        names = [p.name for p in params]
        assert "EngSpeed" in names
        assert "ThrottlePos" in names
        assert "BatteryVolt" in names

    def test_import_records_have_values(self, controller, a2l_file):
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()
        p = controller.get_param_by_name("EngSpeed")
        assert p is not None
        assert p.data_type == "VALUE"
        assert p.unit == "rpm"
        assert p.min_value == 0.0
        assert p.max_value == 8000.0

    def test_import_source_field(self, controller, a2l_file):
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()
        p = controller.get_param_by_name("EngSpeed")
        assert p.source == "a2l"

    def test_import_skip_duplicates(self, controller, a2l_file):
        controller.load_a2l(a2l_file)
        imported1, skipped1 = controller.import_a2l_to_db()
        imported2, skipped2 = controller.import_a2l_to_db()
        assert imported1 == 3
        assert skipped1 == 0
        assert imported2 == 0
        assert skipped2 == 3

    def test_import_inline_format(self, controller, tmp_path):
        f = tmp_path / "inline.a2l"
        f.write_text(A2L_INLINE, encoding="utf-8")
        controller.load_a2l(f)
        imported, skipped = controller.import_a2l_to_db()
        assert imported == 2
        assert skipped == 0

    def test_import_multi_line_limits(self, controller, tmp_path):
        f = tmp_path / "multiline.a2l"
        f.write_text(A2L_MULTI_LINE, encoding="utf-8")
        controller.load_a2l(f)
        imported, skipped = controller.import_a2l_to_db()
        assert imported == 1
        p = controller.get_param_by_name("EngSpeed")
        assert p is not None
        assert p.max_value == 8000.0


# ── Full pipeline (file → parse → import → DB) ──────────────────────────────


class TestFullPipeline:

    def test_file_to_db_pipeline(self, controller, a2l_file):
        """Full pipeline: parse A2L file, import to DB, verify records."""
        ok, _ = controller.load_a2l(a2l_file)
        assert ok

        imported, skipped = controller.import_a2l_to_db()
        assert imported == 3

        params = controller.get_params()
        assert len(params) == 3

        # Verify each parameter
        for p in params:
            assert p.name
            assert p.data_type
            assert p.source == "a2l"
            assert p.source_file

    def test_pipeline_with_groups(self, controller, a2l_file):
        """After import, group management should work."""
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()

        # All params start without a group
        groups = controller.get_groups()
        assert len(groups) == 0

        # Assign a group
        p = controller.get_param_by_name("EngSpeed")
        controller.update_param(p.id, group_name="Engine")
        groups = controller.get_groups()
        assert "Engine" in groups

    def test_pipeline_search(self, controller, a2l_file):
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()
        results = controller.search_params("Engine")
        assert len(results) >= 1
        assert any(p.name == "EngSpeed" for p in results)

    def test_pipeline_validation(self, controller, a2l_file):
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()
        issues = controller.validate()
        # All params have no group → info issues
        assert any(i["rule"] == "CAL_NO_GROUP" for i in issues)

    def test_pipeline_export_json(self, controller, a2l_file, tmp_path):
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()
        out = tmp_path / "export.json"
        ok, errs = controller.export_json(out)
        assert ok
        assert out.exists()
        import json
        data = json.loads(out.read_text(encoding="utf-8"))
        assert len(data["parameters"]) == 3


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestCalibImportEdgeCases:

    def test_empty_a2l(self, controller, tmp_path):
        f = tmp_path / "empty.a2l"
        f.write_text("/begin PROJECT X \"Y\" /end PROJECT", encoding="utf-8")
        controller.load_a2l(f)
        imported, skipped = controller.import_a2l_to_db()
        assert imported == 0

    def test_malformed_a2l(self, controller, tmp_path):
        f = tmp_path / "bad.a2l"
        f.write_text("not an A2L file at all", encoding="utf-8")
        ok, errs = controller.load_a2l(f)
        # Parser should handle gracefully (success=True, empty data)
        if ok:
            imported, skipped = controller.import_a2l_to_db()
            assert imported == 0

    def test_no_quotes_format(self, controller, tmp_path):
        """A2L without quoted long_identifier should still import."""
        content = """/begin CHARACTERISTIC
    Param1 VALUE 0x1000 RL1
    UNIT "V"
    LOWER_LIMIT 0.0 UPPER_LIMIT 100.0
/end CHARACTERISTIC
"""
        f = tmp_path / "noquotes.a2l"
        f.write_text(content, encoding="utf-8")
        controller.load_a2l(f)
        imported, skipped = controller.import_a2l_to_db()
        assert imported == 1
        p = controller.get_param_by_name("Param1")
        assert p is not None
        assert p.data_type == "VALUE"

    def test_name_on_own_line(self, controller, tmp_path):
        """A2L with name on its own line should still import."""
        content = """/begin CHARACTERISTIC
    Param1
    "Description" VALUE 0x1000 RL1
    LOWER_LIMIT 0.0 UPPER_LIMIT 100.0
/end CHARACTERISTIC
"""
        f = tmp_path / "multiline_name.a2l"
        f.write_text(content, encoding="utf-8")
        controller.load_a2l(f)
        imported, skipped = controller.import_a2l_to_db()
        assert imported == 1
        p = controller.get_param_by_name("Param1")
        assert p is not None


# ── Writeback tests ──────────────────────────────────────────────────────────


class TestWritebackA2L:

    A2L_CONTENT = """/begin CHARACTERISTIC
 Param1
 "Param One"
 VALUE
 0x1000
 Default_RL
 0
 CM_Identical
 0.0
 100.0
/end CHARACTERISTIC
/begin CHARACTERISTIC
 Param2
 "Param Two"
 VALUE
 0x2000
 Default_RL
 0
 CM_Identical
 -50.0
 50.0
 UNIT "V"
 LOWER_LIMIT -50.0 UPPER_LIMIT 50.0
/end CHARACTERISTIC
"""

    def test_writeback_no_a2l_loaded(self, controller):
        ok, errs = controller.writeback_a2l()
        assert not ok
        assert "未加载" in errs[0]

    def test_writeback_updates_limits(self, controller, tmp_path):
        a2l = tmp_path / "test.a2l"
        a2l.write_text(self.A2L_CONTENT, encoding="utf-8")
        controller.load_a2l(a2l)
        controller.import_a2l_to_db()

        # Modify Param1's limits in DB
        p = controller.get_param_by_name("Param1")
        controller.update_param(p.id, min_value=10.0, max_value=200.0)

        # Writeback
        out = tmp_path / "out.a2l"
        ok, errs = controller.writeback_a2l(out)
        assert ok
        content = out.read_text(encoding="utf-8")
        assert "10" in content
        assert "200" in content

    def test_writeback_preserves_structure(self, controller, tmp_path):
        a2l = tmp_path / "test.a2l"
        a2l.write_text(self.A2L_CONTENT, encoding="utf-8")
        controller.load_a2l(a2l)
        controller.import_a2l_to_db()

        out = tmp_path / "out.a2l"
        ok, _ = controller.writeback_a2l(out)
        assert ok
        content = out.read_text(encoding="utf-8")
        assert "/begin CHARACTERISTIC" in content
        assert "/end CHARACTERISTIC" in content
        assert "Param1" in content
        assert "Param2" in content

    def test_writeback_only_modified_params(self, controller, tmp_path):
        a2l = tmp_path / "test.a2l"
        a2l.write_text(self.A2L_CONTENT, encoding="utf-8")
        controller.load_a2l(a2l)
        controller.import_a2l_to_db()

        # Only modify Param1
        p1 = controller.get_param_by_name("Param1")
        controller.update_param(p1.id, max_value=999.0)

        out = tmp_path / "out.a2l"
        ok, _ = controller.writeback_a2l(out)
        assert ok
        content = out.read_text(encoding="utf-8")
        # Param2 should keep original values
        assert "-50" in content

    def test_writeback_overwrites_original(self, controller, tmp_path):
        a2l = tmp_path / "test.a2l"
        a2l.write_text(self.A2L_CONTENT, encoding="utf-8")
        controller.load_a2l(a2l)
        controller.import_a2l_to_db()

        p = controller.get_param_by_name("Param1")
        controller.update_param(p.id, max_value=555.0)

        ok, _ = controller.writeback_a2l()  # overwrite
        assert ok
        content = a2l.read_text(encoding="utf-8")
        assert "555" in content

    def test_writeback_no_db_params(self, controller, tmp_path):
        a2l = tmp_path / "test.a2l"
        a2l.write_text(self.A2L_CONTENT, encoding="utf-8")
        controller.load_a2l(a2l)
        # Don't import — no DB params

        out = tmp_path / "out.a2l"
        ok, errs = controller.writeback_a2l(out)
        assert not ok
        assert "没有" in errs[0]


# ── Page management tests ───────────────────────────────────────────────────


class TestCalibrationPage:

    def test_list_pages_default(self, controller):
        """New database has only 'default' page."""
        pages = controller.list_pages()
        assert pages == ["default"]

    def test_create_page(self, controller):
        """Creating a page makes it appear in list_pages."""
        assert controller.create_page("v2")
        pages = controller.list_pages()
        assert "v2" in pages

    def test_create_duplicate_page(self, controller):
        """Creating a duplicate page name returns False."""
        controller.create_page("v2")
        assert not controller.create_page("v2")

    def test_create_empty_name(self, controller):
        """Creating a page with empty name returns False."""
        assert not controller.create_page("")

    def test_import_to_new_page(self, controller, a2l_file):
        """Import to a new page, default page stays empty."""
        controller.load_a2l(a2l_file)
        controller.set_current_page("v2")
        imported, skipped = controller.import_a2l_to_db()
        assert imported == 3

        # v2 page has 3 params
        params = controller.get_params()
        assert len(params) == 3

        # default page has 0 params
        controller.set_current_page("default")
        params = controller.get_params()
        assert len(params) == 0

    def test_switch_page(self, controller, a2l_file):
        """Switching pages returns correct data."""
        controller.load_a2l(a2l_file)

        # Import to default
        controller.import_a2l_to_db()

        # Import to v2
        controller.set_current_page("v2")
        controller.import_a2l_to_db()

        # Switch back to default
        controller.set_current_page("default")
        assert len(controller.get_params()) == 3

        # Switch to v2
        controller.set_current_page("v2")
        assert len(controller.get_params()) == 3

    def test_delete_page(self, controller, a2l_file):
        """Deleting a page removes its parameters."""
        controller.load_a2l(a2l_file)
        controller.set_current_page("v2")
        controller.import_a2l_to_db()
        assert len(controller.get_params()) == 3

        ok, msg = controller.delete_page("v2")
        assert ok
        assert "3" in msg

        # After deletion, current page falls back to default
        assert controller.get_current_page() == "default"
        assert len(controller.get_params()) == 0

    def test_delete_default_page_rejected(self, controller):
        """Cannot delete the default page."""
        ok, msg = controller.delete_page("default")
        assert not ok
        assert "不能删除" in msg

    def test_same_name_different_pages(self, controller, a2l_file):
        """Same parameter name can exist in different pages."""
        controller.load_a2l(a2l_file)

        # Import to default
        controller.import_a2l_to_db()

        # Import to v2 (same parameters)
        controller.set_current_page("v2")
        imported, skipped = controller.import_a2l_to_db()
        assert imported == 3
        assert skipped == 0

        # Both pages have EngSpeed
        controller.set_current_page("default")
        assert controller.get_param_by_name("EngSpeed") is not None

        controller.set_current_page("v2")
        assert controller.get_param_by_name("EngSpeed") is not None

    def test_search_filtered_by_page(self, controller, a2l_file):
        """Search only returns results from current page."""
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()

        controller.set_current_page("v2")
        controller.import_a2l_to_db()

        # Search in v2
        results = controller.search_params("Engine")
        assert len(results) >= 1
        for p in results:
            assert p.calibration_page == "v2"

        # Search in default
        controller.set_current_page("default")
        results = controller.search_params("Engine")
        assert len(results) >= 1
        for p in results:
            assert p.calibration_page == "default"

    def test_groups_filtered_by_page(self, controller, a2l_file):
        """Groups are per-page."""
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()

        # Assign group in default
        p = controller.get_param_by_name("EngSpeed")
        controller.update_param(p.id, group_name="Engine")

        # v2 has no groups
        controller.set_current_page("v2")
        controller.import_a2l_to_db()
        assert controller.get_groups() == []

        # default has the group
        controller.set_current_page("default")
        assert "Engine" in controller.get_groups()
