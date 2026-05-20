"""J1939 Transport Protocol — multi-frame BAM/RTS-CTS reassembly."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from core.parsers.j1939_parser import J1939TPMessage, extract_pgn


# ── TP Control byte types ──────────────────────────────────────────────────

class TPControl:
    """Transport Protocol control byte values (PGN 0xEC00)."""
    BAM = 0x20        # Broadcast Announce Message
    RTS = 0x10        # Request To Send
    CTS = 0x11        # Clear To Send
    EOM = 0x13        # End of Message
    ABORT = 0xFF      # Connection Abort


# ── TP Abort reasons ───────────────────────────────────────────────────────

class TPAbort:
    """Abort reason codes."""
    BUSY = 0x01
    RESOURCES = 0x02
    TIMEOUT = 0x03
    UNEXPECTED_DT = 0x04
    BAD_TRANSFER = 0x05


# ── Reassembly state ───────────────────────────────────────────────────────

@dataclass
class _TPSession:
    """Tracks an in-progress TP reassembly."""
    pgn: int
    total_length: int
    max_packets: int
    source_address: int
    tp_type: str  # "BAM" or "RTS_CTS"
    received_packets: dict[int, bytes] = field(default_factory=dict)
    expected_seq: int = 1  # Next expected DT sequence number
    last_activity: float = field(default_factory=time.monotonic)

    @property
    def bytes_received(self) -> int:
        return sum(len(d) for d in self.received_packets.values())

    @property
    def is_complete(self) -> bool:
        return len(self.received_packets) >= self.max_packets

    def add_packet(self, seq: int, data: bytes) -> None:
        self.received_packets[seq] = data
        self.expected_seq = seq + 1
        self.last_activity = time.monotonic()

    def reassemble(self) -> bytes:
        """Reassemble payload from received packets in order."""
        parts = [self.received_packets[i] for i in sorted(self.received_packets)]
        raw = b"".join(parts)
        return raw[: self.total_length]


# ── Transport Protocol handler ─────────────────────────────────────────────

class J1939TransportProtocol:
    """Reassemble multi-frame J1939 messages (BAM and RTS/CTS).

    Usage::

        tp = J1939TransportProtocol()
        for can_id, data in trace:
            result = tp.process_frame(can_id, data)
            if result:
                print(f"Got TP message PGN=0x{result.pgn:04X}, "
                      f"{result.total_length} bytes")
    """

    TP_CM_PGN = 0xEC00
    TP_DT_PGN = 0xEB00
    BAM_MAX_SIZE = 1785
    RTS_CTS_PACKET_SIZE = 255  # Max data bytes per CTS
    SESSION_TIMEOUT = 1.25  # seconds — per J1939 standard

    def __init__(self) -> None:
        self._sessions: dict[tuple[int, int], _TPSession] = {}
        # key = (pgn, source_address)

    def process_frame(self, can_id: int, data: bytes) -> J1939TPMessage | None:
        """Process a CAN frame. Returns completed TP message when done.

        Args:
            can_id: 29-bit extended CAN ID.
            data: Frame payload (up to 8 bytes for classic CAN).

        Returns:
            Completed J1939TPMessage when a multi-frame transfer finishes,
            otherwise None.
        """
        _, pgn, ps, sa = extract_pgn(can_id)

        if pgn == self.TP_CM_PGN:
            return self._handle_tp_cm(sa, data)
        elif pgn == self.TP_DT_PGN:
            return self._handle_tp_dt(sa, data)

        return None

    def _handle_tp_cm(self, sa: int, data: bytes) -> J1939TPMessage | None:
        if len(data) < 8:
            return None

        control = data[0]

        if control == TPControl.BAM:
            return self._handle_bam(sa, data)
        elif control == TPControl.RTS:
            return self._handle_rts(sa, data)
        elif control == TPControl.CTS:
            self._handle_cts(sa, data)
        elif control == TPControl.EOM:
            return self._handle_eom(sa, data)
        elif control == TPControl.ABORT:
            self._handle_abort(sa, data)

        return None

    def _handle_bam(self, sa: int, data: bytes) -> J1939TPMessage | None:
        """Handle BAM: broadcast multi-frame, no flow control."""
        total_length = data[1] | (data[2] << 8)
        max_packets = data[3]
        pgn = data[5] | (data[6] << 8) | (data[7] << 16)

        session = _TPSession(
            pgn=pgn,
            total_length=total_length,
            max_packets=max_packets,
            source_address=sa,
            tp_type="BAM",
        )
        self._sessions[(pgn, sa)] = session
        return None

    def _handle_rts(self, sa: int, data: bytes) -> J1939TPMessage | None:
        """Handle RTS: request to send, expects CTS response."""
        total_length = data[1] | (data[2] << 8)
        max_packets = data[3]
        pgn = data[5] | (data[6] << 8) | (data[7] << 16)

        session = _TPSession(
            pgn=pgn,
            total_length=total_length,
            max_packets=max_packets,
            source_address=sa,
            tp_type="RTS_CTS",
        )
        self._sessions[(pgn, sa)] = session
        # In a real system, we'd send CTS here. For parsing, just wait for DT.
        return None

    def _handle_cts(self, sa: int, data: bytes) -> None:
        """Handle CTS: clear to send. Not needed for passive parsing."""
        pass

    def _handle_eom(self, sa: int, data: bytes) -> J1939TPMessage | None:
        """Handle EOM: end of message acknowledgement."""
        pgn = data[5] | (data[6] << 8) | (data[7] << 16)
        key = (pgn, sa)
        session = self._sessions.get(key)
        if session and session.is_complete:
            result = J1939TPMessage(
                pgn=session.pgn,
                total_length=session.total_length,
                data=session.reassemble(),
                source_address=session.source_address,
                tp_type=session.tp_type,
            )
            del self._sessions[key]
            return result
        return None

    def _handle_abort(self, sa: int, data: bytes) -> None:
        """Handle connection abort."""
        pgn = data[5] | (data[6] << 8) | (data[7] << 16)
        self._sessions.pop((pgn, sa), None)

    def _handle_tp_dt(self, sa: int, data: bytes) -> J1939TPMessage | None:
        """Handle TP.DT: data transfer packet.

        DT frames don't carry PGN, so we match by SA + expected sequence
        number. If seq=1 (start of new transfer), prefer a session that
        expects seq=1. Otherwise, match a session expecting this seq.
        """
        if len(data) < 1:
            return None

        seq = data[0]
        payload = data[1:]

        # Collect candidate sessions from this SA
        candidates = [
            ((pgn, key_sa), session)
            for (pgn, key_sa), session in self._sessions.items()
            if key_sa == sa
        ]

        if not candidates:
            return None

        # Match by expected sequence number to disambiguate concurrent sessions
        target = None
        for key, session in candidates:
            if session.expected_seq == seq:
                target = (key, session)
                break

        # Fallback: if no exact match, use first candidate (single-session case)
        if target is None:
            target = candidates[0]

        key, session = target
        session.add_packet(seq, payload)

        if session.is_complete:
            # BAM: auto-complete when all packets received
            if session.tp_type == "BAM":
                result = J1939TPMessage(
                    pgn=session.pgn,
                    total_length=session.total_length,
                    data=session.reassemble(),
                    source_address=session.source_address,
                    tp_type=session.tp_type,
                )
                del self._sessions[key]
                return result
        return None

    def cleanup_expired(self) -> None:
        """Remove sessions that have timed out."""
        now = time.monotonic()
        expired = [
            key for key, session in self._sessions.items()
            if now - session.last_activity > self.SESSION_TIMEOUT
        ]
        for key in expired:
            del self._sessions[key]

    @property
    def active_sessions(self) -> int:
        """Number of in-progress TP sessions."""
        return len(self._sessions)
