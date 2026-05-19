"""Tests for core.generators.c_generator — C code generation."""

import pytest
from pathlib import Path

from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef
from core.generators.c_generator import CANCodeGenerator


def _sig(name, start_bit=0, bit_length=8, byte_order="little_endian",
         value_type="unsigned", factor=1.0, offset=0.0, minimum=0.0,
         maximum=255.0, unit="", comment="", receivers=None):
    return SignalDef(
        name=name, start_bit=start_bit, bit_length=bit_length,
        byte_order=byte_order, value_type=value_type,
        factor=factor, offset=offset, minimum=minimum, maximum=maximum,
        unit=unit, comment=comment, receivers=receivers or [],
        value_descriptions={}, mux=None,
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


class TestCANCodeGenerator:

    def setup_method(self):
        self.gen = CANCodeGenerator()

    def test_generate_success(self, tmp_path):
        data = _dbc([_msg("M1", signals=[_sig("S1")])])
        result = self.gen.generate(data, tmp_path)
        assert result.success
        assert len(result.output_files) >= 1

    def test_generate_creates_files(self, tmp_path):
        data = _dbc([_msg("M1", signals=[_sig("S1")])])
        result = self.gen.generate(data, tmp_path)
        for f in result.output_files:
            assert f.exists()

    def test_header_contains_guard(self, tmp_path):
        data = _dbc([_msg("M1", signals=[_sig("S1")])])
        result = self.gen.generate(data, tmp_path)
        header = [f for f in result.output_files if f.suffix == ".h"][0]
        content = header.read_text(encoding="utf-8")
        assert "#ifndef" in content or "#pragma once" in content

    def test_signed_signal(self, tmp_path):
        sig = _sig("SignedSig", bit_length=16, value_type="signed", factor=0.1, offset=-40)
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        assert result.success

    def test_big_endian_signal(self, tmp_path):
        sig = _sig("BESig", start_bit=7, bit_length=8, byte_order="big_endian")
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        assert result.success

    def test_scaled_signal(self, tmp_path):
        sig = _sig("Scaled", factor=0.01, offset=-50, minimum=-50, maximum=200)
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        header = [f for f in result.output_files if f.suffix == ".h"][0]
        content = header.read_text(encoding="utf-8")
        assert "Scaled" in content

    def test_single_bit_signal(self, tmp_path):
        sig = _sig("Flag", bit_length=1)
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        assert result.success

    def test_empty_messages(self, tmp_path):
        data = _dbc([])
        result = self.gen.generate(data, tmp_path)
        assert result.success

    def test_multiple_messages(self, tmp_path):
        data = _dbc([
            _msg("M1", signals=[_sig("S1")]),
            _msg("M2", signals=[_sig("S2", bit_length=16)]),
        ])
        result = self.gen.generate(data, tmp_path)
        assert result.success

    def test_mux_signal(self, tmp_path):
        sig = _sig("MuxSig")
        sig.mux = {"mux_type": "multiplexor"}
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        assert result.success
