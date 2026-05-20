"""Tests for core.generators.rte_generator — AUTOSAR RTE header generation."""

import pytest
from pathlib import Path

from core.parsers.arxml_parser import (
    ARXMLData, SWCDef, PortDef, PortDirection, RunnableDef,
    DataElementDef, SenderReceiverInterface, ClientServerInterface,
    DataTypeDef, AUTOSARVersion,
)
from core.generators.rte_generator import RTEGenerator


def _make_swc(name="VcuPowerMgr", category="APPLICATION", ports=None, runnables=None):
    return SWCDef(
        name=name, category=category, description="",
        ports=ports or [], runnables=runnables or [],
    )


def _make_port(name, direction, interface_ref):
    return PortDef(name=name, direction=direction, interface_ref=interface_ref)


def _make_runnable(name, period_ms=10):
    return RunnableDef(name=name, period_ms=period_ms)


def _make_arxml(swcs=None, interfaces=None, data_types=None):
    return ARXMLData(
        autosar_version=AUTOSARVersion.AUTOSAR_4_4,
        package_name="VCU",
        swcs=swcs or [],
        interfaces=interfaces or [],
        data_types=data_types or [],
        compositions=[],
        source_path="<test>",
    )


class TestRTEGenerator:

    def setup_method(self):
        self.gen = RTEGenerator()

    def test_generate_success(self, tmp_path):
        data = _make_arxml(swcs=[_make_swc()])
        result = self.gen.generate(data, tmp_path)
        assert result.success
        assert len(result.output_files) >= 1

    def test_creates_files(self, tmp_path):
        data = _make_arxml(swcs=[_make_swc()])
        result = self.gen.generate(data, tmp_path)
        for f in result.output_files:
            assert f.exists()
            assert f.stat().st_size > 0

    def test_type_header_created(self, tmp_path):
        data = _make_arxml(swcs=[_make_swc()])
        result = self.gen.generate(data, tmp_path)
        type_file = tmp_path / "Rte_Type.h"
        assert type_file in result.output_files

    def test_swc_header_created(self, tmp_path):
        data = _make_arxml(swcs=[_make_swc("VcuPowerMgr")])
        result = self.gen.generate(data, tmp_path)
        swc_file = tmp_path / "Rte_VcuPowerMgr.h"
        assert swc_file in result.output_files

    def test_empty_data(self, tmp_path):
        data = _make_arxml()
        result = self.gen.generate(data, tmp_path)
        assert result.success
        assert len(result.output_files) == 1  # only Rte_Type.h

    def test_multiple_swcs(self, tmp_path):
        data = _make_arxml(swcs=[_make_swc("SWC_A"), _make_swc("SWC_B")])
        result = self.gen.generate(data, tmp_path)
        assert result.success
        assert (tmp_path / "Rte_SWC_A.h").exists()
        assert (tmp_path / "Rte_SWC_B.h").exists()


# ── Type header content ─────────────────────────────────────────────────────


class TestRTETypeHeader:

    def setup_method(self):
        self.gen = RTEGenerator()

    def test_contains_guard(self, tmp_path):
        data = _make_arxml(swcs=[_make_swc()])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_Type.h").read_text(encoding="utf-8")
        assert "#ifndef RTE_TYPE_H" in content
        assert "#define RTE_TYPE_H" in content
        assert "#endif" in content

    def test_contains_std_return_type(self, tmp_path):
        data = _make_arxml(swcs=[_make_swc()])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_Type.h").read_text(encoding="utf-8")
        assert "Std_ReturnType" in content
        assert "E_OK" in content
        assert "E_NOT_OK" in content

    def test_contains_base_types(self, tmp_path):
        data = _make_arxml(swcs=[_make_swc()])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_Type.h").read_text(encoding="utf-8")
        assert "typedef uint8_t" in content
        assert "typedef uint16_t" in content
        assert "typedef float" in content

    def test_application_data_types(self, tmp_path):
        data = _make_arxml(
            data_types=[
                DataTypeDef(name="Speed_T", category="VALUE", encoding="uint16", min_value=0, max_value=300),
                DataTypeDef(name="Voltage_T", category="VALUE", encoding="float32"),
            ]
        )
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_Type.h").read_text(encoding="utf-8")
        assert "typedef uint16 Rte_DT_Speed_T;" in content
        assert "RTE_DT_Speed_T_MIN" in content
        assert "RTE_DT_Speed_T_MAX" in content
        assert "typedef float32 Rte_DT_Voltage_T;" in content


# ── SWC header content ──────────────────────────────────────────────────────


class TestRTESWCHeader:

    def setup_method(self):
        self.gen = RTEGenerator()

    def test_contains_guard(self, tmp_path):
        data = _make_arxml(swcs=[_make_swc("MySWC")])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_MySWC.h").read_text(encoding="utf-8")
        assert "#ifndef RTE_MYSWC_H" in content
        assert "#define RTE_MYSWC_H" in content

    def test_includes_rte_type(self, tmp_path):
        data = _make_arxml(swcs=[_make_swc()])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_VcuPowerMgr.h").read_text(encoding="utf-8")
        assert '#include "Rte_Type.h"' in content

    def test_provided_port_write_api(self, tmp_path):
        iface = SenderReceiverInterface(
            name="I_PowerStatus",
            data_elements=[DataElementDef(name="PowerMode", type_ref="uint8")],
        )
        port = _make_port("P_PowerStatus", PortDirection.PROVIDED, "I_PowerStatus")
        swc = _make_swc("VcuPowerMgr", ports=[port])
        data = _make_arxml(swcs=[swc], interfaces=[iface])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_VcuPowerMgr.h").read_text(encoding="utf-8")
        assert "Rte_Write_VcuPowerMgr_P_PowerStatus_PowerMode(uint8 data)" in content

    def test_required_port_read_api(self, tmp_path):
        iface = SenderReceiverInterface(
            name="I_BmsStatus",
            data_elements=[DataElementDef(name="Voltage", type_ref="float32")],
        )
        port = _make_port("R_BmsStatus", PortDirection.REQUIRED, "I_BmsStatus")
        swc = _make_swc("VcuPowerMgr", ports=[port])
        data = _make_arxml(swcs=[swc], interfaces=[iface])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_VcuPowerMgr.h").read_text(encoding="utf-8")
        assert "Rte_Read_VcuPowerMgr_R_BmsStatus_Voltage(float32* data)" in content

    def test_client_server_port_api(self, tmp_path):
        iface = ClientServerInterface(
            name="I_DiagService",
            operations=["ReadDTC", "ClearDTC"],
        )
        port = _make_port("PP_Diag", PortDirection.PROVIDED, "I_DiagService")
        swc = _make_swc("DiagMgr", ports=[port])
        data = _make_arxml(swcs=[swc], interfaces=[iface])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_DiagMgr.h").read_text(encoding="utf-8")
        assert "Rte_Call_DiagMgr_PP_Diag_ReadDTC(void)" in content
        assert "Rte_Call_DiagMgr_PP_Diag_ClearDTC(void)" in content

    def test_runnable_declarations(self, tmp_path):
        swc = _make_swc("VcuPowerMgr", runnables=[
            _make_runnable("Init", period_ms=None),
            _make_runnable("Run_10ms", period_ms=10),
        ])
        data = _make_arxml(swcs=[swc])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_VcuPowerMgr.h").read_text(encoding="utf-8")
        assert "void Rte_Run_VcuPowerMgr_Init(void);" in content
        assert "void Rte_Run_VcuPowerMgr_Run_10ms(void);" in content
        assert "period: 10ms" in content
        assert "event-triggered" in content

    def test_unresolved_interface(self, tmp_path):
        port = _make_port("P_Orphan", PortDirection.PROVIDED, "NonExistent")
        swc = _make_swc("MySWC", ports=[port])
        data = _make_arxml(swcs=[swc])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_MySWC.h").read_text(encoding="utf-8")
        assert "not resolved" in content

    def test_multiple_data_elements(self, tmp_path):
        iface = SenderReceiverInterface(
            name="I_Status",
            data_elements=[
                DataElementDef(name="PowerMode", type_ref="uint8"),
                DataElementDef(name="SOC", type_ref="float32"),
            ],
        )
        port = _make_port("P_Status", PortDirection.PROVIDED, "I_Status")
        swc = _make_swc("VcuPowerMgr", ports=[port])
        data = _make_arxml(swcs=[swc], interfaces=[iface])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_VcuPowerMgr.h").read_text(encoding="utf-8")
        assert "PowerMode" in content
        assert "SOC" in content

    def test_type_ref_resolution(self, tmp_path):
        """Type ref with path separator should resolve to last segment."""
        iface = SenderReceiverInterface(
            name="I_WithData",
            data_elements=[DataElementDef(name="Speed", type_ref="/DataTypes/Speed_T")],
        )
        port = _make_port("P_Data", PortDirection.PROVIDED, "I_WithData")
        swc = _make_swc("MySWC", ports=[port])
        data = _make_arxml(swcs=[swc], interfaces=[iface])
        self.gen.generate(data, tmp_path)
        content = (tmp_path / "Rte_MySWC.h").read_text(encoding="utf-8")
        assert "Rte_DT_Speed_T" in content
