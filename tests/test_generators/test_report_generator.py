"""Tests for core.generators.report_generator — Excel report generation."""

import pytest
from pathlib import Path

from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef
from core.diff.dbc_diff import DBCDiffResult, MessageDiff, SignalDiff, DiffType
from core.generators.report_generator import ReportGenerator


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


class TestReportGenerator:

    def setup_method(self):
        self.gen = ReportGenerator()

    def test_signal_matrix(self, tmp_path):
        data = _make_dbc([
            _make_message("M1", signals=[
                _make_signal("S1", unit="V", receivers=["BMS"]),
                _make_signal("S2", factor=0.1, offset=-500),
            ]),
        ])
        out = tmp_path / "matrix.xlsx"
        self.gen.generate_signal_matrix(data, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_signal_matrix_empty(self, tmp_path):
        data = _make_dbc([])
        out = tmp_path / "empty.xlsx"
        self.gen.generate_signal_matrix(data, out)
        assert out.exists()

    def test_diff_report(self, tmp_path):
        diff = DBCDiffResult(
            old_version="v1", new_version="v2",
            message_diffs=[
                MessageDiff(
                    message_name="M1", diff_type=DiffType.MODIFIED, id=0x100,
                    signal_diffs=[
                        SignalDiff(
                            signal_name="S1",
                            diff_type=DiffType.MODIFIED,
                            changes={"factor": (1.0, 0.5)},
                            message_name="M1",
                        ),
                    ],
                ),
                MessageDiff(
                    message_name="M2", diff_type=DiffType.ADDED, id=0x200,
                    signal_diffs=[
                        SignalDiff(signal_name="S2", diff_type=DiffType.ADDED, message_name="M2"),
                    ],
                ),
            ],
            summary={"messages_added": 1, "messages_modified": 1},
        )
        out = tmp_path / "diff_report.xlsx"
        self.gen.generate_diff_report(diff, out)
        assert out.exists()
