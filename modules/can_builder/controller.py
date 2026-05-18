"""CAN Builder business logic controller."""

from __future__ import annotations

from pathlib import Path

from core.parsers.dbc_parser import (
    DBCParser, DBCData, MessageDef, SignalDef,
    dbc_data_to_dict, dbc_data_from_dict,
)
from core.generators.c_generator import CANCodeGenerator
from core.diff.dbc_diff import DBCDiffEngine, DBCDiffResult
from core.rules.engine import RuleEngine, RuleResult


class CANBuilderController:
    """Orchestrates CAN Builder operations."""

    def __init__(self):
        self.parser = DBCParser()
        self.generator = CANCodeGenerator()
        self.diff_engine = DBCDiffEngine()
        self.rule_engine = RuleEngine()
        self.current_dbc: DBCData | None = None
        self.current_path: Path | None = None

    # ── File operations ──────────────────────────────────────────────────

    def load_dbc(self, file_path: Path) -> tuple[bool, list[str]]:
        """Load a DBC file. Returns (success, errors)."""
        result = self.parser.parse(file_path)
        if result.success:
            self.current_dbc = result.data
            self.current_path = file_path
            return True, []
        return False, result.errors

    def save_dbc(self, output_path: Path | None = None) -> tuple[bool, list[str]]:
        """Save current DBC data (re-export). Placeholder — cantools DB not yet round-tripped."""
        # For now, save as JSON snapshot
        if self.current_dbc is None:
            return False, ["No DBC loaded"]
        target = output_path or self.current_path
        if target is None:
            return False, ["No output path specified"]
        import json
        data = dbc_data_to_dict(self.current_dbc)
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True, []

    # ── Data access ──────────────────────────────────────────────────────

    def get_messages(self) -> list[MessageDef]:
        if self.current_dbc is None:
            return []
        return self.current_dbc.messages

    def get_message_by_name(self, name: str) -> MessageDef | None:
        for msg in self.get_messages():
            if msg.name == name:
                return msg
        return None

    def get_signals_for_message(self, msg_name: str) -> list[SignalDef]:
        msg = self.get_message_by_name(msg_name)
        return msg.signals if msg else []

    def get_signal_as_dict(self, msg_name: str, signal_name: str) -> dict | None:
        """Get a single signal's properties as dict for property panel."""
        for sig in self.get_signals_for_message(msg_name):
            if sig.name == signal_name:
                return {
                    "name": sig.name,
                    "start_bit": sig.start_bit,
                    "bit_length": sig.bit_length,
                    "byte_order": sig.byte_order,
                    "value_type": sig.value_type,
                    "factor": sig.factor,
                    "offset": sig.offset,
                    "minimum": sig.minimum,
                    "maximum": sig.maximum,
                    "unit": sig.unit,
                    "comment": sig.comment,
                    "receivers": ", ".join(sig.receivers),
                }
        return None

    # ── Edit operations ──────────────────────────────────────────────────

    def update_signal(self, msg_name: str, signal_name: str, **kwargs) -> bool:
        """Update a signal's properties."""
        msg = self.get_message_by_name(msg_name)
        if msg is None:
            return False
        for sig in msg.signals:
            if sig.name == signal_name:
                for key, value in kwargs.items():
                    if hasattr(sig, key):
                        if key == "receivers" and isinstance(value, str):
                            value = [r.strip() for r in value.split(",") if r.strip()]
                        setattr(sig, key, value)
                return True
        return False

    def add_signal(self, msg_name: str, signal: SignalDef) -> bool:
        """Add a new signal to a message."""
        msg = self.get_message_by_name(msg_name)
        if msg is None:
            return False
        # Check name uniqueness
        if any(s.name == signal.name for s in msg.signals):
            return False
        msg.signals.append(signal)
        return True

    def remove_signal(self, msg_name: str, signal_name: str) -> bool:
        """Remove a signal from a message."""
        msg = self.get_message_by_name(msg_name)
        if msg is None:
            return False
        original_len = len(msg.signals)
        msg.signals = [s for s in msg.signals if s.name != signal_name]
        return len(msg.signals) < original_len

    # ── Validation ───────────────────────────────────────────────────────

    def validate(self) -> list[RuleResult]:
        """Run all validation rules on the current DBC."""
        if self.current_dbc is None:
            return []
        return self.rule_engine.check_dbc(self.current_dbc)

    # ── Diff ─────────────────────────────────────────────────────────────

    def compare_with(self, other_path: Path, as_old: bool = True) -> DBCDiffResult | None:
        """Compare current DBC with another file.

        as_old=True:  other_path is the old version, current is the new version.
        as_old=False: current is the old version, other_path is the new version.
        """
        if self.current_dbc is None:
            return None
        result = self.parser.parse(other_path)
        if not result.success:
            return None
        if as_old:
            return self.diff_engine.compare(result.data, self.current_dbc)
        return self.diff_engine.compare(self.current_dbc, result.data)

    # ── Code generation ──────────────────────────────────────────────────

    def generate_code(self, output_dir: Path) -> tuple[bool, list[str]]:
        """Generate C code from current DBC."""
        if self.current_dbc is None:
            return False, ["No DBC loaded"]
        gen_result = self.generator.generate(self.current_dbc, output_dir)
        return gen_result.success, gen_result.errors
