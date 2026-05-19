"""ARXML generator — produces AUTOSAR 4.x XML from in-memory data models.

Supports DaVinci and EB Tresos output modes (minor formatting/path differences).
"""

from __future__ import annotations

from pathlib import Path
from lxml import etree

from core.parsers.arxml_parser import (
    ARXMLData, SWCDef, PortDef, RunnableDef,
    SenderReceiverInterface, ClientServerInterface, DataElementDef,
    CompositionConnector,
    PortDirection, AUTOSARVersion,
    AUTOSAR_NS, NSMAP, NS,
)


class ARXMLGenerator:
    """Generate ARXML files from ARXMLData."""

    def __init__(self, target_tool: str = "davinci"):
        self.target_tool = target_tool

    def generate(self, data: ARXMLData, output_path: Path) -> tuple[bool, list[str]]:
        """Write ARXML to file. Returns (success, errors)."""
        try:
            tree = self._build_tree(data)
            xml_bytes = etree.tostring(
                tree, pretty_print=True, xml_declaration=True, encoding="UTF-8"
            )
            output_path.write_bytes(xml_bytes)
            return True, []
        except (OSError, etree.XMLSyntaxError, ValueError) as exc:
            return False, [str(exc)]

    def generate_string(self, data: ARXMLData) -> str:
        """Return ARXML as string (for preview/testing)."""
        tree = self._build_tree(data)
        return etree.tostring(tree, pretty_print=True, xml_declaration=False, encoding="unicode")

    # ── Tree construction ──────────────────────────────────────────────────

    def _build_tree(self, data: ARXMLData) -> etree._ElementTree:
        root = etree.Element("AUTOSAR", nsmap=NSMAP)
        root.set(
            f"{{http://www.w3.org/2001/XMLSchema-instance}}schemaLocation",
            f"http://autosar.org/schema/r4.0 AUTOSAR_{self._version_str(data.autosar_version)}.xsd",
        )

        # AR-PACKAGES
        ar_packages = etree.SubElement(root, f"{NS}AR-PACKAGES")
        ar_package = etree.SubElement(ar_packages, f"{NS}AR-PACKAGE")
        _sub_text(ar_package, "SHORT-NAME", data.package_name or "VCU_Package")

        # Elements
        elements = etree.SubElement(ar_package, f"{NS}ELEMENTS")

        # Interfaces
        for iface in data.interfaces:
            if isinstance(iface, SenderReceiverInterface):
                self._write_sr_interface(elements, iface)
            elif isinstance(iface, ClientServerInterface):
                self._write_cs_interface(elements, iface)

        # SWCs
        for swc in data.swcs:
            self._write_swc(elements, swc)

        # Compositions
        for comp in data.compositions:
            self._write_composition(elements, comp)

        return etree.ElementTree(root)

    # ── Interface writing ──────────────────────────────────────────────────

    def _write_sr_interface(self, parent: etree._Element, iface: SenderReceiverInterface):
        tag = f"{NS}SENDER-RECEIVER-INTERFACE"
        elem = etree.SubElement(parent, tag)
        _sub_text(elem, "SHORT-NAME", iface.name)
        if iface.data_elements:
            des = etree.SubElement(elem, f"{NS}DATA-ELEMENTS")
            for de in iface.data_elements:
                de_elem = etree.SubElement(des, f"{NS}DATA-ELEMENT-PROTOTYPE")
                _sub_text(de_elem, "SHORT-NAME", de.name)
                _sub_text(de_elem, "TYPE-TREF", f"/{de.type_ref}")

    def _write_cs_interface(self, parent: etree._Element, iface: ClientServerInterface):
        tag = f"{NS}CLIENT-SERVER-INTERFACE"
        elem = etree.SubElement(parent, tag)
        _sub_text(elem, "SHORT-NAME", iface.name)
        if iface.operations:
            ops = etree.SubElement(elem, f"{NS}OPERATIONS")
            for op_name in iface.operations:
                op = etree.SubElement(ops, f"{NS}OPERATION-PROTOTYPE")
                _sub_text(op, "SHORT-NAME", op_name)

    # ── SWC writing ────────────────────────────────────────────────────────

    def _write_swc(self, parent: etree._Element, swc: SWCDef):
        tag = self._swc_tag(swc.category)
        elem = etree.SubElement(parent, tag)
        _sub_text(elem, "SHORT-NAME", swc.name)
        if swc.description:
            desc = etree.SubElement(elem, f"{NS}DESC")
            _sub_text(desc, "L-2", swc.description)

        # Ports
        if swc.ports:
            ports_elem = etree.SubElement(elem, f"{NS}PORTS")
            for port in swc.ports:
                self._write_port(ports_elem, port)

        # Internal behaviors (runnables)
        if swc.runnables:
            ib = etree.SubElement(elem, f"{NS}INTERNAL-BEHAVIORS")
            swc_ib = etree.SubElement(ib, f"{NS}SWC-INTERNAL-BEHAVIOR")
            _sub_text(swc_ib, "SHORT-NAME", f"{swc.name}_InternalBehavior")

            runs_elem = etree.SubElement(swc_ib, f"{NS}RUNNABLES")
            for run in swc.runnables:
                self._write_runnable(runs_elem, run)

            # Timing events for periodic runnables
            events = etree.SubElement(swc_ib, f"{NS}EVENTS")
            for run in swc.runnables:
                if run.period_ms is not None:
                    te = etree.SubElement(events, f"{NS}TIMING-EVENT")
                    _sub_text(te, "SHORT-NAME", f"TE_{run.name}")
                    _sub_text(te, "PERIOD", str(run.period_ms / 1000.0))
                    _sub_text(te, "START-ON-EVENT-REF", f"/{run.name}")

    def _write_port(self, parent: etree._Element, port: PortDef):
        if port.direction == PortDirection.PROVIDED:
            tag = f"{NS}P-PORT-PROTOTYPE"
            iface_tag = "PROVIDED-INTERFACE-TREF"
        else:
            tag = f"{NS}R-PORT-PROTOTYPE"
            iface_tag = "REQUIRED-INTERFACE-TREF"

        elem = etree.SubElement(parent, tag)
        _sub_text(elem, "SHORT-NAME", port.name)
        _sub_text(elem, iface_tag, f"/{port.interface_ref}")

    def _write_runnable(self, parent: etree._Element, run: RunnableDef):
        elem = etree.SubElement(parent, f"{NS}RUNNABLE-ENTITY")
        _sub_text(elem, "SHORT-NAME", run.name)
        _sub_text(elem, "MINIMUM-START-INTERVAL", str(run.min_start_interval))

        if run.data_read_access:
            for ref in run.data_read_access:
                _sub_text(elem, "DATA-READ-ACCESSS-REFT", f"/{ref}")
        if run.data_write_access:
            for ref in run.data_write_access:
                _sub_text(elem, "DATA-WRITE-ACCESSS-REFT", f"/{ref}")
        if run.server_call_points:
            for ref in run.server_call_points:
                _sub_text(elem, "SERVER-CALL-POINT-REF", f"/{ref}")

    # ── Composition writing ────────────────────────────────────────────────

    def _write_composition(self, parent: etree._Element, comp):
        elem = etree.SubElement(parent, f"{NS}COMPOSITION-SW-COMPONENT-TYPE")
        _sub_text(elem, "SHORT-NAME", comp.name)

        if comp.components:
            comps_elem = etree.SubElement(elem, f"{NS}COMPONENTS")
            for comp_name in comp.components:
                proto = etree.SubElement(comps_elem, f"{NS}SW-COMPONENT-PROTOTYPE")
                _sub_text(proto, "SHORT-NAME", f"{comp_name}Inst")
                _sub_text(proto, "TYPE-TREF", f"/{comp_name}")

        # ── Connectors ─────────────────────────────────────────────────────
        if comp.connectors:
            conns_elem = etree.SubElement(elem, f"{NS}CONNECTORS")
            for conn in comp.connectors:
                if conn.connector_type == "assembly":
                    asm = etree.SubElement(conns_elem, f"{NS}ASSEMBLY-SW-CONNECTOR")
                    prov = etree.SubElement(asm, f"{NS}PROVIDER-IREF")
                    _sub_text(prov, "CONTEXT-COMPONENT-REF", f"/{conn.provider_component}")
                    _sub_text(prov, "TARGET-P-PORT-REF", f"/{conn.provider_port}")
                    req = etree.SubElement(asm, f"{NS}REQUESTER-IREF")
                    _sub_text(req, "CONTEXT-COMPONENT-REF", f"/{conn.requester_component}")
                    _sub_text(req, "TARGET-R-PORT-REF", f"/{conn.requester_port}")
                elif conn.connector_type == "delegation":
                    dlg = etree.SubElement(conns_elem, f"{NS}DELEGATION-SW-CONNECTOR")
                    inner = etree.SubElement(dlg, f"{NS}INNER-PORT-IREF")
                    _sub_text(inner, "CONTEXT-COMPONENT-REF", f"/{conn.provider_component}")
                    _sub_text(inner, "TARGET-P-PORT-REF", f"/{conn.provider_port}")
                    _sub_text(dlg, "OUTER-PORT-REF", f"/{conn.requester_port}")

    # ── Tool-specific helpers ──────────────────────────────────────────────

    def _swc_tag(self, category: str) -> str:
        """Map category to AUTOSAR XML tag."""
        if self.target_tool == "ebtresos":
            mapping = {
                "ApplicationSoftwareComponent": "APPLICATION-SW-COMPONENT-TYPE",
                "ServiceComponent": "SERVICE-SW-COMPONENT-TYPE",
                "ComplexDeviceDriver": "COMPLEX-DEVICE-DRIVER-SW-COMPONENT-TYPE",
            }
            tag = mapping.get(category, "APPLICATION-SW-COMPONENT-TYPE")
        else:
            tag = {
                "ApplicationSoftwareComponent": "APPLICATION-SW-COMPONENT-TYPE",
                "ServiceComponent": "SERVICE-SW-COMPONENT-TYPE",
                "ComplexDeviceDriver": "COMPLEX-DEVICE-DRIVER-SW-COMPONENT-TYPE",
                "SensorActuatorSoftwareComponent": "SENSOR-ACTUATOR-SW-COMPONENT-TYPE",
                "EcuAbstractionSoftwareComponent": "ECU-ABSTRACTION-SW-COMPONENT-TYPE",
            }.get(category, "APPLICATION-SW-COMPONENT-TYPE")
        return f"{NS}{tag}"

    @staticmethod
    def _version_str(version: AUTOSARVersion) -> str:
        return version.value.replace(".", "")


# ── Helper ───────────────────────────────────────────────────────────────────


def _sub_text(parent: etree._Element, tag: str, text: str):
    """Add a child element with text content."""
    child = etree.SubElement(parent, f"{NS}{tag}")
    child.text = text
