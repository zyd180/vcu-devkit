"""DCM (Data Calibration Method) file parser.

DCM is a text-based calibration data format used by ETAS INCA. It stores
actual calibration parameter values alongside their definitions. The format
is ASAP2-compatible, with CHARACTERISTIC blocks that include VALUE = lines.

Typical workflow: A2L defines parameter structure → DCM stores actual values.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from core.parsers.base import BaseParser, ParseResult

logger = logging.getLogger(__name__)


@dataclass
class DCMCharacteristic:
    """Calibration parameter with its actual value from a DCM file."""

    name: str
    description: str = ""
    value: float | None = None
    lower_limit: float = 0.0
    upper_limit: float = 0.0
    unit: str = ""


@dataclass
class DCMData:
    """Parsed DCM file data."""

    characteristics: list[DCMCharacteristic]
    source_path: str


class DCMParser(BaseParser):
    """Parse DCM (Data Calibration Method) calibration data files."""

    def supported_extensions(self) -> list[str]:
        return [".dcm"]

    def validate(self, file_path: Path) -> list[str]:
        errors: list[str] = []
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            if "/BEGIN" not in content.upper():
                errors.append("File does not contain DCM /begin blocks")
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
        characteristics = self._extract_characteristics(content)
        return DCMData(characteristics=characteristics, source_path=source)

    def _extract_characteristics(self, content: str) -> list[DCMCharacteristic]:
        """Extract all CHARACTERISTIC blocks from DCM content."""
        results = []
        pattern = re.compile(
            r"/begin\s+CHARACTERISTIC\s+(.*?)/end\s+CHARACTERISTIC",
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(content):
            try:
                char = self._parse_characteristic(match.group(1))
                if char:
                    results.append(char)
            except (ValueError, IndexError, AttributeError) as exc:
                logger.warning("Failed to parse CHARACTERISTIC block: %s", exc)
                continue
        return results

    def _parse_characteristic(self, block: str) -> DCMCharacteristic | None:
        block = block.strip()
        if not block:
            return None

        lines = block.split("\n")

        # Extract header tokens (name, description, type, address, ...)
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

            # VALUE = xxx (actual calibration value)
            value_match = re.match(r"VALUE\s*=\s*([\d\.\-\+eE]+)", stripped, re.IGNORECASE)
            if value_match:
                try:
                    value = float(value_match.group(1))
                except ValueError:
                    pass
                continue

            # LOWER_LIMIT / UPPER_LIMIT
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

            # UNIT
            unit_match = re.match(r'UNIT\s+"([^"]*)"', stripped, re.IGNORECASE)
            if unit_match:
                unit = unit_match.group(1)
                continue

            # Skip sub-keywords
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

            # Header line: name "description" type addr layout ...
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
                # Bare numeric lines after header = lower/upper limits
                # DCM format: header line, then lower_limit line, then upper_limit line
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

        # If limits weren't set, try header positional tokens
        # A2L header: name "desc" type addr layout max_diff conv lower upper
        # DCM header: name "desc" VALUE addr layout max_diff conv lower upper
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
            lower_limit=lower_limit or 0.0,
            upper_limit=upper_limit or 0.0,
            unit=unit,
        )
