"""DBC file parser — wraps cantools with VCU DevKit data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cantools

from core.parsers.base import BaseParser, ParseResult


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class SignalDef:
    """DBC signal definition."""
    name: str
    start_bit: int
    bit_length: int
    byte_order: str                  # "little_endian" | "big_endian"
    value_type: str                  # "unsigned" | "signed"
    factor: float
    offset: float
    minimum: float
    maximum: float
    unit: str
    comment: str
    receivers: list[str] = field(default_factory=list)
    value_descriptions: dict[int, str] = field(default_factory=dict)
    mux: dict | None = None          # {"mux_type": "multiplexor"|"multiplexed", "mux_value": int|None}


@dataclass
class MessageDef:
    """DBC message definition."""
    id: int                          # CAN ID (numeric, e.g. 0x100 → 256)
    name: str
    dlc: int
    sender: str
    comment: str
    signals: list[SignalDef] = field(default_factory=list)
    is_extended: bool = False


@dataclass
class DBCData:
    """Complete DBC file data."""
    version: str
    messages: list[MessageDef]
    nodes: list[str]
    value_tables: dict[str, dict[int, str]]
    comments: dict[str, str]
    attributes: dict[str, Any]
    source_path: str


# ── Parser ───────────────────────────────────────────────────────────────────


class DBCParser(BaseParser):
    """Parse DBC files via cantools and return VCU DevKit data models."""

    def supported_extensions(self) -> list[str]:
        return [".dbc"]

    def parse(self, file_path: Path) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            return ParseResult(success=False, errors=[f"File not found: {path}"])
        try:
            db = cantools.database.load_file(str(path))
            data = self._convert(db, str(path))
            return ParseResult(success=True, data=data, source_path=path)
        except (OSError, ValueError) as exc:
            return ParseResult(success=False, errors=[str(exc)])
        except cantools.database.Error as exc:
            return ParseResult(success=False, errors=[f"DBC parse error: {exc}"])

    def parse_string(self, content: str) -> ParseResult:
        """Parse DBC content from string (no file I/O)."""
        try:
            db = cantools.database.load_string(content)
            data = self._convert(db, "<string>")
            return ParseResult(success=True, data=data)
        except (ValueError, cantools.database.Error) as exc:
            return ParseResult(success=False, errors=[str(exc)])

    def validate(self, file_path: Path) -> list[str]:
        errors: list[str] = []
        try:
            db = cantools.database.load_file(str(file_path))
            # Check for duplicate message IDs
            ids = [m.frame_id for m in db.messages]
            seen: set[int] = set()
            for mid in ids:
                if mid in seen:
                    errors.append(f"Duplicate message ID: 0x{mid:X}")
                seen.add(mid)
            # Check for signal overlap per message
            for msg in db.messages:
                self._check_signal_overlap(msg, errors)
        except Exception as exc:
            errors.append(f"Parse error: {exc}")
        return errors

    # ── Internal conversion ──────────────────────────────────────────────

    def _convert(self, db: cantools.database.Database, source: str) -> DBCData:
        messages = [self._convert_message(m) for m in db.messages]
        raw_nodes = getattr(db, "nodes", None) or []
        nodes = [str(n) for n in raw_nodes]
        value_tables: dict[str, dict[int, str]] = {}
        if hasattr(db, "value_tables"):
            value_tables = {k: dict(v) for k, v in db.value_tables.items()}
        return DBCData(
            version=getattr(db, "version", "") or "",
            messages=messages,
            nodes=nodes,
            value_tables=value_tables,
            comments={},
            attributes={},
            source_path=source,
        )

    def _convert_message(self, msg: cantools.database.Message) -> MessageDef:
        signals = [self._convert_signal(s) for s in msg.signals]
        comment = msg.comment or ""
        return MessageDef(
            id=msg.frame_id,
            name=msg.name,
            dlc=msg.length,
            sender=msg.senders[0] if msg.senders else "",
            comment=comment,
            signals=signals,
            is_extended=msg.is_extended_frame,
        )

    def _convert_signal(self, sig: cantools.database.Signal) -> SignalDef:
        byte_order = "little_endian" if sig.byte_order == "little_endian" else "big_endian"
        value_type = "signed" if sig.is_signed else "unsigned"

        value_descriptions: dict[int, str] = {}
        if sig.choices:
            value_descriptions = {int(k): str(v) for k, v in sig.choices.items()}

        mux: dict | None = None
        if sig.is_multiplexer:
            mux = {"mux_type": "multiplexor", "mux_value": None}
        elif sig.multiplexer_ids is not None:
            mux = {"mux_type": "multiplexed", "mux_value": sig.multiplexer_ids[0] if sig.multiplexer_ids else None}

        return SignalDef(
            name=sig.name,
            start_bit=sig.start,
            bit_length=sig.length,
            byte_order=byte_order,
            value_type=value_type,
            factor=sig.scale,
            offset=sig.offset,
            minimum=sig.minimum,
            maximum=sig.maximum,
            unit=sig.unit or "",
            comment=sig.comment or "",
            receivers=list(sig.receivers) if sig.receivers else [],
            value_descriptions=value_descriptions,
            mux=mux,
        )

    def _check_signal_overlap(self, msg: cantools.database.Message, errors: list[str]):
        """Check for bit-level signal overlap within a message."""
        occupied: dict[int, str] = {}
        for sig in msg.signals:
            for bit in range(sig.start, sig.start + sig.length):
                if bit in occupied:
                    errors.append(
                        f"Signal overlap in message 0x{msg.frame_id:X} ({msg.name}): "
                        f"'{sig.name}' overlaps with '{occupied[bit]}' at bit {bit}"
                    )
                else:
                    occupied[bit] = sig.name


# ── Serialisation helpers ────────────────────────────────────────────────────


def dbc_data_to_dict(data: DBCData) -> dict:
    """Convert DBCData to a JSON-serialisable dict."""
    return {
        "version": data.version,
        "source_path": data.source_path,
        "nodes": data.nodes,
        "value_tables": data.value_tables,
        "messages": [
            {
                "id": hex(m.id),
                "name": m.name,
                "dlc": m.dlc,
                "sender": m.sender,
                "comment": m.comment,
                "is_extended": m.is_extended,
                "signals": [
                    {
                        "name": s.name,
                        "start_bit": s.start_bit,
                        "bit_length": s.bit_length,
                        "byte_order": s.byte_order,
                        "value_type": s.value_type,
                        "factor": s.factor,
                        "offset": s.offset,
                        "minimum": s.minimum,
                        "maximum": s.maximum,
                        "unit": s.unit,
                        "comment": s.comment,
                        "receivers": s.receivers,
                        "value_descriptions": {str(k): v for k, v in s.value_descriptions.items()},
                        "mux": s.mux,
                    }
                    for s in m.signals
                ],
            }
            for m in data.messages
        ],
    }


def dbc_data_from_dict(d: dict) -> DBCData:
    """Reconstruct DBCData from a dict (reverse of dbc_data_to_dict)."""
    messages = []
    for md in d.get("messages", []):
        signals = []
        for sd in md.get("signals", []):
            signals.append(SignalDef(
                name=sd["name"],
                start_bit=sd["start_bit"],
                bit_length=sd["bit_length"],
                byte_order=sd["byte_order"],
                value_type=sd["value_type"],
                factor=sd["factor"],
                offset=sd["offset"],
                minimum=sd["minimum"],
                maximum=sd["maximum"],
                unit=sd.get("unit", ""),
                comment=sd.get("comment", ""),
                receivers=sd.get("receivers", []),
                value_descriptions={int(k): v for k, v in sd.get("value_descriptions", {}).items()},
                mux=sd.get("mux"),
            ))
        messages.append(MessageDef(
            id=int(md["id"], 16) if isinstance(md["id"], str) else md["id"],
            name=md["name"],
            dlc=md["dlc"],
            sender=md.get("sender", ""),
            comment=md.get("comment", ""),
            signals=signals,
            is_extended=md.get("is_extended", False),
        ))
    return DBCData(
        version=d.get("version", ""),
        messages=messages,
        nodes=d.get("nodes", []),
        value_tables=d.get("value_tables", {}),
        comments=d.get("comments", {}),
        attributes=d.get("attributes", {}),
        source_path=d.get("source_path", ""),
    )
