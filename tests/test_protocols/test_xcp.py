"""Tests for XCP/CCP protocol support — codec, mapping, session, CCP."""

from __future__ import annotations

import struct

import pytest

from core.protocols.xcp import (
    XcpAddressMapping, XcpCmd, XcpConnection, XcpError, XcpPid, XcpResponse,
)
from core.protocols.xcp_codec import XcpCodec
from core.protocols.xcp_mapping import XcpAddressMapper
from core.protocols.xcp_session import LoopbackTransport, ReadResult, WriteResult, XcpSession
from core.protocols.ccp import CcpCmd, CcpCodec, CcpError, CcpResponse
from core.parsers.a2l_parser import A2LCharacteristic, A2LCompuMethod, A2LData, A2LMeasurement


# ── XCP Codec tests ────────────────────────────────────────────────────────


class TestXcpCodec:

    def test_encode_connect(self):
        cmd = XcpCodec.encode_connect(0)
        assert cmd[0] == XcpCmd.CONNECT
        assert cmd[1] == 0
        assert len(cmd) == 2

    def test_encode_connect_mode(self):
        cmd = XcpCodec.encode_connect(1)
        assert cmd[1] == 1

    def test_encode_disconnect(self):
        cmd = XcpCodec.encode_disconnect()
        assert cmd[0] == XcpCmd.DISCONNECT

    def test_encode_get_status(self):
        cmd = XcpCodec.encode_get_status()
        assert cmd[0] == XcpCmd.GET_STATUS
        assert len(cmd) == 1

    def test_encode_short_upload(self):
        cmd = XcpCodec.encode_short_upload(address=0x12345678, size=4, ext=0)
        assert cmd[0] == XcpCmd.SHORT_UPLOAD
        assert cmd[1] == 4  # size
        assert cmd[3] == 0  # ext
        # Address is LE
        assert cmd[4] == 0x78
        assert cmd[5] == 0x56
        assert cmd[6] == 0x34
        assert cmd[7] == 0x12

    def test_encode_upload(self):
        cmd = XcpCodec.encode_upload(8)
        assert cmd[0] == XcpCmd.UPLOAD
        assert cmd[1] == 8

    def test_encode_set_mta(self):
        cmd = XcpCodec.encode_set_mta(address=0x0000FF00, ext=1)
        assert cmd[0] == XcpCmd.SET_MTA
        assert cmd[3] == 1  # ext
        assert cmd[4] == 0x00
        assert cmd[5] == 0xFF
        assert cmd[6] == 0x00
        assert cmd[7] == 0x00

    def test_encode_download(self):
        data = bytes([0xAA, 0xBB, 0xCC])
        cmd = XcpCodec.encode_download(data)
        assert cmd[0] == XcpCmd.DOWNLOAD
        assert cmd[1] == 3  # length
        assert cmd[2:] == data

    def test_encode_download_next(self):
        data = bytes([0x11, 0x22])
        cmd = XcpCodec.encode_download_next(data)
        assert cmd[0] == XcpCmd.DOWNLOAD_NEXT
        assert cmd[1] == 2

    def test_encode_short_download(self):
        data = bytes([0xDE, 0xAD])
        cmd = XcpCodec.encode_short_download(data, address=0x1000, ext=0)
        assert cmd[0] == XcpCmd.SHORT_DOWNLOAD
        assert cmd[1] == 2  # size
        assert cmd[4] == 0x00  # address low byte
        assert cmd[5] == 0x10
        assert cmd[8:] == data

    def test_decode_positive_response(self):
        data = bytes([0xFF, 0x01, 0x02, 0x03])
        resp = XcpCodec.decode_response(data)
        assert resp.is_positive
        assert resp.data == bytes([0x01, 0x02, 0x03])
        assert resp.error_code == 0

    def test_decode_negative_response(self):
        data = bytes([0xFE, 0x22])  # OUT_OF_RANGE
        resp = XcpCodec.decode_response(data)
        assert resp.is_negative
        assert resp.error_code == 0x22

    def test_decode_connect_response(self):
        # Positive response: resource=0x05, comm_mode=0, reserved, max_cto=8, max_dto=8
        data = bytes([0xFF, 0x05, 0x00, 0x00, 0x08, 0x08, 0x00, 0x00])
        resp = XcpCodec.decode_connect_response(data)
        assert resp.is_positive
        conn = XcpCodec.build_connection(resp.data)
        assert conn.is_connected
        assert conn.resource == 0x05
        assert conn.max_cto == 8
        assert conn.max_dto == 8

    def test_decode_short_upload_response(self):
        # Positive response with 4 bytes of data
        data = bytes([0xFF, 0x78, 0x56, 0x34, 0x12])
        result = XcpCodec.decode_short_upload_response(data, 4)
        assert result == bytes([0x78, 0x56, 0x34, 0x12])

    def test_unpack_value_ubyte(self):
        assert XcpCodec.unpack_value(bytes([255]), "UBYTE") == 255.0

    def test_unpack_value_uint16(self):
        raw = struct.pack("<H", 1234)
        assert XcpCodec.unpack_value(raw, "UWORD") == 1234.0

    def test_unpack_value_float32(self):
        raw = struct.pack("<f", 3.14)
        result = XcpCodec.unpack_value(raw, "FLOAT32_IEEE")
        assert abs(result - 3.14) < 0.001

    def test_pack_value_ubyte(self):
        result = XcpCodec.pack_value(42, "UBYTE")
        assert result == bytes([42])

    def test_pack_value_int16(self):
        result = XcpCodec.pack_value(1000, "SWORD")
        assert struct.unpack("<h", result)[0] == 1000

    def test_data_type_sizes(self):
        assert XcpCodec.data_type_size("UBYTE") == 1
        assert XcpCodec.data_type_size("UWORD") == 2
        assert XcpCodec.data_type_size("FLOAT32_IEEE") == 4
        assert XcpCodec.data_type_size("FLOAT64_IEEE") == 8
        assert XcpCodec.data_type_size("UNKNOWN") == 0

    def test_encode_set_daq_ptr(self):
        cmd = XcpCodec.encode_set_daq_ptr(daq_list=2, odt=1, entry=0)
        assert cmd[0] == XcpCmd.SET_DAQ_PTR
        assert cmd[2] == 2  # daq_list low
        assert cmd[4] == 1  # odt

    def test_encode_write_daq(self):
        cmd = XcpCodec.encode_write_daq(size=4, ext=0, address=0x2000)
        assert cmd[0] == XcpCmd.WRITE_DAQ
        assert cmd[2] == 4  # size
        assert cmd[4] == 0x00  # address low byte
        assert cmd[5] == 0x20

    def test_encode_start_stop_daq_list(self):
        cmd = XcpCodec.encode_start_stop_daq_list(mode=1, daq_list=0)
        assert cmd[0] == XcpCmd.START_STOP_DAQ_LIST
        assert cmd[1] == 1  # start

    def test_error_names(self):
        assert XcpError.name(0x22) == "OUT_OF_RANGE"
        assert XcpError.name(0x23) == "WRITE_PROTECTED"
        assert "UNKNOWN" in XcpError.name(0xFF)


# ── XCP Address Mapper tests ───────────────────────────────────────────────


class TestXcpAddressMapper:

    def _make_a2l_data(self) -> A2LData:
        return A2LData(
            characteristics=[
                A2LCharacteristic(
                    name="K_EngSpeed", long_identifier="Engine speed limit",
                    type="VALUE", address=0x1000, record_layout="RL_ULONG",
                    conversion="CM_EngSpeed", unit="rpm",
                    lower_limit=0, upper_limit=8000,
                ),
                A2LCharacteristic(
                    name="K_FuelMap", long_identifier="Fuel injection map",
                    type="MAP", address=0x2000, record_layout="RL_MAP",
                    conversion="CM_Fuel",
                ),
            ],
            measurements=[
                A2LMeasurement(
                    name="M_VehicleSpeed", long_identifier="Vehicle speed",
                    data_type="UWORD", conversion="CM_Speed",
                    unit="km/h", lower_limit=0, upper_limit=250,
                ),
                A2LMeasurement(
                    name="M_EngTemp", long_identifier="Engine coolant temp",
                    data_type="FLOAT32_IEEE", conversion="CM_Temp",
                    unit="degC",
                ),
            ],
            compu_methods=[],
            source_path="<test>",
        )

    def test_build_mappings(self):
        mapper = XcpAddressMapper()
        a2l = self._make_a2l_data()
        mappings = mapper.build_mappings(a2l)
        assert len(mappings) == 4

    def test_calibration_params(self):
        mapper = XcpAddressMapper()
        a2l = self._make_a2l_data()
        mappings = mapper.build_mappings(a2l)
        cal = mapper.get_calibration_params(mappings)
        assert len(cal) == 2
        names = {m.name for m in cal}
        assert "K_EngSpeed" in names
        assert "K_FuelMap" in names

    def test_measurement_params(self):
        mapper = XcpAddressMapper()
        a2l = self._make_a2l_data()
        mappings = mapper.build_mappings(a2l)
        meas = mapper.get_measurement_params(mappings)
        assert len(meas) == 2

    def test_find_mapping(self):
        mapper = XcpAddressMapper()
        a2l = self._make_a2l_data()
        mappings = mapper.build_mappings(a2l)
        m = mapper.find_mapping(mappings, "K_EngSpeed")
        assert m is not None
        assert m.address == 0x1000
        assert m.direction == "calibration"

    def test_find_mapping_not_found(self):
        mapper = XcpAddressMapper()
        mappings = mapper.build_mappings(self._make_a2l_data())
        assert mapper.find_mapping(mappings, "NonExistent") is None

    def test_find_by_address(self):
        mapper = XcpAddressMapper()
        mappings = mapper.build_mappings(self._make_a2l_data())
        result = mapper.find_by_address(mappings, 0x1000)
        assert len(result) == 1
        assert result[0].name == "K_EngSpeed"

    def test_sorted_by_address(self):
        mapper = XcpAddressMapper()
        mappings = mapper.build_mappings(self._make_a2l_data())
        addresses = [m.address for m in mappings if m.address > 0]
        assert addresses == sorted(addresses)

    def test_value_type_size(self):
        mapper = XcpAddressMapper()
        a2l = A2LData(
            characteristics=[
                A2LCharacteristic(name="K1", long_identifier="", type="VALUE",
                                  address=0x100, record_layout=""),
            ],
            measurements=[
                A2LMeasurement(name="M1", long_identifier="", data_type="FLOAT32_IEEE",
                               conversion=""),
            ],
            compu_methods=[], source_path="",
        )
        mappings = mapper.build_mappings(a2l)
        k1 = mapper.find_mapping(mappings, "K1")
        m1 = mapper.find_mapping(mappings, "M1")
        assert k1.size == 4  # VALUE default
        assert m1.size == 4  # FLOAT32_IEEE


# ── XCP Session + LoopbackTransport tests ──────────────────────────────────


class TestXcpSession:

    def test_connect(self):
        transport = LoopbackTransport()
        session = XcpSession(transport)
        assert not session.is_connected
        assert session.connect()
        assert session.is_connected
        assert session.connection.max_cto == 8

    def test_disconnect(self):
        transport = LoopbackTransport()
        session = XcpSession(transport)
        session.connect()
        session.disconnect()
        assert not session.is_connected

    def test_get_status(self):
        transport = LoopbackTransport()
        session = XcpSession(transport)
        session.connect()
        status = session.get_status()
        assert "resource_protection" in status

    def test_read_raw_short_upload(self):
        transport = LoopbackTransport()
        transport.memory[0x1000:0x1004] = struct.pack("<f", 3.14)
        session = XcpSession(transport)
        session.connect()
        raw = session.read_raw(0x1000, 4)
        assert len(raw) == 4
        value = struct.unpack("<f", raw)[0]
        assert abs(value - 3.14) < 0.001

    def test_write_raw_short_download(self):
        transport = LoopbackTransport()
        session = XcpSession(transport)
        session.connect()
        data = struct.pack("<f", 2.71)
        assert session.write_raw(0x2000, data)
        # Verify it was written
        assert bytes(transport.memory[0x2000:0x2004]) == data

    def test_read_write_raw_roundtrip(self):
        transport = LoopbackTransport()
        session = XcpSession(transport)
        session.connect()
        original = struct.pack("<I", 0xDEADBEEF)
        session.write_raw(0x3000, original)
        readback = session.read_raw(0x3000, 4)
        assert readback == original

    def test_read_parameter_by_name(self):
        transport = LoopbackTransport()
        transport.memory[0x1000:0x1004] = struct.pack("<I", 5500)
        session = XcpSession(transport)
        session.connect()
        session.set_mappings([
            XcpAddressMapping(name="K_EngSpeed", address=0x1000, size=4,
                              data_type="ULONG", direction="calibration"),
        ])
        result = session.read_parameter("K_EngSpeed")
        assert result.success
        assert result.raw_value == 5500.0

    def test_write_parameter_by_name(self):
        transport = LoopbackTransport()
        session = XcpSession(transport)
        session.connect()
        session.set_mappings([
            XcpAddressMapping(name="K_EngSpeed", address=0x1000, size=4,
                              data_type="ULONG", direction="calibration"),
        ])
        result = session.write_parameter("K_EngSpeed", 6000.0)
        assert result.success
        # Verify
        raw = transport.memory[0x1000:0x1004]
        assert struct.unpack("<I", raw)[0] == 6000

    def test_write_measurement_fails(self):
        transport = LoopbackTransport()
        session = XcpSession(transport)
        session.connect()
        session.set_mappings([
            XcpAddressMapping(name="M_Speed", address=0x2000, size=2,
                              data_type="UWORD", direction="measurement"),
        ])
        result = session.write_parameter("M_Speed", 100.0)
        assert not result.success
        assert "read-only" in result.error

    def test_read_nonexistent_parameter(self):
        transport = LoopbackTransport()
        session = XcpSession(transport)
        session.connect()
        result = session.read_parameter("NonExistent")
        assert not result.success
        assert "not found" in result.error

    def test_write_disconnected(self):
        transport = LoopbackTransport()
        session = XcpSession(transport)
        session.set_mappings([
            XcpAddressMapping(name="K1", address=0x1000, size=4,
                              data_type="ULONG", direction="calibration"),
        ])
        result = session.write_parameter("K1", 42.0)
        assert not result.success

    def test_loopback_large_write(self):
        """Test multi-frame download via LoopbackTransport."""
        transport = LoopbackTransport()
        session = XcpSession(transport)
        session.connect()
        data = bytes(range(32))  # 32 bytes, needs multiple DOWNLOAD frames
        assert session.write_raw(0x5000, data)
        readback = session.read_raw(0x5000, 32)
        assert readback == data

    def test_loopback_out_of_range(self):
        transport = LoopbackTransport()
        session = XcpSession(transport)
        session.connect()
        # Address beyond memory size
        raw = session.read_raw(0x100000, 4)
        assert raw == b""

    def test_loopback_disconnect_clears_state(self):
        transport = LoopbackTransport()
        session = XcpSession(transport)
        session.connect()
        session.disconnect()
        assert not session.is_connected


# ── CCP Codec tests ────────────────────────────────────────────────────────


class TestCcpCodec:

    def test_encode_connect(self):
        cmd = CcpCodec.encode_connect(station_address=0x0001)
        assert cmd[0] == CcpCmd.CONNECT
        assert cmd[2] == 0x01
        assert cmd[3] == 0x00

    def test_encode_test(self):
        cmd = CcpCodec.encode_test(0x0001)
        assert cmd[0] == CcpCmd.TEST

    def test_encode_disconnect(self):
        cmd = CcpCodec.encode_disconnect()
        assert cmd[0] == CcpCmd.DISCONNECT

    def test_encode_get_ccp_version(self):
        cmd = CcpCodec.encode_get_ccp_version()
        assert cmd[0] == CcpCmd.GET_CCP_VERSION

    def test_decode_ccp_version(self):
        data = bytes([CcpError.ACK, 0x00, 0x02, 0x01])  # v2.1
        major, minor = CcpCodec.decode_ccp_version(data)
        assert major == 2
        assert minor == 1

    def test_encode_set_mta(self):
        cmd = CcpCodec.encode_set_mta(address=0x12345678, addr_ext=0, mta_num=0)
        assert cmd[0] == CcpCmd.SET_MTA
        assert cmd[4] == 0x78
        assert cmd[5] == 0x56
        assert cmd[6] == 0x34
        assert cmd[7] == 0x12

    def test_encode_set_mta_ext(self):
        cmd = CcpCodec.encode_set_mta(address=0x0000, addr_ext=1, mta_num=0)
        assert cmd[3] == 1  # addr_ext

    def test_encode_upload(self):
        cmd = CcpCodec.encode_upload(4)
        assert cmd[0] == CcpCmd.UPLOAD
        assert cmd[2] == 4

    def test_encode_short_upload(self):
        cmd = CcpCodec.encode_short_upload(size=2, address=0x1000, addr_ext=0)
        assert cmd[0] == CcpCmd.SHORT_UP
        assert cmd[2] == 2
        assert cmd[4] == 0x00
        assert cmd[5] == 0x10

    def test_encode_dnload(self):
        data = bytes([0xAA, 0xBB, 0xCC])
        cmd = CcpCodec.encode_dnload(data)
        assert cmd[0] == CcpCmd.DNLOAD
        assert cmd[2] == 3  # size
        assert cmd[3:] == data

    def test_encode_dnload_max_5_bytes(self):
        data = bytes(5)
        cmd = CcpCodec.encode_dnload(data)
        assert len(cmd) == 8

    def test_encode_dnload_exceeds_limit(self):
        with pytest.raises(ValueError, match="max 5 bytes"):
            CcpCodec.encode_dnload(bytes(6))

    def test_encode_dnload_6(self):
        data = bytes([1, 2, 3, 4, 5, 6])
        cmd = CcpCodec.encode_dnload_6(data)
        assert cmd[0] == CcpCmd.DNLOAD_6
        assert cmd[2:] == data

    def test_encode_dnload_6_wrong_size(self):
        with pytest.raises(ValueError, match="exactly 6 bytes"):
            CcpCodec.encode_dnload_6(bytes(4))

    def test_decode_ack_response(self):
        data = bytes([CcpError.ACK, 0x00, 0x01, 0x02])
        resp = CcpCodec.decode_response(data)
        assert resp.is_ack
        assert resp.data == bytes([0x01, 0x02])

    def test_decode_error_response(self):
        data = bytes([CcpError.PARAM_OUT_OF_RANGE, 0x00])
        resp = CcpCodec.decode_response(data)
        assert resp.is_error
        assert resp.return_code == CcpError.PARAM_OUT_OF_RANGE

    def test_decode_upload_response(self):
        data = bytes([CcpError.ACK, 0x00, 0xDE, 0xAD, 0xBE, 0xEF])
        result = CcpCodec.decode_upload_response(data, 4)
        assert result == bytes([0xDE, 0xAD, 0xBE, 0xEF])

    def test_encode_get_daq_size(self):
        cmd = CcpCodec.encode_get_daq_size(daq_list=0)
        assert cmd[0] == CcpCmd.GET_DAQ_SIZE

    def test_encode_set_daq_ptr(self):
        cmd = CcpCodec.encode_set_daq_ptr(daq_list=1, odt=2, element=3)
        assert cmd[0] == CcpCmd.SET_DAQ_PTR
        assert cmd[2] == 1  # daq_list
        assert cmd[4] == 2  # odt
        assert cmd[5] == 3  # element

    def test_encode_write_daq(self):
        cmd = CcpCodec.encode_write_daq(size=4, addr_ext=0, address=0x2000)
        assert cmd[0] == CcpCmd.WRITE_DAQ
        assert cmd[2] == 4
        assert cmd[5] == 0x20

    def test_encode_start_stop(self):
        cmd = CcpCodec.encode_start_stop(daq_list=0, last_odt=2, event_channel=5)
        assert cmd[0] == CcpCmd.START_STOP
        assert cmd[2] == 1  # start

    def test_unpack_value_ubyte(self):
        assert CcpCodec.unpack_value(bytes([42]), "UBYTE") == 42.0

    def test_pack_value_uint16(self):
        result = CcpCodec.pack_value(1000, "UWORD")
        assert struct.unpack("<H", result)[0] == 1000

    def test_data_type_size(self):
        assert CcpCodec.data_type_size("UBYTE") == 1
        assert CcpCodec.data_type_size("FLOAT32_IEEE") == 4
        assert CcpCodec.data_type_size("UNKNOWN") == 0

    def test_error_names(self):
        assert CcpError.name(0x00) == "ACK"
        assert CcpError.name(0x32) == "PARAM_OUT_OF_RANGE"
        assert "UNKNOWN" in CcpError.name(0xFF)
