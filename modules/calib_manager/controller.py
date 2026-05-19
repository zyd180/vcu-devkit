"""Calibration Manager business logic controller."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from core.db.models import CalibrationParameter, CalibrationChange
from core.db.manager import DatabaseManager
from core.db.crud_mixin import CRUDMixin
from core.parsers.a2l_parser import A2LParser, A2LData, a2l_data_to_dict
from core.generators.a2l_generator import A2LGenerator

logger = logging.getLogger(__name__)


class CalibManagerController(CRUDMixin):
    """Orchestrate Calibration Manager operations."""

    model = CalibrationParameter

    def __init__(self, db_manager: DatabaseManager | None = None):
        self.db = db_manager or DatabaseManager()
        if not self.db.is_ready():
            self.db.init()
        self.a2l_parser = A2LParser()
        self.current_a2l: A2LData | None = None

    # ── A2L file operations ────────────────────────────────────────────────

    def load_a2l(self, file_path: Path) -> tuple[bool, list[str]]:
        result = self.a2l_parser.parse(file_path)
        if result.success:
            self.current_a2l = result.data
            return True, []
        return False, result.errors

    def import_a2l_to_db(self) -> tuple[int, int]:
        """Import characteristics from current A2L into DB. Returns (imported, skipped)."""
        if self.current_a2l is None:
            return 0, 0
        imported = 0
        skipped = 0
        for char in self.current_a2l.characteristics:
            existing = CalibrationParameter.select().where(
                CalibrationParameter.name == char.name
            ).first()
            if existing:
                skipped += 1
                continue
            self.db.add_calibration_param(
                name=char.name,
                data_type=char.type,
                default_value=char.lower_limit,
                min_value=char.lower_limit,
                max_value=char.upper_limit,
                unit=char.unit,
                description=char.description or char.long_identifier,
                source="a2l",
                source_file=self.current_a2l.source_path,
            )
            imported += 1
        return imported, skipped

    # ── Parameter CRUD ─────────────────────────────────────────────────────

    def get_params(self, group: str | None = None) -> list[CalibrationParameter]:
        return self.db.get_calibration_params(group=group)

    def get_param_by_name(self, name: str) -> CalibrationParameter | None:
        try:
            return CalibrationParameter.get(CalibrationParameter.name == name)
        except CalibrationParameter.DoesNotExist:
            return None

    def add_param(self, name: str, data_type: str = "VALUE", **kwargs) -> CalibrationParameter | None:
        try:
            return self.db.add_calibration_param(name=name, data_type=data_type, **kwargs)
        except Exception as exc:
            logger.error("Failed to add parameter %s: %s", name, exc)
            return None

    def update_param(self, param_id: int, changed_by: str = "user", reason: str = "", **kwargs) -> bool:
        try:
            self.db.update_calibration_param(param_id, changed_by=changed_by, reason=reason, **kwargs)
            return True
        except Exception as exc:
            logger.error("Failed to update parameter %d: %s", param_id, exc)
            return False

    def remove_param(self, param_id: int) -> bool:
        return self.delete_by_id(param_id)

    def get_param_as_dict(self, param_id: int) -> dict | None:
        try:
            p = CalibrationParameter.get_by_id(param_id)
            return {
                "id": p.id,
                "name": p.name,
                "swc_name": p.swc_name or "",
                "group_name": p.group_name or "",
                "data_type": p.data_type,
                "default_value": p.default_value,
                "min_value": p.min_value,
                "max_value": p.max_value,
                "unit": p.unit or "",
                "description": p.description or "",
                "source": p.source,
            }
        except CalibrationParameter.DoesNotExist:
            return None

    # ── Group management ───────────────────────────────────────────────────

    def get_groups(self) -> list[str]:
        """Get all unique group names."""
        groups = set()
        for p in CalibrationParameter.select(CalibrationParameter.group_name):
            if p.group_name:
                groups.add(p.group_name)
        return sorted(groups)

    def get_params_by_group(self) -> dict[str, list[CalibrationParameter]]:
        """Group parameters by group_name."""
        groups: dict[str, list[CalibrationParameter]] = {}
        for p in self.get_params():
            g = p.group_name or "未分组"
            groups.setdefault(g, []).append(p)
        return groups

    def get_swcs(self) -> list[str]:
        """Get all unique SWC names referenced by parameters."""
        swcs = set()
        for p in CalibrationParameter.select(CalibrationParameter.swc_name):
            if p.swc_name:
                swcs.add(p.swc_name)
        return sorted(swcs)

    # ── Search ─────────────────────────────────────────────────────────────

    def search_params(self, keyword: str) -> list[CalibrationParameter]:
        """Search parameters by name or description."""
        keyword_lower = f"%{keyword.lower()}%"
        return list(
            CalibrationParameter.select().where(
                (CalibrationParameter.name ** keyword_lower) |
                (CalibrationParameter.description ** keyword_lower)
            )
        )

    # ── Change history ─────────────────────────────────────────────────────

    def get_change_history(self, param_id: int) -> list[CalibrationChange]:
        try:
            param = CalibrationParameter.get_by_id(param_id)
            return list(
                CalibrationChange.select()
                .where(CalibrationChange.param == param)
                .order_by(CalibrationChange.changed_at.desc())
            )
        except CalibrationParameter.DoesNotExist:
            return []

    # ── Export ──────────────────────────────────────────────────────────────

    def export_json(self, output_path: Path) -> tuple[bool, list[str]]:
        try:
            data = {
                "parameters": [
                    self.get_param_as_dict(p.id) for p in self.get_params()
                ],
                "groups": self.get_groups(),
                "swcs": self.get_swcs(),
            }
            output_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            return True, []
        except Exception as exc:
            return False, [str(exc)]

    def export_a2l_summary(self, output_path: Path) -> tuple[bool, list[str]]:
        """Export a simplified A2L-like text summary."""
        try:
            lines = ["* Calibration Parameter Summary", f"* Generated by VCU DevKit", ""]
            for group_name, params in sorted(self.get_params_by_group().items()):
                lines.append(f"/* Group: {group_name} ({len(params)} params) */")
                for p in params:
                    lines.append(
                        f"/begin CHARACTERISTIC {p.name}"
                        f' "{p.description or p.name}"'
                        f" {p.data_type}"
                        f" 0x0"
                        f" Default_RL"
                        f" 0"
                        f" {p.min_value or 0}"
                        f" {p.upper_limit or p.max_value or 0}"
                    )
                    if p.unit:
                        lines.append(f'  UNIT "{p.unit}"')
                    lines.append("/end CHARACTERISTIC\n")
            output_path.write_text("\n".join(lines), encoding="utf-8")
            return True, []
        except Exception as exc:
            return False, [str(exc)]

    def export_a2l(self, output_path: Path) -> tuple[bool, list[str]]:
        """Export current A2L data to a ASAP2-compliant .a2l file.

        Requires that an A2L file has been loaded via load_a2l() first.
        Returns (success, errors).
        """
        if self.current_a2l is None:
            return False, ["No A2L data loaded — call load_a2l() first"]
        try:
            generator = A2LGenerator()
            result = generator.generate(self.current_a2l, output_path)
            if result.success:
                return True, []
            return False, result.errors
        except Exception as exc:
            logger.error("Failed to export A2L: %s", exc)
            return False, [str(exc)]

    # ── Validation ─────────────────────────────────────────────────────────

    def validate(self) -> list[dict]:
        issues: list[dict] = []
        for p in self.get_params():
            if not p.description:
                issues.append({
                    "type": "warning",
                    "rule": "CAL_NO_DESC",
                    "location": p.name,
                    "message": f"Parameter '{p.name}' has no description",
                })
            if p.min_value is not None and p.max_value is not None:
                if p.min_value > p.max_value:
                    issues.append({
                        "type": "error",
                        "rule": "CAL_RANGE_INVALID",
                        "location": p.name,
                        "message": f"Parameter '{p.name}' min ({p.min_value}) > max ({p.max_value})",
                    })
            if p.default_value is not None:
                if p.min_value is not None and p.default_value < p.min_value:
                    issues.append({
                        "type": "warning",
                        "rule": "CAL_DEFAULT_BELOW_MIN",
                        "location": p.name,
                        "message": f"Default value ({p.default_value}) below min ({p.min_value})",
                    })
                if p.max_value is not None and p.default_value > p.max_value:
                    issues.append({
                        "type": "warning",
                        "rule": "CAL_DEFAULT_ABOVE_MAX",
                        "location": p.name,
                        "message": f"Default value ({p.default_value}) above max ({p.max_value})",
                    })
            if not p.group_name:
                issues.append({
                    "type": "info",
                    "rule": "CAL_NO_GROUP",
                    "location": p.name,
                    "message": f"Parameter '{p.name}' is not assigned to a group",
                })
        return issues
