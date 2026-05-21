"""Configurable validation rule engine for DBC / ARXML / Diagnostics."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.parsers.arxml_parser import ARXMLData
from core.parsers.dbc_parser import DBCData
from core.parsers.j1939_parser import J1939Data, extract_pgn


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class RuleResult:
    """Single validation finding."""

    rule_id: str
    severity: Severity
    message: str
    location: str  # e.g. "VCU_Status.VCU_SOC"
    suggestion: str = ""


class RuleEngine:
    """Run validation rules on DBC / ARXML / diagnostic data."""

    VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(self):
        self._plugin_rules: list[Any] = []

    def register_plugin_rules(self, rules: list[Any]) -> None:
        """Register rule plugins to be executed alongside built-in rules."""
        self._plugin_rules.extend(rules)

    def check_arxml(self, data: ARXMLData) -> list[RuleResult]:
        """Run all ARXML / SWC validation rules."""
        results: list[RuleResult] = []
        results.extend(self._check_swc_naming(data))
        results.extend(self._check_port_uniqueness(data))
        results.extend(self._check_orphan_interfaces(data))
        results.extend(self._check_runnable_naming(data))
        results.extend(self._check_empty_swc(data))
        results.extend(self._check_duplicate_swc_names(data))
        results.extend(self._check_composition_connectivity(data))
        for plugin in self._plugin_rules:
            if hasattr(plugin, "check_arxml"):
                results.extend(plugin.check_arxml(data))
        return results

    def check_dbc(self, data: DBCData) -> list[RuleResult]:
        """Run all DBC validation rules."""
        results: list[RuleResult] = []
        results.extend(self._check_signal_overlap(data))
        results.extend(self._check_byte_order_consistency(data))
        results.extend(self._check_value_range(data))
        results.extend(self._check_naming_convention(data))
        results.extend(self._check_duplicate_ids(data))
        results.extend(self._check_dlc_vs_signals(data))
        results.extend(self._check_canfd_dlc(data))
        for plugin in self._plugin_rules:
            if hasattr(plugin, "check_dbc"):
                results.extend(plugin.check_dbc(data))
        return results

    def check_j1939(self, data: J1939Data) -> list[RuleResult]:
        """Run all J1939 protocol validation rules."""
        results: list[RuleResult] = []
        results.extend(self._check_j1939_pgn_range(data))
        results.extend(self._check_j1939_dlc(data))
        results.extend(self._check_j1939_spn_no_pgn(data))
        results.extend(self._check_j1939_sa_conflict(data))
        for plugin in self._plugin_rules:
            if hasattr(plugin, "check_j1939"):
                results.extend(plugin.check_j1939(data))
        return results

    # ── Signal overlap ───────────────────────────────────────────────────

    def _check_signal_overlap(self, data: DBCData) -> list[RuleResult]:
        results: list[RuleResult] = []
        for msg in data.messages:
            occupied: dict[int, str] = {}
            for sig in msg.signals:
                bits = set()
                if sig.byte_order == "little_endian":
                    # Little endian: start_bit is LSB, bits go upward
                    for i in range(sig.bit_length):
                        byte_idx = (sig.start_bit + i) // 8
                        bit_idx = (sig.start_bit + i) % 8
                        bit_pos = byte_idx * 8 + bit_idx
                        bits.add(bit_pos)
                else:
                    # Big endian: start_bit is MSB
                    for i in range(sig.bit_length):
                        bits.add(sig.start_bit - i)

                for bit in bits:
                    if bit in occupied:
                        results.append(
                            RuleResult(
                                rule_id="DBC_OVERLAP",
                                severity=Severity.ERROR,
                                message=(f"Signal '{sig.name}' overlaps with '{occupied[bit]}' at bit position {bit}"),
                                location=f"{msg.name}.{sig.name}",
                                suggestion="Adjust start_bit or bit_length to resolve overlap",
                            )
                        )
                    else:
                        occupied[bit] = sig.name
        return results

    # ── Byte order consistency ───────────────────────────────────────────

    def _check_byte_order_consistency(self, data: DBCData) -> list[RuleResult]:
        results: list[RuleResult] = []
        for msg in data.messages:
            orders = set(s.byte_order for s in msg.signals)
            if len(orders) > 1:
                results.append(
                    RuleResult(
                        rule_id="DBC_MIXED_ENDIAN",
                        severity=Severity.WARNING,
                        message=(f"Message contains signals with mixed byte orders: {', '.join(orders)}"),
                        location=msg.name,
                        suggestion="Consider using consistent byte order within a message",
                    )
                )
        return results

    # ── Value range ──────────────────────────────────────────────────────

    def _check_value_range(self, data: DBCData) -> list[RuleResult]:
        results: list[RuleResult] = []
        for msg in data.messages:
            for sig in msg.signals:
                # Check if physical range fits in raw range
                raw_max = (2**sig.bit_length) - 1
                physical_min = sig.offset
                physical_max = raw_max * sig.factor + sig.offset

                if sig.minimum < physical_min:
                    results.append(
                        RuleResult(
                            rule_id="DBC_RANGE_BELOW",
                            severity=Severity.WARNING,
                            message=(
                                f"Signal minimum ({sig.minimum}) is below the physical "
                                f"minimum ({physical_min}) — unreachable value"
                            ),
                            location=f"{msg.name}.{sig.name}",
                            suggestion="Adjust minimum or factor/offset",
                        )
                    )
                if sig.maximum > physical_max + sig.factor:
                    results.append(
                        RuleResult(
                            rule_id="DBC_RANGE_ABOVE",
                            severity=Severity.WARNING,
                            message=(
                                f"Signal maximum ({sig.maximum}) exceeds the physical "
                                f"maximum ({physical_max}) — unreachable value"
                            ),
                            location=f"{msg.name}.{sig.name}",
                            suggestion="Adjust maximum or bit_length",
                        )
                    )

                # Check for negative values in unsigned signals
                if sig.value_type == "unsigned" and sig.offset < 0:
                    results.append(
                        RuleResult(
                            rule_id="DBC_UNSIGNED_NEG_OFFSET",
                            severity=Severity.INFO,
                            message=(
                                f"Unsigned signal has negative offset ({sig.offset}) — physical value can be negative"
                            ),
                            location=f"{msg.name}.{sig.name}",
                            suggestion="Verify this is intentional",
                        )
                    )
        return results

    # ── Naming convention ────────────────────────────────────────────────

    def _check_naming_convention(self, data: DBCData) -> list[RuleResult]:
        results: list[RuleResult] = []
        pattern = self.VALID_IDENTIFIER

        for msg in data.messages:
            if not pattern.match(msg.name):
                results.append(
                    RuleResult(
                        rule_id="DBC_NAME_INVALID",
                        severity=Severity.WARNING,
                        message=f"Message name '{msg.name}' contains invalid characters",
                        location=msg.name,
                        suggestion="Use only letters, digits, and underscores; start with letter or underscore",
                    )
                )
            for sig in msg.signals:
                if not pattern.match(sig.name):
                    results.append(
                        RuleResult(
                            rule_id="DBC_NAME_INVALID",
                            severity=Severity.WARNING,
                            message=f"Signal name '{sig.name}' contains invalid characters",
                            location=f"{msg.name}.{sig.name}",
                            suggestion="Use only letters, digits, and underscores; start with letter or underscore",
                        )
                    )
        return results

    # ── Duplicate IDs ────────────────────────────────────────────────────

    def _check_duplicate_ids(self, data: DBCData) -> list[RuleResult]:
        results: list[RuleResult] = []
        seen: dict[int, str] = {}
        for msg in data.messages:
            if msg.id in seen:
                results.append(
                    RuleResult(
                        rule_id="DBC_DUP_ID",
                        severity=Severity.ERROR,
                        message=(f"Duplicate message ID 0x{msg.id:03X}: '{msg.name}' and '{seen[msg.id]}'"),
                        location=msg.name,
                        suggestion="Assign a unique CAN ID to each message",
                    )
                )
            else:
                seen[msg.id] = msg.name
        return results

    # ── DLC vs signal coverage ───────────────────────────────────────────

    def _check_dlc_vs_signals(self, data: DBCData) -> list[RuleResult]:
        results: list[RuleResult] = []
        for msg in data.messages:
            max_bit = 0
            for sig in msg.signals:
                end_bit = sig.start_bit + sig.bit_length
                if end_bit > max_bit:
                    max_bit = end_bit
            needed_bytes = (max_bit + 7) // 8
            if needed_bytes > msg.dlc:
                results.append(
                    RuleResult(
                        rule_id="DBC_DLC_SHORT",
                        severity=Severity.ERROR,
                        message=(f"Signals require {needed_bytes} bytes but DLC is {msg.dlc}"),
                        location=msg.name,
                        suggestion=f"Increase DLC to at least {needed_bytes}",
                    )
                )
        return results

    # ── CAN FD DLC validation ─────────────────────────────────────────────

    _VALID_FD_DLCS = {0, 8, 12, 16, 20, 24, 32, 48, 64}

    def _check_canfd_dlc(self, data: DBCData) -> list[RuleResult]:
        """Validate CAN FD DLC values and FD flag consistency."""
        results: list[RuleResult] = []
        for msg in data.messages:
            if msg.is_fd or msg.dlc > 8:
                if msg.dlc not in self._VALID_FD_DLCS:
                    results.append(
                        RuleResult(
                            rule_id="DBC_FD_DLC_INVALID",
                            severity=Severity.ERROR,
                            message=(
                                f"CAN FD message '{msg.name}' has invalid DLC {msg.dlc}. "
                                f"Valid values: {sorted(self._VALID_FD_DLCS)}"
                            ),
                            location=msg.name,
                            suggestion=f"Set DLC to one of {sorted(self._VALID_FD_DLCS)}",
                        )
                    )
                if msg.dlc > 8 and not msg.is_fd:
                    results.append(
                        RuleResult(
                            rule_id="DBC_FD_FLAG_MISSING",
                            severity=Severity.WARNING,
                            message=(f"Message '{msg.name}' has DLC {msg.dlc} > 8 but is not marked as CAN FD"),
                            location=msg.name,
                            suggestion="Set is_fd=True for CAN FD frames",
                        )
                    )
        return results

    # ── J1939: PGN range ─────────────────────────────────────────────────

    def _check_j1939_pgn_range(self, data: J1939Data) -> list[RuleResult]:
        results: list[RuleResult] = []
        for pgn in data.pgn_messages:
            if pgn.pgn > 0xFFFF:
                results.append(
                    RuleResult(
                        rule_id="J1939_PGN_RANGE",
                        severity=Severity.ERROR,
                        message=f"PGN 0x{pgn.pgn:04X} out of J1939 range (0x0000-0xFFFF)",
                        location=f"PGN:{pgn.name}",
                        suggestion="Check CAN ID extraction — PGN should be 18 bits max",
                    )
                )
        return results

    # ── J1939: DLC check ───────────────────────────────────────────────────

    def _check_j1939_dlc(self, data: J1939Data) -> list[RuleResult]:
        results: list[RuleResult] = []
        if not data.dbc_data:
            return results
        for msg in data.dbc_data.messages:
            if msg.is_fd:
                continue  # CAN FD has its own DLC rules
            _, pgn, _, _ = extract_pgn(msg.id)
            if msg.dlc != 8 and msg.dlc > 0:
                results.append(
                    RuleResult(
                        rule_id="J1939_DLC_MISMATCH",
                        severity=Severity.WARNING,
                        message=(
                            f"J1939 message '{msg.name}' (PGN 0x{pgn:04X}) has DLC {msg.dlc}, "
                            f"expected 8 for standard J1939"
                        ),
                        location=msg.name,
                        suggestion="Set DLC to 8 for standard J1939 messages",
                    )
                )
        return results

    # ── J1939: SPN without PGN ─────────────────────────────────────────────

    def _check_j1939_spn_no_pgn(self, data: J1939Data) -> list[RuleResult]:
        results: list[RuleResult] = []
        for spn in data.spn_signals:
            if spn.spn == 0:
                results.append(
                    RuleResult(
                        rule_id="J1939_SPN_NO_PGN",
                        severity=Severity.INFO,
                        message=(
                            f"Signal '{spn.name}' has no SPN number — add 'SPN <number>' to signal comment or attribute"
                        ),
                        location=f"SPN:{spn.name}",
                        suggestion="Add SPN number to signal comment (e.g. 'SPN 190')",
                    )
                )
        return results

    # ── J1939: Source address conflict ─────────────────────────────────────

    def _check_j1939_sa_conflict(self, data: J1939Data) -> list[RuleResult]:
        results: list[RuleResult] = []
        sa_to_names: dict[int, list[str]] = {}
        for node, sa in data.source_addresses.items():
            sa_to_names.setdefault(sa, []).append(node)
        for sa, names in sa_to_names.items():
            if len(names) > 1:
                results.append(
                    RuleResult(
                        rule_id="J1939_SA_CONFLICT",
                        severity=Severity.WARNING,
                        message=(f"Source address 0x{sa:02X} assigned to multiple nodes: {', '.join(names)}"),
                        location=f"SA:0x{sa:02X}",
                        suggestion="Each J1939 node should have a unique source address",
                    )
                )
        return results

    # ── ARXML: SWC naming ──────────────────────────────────────────────────

    def _check_swc_naming(self, data: ARXMLData) -> list[RuleResult]:
        results: list[RuleResult] = []
        pattern = self.VALID_IDENTIFIER
        for swc in data.swcs:
            if not pattern.match(swc.name):
                results.append(
                    RuleResult(
                        rule_id="ARXML_SWC_NAME",
                        severity=Severity.WARNING,
                        message=f"SWC name '{swc.name}' contains invalid characters",
                        location=swc.name,
                        suggestion="Use only letters, digits, and underscores; start with letter or underscore",
                    )
                )
            if not swc.description.strip():
                results.append(
                    RuleResult(
                        rule_id="ARXML_SWC_NO_DESC",
                        severity=Severity.INFO,
                        message=f"SWC '{swc.name}' has no description",
                        location=swc.name,
                        suggestion="Add a description for documentation",
                    )
                )
        return results

    # ── ARXML: Port uniqueness ─────────────────────────────────────────────

    def _check_port_uniqueness(self, data: ARXMLData) -> list[RuleResult]:
        results: list[RuleResult] = []
        for swc in data.swcs:
            seen: dict[str, str] = {}
            for port in swc.ports:
                if port.name in seen:
                    results.append(
                        RuleResult(
                            rule_id="ARXML_DUP_PORT",
                            severity=Severity.ERROR,
                            message=f"Duplicate port name '{port.name}' in SWC '{swc.name}'",
                            location=f"{swc.name}.{port.name}",
                            suggestion="Use unique port names within each SWC",
                        )
                    )
                else:
                    seen[port.name] = port.name
        return results

    # ── ARXML: Orphan interfaces ───────────────────────────────────────────

    def _check_orphan_interfaces(self, data: ARXMLData) -> list[RuleResult]:
        results: list[RuleResult] = []
        iface_names = {i.name for i in data.interfaces}
        for swc in data.swcs:
            for port in swc.ports:
                if port.interface_ref and port.interface_ref not in iface_names:
                    results.append(
                        RuleResult(
                            rule_id="ARXML_ORPHAN_IFACE",
                            severity=Severity.WARNING,
                            message=(
                                f"Port '{port.name}' references interface '{port.interface_ref}' "
                                f"which is not defined in this file"
                            ),
                            location=f"{swc.name}.{port.name}",
                            suggestion="Ensure the interface is imported or defined",
                        )
                    )
        return results

    # ── ARXML: Runnable naming ─────────────────────────────────────────────

    def _check_runnable_naming(self, data: ARXMLData) -> list[RuleResult]:
        results: list[RuleResult] = []
        pattern = self.VALID_IDENTIFIER
        for swc in data.swcs:
            for run in swc.runnables:
                if not pattern.match(run.name):
                    results.append(
                        RuleResult(
                            rule_id="ARXML_RUN_NAME",
                            severity=Severity.WARNING,
                            message=f"Runnable name '{run.name}' contains invalid characters",
                            location=f"{swc.name}.{run.name}",
                            suggestion="Use only letters, digits, and underscores",
                        )
                    )
        return results

    # ── ARXML: Empty SWC ───────────────────────────────────────────────────

    def _check_empty_swc(self, data: ARXMLData) -> list[RuleResult]:
        results: list[RuleResult] = []
        for swc in data.swcs:
            if not swc.runnables:
                results.append(
                    RuleResult(
                        rule_id="ARXML_NO_RUNNABLE",
                        severity=Severity.WARNING,
                        message=f"SWC '{swc.name}' has no runnable entities",
                        location=swc.name,
                        suggestion="Add at least one runnable for the SWC to execute",
                    )
                )
            if not swc.ports:
                results.append(
                    RuleResult(
                        rule_id="ARXML_NO_PORTS",
                        severity=Severity.INFO,
                        message=f"SWC '{swc.name}' has no ports",
                        location=swc.name,
                        suggestion="Consider adding ports for inter-SWC communication",
                    )
                )
        return results

    # ── ARXML: Duplicate SWC names ─────────────────────────────────────────

    def _check_duplicate_swc_names(self, data: ARXMLData) -> list[RuleResult]:
        results: list[RuleResult] = []
        seen: dict[str, int] = {}
        for swc in data.swcs:
            seen[swc.name] = seen.get(swc.name, 0) + 1
        for name, count in seen.items():
            if count > 1:
                results.append(
                    RuleResult(
                        rule_id="ARXML_DUP_SWC",
                        severity=Severity.ERROR,
                        message=f"Duplicate SWC name '{name}' ({count} instances)",
                        location=name,
                        suggestion="Each SWC must have a unique name",
                    )
                )
        return results

    # ── ARXML: Composition connectivity ────────────────────────────────────

    def _check_composition_connectivity(self, data: ARXMLData) -> list[RuleResult]:
        results: list[RuleResult] = []
        swc_map = {s.name: s for s in data.swcs}
        for comp in data.compositions:
            # Check all referenced SWCs exist
            for comp_name in comp.components:
                if comp_name not in swc_map:
                    results.append(
                        RuleResult(
                            rule_id="ARXML_COMP_MISSING_SWC",
                            severity=Severity.ERROR,
                            message=f"Composition '{comp.name}' references non-existent SWC '{comp_name}'",
                            location=comp.name,
                            suggestion="Ensure all component references are valid",
                        )
                    )
            # Check for unmatched provided/required ports
            provided: dict[str, str] = {}  # interface_ref → swc.name
            required: dict[str, str] = {}
            for comp_name in comp.components:
                swc = swc_map.get(comp_name)
                if swc is None:
                    continue
                for port in swc.ports:
                    if port.direction.value == "provided":
                        provided[port.interface_ref] = comp_name
                    else:
                        required[port.interface_ref] = comp_name
            for iface_ref in required:
                if iface_ref not in provided:
                    results.append(
                        RuleResult(
                            rule_id="ARXML_UNMATCHED_REQUIRED",
                            severity=Severity.WARNING,
                            message=(
                                f"Composition '{comp.name}': required interface '{iface_ref}' has no matching provider"
                            ),
                            location=comp.name,
                            suggestion="Add an SWC with a P-Port providing this interface",
                        )
                    )
        return results
