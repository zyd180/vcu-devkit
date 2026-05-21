"""Tests for CAN FD support — data models, code generation, and validation."""

from core.generators.c_generator import CANCodeGenerator
from core.generators.capl_generator import CAPLGenerator
from core.parsers.dbc_parser import (
    DBCData,
    MessageDef,
    SignalDef,
    dbc_data_from_dict,
    dbc_data_to_dict,
)
from core.rules.engine import RuleEngine

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_fd_signal(name="Sig1", start=0, length=16):
    return SignalDef(
        name=name,
        start_bit=start,
        bit_length=length,
        byte_order="little_endian",
        value_type="unsigned",
        factor=1.0,
        offset=0.0,
        minimum=0,
        maximum=65535,
        unit="",
        comment="",
    )


def _make_fd_message(name="FD_Msg", msg_id=0x100, dlc=64, signals=None, sender="VCU"):
    if signals is None:
        signals = [_make_fd_signal()]
    return MessageDef(
        id=msg_id,
        name=name,
        dlc=dlc,
        sender=sender,
        comment="",
        signals=signals,
        is_extended=False,
        is_fd=True,
    )


def _make_canfd_dbc(messages=None):
    if messages is None:
        messages = [_make_fd_message()]
    return DBCData(
        version="",
        messages=messages,
        nodes=["VCU"],
        value_tables={},
        comments={},
        attributes={},
        source_path="<test>",
    )


# ── Data model tests ────────────────────────────────────────────────────────


class TestCANFDDataModel:
    def test_message_is_fd_default_false(self):
        msg = MessageDef(id=0x100, name="Msg", dlc=8, sender="", comment="")
        assert msg.is_fd is False

    def test_message_is_fd_true(self):
        msg = _make_fd_message(dlc=64)
        assert msg.is_fd is True

    def test_classic_can_not_fd(self):
        msg = MessageDef(id=0x100, name="Msg", dlc=8, sender="", comment="")
        assert msg.is_fd is False
        assert msg.dlc == 8


# ── Serialisation roundtrip ─────────────────────────────────────────────────


class TestCANFDRoundtrip:
    def test_is_fd_preserved_in_dict(self):
        dbc = _make_canfd_dbc()
        d = dbc_data_to_dict(dbc)
        assert d["messages"][0]["is_fd"] is True

    def test_roundtrip(self):
        dbc = _make_canfd_dbc()
        d = dbc_data_to_dict(dbc)
        restored = dbc_data_from_dict(d)
        assert restored.messages[0].is_fd is True
        assert restored.messages[0].dlc == 64

    def test_classic_can_roundtrip(self):
        classic = MessageDef(id=0x200, name="Classic", dlc=8, sender="", comment="")
        dbc = DBCData(
            version="",
            messages=[classic],
            nodes=[],
            value_tables={},
            comments={},
            attributes={},
            source_path="<test>",
        )
        d = dbc_data_to_dict(dbc)
        assert d["messages"][0]["is_fd"] is False
        restored = dbc_data_from_dict(d)
        assert restored.messages[0].is_fd is False


# ── C code generation tests ─────────────────────────────────────────────────


class TestCANFDCCodeGeneration:
    def test_fd_macro_defined(self):
        gen = CANCodeGenerator()
        dbc = _make_canfd_dbc()
        code = gen._generate_header(dbc)
        assert "#define CAN_IS_FD_FD_Msg  1" in code

    def test_classic_no_fd_macro(self):
        gen = CANCodeGenerator()
        msg = MessageDef(
            id=0x100,
            name="Classic",
            dlc=8,
            sender="VCU",
            comment="",
            signals=[_make_fd_signal()],
        )
        dbc = DBCData(
            version="",
            messages=[msg],
            nodes=[],
            value_tables={},
            comments={},
            attributes={},
            source_path="<test>",
        )
        code = gen._generate_header(dbc)
        assert "CAN_IS_FD_" not in code

    def test_64bit_c_type(self):
        sig = SignalDef(
            name="BigSig",
            start_bit=0,
            bit_length=48,
            byte_order="little_endian",
            value_type="unsigned",
            factor=1.0,
            offset=0.0,
            minimum=0,
            maximum=0,
            unit="",
            comment="",
        )
        assert CANCodeGenerator._raw_c_type(sig) == "uint64_t"

    def test_64bit_signed_c_type(self):
        sig = SignalDef(
            name="BigSig",
            start_bit=0,
            bit_length=48,
            byte_order="little_endian",
            value_type="signed",
            factor=1.0,
            offset=0.0,
            minimum=0,
            maximum=0,
            unit="",
            comment="",
        )
        assert CANCodeGenerator._raw_c_type(sig) == "int64_t"

    def test_fd_message_dlc_in_output(self):
        gen = CANCodeGenerator()
        dbc = _make_canfd_dbc()
        code = gen._generate_header(dbc)
        assert "DLC=64" in code

    def test_generate_fd_files(self, tmp_path):
        gen = CANCodeGenerator()
        dbc = _make_canfd_dbc()
        result = gen.generate(dbc, tmp_path)
        assert result.success
        assert len(result.output_files) == 3


# ── CAPL code generation tests ──────────────────────────────────────────────


class TestCANFDCAPLGeneration:
    def test_fd_tx_uses_star(self):
        gen = CAPLGenerator()
        msg = _make_fd_message()
        lines = gen._generate_tx_block(msg)
        code = "\n".join(lines)
        assert "message *" in code

    def test_classic_tx_no_star(self):
        gen = CAPLGenerator()
        msg = MessageDef(
            id=0x100,
            name="Classic",
            dlc=8,
            sender="VCU",
            comment="",
            signals=[_make_fd_signal()],
        )
        lines = gen._generate_tx_block(msg)
        code = "\n".join(lines)
        assert "message *" not in code
        assert "message 256" in code

    def test_fd_rx_handler_comment(self):
        gen = CAPLGenerator()
        msg = _make_fd_message(sender="BMS")
        lines = gen._generate_rx_handler(msg)
        code = "\n".join(lines)
        assert "(FD)" in code


# ── Validation rule tests ───────────────────────────────────────────────────


class TestCANFDValidation:
    def test_valid_fd_dlc(self):
        engine = RuleEngine()
        dbc = _make_canfd_dbc([_make_fd_message(dlc=64)])
        results = engine.check_dbc(dbc)
        fd_errors = [r for r in results if r.rule_id == "DBC_FD_DLC_INVALID"]
        assert len(fd_errors) == 0

    def test_invalid_fd_dlc(self):
        engine = RuleEngine()
        dbc = _make_canfd_dbc([_make_fd_message(dlc=10)])
        results = engine.check_dbc(dbc)
        fd_errors = [r for r in results if r.rule_id == "DBC_FD_DLC_INVALID"]
        assert len(fd_errors) == 1
        assert "invalid DLC 10" in fd_errors[0].message

    def test_fd_flag_missing_warning(self):
        engine = RuleEngine()
        msg = MessageDef(
            id=0x100,
            name="Msg",
            dlc=16,
            sender="VCU",
            comment="",
            signals=[_make_fd_signal()],
            is_fd=False,
        )
        dbc = DBCData(
            version="",
            messages=[msg],
            nodes=[],
            value_tables={},
            comments={},
            attributes={},
            source_path="<test>",
        )
        results = engine.check_dbc(dbc)
        warnings = [r for r in results if r.rule_id == "DBC_FD_FLAG_MISSING"]
        assert len(warnings) == 1

    def test_classic_can_no_fd_errors(self):
        engine = RuleEngine()
        msg = MessageDef(
            id=0x100,
            name="Classic",
            dlc=8,
            sender="VCU",
            comment="",
            signals=[_make_fd_signal()],
        )
        dbc = DBCData(
            version="",
            messages=[msg],
            nodes=[],
            value_tables={},
            comments={},
            attributes={},
            source_path="<test>",
        )
        results = engine.check_dbc(dbc)
        fd_errors = [r for r in results if r.rule_id in ("DBC_FD_DLC_INVALID", "DBC_FD_FLAG_MISSING")]
        assert len(fd_errors) == 0

    def test_valid_fd_dlcs(self):
        engine = RuleEngine()
        for dlc in (0, 8, 12, 16, 20, 24, 32, 48, 64):
            dbc = _make_canfd_dbc([_make_fd_message(dlc=dlc)])
            results = engine.check_dbc(dbc)
            fd_errors = [r for r in results if r.rule_id == "DBC_FD_DLC_INVALID"]
            assert len(fd_errors) == 0, f"DLC {dlc} should be valid"
