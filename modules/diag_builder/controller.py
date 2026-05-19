"""Diagnostic Builder business logic controller."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from core.db.models import DTCDefinition, DiagService, db
from core.db.manager import DatabaseManager
from core.parsers.odx_parser import ODXParser

logger = logging.getLogger(__name__)


class DiagBuilderController:
    """Orchestrate Diagnostic Builder operations — DTC, UDS services, snapshots."""

    def __init__(self, db_manager: DatabaseManager | None = None):
        self.db = db_manager or DatabaseManager()
        if not self.db.is_ready():
            self.db.init()

    # ── DTC CRUD ───────────────────────────────────────────────────────────

    def get_dtcs(self, obd_only: bool = False) -> list[DTCDefinition]:
        return self.db.get_dtcs(obd_only=obd_only)

    def get_dtc_by_code(self, code: str) -> DTCDefinition | None:
        try:
            return DTCDefinition.get(DTCDefinition.dtc_code == code)
        except DTCDefinition.DoesNotExist:
            return None

    def add_dtc(self, dtc_code: str, description: str, **kwargs) -> DTCDefinition | None:
        try:
            return self.db.add_dtc(
                dtc_code=dtc_code, description=description, **kwargs
            )
        except Exception as exc:
            logger.error("Failed to add DTC %s: %s", dtc_code, exc)
            return None

    def update_dtc(self, dtc_id: int, **kwargs) -> bool:
        try:
            dtc = DTCDefinition.get_by_id(dtc_id)
            for k, v in kwargs.items():
                if hasattr(dtc, k):
                    setattr(dtc, k, v)
            dtc.save()
            return True
        except DTCDefinition.DoesNotExist:
            return False

    def remove_dtc(self, dtc_id: int) -> bool:
        try:
            dtc = DTCDefinition.get_by_id(dtc_id)
            dtc.delete_instance()
            return True
        except DTCDefinition.DoesNotExist:
            return False

    def get_dtc_as_dict(self, dtc_id: int) -> dict | None:
        try:
            dtc = DTCDefinition.get_by_id(dtc_id)
            return {
                "id": dtc.id,
                "dtc_code": dtc.dtc_code,
                "description": dtc.description,
                "severity": dtc.severity or "warning",
                "snapshot_ids": dtc.get_snapshot_ids(),
                "debounce_strategy": dtc.debounce_strategy or "",
                "debounce_counter": dtc.debounce_counter,
                "debounce_time_ms": dtc.debounce_time_ms,
                "obd_related": dtc.obd_related,
            }
        except DTCDefinition.DoesNotExist:
            return None

    def get_dtc_categories(self) -> dict[str, list[DTCDefinition]]:
        """Group DTCs by severity."""
        cats: dict[str, list[DTCDefinition]] = {}
        for dtc in self.get_dtcs():
            sev = dtc.severity or "未分类"
            cats.setdefault(sev, []).append(dtc)
        return cats

    # ── Bulk DTC import ────────────────────────────────────────────────────

    def import_dtcs_from_list(self, dtc_list: list[dict]) -> tuple[int, int]:
        """Import DTCs from a list of dicts. Returns (imported, skipped)."""
        imported = 0
        skipped = 0
        for item in dtc_list:
            code = item.get("dtc_code", "")
            if not code:
                skipped += 1
                continue
            if self.get_dtc_by_code(code):
                skipped += 1
                continue
            result = self.add_dtc(
                dtc_code=code,
                description=item.get("description", ""),
                severity=item.get("severity", "warning"),
                obd_related=item.get("obd_related", False),
                debounce_strategy=item.get("debounce_strategy"),
                debounce_counter=item.get("debounce_counter"),
                debounce_time_ms=item.get("debounce_time_ms"),
            )
            if result:
                imported += 1
            else:
                skipped += 1
        return imported, skipped

    # ── UDS Service CRUD ───────────────────────────────────────────────────

    def get_services(self, enabled_only: bool = False) -> list[DiagService]:
        return self.db.get_diag_services(enabled_only=enabled_only)

    def get_service_by_sid(self, sid: str) -> DiagService | None:
        try:
            return DiagService.get(DiagService.sid == sid)
        except DiagService.DoesNotExist:
            return None

    def add_service(self, sid: str, service_name: str, **kwargs) -> DiagService | None:
        try:
            return self.db.add_diag_service(
                sid=sid, service_name=service_name, **kwargs
            )
        except Exception as exc:
            logger.error("Failed to add service %s: %s", sid, exc)
            return None

    def update_service(self, service_id: int, **kwargs) -> bool:
        try:
            svc = DiagService.get_by_id(service_id)
            for k, v in kwargs.items():
                if hasattr(svc, k):
                    setattr(svc, k, v)
            svc.save()
            return True
        except DiagService.DoesNotExist:
            return False

    def remove_service(self, service_id: int) -> bool:
        try:
            svc = DiagService.get_by_id(service_id)
            svc.delete_instance()
            return True
        except DiagService.DoesNotExist:
            return False

    def get_service_as_dict(self, service_id: int) -> dict | None:
        try:
            svc = DiagService.get_by_id(service_id)
            return {
                "id": svc.id,
                "sid": svc.sid,
                "service_name": svc.service_name,
                "sub_functions": svc.get_sub_functions(),
                "security_level": svc.security_level,
                "nrc_list": svc.get_nrc_list(),
                "description": svc.description or "",
                "enabled": svc.enabled,
            }
        except DiagService.DoesNotExist:
            return None

    # ── Standard UDS service templates ─────────────────────────────────────

    @staticmethod
    def get_standard_services() -> list[dict]:
        """Return standard UDS service definitions."""
        return [
            {"sid": "0x10", "name": "DiagnosticSessionControl", "sub": ["0x01 Default", "0x02 Programming", "0x03 Extended"],
             "desc": "切换诊断会话"},
            {"sid": "0x11", "name": "ECUReset", "sub": ["0x01 HardReset", "0x02 KeyOffOnReset", "0x03 SoftReset"],
             "desc": "ECU复位"},
            {"sid": "0x14", "name": "ClearDiagnosticInformation", "sub": [],
             "desc": "清除DTC信息"},
            {"sid": "0x19", "name": "ReadDTCInformation", "sub": ["0x01 reportNumberOfDTCByStatusMask", "0x02 reportDTCByStatusMask", "0x04 reportDTCSnapshotRecord", "0x06 reportDTCExtDataRecord"],
             "desc": "读取DTC信息"},
            {"sid": "0x22", "name": "ReadDataByIdentifier", "sub": [],
             "desc": "按DID读取数据"},
            {"sid": "0x27", "name": "SecurityAccess", "sub": ["0x01 requestSeed (Level 1)", "0x02 sendKey (Level 1)", "0x03 requestSeed (Level 2)", "0x04 sendKey (Level 2)"],
             "desc": "安全访问"},
            {"sid": "0x2E", "name": "WriteDataByIdentifier", "sub": [],
             "desc": "按DID写入数据"},
            {"sid": "0x31", "name": "RoutineControl", "sub": ["0x01 startRoutine", "0x02 stopRoutine", "0x03 requestRoutineResults"],
             "desc": "例程控制"},
            {"sid": "0x34", "name": "RequestDownload", "sub": [],
             "desc": "请求下载"},
            {"sid": "0x36", "name": "TransferData", "sub": [],
             "desc": "数据传输"},
            {"sid": "0x37", "name": "RequestTransferExit", "sub": [],
             "desc": "请求传输退出"},
            {"sid": "0x3E", "name": "TesterPresent", "sub": ["0x00 suppressPositiveResponse"],
             "desc": "测试器在线"},
            {"sid": "0x85", "name": "ControlDTCSetting", "sub": ["0x01 on", "0x02 off"],
             "desc": "DTC设置控制"},
        ]

    # ── Snapshot / Freeze Frame ────────────────────────────────────────────

    def get_snapshot_configs(self) -> list[dict]:
        """Get all unique snapshot configurations from DTCs."""
        configs: dict[str, dict] = {}
        for dtc in self.get_dtcs():
            for sid in dtc.get_snapshot_ids():
                if sid not in configs:
                    configs[sid] = {"did": sid, "dtc_count": 0, "dtcs": []}
                configs[sid]["dtc_count"] += 1
                configs[sid]["dtcs"].append(dtc.dtc_code)
        return list(configs.values())

    # ── Validation ─────────────────────────────────────────────────────────

    def validate(self) -> list[dict]:
        """Run diagnostic consistency checks."""
        issues: list[dict] = []

        # Check for DTCs with no severity
        for dtc in self.get_dtcs():
            if not dtc.severity:
                issues.append({
                    "type": "warning",
                    "rule": "DIAG_NO_SEVERITY",
                    "location": dtc.dtc_code,
                    "message": f"DTC '{dtc.dtc_code}' has no severity assigned",
                })
            if not dtc.description.strip():
                issues.append({
                    "type": "error",
                    "rule": "DIAG_NO_DESC",
                    "location": dtc.dtc_code,
                    "message": f"DTC '{dtc.dtc_code}' has no description",
                })

        # Check for duplicate SID
        seen_sids: dict[str, str] = {}
        for svc in self.get_services():
            if svc.sid in seen_sids:
                issues.append({
                    "type": "error",
                    "rule": "DIAG_DUP_SID",
                    "location": svc.service_name,
                    "message": f"Duplicate SID {svc.sid}: '{svc.service_name}' and '{seen_sids[svc.sid]}'",
                })
            else:
                seen_sids[svc.sid] = svc.service_name

        # Check for services without sub-functions where expected
        sub_expected = {"0x10", "0x11", "0x19", "0x27", "0x31", "0x85"}
        for svc in self.get_services():
            if svc.sid in sub_expected and not svc.get_sub_functions():
                issues.append({
                    "type": "warning",
                    "rule": "DIAG_NO_SUBFUNC",
                    "location": svc.service_name,
                    "message": f"Service '{svc.service_name}' (SID {svc.sid}) typically requires sub-functions",
                })

        return issues

    # ── Export ──────────────────────────────────────────────────────────────

    def export_json(self, output_path: Path) -> tuple[bool, list[str]]:
        """Export full diagnostic config to JSON."""
        try:
            data = {
                "dtcs": [
                    self.get_dtc_as_dict(d.id) for d in self.get_dtcs()
                ],
                "services": [
                    self.get_service_as_dict(s.id) for s in self.get_services()
                ],
                "snapshot_configs": self.get_snapshot_configs(),
            }
            output_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            return True, []
        except Exception as exc:
            return False, [str(exc)]

    def import_json(self, input_path: Path) -> tuple[bool, list[str]]:
        """Import diagnostic config from JSON."""
        try:
            data = json.loads(input_path.read_text(encoding="utf-8"))
            imported_dtcs = 0
            imported_svcs = 0

            for dtc_data in data.get("dtcs", []):
                code = dtc_data.get("dtc_code", "")
                if code and not self.get_dtc_by_code(code):
                    self.add_dtc(
                        dtc_code=code,
                        description=dtc_data.get("description", ""),
                        severity=dtc_data.get("severity", "warning"),
                        obd_related=dtc_data.get("obd_related", False),
                        debounce_strategy=dtc_data.get("debounce_strategy"),
                        debounce_counter=dtc_data.get("debounce_counter"),
                        debounce_time_ms=dtc_data.get("debounce_time_ms"),
                    )
                    imported_dtcs += 1

            for svc_data in data.get("services", []):
                sid = svc_data.get("sid", "")
                if sid and not self.get_service_by_sid(sid):
                    svc = self.add_service(
                        sid=sid,
                        service_name=svc_data.get("service_name", ""),
                        security_level=svc_data.get("security_level", "default"),
                        description=svc_data.get("description", ""),
                        enabled=svc_data.get("enabled", True),
                    )
                    if svc:
                        svc.set_sub_functions(svc_data.get("sub_functions", []))
                        svc.set_nrc_list(svc_data.get("nrc_list", []))
                        svc.save()
                        imported_svcs += 1

            return True, [f"Imported {imported_dtcs} DTCs, {imported_svcs} services"]
        except Exception as exc:
            return False, [str(exc)]

    def import_odx(self, input_path: Path) -> tuple[bool, list[str]]:
        """Import DTCs and services from an ODX/CDD file."""
        try:
            parser = ODXParser()
            result = parser.parse(input_path)
            if not result.success:
                return False, result.errors

            odx_data = result.data
            imported_dtcs = 0
            imported_svcs = 0
            skipped_dtcs = 0
            skipped_svcs = 0

            for odx_dtc in odx_data.dtcs:
                if self.get_dtc_by_code(odx_dtc.code):
                    skipped_dtcs += 1
                    continue
                dtc = self.add_dtc(
                    dtc_code=odx_dtc.code,
                    description=odx_dtc.description,
                    severity=odx_dtc.severity,
                    obd_related=odx_dtc.obd_related,
                )
                if dtc:
                    if odx_dtc.snapshot_dids:
                        dtc.set_snapshot_ids(odx_dtc.snapshot_dids)
                        dtc.save()
                    imported_dtcs += 1
                else:
                    skipped_dtcs += 1

            for odx_svc in odx_data.services:
                if self.get_service_by_sid(odx_svc.sid):
                    skipped_svcs += 1
                    continue
                svc = self.add_service(
                    sid=odx_svc.sid,
                    service_name=odx_svc.name,
                    description=odx_svc.description,
                )
                if svc:
                    if odx_svc.sub_functions:
                        svc.set_sub_functions(odx_svc.sub_functions)
                        svc.save()
                    imported_svcs += 1
                else:
                    skipped_svcs += 1

            return True, [
                f"导入完成: {imported_dtcs} DTC, {imported_svcs} 服务 "
                f"(跳过 {skipped_dtcs} DTC, {skipped_svcs} 服务)"
            ]
        except Exception as exc:
            return False, [str(exc)]
