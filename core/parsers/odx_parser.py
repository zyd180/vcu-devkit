"""ODX / CDD diagnostic file parser (basic implementation).

ODX (Open Diagnostic data eXchange) is an XML-based standard for describing
diagnostic data. CDD (CANdelaStudio Diagnostic Database) is Vector's format.

This parser extracts DTCs, diagnostic services, and DID definitions from
ODX 2.2 / CDD files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from lxml import etree

from core.parsers.base import BaseParser, ParseResult

# Safe parser: disable external entities and network access (XXE prevention)
_SAFE_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)


@dataclass
class ODXDTC:
    """DTC extracted from ODX/CDD."""
    code: str
    description: str
    severity: str = "warning"
    obd_related: bool = False
    snapshot_dids: list[str] = field(default_factory=list)


@dataclass
class ODXService:
    """Diagnostic service extracted from ODX/CDD."""
    sid: str
    name: str
    sub_functions: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ODXData:
    """Parsed ODX/CDD data."""
    dtcs: list[ODXDTC]
    services: list[ODXService]
    source_path: str


class ODXParser(BaseParser):
    """Parse ODX 2.2 and CDD files."""

    def supported_extensions(self) -> list[str]:
        return [".odx", ".odx-d", ".odx-c", ".cdd"]

    def validate(self, file_path: Path) -> list[str]:
        errors: list[str] = []
        try:
            tree = etree.parse(str(file_path), parser=_SAFE_PARSER)
            root = tree.getroot()
            tag = etree.QName(root).localname if isinstance(root.tag, str) else ""
            if not tag:
                errors.append("Root element has no tag")
        except Exception as exc:
            errors.append(f"Parse error: {exc}")
        return errors

    def parse(self, file_path: Path) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            return ParseResult(success=False, errors=[f"File not found: {path}"])
        try:
            tree = etree.parse(str(path), parser=_SAFE_PARSER)
            data = self._parse_tree(tree, str(path))
            return ParseResult(success=True, data=data, source_path=path)
        except Exception as exc:
            return ParseResult(success=False, errors=[str(exc)])

    def _parse_tree(self, tree: etree._ElementTree, source: str) -> ODXData:
        root = tree.getroot()
        dtcs = self._extract_dtcs(root)
        services = self._extract_services(root)
        return ODXData(dtcs=dtcs, services=services, source_path=source)

    def _extract_dtcs(self, root) -> list[ODXDTC]:
        """Extract DTCs from ODX DIAG-CODE or CDD DTC-PARAM."""
        dtcs: list[ODXDTC] = []
        # ODX 2.2 pattern: //DIAG-CODE
        for elem in root.iter():
            tag = etree.QName(elem).localname if isinstance(elem.tag, str) else ""
            if tag in ("DIAG-CODE", "TROUBLE-CODE", "DTC"):
                code = ""
                desc = ""
                for child in elem:
                    ctag = etree.QName(child).localname if isinstance(child.tag, str) else ""
                    if ctag in ("CODE", "VALUE") and child.text:
                        code = child.text.strip()
                    elif ctag in ("TEXT", "DESCRIPTION", "LONG-NAME") and child.text:
                        desc = child.text.strip()
                if code:
                    dtcs.append(ODXDTC(code=code, description=desc))
        return dtcs

    def _extract_services(self, root) -> list[ODXService]:
        """Extract diagnostic services from ODX DIAG-SERVICE."""
        services: list[ODXService] = []
        for elem in root.iter():
            tag = etree.QName(elem).localname if isinstance(elem.tag, str) else ""
            if tag in ("DIAG-SERVICE", "DIAGNOSTIC-SERVICE"):
                name = ""
                sid = ""
                desc = ""
                for child in elem:
                    ctag = etree.QName(child).localname if isinstance(child.tag, str) else ""
                    if ctag in ("SHORT-NAME", "NAME") and child.text:
                        name = child.text.strip()
                    elif ctag in ("SEMANTIC",) and child.text:
                        sid = child.text.strip()
                    elif ctag in ("LONG-NAME", "DESCRIPTION", "TEXT") and child.text:
                        desc = child.text.strip()
                if name:
                    services.append(ODXService(sid=sid, name=name, description=desc))
        return services
