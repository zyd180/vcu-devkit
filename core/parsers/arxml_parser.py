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
    base_type: str = ""
    size: int = 0                  # bits
    encoding: str = ""             # e.g. "uint8", "sint16", "float32"
    min_value: float | None = None
    max_value: float | None = None


@dataclass
class BaseTypeDef:
    """SW-BASE-TYPE definition parsed from ARXML."""
    name: str
    category: str = ""
    size: int = 0                  # bits
    encoding: str = ""


@dataclass
class CompositionConnector:
    """Connector within a Composition (assembly or delegation)."""
    provider_component: str
    provider_port: str
    requester_component: str
    requester_port: str
    connector_type: str = "assembly"  # "assembly" or "delegation"


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
    components: list[str]                        # SWC names
    connectors: list[CompositionConnector] = field(default_factory=list)


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

    _STREAMING_THRESHOLD = 5 * 1024 * 1024  # 5 MB

    def parse(self, file_path: Path) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            return ParseResult(success=False, errors=[f"File not found: {path}"])
        try:
            # Use streaming parse for large files to reduce memory footprint
            if path.stat().st_size > self._STREAMING_THRESHOLD:
                return self._parse_streaming(path)
            tree = etree.parse(str(path), parser=_SAFE_PARSER)
            data = self._parse_tree(tree, str(path))
            return ParseResult(success=True, data=data, source_path=path)
        except (OSError, etree.XMLSyntaxError, ValueError) as exc:
            return ParseResult(success=False, errors=[str(exc)])

    def _parse_streaming(self, path: Path) -> ParseResult:
        """Stream-parse a large ARXML file using iterparse.

        Builds the tree incrementally, processes it, then frees memory.
        """
        try:
            context = etree.iterparse(str(path), events=("end",), parser=_SAFE_PARSER)
            root = None
            for event, elem in context:
                if elem.getparent() is None:
                    root = elem
                    break
            if root is None:
                return ParseResult(success=False, errors=["Empty ARXML file"])
            tree = etree.ElementTree(root)
            data = self._parse_tree(tree, str(path))
            # Free memory
            root.clear()
            del context
            return ParseResult(success=True, data=data, source_path=path)
        except (OSError, etree.XMLSyntaxError, ValueError) as exc:
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

    def _extract_base_types(self, root: etree._Element) -> dict[str, BaseTypeDef]:
        """Parse all SW-BASE-TYPE elements and return a name-keyed lookup dict."""
        base_types: dict[str, BaseTypeDef] = {}
        for elem in root.iter(f"{self._ns}SW-BASE-TYPE"):
            name = self._text(elem, "SHORT-NAME", "")
            cat = self._text(elem, "CATEGORY", "")
            size_str = self._text(elem, "BASE-TYPE-SIZE", "0")
            try:
                size = int(size_str)
            except ValueError:
                size = 0
            encoding = cat.lower().replace("_", "") if cat else ""
            base_types[name] = BaseTypeDef(name=name, category=cat, size=size, encoding=encoding)
        return base_types

    def _extract_data_types(self, root: etree._Element) -> list[DataTypeDef]:
        base_types = self._extract_base_types(root)
        types: list[DataTypeDef] = []
        for elem in root.iter(f"{self._ns}APPLICATION-PRIMITIVE-DATA-TYPE"):
            name = self._text(elem, "SHORT-NAME", "")
            cat = self._text(elem, "CATEGORY", "")

            # Resolve base type from SW-DATA-DEF-PROPS / BASE-TYPE-REF
            base_type_name = ""
            base_type_size = 0
            base_type_encoding = ""
            base_type_ref_elem = elem.find(
                f"{self._ns}SW-DATA-DEF-PROPS/{self._ns}BASE-TYPE-REF"
            )
            if base_type_ref_elem is not None and base_type_ref_elem.text:
                raw_ref = base_type_ref_elem.text.strip()
                base_type_name = self._strip_path(raw_ref)
                bt = base_types.get(base_type_name)
                if bt:
                    base_type_size = bt.size
                    base_type_encoding = bt.encoding

            types.append(DataTypeDef(
                name=name,
                category=cat,
                base_type=base_type_name,
                size=base_type_size,
                encoding=base_type_encoding,
            ))
        return types

    def _extract_compositions(self, root: etree._Element) -> list[CompositionDef]:
        comps: list[CompositionDef] = []
        for elem in root.iter(f"{self._ns}COMPOSITION-SW-COMPONENT-TYPE"):
            name = self._text(elem, "SHORT-NAME", "")
            components = [
                self._strip_path(self._text(c, "TYPE-TREF", ""))
                for c in elem.iter(f"{self._ns}SW-COMPONENT-PROTOTYPE")
            ]
            connectors = self._extract_connectors(elem)
            comps.append(CompositionDef(name=name, components=components, connectors=connectors))
        return comps

    def _extract_connectors(self, comp_elem: etree._Element) -> list[CompositionConnector]:
        """Parse ASSEMBLY-SW-CONNECTOR and DELEGATION-SW-CONNECTOR elements."""
        connectors: list[CompositionConnector] = []

        # ── Assembly connectors ────────────────────────────────────────────
        for asm in comp_elem.iter(f"{self._ns}ASSEMBLY-SW-CONNECTOR"):
            provider_comp = ""
            provider_port = ""
            requester_comp = ""
            requester_port = ""

            # PROVIDER-IREF
            prov_iref = asm.find(f"{self._ns}PROVIDER-IREF")
            if prov_iref is not None:
                ctx = prov_iref.find(f"{self._ns}CONTEXT-COMPONENT-REF")
                if ctx is not None and ctx.text:
                    provider_comp = self._strip_path(ctx.text.strip())
                tgt = prov_iref.find(f"{self._ns}TARGET-P-PORT-REF")
                if tgt is not None and tgt.text:
                    provider_port = self._strip_path(tgt.text.strip())

            # REQUESTER-IREF
            req_iref = asm.find(f"{self._ns}REQUESTER-IREF")
            if req_iref is not None:
                ctx = req_iref.find(f"{self._ns}CONTEXT-COMPONENT-REF")
                if ctx is not None and ctx.text:
                    requester_comp = self._strip_path(ctx.text.strip())
                tgt = req_iref.find(f"{self._ns}TARGET-R-PORT-REF")
                if tgt is not None and tgt.text:
                    requester_port = self._strip_path(tgt.text.strip())

            connectors.append(CompositionConnector(
                provider_component=provider_comp,
                provider_port=provider_port,
                requester_component=requester_comp,
                requester_port=requester_port,
                connector_type="assembly",
            ))

        # ── Delegation connectors ──────────────────────────────────────────
        for dlg in comp_elem.iter(f"{self._ns}DELEGATION-SW-CONNECTOR"):
            provider_comp = ""
            provider_port = ""
            requester_comp = ""
            requester_port = ""

            # INNER-PORT-IREF  (the internal side, typically a P-Port)
            inner_iref = dlg.find(f"{self._ns}INNER-PORT-IREF")
            if inner_iref is not None:
                ctx = inner_iref.find(f"{self._ns}CONTEXT-COMPONENT-REF")
                if ctx is not None and ctx.text:
                    provider_comp = self._strip_path(ctx.text.strip())
                # Delegation inner side can target P-PORT or R-PORT
                tgt_p = inner_iref.find(f"{self._ns}TARGET-P-PORT-REF")
                tgt_r = inner_iref.find(f"{self._ns}TARGET-R-PORT-REF")
                if tgt_p is not None and tgt_p.text:
                    provider_port = self._strip_path(tgt_p.text.strip())
                elif tgt_r is not None and tgt_r.text:
                    provider_port = self._strip_path(tgt_r.text.strip())

            # OUTER-PORT-REF  (the external composition port)
            outer_ref = dlg.find(f"{self._ns}OUTER-PORT-REF")
            if outer_ref is not None and outer_ref.text:
                requester_port = self._strip_path(outer_ref.text.strip())
                # Delegation's outer port is on the composition itself
                requester_comp = "(composition)"

            connectors.append(CompositionConnector(
                provider_component=provider_comp,
                provider_port=provider_port,
                requester_component=requester_comp,
                requester_port=requester_port,
                connector_type="delegation",
            ))

        return connectors

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
            {"name": dt.name, "category": dt.category, "base_type": dt.base_type,
             "encoding": dt.encoding, "size": dt.size}
            for dt in data.data_types
        ],
        "compositions": [
            {"name": c.name, "components": c.components, "connectors": [
                {
                    "provider_component": cn.provider_component,
                    "provider_port": cn.provider_port,
                    "requester_component": cn.requester_component,
                    "requester_port": cn.requester_port,
                    "connector_type": cn.connector_type,
                }
                for cn in c.connectors
            ]}
            for c in data.compositions
        ],
    }
