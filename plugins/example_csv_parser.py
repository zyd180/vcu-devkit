"""Example CSV parser plugin — demonstrates the VCU DevKit plugin system.

This plugin parses a simple CSV format into DBCData. It serves as a
reference for building your own parser plugins.

CSV format:
    message_id,message_name,dlc,signal_name,start_bit,bit_length,factor,offset

To use: place this file in the plugins/ directory and restart VCU DevKit.
"""

from __future__ import annotations

import csv
from pathlib import Path

from core.parsers.base import ParseResult
from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef
from core.plugins.base import ParserPlugin, PluginMeta


class CSVParserPlugin(ParserPlugin):
    """Parse CSV signal definitions into DBCData."""

    @property
    def plugin_meta(self) -> PluginMeta:
        return PluginMeta(
            name="csv_parser",
            version="1.0.0",
            author="VCU DevKit",
            description="Parse CSV signal definition files",
        )

    def supported_extensions(self) -> list[str]:
        return [".csv"]

    def parse(self, file_path: Path) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            return ParseResult(success=False, errors=[f"File not found: {path}"])
        try:
            messages = self._parse_csv(path)
            data = DBCData(
                version="",
                messages=messages,
                nodes=[],
                value_tables={},
                comments={},
                attributes={},
                source_path=str(path),
            )
            return ParseResult(success=True, data=data, source_path=path)
        except Exception as exc:
            return ParseResult(success=False, errors=[str(exc)])

    def validate(self, file_path: Path) -> list[str]:
        errors: list[str] = []
        path = Path(file_path)
        if not path.exists():
            return [f"File not found: {path}"]
        try:
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                required = {"message_id", "message_name", "dlc",
                            "signal_name", "start_bit", "bit_length"}
                if reader.fieldnames is None:
                    errors.append("Empty CSV file")
                    return errors
                missing = required - set(reader.fieldnames)
                if missing:
                    errors.append(f"Missing columns: {', '.join(sorted(missing))}")
        except Exception as exc:
            errors.append(str(exc))
        return errors

    def _parse_csv(self, path: Path) -> list[MessageDef]:
        msg_map: dict[int, MessageDef] = {}
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                msg_id = int(row["message_id"], 0)
                if msg_id not in msg_map:
                    msg_map[msg_id] = MessageDef(
                        id=msg_id,
                        name=row["message_name"],
                        dlc=int(row["dlc"]),
                        sender=row.get("sender", ""),
                        comment=row.get("comment", ""),
                    )
                sig = SignalDef(
                    name=row["signal_name"],
                    start_bit=int(row["start_bit"]),
                    bit_length=int(row["bit_length"]),
                    byte_order=row.get("byte_order", "little_endian"),
                    value_type=row.get("value_type", "unsigned"),
                    factor=float(row.get("factor", 1.0)),
                    offset=float(row.get("offset", 0.0)),
                    minimum=float(row.get("minimum", 0.0)),
                    maximum=float(row.get("maximum", 0.0)),
                    unit=row.get("unit", ""),
                    comment=row.get("comment", ""),
                )
                msg_map[msg_id].signals.append(sig)
        return list(msg_map.values())
