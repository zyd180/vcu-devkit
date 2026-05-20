"""J1939 protocol parser — PGN/SPN extraction, auto-detection, and enrichment."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cantools

_SPN_PATTERN = re.compile(r"SPN[:\s]+(\d+)", re.IGNORECASE)

from core.parsers.base import BaseParser, ParseResult
from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class J1939PGN:
    """J1939 Parameter Group Number."""
    pgn: int
    name: str
    description: str = ""
    data_length: int = 8
    transmission_rate: str = ""
    source_address: int = 0xFF


@dataclass
class J1939SPN:
    """J1939 Suspect Parameter Number."""
    spn: int
    name: str
    description: str = ""
    pgn: int = 0
    start_bit: int = 0
    bit_length: int = 0
    factor: float = 1.0
    offset: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    unit: str = ""


@dataclass
class J1939DTC:
    """J1939 Diagnostic Trouble Code."""
    spn: int
    fmi: int
    occurrence: int = 0
    status: str = "active"
    description: str = ""


@dataclass
class J1939TPMessage:
    """Transport Protocol multi-frame message (BAM/RTS-CTS)."""
    pgn: int
    total_length: int
    data: bytes = b""
    source_address: int = 0xFF
    tp_type: str = "BAM"


@dataclass
class J1939Data:
    """Complete J1939-enriched data from a DBC file."""
    pgn_messages: list[J1939PGN] = field(default_factory=list)
    spn_signals: list[J1939SPN] = field(default_factory=list)
    source_addresses: dict[str, int] = field(default_factory=dict)  # node_name → SA
    is_j1939: bool = False
    dbc_data: DBCData | None = None


# ── PGN extraction ───────────────────────────────────────────────────────────


def extract_pgn(can_id: int) -> tuple[int, int, int, int]:
    """Extract priority, PGN, PS, and source address from a 29-bit CAN ID.

    Returns (priority, pgn, ps, source_address).
    """
    priority = (can_id >> 26) & 0x07
    pf = (can_id >> 16) & 0xFF
    ps = (can_id >> 8) & 0xFF
    sa = can_id & 0xFF
    if pf >= 240:
        # PDU2 format: PS is group extension, part of PGN
        pgn = (pf << 8) | ps
    else:
        # PDU1 format: PS is destination address, not part of PGN
        pgn = pf << 8
    return priority, pgn, ps, sa


def is_pgn_in_range(pgn: int) -> bool:
    """Check if PGN is in valid J1939 range (0x0000-0xFEFF).

    0xFF00-0xFFFF are reserved for TP.CM, TP.DT, and other management PGNs.
    """
    return 0 <= pgn <= 0xFEFF


# ── Parser ───────────────────────────────────────────────────────────────────


class J1939Parser(BaseParser):
    """Parse DBC files and extract J1939 protocol information."""

    # Minimum fraction of messages that must be extended frames to detect J1939
    _J1939_THRESHOLD = 0.5

    def supported_extensions(self) -> list[str]:
        return [".dbc"]

    def parse(self, file_path: Path) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            return ParseResult(success=False, errors=[f"File not found: {path}"])
        try:
            db = cantools.database.load_file(str(path))
            dbc_data = self._convert_dbc(db, str(path))
            j1939_data = self._extract_j1939(db, dbc_data)
            return ParseResult(success=True, data=j1939_data, source_path=path)
        except (OSError, ValueError) as exc:
            return ParseResult(success=False, errors=[str(exc)])
        except cantools.database.Error as exc:
            return ParseResult(success=False, errors=[f"DBC parse error: {exc}"])

    def validate(self, file_path: Path) -> list[str]:
        errors: list[str] = []
        try:
            db = cantools.database.load_file(str(file_path))
            for msg in db.messages:
                if msg.is_extended_frame:
                    _, pgn, _, _ = extract_pgn(msg.frame_id)
                    if not is_pgn_in_range(pgn):
                        errors.append(
                            f"Message {msg.name} (0x{msg.frame_id:08X}): "
                            f"PGN 0x{pgn:04X} out of J1939 range"
                        )
        except Exception as exc:
            errors.append(f"Parse error: {exc}")
        return errors

    # ── Internal ──────────────────────────────────────────────────────────

    def _convert_dbc(self, db: cantools.database.Database, source: str) -> DBCData:
        """Convert cantools DB to VCU DevKit DBCData (reuse DBCParser logic)."""
        from core.parsers.dbc_parser import DBCParser
        parser = DBCParser()
        return parser.convert(db, source)

    def _extract_j1939(self, db: cantools.database.Database, dbc_data: DBCData) -> J1939Data:
        """Extract J1939 protocol information from parsed DBC data."""
        j1939 = J1939Data(dbc_data=dbc_data)

        # Detect if this is a J1939 DBC
        total = len(db.messages)
        if total == 0:
            return j1939

        extended_count = sum(1 for m in db.messages if m.is_extended_frame)
        if extended_count / total < self._J1939_THRESHOLD:
            return j1939

        j1939.is_j1939 = True

        # Extract PGNs and SPNs
        seen_pgns: dict[int, J1939PGN] = {}
        for msg in db.messages:
            if not msg.is_extended_frame:
                continue
            priority, pgn, ps, sa = extract_pgn(msg.frame_id)

            if pgn not in seen_pgns:
                seen_pgns[pgn] = J1939PGN(
                    pgn=pgn,
                    name=msg.name,
                    description=msg.comment or "",
                    data_length=msg.length,
                    source_address=sa,
                )
            j1939.pgn_messages.append(seen_pgns[pgn])

            # Source address mapping
            if msg.senders:
                for sender in msg.senders:
                    if sender and sender not in j1939.source_addresses:
                        j1939.source_addresses[sender] = sa

            # Extract SPNs from signals
            for sig in msg.signals:
                spn = self._extract_spn_number(sig)
                j1939.spn_signals.append(J1939SPN(
                    spn=spn,
                    name=sig.name,
                    description=sig.comment or "",
                    pgn=pgn,
                    start_bit=sig.start,
                    bit_length=sig.length,
                    factor=sig.scale,
                    offset=sig.offset,
                    min_value=sig.minimum or 0.0,
                    max_value=sig.maximum or 0.0,
                    unit=sig.unit or "",
                ))

        return j1939

    @staticmethod
    def _extract_spn_number(sig: cantools.database.Signal) -> int:
        """Try to extract SPN number from signal comment or attributes.

        Common DBC conventions:
            - Comment contains "SPN 190" or "SPN: 190"
            - Attribute "SPN" set on the signal
        """
        comment = sig.comment or ""
        match = _SPN_PATTERN.search(comment)
        if match:
            return int(match.group(1))

        # Check attributes
        if hasattr(sig, "dbc") and sig.dbc:
            attrs = getattr(sig.dbc, "attributes", None) or {}
            for key in ("SPN", "spn"):
                if key in attrs:
                    try:
                        return int(attrs[key])
                    except (ValueError, TypeError):
                        pass

        return 0  # Unknown SPN
