"""Tests for DBC parser."""

import pytest
from pathlib import Path

from core.parsers.dbc_parser import (
    DBCParser, DBCData, MessageDef, SignalDef,
    dbc_data_to_dict, dbc_data_from_dict,
)


# ── Sample DBC content ──────────────────────────────────────────────────────

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


@pytest.fixture
def dbc_parser():
    return DBCParser()


@pytest.fixture
def sample_dbc_file(tmp_path):
    file_path = tmp_path / "test.dbc"
    file_path.write_text(SAMPLE_DBC, encoding="utf-8")
    return file_path


class TestDBCParser:

    def test_supported_extensions(self, dbc_parser):
        assert dbc_parser.supported_extensions() == [".dbc"]

    def test_parse_file(self, dbc_parser, sample_dbc_file):
        result = dbc_parser.parse(sample_dbc_file)
        assert result.success
        assert isinstance(result.data, DBCData)
        assert result.data.source_path == str(sample_dbc_file)

    def test_parse_string(self, dbc_parser):
        result = dbc_parser.parse_string(SAMPLE_DBC)
        assert result.success
        assert isinstance(result.data, DBCData)

    def test_message_count(self, dbc_parser):
        result = dbc_parser.parse_string(SAMPLE_DBC)
        data: DBCData = result.data
        assert len(data.messages) == 3

    def test_message_details(self, dbc_parser):
        result = dbc_parser.parse_string(SAMPLE_DBC)
        data: DBCData = result.data

        msg = data.messages[0]
        assert msg.name == "VCU_Status"
        assert msg.id == 0x100
        assert msg.dlc == 8
        assert msg.sender == "VCU"

    def test_signal_count(self, dbc_parser):
        result = dbc_parser.parse_string(SAMPLE_DBC)
        data: DBCData = result.data

        vc_status = data.messages[0]
        assert len(vc_status.signals) == 4

        vc_torque = data.messages[1]
        assert len(vc_torque.signals) == 3

        vc_hv = data.messages[2]
        assert len(vc_hv.signals) == 3

    def test_signal_properties(self, dbc_parser):
        result = dbc_parser.parse_string(SAMPLE_DBC)
        data: DBCData = result.data

        sig = data.messages[0].signals[2]  # VCU_SOC
        assert sig.name == "VCU_SOC"
        assert sig.start_bit == 8
        assert sig.bit_length == 8
        assert sig.factor == 0.5
        assert sig.offset == 0.0
        assert sig.minimum == 0.0
        assert sig.maximum == 127.5
        assert sig.unit == "%"
        assert sig.byte_order == "little_endian"
        assert sig.value_type == "unsigned"
        assert "BMS" in sig.receivers
        assert "MCU" in sig.receivers

    def test_signal_with_offset(self, dbc_parser):
        result = dbc_parser.parse_string(SAMPLE_DBC)
        data: DBCData = result.data

        sig = data.messages[1].signals[0]  # Tq_Request
        assert sig.name == "Tq_Request"
        assert sig.factor == 0.1
        assert sig.offset == -500.0

    def test_value_descriptions(self, dbc_parser):
        result = dbc_parser.parse_string(SAMPLE_DBC)
        data: DBCData = result.data

        sig = data.messages[0].signals[0]  # VCU_PowerMode
        assert 0 in sig.value_descriptions
        assert sig.value_descriptions[0] == "PowerOff"
        assert sig.value_descriptions[2] == "PowerOn"
        assert sig.value_descriptions[15] == "Fault"

    def test_nonexistent_file(self, dbc_parser, tmp_path):
        result = dbc_parser.parse(tmp_path / "nonexistent.dbc")
        assert not result.success
        assert len(result.errors) > 0

    def test_validate(self, dbc_parser, sample_dbc_file):
        errors = dbc_parser.validate(sample_dbc_file)
        # Our sample DBC should be valid
        assert len(errors) == 0


class TestDBCDataSerialisation:

    def test_roundtrip(self, dbc_parser):
        original = dbc_parser.parse_string(SAMPLE_DBC).data
        as_dict = dbc_data_to_dict(original)
        restored = dbc_data_from_dict(as_dict)

        assert restored.version == original.version
        assert len(restored.messages) == len(original.messages)
        assert restored.messages[0].name == original.messages[0].name
        assert restored.messages[0].id == original.messages[0].id
        assert len(restored.messages[0].signals) == len(original.messages[0].signals)
        assert restored.messages[0].signals[0].name == original.messages[0].signals[0].name

    def test_dict_keys(self, dbc_parser):
        data = dbc_parser.parse_string(SAMPLE_DBC).data
        d = dbc_data_to_dict(data)
        assert "version" in d
        assert "messages" in d
        assert "nodes" in d
        assert "value_tables" in d
        assert "source_path" in d
