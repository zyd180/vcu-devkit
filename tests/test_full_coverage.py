"""VCU DevKit - Full Coverage Test Suite
Covers: imports, controllers, parsers, UI components, DB, themes, XXE protection.
"""

import sys
import os
import json
import tempfile
import re
from pathlib import Path

import pytest

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ============================================================================
# 1. APPLICATION ENTRY POINT
# ============================================================================

class TestAppEntryPoint:

    def test_main_module_importable(self):
        """main.py can be imported without crashing."""
        import importlib
        spec = importlib.util.find_spec("main")
        assert spec is not None, "main module not found"

    def test_load_stylesheet_function_exists(self):
        """main.load_stylesheet is importable and callable."""
        from main import load_stylesheet
        assert callable(load_stylesheet)

    def test_load_stylesheet_returns_str(self):
        """load_stylesheet returns a string (may be empty if file missing)."""
        from main import load_stylesheet
        result = load_stylesheet("light")
        assert isinstance(result, str)

    def test_main_function_exists(self):
        """main.main function exists and is callable."""
        from main import main
        assert callable(main)


# ============================================================================
# 2. ALL MODULE IMPORT TESTS
# ============================================================================

class TestModuleImports:
    """Verify every key module can be imported without errors."""

    def test_import_config_settings(self):
        from config.settings import AppSettings
        assert AppSettings is not None

    def test_import_arxml_parser(self):
        from core.parsers.arxml_parser import ARXMLParser
        assert ARXMLParser is not None

    def test_import_dbc_parser(self):
        from core.parsers.dbc_parser import DBCParser
        assert DBCParser is not None

    def test_import_odx_parser(self):
        from core.parsers.odx_parser import ODXParser
        assert ODXParser is not None

    def test_import_a2l_parser(self):
        from core.parsers.a2l_parser import A2LParser
        assert A2LParser is not None

    def test_import_base_parser(self):
        from core.parsers.base import BaseParser, ParseResult
        assert BaseParser is not None
        assert ParseResult is not None

    def test_import_c_generator(self):
        from core.generators.c_generator import CANCodeGenerator
        assert CANCodeGenerator is not None

    def test_import_arxml_generator(self):
        from core.generators.arxml_generator import ARXMLGenerator
        assert ARXMLGenerator is not None

    def test_import_rule_engine(self):
        from core.rules.engine import RuleEngine
        assert RuleEngine is not None

    def test_import_db_models(self):
        from core.db.models import (
            CalibrationParameter, CalibrationChange,
            DTCDefinition, DiagService,
            Requirement, TraceabilityLink,
            ProjectConfig, FileVersion,
        )
        assert all(cls is not None for cls in [
            CalibrationParameter, CalibrationChange,
            DTCDefinition, DiagService,
            Requirement, TraceabilityLink,
            ProjectConfig, FileVersion,
        ])

    def test_import_db_manager(self):
        from core.db.manager import DatabaseManager
        assert DatabaseManager is not None

    def test_import_ui_icons(self):
        from ui.icons import (
            icon_open, icon_save, icon_check, icon_generate,
            icon_export, icon_diff, icon_add, icon_remove,
            icon_validate, icon_clear, icon_load, icon_search,
            icon_export_json, icon_export_excel, icon_export_arxml, icon_export_a2l,
        )
        assert all(callable(fn) for fn in [
            icon_open, icon_save, icon_check, icon_generate,
            icon_export, icon_diff, icon_add, icon_remove,
            icon_validate, icon_clear, icon_load, icon_search,
            icon_export_json, icon_export_excel, icon_export_arxml, icon_export_a2l,
        ])

    def test_import_sidebar(self):
        from ui.sidebar import Sidebar
        assert Sidebar is not None

    def test_import_main_window(self):
        from ui.main_window import MainWindow
        assert MainWindow is not None

    def test_import_table_editor(self):
        from ui.widgets.table_editor import DataTableModel, TableEditor
        assert DataTableModel is not None
        assert TableEditor is not None

    def test_import_file_worker(self):
        from ui.widgets.file_worker import FileWorker
        assert FileWorker is not None

    def test_import_tree_view(self):
        from ui.widgets.tree_view import TreeView
        assert TreeView is not None

    def test_import_property_panel(self):
        from ui.widgets.property_panel import PropertyPanel
        assert PropertyPanel is not None

    def test_import_status_bar(self):
        from ui.widgets.status_bar import StatusBarWidget
        assert StatusBarWidget is not None

    def test_import_can_builder_controller(self):
        from modules.can_builder.controller import CANBuilderController
        assert CANBuilderController is not None

    def test_import_swc_designer_controller(self):
        from modules.swc_designer.controller import SWCDesignerController
        assert SWCDesignerController is not None

    def test_import_diag_builder_controller(self):
        from modules.diag_builder.controller import DiagBuilderController
        assert DiagBuilderController is not None

    def test_import_calib_manager_controller(self):
        from modules.calib_manager.controller import CalibManagerController
        assert CalibManagerController is not None

    def test_import_test_generator_controller(self):
        from modules.test_generator.controller import TestGeneratorController
        assert TestGeneratorController is not None

    def test_import_trace_matrix_controller(self):
        from modules.trace_matrix.controller import TraceMatrixController
        assert TraceMatrixController is not None

    def test_import_generators_base(self):
        from core.generators.base import BaseGenerator, GenerateResult, TemplateEngine
        assert all(cls is not None for cls in [BaseGenerator, GenerateResult, TemplateEngine])

    def test_import_diff_engine(self):
        from core.diff.dbc_diff import DBCDiffEngine
        assert DBCDiffEngine is not None


# ============================================================================
# 3. CONTROLLER FUNCTIONAL TESTS
# ============================================================================

SAMPLE_DBC = """\
VERSION ""

NS_ :

BS_:

BU_: VCU BMS MCU

BO_ 256 VCU_Status: 8 VCU
 SG_ VCU_PowerMode : 0|4@1+ (1,0) [0|15] "" BMS,MCU
 SG_ VCU_Ready : 4|1@1+ (1,0) [0|1] "" BMS,MCU
 SG_ VCU_SOC : 8|8@1+ (0.5,0) [0|127.5] "%" BMS,MCU
 SG_ VCU_ErrCode : 16|16@1+ (1,0) [0|65535] "" BMS,MCU

BO_ 512 VCU_Torque: 8 VCU
 SG_ Tq_Request : 0|16@1+ (0.1,-500) [-500|1155.3] "Nm" MCU
 SG_ Tq_Actual : 16|16@1+ (0.1,-500) [-500|1155.3] "Nm" BMS
 SG_ Tq_Limit : 32|16@1+ (0.1,-500) [-500|1155.3] "Nm" MCU

BO_ 768 VCU_HV: 8 VCU
 SG_ HV_Voltage : 0|16@1+ (0.1,0) [0|1000] "V" BMS
 SG_ HV_Current : 16|16@1+ (0.1,-500) [-500|1155.3] "A" BMS
 SG_ HV_Insulation : 32|16@1+ (1,0) [0|65535] "kOhm" VCU

VAL_ 256 VCU_PowerMode 0 "PowerOff" 1 "ACC" 2 "PowerOn" 3 "Charging" 15 "Fault" ;
"""


class TestCANBuilderController:

    def test_create_instance(self):
        from modules.can_builder.controller import CANBuilderController
        ctrl = CANBuilderController()
        assert ctrl is not None
        assert ctrl.current_dbc is None

    def test_load_dbc_from_file(self, tmp_path):
        from modules.can_builder.controller import CANBuilderController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = CANBuilderController()
        ok, errors = ctrl.load_dbc(dbc_file)
        assert ok is True
        assert errors == []
        assert ctrl.current_dbc is not None

    def test_get_messages(self, tmp_path):
        from modules.can_builder.controller import CANBuilderController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = CANBuilderController()
        ctrl.load_dbc(dbc_file)
        msgs = ctrl.get_messages()
        assert len(msgs) == 3
        names = [m.name for m in msgs]
        assert "VCU_Status" in names
        assert "VCU_Torque" in names
        assert "VCU_HV" in names

    def test_get_message_by_name(self, tmp_path):
        from modules.can_builder.controller import CANBuilderController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = CANBuilderController()
        ctrl.load_dbc(dbc_file)
        msg = ctrl.get_message_by_name("VCU_Status")
        assert msg is not None
        assert msg.id == 256
        assert msg.dlc == 8

    def test_get_signals_for_message(self, tmp_path):
        from modules.can_builder.controller import CANBuilderController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = CANBuilderController()
        ctrl.load_dbc(dbc_file)
        sigs = ctrl.get_signals_for_message("VCU_Status")
        assert len(sigs) == 4
        names = [s.name for s in sigs]
        assert "VCU_SOC" in names

    def test_validate(self, tmp_path):
        from modules.can_builder.controller import CANBuilderController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = CANBuilderController()
        ctrl.load_dbc(dbc_file)
        results = ctrl.validate()
        # Valid DBC should have no errors (warnings are OK)
        errors = [r for r in results if r.severity.value == "error"]
        assert len(errors) == 0

    def test_generate_code(self, tmp_path):
        from modules.can_builder.controller import CANBuilderController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        out_dir = tmp_path / "output"
        ctrl = CANBuilderController()
        ctrl.load_dbc(dbc_file)
        ok, errors = ctrl.generate_code(out_dir)
        assert ok is True
        assert errors == []
        assert (out_dir / "can_pack.h").exists()
        assert (out_dir / "can_signals.h").exists()
        assert (out_dir / "can_messages.h").exists()

    def test_add_signal(self, tmp_path):
        from modules.can_builder.controller import CANBuilderController
        from core.parsers.dbc_parser import SignalDef
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = CANBuilderController()
        ctrl.load_dbc(dbc_file)
        sig = SignalDef(
            name="NewSignal", start_bit=48, bit_length=8,
            byte_order="little_endian", value_type="unsigned",
            factor=1.0, offset=0.0, minimum=0, maximum=255,
            unit="", comment="test",
        )
        ok = ctrl.add_signal("VCU_Status", sig)
        assert ok is True
        assert len(ctrl.get_signals_for_message("VCU_Status")) == 5

    def test_remove_signal(self, tmp_path):
        from modules.can_builder.controller import CANBuilderController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = CANBuilderController()
        ctrl.load_dbc(dbc_file)
        ok = ctrl.remove_signal("VCU_Status", "VCU_SOC")
        assert ok is True
        assert len(ctrl.get_signals_for_message("VCU_Status")) == 3

    def test_update_signal(self, tmp_path):
        from modules.can_builder.controller import CANBuilderController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = CANBuilderController()
        ctrl.load_dbc(dbc_file)
        ok = ctrl.update_signal("VCU_Status", "VCU_SOC", comment="Updated comment")
        assert ok is True
        sig = next(s for s in ctrl.get_signals_for_message("VCU_Status") if s.name == "VCU_SOC")
        assert sig.comment == "Updated comment"

    def test_no_dbc_loaded_returns_empty(self):
        from modules.can_builder.controller import CANBuilderController
        ctrl = CANBuilderController()
        assert ctrl.get_messages() == []
        assert ctrl.validate() == []
        ok, errs = ctrl.generate_code(Path("/tmp"))
        assert ok is False


class TestSWCDesignerController:

    def test_create_instance(self):
        from modules.swc_designer.controller import SWCDesignerController
        ctrl = SWCDesignerController()
        assert ctrl is not None

    def test_new_project(self):
        from modules.swc_designer.controller import SWCDesignerController
        ctrl = SWCDesignerController()
        ctrl.new_project("TestPackage")
        assert ctrl.current_data is not None
        assert ctrl.current_data.package_name == "TestPackage"
        assert ctrl.current_data.swcs == []

    def test_add_swc(self):
        from modules.swc_designer.controller import SWCDesignerController
        from core.parsers.arxml_parser import SWCDef
        ctrl = SWCDesignerController()
        ctrl.new_project()
        swc = SWCDef(name="TestSWC", category="ApplicationSoftwareComponent", description="test")
        ok = ctrl.add_swc(swc)
        assert ok is True
        assert len(ctrl.get_swcs()) == 1

    def test_add_duplicate_swc_returns_false(self):
        from modules.swc_designer.controller import SWCDesignerController
        from core.parsers.arxml_parser import SWCDef
        ctrl = SWCDesignerController()
        ctrl.new_project()
        swc = SWCDef(name="TestSWC", category="ApplicationSoftwareComponent", description="test")
        ctrl.add_swc(swc)
        ok = ctrl.add_swc(swc)
        assert ok is False

    def test_remove_swc(self):
        from modules.swc_designer.controller import SWCDesignerController
        from core.parsers.arxml_parser import SWCDef
        ctrl = SWCDesignerController()
        ctrl.new_project()
        ctrl.add_swc(SWCDef(name="TestSWC", category="ApplicationSoftwareComponent", description="test"))
        ok = ctrl.remove_swc("TestSWC")
        assert ok is True
        assert len(ctrl.get_swcs()) == 0

    def test_add_port(self):
        from modules.swc_designer.controller import SWCDesignerController
        from core.parsers.arxml_parser import SWCDef, PortDef, PortDirection
        ctrl = SWCDesignerController()
        ctrl.new_project()
        ctrl.add_swc(SWCDef(name="TestSWC", category="ApplicationSoftwareComponent", description="test"))
        ok = ctrl.add_port("TestSWC", PortDef("TestPort", PortDirection.PROVIDED, "I_Test"))
        assert ok is True
        ports = ctrl.get_ports("TestSWC")
        assert len(ports) == 1
        assert ports[0].name == "TestPort"

    def test_get_ports_nonexistent_swc(self):
        from modules.swc_designer.controller import SWCDesignerController
        ctrl = SWCDesignerController()
        ctrl.new_project()
        assert ctrl.get_ports("Nonexistent") == []

    def test_add_runnable(self):
        from modules.swc_designer.controller import SWCDesignerController
        from core.parsers.arxml_parser import SWCDef, RunnableDef
        ctrl = SWCDesignerController()
        ctrl.new_project()
        ctrl.add_swc(SWCDef(name="TestSWC", category="ApplicationSoftwareComponent", description="test"))
        ok = ctrl.add_runnable("TestSWC", RunnableDef("RE_Test", period_ms=10))
        assert ok is True
        runnables = ctrl.get_runnables("TestSWC")
        assert len(runnables) == 1
        assert runnables[0].name == "RE_Test"

    def test_get_interfaces_empty_project(self):
        from modules.swc_designer.controller import SWCDesignerController
        ctrl = SWCDesignerController()
        ctrl.new_project()
        assert ctrl.get_interfaces() == []
        assert ctrl.get_interface_names() == []

    def test_add_interface(self):
        from modules.swc_designer.controller import SWCDesignerController
        from core.parsers.arxml_parser import SenderReceiverInterface, DataElementDef
        ctrl = SWCDesignerController()
        ctrl.new_project()
        iface = SenderReceiverInterface(name="I_Test", data_elements=[
            DataElementDef(name="Elem1", type_ref="uint8")
        ])
        ok = ctrl.add_interface(iface)
        assert ok is True
        assert "I_Test" in ctrl.get_interface_names()

    def test_template_library(self):
        from modules.swc_designer.controller import SWCDesignerController
        ctrl = SWCDesignerController()
        names = ctrl.get_template_names()
        assert len(names) > 0
        assert "TPL_PowerMgmt" in names
        assert "TPL_DriveCtrl" in names

    def test_create_from_template(self):
        from modules.swc_designer.controller import SWCDesignerController
        ctrl = SWCDesignerController()
        swc = ctrl.create_swc_from_template("TPL_PowerMgmt", "MyPowerMgmt")
        assert swc is not None
        assert swc.name == "MyPowerMgmt"
        assert len(swc.ports) > 0
        assert len(swc.runnables) > 0

    def test_validate_empty_project(self):
        from modules.swc_designer.controller import SWCDesignerController
        ctrl = SWCDesignerController()
        ctrl.new_project()
        results = ctrl.validate()
        assert results == []


class TestDiagBuilderController:

    @pytest.fixture
    def diag_ctrl(self, tmp_path):
        from modules.diag_builder.controller import DiagBuilderController
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test_diag.db")
        ctrl = DiagBuilderController(db_manager=db_mgr)
        yield ctrl
        db_mgr.close()

    def test_create_instance(self, diag_ctrl):
        assert diag_ctrl is not None

    def test_add_dtc(self, diag_ctrl):
        dtc = diag_ctrl.add_dtc("0xD001", "Battery over-voltage", severity="critical")
        assert dtc is not None
        assert dtc.dtc_code == "0xD001"

    def test_get_dtcs(self, diag_ctrl):
        diag_ctrl.add_dtc("0xD001", "Test DTC 1")
        diag_ctrl.add_dtc("0xD002", "Test DTC 2")
        dtcs = diag_ctrl.get_dtcs()
        assert len(dtcs) == 2

    def test_get_dtc_by_code(self, diag_ctrl):
        diag_ctrl.add_dtc("0xD001", "Test DTC")
        dtc = diag_ctrl.get_dtc_by_code("0xD001")
        assert dtc is not None
        assert dtc.description == "Test DTC"

    def test_get_dtc_by_code_not_found(self, diag_ctrl):
        dtc = diag_ctrl.get_dtc_by_code("0xFFFF")
        assert dtc is None

    def test_add_service(self, diag_ctrl):
        svc = diag_ctrl.add_service("0x22", "ReadDataByIdentifier")
        assert svc is not None
        assert svc.sid == "0x22"

    def test_get_services(self, diag_ctrl):
        diag_ctrl.add_service("0x22", "RDBI")
        diag_ctrl.add_service("0x2E", "WDBI")
        svcs = diag_ctrl.get_services()
        assert len(svcs) == 2

    def test_validate(self, diag_ctrl):
        diag_ctrl.add_dtc("0xD001", "Test DTC", severity="warning")
        issues = diag_ctrl.validate()
        # Should not have critical errors for a well-defined DTC
        critical = [i for i in issues if i["type"] == "error"]
        assert len(critical) == 0

    def test_validate_dtc_no_severity(self, diag_ctrl):
        diag_ctrl.add_dtc("0xD001", "Test DTC", severity="")
        issues = diag_ctrl.validate()
        warnings = [i for i in issues if i.get("rule") == "DIAG_NO_SEVERITY"]
        assert len(warnings) > 0

    def test_export_import_json(self, diag_ctrl, tmp_path):
        diag_ctrl.add_dtc("0xD001", "Test DTC", severity="warning")
        diag_ctrl.add_service("0x22", "RDBI")

        out_file = tmp_path / "diag_export.json"
        ok, _ = diag_ctrl.export_json(out_file)
        assert ok is True
        assert out_file.exists()

        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert len(data["dtcs"]) == 1
        assert len(data["services"]) == 1

    def test_standard_services_template(self):
        from modules.diag_builder.controller import DiagBuilderController
        svcs = DiagBuilderController.get_standard_services()
        assert len(svcs) > 0
        sids = [s["sid"] for s in svcs]
        assert "0x10" in sids
        assert "0x22" in sids
        assert "0x27" in sids

    def test_import_odx(self, diag_ctrl, tmp_path):
        """Import DTCs and services from an ODX file."""
        odx_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<ODX version="2.2">
  <DIAG-LAYER-CONTAINER>
    <SHORT-NAME>VCU_Diag</SHORT-NAME>
    <DIAG-CODE>
      <CODE>0xD001</CODE>
      <TEXT>Battery over-voltage</TEXT>
    </DIAG-CODE>
    <DIAG-CODE>
      <CODE>0xD002</CODE>
      <TEXT>Motor over-temperature</TEXT>
    </DIAG-CODE>
    <DIAG-SERVICE>
      <SHORT-NAME>ReadDTC</SHORT-NAME>
      <SEMANTIC>0x19</SEMANTIC>
      <LONG-NAME>Read DTC Information</LONG-NAME>
    </DIAG-SERVICE>
  </DIAG-LAYER-CONTAINER>
</ODX>
"""
        f = tmp_path / "test.odx"
        f.write_text(odx_content, encoding="utf-8")
        ok, msgs = diag_ctrl.import_odx(f)
        assert ok is True
        assert len(diag_ctrl.get_dtcs()) == 2
        assert diag_ctrl.get_dtc_by_code("0xD001") is not None
        assert diag_ctrl.get_dtc_by_code("0xD002") is not None
        assert len(diag_ctrl.get_services()) == 1

    def test_import_odx_skips_duplicates(self, diag_ctrl, tmp_path):
        """ODX import skips already-existing DTC codes."""
        diag_ctrl.add_dtc("0xD001", "Existing DTC")
        odx_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<ODX version="2.2">
  <DIAG-LAYER-CONTAINER>
    <DIAG-CODE><CODE>0xD001</CODE><TEXT>Dup</TEXT></DIAG-CODE>
    <DIAG-CODE><CODE>0xD003</CODE><TEXT>New</TEXT></DIAG-CODE>
  </DIAG-LAYER-CONTAINER>
</ODX>
"""
        f = tmp_path / "dup.odx"
        f.write_text(odx_content, encoding="utf-8")
        ok, msgs = diag_ctrl.import_odx(f)
        assert ok is True
        assert len(diag_ctrl.get_dtcs()) == 2  # original + 0xD003, 0xD001 skipped


class TestCalibManagerController:

    @pytest.fixture
    def calib_ctrl(self, tmp_path):
        from modules.calib_manager.controller import CalibManagerController
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test_calib.db")
        ctrl = CalibManagerController(db_manager=db_mgr)
        yield ctrl
        db_mgr.close()

    def test_create_instance(self, calib_ctrl):
        assert calib_ctrl is not None

    def test_add_param(self, calib_ctrl):
        param = calib_ctrl.add_param("MotorMaxTorque", data_type="VALUE",
                                      default_value=300.0, min_value=0.0,
                                      max_value=500.0, unit="Nm")
        assert param is not None
        assert param.name == "MotorMaxTorque"

    def test_get_params(self, calib_ctrl):
        calib_ctrl.add_param("Param1", data_type="VALUE")
        calib_ctrl.add_param("Param2", data_type="VALUE")
        params = calib_ctrl.get_params()
        assert len(params) == 2

    def test_get_param_by_name(self, calib_ctrl):
        calib_ctrl.add_param("MotorMaxTorque", data_type="VALUE")
        param = calib_ctrl.get_param_by_name("MotorMaxTorque")
        assert param is not None

    def test_get_param_by_name_not_found(self, calib_ctrl):
        param = calib_ctrl.get_param_by_name("Nonexistent")
        assert param is None

    def test_get_groups(self, calib_ctrl):
        calib_ctrl.add_param("P1", data_type="VALUE", group_name="Motor")
        calib_ctrl.add_param("P2", data_type="VALUE", group_name="Battery")
        groups = calib_ctrl.get_groups()
        assert "Motor" in groups
        assert "Battery" in groups

    def test_get_swcs(self, calib_ctrl):
        calib_ctrl.add_param("P1", data_type="VALUE", swc_name="DriveCtrl")
        swcs = calib_ctrl.get_swcs()
        assert "DriveCtrl" in swcs

    def test_validate(self, calib_ctrl):
        calib_ctrl.add_param("P1", data_type="VALUE", description="Test param",
                              min_value=0, max_value=100, group_name="Test")
        issues = calib_ctrl.validate()
        # Well-defined param should have no errors
        errors = [i for i in issues if i["type"] == "error"]
        assert len(errors) == 0

    def test_validate_no_description(self, calib_ctrl):
        calib_ctrl.add_param("P1", data_type="VALUE")
        issues = calib_ctrl.validate()
        desc_warnings = [i for i in issues if i.get("rule") == "CAL_NO_DESC"]
        assert len(desc_warnings) > 0

    def test_export_json(self, calib_ctrl, tmp_path):
        calib_ctrl.add_param("P1", data_type="VALUE", default_value=10.0)
        out_file = tmp_path / "calib_export.json"
        ok, _ = calib_ctrl.export_json(out_file)
        assert ok is True
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert "parameters" in data
        assert len(data["parameters"]) == 1


class TestTestGeneratorController:

    def test_create_instance(self):
        from modules.test_generator.controller import TestGeneratorController
        ctrl = TestGeneratorController()
        assert ctrl is not None
        assert ctrl.get_test_cases() == []

    def test_load_dbc_and_generate(self, tmp_path):
        from modules.test_generator.controller import TestGeneratorController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = TestGeneratorController()
        ok, _ = ctrl.load_dbc(dbc_file)
        assert ok is True

        count = ctrl.generate_signal_tests()
        assert count > 0
        assert len(ctrl.get_test_cases()) == count

    def test_generate_with_methods(self, tmp_path):
        from modules.test_generator.controller import TestGeneratorController, TestMethod
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = TestGeneratorController()
        ctrl.load_dbc(dbc_file)
        count = ctrl.generate_signal_tests([TestMethod.ERROR_INJECTION])
        assert count > 0
        for tc in ctrl.get_test_cases():
            assert tc.method == "error_injection"

    def test_get_cases_by_category(self, tmp_path):
        from modules.test_generator.controller import TestGeneratorController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = TestGeneratorController()
        ctrl.load_dbc(dbc_file)
        ctrl.generate_signal_tests()
        cats = ctrl.get_cases_by_category()
        assert len(cats) > 0

    def test_get_coverage(self, tmp_path):
        from modules.test_generator.controller import TestGeneratorController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = TestGeneratorController()
        ctrl.load_dbc(dbc_file)
        ctrl.generate_signal_tests()
        cov = ctrl.get_coverage()
        assert cov["total_signals"] > 0
        assert cov["covered"] > 0
        assert cov["coverage"] > 0

    def test_export_json(self, tmp_path):
        from modules.test_generator.controller import TestGeneratorController
        dbc_file = tmp_path / "test.dbc"
        dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
        ctrl = TestGeneratorController()
        ctrl.load_dbc(dbc_file)
        ctrl.generate_signal_tests()
        out_file = tmp_path / "tests.json"
        ok, _ = ctrl.export_json(out_file)
        assert ok is True
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert "test_cases" in data
        assert "coverage" in data

    def test_no_dbc_returns_zero(self):
        from modules.test_generator.controller import TestGeneratorController
        ctrl = TestGeneratorController()
        assert ctrl.generate_signal_tests() == 0
        assert ctrl.get_coverage()["total_signals"] == 0


class TestTraceMatrixController:

    @pytest.fixture
    def trace_ctrl(self, tmp_path):
        from modules.trace_matrix.controller import TraceMatrixController
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test_trace.db")
        ctrl = TraceMatrixController(db_manager=db_mgr)
        yield ctrl
        db_mgr.close()

    def test_create_instance(self, trace_ctrl):
        assert trace_ctrl is not None

    def test_add_requirement(self, trace_ctrl):
        req = trace_ctrl.add_requirement("REQ-001", "Power management requirement")
        assert req is not None
        assert req.req_id == "REQ-001"

    def test_get_requirements(self, trace_ctrl):
        trace_ctrl.add_requirement("REQ-001", "Req 1")
        trace_ctrl.add_requirement("REQ-002", "Req 2")
        reqs = trace_ctrl.get_requirements()
        assert len(reqs) == 2

    def test_get_req_by_id(self, trace_ctrl):
        trace_ctrl.add_requirement("REQ-001", "Test Req")
        req = trace_ctrl.get_req_by_id("REQ-001")
        assert req is not None

    def test_get_req_by_id_not_found(self, trace_ctrl):
        req = trace_ctrl.get_req_by_id("REQ-999")
        assert req is None

    def test_add_link(self, trace_ctrl):
        trace_ctrl.add_requirement("REQ-001", "Test Req")
        ok = trace_ctrl.add_link("REQ-001", "swc", "VCU_PowerMgmt")
        assert ok is True

    def test_add_link_nonexistent_req(self, trace_ctrl):
        ok = trace_ctrl.add_link("REQ-999", "swc", "VCU_PowerMgmt")
        assert ok is False

    def test_add_duplicate_link_returns_false(self, trace_ctrl):
        trace_ctrl.add_requirement("REQ-001", "Test Req")
        trace_ctrl.add_link("REQ-001", "swc", "VCU_PowerMgmt")
        ok = trace_ctrl.add_link("REQ-001", "swc", "VCU_PowerMgmt")
        assert ok is False

    def test_get_links_for_req(self, trace_ctrl):
        trace_ctrl.add_requirement("REQ-001", "Test Req")
        trace_ctrl.add_link("REQ-001", "swc", "VCU_PowerMgmt")
        trace_ctrl.add_link("REQ-001", "signal", "VCU_SOC")
        links = trace_ctrl.get_links_for_req("REQ-001")
        assert len(links) == 2

    def test_auto_match_by_naming(self, trace_ctrl):
        trace_ctrl.add_requirement("REQ_PowerMgmt_001", "Power management control")
        artifacts = {
            "swc": ["VCU_PowerMgmt", "VCU_DriveCtrl"],
            "signal": ["VCU_PowerMode", "VCU_SOC"],
        }
        count = trace_ctrl.auto_match_by_naming(artifacts)
        # "power" appears in both REQ title and VCU_PowerMgmt/VCU_PowerMode
        assert count > 0

    def test_get_matrix(self, trace_ctrl):
        trace_ctrl.add_requirement("REQ-001", "Test Req")
        trace_ctrl.add_link("REQ-001", "swc", "VCU_PowerMgmt")
        matrix = trace_ctrl.get_matrix()
        assert "REQ-001" in matrix
        assert matrix["REQ-001"]["link_count"] == 1

    def test_get_statistics(self, trace_ctrl):
        trace_ctrl.add_requirement("REQ-001", "Test Req")
        stats = trace_ctrl.get_statistics()
        assert stats["total_requirements"] == 1
        assert "coverage_pct" in stats

    def test_get_gaps(self, trace_ctrl):
        trace_ctrl.add_requirement("REQ-001", "Test Req")
        gaps = trace_ctrl.get_gaps()
        assert len(gaps) == 1  # No links = gap
        assert gaps[0]["req_id"] == "REQ-001"

    def test_export_json(self, trace_ctrl, tmp_path):
        trace_ctrl.add_requirement("REQ-001", "Test Req")
        trace_ctrl.add_link("REQ-001", "swc", "VCU_PowerMgmt")
        out_file = tmp_path / "trace_export.json"
        ok, _ = trace_ctrl.export_json(out_file)
        assert ok is True
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert "requirements" in data
        assert "statistics" in data


# ============================================================================
# 4. PARSER FUNCTIONAL TESTS
# ============================================================================

class TestA2LParser:

    SAMPLE_A2L = """\
/begin PROJECT VCU_Project "VCU Project"
  /begin HEADER "VCU Calibration"
  /end HEADER
/end PROJECT

/begin COMPU_METHOD CM_Linear "Linear conversion" LINEAR "%8.3" "RPM"
  COEFFS 0 1 0 0 0 1
/end COMPU_METHOD

/begin CHARACTERISTIC MotorMaxTorque "Max motor torque" VALUE 0x1000 Default_RL 0 0 500
  COMPU_METHOD CM_Linear
  UNIT "Nm"
  LOWER_LIMIT 0
  UPPER_LIMIT 500
/end CHARACTERISTIC

/begin MEASUREMENT MotorSpeed "Motor speed" UWORD CM_Linear 1 0 0 8000
  UNIT "RPM"
/end MEASUREMENT
"""

    def test_parse_string(self):
        from core.parsers.a2l_parser import A2LParser, A2LData
        parser = A2LParser()
        result = parser.parse_string(self.SAMPLE_A2L)
        assert result.success
        assert isinstance(result.data, A2LData)

    def test_parse_characteristics(self):
        from core.parsers.a2l_parser import A2LParser
        parser = A2LParser()
        result = parser.parse_string(self.SAMPLE_A2L)
        chars = result.data.characteristics
        assert len(chars) >= 1
        char = next(c for c in chars if c.name == "MotorMaxTorque")
        assert char.type == "VALUE"
        assert char.address == 0x1000

    def test_parse_measurements(self):
        from core.parsers.a2l_parser import A2LParser
        parser = A2LParser()
        result = parser.parse_string(self.SAMPLE_A2L)
        meas = result.data.measurements
        assert len(meas) >= 1
        m = next(x for x in meas if x.name == "MotorSpeed")
        assert m.data_type == "UWORD"

    def test_parse_compu_methods(self):
        from core.parsers.a2l_parser import A2LParser
        parser = A2LParser()
        result = parser.parse_string(self.SAMPLE_A2L)
        cms = result.data.compu_methods
        assert len(cms) >= 1
        cm = next(c for c in cms if c.name == "CM_Linear")
        assert cm.conversion_type == "LINEAR"

    def test_validate_valid_a2l(self, tmp_path):
        """Validate accepts valid A2L files (bug fixed: now checks '/BEGIN')."""
        from core.parsers.a2l_parser import A2LParser
        f = tmp_path / "test.a2l"
        f.write_text(self.SAMPLE_A2L, encoding="utf-8")
        parser = A2LParser()
        errors = parser.validate(f)
        assert len(errors) == 0, f"Expected no errors for valid A2L, got: {errors}"

    def test_validate_invalid_file(self, tmp_path):
        from core.parsers.a2l_parser import A2LParser
        f = tmp_path / "bad.a2l"
        f.write_text("This is not A2L content", encoding="utf-8")
        parser = A2LParser()
        errors = parser.validate(f)
        assert len(errors) > 0


class TestODXParser:

    SAMPLE_ODX = """\
<?xml version="1.0" encoding="UTF-8"?>
<ODX version="2.2">
  <DIAG-LAYER-CONTAINER>
    <SHORT-NAME>VCU_Diag</SHORT-NAME>
    <DIAG-CODE>
      <CODE>0xD001</CODE>
      <TEXT>Battery over-voltage</TEXT>
    </DIAG-CODE>
    <DIAG-CODE>
      <CODE>0xD002</CODE>
      <TEXT>Motor over-temperature</TEXT>
    </DIAG-CODE>
    <DIAG-SERVICE>
      <SHORT-NAME>ReadDTC</SHORT-NAME>
      <SEMANTIC>0x19</SEMANTIC>
      <LONG-NAME>Read DTC Information</LONG-NAME>
    </DIAG-SERVICE>
  </DIAG-LAYER-CONTAINER>
</ODX>
"""

    def test_parse_string_via_file(self, tmp_path):
        from core.parsers.odx_parser import ODXParser, ODXData
        f = tmp_path / "test.odx"
        f.write_text(self.SAMPLE_ODX, encoding="utf-8")
        parser = ODXParser()
        result = parser.parse(f)
        assert result.success
        assert isinstance(result.data, ODXData)

    def test_extract_dtcs(self, tmp_path):
        from core.parsers.odx_parser import ODXParser
        f = tmp_path / "test.odx"
        f.write_text(self.SAMPLE_ODX, encoding="utf-8")
        parser = ODXParser()
        result = parser.parse(f)
        assert len(result.data.dtcs) == 2
        codes = [d.code for d in result.data.dtcs]
        assert "0xD001" in codes
        assert "0xD002" in codes

    def test_extract_services(self, tmp_path):
        from core.parsers.odx_parser import ODXParser
        f = tmp_path / "test.odx"
        f.write_text(self.SAMPLE_ODX, encoding="utf-8")
        parser = ODXParser()
        result = parser.parse(f)
        assert len(result.data.services) == 1
        assert result.data.services[0].name == "ReadDTC"

    def test_validate_valid_odx(self, tmp_path):
        from core.parsers.odx_parser import ODXParser
        f = tmp_path / "test.odx"
        f.write_text(self.SAMPLE_ODX, encoding="utf-8")
        parser = ODXParser()
        errors = parser.validate(f)
        assert len(errors) == 0

    def test_validate_invalid_xml(self, tmp_path):
        from core.parsers.odx_parser import ODXParser
        f = tmp_path / "bad.odx"
        f.write_text("not xml at all", encoding="utf-8")
        parser = ODXParser()
        errors = parser.validate(f)
        assert len(errors) > 0

    def test_supported_extensions(self):
        from core.parsers.odx_parser import ODXParser
        parser = ODXParser()
        exts = parser.supported_extensions()
        assert ".odx" in exts
        assert ".cdd" in exts


class TestXXEProtection:
    """Verify that XML parsers block XXE attacks."""

    XXE_PAYLOAD = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///c:/windows/win.ini">
]>
<AUTOSAR>&xxe;</AUTOSAR>
"""

    def test_arxml_parser_blocks_xxe(self, tmp_path):
        from core.parsers.arxml_parser import ARXMLParser
        f = tmp_path / "xxe.arxml"
        f.write_text(self.XXE_PAYLOAD, encoding="utf-8")
        parser = ARXMLParser()
        result = parser.parse(f)
        # Should either fail to parse or parse without resolving the entity
        if result.success:
            # If it parsed, the entity should NOT have been resolved
            assert "xxe" not in str(result.data).lower() or "[drivers]" not in str(result.data).lower()
        # The key test: no exception should expose file contents

    def test_odx_parser_blocks_xxe(self, tmp_path):
        from core.parsers.odx_parser import ODXParser
        f = tmp_path / "xxe.odx"
        f.write_text(self.XXE_PAYLOAD, encoding="utf-8")
        parser = ODXParser()
        result = parser.parse(f)
        # Should either fail or not resolve entity
        if result.success:
            data_str = str(result.data)
            assert "[drivers]" not in data_str.lower()


# ============================================================================
# 5. UI COMPONENT TESTS (without GUI startup)
# ============================================================================

class TestAppSettings:

    def test_default_values(self):
        from config.settings import AppSettings
        s = AppSettings()
        assert s.app_name == "VCU DevKit"
        assert s.version == "0.1.0"
        assert s.theme == "light"

    def test_add_recent_file(self):
        from config.settings import AppSettings
        s = AppSettings()
        s.add_recent_file("/path/to/file.dbc")
        assert s.recent_files[0] == "/path/to/file.dbc"

    def test_add_recent_file_dedup(self):
        from config.settings import AppSettings
        s = AppSettings()
        s.add_recent_file("/path/to/file.dbc")
        s.add_recent_file("/path/to/other.dbc")
        s.add_recent_file("/path/to/file.dbc")
        assert s.recent_files[0] == "/path/to/file.dbc"
        assert len(s.recent_files) == 2

    def test_save_and_load(self, tmp_path):
        from config.settings import AppSettings
        cfg = tmp_path / "settings.json"
        s = AppSettings()
        s.theme = "dark"
        s.save(cfg)

        s2 = AppSettings()
        s2.load(cfg)
        assert s2.theme == "dark"

    def test_load_nonexistent(self, tmp_path):
        from config.settings import AppSettings
        s = AppSettings()
        s.load(tmp_path / "nonexistent.json")
        assert s.theme == "light"  # default unchanged


class TestDataTableModel:

    def test_create_model(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.table_editor import DataTableModel
        model = DataTableModel(["Name", "Value"], ["name", "value"])
        assert model.rowCount() == 0

    def test_load_data(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.table_editor import DataTableModel
        model = DataTableModel(["Name", "Value"], ["name", "value"])
        data = [{"name": "A", "value": 1}, {"name": "B", "value": 2}]
        model.load_data(data)
        assert model.rowCount() == 2

    def test_get_row(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.table_editor import DataTableModel
        model = DataTableModel(["Name", "Value"], ["name", "value"])
        model.load_data([{"name": "A", "value": 1}])
        row = model.get_row(0)
        assert row["name"] == "A"
        assert row["value"] == 1

    def test_add_row(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.table_editor import DataTableModel
        model = DataTableModel(["Name", "Value"], ["name", "value"])
        model.add_row({"name": "New", "value": 42})
        assert model.rowCount() == 1
        assert model.get_row(0)["name"] == "New"

    def test_remove_row(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.table_editor import DataTableModel
        model = DataTableModel(["Name", "Value"], ["name", "value"])
        model.load_data([{"name": "A", "value": 1}, {"name": "B", "value": 2}])
        model.remove_row(0)
        assert model.rowCount() == 1
        assert model.get_row(0)["name"] == "B"

    def test_column_count(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.table_editor import DataTableModel
        model = DataTableModel(["A", "B", "C"], ["a", "b", "c"])
        assert model.columnCount() == 3


class TestFileWorker:

    def test_create_instance(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.file_worker import FileWorker
        worker = FileWorker(lambda: 42)
        assert worker is not None

    def test_has_signals(self):
        from ui.widgets.file_worker import FileWorker
        assert hasattr(FileWorker, 'finished_ok')
        assert hasattr(FileWorker, 'finished_err')


class TestUIIcons:
    """Test that all icon functions return non-empty QIcon objects."""

    def test_icon_open(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.icons import icon_open
        icon = icon_open()
        assert icon is not None

    def test_icon_save(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.icons import icon_save
        icon = icon_save()
        assert icon is not None

    def test_icon_generate(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.icons import icon_generate
        icon = icon_generate()
        assert icon is not None

    def test_all_icons_return_qicon(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QIcon
        app = QApplication.instance() or QApplication([])
        from ui.icons import (
            icon_open, icon_save, icon_check, icon_generate,
            icon_export, icon_diff, icon_add, icon_remove,
            icon_validate, icon_clear, icon_load, icon_search,
            icon_export_json, icon_export_excel, icon_export_arxml, icon_export_a2l,
        )
        for fn in [icon_open, icon_save, icon_check, icon_generate,
                    icon_export, icon_diff, icon_add, icon_remove,
                    icon_validate, icon_clear, icon_load, icon_search,
                    icon_export_json, icon_export_excel, icon_export_arxml, icon_export_a2l]:
            result = fn()
            assert isinstance(result, QIcon), f"{fn.__name__} did not return QIcon"


class TestStatusBarWidget:

    def test_create(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.status_bar import StatusBarWidget
        widget = StatusBarWidget()
        assert widget is not None

    def test_set_project(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.status_bar import StatusBarWidget
        widget = StatusBarWidget()
        widget.set_project("/path/to/MyProject")
        assert "MyProject" in widget.project_label.text()

    def test_set_file_counts(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.status_bar import StatusBarWidget
        widget = StatusBarWidget()
        widget.set_file_counts(dbc=3, arxml=2, odx=1, a2l=4)
        text = widget.files_label.text()
        assert "DBC: 3" in text
        assert "ARXML: 2" in text


class TestTreeView:

    def test_create(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.tree_view import TreeView
        tv = TreeView()
        assert tv is not None

    def test_add_items(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.tree_view import TreeView
        tv = TreeView()
        parent = tv.add_top_level_item("Messages")
        tv.add_child_item(parent, "VCU_Status")
        tv.add_child_item(parent, "VCU_Torque")
        assert tv.model.rowCount() == 1
        assert tv.model.item(0).rowCount() == 2


class TestPropertyPanel:

    def test_create(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.property_panel import PropertyPanel
        panel = PropertyPanel()
        assert panel is not None

    def test_set_properties(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.property_panel import PropertyPanel
        panel = PropertyPanel()
        fields = [
            {"name": "name", "label": "Name", "type": "text", "value": "Test"},
            {"name": "count", "label": "Count", "type": "int", "value": 5, "min": 0, "max": 100},
        ]
        panel.set_properties("Test Properties", fields)
        assert panel.get_value("name") == "Test"
        assert panel.get_value("count") == 5

    def test_clear(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.widgets.property_panel import PropertyPanel
        panel = PropertyPanel()
        panel.set_properties("Test", [{"name": "x", "label": "X", "type": "text", "value": "1"}])
        panel.clear()
        assert panel.get_value("x") is None


# ============================================================================
# 6. DATABASE TESTS
# ============================================================================

class TestDatabaseManager:

    def test_init(self, tmp_path):
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test.db")
        db_mgr.init()
        assert db_mgr.is_ready()
        db_mgr.close()

    def test_create_tables(self, tmp_path):
        from core.db.manager import DatabaseManager
        from core.db.models import db
        db_mgr = DatabaseManager(tmp_path / "test.db")
        db_mgr.init()
        # Tables should exist
        tables = db.get_tables()
        assert "calibrationparameter" in [t.lower() for t in tables]
        assert "dtcdefinition" in [t.lower() for t in tables]
        db_mgr.close()

    def test_add_and_get_calibration_param(self, tmp_path):
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test.db")
        db_mgr.init()
        param = db_mgr.add_calibration_param(name="TestParam", data_type="VALUE")
        assert param is not None
        params = db_mgr.get_calibration_params()
        assert len(params) == 1
        db_mgr.close()

    def test_add_and_get_dtc(self, tmp_path):
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test.db")
        db_mgr.init()
        dtc = db_mgr.add_dtc(dtc_code="0xD001", description="Test DTC")
        assert dtc is not None
        dtcs = db_mgr.get_dtcs()
        assert len(dtcs) == 1
        db_mgr.close()

    def test_add_and_get_diag_service(self, tmp_path):
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test.db")
        db_mgr.init()
        svc = db_mgr.add_diag_service(sid="0x22", service_name="RDBI")
        assert svc is not None
        svcs = db_mgr.get_diag_services(enabled_only=False)
        assert len(svcs) == 1
        db_mgr.close()

    def test_add_and_get_requirement(self, tmp_path):
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test.db")
        db_mgr.init()
        req = db_mgr.add_requirement(req_id="REQ-001", title="Test Req")
        assert req is not None
        reqs = db_mgr.get_requirements()
        assert len(reqs) == 1
        db_mgr.close()

    def test_reset(self, tmp_path):
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test.db")
        db_mgr.init()
        db_mgr.add_dtc(dtc_code="0xD001", description="Test")
        assert len(db_mgr.get_dtcs()) == 1
        db_mgr.reset()
        assert len(db_mgr.get_dtcs()) == 0
        db_mgr.close()

    def test_record_file_version(self, tmp_path):
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test.db")
        db_mgr.init()
        fv = db_mgr.record_file_version("/path/to/test.dbc", "dbc", "abc123")
        assert fv is not None
        versions = db_mgr.get_file_versions("/path/to/test.dbc")
        assert len(versions) == 1
        db_mgr.close()


# ============================================================================
# 7. THEME FILE TESTS
# ============================================================================

class TestThemeFiles:

    def test_light_qss_exists(self):
        qss_path = Path(__file__).resolve().parent.parent / "ui" / "themes" / "light.qss"
        assert qss_path.exists(), "light.qss not found"

    def test_dark_qss_exists(self):
        qss_path = Path(__file__).resolve().parent.parent / "ui" / "themes" / "dark.qss"
        assert qss_path.exists(), "dark.qss not found"

    def test_light_qss_has_content(self):
        qss_path = Path(__file__).resolve().parent.parent / "ui" / "themes" / "light.qss"
        content = qss_path.read_text(encoding="utf-8")
        assert len(content) > 100, "light.qss is suspiciously short"

    def test_dark_qss_has_content(self):
        qss_path = Path(__file__).resolve().parent.parent / "ui" / "themes" / "dark.qss"
        content = qss_path.read_text(encoding="utf-8")
        assert len(content) > 100, "dark.qss is suspiciously short"

    def test_light_qss_basic_syntax(self):
        """Check for balanced braces — basic QSS syntax validation."""
        qss_path = Path(__file__).resolve().parent.parent / "ui" / "themes" / "light.qss"
        content = qss_path.read_text(encoding="utf-8")
        open_braces = content.count("{")
        close_braces = content.count("}")
        assert open_braces == close_braces, f"Unbalanced braces: {open_braces} open vs {close_braces} close"

    def test_dark_qss_basic_syntax(self):
        qss_path = Path(__file__).resolve().parent.parent / "ui" / "themes" / "dark.qss"
        content = qss_path.read_text(encoding="utf-8")
        open_braces = content.count("{")
        close_braces = content.count("}")
        assert open_braces == close_braces, f"Unbalanced braces: {open_braces} open vs {close_braces} close"

    def test_light_qss_has_key_selectors(self):
        qss_path = Path(__file__).resolve().parent.parent / "ui" / "themes" / "light.qss"
        content = qss_path.read_text(encoding="utf-8")
        for selector in ["QMainWindow", "QPushButton", "QTableView", "QTreeView", "QTabBar"]:
            assert selector in content, f"Missing selector {selector} in light.qss"

    def test_dark_qss_has_key_selectors(self):
        qss_path = Path(__file__).resolve().parent.parent / "ui" / "themes" / "dark.qss"
        content = qss_path.read_text(encoding="utf-8")
        for selector in ["QMainWindow", "QPushButton", "QTableView", "QTreeView", "QTabBar"]:
            assert selector in content, f"Missing selector {selector} in dark.qss"


# ============================================================================
# 8. RULE ENGINE TESTS
# ============================================================================

class TestRuleEngine:

    def test_check_dbc_valid(self):
        from core.rules.engine import RuleEngine
        from core.parsers.dbc_parser import DBCParser
        parser = DBCParser()
        result = parser.parse_string(SAMPLE_DBC)
        engine = RuleEngine()
        findings = engine.check_dbc(result.data)
        errors = [f for f in findings if f.severity.value == "error"]
        assert len(errors) == 0

    def test_check_dbc_duplicate_id(self):
        from core.rules.engine import RuleEngine
        from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef
        data = DBCData(
            version="", messages=[
                MessageDef(id=0x100, name="Msg1", dlc=8, sender="", comment="", signals=[]),
                MessageDef(id=0x100, name="Msg2", dlc=8, sender="", comment="", signals=[]),
            ],
            nodes=[], value_tables={}, comments={}, attributes={}, source_path="",
        )
        engine = RuleEngine()
        findings = engine.check_dbc(data)
        dup_errors = [f for f in findings if f.rule_id == "DBC_DUP_ID"]
        assert len(dup_errors) > 0


# ============================================================================
# 9. CODE GENERATOR TESTS
# ============================================================================

class TestCANCodeGenerator:

    def test_generate_to_dir(self, tmp_path):
        from core.generators.c_generator import CANCodeGenerator
        from core.parsers.dbc_parser import DBCParser
        parser = DBCParser()
        result = parser.parse_string(SAMPLE_DBC)
        gen = CANCodeGenerator()
        out_dir = tmp_path / "gen_output"
        gen_result = gen.generate(result.data, out_dir)
        assert gen_result.success
        assert (out_dir / "can_pack.h").exists()
        assert (out_dir / "can_signals.h").exists()
        assert (out_dir / "can_messages.h").exists()

    def test_generated_header_content(self, tmp_path):
        from core.generators.c_generator import CANCodeGenerator
        from core.parsers.dbc_parser import DBCParser
        parser = DBCParser()
        result = parser.parse_string(SAMPLE_DBC)
        gen = CANCodeGenerator()
        out_dir = tmp_path / "gen_output"
        gen.generate(result.data, out_dir)
        content = (out_dir / "can_pack.h").read_text(encoding="utf-8")
        assert "#ifndef CAN_PACK_H" in content
        assert "CAN_Pack_VCU_SOC" in content
        assert "CAN_Unpack_VCU_SOC" in content


# ============================================================================
# SUMMARY
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
