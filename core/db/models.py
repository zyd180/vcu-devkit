"""Database ORM models using Peewee."""

import json
from datetime import datetime

from peewee import (
    AutoField,
    BooleanField,
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

# Database instance — initialised by db.manager
db = SqliteDatabase(None)


class BaseModel(Model):
    class Meta:
        database = db


# ── Calibration ──────────────────────────────────────────────────────────────


class CalibrationPage(BaseModel):
    """Named calibration page (version/snapshot)."""

    id = AutoField()
    name = CharField(unique=True, max_length=128)
    created_at = DateTimeField(default=datetime.now)


class CalibrationParameter(BaseModel):
    """Calibration (标定) parameter definition."""

    id = AutoField()
    name = CharField(max_length=128)
    calibration_page = CharField(max_length=128, default="default")
    swc_name = CharField(max_length=128, null=True)
    group_name = CharField(max_length=128, null=True)
    data_type = CharField(max_length=32)
    default_value = FloatField(null=True)
    min_value = FloatField(null=True)
    max_value = FloatField(null=True)
    unit = CharField(max_length=32, null=True)
    description = TextField(null=True)
    source = CharField(default="manual", max_length=32)  # manual / model / a2l
    source_file = CharField(max_length=512, null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class CalibrationChange(BaseModel):
    """Audit trail for calibration parameter changes."""

    id = AutoField()
    param = ForeignKeyField(CalibrationParameter, backref="changes")
    old_value = FloatField(null=True)
    new_value = FloatField(null=True)
    changed_by = CharField(max_length=64, null=True)
    reason = TextField(null=True)
    changed_at = DateTimeField(default=datetime.now)


# ── Diagnostics ──────────────────────────────────────────────────────────────


class DTCDefinition(BaseModel):
    """Diagnostic Trouble Code definition."""

    id = AutoField()
    dtc_code = CharField(unique=True, max_length=16)  # e.g. 0xD001
    description = TextField()
    severity = CharField(max_length=16, null=True)  # warning / critical / fault
    snapshot_ids = TextField(null=True)  # JSON array
    debounce_strategy = CharField(max_length=64, null=True)
    debounce_counter = IntegerField(null=True)
    debounce_time_ms = IntegerField(null=True)
    obd_related = BooleanField(default=False)
    custom_spec_source = CharField(max_length=512, null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    def get_snapshot_ids(self) -> list[str]:
        if self.snapshot_ids:
            return json.loads(self.snapshot_ids)
        return []

    def set_snapshot_ids(self, ids: list[str]):
        self.snapshot_ids = json.dumps(ids)


class DiagService(BaseModel):
    """UDS diagnostic service definition."""

    id = AutoField()
    sid = CharField(max_length=8)  # e.g. 0x19
    service_name = CharField(max_length=128)
    sub_functions = TextField(null=True)  # JSON array
    security_level = CharField(default="default", max_length=32)
    nrc_list = TextField(null=True)  # JSON array
    description = TextField(null=True)
    enabled = BooleanField(default=True)

    def get_sub_functions(self) -> list[str]:
        if self.sub_functions:
            return json.loads(self.sub_functions)
        return []

    def set_sub_functions(self, sfs: list[str]):
        self.sub_functions = json.dumps(sfs)

    def get_nrc_list(self) -> list[str]:
        if self.nrc_list:
            return json.loads(self.nrc_list)
        return []

    def set_nrc_list(self, nrcs: list[str]):
        self.nrc_list = json.dumps(nrcs)


# ── Requirements & Traceability ──────────────────────────────────────────────


class Requirement(BaseModel):
    """Requirement from external source (飞书多维表格 / Excel)."""

    id = AutoField()
    req_id = CharField(unique=True, max_length=64)
    title = CharField(max_length=256)
    description = TextField(null=True)
    source = CharField(default="feishu", max_length=32)
    source_id = CharField(max_length=128, null=True)
    module_name = CharField(max_length=128, null=True)
    status = CharField(default="active", max_length=32)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class TraceabilityLink(BaseModel):
    """Link between requirement and implementation/test artifact."""

    id = AutoField()
    req = ForeignKeyField(Requirement, backref="links")
    link_type = CharField(max_length=32)  # swc / test_case / signal / dtc
    link_target = CharField(max_length=256)
    link_target_id = CharField(max_length=128, null=True)
    auto_matched = BooleanField(default=False)
    verified = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)


# ── Project config & file versioning ─────────────────────────────────────────


class ProjectConfig(BaseModel):
    """Key-value project configuration."""

    id = AutoField()
    key = CharField(unique=True, max_length=128)
    value = TextField()
    category = CharField(max_length=64, null=True)
    description = TextField(null=True)


class FileVersion(BaseModel):
    """Version snapshot of a managed file (DBC/ARXML/A2L/ODX)."""

    id = AutoField()
    file_path = CharField(max_length=512)
    file_type = CharField(max_length=16)
    version_tag = CharField(max_length=64, null=True)
    checksum = CharField(max_length=64)
    snapshot_json = TextField(null=True)
    git_commit = CharField(max_length=64, null=True)
    created_at = DateTimeField(default=datetime.now)


# All tables for easy iteration
ALL_MODELS = [
    CalibrationPage,
    CalibrationParameter,
    CalibrationChange,
    DTCDefinition,
    DiagService,
    Requirement,
    TraceabilityLink,
    ProjectConfig,
    FileVersion,
]
