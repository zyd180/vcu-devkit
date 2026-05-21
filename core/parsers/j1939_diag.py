"""J1939 Diagnostic Messages — DM1/DM2 DTC parsing."""

from __future__ import annotations

from core.parsers.j1939_parser import J1939DTC, extract_pgn
from core.parsers.j1939_tp import J1939TransportProtocol

# ── DTC Lamp Status ────────────────────────────────────────────────────────


class DTCLamp:
    """DM1 lamp status byte positions."""

    MALFUNCTION_INDICATOR = 0x00
    RED_STOP = 0x01
    AMBER_WARNING = 0x02
    PROTECT_LAMP = 0x03


LAMP_NAMES = {
    0b00: "off",
    0b01: "on",
    0b10: "reserved",
    0b11: "not_available",
}


# ── Diagnostic message parser ──────────────────────────────────────────────


class J1939Diagnostics:
    """Parse J1939 DM1/DM2 diagnostic messages.

    DM1 (PGN 0xFECA) and DM2 (PGN 0xFECB) carry DTCs in a compact format:
    - Each DTC is 4 bytes
    - Byte 1-2: SPN (19 bits) + lamp status (in first byte for multi-DTC)
    - Byte 3: FMI (5 bits) + SPN high bits (3 bits)
    - Byte 4: Occurrence count (7 bits) + SPN conversion method (1 bit)

    For single-frame (≤8 bytes), the first 2 bytes are lamp status,
    then up to 3 DTCs (3×4 = 12 bytes, but only 6 bytes remain → 1 DTC
    plus lamp header).

    For multi-frame (>8 bytes), use TP reassembly first, then parse DTCs
    from the reassembled payload (4 bytes per DTC, no lamp header in payload).
    """

    DM1_PGN = 0xFECA
    DM2_PGN = 0xFECB
    DTC_BYTE_SIZE = 4

    def __init__(self) -> None:
        self._tp = J1939TransportProtocol()

    def parse_dm1(self, data: bytes) -> list[J1939DTC]:
        """Parse DM1 message payload into DTC list.

        Handles both single-frame and multi-frame (via TP reassembly).
        """
        return self._parse_dtcs(data)

    def parse_dm2(self, data: bytes) -> list[J1939DTC]:
        """Parse DM2 (previously active) DTCs."""
        return self._parse_dtcs(data)

    def process_frame(self, can_id: int, data: bytes) -> list[J1939DTC] | None:
        """Process a CAN frame and return DTCs when available.

        For single-frame DM1/DM2, returns DTCs immediately.
        For multi-frame, returns DTCs after TP reassembly completes.
        """
        _, pgn, _, _ = extract_pgn(can_id)

        if pgn in (self.DM1_PGN, self.DM2_PGN):
            if len(data) <= 8:
                return self._parse_dtcs(data)
            # Multi-frame — shouldn't happen directly, but handle anyway
            return self._parse_dtcs(data)

        # Feed TP frames
        tp_result = self._tp.process_frame(can_id, data)
        if tp_result and tp_result.pgn in (self.DM1_PGN, self.DM2_PGN):
            return self._parse_dtcs(tp_result.data)

        return None

    def _parse_dtcs(self, data: bytes) -> list[J1939DTC]:
        """Parse DTCs from a message payload.

        Single-frame format (up to 1 DTC in 8 bytes):
            Byte 0-1: Lamp status
            Byte 2-5: DTC 1 (4 bytes)
            (Bytes 6-7 are unused — not enough for a second DTC)

        Multi-frame / extended format (after TP reassembly):
            Every 4 bytes = 1 DTC, no lamp header.
        """
        if len(data) < 4:
            return []

        dtcs: list[J1939DTC] = []

        if len(data) <= 8:
            # Single-frame: first 2 bytes are lamp status, then 1 DTC
            if len(data) >= 6:
                dtcs.append(self._decode_dtc(data[2:6]))
        else:
            # Multi-frame: 4 bytes per DTC, no lamp header
            for i in range(0, len(data) - 3, self.DTC_BYTE_SIZE):
                dtcs.append(self._decode_dtc(data[i : i + self.DTC_BYTE_SIZE]))

        return dtcs

    @staticmethod
    def _decode_dtc(raw: bytes) -> J1939DTC:
        """Decode a 4-byte DTC.

        Byte layout (per J1939-73):
            Byte 0: SPN bits 18-16 (3 bits) + FMI (5 bits)
            Byte 1: SPN bits 15-8
            Byte 2: SPN bits 7-0
            Byte 3: Occurrence count (7 bits) + SPN conversion method (1 bit)

        Wait — the standard DTC format is actually:
            Byte 1 (low): SPN low 8 bits
            Byte 2: SPN mid 8 bits
            Byte 3: SPN high 3 bits + FMI (5 bits)
            Byte 4: Occurrence count (7 bits) + CM (1 bit)

        But the DM1 single-frame format is:
            Byte 0-1: Lamp status
            Byte 2: SPN low 8 bits
            Byte 3: SPN mid 8 bits
            Byte 4: SPN high 3 bits (bits 7-5) + FMI (bits 4-0)
            Byte 5: Occurrence count (bits 6-0) + CM (bit 7)
        """
        if len(raw) < 4:
            return J1939DTC(spn=0, fmi=0)

        spn = raw[0] | (raw[1] << 8) | ((raw[2] >> 5) << 16)
        fmi = raw[2] & 0x1F
        occurrence = raw[3] & 0x7F

        return J1939DTC(
            spn=spn,
            fmi=fmi,
            occurrence=occurrence,
            status="active",
        )

    @staticmethod
    def get_lamp_status(data: bytes) -> dict[str, str]:
        """Extract lamp status from single-frame DM1.

        Returns dict with lamp names and their states.
        """
        if len(data) < 2:
            return {}

        byte0 = data[0]
        byte1 = data[1]

        return {
            "malfunction_indicator": LAMP_NAMES.get((byte0 >> 6) & 0x03, "unknown"),
            "red_stop_lamp": LAMP_NAMES.get((byte0 >> 4) & 0x03, "unknown"),
            "amber_warning_lamp": LAMP_NAMES.get((byte0 >> 2) & 0x03, "unknown"),
            "protect_lamp": LAMP_NAMES.get(byte0 & 0x03, "unknown"),
            "flash_malfunction": LAMP_NAMES.get((byte1 >> 6) & 0x03, "unknown"),
            "flash_red_stop": LAMP_NAMES.get((byte1 >> 4) & 0x03, "unknown"),
            "flash_amber_warning": LAMP_NAMES.get((byte1 >> 2) & 0x03, "unknown"),
            "flash_protect": LAMP_NAMES.get(byte1 & 0x03, "unknown"),
        }
