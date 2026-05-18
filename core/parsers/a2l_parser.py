"""A2L (ASAP2) calibration file parser.

A2L is a text-based format used by ETAS INCA, Vector CANape, and other
calibration tools. It defines measurement variables and calibration
parameters (characteristics) with addresses, data types, and conversion methods.

This parser extracts CHARACTERISTIC (calibration parameters) and MEASUREMENT
(signal/variable definitions) sections.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from core.parsers.base import BaseParser, ParseResult


@dataclass
class A2LCharacteristic:
    """Calibration parameter (CHARACTERISTIC block)."""
    name: str
    long_identifier: str
    type: str                       # VALUE, CURVE, MAP, ASCII, CUBE, etc.
    address: int
    record_layout: str
    max_diff: float = 0.0
    conversion: str = ""
    lower_limit: float = 0.0
    upper_limit: float = 0.0
    unit: str = ""
    description: str = ""


@dataclass
class A2LMeasurement:
    """Measurement variable (MEASUREMENT block)."""
    name: str
    long_identifier: str
    data_type: str                  # UBYTE, SBYTE, UWORD, SWORD, ULONG, SLONG, FLOAT32_IEEE, etc.
    conversion: str
    resolution: int = 0
    accuracy: float = 0.0
    lower_limit: float = 0.0
    upper_limit: float = 0.0
    unit: str = ""
    description: str = ""


@dataclass
class A2LCompuMethod:
    """Conversion method (COMPU_METHOD block)."""
    name: str
    description: str
    conversion_type: str            # IDENTICAL, LINEAR, RAT_FUNC, FORM, TAB_INTP, TAB_NOINTP
    format_string: str = ""
    unit: str = ""
    coeffs: list[float] = field(default_factory=list)  # For RAT_FUNC: a,b,c,d,e,f
    formula: str = ""               # For FORM type


@dataclass
class A2LData:
    """Parsed A2L file data."""
    characteristics: list[A2LCharacteristic]
    measurements: list[A2LMeasurement]
    compu_methods: list[A2LCompuMethod]
    source_path: str


class A2LParser(BaseParser):
    """Parse A2L (ASAP2) calibration files."""

    def supported_extensions(self) -> list[str]:
        return [".a2l"]

    def validate(self, file_path: Path) -> list[str]:
        errors: list[str] = []
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            # Check for basic A2L structure
            if "/BEGIN" not in content.upper():
                errors.append("File does not contain A2L /begin blocks")
        except Exception as exc:
            errors.append(f"Read error: {exc}")
        return errors

    def parse(self, file_path: Path) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            return ParseResult(success=False, errors=[f"File not found: {path}"])
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            data = self._parse_content(content, str(path))
            return ParseResult(success=True, data=data, source_path=path)
        except Exception as exc:
            return ParseResult(success=False, errors=[str(exc)])

    def parse_string(self, content: str) -> ParseResult:
        try:
            data = self._parse_content(content, "<string>")
            return ParseResult(success=True, data=data)
        except Exception as exc:
            return ParseResult(success=False, errors=[str(exc)])

    def _parse_content(self, content: str, source: str) -> A2LData:
        characteristics = self._extract_blocks(content, "CHARACTERISTIC", self._parse_characteristic)
        measurements = self._extract_blocks(content, "MEASUREMENT", self._parse_measurement)
        compu_methods = self._extract_blocks(content, "COMPU_METHOD", self._parse_compu_method)
        return A2LData(
            characteristics=characteristics,
            measurements=measurements,
            compu_methods=compu_methods,
            source_path=source,
        )

    def _extract_blocks(self, content: str, block_type: str, parser_fn) -> list:
        """Extract all /begin BLOCK_TYPE ... /end BLOCK_TYPE blocks."""
        results = []
        pattern = re.compile(
            rf'/begin\s+{block_type}\s+(.*?)/end\s+{block_type}',
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(content):
            try:
                result = parser_fn(match.group(1))
                if result:
                    results.append(result)
            except Exception:
                continue
        return results

    def _parse_characteristic(self, block: str) -> A2LCharacteristic | None:
        lines = block.strip().split('\n')
        if not lines:
            return None

        # First line: name long_identifier type address record_layout [max_diff] [conversion]
        first = lines[0].strip().split()
        if len(first) < 5:
            return None

        name = first[0]
        # long_identifier is quoted string
        long_id_match = re.search(r'"([^"]*)"', lines[0])
        long_id = long_id_match.group(1) if long_id_match else ""

        # Find remaining tokens after the quoted string
        after_quote = lines[0][long_id_match.end():].strip().split() if long_id_match else first[1:]
        type_val = after_quote[0] if after_quote else "VALUE"
        address = int(after_quote[1], 16) if len(after_quote) > 1 else 0
        record_layout = after_quote[2] if len(after_quote) > 2 else ""

        char = A2LCharacteristic(
            name=name,
            long_identifier=long_id,
            type=type_val,
            address=address,
            record_layout=record_layout,
        )

        # Parse sub-keys
        block_text = '\n'.join(lines[1:])
        char.conversion = self._extract_keyword(block_text, "COMPU_METHOD")
        char.unit = self._extract_keyword(block_text, "UNIT")
        char.description = self._extract_keyword(block_text, "LONG-NAME") or long_id

        # Limits
        limits = self._extract_limits(block_text)
        char.lower_limit = limits[0]
        char.upper_limit = limits[1]

        return char

    def _parse_measurement(self, block: str) -> A2LMeasurement | None:
        lines = block.strip().split('\n')
        if not lines:
            return None

        # First line: name long_identifier data_type conversion [resolution] [accuracy] lower_limit upper_limit
        first = lines[0].strip()
        name_match = re.match(r'(\S+)\s+"([^"]*)"\s+(\S+)\s+(\S+)\s*(.*)', first)
        if not name_match:
            return None

        name = name_match.group(1)
        long_id = name_match.group(2)
        data_type = name_match.group(3)
        conversion = name_match.group(4)
        rest = name_match.group(5).strip().split()

        meas = A2LMeasurement(
            name=name,
            long_identifier=long_id,
            data_type=data_type,
            conversion=conversion,
        )

        if len(rest) >= 2:
            try:
                meas.resolution = int(rest[0])
                meas.accuracy = float(rest[1])
            except ValueError:
                pass
        if len(rest) >= 4:
            try:
                meas.lower_limit = float(rest[2])
                meas.upper_limit = float(rest[3])
            except ValueError:
                pass

        block_text = '\n'.join(lines[1:])
        meas.unit = self._extract_keyword(block_text, "UNIT") or ""
        meas.description = long_id

        return meas

    def _parse_compu_method(self, block: str) -> A2LCompuMethod | None:
        lines = block.strip().split('\n')
        if not lines:
            return None

        # First line: name description conversion_type format_string unit
        first = lines[0].strip()
        parts = re.match(r'(\S+)\s+"([^"]*)"\s+(\S+)\s+(\S+)\s+(\S+)\s*(.*)', first)
        if not parts:
            return None

        cm = A2LCompuMethod(
            name=parts.group(1),
            description=parts.group(2),
            conversion_type=parts.group(3),
            format_string=parts.group(4),
            unit=parts.group(5),
        )

        # COEFFS for RAT_FUNC
        block_text = '\n'.join(lines[1:])
        coeffs_match = re.search(r'COEFFS\s+([\d\.\-\+\s]+)', block_text)
        if coeffs_match:
            cm.coeffs = [float(x) for x in coeffs_match.group(1).strip().split()]

        # FORMULA for FORM type
        formula_match = re.search(r'FORMULA\s+"([^"]*)"', block_text)
        if formula_match:
            cm.formula = formula_match.group(1)

        return cm

    @staticmethod
    def _extract_keyword(block_text: str, keyword: str) -> str:
        """Extract value after a keyword in block text."""
        match = re.search(rf'{keyword}\s+"?([^"\n\s]+)"?', block_text, re.IGNORECASE)
        return match.group(1) if match else ""

    @staticmethod
    def _extract_limits(block_text: str) -> tuple[float, float]:
        """Extract lower/upper limits."""
        match = re.search(r'LOWER_LIMIT\s+([\d\.\-\+eE]+)\s+UPPER_LIMIT\s+([\d\.\-\+eE]+)', block_text, re.IGNORECASE)
        if match:
            return float(match.group(1)), float(match.group(2))
        return 0.0, 0.0


# ── Serialisation ────────────────────────────────────────────────────────────


def a2l_data_to_dict(data: A2LData) -> dict:
    """Convert A2LData to JSON-serialisable dict."""
    return {
        "source_path": data.source_path,
        "characteristics": [
            {
                "name": c.name,
                "long_identifier": c.long_identifier,
                "type": c.type,
                "address": hex(c.address),
                "record_layout": c.record_layout,
                "conversion": c.conversion,
                "unit": c.unit,
                "lower_limit": c.lower_limit,
                "upper_limit": c.upper_limit,
            }
            for c in data.characteristics
        ],
        "measurements": [
            {
                "name": m.name,
                "long_identifier": m.long_identifier,
                "data_type": m.data_type,
                "conversion": m.conversion,
                "unit": m.unit,
                "lower_limit": m.lower_limit,
                "upper_limit": m.upper_limit,
            }
            for m in data.measurements
        ],
        "compu_methods": [
            {
                "name": cm.name,
                "description": cm.description,
                "conversion_type": cm.conversion_type,
                "format_string": cm.format_string,
                "unit": cm.unit,
                "coeffs": cm.coeffs,
                "formula": cm.formula,
            }
            for cm in data.compu_methods
        ],
    }
