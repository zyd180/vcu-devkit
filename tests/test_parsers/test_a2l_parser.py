"""Tests for core.parsers.a2l_parser — A2L parsing, including malformed input."""

import pytest
from pathlib import Path

from core.parsers.a2l_parser import A2LParser, A2LData


@pytest.fixture
def parser():
    return A2LParser()


# ── Normal parsing ────────────────────────────────────────────────────────────


class TestA2LParserBasic:

    def test_parse_valid_characteristic(self, parser):
        content = '''
/begin CHARACTERISTIC
    EngSpeed "Engine Speed" VALUE 0x1000 RL_Speed 0.0 5000.0
    COMPU_METHOD "CM_Speed"
    UNIT "rpm"
    LOWER_LIMIT 0.0 UPPER_LIMIT 8000.0
/end CHARACTERISTIC
'''
        result = parser.parse_string(content)
        assert result.success
        data = result.data
        assert len(data.characteristics) == 1
        char = data.characteristics[0]
        assert char.name == "EngSpeed"
        assert char.address == 0x1000
        assert char.type == "VALUE"
        assert char.unit == "rpm"
        assert char.upper_limit == 8000.0

    def test_parse_valid_measurement(self, parser):
        content = '''
/begin MEASUREMENT
    ThrottlePos "Throttle Position" UBYTE CM_Throttle 0 0.0 0.0 100.0
/end MEASUREMENT
'''
        result = parser.parse_string(content)
        assert result.success
        assert len(result.data.measurements) == 1
        meas = result.data.measurements[0]
        assert meas.name == "ThrottlePos"
        assert meas.data_type == "UBYTE"
        assert meas.upper_limit == 100.0

    def test_parse_valid_compu_method(self, parser):
        content = '''
/begin COMPU_METHOD
    CM_Speed "Speed conversion" RAT_FUNC "%8.2" "rpm"
    COEFFS 0 1 0 0 0 1
/end COMPU_METHOD
'''
        result = parser.parse_string(content)
        assert result.success
        assert len(result.data.compu_methods) == 1
        cm = result.data.compu_methods[0]
        assert cm.name == "CM_Speed"
        assert cm.conversion_type == "RAT_FUNC"
        assert len(cm.coeffs) == 6
        assert cm.coeffs == [0.0, 1.0, 0.0, 0.0, 0.0, 1.0]

    def test_parse_empty_content(self, parser):
        result = parser.parse_string("")
        assert result.success
        assert len(result.data.characteristics) == 0
        assert len(result.data.measurements) == 0

    def test_parse_multiple_blocks(self, parser):
        content = '''
/begin CHARACTERISTIC Param1 "Param 1" VALUE 0x1000 RL1 0 100
/end CHARACTERISTIC
/begin CHARACTERISTIC Param2 "Param 2" VALUE 0x2000 RL2 0 200
/end CHARACTERISTIC
/begin MEASUREMENT Sig1 "Signal 1" UWORD CM1 0 0 0 65535
/end MEASUREMENT
'''
        result = parser.parse_string(content)
        assert result.success
        assert len(result.data.characteristics) == 2
        assert len(result.data.measurements) == 1


# ── P0: Malformed input — early return None branches ─────────────────────────


class TestA2LParserMalformed:

    def test_characteristic_empty_block(self, parser):
        """Empty CHARACTERISTIC block should be skipped, not crash."""
        content = '/begin CHARACTERISTIC\n/end CHARACTERISTIC'
        result = parser.parse_string(content)
        assert result.success
        assert len(result.data.characteristics) == 0

    def test_characteristic_insufficient_tokens(self, parser):
        """CHARACTERISTIC with only a name (no type) should be skipped."""
        content = '''
/begin CHARACTERISTIC
    OnlyName
/end CHARACTERISTIC
'''
        result = parser.parse_string(content)
        assert result.success
        assert len(result.data.characteristics) == 0

    def test_characteristic_missing_address(self, parser):
        """CHARACTERISTIC with missing address field should still parse (defaults to 0)."""
        content = '''
/begin CHARACTERISTIC
    Param1 "Description" VALUE
/end CHARACTERISTIC
'''
        result = parser.parse_string(content)
        assert result.success
        assert len(result.data.characteristics) == 1
        char = result.data.characteristics[0]
        assert char.name == "Param1"
        assert char.address == 0

    def test_measurement_empty_block(self, parser):
        """Empty MEASUREMENT block should be skipped."""
        content = '/begin MEASUREMENT\n/end MEASUREMENT'
        result = parser.parse_string(content)
        assert result.success
        assert len(result.data.measurements) == 0

    def test_measurement_no_regex_match(self, parser):
        """MEASUREMENT with unparseable first line should be skipped."""
        content = '''
/begin MEASUREMENT
    garbage line with no quotes
/end MEASUREMENT
'''
        result = parser.parse_string(content)
        assert result.success
        assert len(result.data.measurements) == 0

    def test_compu_method_empty_block(self, parser):
        """Empty COMPU_METHOD block should be skipped."""
        content = '/begin COMPU_METHOD\n/end COMPU_METHOD'
        result = parser.parse_string(content)
        assert result.success
        assert len(result.data.compu_methods) == 0

    def test_compu_method_no_regex_match(self, parser):
        """COMPU_METHOD with unparseable first line should be skipped."""
        content = '''
/begin COMPU_METHOD
    no_description_no_type
/end COMPU_METHOD
'''
        result = parser.parse_string(content)
        assert result.success
        assert len(result.data.compu_methods) == 0

    def test_compu_method_no_coeffs(self, parser):
        """COMPU_METHOD without COEFFS should parse with empty coeffs list."""
        content = '''
/begin COMPU_METHOD
    CM_Identical "Identity" IDENTICAL "%8.2" "rpm"
/end COMPU_METHOD
'''
        result = parser.parse_string(content)
        assert result.success
        cm = result.data.compu_methods[0]
        assert cm.coeffs == []
        assert cm.formula == ""

    def test_compu_method_with_formula(self, parser):
        """COMPU_METHOD with FORMULA should parse formula correctly."""
        content = '''
/begin COMPU_METHOD
    CM_Formula "Formula" FORM "%8.2" "kPa"
    FORMULA "X1 * 2.5 + 100"
/end COMPU_METHOD
'''
        result = parser.parse_string(content)
        assert result.success
        cm = result.data.compu_methods[0]
        assert cm.formula == "X1 * 2.5 + 100"

    def test_mixed_valid_and_malformed(self, parser):
        """Valid and malformed blocks should coexist — valid ones still parsed."""
        content = '''
/begin CHARACTERISTIC
    /end CHARACTERISTIC
/begin CHARACTERISTIC
    GoodParam "Good Parameter" VALUE 0x1000 RL1 0 100
/end CHARACTERISTIC
/begin MEASUREMENT
    bad line
/end MEASUREMENT
/begin MEASUREMENT
    GoodSig "Good Signal" UBYTE CM1 0 0 0 255
/end MEASUREMENT
'''
        result = parser.parse_string(content)
        assert result.success
        # First characteristic is empty (skipped), second is valid
        assert len(result.data.characteristics) == 1
        assert result.data.characteristics[0].name == "GoodParam"
        # First measurement is malformed (skipped), second is valid
        assert len(result.data.measurements) == 1
        assert result.data.measurements[0].name == "GoodSig"

    def test_file_not_found(self, parser):
        """Non-existent file should return failure."""
        result = parser.parse(Path("/nonexistent/file.a2l"))
        assert not result.success
        assert any("not found" in e.lower() for e in result.errors)


# ── Validation ────────────────────────────────────────────────────────────────


class TestA2LParserValidation:

    def test_validate_missing_begin(self, parser, tmp_path):
        f = tmp_path / "bad.a2l"
        f.write_text("no begin blocks here", encoding="utf-8")
        errors = parser.validate(f)
        assert any("begin" in e.lower() for e in errors)

    def test_validate_valid_file(self, parser, tmp_path):
        f = tmp_path / "good.a2l"
        f.write_text('/begin CHARACTERISTIC\n/end CHARACTERISTIC', encoding="utf-8")
        errors = parser.validate(f)
        assert len(errors) == 0


# ── Serialisation round-trip ──────────────────────────────────────────────────


class TestA2LParserSerialisation:

    def test_to_dict_contains_all_fields(self, parser):
        from core.parsers.a2l_parser import a2l_data_to_dict
        content = '''
/begin CHARACTERISTIC
    EngSpeed "Engine Speed" VALUE 0x1000 RL_Speed 0.0 5000.0
    COMPU_METHOD "CM_Speed"
    UNIT "rpm"
    LOWER_LIMIT 0.0 UPPER_LIMIT 8000.0
/end CHARACTERISTIC
/begin MEASUREMENT
    ThrottlePos "Throttle Position" UBYTE CM_Throttle 0 0.0 0.0 100.0
/end MEASUREMENT
/begin COMPU_METHOD
    CM_Speed "Speed conversion" RAT_FUNC "%8.2" "rpm"
    COEFFS 0 1 0 0 0 1
/end COMPU_METHOD
'''
        result = parser.parse_string(content)
        assert result.success
        d = a2l_data_to_dict(result.data)
        assert "characteristics" in d
        assert "measurements" in d
        assert "compu_methods" in d
        assert len(d["characteristics"]) == 1
        assert d["characteristics"][0]["name"] == "EngSpeed"
        assert d["characteristics"][0]["address"] == "0x1000"
        assert len(d["measurements"]) == 1
        assert d["measurements"][0]["name"] == "ThrottlePos"
        assert len(d["compu_methods"]) == 1
        assert d["compu_methods"][0]["coeffs"] == [0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
