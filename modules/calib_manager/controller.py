"""Calibration Manager business logic controller."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from core.db.crud_mixin import CRUDMixin
from core.db.manager import DatabaseManager
from core.db.models import CalibrationChange, CalibrationPage, CalibrationParameter
from core.generators.a2l_generator import A2LGenerator
from core.generators.dcm_generator import DCMGenerator
from core.parsers.a2l_parser import A2LData, A2LParser
from core.parsers.dcm_parser import DCMData, DCMParser

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
        self.current_dcm: DCMData | None = None
        self.current_page: str = "default"
        self._ensure_default_page()

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

        # Collect existing names for current page in one query
        existing_names = set(
            row.name
            for row in CalibrationParameter.select(CalibrationParameter.name).where(
                CalibrationParameter.calibration_page == self.current_page
            )
        )

        rows = []
        skipped = 0
        for char in self.current_a2l.characteristics:
            if char.name in existing_names:
                skipped += 1
                continue
            existing_names.add(char.name)
            rows.append(
                {
                    "name": char.name,
                    "calibration_page": self.current_page,
                    "data_type": char.type,
                    "default_value": char.lower_limit,
                    "min_value": char.lower_limit,
                    "max_value": char.upper_limit,
                    "unit": char.unit,
                    "description": char.description or char.long_identifier,
                    "source": "a2l",
                    "source_file": self.current_a2l.source_path,
                }
            )

        # Batch insert
        if rows:
            batch_size = 500
            for i in range(0, len(rows), batch_size):
                CalibrationParameter.insert_many(rows[i : i + batch_size]).execute()

        return len(rows), skipped

    # ── DCM file operations ──────────────────────────────────────────────────

    def load_dcm(self, file_path: Path) -> tuple[bool, list[str]]:
        """Parse a DCM file and store the result."""
        parser = DCMParser()
        result = parser.parse(file_path)
        if result.success:
            self.current_dcm = result.data
            return True, []
        return False, result.errors

    def import_dcm_values(self) -> tuple[int, int, int]:
        """Import DCM values into existing DB parameters by name matching.

        Returns (matched, updated, not_found).
        matched: params found in both DCM and DB
        updated: params whose default_value was actually changed
        not_found: DCM params that have no DB match on current page
        """
        if self.current_dcm is None:
            return 0, 0, 0

        # Build name→param lookup for current page
        db_params: dict[str, CalibrationParameter] = {}
        for p in CalibrationParameter.select().where(CalibrationParameter.calibration_page == self.current_page):
            db_params[p.name] = p

        matched = updated = not_found = 0
        for char in self.current_dcm.characteristics:
            if char.name not in db_params:
                not_found += 1
                continue
            matched += 1
            param = db_params[char.name]
            # Update block_type and raw_block for roundtrip support
            needs_save = False
            if char.block_type and param.block_type != char.block_type:
                param.block_type = char.block_type
                needs_save = True
            if char.raw_block and param.raw_block != char.raw_block:
                param.raw_block = char.raw_block
                needs_save = True
            if char.value is not None:
                old_value = param.default_value
                if old_value != char.value:
                    param.default_value = char.value
                    needs_save = True
                    CalibrationChange.create(
                        param=param,
                        old_value=old_value,
                        new_value=char.value,
                        changed_by="dcm_import",
                        reason=f"DCM import value = {char.value}",
                    )
                    updated += 1
            if needs_save:
                param.save()

        return matched, updated, not_found

    def import_dcm_as_new(self) -> tuple[int, int]:
        """Import DCM parameters as new DB records (independent of A2L).

        Returns (imported, skipped).
        """
        if self.current_dcm is None:
            return 0, 0

        existing_names = set(
            row.name
            for row in CalibrationParameter.select(CalibrationParameter.name).where(
                CalibrationParameter.calibration_page == self.current_page
            )
        )

        rows = []
        skipped = 0
        for char in self.current_dcm.characteristics:
            if char.name in existing_names:
                skipped += 1
                continue
            existing_names.add(char.name)
            rows.append(
                {
                    "name": char.name,
                    "calibration_page": self.current_page,
                    "data_type": "VALUE",
                    "default_value": char.value if char.value is not None else 0.0,
                    "min_value": char.lower_limit,
                    "max_value": char.upper_limit,
                    "unit": char.unit,
                    "description": char.description or char.name,
                    "source": "dcm",
                    "source_file": self.current_dcm.source_path,
                    "block_type": char.block_type,
                    "raw_block": char.raw_block or None,
                }
            )

        if rows:
            batch_size = 500
            for i in range(0, len(rows), batch_size):
                CalibrationParameter.insert_many(rows[i : i + batch_size]).execute()

        return len(rows), skipped

    def export_dcm(self, output_path: Path) -> tuple[bool, list[str]]:
        """Export current page parameters to a DCM file."""
        try:
            params = []
            raw_blocks = {}
            for p in self.get_params():
                params.append(
                    {
                        "name": p.name,
                        "description": p.description or p.name,
                        "default_value": p.default_value,
                        "min_value": p.min_value,
                        "max_value": p.max_value,
                        "unit": p.unit or "",
                        "block_type": p.block_type or "",
                    }
                )
                if p.raw_block:
                    raw_blocks[p.name] = p.raw_block
            generator = DCMGenerator()
            result = generator.generate(params, output_path, raw_blocks=raw_blocks)
            if result.success:
                return True, []
            return False, result.errors
        except Exception as exc:
            logger.error("Failed to export DCM: %s", exc)
            return False, [str(exc)]

    # ── Page management ───────────────────────────────────────────────────

    def list_pages(self) -> list[str]:
        """Return all calibration page names."""
        pages = [p.name for p in CalibrationPage.select(CalibrationPage.name)]
        if not pages:
            self._ensure_default_page()
            pages = ["default"]
        return sorted(pages)

    def create_page(self, name: str) -> bool:
        """Create a new empty calibration page."""
        if not name:
            return False
        if CalibrationPage.select().where(CalibrationPage.name == name).exists():
            return False
        CalibrationPage.create(name=name)
        return True

    def delete_page(self, name: str) -> tuple[bool, str]:
        """Delete a calibration page and all its parameters."""
        if name == "default":
            return False, "不能删除 default 页面"
        count = CalibrationParameter.delete().where(CalibrationParameter.calibration_page == name).execute()
        CalibrationPage.delete().where(CalibrationPage.name == name).execute()
        if self.current_page == name:
            self.current_page = "default"
        return True, f"已删除 {count} 条参数"

    def set_current_page(self, page: str):
        """Switch current page."""
        self.current_page = page

    def get_current_page(self) -> str:
        """Return current page name."""
        return self.current_page

    def _ensure_default_page(self):
        """Ensure 'default' page exists in CalibrationPage table."""
        if not CalibrationPage.select().where(CalibrationPage.name == "default").exists():
            CalibrationPage.create(name="default")

    # ── Parameter CRUD ─────────────────────────────────────────────────────

    def get_params(self, group: str | None = None) -> list[CalibrationParameter]:
        query = CalibrationParameter.select().where(CalibrationParameter.calibration_page == self.current_page)
        if group:
            query = query.where(CalibrationParameter.group_name == group)
        return list(query)

    def get_param_by_name(self, name: str) -> CalibrationParameter | None:
        try:
            return CalibrationParameter.get(
                (CalibrationParameter.name == name) & (CalibrationParameter.calibration_page == self.current_page)
            )
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
                "calibration_page": p.calibration_page or "default",
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
        """Get all unique group names for current page."""
        groups = set()
        for p in CalibrationParameter.select(CalibrationParameter.group_name).where(
            CalibrationParameter.calibration_page == self.current_page
        ):
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
        """Get all unique SWC names referenced by parameters in current page."""
        swcs = set()
        for p in CalibrationParameter.select(CalibrationParameter.swc_name).where(
            CalibrationParameter.calibration_page == self.current_page
        ):
            if p.swc_name:
                swcs.add(p.swc_name)
        return sorted(swcs)

    # ── Search ─────────────────────────────────────────────────────────────

    def search_params(self, keyword: str) -> list[CalibrationParameter]:
        """Search parameters by name or description."""
        keyword_lower = f"%{keyword.lower()}%"
        return list(
            CalibrationParameter.select().where(
                (CalibrationParameter.calibration_page == self.current_page)
                & ((CalibrationParameter.name**keyword_lower) | (CalibrationParameter.description**keyword_lower))
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
                "page": self.current_page,
                "parameters": [self.get_param_as_dict(p.id) for p in self.get_params()],
                "groups": self.get_groups(),
                "swcs": self.get_swcs(),
            }
            output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True, []
        except Exception as exc:
            return False, [str(exc)]

    def export_a2l_summary(self, output_path: Path) -> tuple[bool, list[str]]:
        """Export a simplified A2L-like text summary."""
        try:
            lines = ["* Calibration Parameter Summary", "* Generated by VCU DevKit", ""]
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
            r"(/begin\s+CHARACTERISTIC\s+)(.*?)(/end\s+CHARACTERISTIC)",
            re.DOTALL | re.IGNORECASE,
        )

        def _replace_block(match: re.Match) -> str:
            prefix = match.group(1)
            body = match.group(2)
            suffix = match.group(3)

            # Find the characteristic name from the body
            name_match = re.search(r"(\S+)", body.strip())
            if not name_match:
                return match.group(0)
            name = name_match.group(1)

            if name not in db_params:
                return match.group(0)

            vals = db_params[name]
            new_lower = self._fmt_val(vals["min_value"])
            new_upper = self._fmt_val(vals["max_value"])

            # Strategy 1: Replace limits in the header line
            # Header has: name "id" type addr layout max_diff conversion lower upper
            # The lower and upper are the 8th and 9th tokens after quoted string
            lines = body.split("\n")
            new_lines = []
            in_sub_block = 0

            for line in lines:
                stripped = line.strip()

                # Track nested blocks
                if re.match(r"/begin\s+", stripped, re.IGNORECASE):
                    in_sub_block += 1
                if re.match(r"/end\s+", stripped, re.IGNORECASE):
                    in_sub_block -= 1

                if in_sub_block > 0:
                    new_lines.append(line)
                    continue

                # Replace LOWER_LIMIT / UPPER_LIMIT sub-keys
                if re.match(r"\s*LOWER_LIMIT\s+", stripped, re.IGNORECASE):
                    new_lines.append(
                        re.sub(
                            r"(LOWER_LIMIT\s+)[\d\.\-\+eE]+",
                            rf"\g<1>{new_lower}",
                            line,
                            flags=re.IGNORECASE,
                        )
                    )
                    continue
                if re.match(r"\s*UPPER_LIMIT\s+", stripped, re.IGNORECASE):
                    new_lines.append(
                        re.sub(
                            r"(UPPER_LIMIT\s+)[\d\.\-\+eE]+",
                            rf"\g<1>{new_upper}",
                            line,
                            flags=re.IGNORECASE,
                        )
                    )
                    continue

                new_lines.append(line)

            new_body = "\n".join(new_lines)

            # Replace header limits: find the lower/upper values in the header
            # Header tokens (after quoted string): type addr layout max_diff conv lower upper
            # We replace the 7th and 8th numeric tokens after the name
            header_lower_upper_re = re.compile(
                r'("([^"]*)"'  # quoted string
                r"\s+\S+"  # type
                r"\s+\S+"  # address
                r"\s+\S+"  # layout
                r"\s+\S+"  # max_diff
                r"\s+\S+"  # conversion
                r"\s+)[\d\.\-\+eE]+"  # lower_limit
                r"(\s+)[\d\.\-\+eE]+",  # upper_limit
            )
            m = header_lower_upper_re.search(new_body)
            if m:
                new_body = new_body[: m.start()] + m.group(1) + new_lower + m.group(3) + new_upper + new_body[m.end() :]

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
                issues.append(
                    {
                        "type": "warning",
                        "rule": "CAL_NO_DESC",
                        "location": p.name,
                        "message": f"Parameter '{p.name}' has no description",
                    }
                )
            if p.min_value is not None and p.max_value is not None:
                if p.min_value > p.max_value:
                    issues.append(
                        {
                            "type": "error",
                            "rule": "CAL_RANGE_INVALID",
                            "location": p.name,
                            "message": f"Parameter '{p.name}' min ({p.min_value}) > max ({p.max_value})",
                        }
                    )
            if p.default_value is not None:
                if p.min_value is not None and p.default_value < p.min_value:
                    issues.append(
                        {
                            "type": "warning",
                            "rule": "CAL_DEFAULT_BELOW_MIN",
                            "location": p.name,
                            "message": f"Default value ({p.default_value}) below min ({p.min_value})",
                        }
                    )
                if p.max_value is not None and p.default_value > p.max_value:
                    issues.append(
                        {
                            "type": "warning",
                            "rule": "CAL_DEFAULT_ABOVE_MAX",
                            "location": p.name,
                            "message": f"Default value ({p.default_value}) above max ({p.max_value})",
                        }
                    )
            if not p.group_name:
                issues.append(
                    {
                        "type": "info",
                        "rule": "CAL_NO_GROUP",
                        "location": p.name,
                        "message": f"Parameter '{p.name}' is not assigned to a group",
                    }
                )
        return issues
