"""Calibration Manager business logic controller."""

from __future__ import annotations

import json
import logging
import re
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

        # Collect existing names in one query
        existing_names = set(
            row.name
            for row in CalibrationParameter.select(CalibrationParameter.name)
        )

        rows = []
        skipped = 0
        for char in self.current_a2l.characteristics:
            if char.name in existing_names:
                skipped += 1
                continue
            existing_names.add(char.name)
            rows.append({
                "name": char.name,
                "data_type": char.type,
                "default_value": char.lower_limit,
                "min_value": char.lower_limit,
                "max_value": char.upper_limit,
                "unit": char.unit,
                "description": char.description or char.long_identifier,
                "source": "a2l",
                "source_file": self.current_a2l.source_path,
            })

        # Batch insert
        if rows:
            batch_size = 500
            for i in range(0, len(rows), batch_size):
                CalibrationParameter.insert_many(rows[i:i + batch_size]).execute()

        return len(rows), skipped

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

    def writeback_a2l(self, output_path: Path | None = None) -> tuple[bool, list[str]]:
        """Write modified calibration values back to the A2L file.

        Reads the original A2L file, updates CHARACTERISTIC limits/defaults
        with values from the DB, and writes the result.
        If output_path is None, overwrites the original file.
        Returns (success, errors).
        """
        if self.current_a2l is None:
            return False, ["未加载A2L文件"]
        source = self.current_a2l.source_path
        if not source or source == "<string>":
            return False, ["无法确定原始A2L文件路径"]
        source_path = Path(source)
        if not source_path.exists():
            return False, [f"原始A2L文件不存在: {source_path}"]

        try:
            content = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return False, [f"读取A2L文件失败: {exc}"]

        # Build name→DB value lookup
        db_params: dict[str, dict] = {}
        for p in self.get_params():
            if p.source == "a2l":
                db_params[p.name] = {
                    "min_value": p.min_value,
                    "max_value": p.max_value,
                    "default_value": p.default_value,
                    "unit": p.unit or "",
                    "description": p.description or "",
                }

        if not db_params:
            return False, ["数据库中没有A2L来源的标定量"]

        # Replace each CHARACTERISTIC block
        block_re = re.compile(
            r'(/begin\s+CHARACTERISTIC\s+)(.*?)(/end\s+CHARACTERISTIC)',
            re.DOTALL | re.IGNORECASE,
        )

        def _replace_block(match: re.Match) -> str:
            prefix = match.group(1)
            body = match.group(2)
            suffix = match.group(3)

            # Find the characteristic name from the body
            name_match = re.search(r'(\S+)', body.strip())
            if not name_match:
                return match.group(0)
            name = name_match.group(1)

            if name not in db_params:
                return match.group(0)

            vals = db_params[name]
            new_lower = self._fmt_val(vals["min_value"])
            new_upper = self._fmt_val(vals["max_value"])
            new_default = self._fmt_val(vals["default_value"])

            # Strategy 1: Replace limits in the header line
            # Header has: name "id" type addr layout max_diff conversion lower upper
            # The lower and upper are the 8th and 9th tokens after quoted string
            lines = body.split('\n')
            new_lines = []
            header_tokens_done = 0
            in_sub_block = 0

            for line in lines:
                stripped = line.strip()

                # Track nested blocks
                if re.match(r'/begin\s+', stripped, re.IGNORECASE):
                    in_sub_block += 1
                if re.match(r'/end\s+', stripped, re.IGNORECASE):
                    in_sub_block -= 1

                if in_sub_block > 0:
                    new_lines.append(line)
                    continue

                # Replace LOWER_LIMIT / UPPER_LIMIT sub-keys
                if re.match(r'\s*LOWER_LIMIT\s+', stripped, re.IGNORECASE):
                    new_lines.append(re.sub(
                        r'(LOWER_LIMIT\s+)[\d\.\-\+eE]+',
                        rf'\g<1>{new_lower}',
                        line, flags=re.IGNORECASE,
                    ))
                    continue
                if re.match(r'\s*UPPER_LIMIT\s+', stripped, re.IGNORECASE):
                    new_lines.append(re.sub(
                        r'(UPPER_LIMIT\s+)[\d\.\-\+eE]+',
                        rf'\g<1>{new_upper}',
                        line, flags=re.IGNORECASE,
                    ))
                    continue

                new_lines.append(line)

            new_body = '\n'.join(new_lines)

            # Replace header limits: find the lower/upper values in the header
            # Header tokens (after quoted string): type addr layout max_diff conv lower upper
            # We replace the 7th and 8th numeric tokens after the name
            header_lower_upper_re = re.compile(
                r'("([^"]*)"'          # quoted string
                r'\s+\S+'              # type
                r'\s+\S+'              # address
                r'\s+\S+'              # layout
                r'\s+\S+'              # max_diff
                r'\s+\S+'              # conversion
                r'\s+)[\d\.\-\+eE]+'   # lower_limit
                r'(\s+)[\d\.\-\+eE]+', # upper_limit
            )
            m = header_lower_upper_re.search(new_body)
            if m:
                new_body = (
                    new_body[:m.start()] +
                    m.group(1) + new_lower +
                    m.group(3) + new_upper +
                    new_body[m.end():]
                )

            return prefix + new_body + suffix

        new_content = block_re.sub(_replace_block, content)

        # Write output
        out = output_path or source_path
        try:
            out = Path(out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(new_content, encoding="utf-8")
            return True, []
        except OSError as exc:
            return False, [f"写入文件失败: {exc}"]

    @staticmethod
    def _fmt_val(value: float | None) -> str:
        if value is None:
            return "0"
        if value == int(value):
            return str(int(value))
        return f"{value:g}"

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
