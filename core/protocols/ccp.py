"""CCP (CAN Calibration Protocol) — simplified support.

CCP is the predecessor to XCP, operating exclusively over CAN.
Key differences from XCP:
- Simpler command set (no DAQ lists, no STIM)
- 2-byte command/response header (cmd code + return code)
- CRO (Command Receive Object) master→slave, DTO (Data Transmission Object) slave→master

Reference: ASAM MCD-1 CCP v2.1
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


# ── CCP Command Codes ──────────────────────────────────────────────────────


class CcpCmd:
    """CCP command codes."""
    CONNECT = 0x01
    DISCONNECT = 0x07
    SET_MTA = 0x02
    DNLOAD = 0x03
    UPLOAD = 0x04
    SHORT_UP = 0x23
    DNLOAD_6 = 0x23  # Same code as SHORT_UP but different direction
    GET_DAQ_SIZE = 0x14
    SET_DAQ_PTR = 0x15
    WRITE_DAQ = 0x16
    START_STOP = 0x06
    START_STOP_ALL = 0x08
    GET_CCP_VERSION = 0x1B
    EXCHANGE_ID = 0x17
    SET_S_STATUS = 0x0C
    GET_S_STATUS = 0x0D
    BUILD_CHKSUM = 0x0E
    CLEAR_MEMORY = 0x10
    PROGRAM = 0x18
    MOVE = 0x19
    DIAG_SERVICE = 0x20
    ACTION_SERVICE = 0x21
    TEST = 0x05


# ── CCP Error/Return Codes ─────────────────────────────────────────────────


class CcpError:
    """CCP return codes (byte 1 of positive/negative DTO)."""
    ACK = 0x00
    DAQ_OVERLOAD = 0x01
    CMD_UNKNOWN = 0x30
    CMD_SYNTAX = 0x31
    PARAM_OUT_OF_RANGE = 0x32
    ACCESS_DENIED = 0x33
    OVERFLOW = 0x34
    NOT_CONNECTED = 0x20
    RESOURCE_BUSY = 0x21

    _NAMES = {
        0x00: "ACK", 0x01: "DAQ_OVERLOAD",
        0x30: "CMD_UNKNOWN", 0x31: "CMD_SYNTAX",
        0x32: "PARAM_OUT_OF_RANGE", 0x33: "ACCESS_DENIED",
        0x34: "OVERFLOW", 0x20: "NOT_CONNECTED", 0x21: "RESOURCE_BUSY",
    }

    @classmethod
    def name(cls, code: int) -> str:
        return cls._NAMES.get(code, f"UNKNOWN(0x{code:02X})")


# ── CCP Response ───────────────────────────────────────────────────────────


@dataclass
class CcpResponse:
    """Decoded CCP DTO response."""
    return_code: int
    data: bytes
    counter: int = 0

    @property
    def is_ack(self) -> bool:
        return self.return_code == CcpError.ACK

    @property
    def is_error(self) -> bool:
        return self.return_code != CcpError.ACK


# ── CCP Codec ──────────────────────────────────────────────────────────────


class CcpCodec:
    """Encode/decode CCP CRO (Command Receive Object) and DTO frames.

    CCP CRO format (8 bytes CAN):
        Byte 0: Command code
        Byte 1: Command counter (CTR)
        Bytes 2-7: Command-specific data

    CCP DTO format (8 bytes CAN):
        Byte 0: Return code (PID)
        Byte 1: Command counter (CTR) echo
        Bytes 2-7: Response data
    """

    # ── CONNECT ────────────────────────────────────────────────────────────

    @staticmethod
    def encode_connect(station_address: int = 0x0000) -> bytes:
        """CONNECT CRO. station_address is the ECU address."""
        return bytes([
            CcpCmd.CONNECT,
            0x00,  # counter
            station_address & 0xFF,
            (station_address >> 8) & 0xFF,
        ])

    @staticmethod
    def encode_test(station_address: int = 0x0000) -> bytes:
        """TEST CRO — check if ECU at station_address is available."""
        return bytes([
            CcpCmd.TEST,
            0x00,
            station_address & 0xFF,
            (station_address >> 8) & 0xFF,
        ])

    # ── DISCONNECT ─────────────────────────────────────────────────────────

    @staticmethod
    def encode_disconnect() -> bytes:
        """DISCONNECT CRO."""
        return bytes([CcpCmd.DISCONNECT, 0x00, 0x00, 0x00])

    # ── GET_CCP_VERSION ────────────────────────────────────────────────────

    @staticmethod
    def encode_get_ccp_version() -> bytes:
        """GET_CCP_VERSION CRO."""
        return bytes([CcpCmd.GET_CCP_VERSION, 0x00])

    @staticmethod
    def decode_ccp_version(data: bytes) -> tuple[int, int]:
        """Decode GET_CCP_VERSION response. Returns (major, minor)."""
        if len(data) < 4:
            return 0, 0
        return data[2], data[3]

    # ── EXCHANGE_ID ────────────────────────────────────────────────────────

    @staticmethod
    def encode_exchange_id() -> bytes:
        """EXCHANGE_ID CRO — get ECU identification."""
        return bytes([CcpCmd.EXCHANGE_ID, 0x00])

    # ── SET_MTA ────────────────────────────────────────────────────────────

    @staticmethod
    def encode_set_mta(address: int, addr_ext: int = 0, mta_num: int = 0) -> bytes:
        """SET_MTA CRO. Sets Memory Transfer Address.

        Args:
            address: 32-bit ECU memory address.
            addr_ext: Address extension (memory segment).
            mta_num: MTA number (0 or 1).
        """
        return bytes([
            CcpCmd.SET_MTA,
            0x00,       # counter
            mta_num,
            addr_ext,
            address & 0xFF,
            (address >> 8) & 0xFF,
            (address >> 16) & 0xFF,
            (address >> 24) & 0xFF,
        ])

    # ── UPLOAD ─────────────────────────────────────────────────────────────

    @staticmethod
    def encode_upload(size: int) -> bytes:
        """UPLOAD CRO — read size bytes from current MTA."""
        return bytes([CcpCmd.UPLOAD, 0x00, size])

    # ── SHORT_UP ───────────────────────────────────────────────────────────

    @staticmethod
    def encode_short_upload(size: int, address: int, addr_ext: int = 0) -> bytes:
        """SHORT_UP CRO — read size bytes directly from address."""
        return bytes([
            CcpCmd.SHORT_UP,
            0x00,
            size,
            addr_ext,
            address & 0xFF,
            (address >> 8) & 0xFF,
            (address >> 16) & 0xFF,
            (address >> 24) & 0xFF,
        ])

    # ── DNLOAD ─────────────────────────────────────────────────────────────

    @staticmethod
    def encode_dnload(data: bytes) -> bytes:
        """DNLOAD CRO — write data bytes starting at current MTA.

        Max 5 bytes of payload (8 - 3 header bytes).
        """
        if len(data) > 5:
            raise ValueError(f"DNLOAD payload max 5 bytes, got {len(data)}")
        return bytes([CcpCmd.DNLOAD, 0x00, len(data)]) + data

    @staticmethod
    def encode_dnload_6(data: bytes) -> bytes:
        """DNLOAD_6 CRO — write exactly 6 bytes starting at current MTA."""
        if len(data) != 6:
            raise ValueError(f"DNLOAD_6 requires exactly 6 bytes, got {len(data)}")
        return bytes([CcpCmd.DNLOAD_6, 0x00]) + data

    # ── Response decoding ──────────────────────────────────────────────────

    @staticmethod
    def decode_response(data: bytes) -> CcpResponse:
        """Decode a CCP DTO response frame."""
        if len(data) < 2:
            return CcpResponse(return_code=0xFF, data=b"")
        return CcpResponse(
            return_code=data[0],
            counter=data[1],
            data=data[2:],
        )

    @staticmethod
    def decode_upload_response(data: bytes, expected_size: int) -> bytes:
        """Extract payload from UPLOAD/SHORT_UP positive response."""
        resp = CcpCodec.decode_response(data)
        if not resp.is_ack:
            return b""
        return resp.data[:expected_size]

    # ── DAQ commands ───────────────────────────────────────────────────────

    @staticmethod
    def encode_get_daq_size(daq_list: int = 0) -> bytes:
        """GET_DAQ_SIZE CRO — query DAQ list size."""
        return bytes([CcpCmd.GET_DAQ_SIZE, 0x00, daq_list, 0x00])

    @staticmethod
    def encode_set_daq_ptr(daq_list: int, odt: int, element: int) -> bytes:
        """SET_DAQ_PTR CRO — set pointer for DAQ configuration."""
        return bytes([
            CcpCmd.SET_DAQ_PTR,
            0x00,
            daq_list,
            0x00,
            odt,
            element,
        ])

    @staticmethod
    def encode_write_daq(size: int, addr_ext: int, address: int) -> bytes:
        """WRITE_DAQ CRO — define one DAQ entry."""
        return bytes([
            CcpCmd.WRITE_DAQ,
            0x00,
            size,
            addr_ext,
            address & 0xFF,
            (address >> 8) & 0xFF,
            (address >> 16) & 0xFF,
            (address >> 24) & 0xFF,
        ])

    @staticmethod
    def encode_start_stop(
        daq_list: int, last_odt: int, event_channel: int, rate_prescaler: int = 0,
    ) -> bytes:
        """START_STOP CRO — start/stop a DAQ list."""
        return bytes([
            CcpCmd.START_STOP,
            0x00,
            0x01,  # start
            daq_list,
            last_odt,
            event_channel & 0xFF,
            (event_channel >> 8) & 0xFF,
            rate_prescaler,
        ])

    # ── Utility ────────────────────────────────────────────────────────────

    @staticmethod
    def data_type_size(data_type: str) -> int:
        """Return byte size for a CCP data type."""
        sizes = {
            "UBYTE": 1, "SBYTE": 1,
            "UWORD": 2, "SWORD": 2,
            "ULONG": 4, "SLONG": 4,
            "FLOAT32_IEEE": 4, "FLOAT64_IEEE": 8,
        }
        return sizes.get(data_type, 0)

    @staticmethod
    def unpack_value(raw: bytes, data_type: str) -> float:
        """Unpack raw bytes to numeric value."""
        type_map = {
            "UBYTE": ("B", 1), "SBYTE": ("b", 1),
            "UWORD": ("<H", 2), "SWORD": ("<h", 2),
            "ULONG": ("<I", 4), "SLONG": ("<i", 4),
            "FLOAT32_IEEE": ("<f", 4), "FLOAT64_IEEE": ("<d", 8),
        }
        fmt_info = type_map.get(data_type)
        if fmt_info is None:
            return 0.0
        fmt, size = fmt_info
        if len(raw) < size:
            return 0.0
        return float(struct.unpack(fmt, raw[:size])[0])

    @staticmethod
    def pack_value(value: float, data_type: str) -> bytes:
        """Pack numeric value to bytes."""
        type_map = {
            "UBYTE": ("B", 1), "SBYTE": ("b", 1),
            "UWORD": ("<H", 2), "SWORD": ("<h", 2),
            "ULONG": ("<I", 4), "SLONG": ("<i", 4),
            "FLOAT32_IEEE": ("<f", 4), "FLOAT64_IEEE": ("<d", 8),
        }
        fmt_info = type_map.get(data_type)
        if fmt_info is None:
            return b""
        fmt, size = fmt_info
        return struct.pack(fmt, int(value) if "f" not in fmt else value)[:size]
