"""Tests for core.generators.capl_generator — CAPL code generation."""

import pytest
from pathlib import Path

from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef
from core.generators.capl_generator import CAPLGenerator


def _make_signal(name, start_bit=0, bit_length=8, byte_order="little_endian",
                 value_type="unsigned", factor=1.0, offset=0.0, minimum=0.0,
                 maximum=255.0, unit="", comment="", receivers=None):
    return SignalDef(
        name=name, start_bit=start_bit, bit_length=bit_length,
        byte_order=byte_order, value_type=value_type,
        factor=factor, offset=offset, minimum=minimum, maximum=maximum,
        unit=unit, comment=comment, receivers=receivers or [],
        value_descriptions={}, mux=None,
    )


def _make_message(name, msg_id=0x100, dlc=8, sender="VCU", signals=None):
    return MessageDef(
        id=msg_id, name=name, dlc=dlc, sender=sender,
        signals=signals or [], comment="", is_extended=False,
    )


def _make_dbc(messages):
    return DBCData(
        version="v1", messages=messages, nodes=[],
        value_tables={}, comments={}, attributes={}, source_path="<test>",
    )


# ── Generator tests ──────────────────────────────────────────────────────────

class TestCAPLGenerator:

    def setup_method(self):
        self.gen = CAPLGenerator()

    def test_generate_returns_result(self, tmp_path):
        data = _make_dbc([_make_message("M1", signals=[_make_signal("S1")])])
        result = self.gen.generate(data, tmp_path)
        assert result.success
        assert len(result.output_files) == 1

    def test_output_file_exists(self, tmp_path):
        data = _make_dbc([_make_message("M1")])
        result = self.gen.generate(data, tmp_path)
        assert result.output_files[0].exists()

    def test_contains_header(self, tmp_path):
        data = _make_dbc([_make_message("M1")])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "VCU DevKit" in content
        assert "DO NOT EDIT" in content

    def test_contains_global_variables(self, tmp_path):
        sig = _make_signal("VCU_PowerMode", bit_length=4)
        data = _make_dbc([_make_message("VCU_Status", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "VCU_PowerMode" in content

    def test_contains_timer(self, tmp_path):
        data = _make_dbc([_make_message("M1")])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "cyclicTimer" in content

    def test_contains_on_start(self, tmp_path):
        data = _make_dbc([_make_message("M1")])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "on start" in content

    def test_tx_message_block(self, tmp_path):
        """VCU-sender messages get TX blocks."""
        sig = _make_signal("S1")
        data = _make_dbc([_make_message("M1", sender="VCU", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "output(msg_M1)" in content

    def test_rx_handler(self, tmp_path):
        """Non-VCU messages get RX handlers."""
        sig = _make_signal("S1")
        data = _make_dbc([_make_message("M1", sender="BMS", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "on message" in content

    def test_empty_messages(self, tmp_path):
        data = _make_dbc([])
        result = self.gen.generate(data, tmp_path)
        assert result.success


# ── Type mapping tests ────────────────────────────────────────────────────────

class TestCAPLTypeMapping:

    def test_unsigned_byte(self):
        sig = _make_signal("S", bit_length=8, value_type="unsigned")
        assert CAPLGenerator._capl_type(sig) == "byte"

    def test_unsigned_word(self):
        sig = _make_signal("S", bit_length=16, value_type="unsigned")
        assert CAPLGenerator._capl_type(sig) == "word"

    def test_unsigned_dword(self):
        sig = _make_signal("S", bit_length=32, value_type="unsigned")
        assert CAPLGenerator._capl_type(sig) == "dword"

    def test_signed_byte(self):
        sig = _make_signal("S", bit_length=8, value_type="signed")
        assert CAPLGenerator._capl_type(sig) == "byte"

    def test_signed_int(self):
        sig = _make_signal("S", bit_length=16, value_type="signed")
        assert CAPLGenerator._capl_type(sig) == "int"

    def test_signed_long(self):
        sig = _make_signal("S", bit_length=32, value_type="signed")
        assert CAPLGenerator._capl_type(sig) == "long"

    def test_single_bit(self):
        sig = _make_signal("S", bit_length=1, value_type="unsigned")
        assert CAPLGenerator._capl_type(sig) == "byte"

    def test_capl_default(self):
        sig = _make_signal("S", value_type="unsigned")
        assert CAPLGenerator._capl_default(sig) == "0"

    def test_capl_default_signed(self):
        sig = _make_signal("S", value_type="signed")
        assert CAPLGenerator._capl_default(sig) == "0"
