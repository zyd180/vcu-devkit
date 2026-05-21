"""DCM (Data Calibration Method) file parser.

Supports two DCM formats:
- ASAP2-compatible: /begin CHARACTERISTIC ... /end CHARACTERISTIC
- DAMOS/CDM: FESTWERT ... END, GRUPPENKENNFELD ... END, FESTWERTEBLOCK ... END

DAMOS/CDM is the format used by ETAS INCA CDM (Calibration Data Manager) exports.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.parsers.base import BaseParser, ParseResult

logger = logging.getLogger(__name__)


@dataclass
class DCMCharacteristic:
    """Calibration parameter with its actual value from a DCM file."""

    name: str
    description: str = ""
    value: float | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    unit: str = ""
    # For arrays/maps: multiple values
    values: list[float] = field(default_factory=list)
    block_type: str = ""  # FESTWERT, GRUPPENKENNFELD, FESTWERTEBLOCK, CHARACTERISTIC
    raw_block: str = ""  # original block text for roundtrip export


@dataclass
class DCMData:
    """Parsed DCM file data."""

    characteristics: list[DCMCharacteristic]
    source_path: str


class DCMParser(BaseParser):
    """Parse DCM calibration data files (ASAP2 and DAMOS/CDM formats)."""

    def supported_extensions(self) -> list[str]:
        return [".dcm"]

    def validate(self, file_path: Path) -> list[str]:
        errors: list[str] = []
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            upper = content.upper()
            if "/BEGIN" not in upper and "FESTWERT" not in upper and "KONSERVIERUNG_FORMAT" not in upper:
                errors.append("File does not appear to be a DCM file")
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
        except (OSError, ValueError) as exc:
            return ParseResult(success=False, errors=[str(exc)])

    def parse_string(self, content: str) -> ParseResult:
        try:
            data = self._parse_content(content, "<string>")
            return ParseResult(success=True, data=data)
        except ValueError as exc:
            return ParseResult(success=False, errors=[str(exc)])

    def _parse_content(self, content: str, source: str) -> DCMData:
        if self._is_damos_format(content):
            characteristics = self._parse_damos(content)
        else:
            characteristics = self._parse_asap2(content)
        return DCMData(characteristics=characteristics, source_path=source)

    @staticmethod
    def _is_damos_format(content: str) -> bool:
        """Detect DAMOS/CDM format by checking for KONSERVIERUNG_FORMAT or FESTWERT."""
        head = content[:2000].upper()
        return "KONSERVIERUNG_FORMAT" in head or "FESTWERT" in head

    # ── DAMOS/CDM format ─────────────────────────────────────────────

    def _parse_damos(self, content: str) -> list[DCMCharacteristic]:
        results: list[DCMCharacteristic] = []
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # Skip comments and empty lines
            if not line or line.startswith("*"):
                i += 1
                continue

            # FESTWERT (scalar)
            m = re.match(r"^FESTWERT\s+(\S+)", line, re.IGNORECASE)
            if m:
                char, end_idx = self._parse_damos_block(lines, i, m.group(1), "FESTWERT")
                if char:
                    char.raw_block = "\n".join(lines[i : end_idx + 1])
                    results.append(char)
                i = end_idx + 1
                continue

            # GRUPPENKENNFELD (2D map)
            m = re.match(r"^GRUPPENKENNFELD\s+(\S+)", line, re.IGNORECASE)
            if m:
                char, end_idx = self._parse_damos_block(lines, i, m.group(1), "GRUPPENKENNFELD")
                if char:
                    char.raw_block = "\n".join(lines[i : end_idx + 1])
                    results.append(char)
                i = end_idx + 1
                continue

            # FESTWERTEBLOCK (value array)
            m = re.match(r"^FESTWERTEBLOCK\s+(\S+)", line, re.IGNORECASE)
            if m:
                char, end_idx = self._parse_damos_block(lines, i, m.group(1), "FESTWERTEBLOCK")
                if char:
                    char.raw_block = "\n".join(lines[i : end_idx + 1])
                    results.append(char)
                i = end_idx + 1
                continue

            i += 1

        return results

    def _parse_damos_block(
        self, lines: list[str], start: int, name: str, block_type: str
    ) -> tuple[DCMCharacteristic | None, int]:
        """Parse a single DAMOS block from start to END. Returns (char, end_line_index)."""
        description = ""
        unit = ""
        values: list[float] = []

        i = start + 1
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith("*"):
                i += 1
                continue
            if line.upper() == "END":
                break

            # LANGNAME "description"
            m = re.match(r'LANGNAME\s+"([^"]*)"', line, re.IGNORECASE)
            if m:
                description = m.group(1)
                i += 1
                continue

            # EINHEIT_W "unit" (value unit)
            m = re.match(r'EINHEIT_W\s+"([^"]*)"', line, re.IGNORECASE)
            if m:
                unit = m.group(1)
                i += 1
                continue

            # EINHEIT_X "unit" (X axis unit — use as unit if no EINHEIT_W)
            m = re.match(r'EINHEIT_X\s+"([^"]*)"', line, re.IGNORECASE)
            if m:
                if not unit:
                    unit = m.group(1)
                i += 1
                continue

            # EINHEIT_Y "unit" (Y axis unit — skip)
            if re.match(r'EINHEIT_Y\s+"', line, re.IGNORECASE):
                i += 1
                continue

            # WERT <values...> (one or more values on the line)
            m = re.match(r"WERT\s+(.*)", line, re.IGNORECASE)
            if m:
                for tok in m.group(1).split():
                    try:
                        values.append(self._normalize_float(float(tok)))
                    except ValueError:
                        pass
                i += 1
                continue

            # ST/X, ST/Y, *SST, *SSTX, *SSTY — axis data, skip
            if re.match(r"(\*SST|ST/|FESTWERT)", line, re.IGNORECASE):
                i += 1
                continue

            i += 1

        if not name:
            return None, i

        # For scalars: single value; for arrays/maps: keep all values
        scalar_value = values[0] if len(values) == 1 else (values[0] if values else None)

        char = DCMCharacteristic(
            name=name,
            description=description,
            value=scalar_value,
            unit=unit,
            values=values,
            block_type=block_type,
        )
        return char, i

    @staticmethod
    def _normalize_float(val: float) -> float:
        """Normalize a float to strip float32 precision artifacts.

        E.g. 0.1000000014901161 → 0.1, 1638.4000244140625 → 1638.4

        DCM files from INCA store float32 values with 16 decimal places,
        which introduces artifacts when parsed as float64. We round-trip
        through float32 to recover the canonical value.
        """
        import struct

        try:
            f32_bits = struct.pack("f", val)
            return struct.unpack("f", f32_bits)[0]
        except (struct.error, OverflowError):
            return val

    # ── ASAP2 format ─────────────────────────────────────────────────

    def _parse_asap2(self, content: str) -> list[DCMCharacteristic]:
        results = []
        pattern = re.compile(
            r"/begin\s+CHARACTERISTIC\s+(.*?)/end\s+CHARACTERISTIC",
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(content):
            try:
                char = self._parse_asap2_characteristic(match.group(1))
                if char:
                    results.append(char)
            except (ValueError, IndexError, AttributeError) as exc:
                logger.warning("Failed to parse CHARACTERISTIC block: %s", exc)
                continue
        return results

    def _parse_asap2_characteristic(self, block: str) -> DCMCharacteristic | None:
        block = block.strip()
        if not block:
            return None

        lines = block.split("\n")

        header_tokens: list[str] = []
        description = ""
        value: float | None = None
        lower_limit: float | None = None
        upper_limit: float | None = None
        unit = ""

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            value_match = re.match(r"VALUE\s*=\s*([\d\.\-\+eE]+)", stripped, re.IGNORECASE)
            if value_match:
                try:
                    value = float(value_match.group(1))
                except ValueError:
                    pass
                continue

            ll_match = re.match(r"LOWER_LIMIT\s+([\d\.\-\+eE]+)", stripped, re.IGNORECASE)
            if ll_match:
                try:
                    lower_limit = float(ll_match.group(1))
                except ValueError:
                    pass
                continue

            ul_match = re.match(r"UPPER_LIMIT\s+([\d\.\-\+eE]+)", stripped, re.IGNORECASE)
            if ul_match:
                try:
                    upper_limit = float(ul_match.group(1))
                except ValueError:
                    pass
                continue

            unit_match = re.match(r'UNIT\s+"([^"]*)"', stripped, re.IGNORECASE)
            if unit_match:
                unit = unit_match.group(1)
                continue

            first_tok = stripped.split()[0].upper() if stripped.split() else ""
            if first_tok in (
                "COMPU_METHOD",
                "FORMAT",
                "NUMBER",
                "BIT_MASK",
                "READ_ONLY",
                "DISPLAY_IDENTIFIER",
                "MATRIX_DIM",
                "ECU_ADDRESS",
                "ECU_ADDRESS_EXTENSION",
                "ANNOTATION",
                "FUNCTION_LIST",
                "EXTENDED_LIMITS",
                "LONG-NAME",
            ):
                continue

            if not header_tokens:
                q = re.search(r'"([^"]*)"', line)
                if q:
                    description = q.group(1)
                    before = line[: q.start()].strip().split()
                    after = line[q.end() :].strip().split()
                    header_tokens = before + after
                else:
                    header_tokens = stripped.split()
            else:
                try:
                    num = float(stripped)
                    if lower_limit is None and upper_limit is None:
                        lower_limit = num
                    elif upper_limit is None:
                        upper_limit = num
                except ValueError:
                    pass

        if not header_tokens:
            return None

        name = header_tokens[0]

        if upper_limit is None and lower_limit is None:
            if len(header_tokens) >= 8:
                try:
                    lower_limit = float(header_tokens[6])
                    upper_limit = float(header_tokens[7])
                except (ValueError, IndexError):
                    pass

        return DCMCharacteristic(
            name=name,
            description=description or (header_tokens[1] if len(header_tokens) > 1 else ""),
            value=value,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            unit=unit,
            block_type="CHARACTERISTIC",
        )
