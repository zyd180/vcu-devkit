"""Tests for A2L (ASAP2) file generator."""

import re
from pathlib import Path

import pytest

from core.parsers.a2l_parser import (
    A2LCharacteristic,
    A2LCompuMethod,
    A2LData,
    A2LMeasurement,
    A2LParser,
)


@pytest.fixture
def sample_a2l_data() -> A2LData:
    """Construct a representative A2LData for testing."""
    return A2LData(
        characteristics=[
            A2LCharacteristic(
                name="MotorMaxTorque",
                long_identifier="Max motor torque",
                type="VALUE",
                address=0x1000,
                record_layout="Default_RL",
                max_diff=0.0,
                conversion="CM_Linear",
                lower_limit=0.0,
                upper_limit=500.0,
                unit="Nm",
                description="Maximum motor torque limit",
            ),
            A2LCharacteristic(
                name="BattMaxCurrent",
                long_identifier="Battery max current",
                type="VALUE",
                address=0x1004,
                record_layout="Default_RL",
                conversion="CM_Identical",
                lower_limit=0.0,
                upper_limit=300.0,
                unit="A",
            ),
        ],
        measurements=[
            A2LMeasurement(
                name="MotorSpeed",
                long_identifier="Motor speed",
                data_type="UWORD",
                conversion="CM_Linear",
                resolution=1,
                accuracy=0.0,
                lower_limit=0.0,
                upper_limit=8000.0,
                unit="RPM",
            ),
            A2LMeasurement(
                name="BattVoltage",
                long_identifier="Battery voltage",
                data_type="UWORD",
                conversion="CM_RatFunc",
                resolution=1,
                accuracy=0.1,
                lower_limit=0.0,
                upper_limit=1000.0,
                unit="V",
            ),
        ],
        compu_methods=[
            A2LCompuMethod(
                name="CM_Linear",
                description="Linear conversion",
                conversion_type="LINEAR",
                format_string="%8.4",
                unit="",
                coeffs=[0, 1, 0, 0, 1, 0],
            ),
            A2LCompuMethod(
                name="CM_Identical",
                description="No conversion",
                conversion_type="IDENTICAL",
                format_string="%8.4",
                unit="",
            ),
            A2LCompuMethod(
                name="CM_RatFunc",
                description="Rational function",
                conversion_type="RAT_FUNC",
                format_string="%8.4",
                unit="V",
                coeffs=[0, 1, 0, 0, 0, 1],
            ),
            A2LCompuMethod(
                name="CM_Formula",
                description="Custom formula",
                conversion_type="FORM",
                format_string="%8.4",
                unit="deg",
                formula="x * 180 / 3.14159",
            ),
        ],
        source_path="test_source.a2l",
    )


class TestA2LGenerator:
    """Unit tests for A2LGenerator.generate_string()."""

    def test_import(self):
        from core.generators.a2l_generator import A2LGenerator
        assert A2LGenerator is not None

    def test_generate_string_returns_str(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        gen = A2LGenerator()
        result = gen.generate_string(sample_a2l_data)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_project_structure(self, sample_a2l_data):
        """Output must contain /begin PROJECT ... /end PROJECT wrapping everything."""
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        assert "/begin PROJECT" in text
        assert "/end PROJECT" in text
        assert "/begin MODULE" in text
        assert "/end MODULE" in text
        assert "/begin HEADER" in text
        assert "/end HEADER" in text

    def test_compu_methods_emitted(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        for cm in sample_a2l_data.compu_methods:
            assert f"/begin COMPU_METHOD {cm.name}" in text
            assert f"/end COMPU_METHOD" in text

    def test_linear_compu_method_coeffs(self, sample_a2l_data):
        """LINEAR type must emit COEFFS line."""
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        assert "CM_Linear" in text
        # COEFFS 0 1 0 0 1 0
        assert re.search(r"COEFFS\s+0\s+1\s+0\s+0\s+1\s+0", text)

    def test_identical_compu_method(self, sample_a2l_data):
        """IDENTICAL type must NOT contain COEFFS."""
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        # Find the IDENTICAL block — it should not have COEFFS
        ident_block = re.search(
            r"/begin COMPU_METHOD CM_Identical.*?/end COMPU_METHOD", text, re.DOTALL
        )
        assert ident_block is not None
        assert "COEFFS" not in ident_block.group()

    def test_rat_func_compu_method_coeffs(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        rat_block = re.search(
            r"/begin COMPU_METHOD CM_RatFunc.*?/end COMPU_METHOD", text, re.DOTALL
        )
        assert rat_block is not None
        assert "RAT_FUNC" in rat_block.group()
        assert "COEFFS" in rat_block.group()

    def test_form_compu_method_formula(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        form_block = re.search(
            r"/begin COMPU_METHOD CM_Formula.*?/end COMPU_METHOD", text, re.DOTALL
        )
        assert form_block is not None
        assert "FORMULA" in form_block.group()

    def test_characteristics_emitted(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        assert "MotorMaxTorque" in text
        assert "BattMaxCurrent" in text
        assert "/begin CHARACTERISTIC" in text
        assert "/end CHARACTERISTIC" in text

    def test_characteristic_address_hex(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        assert "0x00001000" in text
        assert "0x00001004" in text

    def test_characteristic_unit(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        assert 'UNIT "Nm"' in text
        assert 'UNIT "A"' in text

    def test_measurements_emitted(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        assert "MotorSpeed" in text
        assert "BattVoltage" in text
        assert "/begin MEASUREMENT" in text
        assert "/end MEASUREMENT" in text

    def test_measurement_unit(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        assert 'UNIT "RPM"' in text
        assert 'UNIT "V"' in text

    def test_measurement_data_type(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)
        # UWORD should appear in MEASUREMENT lines
        assert "UWORD" in text

    def test_empty_data(self):
        """Generator handles empty data gracefully."""
        from core.generators.a2l_generator import A2LGenerator
        data = A2LData(
            characteristics=[],
            measurements=[],
            compu_methods=[],
            source_path="empty.a2l",
        )
        text = A2LGenerator().generate_string(data)
        assert "/begin PROJECT" in text
        assert "/end PROJECT" in text
        assert "/begin MODULE" in text
        assert "/end MODULE" in text

    def test_roundtrip_parse(self, sample_a2l_data):
        """Generated A2L can be parsed back by A2LParser."""
        from core.generators.a2l_generator import A2LGenerator
        gen = A2LGenerator()
        text = gen.generate_string(sample_a2l_data)

        parser = A2LParser()
        result = parser.parse_string(text)
        assert result.success, f"Round-trip parse failed: {result.errors}"
        assert isinstance(result.data, A2LData)

    def test_roundtrip_preserves_characteristics(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)

        parser = A2LParser()
        result = parser.parse_string(text)
        names = {c.name for c in result.data.characteristics}
        assert "MotorMaxTorque" in names
        assert "BattMaxCurrent" in names

    def test_roundtrip_preserves_measurements(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)

        parser = A2LParser()
        result = parser.parse_string(text)
        names = {m.name for m in result.data.measurements}
        assert "MotorSpeed" in names
        assert "BattVoltage" in names

    def test_roundtrip_preserves_compu_methods(self, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        text = A2LGenerator().generate_string(sample_a2l_data)

        parser = A2LParser()
        result = parser.parse_string(text)
        names = {cm.name for cm in result.data.compu_methods}
        assert "CM_Linear" in names
        assert "CM_Identical" in names
        assert "CM_RatFunc" in names


class TestA2LGeneratorFile:
    """Tests for A2LGenerator.generate() writing to disk."""

    def test_generate_to_file(self, tmp_path, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        gen = A2LGenerator()
        out_file = tmp_path / "output.a2l"
        result = gen.generate(sample_a2l_data, out_file)
        assert result.success
        assert out_file.exists()
        assert out_file in result.output_files

    def test_generated_file_content(self, tmp_path, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        gen = A2LGenerator()
        out_file = tmp_path / "output.a2l"
        gen.generate(sample_a2l_data, out_file)
        content = out_file.read_text(encoding="utf-8")
        assert "/begin PROJECT" in content
        assert "MotorMaxTorque" in content
        assert "MotorSpeed" in content

    def test_generate_creates_parent_dirs(self, tmp_path, sample_a2l_data):
        from core.generators.a2l_generator import A2LGenerator
        gen = A2LGenerator()
        out_file = tmp_path / "nested" / "dir" / "output.a2l"
        result = gen.generate(sample_a2l_data, out_file)
        assert result.success
        assert out_file.exists()

    def test_generate_file_is_valid_a2l(self, tmp_path, sample_a2l_data):
        """Written file passes A2LParser validation."""
        from core.generators.a2l_generator import A2LGenerator
        gen = A2LGenerator()
        out_file = tmp_path / "output.a2l"
        gen.generate(sample_a2l_data, out_file)

        parser = A2LParser()
        errors = parser.validate(out_file)
        assert errors == [], f"Validation errors: {errors}"

    def test_generate_roundtrip_file(self, tmp_path, sample_a2l_data):
        """Written file can be parsed back and preserves data."""
        from core.generators.a2l_generator import A2LGenerator
        gen = A2LGenerator()
        out_file = tmp_path / "output.a2l"
        gen.generate(sample_a2l_data, out_file)

        parser = A2LParser()
        result = parser.parse(out_file)
        assert result.success
        assert len(result.data.characteristics) == 2
        assert len(result.data.measurements) == 2
        assert len(result.data.compu_methods) >= 3  # CM_Linear, CM_Identical, CM_RatFunc


class TestCalibManagerExportA2L:
    """Tests for CalibManagerController.export_a2l()."""

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

    def test_export_a2l_no_data(self, tmp_path):
        """export_a2l returns error when no A2L is loaded."""
        from modules.calib_manager.controller import CalibManagerController
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test.db")
        ctrl = CalibManagerController(db_manager=db_mgr)
        ok, errors = ctrl.export_a2l(tmp_path / "out.a2l")
        assert ok is False
        assert len(errors) > 0
        db_mgr.close()

    def test_export_a2l_success(self, tmp_path):
        """export_a2l writes a valid file after loading A2L data."""
        from modules.calib_manager.controller import CalibManagerController
        from core.db.manager import DatabaseManager
        db_mgr = DatabaseManager(tmp_path / "test.db")
        ctrl = CalibManagerController(db_manager=db_mgr)

        # Load A2L first
        a2l_file = tmp_path / "input.a2l"
        a2l_file.write_text(self.SAMPLE_A2L, encoding="utf-8")
        ok, _ = ctrl.load_a2l(a2l_file)
        assert ok

        # Export
        out_file = tmp_path / "exported.a2l"
        ok, errors = ctrl.export_a2l(out_file)
        assert ok is True
        assert errors == []
        assert out_file.exists()

        # Verify content
        content = out_file.read_text(encoding="utf-8")
        assert "/begin PROJECT" in content
        assert "MotorMaxTorque" in content
        assert "MotorSpeed" in content
        db_mgr.close()

    def test_export_a2l_is_parseable(self, tmp_path):
        """Exported A2L can be parsed back by A2LParser."""
        from modules.calib_manager.controller import CalibManagerController
        from core.db.manager import DatabaseManager
        from core.parsers.a2l_parser import A2LParser
        db_mgr = DatabaseManager(tmp_path / "test.db")
        ctrl = CalibManagerController(db_manager=db_mgr)

        a2l_file = tmp_path / "input.a2l"
        a2l_file.write_text(self.SAMPLE_A2L, encoding="utf-8")
        ctrl.load_a2l(a2l_file)

        out_file = tmp_path / "exported.a2l"
        ctrl.export_a2l(out_file)

        parser = A2LParser()
        result = parser.parse(out_file)
        assert result.success, f"Round-trip failed: {result.errors}"
        assert len(result.data.characteristics) >= 1
        assert len(result.data.measurements) >= 1
        db_mgr.close()
