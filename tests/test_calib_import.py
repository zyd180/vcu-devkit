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
