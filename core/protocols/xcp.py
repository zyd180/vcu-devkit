"""XCP (Universal Measurement and Calibration Protocol) data models.

XCP is the ASAM MCD-1 standard for ECU calibration and measurement.
This module defines the protocol constants, message structures, and
data models used across the XCP codec, mapping, and session layers.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── XCP Command Codes (CAN transport) ──────────────────────────────────────


class XcpCmd:
    """XCP command codes (byte 0 of CTO packet)."""

    CONNECT = 0xFF
    DISCONNECT = 0xFE
    GET_STATUS = 0xFD
    SYNCH = 0xFC
    GET_COMM_MODE_INFO = 0xFB
    GET_ID = 0xFA
    SET_REQUEST = 0xF9
    GET_SEED = 0xF8
    UNLOCK = 0xF7
    SET_MTA = 0xF6
    UPLOAD = 0xF5
    SHORT_UPLOAD = 0xF4
    BUILD_CHECKSUM = 0xF3
    TRANSPORT_LAYER_CMD = 0xF2
    USER_CMD = 0xF1
    DOWNLOAD = 0xF0
    DOWNLOAD_NEXT = 0xEF
    DOWNLOAD_MAX = 0xEE
    SHORT_DOWNLOAD = 0xED
    MODIFY_BITS = 0xEC
    SET_CAL_PAGE = 0xEB
    GET_CAL_PAGE = 0xEA
    GET_PAG_PROCESSOR_INFO = 0xE9
    GET_SEGMENT_INFO = 0xE8
    GET_PAGE_INFO = 0xE7
    SET_SEGMENT_MODE = 0xE6
    GET_SEGMENT_MODE = 0xE5
    COPY_CAL_PAGE = 0xE4
    CLEAR_DAQ_LIST = 0xE3
    SET_DAQ_PTR = 0xE2
    WRITE_DAQ = 0xE1
    SET_DAQ_LIST_MODE = 0xE0
    GET_DAQ_LIST_MODE = 0xDF
    START_STOP_DAQ_LIST = 0xDE
    START_STOP_SYNCH = 0xDD
    GET_DAQ_CLOCK = 0xDC
    READ_DAQ = 0xDB
    GET_DAQ_RESOLUTION_INFO = 0xD9
    GET_DAQ_LIST_INFO = 0xD8
    GET_DAQ_EVENT_INFO = 0xD7
    FREE_DAQ = 0xD6
    ALLOC_DAQ = 0xD5
    ALLOC_ODT = 0xD4
    ALLOC_ODT_ENTRY = 0xD3
    PROGRAM_START = 0xD2
    PROGRAM_CLEAR = 0xD1
    PROGRAM = 0xD0
    PROGRAM_RESET = 0xCF
    GET_PGM_PROCESSOR_INFO = 0xCE
    GET_SECTOR_INFO = 0xCD
    PROGRAM_PREPARE = 0xCC
    PROGRAM_FORMAT = 0xCB
    PROGRAM_NEXT = 0xCA


# ── XCP Error Codes ────────────────────────────────────────────────────────


class XcpError:
    """XCP negative response error codes."""

    ERR_CMD_SYNCH = 0x00
    ERR_CMD_BUSY = 0x10
    ERR_DAQ_ACTIVE = 0x11
    ERR_PGM_ACTIVE = 0x12
    ERR_CMD_UNKNOWN = 0x20
    ERR_CMD_SYNTAX = 0x21
    ERR_OUT_OF_RANGE = 0x22
    ERR_WRITE_PROTECTED = 0x23
    ERR_ACCESS_DENIED = 0x24
    ERR_ACCESS_LOCKED = 0x25
    ERR_PAGE_NOT_VALID = 0x26
    ERR_MODE_NOT_VALID = 0x27
    ERR_SEGMENT_NOT_VALID = 0x28
    ERR_SEQUENCE = 0x29
    ERR_DAQ_CONFIG = 0x2A
    ERR_MEMORY_OVERFLOW = 0x30
    ERR_GENERIC = 0x31
    ERR_VERIFY = 0x32

    _NAMES = {
        0x00: "CMD_SYNCH",
        0x10: "CMD_BUSY",
        0x11: "DAQ_ACTIVE",
        0x12: "PGM_ACTIVE",
        0x20: "CMD_UNKNOWN",
        0x21: "CMD_SYNTAX",
        0x22: "OUT_OF_RANGE",
        0x23: "WRITE_PROTECTED",
        0x24: "ACCESS_DENIED",
        0x25: "ACCESS_LOCKED",
        0x26: "PAGE_NOT_VALID",
        0x27: "MODE_NOT_VALID",
        0x28: "SEGMENT_NOT_VALID",
        0x29: "SEQUENCE",
        0x2A: "DAQ_CONFIG",
        0x30: "MEMORY_OVERFLOW",
        0x31: "GENERIC",
        0x32: "VERIFY",
    }

    @classmethod
    def name(cls, code: int) -> str:
        return cls._NAMES.get(code, f"UNKNOWN(0x{code:02X})")


# ── XCP Response PIDs ──────────────────────────────────────────────────────


class XcpPid:
    """XCP response packet IDs."""

    RES_POSITIVE = 0xFF
    RES_NEGATIVE = 0xFE
    RES_ERROR = 0xFE  # Alias
    RES_SERV = 0xFD  # Service request (e.g., EV_DAQ, EV_CAL)
    EV_CMD = 0xFC


# ── XCP Data Structures ────────────────────────────────────────────────────


@dataclass
class XcpResponse:
    """Decoded XCP response."""

    pid: int
    data: bytes
    error_code: int = 0

    @property
    def is_positive(self) -> bool:
        return self.pid == XcpPid.RES_POSITIVE

    @property
    def is_negative(self) -> bool:
        return self.pid == XcpPid.RES_NEGATIVE


@dataclass
class XcpMessage:
    """XCP CAN frame."""

    can_id: int
    data: bytes
    direction: str = "cmd"  # "cmd" (master→slave) or "res" (slave→master)


@dataclass
class XcpConnection:
    """XCP connection state after CONNECT."""

    resource: int = 0
    comm_mode: int = 0
    max_cto: int = 8
    max_dto: int = 8
    is_connected: bool = False


@dataclass
class XcpDaqEntry:
    """Single DAQ list entry — maps an ECU address to a measurement."""

    address: int
    size: int
    byte_order: str = "little_endian"
    bit_offset: int = 0
    ext: int = 0


@dataclass
class XcpAddressMapping:
    """A2L → XCP address mapping for a single parameter."""

    name: str
    address: int
    size: int
    data_type: str
    direction: str = "calibration"  # "calibration" (R/W) or "measurement" (R/O)
    conversion: str = ""
