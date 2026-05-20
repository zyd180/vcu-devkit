"""XCP command/response codec — encode and decode XCP CTO/DTO packets."""

from __future__ import annotations

import struct

from core.protocols.xcp import (
    XcpCmd, XcpConnection, XcpError, XcpPid, XcpResponse,
)


class XcpCodec:
    """Encode XCP commands and decode responses for CAN transport.

    All multi-byte values are little-endian (XCP default for CAN).
    """

    # ── CONNECT ────────────────────────────────────────────────────────────

    @staticmethod
    def encode_connect(mode: int = 0) -> bytes:
        """CONNECT command. mode=0 for normal, 1 for user-defined."""
        return bytes([XcpCmd.CONNECT, mode])

    @staticmethod
    def decode_connect_response(data: bytes) -> XcpResponse:
        """Decode CONNECT positive response.

        Layout (8 bytes CTO):
            Byte 0: 0xFF (positive response)
            Byte 1: resource (bitmask: CAL_PAG=0x01, DAQ=0x04, STIM=0x08, PGM=0x10)
            Byte 2: comm_mode_basic
            Byte 3: reserved
            Byte 4: max_cto
            Byte 5-6: max_dto (uint16 LE)
            Byte 7: reserved
        """
        if len(data) < 7:
            return XcpResponse(pid=XcpPid.RES_NEGATIVE, data=data)
        return XcpResponse(
            pid=data[0],
            data=data[1:],
        )

    @staticmethod
    def build_connection(data: bytes) -> XcpConnection:
        """Build XcpConnection from CONNECT positive response payload (byte 1+)."""
        if len(data) < 6:
            return XcpConnection()
        max_dto = data[4] | (data[5] << 8) if len(data) > 5 else 8
        return XcpConnection(
            resource=data[0],
            comm_mode=data[1],
            max_cto=data[3] if data[3] > 0 else 8,
            max_dto=max_dto if max_dto > 0 else 8,
            is_connected=True,
        )

    # ── DISCONNECT ─────────────────────────────────────────────────────────

    @staticmethod
    def encode_disconnect() -> bytes:
        return bytes([XcpCmd.DISCONNECT])

    # ── GET_STATUS ─────────────────────────────────────────────────────────

    @staticmethod
    def encode_get_status() -> bytes:
        return bytes([XcpCmd.GET_STATUS])

    @staticmethod
    def decode_get_status_response(data: bytes) -> dict:
        """Decode GET_STATUS response.

        Returns dict with: status, resource_protection, session_config,
        session_status.
        """
        if len(data) < 6 or data[0] != XcpPid.RES_POSITIVE:
            return {}
        return {
            "status": data[1],
            "resource_protection": data[2],
            "session_config": data[3] | (data[4] << 8) if len(data) > 4 else 0,
            "session_status": data[5] if len(data) > 5 else 0,
        }

    # ── SET_MTA ────────────────────────────────────────────────────────────

    @staticmethod
    def encode_set_mta(address: int, ext: int = 0) -> bytes:
        """SET_MTA: set Memory Transfer Address for subsequent UPLOAD/DOWNLOAD.

        Args:
            address: 32-bit ECU memory address.
            ext: Address extension (usually 0).
        """
        return bytes([
            XcpCmd.SET_MTA,
            0x00, 0x00,  # reserved
            ext,
            address & 0xFF,
            (address >> 8) & 0xFF,
            (address >> 16) & 0xFF,
            (address >> 24) & 0xFF,
        ])

    # ── SHORT_UPLOAD ───────────────────────────────────────────────────────

    @staticmethod
    def encode_short_upload(address: int, size: int, ext: int = 0) -> bytes:
        """SHORT_UPLOAD: read up to max_cto-4 bytes directly.

        Args:
            address: 32-bit ECU memory address.
            size: Number of bytes to upload (max = max_cto - 4).
            ext: Address extension.
        """
        return bytes([
            XcpCmd.SHORT_UPLOAD,
            size,
            0x00,  # reserved
            ext,
            address & 0xFF,
            (address >> 8) & 0xFF,
            (address >> 16) & 0xFF,
            (address >> 24) & 0xFF,
        ])

    # ── UPLOAD ─────────────────────────────────────────────────────────────

    @staticmethod
    def encode_upload(size: int) -> bytes:
        """UPLOAD: read size bytes starting at current MTA.

        For size > max_cto, multiple response frames are expected.
        """
        return bytes([XcpCmd.UPLOAD, size])

    # ── DOWNLOAD ───────────────────────────────────────────────────────────

    @staticmethod
    def encode_download(data: bytes) -> bytes:
        """DOWNLOAD: write data bytes starting at current MTA.

        Args:
            data: Payload to write (max = max_cto - 2 bytes).
        """
        return bytes([XcpCmd.DOWNLOAD, len(data)]) + data

    @staticmethod
    def encode_download_next(data: bytes) -> bytes:
        """DOWNLOAD_NEXT: continue writing data for multi-frame downloads."""
        return bytes([XcpCmd.DOWNLOAD_NEXT, len(data)]) + data

    # ── SHORT_DOWNLOAD ─────────────────────────────────────────────────────

    @staticmethod
    def encode_short_download(data: bytes, address: int, ext: int = 0) -> bytes:
        """SHORT_DOWNLOAD: write data directly to address (no SET_MTA needed)."""
        return bytes([
            XcpCmd.SHORT_DOWNLOAD,
            len(data),
            0x00,  # reserved
            ext,
            address & 0xFF,
            (address >> 8) & 0xFF,
            (address >> 16) & 0xFF,
            (address >> 24) & 0xFF,
        ]) + data

    # ── DAQ commands ───────────────────────────────────────────────────────

    @staticmethod
    def encode_set_daq_ptr(daq_list: int, odt: int, entry: int) -> bytes:
        """SET_DAQ_PTR: set pointer for DAQ list configuration."""
        return bytes([
            XcpCmd.SET_DAQ_PTR,
            0x00,  # reserved
            daq_list & 0xFF,
            (daq_list >> 8) & 0xFF,
            odt,
            entry,
        ])

    @staticmethod
    def encode_write_daq(size: int, ext: int, address: int) -> bytes:
        """WRITE_DAQ: define a single DAQ entry."""
        return bytes([
            XcpCmd.WRITE_DAQ,
            0xFF,  # bit_offset (0xFF = byte aligned)
            size,
            ext,
            address & 0xFF,
            (address >> 8) & 0xFF,
            (address >> 16) & 0xFF,
            (address >> 24) & 0xFF,
        ])

    @staticmethod
    def encode_start_stop_daq_list(mode: int, daq_list: int) -> bytes:
        """START_STOP_DAQ_LIST. mode: 0=stop, 1=start, 2=start_select."""
        return bytes([
            XcpCmd.START_STOP_DAQ_LIST,
            mode,
            daq_list & 0xFF,
            (daq_list >> 8) & 0xFF,
        ])

    @staticmethod
    def encode_start_stop_synch(mode: int) -> bytes:
        """START_STOP_SYNCH. mode: 0=stop_all, 1=start_all, 2=stop_sel, 3=start_sel."""
        return bytes([XcpCmd.START_STOP_SYNCH, mode])

    # ── Response decoding ──────────────────────────────────────────────────

    @staticmethod
    def decode_response(data: bytes) -> XcpResponse:
        """Decode a generic XCP response frame."""
        if len(data) < 1:
            return XcpResponse(pid=0, data=b"")
        pid = data[0]
        payload = data[1:]
        error_code = 0
        if pid == XcpPid.RES_NEGATIVE and len(payload) >= 1:
            error_code = payload[0]
        return XcpResponse(pid=pid, data=payload, error_code=error_code)

    @staticmethod
    def decode_short_upload_response(data: bytes, expected_size: int) -> bytes:
        """Extract payload from SHORT_UPLOAD positive response.

        Returns raw bytes of the uploaded data.
        """
        if len(data) < 1 or data[0] != XcpPid.RES_POSITIVE:
            return b""
        return data[1:1 + expected_size]

    @staticmethod
    def decode_upload_response(data: bytes, expected_size: int) -> bytes:
        """Extract payload from UPLOAD positive response."""
        if len(data) < 1 or data[0] != XcpPid.RES_POSITIVE:
            return b""
        return data[1:1 + expected_size]

    # ── Utility ────────────────────────────────────────────────────────────

    @staticmethod
    def unpack_value(raw: bytes, data_type: str) -> float:
        """Unpack raw bytes to a numeric value based on A2L data type."""
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
        """Pack a numeric value to bytes based on A2L data type."""
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

    @staticmethod
    def data_type_size(data_type: str) -> int:
        """Return byte size for an A2L data type."""
        sizes = {
            "UBYTE": 1, "SBYTE": 1,
            "UWORD": 2, "SWORD": 2,
            "ULONG": 4, "SLONG": 4,
            "FLOAT32_IEEE": 4, "FLOAT64_IEEE": 8,
        }
        return sizes.get(data_type, 0)
