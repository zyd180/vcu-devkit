"""Tests for core.diff.dbc_diff — DBC version diff engine."""

import pytest
from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef
from core.diff.dbc_diff import DBCDiffEngine, DiffType, DBCDiffResult


def _make_signal(name, start_bit=0, bit_length=8, factor=1.0, offset=0.0,
                 byte_order="little_endian", value_type="unsigned", unit="",
                 minimum=0.0, maximum=255.0, receivers=None, comment=""):
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


def _make_dbc(messages, version="v1"):
    return DBCData(
        version=version, messages=messages, nodes=[],
        value_tables={}, comments={}, attributes={},
        source_path="<test>",
    )


# ── Core diff tests ──────────────────────────────────────────────────────────

class TestDBCDiffEngine:

    def setup_method(self):
        self.engine = DBCDiffEngine()

    def test_identical_dbc_no_diff(self):
        msg = _make_message("Msg1", signals=[_make_signal("Sig1")])
        old = _make_dbc([msg])
        new = _make_dbc([msg])
        result = self.engine.compare(old, new)
        assert result.summary["messages_added"] == 0
        assert result.summary["messages_removed"] == 0
        assert result.summary["messages_modified"] == 0

    def test_added_message(self):
        old = _make_dbc([])
        new_msg = _make_message("NewMsg", signals=[_make_signal("S1")])
        new = _make_dbc([new_msg])
        result = self.engine.compare(old, new)
        assert result.summary["messages_added"] == 1
        assert "NewMsg" in result.added_messages

    def test_removed_message(self):
        old_msg = _make_message("OldMsg")
        old = _make_dbc([old_msg])
        new = _make_dbc([])
        result = self.engine.compare(old, new)
        assert result.summary["messages_removed"] == 1
        assert "OldMsg" in result.removed_messages

    def test_added_signal(self):
        msg_old = _make_message("M1", signals=[_make_signal("S1")])
        msg_new = _make_message("M1", signals=[_make_signal("S1"), _make_signal("S2")])
        result = self.engine.compare(_make_dbc([msg_old]), _make_dbc([msg_new]))
        assert result.summary["signals_added"] == 1

    def test_removed_signal(self):
        msg_old = _make_message("M1", signals=[_make_signal("S1"), _make_signal("S2")])
        msg_new = _make_message("M1", signals=[_make_signal("S1")])
        result = self.engine.compare(_make_dbc([msg_old]), _make_dbc([msg_new]))
        assert result.summary["signals_removed"] == 1

    def test_modified_signal(self):
        sig_old = _make_signal("S1", factor=1.0)
        sig_new = _make_signal("S1", factor=0.5)
        result = self.engine.compare(
            _make_dbc([_make_message("M1", signals=[sig_old])]),
            _make_dbc([_make_message("M1", signals=[sig_new])]),
        )
        assert result.summary["signals_modified"] == 1
        md = result.message_diffs[0]
        sd = md.signal_diffs[0]
        assert sd.diff_type == DiffType.MODIFIED
        assert "factor" in sd.changes

    def test_modified_message_dlc(self):
        m1 = _make_message("M1", dlc=8)
        m2 = _make_message("M1", dlc=16)
        result = self.engine.compare(_make_dbc([m1]), _make_dbc([m2]))
        assert result.summary["messages_modified"] == 1
        assert "dlc" in result.message_diffs[0].changes

    def test_modified_sender(self):
        m1 = _make_message("M1", sender="VCU")
        m2 = _make_message("M1", sender="BMS")
        result = self.engine.compare(_make_dbc([m1]), _make_dbc([m2]))
        assert "sender" in result.message_diffs[0].changes

    def test_modified_comment(self):
        m1 = _make_message("M1"); m1.comment = "old"
        m2 = _make_message("M1"); m2.comment = "new"
        result = self.engine.compare(_make_dbc([m1]), _make_dbc([m2]))
        assert "comment" in result.message_diffs[0].changes

    def test_receivers_change(self):
        sig_old = _make_signal("S1", receivers=["A"])
        sig_new = _make_signal("S1", receivers=["B"])
        result = self.engine.compare(
            _make_dbc([_make_message("M1", signals=[sig_old])]),
            _make_dbc([_make_message("M1", signals=[sig_new])]),
        )
        sd = result.message_diffs[0].signal_diffs[0]
        assert "receivers" in sd.changes

    def test_value_descriptions_change(self):
        sig_old = _make_signal("S1"); sig_old.value_descriptions = {0: "Off"}
        sig_new = _make_signal("S1"); sig_new.value_descriptions = {0: "On"}
        result = self.engine.compare(
            _make_dbc([_make_message("M1", signals=[sig_old])]),
            _make_dbc([_make_message("M1", signals=[sig_new])]),
        )
        sd = result.message_diffs[0].signal_diffs[0]
        assert "value_descriptions" in sd.changes

    def test_text_report(self):
        old = _make_dbc([_make_message("M1", signals=[_make_signal("S1")])])
        new = _make_dbc([])
        result = self.engine.compare(old, new)
        report = self.engine.generate_text_report(result)
        assert "DBC Diff Report" in report
        assert "M1" in report

    def test_excel_report(self, tmp_path):
        old = _make_dbc([_make_message("M1", signals=[_make_signal("S1")])])
        new = _make_dbc([_make_message("M1", signals=[_make_signal("S1", factor=0.5)])])
        result = self.engine.compare(old, new)
        out = tmp_path / "diff.xlsx"
        self.engine.export_excel_report(result, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_mixed_changes(self):
        """Added, removed, modified messages in one diff."""
        m1 = _make_message("Keep", signals=[_make_signal("S1")])
        m2 = _make_message("Remove")
        m3 = _make_message("Keep", signals=[_make_signal("S1", factor=2.0)])
        m4 = _make_message("Add")
        old = _make_dbc([m1, m2])
        new = _make_dbc([m3, m4])
        result = self.engine.compare(old, new)
        assert "Remove" in result.removed_messages
        assert "Add" in result.added_messages
