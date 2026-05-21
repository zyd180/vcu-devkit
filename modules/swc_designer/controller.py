"""SWC Designer business logic controller."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from core.generators.arxml_generator import ARXMLGenerator
from core.generators.base import GenerateResult
from core.parsers.arxml_parser import (
    ARXMLData,
    ARXMLParser,
    AUTOSARVersion,
    ClientServerInterface,
    PortDef,
    PortDirection,
    RunnableDef,
    SenderReceiverInterface,
    SWCDef,
    arxml_data_to_dict,
)
from core.rules.engine import RuleEngine, RuleResult


class SWCDesignerController:
    """Orchestrate SWC Designer operations."""

    def __init__(self, target_tool: str = "davinci"):
        self.target_tool = target_tool
        self.parser = ARXMLParser(target_tool)
        self.rule_engine = RuleEngine()
        self.current_data: ARXMLData | None = None
        self.current_path: Path | None = None
        self.template_library: list[dict] = []
        self._load_default_templates()

    # ── File operations ──────────────────────────────────────────────────

    def load_arxml(self, file_path: Path) -> tuple[bool, list[str]]:
        result = self.parser.parse(file_path)
        if result.success:
            self.current_data = result.data
            self.current_path = file_path
            return True, []
        return False, result.errors

    def new_project(self, package_name: str = "VCU"):
        """Create a blank ARXML project."""
        self.current_data = ARXMLData(
            autosar_version=AUTOSARVersion.AUTOSAR_4_4,
            package_name=package_name,
            swcs=[],
            interfaces=[],
            data_types=[],
            compositions=[],
            source_path="<new>",
        )
        self.current_path = None

    def save_json(self, output_path: Path) -> tuple[bool, list[str]]:
        if self.current_data is None:
            return False, ["No data"]
        data = arxml_data_to_dict(self.current_data)
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True, []

    def save_arxml(self, output_path: Path) -> GenerateResult:
        """Export current data as ARXML."""
        if self.current_data is None:
            return GenerateResult(success=False, errors=["No data"])
        gen = ARXMLGenerator(self.target_tool)
        return gen.generate(self.current_data, output_path)

    # ── SWC CRUD ─────────────────────────────────────────────────────────

    def get_swcs(self) -> list[SWCDef]:
        if self.current_data is None:
            return []
        return self.current_data.swcs

    def get_swc_by_name(self, name: str) -> SWCDef | None:
        for swc in self.get_swcs():
            if swc.name == name:
                return swc
        return None

    def add_swc(self, swc: SWCDef) -> bool:
        if self.current_data is None:
            return False
        if any(s.name == swc.name for s in self.current_data.swcs):
            return False
        self.current_data.swcs.append(swc)
        return True

    def remove_swc(self, name: str) -> bool:
        if self.current_data is None:
            return False
        original = len(self.current_data.swcs)
        self.current_data.swcs = [s for s in self.current_data.swcs if s.name != name]
        return len(self.current_data.swcs) < original

    def create_swc_from_template(self, template_name: str, instance_name: str | None = None) -> SWCDef | None:
        """Create a new SWC from a template."""
        tpl = self.get_template(template_name)
        if tpl is None:
            return None
        swc = deepcopy(tpl)
        if instance_name:
            swc.name = instance_name
        return swc

    # ── Port CRUD ────────────────────────────────────────────────────────

    def get_ports(self, swc_name: str) -> list[PortDef]:
        swc = self.get_swc_by_name(swc_name)
        return swc.ports if swc else []

    def add_port(self, swc_name: str, port: PortDef) -> bool:
        swc = self.get_swc_by_name(swc_name)
        if swc is None:
            return False
        if any(p.name == port.name for p in swc.ports):
            return False
        swc.ports.append(port)
        return True

    def remove_port(self, swc_name: str, port_name: str) -> bool:
        swc = self.get_swc_by_name(swc_name)
        if swc is None:
            return False
        original = len(swc.ports)
        swc.ports = [p for p in swc.ports if p.name != port_name]
        return len(swc.ports) < original

    def update_port(self, swc_name: str, port_name: str, **kwargs) -> bool:
        swc = self.get_swc_by_name(swc_name)
        if swc is None:
            return False
        for port in swc.ports:
            if port.name == port_name:
                for k, v in kwargs.items():
                    if k == "direction":
                        v = PortDirection(v)
                    if hasattr(port, k):
                        setattr(port, k, v)
                return True
        return False

    # ── Runnable CRUD ────────────────────────────────────────────────────

    def get_runnables(self, swc_name: str) -> list[RunnableDef]:
        swc = self.get_swc_by_name(swc_name)
        return swc.runnables if swc else []

    def add_runnable(self, swc_name: str, runnable: RunnableDef) -> bool:
        swc = self.get_swc_by_name(swc_name)
        if swc is None:
            return False
        if any(r.name == runnable.name for r in swc.runnables):
            return False
        swc.runnables.append(runnable)
        return True

    def remove_runnable(self, swc_name: str, runnable_name: str) -> bool:
        swc = self.get_swc_by_name(swc_name)
        if swc is None:
            return False
        original = len(swc.runnables)
        swc.runnables = [r for r in swc.runnables if r.name != runnable_name]
        return len(swc.runnables) < original

    def update_runnable(self, swc_name: str, runnable_name: str, **kwargs) -> bool:
        swc = self.get_swc_by_name(swc_name)
        if swc is None:
            return False
        for run in swc.runnables:
            if run.name == runnable_name:
                for k, v in kwargs.items():
                    if hasattr(run, k):
                        setattr(run, k, v)
                return True
        return False

    # ── Interface access ─────────────────────────────────────────────────

    def get_interfaces(self) -> list[SenderReceiverInterface | ClientServerInterface]:
        if self.current_data is None:
            return []
        return self.current_data.interfaces

    def get_interface_names(self) -> list[str]:
        return [i.name for i in self.get_interfaces()]

    def get_interface_by_name(self, name: str) -> SenderReceiverInterface | ClientServerInterface | None:
        for iface in self.get_interfaces():
            if iface.name == name:
                return iface
        return None

    def add_interface(self, iface: SenderReceiverInterface | ClientServerInterface) -> bool:
        if self.current_data is None:
            return False
        if any(i.name == iface.name for i in self.current_data.interfaces):
            return False
        self.current_data.interfaces.append(iface)
        return True

    def remove_interface(self, name: str) -> bool:
        if self.current_data is None:
            return False
        original = len(self.current_data.interfaces)
        self.current_data.interfaces = [i for i in self.current_data.interfaces if i.name != name]
        return len(self.current_data.interfaces) < original

    def update_interface(self, name: str, new_iface: SenderReceiverInterface | ClientServerInterface) -> bool:
        if self.current_data is None:
            return False
        for i, iface in enumerate(self.current_data.interfaces):
            if iface.name == name:
                self.current_data.interfaces[i] = new_iface
                return True
        return False

    # ── Validation ───────────────────────────────────────────────────────

    def validate(self) -> list[RuleResult]:
        if self.current_data is None:
            return []
        return self.rule_engine.check_arxml(self.current_data)

    # ── Template library ─────────────────────────────────────────────────

    def _load_default_templates(self):
        """Load built-in VCU SWC templates."""
        self.template_library = _build_default_templates()

    def get_template(self, name: str) -> SWCDef | None:
        for tpl in self.template_library:
            if tpl.name == name:
                return deepcopy(tpl)
        return None

    def get_template_names(self) -> list[str]:
        return [tpl.name for tpl in self.template_library]

    def get_template_categories(self) -> dict[str, list[str]]:
        cats: dict[str, list[str]] = {}
        for tpl in self.template_library:
            cat = tpl.description.split("|")[0].strip() if "|" in tpl.description else "通用"
            cats.setdefault(cat, []).append(tpl.name)
        return cats


# ── Default VCU template definitions ─────────────────────────────────────────


def _build_default_templates() -> list[SWCDef]:
    return [
        SWCDef(
            name="TPL_PowerMgmt",
            category="ApplicationSoftwareComponent",
            description="电源管理|整车高压/低压电源状态管理、上下电控制",
            ports=[
                PortDef("PwrStatus_P", PortDirection.PROVIDED, "I_PwrStatus"),
                PortDef("BMS_Status_R", PortDirection.REQUIRED, "I_BMS_Status"),
                PortDef("VCU_Cmd_P", PortDirection.PROVIDED, "I_VCU_Cmd"),
            ],
            runnables=[
                RunnableDef("RE_PowerOn", period_ms=10),
                RunnableDef("RE_PowerOff", period_ms=10),
                RunnableDef("RE_FaultHandler", period_ms=None),
            ],
        ),
        SWCDef(
            name="TPL_DriveCtrl",
            category="ApplicationSoftwareComponent",
            description="驱动控制|扭矩请求、驱动模式管理、能量回收",
            ports=[
                PortDef("TorqueCmd_P", PortDirection.PROVIDED, "I_TorqueCmd"),
                PortDef("MotorStatus_R", PortDirection.REQUIRED, "I_MotorStatus"),
                PortDef("DrvMode_P", PortDirection.PROVIDED, "I_DrvMode"),
            ],
            runnables=[
                RunnableDef("RE_TorqueCalc", period_ms=10),
                RunnableDef("RE_DrvModeMgr", period_ms=20),
                RunnableDef("RE_RegenCtrl", period_ms=10),
            ],
        ),
        SWCDef(
            name="TPL_ThermalMgmt",
            category="ApplicationSoftwareComponent",
            description="热管理|冷却系统控制、温度监控、热保护策略",
            ports=[
                PortDef("ThermalStatus_P", PortDirection.PROVIDED, "I_ThermalStatus"),
                PortDef("TempSensor_R", PortDirection.REQUIRED, "I_TempSensor"),
                PortDef("CoolantCmd_P", PortDirection.PROVIDED, "I_CoolantCmd"),
            ],
            runnables=[
                RunnableDef("RE_TempMonitor", period_ms=100),
                RunnableDef("RE_CoolantCtrl", period_ms=100),
                RunnableDef("RE_ThermalProtect", period_ms=50),
            ],
        ),
        SWCDef(
            name="TPL_DiagMgmt",
            category="ApplicationSoftwareComponent",
            description="诊断管理|DTC管理、UDS服务处理、快照数据采集",
            ports=[
                PortDef("DiagStatus_P", PortDirection.PROVIDED, "I_DiagStatus"),
                PortDef("FaultInfo_R", PortDirection.REQUIRED, "I_FaultInfo"),
            ],
            runnables=[
                RunnableDef("RE_DTCManager", period_ms=100),
                RunnableDef("RE_UDSHandler", period_ms=None),
                RunnableDef("RE_SnapshotCapture", period_ms=None),
            ],
        ),
        SWCDef(
            name="TPL_CommMgmt",
            category="ApplicationSoftwareComponent",
            description="通信管理|CAN信号收发、网关路由、通信超时监控",
            ports=[
                PortDef("CommStatus_P", PortDirection.PROVIDED, "I_CommStatus"),
                PortDef("CanSignal_R", PortDirection.REQUIRED, "I_CanSignal"),
            ],
            runnables=[
                RunnableDef("RE_CanTx", period_ms=10),
                RunnableDef("RE_CanRx", period_ms=None),
                RunnableDef("RE_CommTimeout", period_ms=100),
            ],
        ),
    ]
