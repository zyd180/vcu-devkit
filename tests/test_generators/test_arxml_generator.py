"""Tests for core.generators.arxml_generator — ARXML output."""

from lxml import etree

from core.generators.arxml_generator import ARXMLGenerator
from core.parsers.arxml_parser import (
    ARXMLData,
    AUTOSARVersion,
    ClientServerInterface,
    CompositionConnector,
    CompositionDef,
    DataElementDef,
    PortDef,
    PortDirection,
    RunnableDef,
    SenderReceiverInterface,
    SWCDef,
)


def _make_arxml_data(**overrides):
    defaults = dict(
        autosar_version=AUTOSARVersion.AUTOSAR_4_2,
        package_name="TestPkg",
        swcs=[],
        interfaces=[],
        data_types=[],
        compositions=[],
        source_path="<test>",
    )
    defaults.update(overrides)
    return ARXMLData(**defaults)


# ── Basic generation ──────────────────────────────────────────────────────────


class TestARXMLGenerator:
    def setup_method(self):
        self.gen = ARXMLGenerator()

    def test_generate_string_contains_autosar_root(self):
        data = _make_arxml_data()
        xml = self.gen.generate_string(data)
        assert "AUTOSAR" in xml

    def test_generate_string_contains_package(self):
        data = _make_arxml_data(package_name="MyPkg")
        xml = self.gen.generate_string(data)
        assert "MyPkg" in xml

    def test_write_sr_interface(self):
        iface = SenderReceiverInterface(
            name="IF_Voltage",
            data_elements=[DataElementDef(name="Voltage", type_ref="float32")],
        )
        data = _make_arxml_data(interfaces=[iface])
        xml = self.gen.generate_string(data)
        assert "SENDER-RECEIVER-INTERFACE" in xml
        assert "IF_Voltage" in xml

    def test_write_cs_interface(self):
        iface = ClientServerInterface(name="IF_Cmd", operations=["Start", "Stop"])
        data = _make_arxml_data(interfaces=[iface])
        xml = self.gen.generate_string(data)
        assert "CLIENT-SERVER-INTERFACE" in xml
        assert "Start" in xml

    def test_write_swc_with_ports(self):
        swc = SWCDef(
            name="VCU_App",
            category="ApplicationSoftwareComponent",
            description="VCU application",
            ports=[
                PortDef(name="P_Status", direction=PortDirection.PROVIDED, interface_ref="IF_Status"),
                PortDef(name="R_Cmd", direction=PortDirection.REQUIRED, interface_ref="IF_Cmd"),
            ],
        )
        data = _make_arxml_data(swcs=[swc])
        xml = self.gen.generate_string(data)
        assert "APPLICATION-SW-COMPONENT-TYPE" in xml
        assert "P-PORT-PROTOTYPE" in xml
        assert "R-PORT-PROTOTYPE" in xml

    def test_write_swc_with_runnables(self):
        swc = SWCDef(
            name="VCU_App",
            category="ApplicationSoftwareComponent",
            description="",
            runnables=[
                RunnableDef(name="Run_10ms", period_ms=10, min_start_interval=0),
            ],
        )
        data = _make_arxml_data(swcs=[swc])
        xml = self.gen.generate_string(data)
        assert "RUNNABLE-ENTITY" in xml
        assert "Run_10ms" in xml
        assert "TIMING-EVENT" in xml

    def test_write_composition_with_connectors(self):
        comp = CompositionDef(
            name="VCU_Comp",
            components=["SWC_A", "SWC_B"],
            connectors=[
                CompositionConnector(
                    provider_component="SWC_A",
                    provider_port="P_Out",
                    requester_component="SWC_B",
                    requester_port="R_In",
                    connector_type="assembly",
                ),
                CompositionConnector(
                    provider_component="SWC_A",
                    provider_port="P_Ext",
                    requester_component="(composition)",
                    requester_port="ExtPort",
                    connector_type="delegation",
                ),
            ],
        )
        data = _make_arxml_data(compositions=[comp])
        xml = self.gen.generate_string(data)
        assert "COMPOSITION-SW-COMPONENT-TYPE" in xml
        assert "ASSEMBLY-SW-CONNECTOR" in xml
        assert "DELEGATION-SW-CONNECTOR" in xml
        assert "SWC_A" in xml

    def test_write_swc_service_category(self):
        swc = SWCDef(name="Svc", category="ServiceComponent", description="")
        data = _make_arxml_data(swcs=[swc])
        xml = self.gen.generate_string(data)
        assert "SERVICE-SW-COMPONENT-TYPE" in xml

    def test_write_swc_complex_device_driver(self):
        swc = SWCDef(name="CDD", category="ComplexDeviceDriver", description="")
        data = _make_arxml_data(swcs=[swc])
        xml = self.gen.generate_string(data)
        assert "COMPLEX-DEVICE-DRIVER-SW-COMPONENT-TYPE" in xml

    def test_eb_tresos_target(self):
        gen = ARXMLGenerator(target_tool="ebtresos")
        swc = SWCDef(name="Svc", category="ServiceComponent", description="")
        data = _make_arxml_data(swcs=[swc])
        xml = gen.generate_string(data)
        assert "SERVICE-SW-COMPONENT-TYPE" in xml


# ── File generation ───────────────────────────────────────────────────────────


class TestARXMLGeneratorFile:
    def test_generate_to_file(self, tmp_path):
        gen = ARXMLGenerator()
        data = _make_arxml_data()
        out = tmp_path / "test.arxml"
        result = gen.generate(data, out)
        assert result.success
        assert not result.errors
        assert out.exists()

    def test_generated_file_is_valid_xml(self, tmp_path):
        gen = ARXMLGenerator()
        data = _make_arxml_data(
            swcs=[
                SWCDef(name="TestSWC", category="ApplicationSoftwareComponent", description="test"),
            ]
        )
        out = tmp_path / "test.arxml"
        gen.generate(data, out)
        tree = etree.parse(str(out))
        root = tree.getroot()
        assert "AUTOSAR" in root.tag
