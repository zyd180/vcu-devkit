"""A2L → XCP address mapping — build XCP read/write targets from A2L data."""

from __future__ import annotations

from core.parsers.a2l_parser import A2LData, A2LCharacteristic, A2LMeasurement
from core.protocols.xcp import XcpAddressMapping
from core.protocols.xcp_codec import XcpCodec


class XcpAddressMapper:
    """Build XCP address mapping from A2L calibration data.

    Maps A2L CHARACTERISTIC (calibration parameters, read/write) and
    MEASUREMENT (signal variables, read-only) to XcpAddressMapping entries
    with ECU memory addresses and byte sizes.
    """

    def build_mappings(self, a2l: A2LData) -> list[XcpAddressMapping]:
        """Build full address mapping list from A2L data.

        Returns:
            List of XcpAddressMapping, sorted by address.
        """
        mappings: list[XcpAddressMapping] = []

        for char in a2l.characteristics:
            size = self._resolve_size(char)
            if size == 0:
                continue
            mappings.append(XcpAddressMapping(
                name=char.name,
                address=char.address,
                size=size,
                data_type=char.type,
                direction="calibration",
                conversion=char.conversion,
            ))

        for meas in a2l.measurements:
            size = XcpCodec.data_type_size(meas.data_type)
            if size == 0:
                continue
            mappings.append(XcpAddressMapping(
                name=meas.name,
                address=0,  # Measurements may not have direct address in A2L
                size=size,
                data_type=meas.data_type,
                direction="measurement",
                conversion=meas.conversion,
            ))

        mappings.sort(key=lambda m: (m.address, m.name))
        return mappings

    def find_mapping(
        self, mappings: list[XcpAddressMapping], name: str,
    ) -> XcpAddressMapping | None:
        """Find a mapping by parameter name (case-sensitive)."""
        for m in mappings:
            if m.name == name:
                return m
        return None

    def find_by_address(
        self, mappings: list[XcpAddressMapping], address: int,
    ) -> list[XcpAddressMapping]:
        """Find all mappings at a given address."""
        return [m for m in mappings if m.address == address]

    def get_calibration_params(
        self, mappings: list[XcpAddressMapping],
    ) -> list[XcpAddressMapping]:
        """Return only calibration (read/write) parameters."""
        return [m for m in mappings if m.direction == "calibration"]

    def get_measurement_params(
        self, mappings: list[XcpAddressMapping],
    ) -> list[XcpAddressMapping]:
        """Return only measurement (read-only) parameters."""
        return [m for m in mappings if m.direction == "measurement"]

    @staticmethod
    def _resolve_size(char: A2LCharacteristic) -> int:
        """Resolve byte size for an A2L CHARACTERISTIC.

        CHARACTERISTIC type is VALUE/CURVE/MAP/etc., not a primitive type.
        We estimate size from the record layout or use defaults:
            VALUE → 4 bytes (float32 or uint32)
            CURVE → depends on axis points
            MAP → depends on axis points
        """
        type_sizes = {
            "VALUE": 4,
            "ASCII": 1,  # Variable, but at least 1
            "CURVE": 8,  # Minimum estimate
            "MAP": 16,   # Minimum estimate
            "CUBE_4": 32,
            "CUBE_5": 64,
            "VAL_BLK": 4,
        }
        return type_sizes.get(char.type, 4)
