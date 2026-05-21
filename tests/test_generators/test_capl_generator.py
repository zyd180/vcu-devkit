"""Tests for core.generators.capl_generator — CAPL code generation."""

from core.generators.capl_generator import CAPLGenerator
from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef


def _make_signal(
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
        value_descriptions={},
        mux=None,
    )


def _make_message(name, msg_id=0x100, dlc=8, sender="VCU", signals=None):
    return MessageDef(
        id=msg_id,
        name=name,
        dlc=dlc,
        sender=sender,
        signals=signals or [],
        comment="",
        is_extended=False,
    )


def _make_dbc(messages):
    return DBCData(
        version="v1",
        messages=messages,
        nodes=[],
        value_tables={},
        comments={},
        attributes={},
        source_path="<test>",
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


# ── P1: Generated content verification ──────────────────────────────────────


class TestCAPLContentVerification:
    def setup_method(self):
        self.gen = CAPLGenerator()

    def test_can_fd_tx_uses_message_star(self, tmp_path):
        """CAN FD TX block should use 'message *' syntax."""
        sig = _make_signal("S1")
        msg = _make_message("FDMsg", dlc=64, sender="VCU", signals=[sig])
        msg.is_fd = True
        data = _make_dbc([msg])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "message * 256 msg_FDMsg" in content

    def test_normal_tx_uses_message(self, tmp_path):
        """Normal CAN TX block should use 'message' (no star)."""
        sig = _make_signal("S1")
        data = _make_dbc([_make_message("M1", sender="VCU", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "message 256 msg_M1" in content
        assert "message *" not in content

    def test_tx_signal_assignment(self, tmp_path):
        """TX block should assign signal to message field."""
        sig = _make_signal("ThrottlePos")
        data = _make_dbc([_make_message("M1", sender="VCU", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "msg_M1.ThrottlePos = ThrottlePos;" in content

    def test_rx_handler_signal_read(self, tmp_path):
        """RX handler should read signal via this.SigName."""
        sig = _make_signal("BMS_Voltage")
        data = _make_dbc([_make_message("M1", sender="BMS", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "BMS_Voltage = this.BMS_Voltage;" in content

    def test_rx_handler_message_id_decimal(self, tmp_path):
        """RX handler should reference message ID as decimal."""
        sig = _make_signal("S1")
        data = _make_dbc([_make_message("M1", msg_id=0x200, sender="BMS", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "on message 512" in content

    def test_multiple_messages_in_output(self, tmp_path):
        """Multiple messages should all appear in the generated file."""
        data = _make_dbc(
            [
                _make_message("M1", msg_id=0x100, sender="VCU", signals=[_make_signal("S1")]),
                _make_message("M2", msg_id=0x200, sender="BMS", signals=[_make_signal("S2")]),
                _make_message("M3", msg_id=0x300, sender="VCU", signals=[_make_signal("S3")]),
            ]
        )
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "M1" in content
        assert "M2" in content
        assert "M3" in content
        assert "output(msg_M1)" in content
        assert "output(msg_M3)" in content
        assert "on message 512" in content

    def test_global_variable_declaration(self, tmp_path):
        """Signals should be declared as global variables with correct CAPL type and initial value."""
        sig = _make_signal("Speed", bit_length=16, value_type="unsigned")
        data = _make_dbc([_make_message("M1", signals=[sig])])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "word Speed = 0;" in content

    def test_fd_rx_handler(self, tmp_path):
        """CAN FD RX handler should include (FD) tag in comment."""
        sig = _make_signal("S1")
        msg = _make_message("FDMsg", msg_id=0x100, dlc=64, sender="BMS", signals=[sig])
        msg.is_fd = True
        data = _make_dbc([msg])
        result = self.gen.generate(data, tmp_path)
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "(FD)" in content
