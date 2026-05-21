"""XCP session — high-level calibration read/write framework.

Provides an abstract transport interface and a concrete loopback transport
for testing. The session layer handles CONNECT/DISCONNECT, MTA management,
and parameter read/write by name via A2L address mapping.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.protocols.xcp import XcpAddressMapping, XcpConnection
from core.protocols.xcp_codec import XcpCodec
from core.protocols.xcp_mapping import XcpAddressMapper

logger = logging.getLogger(__name__)


# ── Abstract Transport ─────────────────────────────────────────────────────


class XcpTransport(ABC):
    """Abstract XCP transport layer.

    Concrete implementations connect to real hardware (CAN adapter,
    Ethernet socket, etc.). The session layer calls send_receive()
    for each XCP command/response exchange.
    """

    @abstractmethod
    def send_receive(self, cmd: bytes) -> bytes:
        """Send an XCP command frame and receive the response.

        Args:
            cmd: Encoded XCP command (CTO).

        Returns:
            Encoded XCP response (CTO).
        """
        ...


# ── Loopback Transport (for testing) ───────────────────────────────────────


class LoopbackTransport(XcpTransport):
    """In-memory loopback transport that simulates an ECU.

    Maintains a simulated memory space. Commands are processed locally:
    - CONNECT: returns success with default CTO/DTO sizes
    - SHORT_UPLOAD: reads from simulated memory
    - DOWNLOAD/SHORT_DOWNLOAD: writes to simulated memory
    - GET_STATUS: returns current state

    Useful for testing the session layer without real hardware.
    """

    def __init__(self, memory_size: int = 65536) -> None:
        self._memory = bytearray(memory_size)
        self._connected = False
        self._mta = 0  # Memory Transfer Address
        self._max_cto = 8
        self._max_dto = 8
        self._daq_active = False
        self._daq_lists: dict[int, list[tuple[int, int, int]]] = {}

    @property
    def memory(self) -> bytearray:
        return self._memory

    def send_receive(self, cmd: bytes) -> bytes:
        if len(cmd) < 1:
            return self._negative_response(0x20)  # CMD_UNKNOWN

        command = cmd[0]

        handlers = {
            0xFF: self._handle_connect,
            0xFE: self._handle_disconnect,
            0xFD: self._handle_get_status,
            0xF6: self._handle_set_mta,
            0xF5: self._handle_upload,
            0xF4: self._handle_short_upload,
            0xF0: self._handle_download,
            0xEF: self._handle_download_next,
            0xED: self._handle_short_download,
            0xE2: self._handle_set_daq_ptr,
            0xE1: self._handle_write_daq,
            0xDE: self._handle_start_stop_daq,
            0xDD: self._handle_start_stop_synch,
        }

        handler = handlers.get(command)
        if handler is None:
            return self._negative_response(0x20)
        return handler(cmd)

    def _positive_response(self, data: bytes = b"") -> bytes:
        return bytes([0xFF]) + data

    def _negative_response(self, error_code: int) -> bytes:
        return bytes([0xFE, error_code])

    def _handle_connect(self, cmd: bytes) -> bytes:
        self._connected = True
        # resource, comm_mode_basic, reserved, max_cto, max_dto(LE)
        return self._positive_response(
            bytes(
                [
                    0x05,  # resource: CAL_PAG | DAQ
                    0x00,  # comm_mode_basic
                    0x00,  # reserved
                    self._max_cto,
                    self._max_dto & 0xFF,
                    (self._max_dto >> 8) & 0xFF,
                    0x00,  # reserved
                ]
            )
        )

    def _handle_disconnect(self, cmd: bytes) -> bytes:
        self._connected = False
        return self._positive_response()

    def _handle_get_status(self, cmd: bytes) -> bytes:
        return self._positive_response(
            bytes(
                [
                    0x00,  # status
                    0x05,  # resource_protection
                    0x00,
                    0x00,  # session_config
                    0x00,  # reserved
                    0x00,
                    0x00,  # reserved
                ]
            )
        )

    def _handle_set_mta(self, cmd: bytes) -> bytes:
        if len(cmd) < 8:
            return self._negative_response(0x21)  # CMD_SYNTAX
        self._mta = cmd[4] | (cmd[5] << 8) | (cmd[6] << 16) | (cmd[7] << 24)
        return self._positive_response()

    def _handle_short_upload(self, cmd: bytes) -> bytes:
        if len(cmd) < 8:
            return self._negative_response(0x21)
        size = cmd[1]
        addr = cmd[4] | (cmd[5] << 8) | (cmd[6] << 16) | (cmd[7] << 24)
        if addr + size > len(self._memory):
            return self._negative_response(0x22)  # OUT_OF_RANGE
        return self._positive_response(bytes(self._memory[addr : addr + size]))

    def _handle_upload(self, cmd: bytes) -> bytes:
        if len(cmd) < 2:
            return self._negative_response(0x21)
        size = cmd[1]
        if self._mta + size > len(self._memory):
            return self._negative_response(0x22)
        data = bytes(self._memory[self._mta : self._mta + size])
        self._mta += size
        return self._positive_response(data)

    def _handle_download(self, cmd: bytes) -> bytes:
        if len(cmd) < 2:
            return self._negative_response(0x21)
        size = cmd[1]
        if len(cmd) < 2 + size:
            return self._negative_response(0x21)
        data = cmd[2 : 2 + size]
        if self._mta + size > len(self._memory):
            return self._negative_response(0x22)
        self._memory[self._mta : self._mta + size] = data
        self._mta += size
        return self._positive_response()

    def _handle_download_next(self, cmd: bytes) -> bytes:
        return self._handle_download(cmd)

    def _handle_short_download(self, cmd: bytes) -> bytes:
        if len(cmd) < 8:
            return self._negative_response(0x21)
        size = cmd[1]
        addr = cmd[4] | (cmd[5] << 8) | (cmd[6] << 16) | (cmd[7] << 24)
        data = cmd[8 : 8 + size]
        if addr + size > len(self._memory):
            return self._negative_response(0x22)
        self._memory[addr : addr + size] = data
        return self._positive_response()

    def _handle_set_daq_ptr(self, cmd: bytes) -> bytes:
        if len(cmd) < 6:
            return self._negative_response(0x21)
        daq_list = cmd[2] | (cmd[3] << 8)
        self._current_daq = daq_list
        self._current_odt = cmd[4]
        self._current_entry = cmd[5]
        return self._positive_response()

    def _handle_write_daq(self, cmd: bytes) -> bytes:
        if len(cmd) < 8:
            return self._negative_response(0x21)
        daq = getattr(self, "_current_daq", 0)
        entry = (
            cmd[2],  # size
            cmd[3],  # ext
            cmd[4] | (cmd[5] << 8) | (cmd[6] << 16) | (cmd[7] << 24),  # address
        )
        self._daq_lists.setdefault(daq, []).append(entry)
        return self._positive_response()

    def _handle_start_stop_daq(self, cmd: bytes) -> bytes:
        if len(cmd) < 4:
            return self._negative_response(0x21)
        mode = cmd[1]
        if mode == 1:
            self._daq_active = True
        elif mode == 0:
            self._daq_active = False
        return self._positive_response(bytes([0x00, 0x00, 0x00]))  # first PID

    def _handle_start_stop_synch(self, cmd: bytes) -> bytes:
        if len(cmd) < 2:
            return self._negative_response(0x21)
        mode = cmd[1]
        if mode == 0:
            self._daq_active = False
        elif mode == 1:
            self._daq_active = True
        return self._positive_response()


# ── XCP Session ────────────────────────────────────────────────────────────


@dataclass
class ReadResult:
    """Result of a parameter read operation."""

    success: bool
    raw_value: float = 0.0
    raw_bytes: bytes = b""
    error: str = ""


@dataclass
class WriteResult:
    """Result of a parameter write operation."""

    success: bool
    error: str = ""


class XcpSession:
    """High-level XCP session for calibration parameter read/write.

    Manages connection lifecycle, MTA pointer, and provides named
    parameter access via A2L address mapping.
    """

    def __init__(self, transport: XcpTransport) -> None:
        self._transport = transport
        self._codec = XcpCodec()
        self._connection: XcpConnection = XcpConnection()
        self._mappings: list[XcpAddressMapping] = []

    @property
    def is_connected(self) -> bool:
        return self._connection.is_connected

    @property
    def connection(self) -> XcpConnection:
        return self._connection

    def set_mappings(self, mappings: list[XcpAddressMapping]) -> None:
        """Set A2L address mappings for named parameter access."""
        self._mappings = mappings

    # ── Connection ─────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Send CONNECT command and parse response."""
        cmd = self._codec.encode_connect()
        resp_data = self._transport.send_receive(cmd)
        resp = self._codec.decode_response(resp_data)
        if resp.is_positive:
            self._connection = self._codec.build_connection(resp.data)
            return True
        logger.warning("XCP CONNECT failed: error=0x%02X", resp.error_code)
        return False

    def disconnect(self) -> None:
        """Send DISCONNECT command."""
        cmd = self._codec.encode_disconnect()
        self._transport.send_receive(cmd)
        self._connection = XcpConnection()

    def get_status(self) -> dict:
        """Send GET_STATUS and return parsed status dict."""
        cmd = self._codec.encode_get_status()
        resp_data = self._transport.send_receive(cmd)
        return self._codec.decode_get_status_response(resp_data)

    # ── Raw read/write ─────────────────────────────────────────────────────

    def read_raw(self, address: int, size: int) -> bytes:
        """Read raw bytes from ECU memory.

        Uses SHORT_UPLOAD for small reads (size <= max_cto - 4),
        otherwise uses SET_MTA + UPLOAD.
        """
        if not self._connection.is_connected:
            return b""

        if size <= self._connection.max_cto - 4:
            cmd = self._codec.encode_short_upload(address, size)
            resp_data = self._transport.send_receive(cmd)
            return self._codec.decode_short_upload_response(resp_data, size)
        else:
            # SET_MTA first
            mta_cmd = self._codec.encode_set_mta(address)
            self._transport.send_receive(mta_cmd)
            # UPLOAD
            upload_cmd = self._codec.encode_upload(size)
            resp_data = self._transport.send_receive(upload_cmd)
            return self._codec.decode_upload_response(resp_data, size)

    def write_raw(self, address: int, data: bytes) -> bool:
        """Write raw bytes to ECU memory.

        Uses SHORT_DOWNLOAD for small writes, otherwise SET_MTA + DOWNLOAD.
        """
        if not self._connection.is_connected:
            return False

        if len(data) <= self._connection.max_cto - 8:
            cmd = self._codec.encode_short_download(data, address)
            resp = self._codec.decode_response(self._transport.send_receive(cmd))
            return resp.is_positive
        else:
            # SET_MTA
            mta_cmd = self._codec.encode_set_mta(address)
            resp = self._codec.decode_response(self._transport.send_receive(mta_cmd))
            if not resp.is_positive:
                return False
            # DOWNLOAD (may need multiple frames)
            max_payload = self._connection.max_cto - 2
            offset = 0
            while offset < len(data):
                chunk = data[offset : offset + max_payload]
                if offset == 0:
                    cmd = self._codec.encode_download(chunk)
                else:
                    cmd = self._codec.encode_download_next(chunk)
                resp = self._codec.decode_response(self._transport.send_receive(cmd))
                if not resp.is_positive:
                    return False
                offset += len(chunk)
            return True

    # ── Named parameter access ─────────────────────────────────────────────

    def read_parameter(self, name: str) -> ReadResult:
        """Read a named parameter using A2L address mapping."""
        mapping = self._codec_find_mapping(name)
        if mapping is None:
            return ReadResult(success=False, error=f"Parameter '{name}' not found in mappings")

        raw_bytes = self.read_raw(mapping.address, mapping.size)
        if not raw_bytes:
            return ReadResult(success=False, error="Read failed — no data returned")

        raw_value = self._codec.unpack_value(raw_bytes, mapping.data_type)
        return ReadResult(success=True, raw_value=raw_value, raw_bytes=raw_bytes)

    def write_parameter(self, name: str, value: float) -> WriteResult:
        """Write a named parameter using A2L address mapping."""
        mapping = self._codec_find_mapping(name)
        if mapping is None:
            return WriteResult(success=False, error=f"Parameter '{name}' not found in mappings")

        if mapping.direction != "calibration":
            return WriteResult(success=False, error=f"Parameter '{name}' is read-only (measurement)")

        raw_bytes = self._codec.pack_value(value, mapping.data_type)
        if not raw_bytes:
            return WriteResult(success=False, error=f"Cannot pack value for type '{mapping.data_type}'")

        success = self.write_raw(mapping.address, raw_bytes)
        if not success:
            return WriteResult(success=False, error="Write failed — ECU rejected")
        return WriteResult(success=True)

    def _codec_find_mapping(self, name: str) -> XcpAddressMapping | None:
        """Find mapping by name."""
        return XcpAddressMapper().find_mapping(self._mappings, name)
