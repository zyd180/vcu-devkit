"""Tests for core.generators.c_generator — C code generation."""

from core.generators.c_generator import CANCodeGenerator
from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef


def _sig(
    name,
    start_bit=0,
    bit_length=8,
    byte_order="little_endian",
    value_type="unsigned",
    factor=1.0,
    offset=0.0,
    minimum=0.0,
    maximum=255.0,
    unit="",
    comment="",
    receivers=None,
    value_descriptions=None,
):
    return SignalDef(
        name=name,
        start_bit=start_bit,
        bit_length=bit_length,
        byte_order=byte_order,
        value_type=value_type,
        factor=factor,
        offset=offset,
        minimum=minimum,
        maximum=maximum,
        unit=unit,
        comment=comment,
        receivers=receivers or [],
        value_descriptions=value_descriptions or {},
        mux=None,
    )


def _msg(name, msg_id=0x100, dlc=8, sender="VCU", signals=None):
    return MessageDef(
        id=msg_id,
        name=name,
        dlc=dlc,
        sender=sender,
        signals=signals or [],
        comment="",
        is_extended=False,
    )


def _dbc(messages):
    return DBCData(
        version="v1",
        messages=messages,
        nodes=[],
        value_tables={},
        comments={},
        attributes={},
        source_path="<test>",
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
        data = _dbc(
            [
                _msg("M1", signals=[_sig("S1")]),
                _msg("M2", signals=[_sig("S2", bit_length=16)]),
            ]
        )
        result = self.gen.generate(data, tmp_path)
        assert result.success

    def test_mux_signal(self, tmp_path):
        sig = _sig("MuxSig")
        sig.mux = {"mux_type": "multiplexor"}
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        assert result.success

    # ── P0: Big endian pack/unpack correctness ───────────────────────────

    def _get_func_body(self, content: str, func_name: str) -> str:
        """Extract function body from 'CAN_FuncName(' to the next 'static inline' or end."""
        marker = f"CAN_{func_name}"
        idx = content.find(marker)
        if idx == -1:
            return ""
        rest = content[idx:]
        # Find next 'static inline' or '#endif' as boundary
        end = len(rest)
        for boundary in ["static inline", "#endif"]:
            pos = rest.find(boundary, 10)
            if pos != -1 and pos < end:
                end = pos
        return rest[:end]

    def test_big_endian_pack_has_motorola_logic(self, tmp_path):
        """Big endian pack code must use cur_byte/cur_bit/shift (Motorola bit order)."""
        sig = _sig("BE_Sig", start_bit=7, bit_length=8, byte_order="big_endian")
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        header = [f for f in result.output_files if f.suffix == ".h"][0]
        content = header.read_text(encoding="utf-8")
        pack_body = self._get_func_body(content, "Pack_BE_Sig")
        assert "cur_byte" in pack_body
        assert "cur_bit" in pack_body
        assert "shift" in pack_body
        assert "start_byte" not in pack_body

    def test_big_endian_unpack_has_motorola_logic(self, tmp_path):
        """Big endian unpack code must use cur_byte/cur_bit/shift (Motorola bit order)."""
        sig = _sig("BE_Sig", start_bit=7, bit_length=8, byte_order="big_endian")
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        header = [f for f in result.output_files if f.suffix == ".h"][0]
        content = header.read_text(encoding="utf-8")
        unpack_body = self._get_func_body(content, "Unpack_BE_Sig")
        assert "cur_byte" in unpack_body
        assert "shift" in unpack_body

    def test_big_endian_16bit_pack(self, tmp_path):
        """16-bit big endian signal: MSB at byte 1 bit 7."""
        sig = _sig("BE16", start_bit=15, bit_length=16, byte_order="big_endian", value_type="unsigned", maximum=65535.0)
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        header = [f for f in result.output_files if f.suffix == ".h"][0]
        content = header.read_text(encoding="utf-8")
        pack_body = self._get_func_body(content, "Pack_BE16")
        assert "cur_byte = 1u" in pack_body
        assert "cur_bit  = 7u" in pack_body
        assert "remaining = 16u" in pack_body

    # ── P0: Signed signal sign extension ─────────────────────────────────

    def test_signed_16bit_has_sign_extension(self, tmp_path):
        """Signed 16-bit unpack must include sign extension logic."""
        sig = _sig("Signed16", bit_length=16, value_type="signed", factor=0.1, offset=-40, minimum=-40, maximum=215.0)
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        header = [f for f in result.output_files if f.suffix == ".h"][0]
        content = header.read_text(encoding="utf-8")
        unpack_body = self._get_func_body(content, "Unpack_Signed16")
        assert "0x8000u" in unpack_body
        assert "~0xFFFFu" in unpack_body
        assert "int16_t" in unpack_body

    def test_signed_8bit_has_sign_extension(self, tmp_path):
        """Signed 8-bit unpack must include sign extension."""
        sig = _sig("Signed8", bit_length=8, value_type="signed", minimum=-128, maximum=127)
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        header = [f for f in result.output_files if f.suffix == ".h"][0]
        content = header.read_text(encoding="utf-8")
        unpack_body = self._get_func_body(content, "Unpack_Signed8")
        assert "0x80u" in unpack_body
        assert "~0xFFu" in unpack_body

    def test_unsigned_no_sign_extension(self, tmp_path):
        """Unsigned unpack must NOT include sign extension logic."""
        sig = _sig("Unsigned16", bit_length=16, value_type="unsigned", maximum=65535)
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        header = [f for f in result.output_files if f.suffix == ".h"][0]
        content = header.read_text(encoding="utf-8")
        unpack_body = self._get_func_body(content, "Unpack_Unsigned16")
        assert "0x8000u" not in unpack_body
        assert "uint16_t" in unpack_body

    def test_big_endian_signed_combo(self, tmp_path):
        """Big endian + signed: must have both Motorola logic and sign extension."""
        sig = _sig(
            "BE_Signed",
            start_bit=23,
            bit_length=16,
            byte_order="big_endian",
            value_type="signed",
            factor=0.01,
            offset=-100,
            minimum=-100,
            maximum=555.35,
        )
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        header = [f for f in result.output_files if f.suffix == ".h"][0]
        content = header.read_text(encoding="utf-8")
        unpack_body = self._get_func_body(content, "Unpack_BE_Signed")
        assert "cur_byte" in unpack_body
        assert "shift" in unpack_body
        assert "0x8000u" in unpack_body
        assert "int16_t" in unpack_body

    # ── P0: Enum typedef from value_descriptions ─────────────────────────

    def test_enum_typedef_generated(self, tmp_path):
        """Signal with value_descriptions must generate enum typedef."""
        sig = _sig(
            "GearPos",
            bit_length=8,
            value_type="unsigned",
            value_descriptions={0: "Park", 1: "Reverse", 2: "Neutral", 3: "Drive"},
        )
        data = _dbc([_msg("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        header = [f for f in result.output_files if f.suffix == ".h"][0]
        content = header.read_text(encoding="utf-8")
        assert "typedef enum" in content
        assert "GearPos_e" in content
        assert "GearPos_Park" in content
        assert "GearPos_Drive" in content
        assert "GearPos_e val" in content
        assert "GearPos_e CAN_Unpack_GearPos" in content
