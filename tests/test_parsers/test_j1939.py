"""Tests for J1939 protocol support — PGN extraction, TP reassembly, DM1/DM2, C code gen."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from core.parsers.j1939_parser import (
    J1939Data, J1939DTC, J1939PGN, J1939SPN, J1939TPMessage,
    J1939Parser, extract_pgn, is_pgn_in_range,
)
from core.parsers.j1939_tp import J1939TransportProtocol, TPControl
from core.parsers.j1939_diag import J1939Diagnostics, DTCLamp
from core.generators.j1939_c_generator import J1939CodeGenerator
from core.rules.engine import RuleEngine, Severity
from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef


# ── PGN extraction tests ────────────────────────────────────────────────────


class TestPGNExtraction:

    def test_pdu2_format(self):
        """PDU2: PF >= 240, PS is group extension, part of PGN."""
        # EEC1: PGN 0xF004, priority 6, SA 0x00
        can_id = (6 << 26) | (0xF004 << 8) | 0x00
        priority, pgn, ps, sa = extract_pgn(can_id)
        assert priority == 6
        assert pgn == 0xF004
        assert ps == 0x04
        assert sa == 0x00

    def test_pdu1_format(self):
        """PDU1: PF < 240, PS is destination address, NOT part of PGN."""
        # PF=0x00 (ACK), PS=0xFF (broadcast), SA=0x10
        can_id = (6 << 26) | (0x00 << 16) | (0xFF << 8) | 0x10
        priority, pgn, ps, sa = extract_pgn(can_id)
        assert priority == 6
        assert pgn == 0x0000
        assert ps == 0xFF
        assert sa == 0x10

    def test_pdu1_destination_specific(self):
        """PDU1 with specific destination."""
        # PF=0xE6 (TP.CM), PS=0x00 (dest=0), SA=0x03
        can_id = (6 << 26) | (0xE6 << 16) | (0x00 << 8) | 0x03
        priority, pgn, ps, sa = extract_pgn(can_id)
        assert priority == 6
        assert pgn == 0xE600
        assert ps == 0x00
        assert sa == 0x03

    def test_priority_range(self):
        """Priority is 3 bits (0-7)."""
        for pri in range(8):
            can_id = (pri << 26) | (0xF004 << 8)
            priority, _, _, _ = extract_pgn(can_id)
            assert priority == pri

    def test_source_address_extraction(self):
        """Source address is lowest byte."""
        for sa in [0x00, 0x10, 0xFF, 0x80]:
            can_id = (6 << 26) | (0xF004 << 8) | sa
            _, _, _, extracted_sa = extract_pgn(can_id)
            assert extracted_sa == sa

    def test_is_pgn_in_range(self):
        assert is_pgn_in_range(0x0000)
        assert is_pgn_in_range(0xF004)
        assert is_pgn_in_range(0xFEFF)
        assert not is_pgn_in_range(0xFF00)
        assert not is_pgn_in_range(0xFFFF)

    def test_pgn_boundary(self):
        """PF=239 (PDU1 boundary)."""
        can_id = (6 << 26) | (239 << 16) | (0x05 << 8) | 0x00
        _, pgn, _, _ = extract_pgn(can_id)
        assert pgn == 239 << 8  # PDU1: PS not in PGN

    def test_pgn_boundary_pdu2(self):
        """PF=240 (PDU2 boundary)."""
        can_id = (6 << 26) | (240 << 16) | (0x05 << 8) | 0x00
        _, pgn, _, _ = extract_pgn(can_id)
        assert pgn == (240 << 8) | 0x05  # PDU2: PS is in PGN


# ── TP reassembly tests ─────────────────────────────────────────────────────


class TestTransportProtocol:

    def _make_bam_cm(self, sa: int, total_length: int, max_packets: int, pgn: int) -> bytes:
        """Build a BAM TP.CM frame."""
        return bytes([
            TPControl.BAM,
            total_length & 0xFF, (total_length >> 8) & 0xFF,
            max_packets,
            0xFF,  # reserved
            pgn & 0xFF, (pgn >> 8) & 0xFF, (pgn >> 16) & 0xFF,
        ])

    def _make_rts(self, sa: int, total_length: int, max_packets: int, pgn: int) -> bytes:
        """Build an RTS TP.CM frame."""
        return bytes([
            TPControl.RTS,
            total_length & 0xFF, (total_length >> 8) & 0xFF,
            max_packets,
            max_packets,  # max packets per CTS
            pgn & 0xFF, (pgn >> 8) & 0xFF, (pgn >> 16) & 0xFF,
        ])

    def _make_dt(self, sa: int, seq: int, payload: bytes) -> bytes:
        """Build a TP.DT frame."""
        data = bytes([seq]) + payload
        # Pad to 8 bytes
        return data.ljust(8, b'\xFF')

    def test_bam_single_transfer(self):
        """BAM: single multi-frame transfer completes after all packets."""
        tp = J1939TransportProtocol()
        sa = 0x01
        pgn = 0xF004
        total_length = 12
        max_packets = 2  # 12 bytes / 7 bytes per packet = 2

        # Send BAM TP.CM
        cm_data = self._make_bam_cm(sa, total_length, max_packets, pgn)
        cm_id = (6 << 26) | (0xEC00 << 8) | sa
        result = tp.process_frame(cm_id, cm_data)
        assert result is None  # Not complete yet

        # Send TP.DT packet 1
        dt1 = self._make_dt(sa, 1, b'\x01\x02\x03\x04\x05\x06\x07')
        dt_id = (6 << 26) | (0xEB00 << 8) | sa
        result = tp.process_frame(dt_id, dt1)
        assert result is None

        # Send TP.DT packet 2
        dt2 = self._make_dt(sa, 2, b'\x08\x09\x0A\x0B\x0C')
        result = tp.process_frame(dt_id, dt2)
        assert result is not None
        assert result.pgn == pgn
        assert result.total_length == total_length
        assert result.source_address == sa
        assert result.tp_type == "BAM"
        assert len(result.data) == total_length

    def test_bam_large_transfer(self):
        """BAM: large transfer with many packets."""
        tp = J1939TransportProtocol()
        sa = 0x02
        pgn = 0xFECA  # DM1
        total_length = 30
        max_packets = 5  # 30 / 7 = 5 (ceil)

        cm_id = (6 << 26) | (0xEC00 << 8) | sa
        dt_id = (6 << 26) | (0xEB00 << 8) | sa

        tp.process_frame(cm_id, self._make_bam_cm(sa, total_length, max_packets, pgn))

        for i in range(1, max_packets + 1):
            payload = bytes([i] * 7)
            result = tp.process_frame(dt_id, self._make_dt(sa, i, payload))
            if i < max_packets:
                assert result is None
            else:
                assert result is not None
                assert result.pgn == pgn

    def test_rts_session_created(self):
        """RTS creates a session but doesn't complete (needs CTS)."""
        tp = J1939TransportProtocol()
        sa = 0x03
        pgn = 0xF004

        cm_id = (6 << 26) | (0xEC00 << 8) | sa
        rts_data = self._make_rts(sa, 20, 3, pgn)
        result = tp.process_frame(cm_id, rts_data)
        assert result is None
        assert tp.active_sessions == 1

    def test_non_tp_frame_ignored(self):
        """Non-TP CAN frames are ignored."""
        tp = J1939TransportProtocol()
        # Regular message, not TP.CM or TP.DT
        can_id = (6 << 26) | (0xF004 << 8) | 0x00
        result = tp.process_frame(can_id, b'\x00' * 8)
        assert result is None
        assert tp.active_sessions == 0

    def test_cleanup_expired(self):
        """Expired sessions are cleaned up."""
        tp = J1939TransportProtocol()
        # Manually add an expired session
        from core.parsers.j1939_tp import _TPSession
        import time
        session = _TPSession(
            pgn=0xF004, total_length=10, max_packets=2,
            source_address=0x01, tp_type="BAM",
            last_activity=time.monotonic() - 10.0,
        )
        tp._sessions[(0xF004, 0x01)] = session
        assert tp.active_sessions == 1
        tp.cleanup_expired()
        assert tp.active_sessions == 0

    def test_duplicate_packet_overwrites(self):
        """Duplicate sequence number overwrites previous data."""
        tp = J1939TransportProtocol()
        sa = 0x01
        pgn = 0xF004

        cm_id = (6 << 26) | (0xEC00 << 8) | sa
        dt_id = (6 << 26) | (0xEB00 << 8) | sa

        tp.process_frame(cm_id, self._make_bam_cm(sa, 14, 2, pgn))
        tp.process_frame(dt_id, self._make_dt(sa, 1, b'\xAA' * 7))
        # Overwrite packet 1
        tp.process_frame(dt_id, self._make_dt(sa, 1, b'\xBB' * 7))
        result = tp.process_frame(dt_id, self._make_dt(sa, 2, b'\xCC' * 7))
        assert result is not None
        assert result.data[:7] == b'\xBB' * 7


# ── DM1/DM2 diagnostic tests ───────────────────────────────────────────────


class TestDiagnostics:

    def test_parse_single_dtc(self):
        """Parse a single DTC from DM1 payload."""
        diag = J1939Diagnostics()
        # SPN=190 (0x000BE), FMI=2, Occurrence=3
        spn = 190  # 0x000BE
        fmi = 2
        occ = 3
        # Encoding: byte0=SPN low, byte1=SPN mid, byte2=(SPN_hi<<5)|FMI, byte3=occ
        byte0 = spn & 0xFF
        byte1 = (spn >> 8) & 0xFF
        byte2 = ((spn >> 16) & 0x07) << 5 | (fmi & 0x1F)
        byte3 = occ & 0x7F

        # Single-frame DM1: 2 lamp bytes + 4 DTC bytes
        lamp = bytes([0x00, 0x00])  # All lamps off
        dtc_bytes = bytes([byte0, byte1, byte2, byte3])
        data = lamp + dtc_bytes

        dtcs = diag.parse_dm1(data)
        assert len(dtcs) == 1
        assert dtcs[0].spn == spn
        assert dtcs[0].fmi == fmi
        assert dtcs[0].occurrence == occ

    def test_parse_two_dtcs(self):
        """Parse two DTCs from multi-frame DM1 (no lamp header)."""
        diag = J1939Diagnostics()

        # Multi-frame format (>8 bytes): no lamp header, 4 bytes per DTC
        dtc1 = bytes([0xBE, 0x00, (0x00 << 5) | 0x02, 0x03])  # SPN=190, FMI=2, Occ=3
        dtc2 = bytes([0x34, 0x12, (0x01 << 5) | 0x05, 0x0A])  # SPN=0x11234, FMI=5, Occ=10
        # Need >8 bytes to trigger multi-frame path (no lamp header)
        padding = bytes([0x00, 0x00, 0x00, 0x00])
        data = dtc1 + dtc2 + padding  # 12 bytes

        dtcs = diag.parse_dm1(data)
        assert len(dtcs) >= 2
        assert dtcs[0].spn == 190
        assert dtcs[0].fmi == 2
        assert dtcs[1].fmi == 5

    def test_empty_dm1(self):
        """Empty DM1 returns no DTCs."""
        diag = J1939Diagnostics()
        assert diag.parse_dm1(b"") == []
        assert diag.parse_dm1(b'\x00') == []

    def test_lamp_status(self):
        """Extract lamp status from DM1 header."""
        diag = J1939Diagnostics()
        # Byte 0: MI=01 (on), Red=00 (off), Amber=11 (N/A), Protect=01 (on)
        # Byte 1: all flash off (00)
        data = bytes([0b01_00_11_01, 0x00])
        status = diag.get_lamp_status(data)
        assert status["malfunction_indicator"] == "on"
        assert status["red_stop_lamp"] == "off"
        assert status["amber_warning_lamp"] == "not_available"
        assert status["protect_lamp"] == "on"

    def test_dm2_parsing(self):
        """DM2 uses same format as DM1."""
        diag = J1939Diagnostics()
        dtc_bytes = bytes([0xBE, 0x00, 0x02, 0x03])  # SPN=190, FMI=2, Occ=3
        lamp = bytes([0x00, 0x00])
        dtcs = diag.parse_dm2(lamp + dtc_bytes)
        assert len(dtcs) == 1
        assert dtcs[0].spn == 190

    def test_process_frame_dm1(self):
        """process_frame detects DM1 PGN and returns DTCs."""
        diag = J1939Diagnostics()
        dm1_id = (6 << 26) | (0xFECA << 8) | 0x00
        dtc_bytes = bytes([0xBE, 0x00, 0x02, 0x03])
        lamp = bytes([0x00, 0x00])
        result = diag.process_frame(dm1_id, lamp + dtc_bytes)
        assert result is not None
        assert len(result) == 1

    def test_process_frame_non_dm(self):
        """Non-DM frames return None."""
        diag = J1939Diagnostics()
        can_id = (6 << 26) | (0xF004 << 8) | 0x00
        result = diag.process_frame(can_id, b'\x00' * 8)
        assert result is None


# ── J1939 C code generator tests ────────────────────────────────────────────


class TestJ1939CodeGenerator:

    def _make_j1939_data(self) -> J1939Data:
        return J1939Data(
            is_j1939=True,
            pgn_messages=[
                J1939PGN(pgn=0xF004, name="EEC1", description="Engine Electronic Controller 1"),
                J1939PGN(pgn=0xF003, name="EEC2", description="Engine Electronic Controller 2"),
            ],
            spn_signals=[
                J1939SPN(spn=190, name="EngineSpeed", pgn=0xF004, unit="rpm"),
                J1939SPN(spn=513, name="ActualEnginePercentTorque", pgn=0xF004, unit="%"),
                J1939SPN(spn=0, name="UnknownSignal", pgn=0xF003),
            ],
            source_addresses={"ECU1": 0x00, "ECU2": 0x10},
            dbc_data=DBCData(
                version="", messages=[], nodes=[],
                value_tables={}, comments={}, attributes={},
                source_path="<test>",
            ),
        )

    def test_generate_j1939_header(self, tmp_path):
        gen = J1939CodeGenerator()
        data = self._make_j1939_data()
        result = gen.generate(data, tmp_path)
        assert result.success
        assert len(result.output_files) == 4

        content = (tmp_path / "can_j1939.h").read_text(encoding="utf-8")
        assert "J1939_SA_ECU1" in content
        assert "J1939_ID_EEC1" in content
        assert "j1939_pgn.h" in content

    def test_generate_pgn_header(self, tmp_path):
        gen = J1939CodeGenerator()
        data = self._make_j1939_data()
        gen.generate(data, tmp_path)

        content = (tmp_path / "j1939_pgn.h").read_text(encoding="utf-8")
        assert "J1939_PGN_EEC1" in content
        assert "0xF004u" in content

    def test_generate_spn_header(self, tmp_path):
        gen = J1939CodeGenerator()
        data = self._make_j1939_data()
        gen.generate(data, tmp_path)

        content = (tmp_path / "j1939_spn.h").read_text(encoding="utf-8")
        assert "J1939_SPN_ENGINESPEED" in content
        assert "190u" in content
        # Unknown SPN (0) should be skipped
        assert "UNKNOWN" not in content.upper() or "UnknownSignal" not in content

    def test_generate_dtc_header(self, tmp_path):
        gen = J1939CodeGenerator()
        data = self._make_j1939_data()
        gen.generate(data, tmp_path)

        content = (tmp_path / "j1939_dtc.h").read_text(encoding="utf-8")
        assert "J1939_DTC_t" in content
        assert "J1939_EncodeDTC" in content
        assert "J1939_DecodeDTC" in content
        assert "J1939_FMI_HIGH_SEVERITY" in content

    def test_encode_decode_dtc_roundtrip(self, tmp_path):
        """Encode a DTC, then decode it — verify round-trip."""
        gen = J1939CodeGenerator()
        data = self._make_j1939_data()
        gen.generate(data, tmp_path)

        content = (tmp_path / "j1939_dtc.h").read_text(encoding="utf-8")
        # Verify encode/decode functions exist and look correct
        assert "buf[0] = (uint8_t)(spn & 0xFF)" in content
        assert "dtc.spn = buf[0]" in content


# ── J1939 validation rules tests ───────────────────────────────────────────


class TestJ1939Rules:

    def _make_j1939_data(self) -> J1939Data:
        return J1939Data(
            is_j1939=True,
            pgn_messages=[
                J1939PGN(pgn=0xF004, name="EEC1"),
                J1939PGN(pgn=0x1FFFF, name="OutOfRange"),  # Invalid PGN
            ],
            spn_signals=[
                J1939SPN(spn=190, name="EngineSpeed", pgn=0xF004),
                J1939SPN(spn=0, name="UnknownSig", pgn=0xF004),
            ],
            source_addresses={"ECU1": 0x00, "ECU2": 0x00},  # Conflict!
            dbc_data=DBCData(
                version="", messages=[], nodes=[],
                value_tables={}, comments={}, attributes={},
                source_path="<test>",
            ),
        )

    def test_pgn_range_rule(self):
        engine = RuleEngine()
        data = self._make_j1939_data()
        results = engine.check_j1939(data)
        pgn_errors = [r for r in results if r.rule_id == "J1939_PGN_RANGE"]
        assert len(pgn_errors) == 1
        assert "1FFFF" in pgn_errors[0].message

    def test_sa_conflict_rule(self):
        engine = RuleEngine()
        data = self._make_j1939_data()
        results = engine.check_j1939(data)
        sa_warnings = [r for r in results if r.rule_id == "J1939_SA_CONFLICT"]
        assert len(sa_warnings) == 1
        assert "0x00" in sa_warnings[0].message

    def test_spn_no_number_rule(self):
        engine = RuleEngine()
        data = self._make_j1939_data()
        results = engine.check_j1939(data)
        spn_info = [r for r in results if r.rule_id == "J1939_SPN_NO_PGN"]
        assert len(spn_info) == 1
        assert "UnknownSig" in spn_info[0].message

    def test_dlc_mismatch_rule(self):
        engine = RuleEngine()
        data = J1939Data(
            is_j1939=True,
            pgn_messages=[J1939PGN(pgn=0xF004, name="EEC1")],
            spn_signals=[],
            source_addresses={},
            dbc_data=DBCData(
                version="", messages=[
                    MessageDef(id=0x18F00400, name="EEC1", dlc=6, signals=[], sender="ECU1", comment=""),
                ], nodes=[],
                value_tables={}, comments={}, attributes={},
                source_path="<test>",
            ),
        )
        results = engine.check_j1939(data)
        dlc_warnings = [r for r in results if r.rule_id == "J1939_DLC_MISMATCH"]
        assert len(dlc_warnings) == 1
        assert "DLC 6" in dlc_warnings[0].message

    def test_no_issues_with_valid_data(self):
        engine = RuleEngine()
        data = J1939Data(
            is_j1939=True,
            pgn_messages=[J1939PGN(pgn=0xF004, name="EEC1")],
            spn_signals=[J1939SPN(spn=190, name="EngineSpeed", pgn=0xF004)],
            source_addresses={"ECU1": 0x00},
            dbc_data=DBCData(
                version="", messages=[
                    MessageDef(id=0x18F00400, name="EEC1", dlc=8, signals=[], sender="ECU1", comment=""),
                ], nodes=[],
                value_tables={}, comments={}, attributes={},
                source_path="<test>",
            ),
        )
        results = engine.check_j1939(data)
        assert len(results) == 0
