"""Tests for ARXML parser."""

import pytest

from core.parsers.arxml_parser import (
    ARXMLData,
    ARXMLParser,
    AUTOSARVersion,
    PortDirection,
    SenderReceiverInterface,
    arxml_data_to_dict,
)

SAMPLE_ARXML = """\
<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR xmlns="http://autosar.org/schema/r4.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://autosar.org/schema/r4.0 AUTOSAR_00044.xsd">
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>VCU</SHORT-NAME>
      <ELEMENTS>
        <APPLICATION-SW-COMPONENT-TYPE>
          <SHORT-NAME>VCU_PowerMgmt</SHORT-NAME>
          <DESC>
            <L-2>Power management component</L-2>
          </DESC>
          <PORTS>
            <P-PORT-PROTOTYPE>
              <SHORT-NAME>PwrStatus_P</SHORT-NAME>
              <PROVIDED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE">/VCU/Interfaces/I_PwrStatus</PROVIDED-INTERFACE-TREF>
            </P-PORT-PROTOTYPE>
            <R-PORT-PROTOTYPE>
              <SHORT-NAME>BMS_Status_R</SHORT-NAME>
              <REQUIRED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE">/VCU/Interfaces/I_BMS_Status</REQUIRED-INTERFACE-TREF>
            </R-PORT-PROTOTYPE>
          </PORTS>
          <INTERNAL-BEHAVIORS>
            <SWC-INTERNAL-BEHAVIOR>
              <RUNNABLE-ENTITIES>
                <RUNNABLE-ENTITY>
                  <SHORT-NAME>RE_PowerOn</SHORT-NAME>
                  <MINIMUM-START-INTERVAL>0.01</MINIMUM-START-INTERVAL>
                </RUNNABLE-ENTITY>
                <RUNNABLE-ENTITY>
                  <SHORT-NAME>RE_PowerOff</SHORT-NAME>
                  <MINIMUM-START-INTERVAL>0.01</MINIMUM-START-INTERVAL>
                </RUNNABLE-ENTITY>
              </RUNNABLE-ENTITIES>
            </SWC-INTERNAL-BEHAVIOR>
          </INTERNAL-BEHAVIORS>
        </APPLICATION-SW-COMPONENT-TYPE>

        <APPLICATION-SW-COMPONENT-TYPE>
          <SHORT-NAME>VCU_DriveCtrl</SHORT-NAME>
          <PORTS>
            <P-PORT-PROTOTYPE>
              <SHORT-NAME>TorqueCmd_P</SHORT-NAME>
              <PROVIDED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE">/VCU/Interfaces/I_TorqueCmd</PROVIDED-INTERFACE-TREF>
            </P-PORT-PROTOTYPE>
          </PORTS>
          <INTERNAL-BEHAVIORS>
            <SWC-INTERNAL-BEHAVIOR>
              <RUNNABLE-ENTITIES>
                <RUNNABLE-ENTITY>
                  <SHORT-NAME>RE_TorqueCalc</SHORT-NAME>
                </RUNNABLE-ENTITY>
              </RUNNABLE-ENTITIES>
            </SWC-INTERNAL-BEHAVIOR>
          </INTERNAL-BEHAVIORS>
        </APPLICATION-SW-COMPONENT-TYPE>

        <SENDER-RECEIVER-INTERFACE>
          <SHORT-NAME>I_PwrStatus</SHORT-NAME>
          <DATA-ELEMENTS>
            <DATA-ELEMENT-PROTOTYPE>
              <SHORT-NAME>PowerMode</SHORT-NAME>
              <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">/VCU/DataTypes/uint8</TYPE-TREF>
            </DATA-ELEMENT-PROTOTYPE>
            <DATA-ELEMENT-PROTOTYPE>
              <SHORT-NAME>VCU_Ready</SHORT-NAME>
              <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">/VCU/DataTypes/boolean</TYPE-TREF>
            </DATA-ELEMENT-PROTOTYPE>
          </DATA-ELEMENTS>
        </SENDER-RECEIVER-INTERFACE>

        <SENDER-RECEIVER-INTERFACE>
          <SHORT-NAME>I_BMS_Status</SHORT-NAME>
          <DATA-ELEMENTS>
            <DATA-ELEMENT-PROTOTYPE>
              <SHORT-NAME>BattVoltage</SHORT-NAME>
              <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">/VCU/DataTypes/uint16</TYPE-TREF>
            </DATA-ELEMENT-PROTOTYPE>
          </DATA-ELEMENTS>
        </SENDER-RECEIVER-INTERFACE>

        <SENDER-RECEIVER-INTERFACE>
          <SHORT-NAME>I_TorqueCmd</SHORT-NAME>
          <DATA-ELEMENTS>
            <DATA-ELEMENT-PROTOTYPE>
              <SHORT-NAME>TorqueRequest</SHORT-NAME>
              <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">/VCU/DataTypes/sint16</TYPE-TREF>
            </DATA-ELEMENT-PROTOTYPE>
          </DATA-ELEMENTS>
        </SENDER-RECEIVER-INTERFACE>

        <APPLICATION-PRIMITIVE-DATA-TYPE>
          <SHORT-NAME>uint8</SHORT-NAME>
          <CATEGORY>VALUE</CATEGORY>
        </APPLICATION-PRIMITIVE-DATA-TYPE>

        <APPLICATION-PRIMITIVE-DATA-TYPE>
          <SHORT-NAME>uint16</SHORT-NAME>
          <CATEGORY>VALUE</CATEGORY>
        </APPLICATION-PRIMITIVE-DATA-TYPE>

        <APPLICATION-PRIMITIVE-DATA-TYPE>
          <SHORT-NAME>sint16</SHORT-NAME>
          <CATEGORY>VALUE</CATEGORY>
        </APPLICATION-PRIMITIVE-DATA-TYPE>

        <APPLICATION-PRIMITIVE-DATA-TYPE>
          <SHORT-NAME>boolean</SHORT-NAME>
          <CATEGORY>VALUE</CATEGORY>
        </APPLICATION-PRIMITIVE-DATA-TYPE>

        <COMPOSITION-SW-COMPONENT-TYPE>
          <SHORT-NAME>VCU_Composition</SHORT-NAME>
          <COMPONENTS>
            <SW-COMPONENT-PROTOTYPE>
              <SHORT-NAME>PowerMgmt_Inst</SHORT-NAME>
              <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE">/VCU/VCU_PowerMgmt</TYPE-TREF>
            </SW-COMPONENT-PROTOTYPE>
            <SW-COMPONENT-PROTOTYPE>
              <SHORT-NAME>DriveCtrl_Inst</SHORT-NAME>
              <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE">/VCU/VCU_DriveCtrl</TYPE-TREF>
            </SW-COMPONENT-PROTOTYPE>
          </COMPONENTS>
        </COMPOSITION-SW-COMPONENT-TYPE>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
"""


@pytest.fixture
def arxml_parser():
    return ARXMLParser()


@pytest.fixture
def sample_arxml_file(tmp_path):
    file_path = tmp_path / "test.arxml"
    file_path.write_text(SAMPLE_ARXML, encoding="utf-8")
    return file_path


class TestARXMLParser:
    def test_supported_extensions(self, arxml_parser):
        assert arxml_parser.supported_extensions() == [".arxml"]

    def test_parse_file(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        assert result.success
        assert isinstance(result.data, ARXMLData)

    def test_autosar_version(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        assert result.data.autosar_version == AUTOSARVersion.AUTOSAR_4_4

    def test_package_name(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        assert result.data.package_name == "VCU"

    def test_swc_count(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        assert len(result.data.swcs) == 2

    def test_swc_names(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        names = [s.name for s in result.data.swcs]
        assert "VCU_PowerMgmt" in names
        assert "VCU_DriveCtrl" in names

    def test_swc_category(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        pm = next(s for s in result.data.swcs if s.name == "VCU_PowerMgmt")
        assert pm.category == "ApplicationSoftwareComponent"

    def test_swc_description(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        pm = next(s for s in result.data.swcs if s.name == "VCU_PowerMgmt")
        assert pm.description == "Power management component"

    def test_swc_ports(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        pm = next(s for s in result.data.swcs if s.name == "VCU_PowerMgmt")
        assert len(pm.ports) == 2

        p_port = next(p for p in pm.ports if p.direction == PortDirection.PROVIDED)
        assert p_port.name == "PwrStatus_P"
        assert p_port.interface_ref == "I_PwrStatus"

        r_port = next(p for p in pm.ports if p.direction == PortDirection.REQUIRED)
        assert r_port.name == "BMS_Status_R"
        assert r_port.interface_ref == "I_BMS_Status"

    def test_swc_runnables(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        pm = next(s for s in result.data.swcs if s.name == "VCU_PowerMgmt")
        assert len(pm.runnables) == 2
        names = [r.name for r in pm.runnables]
        assert "RE_PowerOn" in names
        assert "RE_PowerOff" in names

    def test_interfaces(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        assert len(result.data.interfaces) == 3

        ps = next(i for i in result.data.interfaces if i.name == "I_PwrStatus")
        assert isinstance(ps, SenderReceiverInterface)
        assert len(ps.data_elements) == 2
        assert ps.data_elements[0].name == "PowerMode"
        assert ps.data_elements[0].type_ref == "uint8"

    def test_data_types(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        assert len(result.data.data_types) == 4
        names = [dt.name for dt in result.data.data_types]
        assert "uint8" in names
        assert "uint16" in names
        assert "sint16" in names
        assert "boolean" in names

    def test_compositions(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        assert len(result.data.compositions) == 1
        comp = result.data.compositions[0]
        assert comp.name == "VCU_Composition"
        assert len(comp.components) == 2

    def test_nonexistent_file(self, arxml_parser, tmp_path):
        result = arxml_parser.parse(tmp_path / "nonexistent.arxml")
        assert not result.success

    def test_validate(self, arxml_parser, sample_arxml_file):
        errors = arxml_parser.validate(sample_arxml_file)
        assert len(errors) == 0


class TestARXMLSerialisation:
    def test_to_dict(self, arxml_parser, sample_arxml_file):
        result = arxml_parser.parse(sample_arxml_file)
        d = arxml_data_to_dict(result.data)
        assert d["autosar_version"] == "4.4"
        assert d["package_name"] == "VCU"
        assert len(d["swcs"]) == 2
        assert d["swcs"][0]["name"] == "VCU_PowerMgmt"
        assert d["swcs"][0]["ports"][0]["name"] == "PwrStatus_P"
