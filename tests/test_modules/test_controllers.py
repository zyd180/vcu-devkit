"""Controller integration tests — covers data access, edit, save, export paths."""

from pathlib import Path

import pytest

from core.parsers.dbc_parser import DBCParser, SignalDef

# ── Helper to build DBCData from sample ──────────────────────────────────────


@pytest.fixture
def sample_dbc_data(sample_dbc_file):
    parser = DBCParser()
    result = parser.parse(sample_dbc_file)
    return result.data


@pytest.fixture
def can_ctrl(sample_dbc_file, sample_dbc_data):
    from modules.can_builder.controller import CANBuilderController

    ctrl = CANBuilderController()
    ctrl.current_dbc = sample_dbc_data
    ctrl.current_path = sample_dbc_file
    return ctrl


@pytest.fixture
def calib_ctrl(db_manager):
    from modules.calib_manager.controller import CalibManagerController

    return CalibManagerController(db_manager=db_manager)


@pytest.fixture
def test_gen_ctrl(sample_dbc_file, sample_dbc_data):
    from modules.test_generator.controller import TestGeneratorController

    ctrl = TestGeneratorController()
    ctrl.current_dbc = sample_dbc_data
    return ctrl


# ── CAN Builder Controller ───────────────────────────────────────────────────


class TestCANBuilderController:
    def test_get_messages(self, can_ctrl):
        msgs = can_ctrl.get_messages()
        assert len(msgs) == 3
        names = {m.name for m in msgs}
        assert "VCU_Status" in names

    def test_get_message_by_name(self, can_ctrl):
        msg = can_ctrl.get_message_by_name("VCU_Status")
        assert msg is not None
        assert msg.id == 256

    def test_get_message_by_name_not_found(self, can_ctrl):
        assert can_ctrl.get_message_by_name("NonExistent") is None

    def test_get_signals_for_message(self, can_ctrl):
        sigs = can_ctrl.get_signals_for_message("VCU_Status")
        assert len(sigs) == 4
        names = {s.name for s in sigs}
        assert "VCU_PowerMode" in names

    def test_get_signals_for_missing_message(self, can_ctrl):
        assert can_ctrl.get_signals_for_message("NonExistent") == []

    def test_get_signal_as_dict(self, can_ctrl):
        d = can_ctrl.get_signal_as_dict("VCU_Status", "VCU_PowerMode")
        assert d is not None
        assert d["name"] == "VCU_PowerMode"
        assert d["bit_length"] == 4
        assert "BMS" in d["receivers"]

    def test_get_signal_as_dict_not_found(self, can_ctrl):
        assert can_ctrl.get_signal_as_dict("VCU_Status", "NonExistent") is None

    def test_update_signal(self, can_ctrl):
        assert can_ctrl.update_signal("VCU_Status", "VCU_PowerMode", comment="updated")
        sig = can_ctrl.get_signal_as_dict("VCU_Status", "VCU_PowerMode")
        assert sig["comment"] == "updated"

    def test_update_signal_receivers_string(self, can_ctrl):
        assert can_ctrl.update_signal("VCU_Status", "VCU_PowerMode", receivers="A,B,C")
        sig = can_ctrl.get_signal_as_dict("VCU_Status", "VCU_PowerMode")
        assert "A, B, C" in sig["receivers"]

    def test_update_signal_missing(self, can_ctrl):
        assert not can_ctrl.update_signal("NonExistent", "S", comment="x")

    def test_add_signal(self, can_ctrl):
        new_sig = SignalDef(
            name="NewSignal",
            start_bit=32,
            bit_length=8,
            byte_order="little_endian",
            value_type="unsigned",
            factor=1.0,
            offset=0.0,
            minimum=0.0,
            maximum=255.0,
            unit="",
            comment="",
            receivers=[],
            value_descriptions={},
            mux=None,
        )
        assert can_ctrl.add_signal("VCU_Status", new_sig)
        assert can_ctrl.get_signal_as_dict("VCU_Status", "NewSignal") is not None

    def test_add_signal_duplicate_name(self, can_ctrl):
        dup = SignalDef(
            name="VCU_PowerMode",
            start_bit=48,
            bit_length=8,
            byte_order="little_endian",
            value_type="unsigned",
            factor=1.0,
            offset=0.0,
            minimum=0.0,
            maximum=255.0,
            unit="",
            comment="",
            receivers=[],
            value_descriptions={},
            mux=None,
        )
        assert not can_ctrl.add_signal("VCU_Status", dup)

    def test_add_signal_missing_msg(self, can_ctrl):
        sig = SignalDef(
            name="X",
            start_bit=0,
            bit_length=8,
            byte_order="little_endian",
            value_type="unsigned",
            factor=1.0,
            offset=0.0,
            minimum=0.0,
            maximum=255.0,
            unit="",
            comment="",
            receivers=[],
            value_descriptions={},
            mux=None,
        )
        assert not can_ctrl.add_signal("NonExistent", sig)

    def test_remove_signal(self, can_ctrl):
        assert can_ctrl.remove_signal("VCU_Status", "VCU_ErrCode")
        assert can_ctrl.get_signal_as_dict("VCU_Status", "VCU_ErrCode") is None

    def test_remove_signal_missing(self, can_ctrl):
        assert not can_ctrl.remove_signal("VCU_Status", "NonExistent")

    def test_remove_signal_missing_msg(self, can_ctrl):
        assert not can_ctrl.remove_signal("NonExistent", "S")

    def test_validate(self, can_ctrl):
        results = can_ctrl.validate()
        assert isinstance(results, list)

    def test_validate_no_data(self):
        from modules.can_builder.controller import CANBuilderController

        ctrl = CANBuilderController()
        assert ctrl.validate() == []

    def test_save_dbc(self, can_ctrl, tmp_path):
        out = tmp_path / "output.dbc"
        success, errors = can_ctrl.save_dbc(out)
        assert success
        assert not errors
        assert out.exists()
        # Verify round-trip
        parser = DBCParser()
        result = parser.parse(out)
        assert result.success
        assert len(result.data.messages) == 3

    def test_save_dbc_no_data(self):
        from modules.can_builder.controller import CANBuilderController

        ctrl = CANBuilderController()
        success, errors = ctrl.save_dbc(Path("x.dbc"))
        assert not success
        assert "No DBC loaded" in errors[0]

    def test_save_dbc_no_path(self, can_ctrl):
        can_ctrl.current_path = None
        success, errors = can_ctrl.save_dbc()
        assert not success

    def test_save_json_snapshot(self, can_ctrl, tmp_path):
        out = tmp_path / "snapshot.json"
        success, errors = can_ctrl.save_json_snapshot(out)
        assert success
        assert out.exists()

    def test_save_json_snapshot_no_data(self):
        from modules.can_builder.controller import CANBuilderController

        ctrl = CANBuilderController()
        success, errors = ctrl.save_json_snapshot(Path("x.json"))
        assert not success

    def test_compare_with(self, can_ctrl, sample_dbc_file):
        result = can_ctrl.compare_with(sample_dbc_file)
        assert result is not None
        assert result.summary["messages_added"] == 0

    def test_compare_with_no_data(self):
        from modules.can_builder.controller import CANBuilderController

        ctrl = CANBuilderController()
        assert ctrl.compare_with(Path("x.dbc")) is None

    def test_generate_code(self, can_ctrl, tmp_path):
        success, errors = can_ctrl.generate_code(tmp_path)
        assert success
        assert not errors

    def test_generate_code_no_data(self):
        from modules.can_builder.controller import CANBuilderController

        ctrl = CANBuilderController()
        success, errors = ctrl.generate_code(Path("x"))
        assert not success

    def test_load_dbc(self, sample_dbc_file):
        from modules.can_builder.controller import CANBuilderController

        ctrl = CANBuilderController()
        success, errors = ctrl.load_dbc(sample_dbc_file)
        assert success
        assert ctrl.current_dbc is not None

    def test_load_dbc_nonexistent(self):
        from modules.can_builder.controller import CANBuilderController

        ctrl = CANBuilderController()
        success, errors = ctrl.load_dbc(Path("nonexistent.dbc"))
        assert not success


# ── Calib Manager Controller ─────────────────────────────────────────────────


class TestCalibManagerController:
    def test_get_params_empty(self, calib_ctrl):
        params = calib_ctrl.get_params()
        assert params == []

    def test_add_param(self, calib_ctrl):
        p = calib_ctrl.add_param("TestParam", data_type="VALUE", default_value=0.0)
        assert p is not None
        assert p.name == "TestParam"

    def test_get_param_by_name(self, calib_ctrl):
        calib_ctrl.add_param("Lookup")
        p = calib_ctrl.get_param_by_name("Lookup")
        assert p is not None

    def test_get_param_by_name_not_found(self, calib_ctrl):
        assert calib_ctrl.get_param_by_name("NonExistent") is None

    def test_update_param(self, calib_ctrl):
        p = calib_ctrl.add_param("ToUpdate")
        assert calib_ctrl.update_param(p.id, default_value=42.0)

    def test_update_param_not_found(self, calib_ctrl):
        assert not calib_ctrl.update_param(99999, default_value=1.0)

    def test_delete_by_id(self, calib_ctrl):
        p = calib_ctrl.add_param("ToDelete")
        assert calib_ctrl.delete_by_id(p.id)
        assert calib_ctrl.get_param_by_name("ToDelete") is None

    def test_delete_by_id_not_found(self, calib_ctrl):
        assert not calib_ctrl.delete_by_id(99999)

    def test_export_json(self, calib_ctrl, tmp_path):
        calib_ctrl.add_param("P1")
        out = tmp_path / "cal.json"
        success, errors = calib_ctrl.export_json(out)
        assert success
        assert out.exists()

    def test_export_json_empty(self, calib_ctrl, tmp_path):
        out = tmp_path / "empty.json"
        success, errors = calib_ctrl.export_json(out)
        assert success


# ── Test Generator Controller ────────────────────────────────────────────────


class TestTestGeneratorController:
    def test_get_test_cases_empty(self, test_gen_ctrl):
        assert test_gen_ctrl.get_test_cases() == []

    def test_generate_signal_tests(self, test_gen_ctrl):
        count = test_gen_ctrl.generate_signal_tests()
        assert count > 0
        assert len(test_gen_ctrl.get_test_cases()) == count

    def test_get_cases_by_category(self, test_gen_ctrl):
        test_gen_ctrl.generate_signal_tests()
        cats = test_gen_ctrl.get_cases_by_category()
        assert len(cats) > 0

    def test_get_cases_by_message(self, test_gen_ctrl):
        test_gen_ctrl.generate_signal_tests()
        msgs = test_gen_ctrl.get_cases_by_message()
        assert len(msgs) > 0

    def test_export_excel(self, test_gen_ctrl, tmp_path):
        test_gen_ctrl.generate_signal_tests()
        out = tmp_path / "tests.xlsx"
        success, errors = test_gen_ctrl.export_excel(out)
        assert success
        assert out.exists()

    def test_export_json(self, test_gen_ctrl, tmp_path):
        test_gen_ctrl.generate_signal_tests()
        out = tmp_path / "tests.json"
        success, errors = test_gen_ctrl.export_json(out)
        assert success
        assert out.exists()

    def test_get_coverage(self, test_gen_ctrl):
        test_gen_ctrl.generate_signal_tests()
        coverage = test_gen_ctrl.get_coverage()
        assert isinstance(coverage, dict)
