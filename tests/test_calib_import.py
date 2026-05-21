"""Tests for A2L → calibration DB import pipeline."""

from pathlib import Path

import pytest

from core.db.manager import DatabaseManager
from core.generators.dcm_generator import DCMGenerator
from core.parsers.a2l_parser import A2LParser
from core.parsers.dcm_parser import DCMParser
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
        f.write_text('/begin PROJECT X "Y" /end PROJECT', encoding="utf-8")
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


# ── DCM content fixtures ─────────────────────────────────────────────────────

DCM_BASIC = """\
/begin PROJECT VCU_Calibration "VCU Calibration Data"
  /begin HEADER "DCM Export"
    VERSION "1.0"
  /end HEADER

  /begin MODULE VCU_Module "VCU"

    /begin CHARACTERISTIC
      EngSpeed "Engine Speed" VALUE 0x1000 Default_RL 0 CM_Identical
      0
      8000
      VALUE = 1500
    /end CHARACTERISTIC

    /begin CHARACTERISTIC
      ThrottlePos "Throttle Position" VALUE 0x1004 Default_RL 0 CM_Identical
      0
      100
      VALUE = 15.5
    /end CHARACTERISTIC

    /begin CHARACTERISTIC
      BatteryVolt "Battery Voltage" VALUE 0x1008 Default_RL 0 CM_Identical
      0
      18
      VALUE = 12.6
    /end CHARACTERISTIC

  /end MODULE
/end PROJECT
"""

DCM_EXTRA = """\
/begin PROJECT VCU_Calibration "VCU Calibration Data"
  /begin HEADER "DCM Export"
    VERSION "1.0"
  /end HEADER

  /begin MODULE VCU_Module "VCU"

    /begin CHARACTERISTIC
      EngSpeed "Engine Speed" VALUE 0x1000 Default_RL 0 CM_Identical
      0
      8000
      VALUE = 2000
    /end CHARACTERISTIC

    /begin CHARACTERISTIC
      NewParam "New Parameter" VALUE 0x2000 Default_RL 0 CM_Identical
      0
      100
      VALUE = 50
    /end CHARACTERISTIC

  /end MODULE
/end PROJECT
"""


# ── DCM tests ────────────────────────────────────────────────────────────────


class TestDCMParser:
    def test_parse_dcm_basic(self):
        parser = DCMParser()
        result = parser.parse_string(DCM_BASIC)
        assert result.success
        assert len(result.data.characteristics) == 3

    def test_parse_dcm_names(self):
        parser = DCMParser()
        result = parser.parse_string(DCM_BASIC)
        names = [c.name for c in result.data.characteristics]
        assert "EngSpeed" in names
        assert "ThrottlePos" in names
        assert "BatteryVolt" in names

    def test_parse_dcm_values(self):
        parser = DCMParser()
        result = parser.parse_string(DCM_BASIC)
        eng = next(c for c in result.data.characteristics if c.name == "EngSpeed")
        assert eng.value == 1500.0

    def test_parse_dcm_limits(self):
        parser = DCMParser()
        result = parser.parse_string(DCM_BASIC)
        eng = next(c for c in result.data.characteristics if c.name == "EngSpeed")
        assert eng.lower_limit == 0.0
        assert eng.upper_limit == 8000.0

    def test_parse_dcm_description(self):
        parser = DCMParser()
        result = parser.parse_string(DCM_BASIC)
        eng = next(c for c in result.data.characteristics if c.name == "EngSpeed")
        assert "Engine" in eng.description

    def test_parse_dcm_file(self, tmp_path):
        f = tmp_path / "test.dcm"
        f.write_text(DCM_BASIC, encoding="utf-8")
        parser = DCMParser()
        result = parser.parse(f)
        assert result.success
        assert len(result.data.characteristics) == 3

    def test_parse_dcm_nonexistent(self):
        parser = DCMParser()
        result = parser.parse(Path("/nonexistent.dcm"))
        assert not result.success

    def test_parse_dcm_empty(self):
        parser = DCMParser()
        result = parser.parse_string("not a dcm file")
        assert result.success  # parser returns empty, not error
        assert len(result.data.characteristics) == 0

    def test_parse_dcm_float_value(self):
        parser = DCMParser()
        result = parser.parse_string(DCM_BASIC)
        throttle = next(c for c in result.data.characteristics if c.name == "ThrottlePos")
        assert throttle.value == 15.5


class TestDCMGenerator:
    def test_generate_basic(self, tmp_path):
        gen = DCMGenerator()
        params = [
            {
                "name": "EngSpeed",
                "description": "Engine Speed",
                "default_value": 1500,
                "min_value": 0,
                "max_value": 8000,
                "unit": "rpm",
            },
        ]
        out = tmp_path / "out.dcm"
        result = gen.generate(params, out)
        assert result.success
        assert out.exists()

    def test_generate_content(self):
        gen = DCMGenerator()
        params = [
            {
                "name": "EngSpeed",
                "description": "Engine Speed",
                "default_value": 1500,
                "min_value": 0,
                "max_value": 8000,
                "unit": "rpm",
            },
        ]
        content = gen.generate_string(params)
        assert "EngSpeed" in content
        assert "VALUE = 1500" in content
        assert "/begin CHARACTERISTIC" in content

    def test_generate_with_unit(self):
        gen = DCMGenerator()
        params = [
            {
                "name": "BatteryVolt",
                "description": "Battery Voltage",
                "default_value": 12.6,
                "min_value": 0,
                "max_value": 18,
                "unit": "V",
            },
        ]
        content = gen.generate_string(params)
        assert 'UNIT "V"' in content

    def test_generate_roundtrip(self, tmp_path):
        """Generate DCM, parse it back, values should match."""
        gen = DCMGenerator()
        params = [
            {
                "name": "Param1",
                "description": "Test Param",
                "default_value": 42.5,
                "min_value": 0,
                "max_value": 100,
                "unit": "",
            },
        ]
        out = tmp_path / "roundtrip.dcm"
        gen.generate(params, out)

        parser = DCMParser()
        result = parser.parse(out)
        assert result.success
        assert len(result.data.characteristics) == 1
        assert result.data.characteristics[0].name == "Param1"
        assert result.data.characteristics[0].value == 42.5


class TestDCMController:
    def test_load_dcm(self, controller, tmp_path):
        f = tmp_path / "test.dcm"
        f.write_text(DCM_BASIC, encoding="utf-8")
        ok, errs = controller.load_dcm(f)
        assert ok
        assert controller.current_dcm is not None
        assert len(controller.current_dcm.characteristics) == 3

    def test_load_dcm_nonexistent(self, controller):
        ok, errs = controller.load_dcm(Path("/nonexistent.dcm"))
        assert not ok

    def test_import_dcm_values_to_existing(self, controller, a2l_file, tmp_path):
        """Import A2L first, then import DCM values."""
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()

        dcm_file = tmp_path / "test.dcm"
        dcm_file.write_text(DCM_BASIC, encoding="utf-8")
        controller.load_dcm(dcm_file)

        matched, updated, not_found = controller.import_dcm_values()
        assert matched == 3
        assert updated == 3
        assert not_found == 0

        eng = controller.get_param_by_name("EngSpeed")
        assert eng.default_value == 1500.0

    def test_import_dcm_values_partial_match(self, controller, a2l_file, tmp_path):
        """DCM has extra params not in DB."""
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()

        dcm_file = tmp_path / "extra.dcm"
        dcm_file.write_text(DCM_EXTRA, encoding="utf-8")
        controller.load_dcm(dcm_file)

        matched, updated, not_found = controller.import_dcm_values()
        assert matched == 1  # EngSpeed
        assert not_found == 1  # NewParam

    def test_import_dcm_values_no_dcm_loaded(self, controller):
        matched, updated, not_found = controller.import_dcm_values()
        assert matched == 0

    def test_import_dcm_as_new(self, controller, tmp_path):
        """Import DCM as new records without A2L."""
        f = tmp_path / "test.dcm"
        f.write_text(DCM_BASIC, encoding="utf-8")
        controller.load_dcm(f)

        imported, skipped = controller.import_dcm_as_new()
        assert imported == 3
        assert skipped == 0

        params = controller.get_params()
        assert len(params) == 3

    def test_import_dcm_as_new_skip_existing(self, controller, a2l_file, tmp_path):
        """Duplicated names are skipped."""
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()

        dcm_file = tmp_path / "test.dcm"
        dcm_file.write_text(DCM_BASIC, encoding="utf-8")
        controller.load_dcm(dcm_file)

        imported, skipped = controller.import_dcm_as_new()
        assert imported == 0
        assert skipped == 3

    def test_export_dcm(self, controller, a2l_file, tmp_path):
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()

        out = tmp_path / "export.dcm"
        ok, errs = controller.export_dcm(out)
        assert ok
        assert out.exists()

        # Verify exported DCM can be parsed back
        parser = DCMParser()
        result = parser.parse(out)
        assert result.success
        assert len(result.data.characteristics) == 3

    def test_export_dcm_values_match_db(self, controller, a2l_file, tmp_path):
        """Exported DCM values should match DB values."""
        controller.load_a2l(a2l_file)
        controller.import_a2l_to_db()

        # Modify a value
        p = controller.get_param_by_name("EngSpeed")
        controller.update_param(p.id, default_value=2500.0, changed_by="test", reason="test")

        out = tmp_path / "export.dcm"
        controller.export_dcm(out)

        parser = DCMParser()
        result = parser.parse(out)
        eng = next(c for c in result.data.characteristics if c.name == "EngSpeed")
        assert eng.value == 2500.0

    def test_a2l_then_dcm_pipeline(self, controller, a2l_file, tmp_path):
        """Full pipeline: A2L defines structure, DCM fills values."""
        # Step 1: Load A2L and import structure
        controller.load_a2l(a2l_file)
        imported, _ = controller.import_a2l_to_db()
        assert imported == 3

        # Verify A2L default values (lower_limit)
        eng = controller.get_param_by_name("EngSpeed")
        assert eng.default_value == 0.0

        # Step 2: Load DCM and import values
        dcm_file = tmp_path / "values.dcm"
        dcm_file.write_text(DCM_BASIC, encoding="utf-8")
        controller.load_dcm(dcm_file)
        matched, updated, _ = controller.import_dcm_values()
        assert matched == 3
        assert updated == 3

        # Step 3: Verify values updated
        eng = controller.get_param_by_name("EngSpeed")
        assert eng.default_value == 1500.0

        # Step 4: Export DCM with updated values
        out = tmp_path / "roundtrip.dcm"
        ok, _ = controller.export_dcm(out)
        assert ok

        parser = DCMParser()
        result = parser.parse(out)
        eng_dcm = next(c for c in result.data.characteristics if c.name == "EngSpeed")
        assert eng_dcm.value == 1500.0
