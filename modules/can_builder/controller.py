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
        """Save current DBC data as a real DBC file via cantools."""
        if self.current_dbc is None:
            return False, ["No DBC loaded"]
        target = output_path or self.current_path
        if target is None:
            return False, ["No output path specified"]

        try:
            import cantools
            import cantools.database
            import cantools.database.can
            from cantools.database.conversion import (
                IdentityConversion, LinearConversion, NamedSignalConversion,
            )
            from collections import OrderedDict

            # Build cantools Message objects
            ct_messages: list[cantools.database.can.Message] = []
            for msg_def in self.current_dbc.messages:
                ct_signals: list[cantools.database.can.Signal] = []
                for sig_def in msg_def.signals:
                    is_little_endian = sig_def.byte_order == "little_endian"
                    is_signed = sig_def.value_type == "signed"
                    # Determine if conversion needs float representation
                    is_float = (sig_def.factor != int(sig_def.factor)
                                or sig_def.offset != int(sig_def.offset))

                    # Build conversion object
                    if sig_def.value_descriptions:
                        choices: OrderedDict[int, str] = OrderedDict()
                        for val, desc in sorted(sig_def.value_descriptions.items()):
                            choices[int(val)] = str(desc)
                        conversion = NamedSignalConversion(
                            scale=sig_def.factor,
                            offset=sig_def.offset,
                            choices=choices,
                            is_float=is_float,
                        )
                    elif sig_def.factor != 1.0 or sig_def.offset != 0.0:
                        conversion = LinearConversion(
                            scale=sig_def.factor,
                            offset=sig_def.offset,
                            is_float=is_float,
                        )
                    else:
                        conversion = IdentityConversion(is_float=is_float)

                    # Multiplexer fields
                    is_multiplexer = False
                    multiplexer_ids: list[int] | None = None
                    if sig_def.mux:
                        if sig_def.mux.get("mux_type") == "multiplexor":
                            is_multiplexer = True
                        elif sig_def.mux.get("mux_type") == "multiplexed":
                            mux_val = sig_def.mux.get("mux_value")
                            multiplexer_ids = [int(mux_val)] if mux_val is not None else []

                    ct_sig = cantools.database.can.Signal(
                        name=sig_def.name,
                        start=sig_def.start_bit,
                        length=sig_def.bit_length,
                        byte_order='little_endian' if is_little_endian else 'big_endian',
                        is_signed=is_signed,
                        conversion=conversion,
                        minimum=sig_def.minimum if sig_def.minimum != 0.0 else None,
                        maximum=sig_def.maximum if sig_def.maximum != 0.0 else None,
                        unit=sig_def.unit or None,
                        receivers=sig_def.receivers if sig_def.receivers else [],
                        comment=sig_def.comment or None,
                        is_multiplexer=is_multiplexer,
                        multiplexer_ids=multiplexer_ids,
                    )
                    ct_signals.append(ct_sig)

                ct_msg = cantools.database.can.Message(
                    frame_id=msg_def.id,
                    name=msg_def.name,
                    length=msg_def.dlc,
                    signals=ct_signals,
                    senders=[msg_def.sender] if msg_def.sender else [],
                    comment=msg_def.comment or None,
                    is_extended_frame=msg_def.is_extended,
                    unused_bit_pattern=0,
                    strict=False,
                )
                ct_messages.append(ct_msg)

            # Build cantools Database
            db = cantools.database.Database(
                messages=ct_messages,
                nodes=[cantools.database.can.Node(name=n) for n in self.current_dbc.nodes],
                version=self.current_dbc.version or "",
                dbc_specifics=None,
            )

            # Write DBC file
            with open(target, "w", encoding="utf-8") as f:
                db.dump(f)

            return True, []
        except cantools.database.Error as e:
            return False, [f"cantools database error: {e}"]
        except OSError as e:
            return False, [f"File write error: {e}"]

    def save_json_snapshot(self, output_path: Path | None = None) -> tuple[bool, list[str]]:
        """Save current DBC data as a JSON snapshot (legacy format)."""
        if self.current_dbc is None:
            return False, ["No DBC loaded"]
        target = output_path or self.current_path
        if target is None:
            return False, ["No output path specified"]
        try:
            import json
            data = dbc_data_to_dict(self.current_dbc)
            target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True, []
        except OSError as e:
            return False, [f"File write error: {e}"]

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
