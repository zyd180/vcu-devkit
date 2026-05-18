"""ARXML parser for AUTOSAR 4.x software component descriptions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from lxml import etree

from core.parsers.base import BaseParser, ParseResult

# Safe parser: disable external entities and network access (XXE prevention)
_SAFE_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)


# ── Enums ────────────────────────────────────────────────────────────────────


class AUTOSARVersion(Enum):
    AUTOSAR_4_2 = "4.2"
    AUTOSAR_4_3 = "4.3"
    AUTOSAR_4_4 = "4.4"


class PortDirection(Enum):
    PROVIDED = "provided"
    REQUIRED = "required"


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class DataTypeDef:
    """AUTOSAR data type."""
    name: str
    category: str
    base_type: str
    size: int                      # bits
    encoding: str                  # e.g. "uint8", "sint16", "float32"
    min_value: float | None = None
    max_value: float | None = None


@dataclass
class DataElementDef:
    """Data element within an interface."""
    name: str
    type_ref: str
    description: str = ""


@dataclass
class SenderReceiverInterface:
    """Sender-Receiver port interface."""
    name: str
    data_elements: list[DataElementDef] = field(default_factory=list)


@dataclass
class ClientServerInterface:
    """Client-Server port interface."""
    name: str
    operations: list[str] = field(default_factory=list)


@dataclass
class PortDef:
    """Port on a component."""
    name: str
    direction: PortDirection
    interface_ref: str


@dataclass
class RunnableDef:
    """Runnable entity inside an SWC internal behaviour."""
    name: str
    period_ms: int | None              # None → event-triggered
    min_start_interval: int = 0
    data_read_access: list[str] = field(default_factory=list)
    data_write_access: list[str] = field(default_factory=list)
    server_call_points: list[str] = field(default_factory=list)


@dataclass
class SWCDef:
    """Software component definition."""
    name: str
    category: str
    description: str
    ports: list[PortDef] = field(default_factory=list)
    runnables: list[RunnableDef] = field(default_factory=list)
    internal_behaviors: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompositionDef:
    """SWC composition (aggregation of components)."""
    name: str
    components: list[str]      # SWC names
    connectors: list[dict]     # component-port connections


@dataclass
class ARXMLData:
    """Parsed ARXML file data."""
    autosar_version: AUTOSARVersion
    package_name: str
    swcs: list[SWCDef]
    interfaces: list[SenderReceiverInterface | ClientServerInterface]
    data_types: list[DataTypeDef]
    compositions: list[CompositionDef]
    source_path: str


# ── AUTOSAR XML namespaces ───────────────────────────────────────────────────

AUTOSAR_NS = "http://autosar.org/schema/r4.0"
NSMAP = {None: AUTOSAR_NS}
NS = f"{{{AUTOSAR_NS}}}"


# ── Tool adapters ────────────────────────────────────────────────────────────


class ToolAdapter:
    """Base adapter for tool-specific ARXML quirks."""

    def normalise_path(self, path: str) -> str:
        return path

    def swc_category(self, raw: str) -> str:
        return raw


class DaVinciAdapter(ToolAdapter):
    """DaVinci Configurator adapter."""
    pass


class EBTresosAdapter(ToolAdapter):
    """EB Tresos adapter — minor namespace differences."""

    def swc_category(self, raw: str) -> str:
        mapping = {
            "APPLICATION_SOFTWARE_COMPONENT_TYPE": "ApplicationSoftwareComponent",
            "SERVICE_COMPONENT_TYPE": "ServiceComponent",
        }
        return mapping.get(raw, raw)


# ── Parser ───────────────────────────────────────────────────────────────────


class ARXMLParser(BaseParser):
    """Parse AUTOSAR 4.x ARXML files (SWC description)."""

    def __init__(self, target_tool: str = "davinci"):
        self.target_tool = target_tool
        self._adapter: ToolAdapter = (
            DaVinciAdapter() if target_tool == "davinci" else EBTresosAdapter()
        )
        self._ns: str = NS  # default: with namespace

    def supported_extensions(self) -> list[str]:
        return [".arxml"]

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

    def validate(self, file_path: Path) -> list[str]:
        errors: list[str] = []
        try:
            tree = etree.parse(str(file_path), parser=_SAFE_PARSER)
            root = tree.getroot()
            if "AUTOSAR" not in root.tag:
                errors.append("Root element is not AUTOSAR")
        except Exception as exc:
            errors.append(f"Parse error: {exc}")
        return errors

    # ── Internal ─────────────────────────────────────────────────────────

    def _parse_tree(self, tree: etree._ElementTree, source: str) -> ARXMLData:
        root = tree.getroot()

        # Detect namespace: some ARXML files omit xmlns entirely
        if root.nsmap and None in root.nsmap:
            self._ns = NS  # {http://autosar.org/schema/r4.0}
        else:
            self._ns = ""  # no namespace

        autosar_version = self._detect_version(root)
        package_name = self._extract_package_name(root)

        swcs = self._extract_swcs(root)
        interfaces = self._extract_interfaces(root)
        data_types = self._extract_data_types(root)
        compositions = self._extract_compositions(root)

        return ARXMLData(
            autosar_version=autosar_version,
            package_name=package_name,
            swcs=swcs,
            interfaces=interfaces,
            data_types=data_types,
            compositions=compositions,
            source_path=source,
        )

    def _detect_version(self, root: etree._Element) -> AUTOSARVersion:
        # Try all possible attribute names for schemaLocation
        schema_loc = ""
        for attr_name, attr_val in root.attrib.items():
            if "schemaLocation" in attr_name:
                schema_loc = attr_val
                break
        if not schema_loc:
            # Fallback: check all attributes for version pattern
            for attr_val in root.attrib.values():
                if "4.4" in attr_val or "00044" in attr_val:
                    return AUTOSARVersion.AUTOSAR_4_4
                if "4.3" in attr_val or "00043" in attr_val:
                    return AUTOSARVersion.AUTOSAR_4_3
        if "4.4" in schema_loc or "00044" in schema_loc:
            return AUTOSARVersion.AUTOSAR_4_4
        if "4.3" in schema_loc or "00043" in schema_loc:
            return AUTOSARVersion.AUTOSAR_4_3
        return AUTOSARVersion.AUTOSAR_4_2

    def _extract_package_name(self, root: etree._Element) -> str:
        pkg = root.find(f"{self._ns}AR-PACKAGES/{self._ns}AR-PACKAGE/{self._ns}SHORT-NAME")
        return pkg.text if pkg is not None else ""

    def _extract_swcs(self, root: etree._Element) -> list[SWCDef]:
        swcs: list[SWCDef] = []
        for swc_elem in root.iter(f"{self._ns}APPLICATION-SW-COMPONENT-TYPE"):
            swcs.append(self._parse_swc(swc_elem, "ApplicationSoftwareComponent"))
        for swc_elem in root.iter(f"{self._ns}SERVICE-SW-COMPONENT-TYPE"):
            swcs.append(self._parse_swc(swc_elem, "ServiceComponent"))
        for swc_elem in root.iter(f"{self._ns}COMPLEX-DEVICE-DRIVER-SW-COMPONENT-TYPE"):
            swcs.append(self._parse_swc(swc_elem, "ComplexDeviceDriver"))
        return swcs

    def _parse_swc(self, elem: etree._Element, category: str) -> SWCDef:
        name = self._text(elem, "SHORT-NAME", "")
        desc = self._text(elem, "DESC/L-2", "")

        ports = self._extract_ports(elem)
        runnables = self._extract_runnables(elem)

        return SWCDef(
            name=name,
            category=category,
            description=desc,
            ports=ports,
            runnables=runnables,
        )

    def _extract_ports(self, swc_elem: etree._Element) -> list[PortDef]:
        ports: list[PortDef] = []
        for port_elem in swc_elem.iter(f"{self._ns}P-PORT-PROTOTYPE"):
            name = self._text(port_elem, "SHORT-NAME", "")
            iface = self._text(port_elem, "PROVIDED-INTERFACE-TREF", "")
            ports.append(PortDef(name=name, direction=PortDirection.PROVIDED, interface_ref=self._strip_path(iface)))
        for port_elem in swc_elem.iter(f"{self._ns}R-PORT-PROTOTYPE"):
            name = self._text(port_elem, "SHORT-NAME", "")
            iface = self._text(port_elem, "REQUIRED-INTERFACE-TREF", "")
            ports.append(PortDef(name=name, direction=PortDirection.REQUIRED, interface_ref=self._strip_path(iface)))
        return ports

    def _extract_runnables(self, swc_elem: etree._Element) -> list[RunnableDef]:
        runnables: list[RunnableDef] = []
        for run_elem in swc_elem.iter(f"{self._ns}RUNNABLE-ENTITY"):
            name = self._text(run_elem, "SHORT-NAME", "")

            # Period from timing event
            period_ms: int | None = None
            for te in swc_elem.iter(f"{self._ns}TIMING-EVENT"):
                period_str = self._text(te, "PERIOD", "")
                if period_str:
                    try:
                        period_ms = int(float(period_str) * 1000)
                    except ValueError:
                        pass

            reads = [self._strip_path(e.text or "") for e in run_elem.iter(f"{self._ns}DATA-READ-ACCESSS-REFT")]
            writes = [self._strip_path(e.text or "") for e in run_elem.iter(f"{self._ns}DATA-WRITE-ACCESSS-REFT")]
            calls = [self._strip_path(e.text or "") for e in run_elem.iter(f"{self._ns}SERVER-CALL-POINT-REF")]

            runnables.append(RunnableDef(
                name=name,
                period_ms=period_ms,
                data_read_access=reads,
                data_write_access=writes,
                server_call_points=calls,
            ))
        return runnables

    def _extract_interfaces(self, root: etree._Element) -> list[SenderReceiverInterface | ClientServerInterface]:
        ifaces: list[SenderReceiverInterface | ClientServerInterface] = []
        for elem in root.iter(f"{self._ns}SENDER-RECEIVER-INTERFACE"):
            name = self._text(elem, "SHORT-NAME", "")
            elements = []
            for de in elem.iter(f"{self._ns}DATA-ELEMENT-PROTOTYPE"):
                de_name = self._text(de, "SHORT-NAME", "")
                type_ref = self._strip_path(self._text(de, "TYPE-TREF", ""))
                elements.append(DataElementDef(name=de_name, type_ref=type_ref))
            ifaces.append(SenderReceiverInterface(name=name, data_elements=elements))
        for elem in root.iter(f"{self._ns}CLIENT-SERVER-INTERFACE"):
            name = self._text(elem, "SHORT-NAME", "")
            ops = [self._text(op, "SHORT-NAME", "") for op in elem.iter(f"{self._ns}OPERATION-PROTOTYPE")]
            ifaces.append(ClientServerInterface(name=name, operations=ops))
        return ifaces

    def _extract_data_types(self, root: etree._Element) -> list[DataTypeDef]:
        types: list[DataTypeDef] = []
        for elem in root.iter(f"{self._ns}APPLICATION-PRIMITIVE-DATA-TYPE"):
            name = self._text(elem, "SHORT-NAME", "")
            cat = self._text(elem, "CATEGORY", "")
            types.append(DataTypeDef(name=name, category=cat, base_type="", size=0, encoding=""))
        return types

    def _extract_compositions(self, root: etree._Element) -> list[CompositionDef]:
        comps: list[CompositionDef] = []
        for elem in root.iter(f"{self._ns}COMPOSITION-SW-COMPONENT-TYPE"):
            name = self._text(elem, "SHORT-NAME", "")
            components = [
                self._strip_path(self._text(c, "TYPE-TREF", ""))
                for c in elem.iter(f"{self._ns}SW-COMPONENT-PROTOTYPE")
            ]
            comps.append(CompositionDef(name=name, components=components, connectors=[]))
        return comps

    # ── Helpers ──────────────────────────────────────────────────────────

    def _text(self, elem: etree._Element, tag: str, default: str = "") -> str:
        """Find tag (relative path) and return text."""
        parts = tag.split("/")
        current = elem
        for part in parts:
            child = current.find(f"{self._ns}{part}")
            if child is None:
                return default
            current = child
        return (current.text or "").strip()

    @staticmethod
    def _strip_path(ref: str) -> str:
        """Strip AUTOSAR path prefix, return last segment."""
        if "/" in ref:
            return ref.rsplit("/", 1)[-1]
        return ref


# ── Serialisation ────────────────────────────────────────────────────────────


def arxml_data_to_dict(data: ARXMLData) -> dict:
    """Convert ARXMLData to JSON-serialisable dict."""
    def _port(p: PortDef) -> dict:
        return {"name": p.name, "direction": p.direction.value, "interface_ref": p.interface_ref}

    def _runnable(r: RunnableDef) -> dict:
        return {
            "name": r.name,
            "period_ms": r.period_ms,
            "data_read_access": r.data_read_access,
            "data_write_access": r.data_write_access,
            "server_call_points": r.server_call_points,
        }

    def _swc(s: SWCDef) -> dict:
        return {
            "name": s.name,
            "category": s.category,
            "description": s.description,
            "ports": [_port(p) for p in s.ports],
            "runnables": [_runnable(r) for r in s.runnables],
        }

    def _iface(i: SenderReceiverInterface | ClientServerInterface) -> dict:
        if isinstance(i, SenderReceiverInterface):
            return {
                "type": "sender_receiver",
                "name": i.name,
                "data_elements": [{"name": de.name, "type_ref": de.type_ref} for de in i.data_elements],
            }
        return {"type": "client_server", "name": i.name, "operations": i.operations}

    return {
        "autosar_version": data.autosar_version.value,
        "package_name": data.package_name,
        "source_path": data.source_path,
        "swcs": [_swc(s) for s in data.swcs],
        "interfaces": [_iface(i) for i in data.interfaces],
        "data_types": [
            {"name": dt.name, "category": dt.category, "encoding": dt.encoding, "size": dt.size}
            for dt in data.data_types
        ],
        "compositions": [
            {"name": c.name, "components": c.components, "connectors": c.connectors}
            for c in data.compositions
        ],
    }
