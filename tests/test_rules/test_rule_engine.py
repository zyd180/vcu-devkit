"""Tests for core.rules.engine — validation rule engine."""

import pytest

from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef
from core.parsers.arxml_parser import (
    ARXMLData, SWCDef, PortDef, RunnableDef, DataElementDef,
    SenderReceiverInterface, CompositionDef, CompositionConnector,
    PortDirection, AUTOSARVersion,
)
from core.rules.engine import RuleEngine, Severity


def _sig(name, start_bit=0, bit_length=8, byte_order="little_endian",
         value_type="unsigned", factor=1.0, offset=0.0, minimum=0.0, maximum=255.0):
    return SignalDef(
        name=name, start_bit=start_bit, bit_length=bit_length,
        byte_order=byte_order, value_type=value_type,
        factor=factor, offset=offset, minimum=minimum, maximum=maximum,
        unit="", comment="", receivers=[], value_descriptions={}, mux=None,
    )


def _msg(name, msg_id=0x100, dlc=8, sender="VCU", signals=None):
    return MessageDef(
        id=msg_id, name=name, dlc=dlc, sender=sender,
        signals=signals or [], comment="", is_extended=False,
    )


def _dbc(messages):
    return DBCData(
        version="v1", messages=messages, nodes=[],
        value_tables={}, comments={}, attributes={}, source_path="<test>",
    )


def _arxml(swcs=None, interfaces=None, compositions=None):
    return ARXMLData(
        autosar_version=AUTOSARVersion.AUTOSAR_4_2,
        package_name="Test", swcs=swcs or [], interfaces=interfaces or [],
        data_types=[], compositions=compositions or [], source_path="<test>",
    )


class TestRuleEngine:

    def setup_method(self):
        self.engine = RuleEngine()

    # ── DBC rules ───────────────────────────────────────────────────────────

    def test_signal_overlap_detected(self):
        sig1 = _sig("A", start_bit=0, bit_length=8)
        sig2 = _sig("B", start_bit=4, bit_length=8)  # overlaps at bits 4-7
        results = self.engine.check_dbc(_dbc([_msg("M", signals=[sig1, sig2])]))
        ids = [r.rule_id for r in results]
        assert "DBC_OVERLAP" in ids

    def test_no_overlap(self):
        sig1 = _sig("A", start_bit=0, bit_length=8)
        sig2 = _sig("B", start_bit=8, bit_length=8)
        results = self.engine.check_dbc(_dbc([_msg("M", signals=[sig1, sig2])]))
        ids = [r.rule_id for r in results]
        assert "DBC_OVERLAP" not in ids

    def test_mixed_endian_warning(self):
        sig1 = _sig("A", byte_order="little_endian")
        sig2 = _sig("B", byte_order="big_endian")
        results = self.engine.check_dbc(_dbc([_msg("M", signals=[sig1, sig2])]))
        ids = [r.rule_id for r in results]
        assert "DBC_MIXED_ENDIAN" in ids

    def test_value_range_below(self):
        sig = _sig("S", minimum=-10.0, factor=1.0, offset=0.0)
        results = self.engine.check_dbc(_dbc([_msg("M", signals=[sig])]))
        ids = [r.rule_id for r in results]
        assert "DBC_RANGE_BELOW" in ids

    def test_value_range_above(self):
        sig = _sig("S", bit_length=8, maximum=999.0, factor=1.0, offset=0.0)
        results = self.engine.check_dbc(_dbc([_msg("M", signals=[sig])]))
        ids = [r.rule_id for r in results]
        assert "DBC_RANGE_ABOVE" in ids

    def test_unsigned_negative_offset(self):
        sig = _sig("S", value_type="unsigned", offset=-10.0)
        results = self.engine.check_dbc(_dbc([_msg("M", signals=[sig])]))
        ids = [r.rule_id for r in results]
        assert "DBC_UNSIGNED_NEG_OFFSET" in ids

    def test_invalid_message_name(self):
        results = self.engine.check_dbc(_dbc([_msg("Bad-Name!")]))
        ids = [r.rule_id for r in results]
        assert "DBC_NAME_INVALID" in ids

    def test_invalid_signal_name(self):
        results = self.engine.check_dbc(_dbc([_msg("M", signals=[_sig("bad.name")])]))
        ids = [r.rule_id for r in results]
        assert "DBC_NAME_INVALID" in ids

    def test_duplicate_ids(self):
        m1 = _msg("A", msg_id=0x100)
        m2 = _msg("B", msg_id=0x100)
        results = self.engine.check_dbc(_dbc([m1, m2]))
        ids = [r.rule_id for r in results]
        assert "DBC_DUP_ID" in ids

    def test_dlc_short(self):
        sig = _sig("S", start_bit=0, bit_length=16)
        results = self.engine.check_dbc(_dbc([_msg("M", dlc=1, signals=[sig])]))
        ids = [r.rule_id for r in results]
        assert "DBC_DLC_SHORT" in ids

    def test_clean_dbc_no_issues(self):
        sig = _sig("Valid_Signal", start_bit=0, bit_length=8)
        results = self.engine.check_dbc(_dbc([_msg("Valid_Msg", signals=[sig])]))
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    # ── ARXML rules ─────────────────────────────────────────────────────────

    def test_swc_invalid_name(self):
        swc = SWCDef(name="Bad-Name", category="ApplicationSoftwareComponent", description="desc",
                     runnables=[RunnableDef(name="Run", period_ms=10)])
        results = self.engine.check_arxml(_arxml(swcs=[swc]))
        ids = [r.rule_id for r in results]
        assert "ARXML_SWC_NAME" in ids

    def test_swc_no_description(self):
        swc = SWCDef(name="GoodName", category="ApplicationSoftwareComponent", description="",
                     runnables=[RunnableDef(name="Run", period_ms=10)])
        results = self.engine.check_arxml(_arxml(swcs=[swc]))
        ids = [r.rule_id for r in results]
        assert "ARXML_SWC_NO_DESC" in ids

    def test_duplicate_port_name(self):
        swc = SWCDef(
            name="SWC1", category="ApplicationSoftwareComponent", description="d",
            ports=[
                PortDef(name="P1", direction=PortDirection.PROVIDED, interface_ref="IF1"),
                PortDef(name="P1", direction=PortDirection.REQUIRED, interface_ref="IF2"),
            ],
        )
        results = self.engine.check_arxml(_arxml(swcs=[swc]))
        ids = [r.rule_id for r in results]
        assert "ARXML_DUP_PORT" in ids

    def test_orphan_interface(self):
        swc = SWCDef(
            name="SWC1", category="ApplicationSoftwareComponent", description="d",
            ports=[PortDef(name="P1", direction=PortDirection.PROVIDED, interface_ref="NonExistent")],
        )
        results = self.engine.check_arxml(_arxml(swcs=[swc]))
        ids = [r.rule_id for r in results]
        assert "ARXML_ORPHAN_IFACE" in ids

    def test_runnable_invalid_name(self):
        swc = SWCDef(
            name="SWC1", category="ApplicationSoftwareComponent", description="d",
            runnables=[RunnableDef(name="bad-name!", period_ms=10)],
        )
        results = self.engine.check_arxml(_arxml(swcs=[swc]))
        ids = [r.rule_id for r in results]
        assert "ARXML_RUN_NAME" in ids

    def test_empty_swc_no_runnables(self):
        swc = SWCDef(name="SWC1", category="ApplicationSoftwareComponent", description="d")
        results = self.engine.check_arxml(_arxml(swcs=[swc]))
        ids = [r.rule_id for r in results]
        assert "ARXML_NO_RUNNABLE" in ids

    def test_empty_swc_no_ports(self):
        swc = SWCDef(name="SWC1", category="ApplicationSoftwareComponent", description="d",
                     runnables=[RunnableDef(name="Run", period_ms=10)])
        results = self.engine.check_arxml(_arxml(swcs=[swc]))
        ids = [r.rule_id for r in results]
        assert "ARXML_NO_PORTS" in ids

    def test_duplicate_swc_names(self):
        swc1 = SWCDef(name="Dup", category="ApplicationSoftwareComponent", description="d",
                      runnables=[RunnableDef(name="R1", period_ms=10)])
        swc2 = SWCDef(name="Dup", category="ApplicationSoftwareComponent", description="d",
                      runnables=[RunnableDef(name="R2", period_ms=10)])
        results = self.engine.check_arxml(_arxml(swcs=[swc1, swc2]))
        ids = [r.rule_id for r in results]
        assert "ARXML_DUP_SWC" in ids

    def test_composition_missing_swc(self):
        comp = CompositionDef(name="C1", components=["NonExistent"], connectors=[])
        results = self.engine.check_arxml(_arxml(compositions=[comp]))
        ids = [r.rule_id for r in results]
        assert "ARXML_COMP_MISSING_SWC" in ids

    def test_composition_unmatched_required(self):
        swc = SWCDef(
            name="SWC1", category="ApplicationSoftwareComponent", description="d",
            ports=[PortDef(name="R1", direction=PortDirection.REQUIRED, interface_ref="IF1")],
            runnables=[RunnableDef(name="Run", period_ms=10)],
        )
        comp = CompositionDef(name="C1", components=["SWC1"], connectors=[])
        results = self.engine.check_arxml(_arxml(swcs=[swc], compositions=[comp]))
        ids = [r.rule_id for r in results]
        assert "ARXML_UNMATCHED_REQUIRED" in ids

    def test_clean_arxml_no_issues(self):
        iface = SenderReceiverInterface(name="IF1", data_elements=[
            DataElementDef(name="E1", type_ref="float32"),
        ])
        swc = SWCDef(
            name="Valid_SWC", category="ApplicationSoftwareComponent", description="A valid SWC",
            ports=[PortDef(name="P1", direction=PortDirection.PROVIDED, interface_ref="IF1")],
            runnables=[RunnableDef(name="Run_10ms", period_ms=10)],
        )
        results = self.engine.check_arxml(_arxml(swcs=[swc], interfaces=[iface]))
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_big_endian_overlap(self):
        """Big endian signals use descending bit positions."""
        sig1 = _sig("A", start_bit=15, bit_length=8, byte_order="big_endian")
        sig2 = _sig("B", start_bit=7, bit_length=8, byte_order="big_endian")
        results = self.engine.check_dbc(_dbc([_msg("M", signals=[sig1, sig2])]))
        # No overlap: A occupies bits 15-8, B occupies bits 7-0
        ids = [r.rule_id for r in results]
        assert "DBC_OVERLAP" not in ids
