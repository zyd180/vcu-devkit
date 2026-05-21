"""Shared test fixtures and configuration."""

import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


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
def sample_dbc_file(tmp_path):
    """Write SAMPLE_DBC to a temp file and return its Path."""
    dbc_file = tmp_path / "test.dbc"
    dbc_file.write_text(SAMPLE_DBC, encoding="utf-8")
    return dbc_file


@pytest.fixture
def sample_dbc_data(sample_dbc_file):
    """Parse SAMPLE_DBC and return DBCData."""
    from core.parsers.dbc_parser import DBCParser

    parser = DBCParser()
    result = parser.parse(sample_dbc_file)
    assert result.success, f"Failed to parse sample DBC: {result.errors}"
    return result.data


@pytest.fixture
def db_manager(tmp_path):
    """Return an initialised DatabaseManager using a temp SQLite file."""
    from core.db.manager import DatabaseManager

    db_path = tmp_path / "test.db"
    mgr = DatabaseManager(db_path)
    mgr.init()
    yield mgr
    DatabaseManager._initialized_paths.discard(str(db_path))
