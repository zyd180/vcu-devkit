"""Database lifecycle manager."""

from __future__ import annotations

from pathlib import Path

from core.db.models import db, ALL_MODELS


class DatabaseManager:
    """Initialise, open, and manage the SQLite database."""

    # Class-level tracking to avoid re-initializing the same database
    _initialized_paths: set[str] = set()

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = Path.home() / ".vcu-devkit" / "vcu-devkit.db"
        self.db_path = Path(db_path)
        self._initialised = str(self.db_path) in self._initialized_paths

    def init(self):
        """Create database file and tables if they don't exist (idempotent)."""
        path_key = str(self.db_path)
        if path_key in self._initialized_paths:
            self._initialised = True
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db.init(path_key)
        db.connect(reuse_if_open=True)
        db.create_tables(ALL_MODELS, safe=True)
        self._auto_migrate()
        self._initialized_paths.add(path_key)
        self._initialised = True

    def _auto_migrate(self):
        """Auto-migrate schema changes for existing databases."""
        try:
            db.execute_sql(
                "SELECT calibration_page FROM calibrationparameter LIMIT 1"
            )
        except Exception:
            db.execute_sql(
                "ALTER TABLE calibrationparameter "
                "ADD COLUMN calibration_page VARCHAR(128) DEFAULT 'default'"
            )
            db.execute_sql(
                "UPDATE calibrationparameter SET calibration_page = 'default' "
                "WHERE calibration_page IS NULL"
            )
        # Drop old single-column UNIQUE index on name, replace with composite
        self._migrate_name_unique_to_composite()

    def _migrate_name_unique_to_composite(self):
        """Replace UNIQUE(name) with UNIQUE(name, calibration_page).

        SQLite UNIQUE constraints created by table definition are auto-indexes
        that cannot be dropped with DROP INDEX. Must recreate the table.
        """
        try:
            # Check if old UNIQUE(name) auto-index exists
            has_old_unique = False
            for row in db.execute_sql("PRAGMA index_list(calibrationparameter)"):
                if not row[2]:  # not unique
                    continue
                cols = [
                    r[2] for r in
                    db.execute_sql(f"PRAGMA index_info({row[1]})")
                ]
                if cols == ["name"]:
                    has_old_unique = True
                    break

            if not has_old_unique:
                # No old constraint, just ensure composite index exists
                db.execute_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "calibrationparameter_name_calibration_page "
                    "ON calibrationparameter (name, calibration_page)"
                )
                return

            # Recreate table without UNIQUE on name, with composite index
            db.execute_sql("ALTER TABLE calibrationparameter RENAME TO _calparam_old")
            db.execute_sql(
                """CREATE TABLE calibrationparameter (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(128),
                    calibration_page VARCHAR(128) DEFAULT 'default',
                    swc_name VARCHAR(128),
                    group_name VARCHAR(128),
                    data_type VARCHAR(32),
                    default_value REAL,
                    min_value REAL,
                    max_value REAL,
                    unit VARCHAR(32),
                    description TEXT,
                    source VARCHAR(32) DEFAULT 'manual',
                    source_file VARCHAR(512),
                    created_at DATETIME,
                    updated_at DATETIME
                )"""
            )
            db.execute_sql(
                """INSERT INTO calibrationparameter
                   (id, name, calibration_page, swc_name, group_name, data_type,
                    default_value, min_value, max_value, unit, description,
                    source, source_file, created_at, updated_at)
                   SELECT id, name,
                          COALESCE(calibration_page, 'default'),
                          swc_name, group_name, data_type,
                          default_value, min_value, max_value, unit, description,
                          source, source_file, created_at, updated_at
                   FROM _calparam_old"""
            )
            db.execute_sql("DROP TABLE _calparam_old")
            db.execute_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "calibrationparameter_name_calibration_page "
                "ON calibrationparameter (name, calibration_page)"
            )
        except Exception:
            pass  # Best-effort migration

    def close(self):
        """Close the database connection."""
        if not db.is_closed():
            db.close()

    def is_ready(self) -> bool:
        return self._initialised and not db.is_closed()

    def reset(self):
        """Drop all tables and recreate (destroys data!)."""
        db.drop_tables(ALL_MODELS, safe=True)
        db.create_tables(ALL_MODELS, safe=True)

    # ── Convenience CRUD wrappers ────────────────────────────────────────

    # Calibration
    def add_calibration_param(self, **kwargs) -> "CalibrationParameter":
        from core.db.models import CalibrationParameter
        return CalibrationParameter.create(**kwargs)

    def get_calibration_params(self, group: str | None = None) -> list:
        from core.db.models import CalibrationParameter
        query = CalibrationParameter.select()
        if group:
            query = query.where(CalibrationParameter.group_name == group)
        return list(query)

    def update_calibration_param(self, param_id: int, changed_by: str, reason: str, **kwargs):
        from core.db.models import CalibrationParameter, CalibrationChange
        param = CalibrationParameter.get_by_id(param_id)
        old_value = param.default_value
        for k, v in kwargs.items():
            setattr(param, k, v)
        param.save()
        CalibrationChange.create(
            param=param,
            old_value=old_value,
            new_value=kwargs.get("default_value"),
            changed_by=changed_by,
            reason=reason,
        )

    # DTC
    def add_dtc(self, **kwargs) -> "DTCDefinition":
        from core.db.models import DTCDefinition
        return DTCDefinition.create(**kwargs)

    def get_dtcs(self, obd_only: bool = False) -> list:
        from core.db.models import DTCDefinition
        query = DTCDefinition.select()
        if obd_only:
            query = query.where(DTCDefinition.obd_related == True)
        return list(query)

    # Diag services
    def add_diag_service(self, **kwargs) -> "DiagService":
        from core.db.models import DiagService
        return DiagService.create(**kwargs)

    def get_diag_services(self, enabled_only: bool = True) -> list:
        from core.db.models import DiagService
        query = DiagService.select()
        if enabled_only:
            query = query.where(DiagService.enabled == True)
        return list(query)

    # Requirements
    def add_requirement(self, **kwargs) -> "Requirement":
        from core.db.models import Requirement
        return Requirement.create(**kwargs)

    def get_requirements(self, module: str | None = None) -> list:
        from core.db.models import Requirement
        query = Requirement.select()
        if module:
            query = query.where(Requirement.module_name == module)
        return list(query)

    def add_trace_link(self, req_id: int, link_type: str, link_target: str, auto: bool = False):
        from core.db.models import TraceabilityLink
        return TraceabilityLink.create(
            req=req_id,
            link_type=link_type,
            link_target=link_target,
            auto_matched=auto,
        )

    def get_trace_matrix(self) -> dict:
        """Return full traceability matrix as dict: req_id → links."""
        from core.db.models import Requirement, TraceabilityLink
        matrix = {}
        for req in Requirement.select():
            links = list(TraceabilityLink.select().where(TraceabilityLink.req == req))
            matrix[req.req_id] = {
                "title": req.title,
                "module": req.module_name,
                "links": [
                    {
                        "type": l.link_type,
                        "target": l.link_target,
                        "auto": l.auto_matched,
                        "verified": l.verified,
                    }
                    for l in links
                ],
            }
        return matrix

    # File versions
    def record_file_version(self, file_path: str, file_type: str, checksum: str, **kwargs):
        from core.db.models import FileVersion
        return FileVersion.create(
            file_path=file_path,
            file_type=file_type,
            checksum=checksum,
            **kwargs,
        )

    def get_file_versions(self, file_path: str) -> list:
        from core.db.models import FileVersion
        return list(
            FileVersion.select()
            .where(FileVersion.file_path == file_path)
            .order_by(FileVersion.created_at.desc())
        )
