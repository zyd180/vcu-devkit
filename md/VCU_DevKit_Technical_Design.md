# VCU DevKit — 技术设计文档

> **版本**: v0.1 | **日期**: 2026-05-13 | **前置文档**: VCU_DevKit_Proposal.md

---

## 1. 项目结构

```
vcu-devkit/
├── main.py                          # 入口
├── requirements.txt                 # 依赖
├── pyproject.toml                   # 项目配置
│
├── core/                            # Core Engine
│   ├── __init__.py
│   ├── parsers/                     # 文件解析器
│   │   ├── __init__.py
│   │   ├── base.py                  # 解析器基类
│   │   ├── dbc_parser.py            # DBC解析
│   │   ├── arxml_parser.py          # ARXML解析
│   │   ├── odx_parser.py            # ODX/PDX解析
│   │   └── a2l_parser.py            # A2L解析
│   ├── generators/                  # 代码生成器
│   │   ├── __init__.py
│   │   ├── base.py                  # 生成器基类
│   │   ├── c_generator.py           # C代码生成
│   │   ├── capl_generator.py        # CAPL代码生成
│   │   ├── h_generator.py           # 头文件生成
│   │   └── arxml_generator.py       # ARXML生成
│   ├── diff/                        # Diff引擎
│   │   ├── __init__.py
│   │   ├── dbc_diff.py              # DBC版本对比
│   │   ├── arxml_diff.py            # ARXML版本对比
│   │   └── a2l_diff.py              # A2L版本对比
│   ├── rules/                       # 校验规则引擎
│   │   ├── __init__.py
│   │   ├── engine.py                # 规则引擎框架
│   │   ├── dbc_rules.py             # DBC校验规则
│   │   ├── arxml_rules.py           # ARXML校验规则
│   │   └── diag_rules.py            # 诊断校验规则
│   ├── templates/                   # Jinja2模板
│   │   ├── c/                       # C代码模板
│   │   ├── capl/                    # CAPL模板
│   │   ├── arxml/                   # ARXML模板
│   │   └── report/                  # 报告模板
│   ├── db/                          # 数据库
│   │   ├── __init__.py
│   │   ├── models.py                # ORM模型
│   │   ├── manager.py               # 数据库管理
│   │   └── migrations/              # 迁移脚本
│   ├── integrations/                # 外部集成
│   │   ├── __init__.py
│   │   ├── git_client.py            # Git集成
│   │   ├── feishu_client.py         # 飞书API集成
│   │   └── vector_adapter.py        # Vector工具链适配
│   └── utils/                       # 工具函数
│       ├── __init__.py
│       ├── endian.py                # 字节序处理
│       ├── signal_math.py           # 信号物理值换算
│       └── encoding.py              # 编码处理
│
├── modules/                         # 业务模块
│   ├── swc_designer/                # SWC Designer
│   │   ├── __init__.py
│   │   ├── models.py                # SWC数据模型
│   │   ├── controller.py            # 业务逻辑
│   │   ├── views/                   # UI视图
│   │   └── widgets/                 # 自定义控件
│   ├── can_builder/                 # CAN Builder
│   │   ├── __init__.py
│   │   ├── models.py                # CAN数据模型
│   │   ├── controller.py            # 业务逻辑
│   │   ├── views/                   # UI视图
│   │   └── widgets/                 # 自定义控件
│   ├── diag_builder/                # 诊断 Builder
│   │   ├── __init__.py
│   │   ├── models.py                # 诊断数据模型
│   │   ├── controller.py            # 业务逻辑
│   │   ├── views/                   # UI视图
│   │   └── widgets/                 # 自定义控件
│   ├── calib_manager/               # 标定 Manager
│   │   ├── __init__.py
│   │   ├── models.py                # 标定数据模型
│   │   ├── controller.py            # 业务逻辑
│   │   ├── views/                   # UI视图
│   │   └── widgets/                 # 自定义控件
│   ├── test_gen/                    # 测试 Gen
│   │   ├── __init__.py
│   │   ├── strategies/              # 测试策略
│   │   ├── controller.py            # 业务逻辑
│   │   ├── views/                   # UI视图
│   │   └── widgets/                 # 自定义控件
│   └── trace_matrix/                # 追溯 Matrix
│       ├── __init__.py
│       ├── models.py                # 追溯数据模型
│       ├── controller.py            # 业务逻辑
│       ├── views/                   # UI视图
│       └── widgets/                 # 自定义控件
│
├── ui/                              # 公共UI组件
│   ├── __init__.py
│   ├── main_window.py               # 主窗口
│   ├── sidebar.py                   # 侧边栏导航
│   ├── toolbar.py                   # 工具栏
│   ├── dialogs/                     # 通用对话框
│   ├── widgets/                     # 通用控件
│   │   ├── table_editor.py          # 可编辑表格
│   │   ├── tree_view.py             # 树形视图
│   │   ├── diff_viewer.py           # Diff查看器
│   │   ├── code_editor.py           # 代码编辑器
│   │   └── property_panel.py        # 属性面板
│   └── themes/                      # 主题
│       ├── light.qss
│       └── dark.qss
│
├── config/                          # 配置
│   ├── settings.py                  # 应用设置
│   ├── logging.py                   # 日志配置
│   └── defaults/                    # 默认配置
│       ├── dbc_rules.json           # DBC默认校验规则
│       ├── diag_services.json       # 通用诊断服务定义
│       ├── dtc_defaults.json        # 通用DTC默认定义
│       └── swc_templates/           # SWC模板库
│
└── tests/                           # 测试
    ├── test_parsers/
    ├── test_generators/
    ├── test_diff/
    ├── test_rules/
    └── test_modules/
```

---

## 2. Core Engine 设计

### 2.1 解析器基类

```python
# core/parsers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParseResult:
    """解析结果"""
    success: bool
    data: Any = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_path: Path | None = None


class BaseParser(ABC):
    """文件解析器基类"""

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """解析文件，返回结构化数据"""
        ...

    @abstractmethod
    def validate(self, file_path: Path) -> list[str]:
        """验证文件格式，返回错误列表"""
        ...

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """支持的文件扩展名"""
        ...
```

### 2.2 DBC解析器接口

```python
# core/parsers/dbc_parser.py

from dataclasses import dataclass, field


@dataclass
class SignalDef:
    """DBC信号定义"""
    name: str
    start_bit: int
    bit_length: int
    byte_order: str           # "little_endian" | "big_endian"
    value_type: str           # "unsigned" | "signed"
    factor: float
    offset: float
    minimum: float
    maximum: float
    unit: str
    comment: str
    receivers: list[str] = field(default_factory=list)
    value_descriptions: dict[int, str] = field(default_factory=dict)
    mux: dict | None = None   # 多路复用定义


@dataclass
class MessageDef:
    """DBC报文定义"""
    id: int                   # CAN ID (16进制)
    name: str
    dlc: int                  # 数据长度
    sender: str
    comment: str
    signals: list[SignalDef] = field(default_factory=list)


@dataclass
class DBCData:
    """DBC文件解析结果"""
    version: str
    messages: list[MessageDef]
    nodes: list[str]
    value_tables: dict[str, dict[int, str]]
    comments: dict[str, str]  # {"message_id:signal_name": "comment"}
    attributes: dict[str, Any]
    source_path: str


class DBCParser(BaseParser):
    """DBC文件解析器"""

    def parse(self, file_path: Path) -> ParseResult:
        """解析DBC文件"""
        ...

    def parse_string(self, content: str) -> ParseResult:
        """从字符串解析（用于内存中的DBC内容）"""
        ...

    def to_dict(self, data: DBCData) -> dict:
        """转为字典（用于JSON序列化）"""
        ...

    def from_dict(self, d: dict) -> DBCData:
        """从字典恢复"""
        ...
```

### 2.3 ARXML解析器接口

```python
# core/parsers/arxml_parser.py

from enum import Enum


class AUTOSARVersion(Enum):
    AUTOSAR_4_2 = "4.2"
    AUTOSAR_4_3 = "4.3"
    AUTOSAR_4_4 = "4.4"


class PortDirection(Enum):
    PROVIDED = "provided"      # P-Port (Server)
    REQUIRED = "required"      # R-Port (Client)


@dataclass
class DataTypeDef:
    """AUTOSAR数据类型"""
    name: str
    category: str             # "VALUE_TYPE" | "ARRAY_TYPE" | "STRUCT_TYPE"
    base_type: str
    size: int                 # bit
    encoding: str             # "uint8" | "sint16" | "float32" 等
    min_value: float | None = None
    max_value: float | None = None


@dataclass
class DataElementDef:
    """数据元素"""
    name: str
    type_ref: str             # 引用DataTypeDef.name
    description: str = ""


@dataclass
class SenderReceiverInterface:
    """Sender-Receiver接口"""
    name: str
    data_elements: list[DataElementDef]


@dataclass
class ClientServerInterface:
    """Client-Server接口"""
    name: str
    operations: list[str]


@dataclass
class PortDef:
    """Port定义"""
    name: str
    direction: PortDirection
    interface_ref: str        # 引用接口名


@dataclass
class RunnableDef:
    """Runnable定义"""
    name: str
    period_ms: int | None     # 周期调度，None=事件触发
    min_start_interval: int = 0
    data_read_access: list[str] = field(default_factory=list)
    data_write_access: list[str] = field(default_factory=list)
    server_call_points: list[str] = field(default_factory=list)


@dataclass
class SWCDef:
    """SWC定义"""
    name: str
    category: str             # "ApplicationSoftwareComponent" | "ServiceComponent" 等
    description: str
    ports: list[PortDef]
    runnables: list[RunnableDef]
    internal_behaviors: dict[str, Any] = field(default_factory=dict)


@dataclass
class ARXMLData:
    """ARXML解析结果"""
    autosar_version: AUTOSARVersion
    package_name: str
    swcs: list[SWCDef]
    interfaces: list[SenderReceiverInterface | ClientServerInterface]
    data_types: list[DataTypeDef]
    compositions: list[dict]  # SWC组合
    source_path: str


class ARXMLParser(BaseParser):
    """ARXML解析器（兼容DaVinci / EB Tresos）"""

    def __init__(self, target_tool: str = "davinci"):
        """
        target_tool: "davinci" | "eb_tresos"
        不同工具的ARXML结构有细微差异，通过适配层处理
        """
        self.target_tool = target_tool
        self._adapter = self._get_adapter(target_tool)

    def parse(self, file_path: Path) -> ParseResult:
        """解析ARXML文件"""
        ...

    def _get_adapter(self, tool: str):
        """获取目标工具的适配器"""
        if tool == "davinci":
            return DaVinciAdapter()
        elif tool == "eb_tresos":
            return EBTresosAdapter()
        raise ValueError(f"Unsupported tool: {tool}")


class DaVinciAdapter:
    """DaVinci Configurator ARXML适配"""
    # 处理DaVinci特有的ARXML命名空间和结构差异
    ...

class EBTresosAdapter:
    """EB Tresos ARXML适配"""
    # 处理EB Tresos特有的ARXML结构差异
    ...
```

### 2.4 Diff引擎接口

```python
# core/diff/dbc_diff.py

from enum import Enum


class DiffType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class SignalDiff:
    """信号级Diff"""
    signal_name: str
    diff_type: DiffType
    changes: dict[str, tuple[Any, Any]]  # {"factor": (0.5, 1.0), ...}
    message_name: str


@dataclass
class MessageDiff:
    """报文级Diff"""
    message_name: str
    diff_type: DiffType
    id: int
    signal_diffs: list[SignalDiff]


@dataclass
class DBCDiffResult:
    """DBC Diff结果"""
    old_version: str
    new_version: str
    message_diffs: list[MessageDiff]
    added_messages: list[str]
    removed_messages: list[str]
    summary: dict[str, int]  # {"added": 3, "removed": 1, "modified": 5}


class DBCDiffEngine:
    """DBC版本对比引擎"""

    def compare(self, old: DBCData, new: DBCData) -> DBCDiffResult:
        """对比两个DBC版本"""
        ...

    def generate_impact_report(self, diff: DBCDiffResult) -> dict:
        """生成变更影响分析报告"""
        ...

    def export_diff_report(self, diff: DBCDiffResult, output_path: Path, fmt: str = "xlsx"):
        """导出Diff报告（xlsx/html）"""
        ...
```

### 2.5 代码生成器接口

```python
# core/generators/base.py

from pathlib import Path


@dataclass
class GenerateResult:
    success: bool
    output_files: list[Path]   # 生成的文件列表
    errors: list[str]


class BaseGenerator(ABC):
    """代码生成器基类"""

    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(template_dir))

    @abstractmethod
    def generate(self, data: Any, output_dir: Path) -> GenerateResult:
        """从数据生成代码文件"""
        ...


# core/generators/c_generator.py

class CANCodeGenerator(BaseGenerator):
    """CAN Pack/Unpack C代码生成器"""

    def generate(self, data: DBCData, output_dir: Path) -> GenerateResult:
        """
        生成产物:
        - can_pack.c / can_pack.h     : Pack/Unpack函数
        - can_signals.h               : 信号-变量映射
        - can_messages.h              : 报文ID定义
        """
        ...

    def generate_signal_mapping(self, data: DBCData) -> str:
        """生成信号-变量映射头文件"""
        ...

    def generate_pack_unpack(self, message: MessageDef) -> str:
        """为单条报文生成Pack/Unpack函数"""
        ...


# core/generators/capl_generator.py

class CAPLGenerator(BaseGenerator):
    """CANoe CAPL代码生成器"""

    def generate(self, data: DBCData, output_dir: Path) -> GenerateResult:
        """
        生成产物:
        - vcu_node.can : CANoe网络节点CAPL代码
        """
        ...


# core/generators/arxml_generator.py

class ARXMLGenerator(BaseGenerator):
    """ARXML文件生成器"""

    def __init__(self, template_dir: Path, target_tool: str = "davinci"):
        super().__init__(template_dir)
        self.target_tool = target_tool

    def generate(self, data: ARXMLData, output_dir: Path) -> GenerateResult:
        """从SWC定义生成ARXML文件"""
        ...
```

### 2.6 校验规则引擎

```python
# core/rules/engine.py

from enum import Enum


class Severity(Enum):
    ERROR = "error"       # 必须修复
    WARNING = "warning"   # 建议修复
    INFO = "info"         # 提示


@dataclass
class RuleResult:
    rule_id: str
    severity: Severity
    message: str
    location: str         # 具体位置（信号名/报文名/SWC名等）
    suggestion: str       # 修复建议


class RuleEngine:
    """可配置的校验规则引擎"""

    def __init__(self, rules_config: Path):
        self.rules = self._load_rules(rules_config)

    def check_dbc(self, data: DBCData) -> list[RuleResult]:
        """DBC校验"""
        results = []
        results.extend(self._check_signal_overlap(data))
        results.extend(self._check_byte_order_consistency(data))
        results.extend(self._check_value_range(data))
        results.extend(self._check_naming_convention(data))
        return results

    def check_arxml(self, data: ARXMLData) -> list[RuleResult]:
        """ARXML校验"""
        results = []
        results.extend(self._check_port_interface_match(data))
        results.extend(self._check_runnable_period(data))
        results.extend(self._check_data_type_compatibility(data))
        return results

    def check_diag(self, config: dict) -> list[RuleResult]:
        """诊断配置校验"""
        results = []
        results.extend(self._check_dtc_coverage(config))
        results.extend(self._check_snapshot_completeness(config))
        results.extend(self._check_security_level_consistency(config))
        return results

    # --- DBC校验规则 ---

    def _check_signal_overlap(self, data: DBCData) -> list[RuleResult]:
        """检测信号位域重叠"""
        ...

    def _check_byte_order_consistency(self, data: DBCData) -> list[RuleResult]:
        """字节序一致性检查"""
        ...

    def _check_value_range(self, data: DBCData) -> list[RuleResult]:
        """取值范围合理性（物理值是否溢出）"""
        ...

    def _check_naming_convention(self, data: DBCData) -> list[RuleResult]:
        """命名规范检查（可配置规则）"""
        ...
```

---

## 3. 数据库设计

### 3.1 SQLite Schema

```sql
-- 标定参数表
CREATE TABLE calibration_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 参数名 (如 HV_ThreshOn)
    swc_name TEXT,                       -- 所属SWC
    group_name TEXT,                     -- 分组 (如 PowerMgmt)
    data_type TEXT NOT NULL,             -- uint8/uint16/int16/float32...
    default_value REAL,                  -- 默认值
    min_value REAL,                      -- 范围下限
    max_value REAL,                      -- 范围上限
    unit TEXT,                           -- 单位
    description TEXT,                    -- 描述
    source TEXT DEFAULT 'manual',        -- 来源: manual/model/a2l
    source_file TEXT,                    -- 来源文件路径
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 标定参数变更记录
CREATE TABLE calibration_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    param_id INTEGER NOT NULL,
    old_value REAL,
    new_value REAL,
    changed_by TEXT,                     -- 修改人
    reason TEXT,                         -- 修改原因
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (param_id) REFERENCES calibration_parameters(id)
);

-- DTC定义表
CREATE TABLE dtc_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dtc_code TEXT NOT NULL UNIQUE,       -- 如 0xD001
    description TEXT NOT NULL,
    severity TEXT,                       -- warning/critical/fault
    snapshot_ids TEXT,                   -- JSON数组: 关联的Snapshot数据项
    debounce_strategy TEXT,              -- debounce策略描述
    debounce_counter INTEGER,
    debounce_time_ms INTEGER,
    obd_related BOOLEAN DEFAULT FALSE,   -- 是否OBD相关
    custom_spec_source TEXT,             -- 自定义规范来源
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 诊断服务表
CREATE TABLE diag_services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sid TEXT NOT NULL,                   -- 如 0x19
    service_name TEXT NOT NULL,
    sub_functions TEXT,                  -- JSON数组: 子功能列表
    security_level TEXT,                 -- default/extended/security
    nrc_list TEXT,                       -- JSON数组: 支持的NRC
    description TEXT,
    enabled BOOLEAN DEFAULT TRUE
);

-- 需求追溯表
CREATE TABLE requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    req_id TEXT NOT NULL UNIQUE,         -- 需求ID (如 REQ_VCU_001)
    title TEXT NOT NULL,
    description TEXT,
    source TEXT DEFAULT 'feishu',        -- 来源: feishu/excel/csv
    source_id TEXT,                      -- 飞书多维表格记录ID
    module_name TEXT,                    -- 关联模块
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 追溯关联表
CREATE TABLE traceability_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    req_id INTEGER NOT NULL,
    link_type TEXT NOT NULL,             -- swc/test_case/signal/dtc
    link_target TEXT NOT NULL,           -- 关联目标名称
    link_target_id TEXT,                 -- 关联目标ID
    auto_matched BOOLEAN DEFAULT FALSE,  -- 是否自动匹配
    verified BOOLEAN DEFAULT FALSE,      -- 是否人工确认
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (req_id) REFERENCES requirements(id)
);

-- 项目配置表
CREATE TABLE project_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    category TEXT,                       -- general/can/swc/diag/calib
    description TEXT
);

-- 文件版本记录
CREATE TABLE file_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,             -- dbc/arxml/odx/a2l
    version_tag TEXT,                    -- 版本标签
    checksum TEXT NOT NULL,              -- 文件MD5
    snapshot_json TEXT,                  -- 文件解析快照(JSON)
    git_commit TEXT,                     -- Git commit hash
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. UI设计

### 4.1 主窗口布局

```
┌──────────────────────────────────────────────────────────────────────────┐
│  VCU DevKit v0.1                              [项目: VCU_2026] [⚙] [?] │
├────────┬─────────────────────────────────────────────────────────────────┤
│        │  [工具栏: 打开项目 | 保存 | 生成 | 校验 | 导出 | 撤销 | 重做]  │
│  导航  ├─────────────────────────────────────────────────────────────────┤
│        │                                                                 │
│  ▼ CAN │  ┌── 主工作区 ──────────────────────────────────────────────┐ │
│    Builder│  │                                                        │ │
│        │  │   (根据选中模块动态切换)                                   │ │
│  ▼ SWC │  │                                                        │ │
│    Designer│ │                                                        │ │
│        │  │                                                        │ │
│  ▼ 诊断│  │                                                        │ │
│    Builder│ │                                                        │ │
│        │  │                                                        │ │
│  ▼ 标定│  └────────────────────────────────────────────────────────┘ │
│    Manager│                                                           │
│        │  ┌── 属性/输出面板 ────────────────────────────────────────┐ │
│  ▼ 测试│  │ [属性] [校验结果] [生成日志] [变更历史]                   │ │
│    Gen │  │                                                        │ │
│        │  │  校验结果:                                               │ │
│  ▼ 追溯│  │  ⚠ WARN: Signal VCU_SOC range [0,127.5] exceeds uint8  │ │
│    Matrix│ │  ✗ ERR:  Signal Tq_Request overlaps with Tq_Actual     │ │
│        │  └────────────────────────────────────────────────────────┘ │
├────────┴─────────────────────────────────────────────────────────────────┤
│  状态栏: 已加载 3 DBC | 12 ARXML | 2 ODX | 就绪                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.2 CAN Builder 视图

```
┌──────────────────────────────────────────────────────────────────────────┐
│ CAN Builder                                                              │
│                                                                          │
│  ┌── 工具栏 ───────────────────────────────────────────────────────────┐ │
│  │ [打开DBC▾] [版本Diff▾] [校验] [生成▾]    搜索: [______________] [🔍]│ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌── 报文列表 ────────┬── 信号详情 ────────────────────────────────────┐ │
│  │ ▼ VCU_Status (0x100)│  Signal: VCU_SOC                              │ │
│  │   ├ VCU_PowerMode   │                                              │ │
│  │   ├ VCU_Ready       │  Start Bit:    [8]                            │ │
│  │   ├ VCU_SOC  ←      │  Bit Length:   [8]                            │ │
│  │   └ VCU_ErrCode     │  Byte Order:   [Little Endian ▾]              │ │
│  │                     │  Value Type:   [Unsigned ▾]                    │ │
│  │ ▼ VCU_Torque (0x200)│  Factor:       [0.5]                          │ │
│  │   ├ Tq_Request      │  Offset:       [0]                            │ │
│  │   ├ Tq_Actual       │  Min:          [0]                            │ │
│  │   └ Tq_Limit        │  Max:          [127.5]                        │ │
│  │                     │  Unit:         [%]                             │ │
│  │ ▼ VCU_HV (0x300)    │  Receiver:     [BMS, MCU ▾]                   │ │
│  │   ├ HV_Voltage      │                                              │ │
│  │   ├ HV_Current      │  值描述:                                       │ │
│  │   └ HV_Insulation   │  0x00 = "SOC_0%"                             │ │
│  │                     │  0xFE = "SOC_100%"                            │ │
│  │ ▼ ...               │  0xFF = "Invalid"                             │ │
│  └─────────────────────┴──────────────────────────────────────────────┘ │
│                                                                          │
│  ┌── Diff面板 (点击版本Diff时展开) ────────────────────────────────────┐ │
│  │  v2.2 → v2.3 (2026-05-13)                                          │ │
│  │  + VCU_HV.HV_Insulation     [新增]                                  │ │
│  │  ~ VCU_Status.VCU_SOC       Factor: 0.25 → 0.5                     │ │
│  │  - VCU_Torque.Tq_Reserved   [删除]                                  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌── 生成产物 ────────────────────────────────────────────────────────┐ │
│  │  ☑ can_pack.c / can_pack.h                                         │ │
│  │  ☑ can_signals.h                                                    │ │
│  │  ☑ can_node.can (CAPL)                                              │ │
│  │  ☑ 变更报告.xlsx                                                    │ │
│  │  输出目录: [./output/can/_______________] [浏览]  [生成 ▶]          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.3 SWC Designer 视图

```
┌──────────────────────────────────────────────────────────────────────────┐
│ SWC Designer                                            目标: [DaVinci ▾]│
│                                                                          │
│  ┌── SWC树 ──────────┬── SWC编辑器 ────────────────────────────────────┐ │
│  │                   │                                                │ │
│  │ ▼ Application     │  SWC: VCU_PowerMgmt                            │ │
│  │   ▼ VCU_PowerMgmt │  Category: ApplicationSoftwareComponent        │ │
│  │     ├ Ports (3)   │  Description: 整车电源管理                      │ │
│  │     ├ Runnables(2)│                                                │ │
│  │     └ Internals   │  ┌─ Ports ───────────────────────────────────┐ │ │
│  │                   │  │ Name           │ Dir  │ Interface          │ │ │
│  │   ▼ VCU_DriveCtrl │  │ PwrStatus_P    │ PR   │ I_PwrStatus_SR     │ │ │
│  │     ├ Ports (4)   │  │ VCU_Cmd_P      │ PR   │ I_VCU_Cmd_SR       │ │ │
│  │     └ Runnables(3)│  │ BMS_Status_R   │ REQ  │ I_BMS_Status_SR    │ │ │
│  │                   │  │ [+ 添加Port]                              │ │ │
│  │   ▼ VCU_Thermal   │  └──────────────────────────────────────────┘ │ │
│  │   ▼ VCU_Diag      │                                                │ │
│  │   ▼ VCU_Comm      │  ┌─ Runnables ──────────────────────────────┐ │ │
│  │                   │  │ Name              │ Trigger   │ Acc. Time │ │ │
│  │ ──── 模板库 ──── │  │ RE_PowerOn        │ 10ms      │ 2ms      │ │ │
│  │ ▼ Power系         │  │ RE_PowerOff       │ 10ms      │ 2ms      │ │ │
│  │   [电源管理模板]  │  │ RE_FaultHandler   │ Event     │ 1ms      │ │ │
│  │ ▼ Drive系         │  │ [+ 添加Runnable]                          │ │ │
│  │   [驱动控制模板]  │  └──────────────────────────────────────────┘ │ │
│  │ ▼ Thermal系       │                                                │ │
│  │   [热管理模板]    │  [从ARXML导入] [导出ARXML] [生成骨架C] [一致性检查]│ │
│  └───────────────────┴────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 代码生成产物示例

### 5.1 Pack/Unpack C代码 (can_pack.h)

```c
/* Auto-generated by VCU DevKit - CAN Builder */
/* Source: VCU_Main.dbc v2.3 */
/* Date: 2026-05-13 14:30:00 */
/* DO NOT EDIT MANUALLY */

#ifndef CAN_PACK_H
#define CAN_PACK_H

#include <stdint.h>

/* ========== Message IDs ========== */
#define CAN_MSG_VCU_STATUS      0x100u
#define CAN_MSG_VCU_TORQUE      0x200u
#define CAN_MSG_VCU_HV          0x300u

/* ========== DLC ========== */
#define CAN_DLC_VCU_STATUS      8u
#define CAN_DLC_VCU_TORQUE      8u
#define CAN_DLC_VCU_HV          8u

/* ========== Signal: VCU_Status.VCU_PowerMode ========== */
/* Start: 0, Len: 4, Factor: 1, Offset: 0, Range: [0, 15] */
typedef enum {
    VCU_POWER_OFF     = 0u,
    VCU_POWER_ACC     = 1u,
    VCU_POWER_ON      = 2u,
    VCU_POWER_CHARGING = 3u,
    VCU_POWER_FAULT   = 15u
} VCU_PowerMode_e;

static inline void CAN_Pack_VCU_PowerMode(uint8_t *buf, VCU_PowerMode_e val) {
    buf[0] = (buf[0] & 0xF0u) | ((uint8_t)val & 0x0Fu);
}

static inline VCU_PowerMode_e CAN_Unpack_VCU_PowerMode(const uint8_t *buf) {
    return (VCU_PowerMode_e)(buf[0] & 0x0Fu);
}

/* ========== Signal: VCU_Status.VCU_Ready ========== */
/* Start: 4, Len: 1, Factor: 1, Offset: 0, Range: [0, 1] */

static inline void CAN_Pack_VCU_Ready(uint8_t *buf, uint8_t val) {
    buf[0] = (buf[0] & 0xEFu) | ((val & 0x01u) << 4);
}

static inline uint8_t CAN_Unpack_VCU_Ready(const uint8_t *buf) {
    return (buf[0] >> 4) & 0x01u;
}

/* ========== Signal: VCU_Status.VCU_SOC ========== */
/* Start: 8, Len: 8, Factor: 0.5, Offset: 0, Range: [0, 127.5], Unit: % */

static inline void CAN_Pack_VCU_SOC(uint8_t *buf, float physical) {
    uint8_t raw = (uint8_t)(physical / 0.5f);
    buf[1] = raw;
}

static inline float CAN_Unpack_VCU_SOC(const uint8_t *buf) {
    return (float)buf[1] * 0.5f;
}

/* ========== Signal: VCU_Torque.Tq_Request ========== */
/* Start: 0, Len: 16, Factor: 0.1, Offset: -500, Range: [-500, 1155.3], Unit: Nm */
/* Byte Order: Little Endian */

static inline void CAN_Pack_Tq_Request(uint8_t *buf, float physical) {
    uint16_t raw = (uint16_t)((physical - (-500.0f)) / 0.1f);
    buf[0] = (uint8_t)(raw & 0xFFu);
    buf[1] = (uint8_t)((raw >> 8) & 0xFFu);
}

static inline float CAN_Unpack_Tq_Request(const uint8_t *buf) {
    uint16_t raw = (uint16_t)buf[0] | ((uint16_t)buf[1] << 8);
    return (float)raw * 0.1f + (-500.0f);
}

#endif /* CAN_PACK_H */
```

### 5.2 SWC骨架代码 (vcu_powermgmt.c)

```c
/* Auto-generated by VCU DevKit - SWC Designer */
/* SWC: VCU_PowerMgmt */
/* Target: DaVinci Configurator ARXML 4.4 */
/* Date: 2026-05-13 14:30:00 */
/* DO NOT EDIT MANUALLY - Modify in SWC Designer and re-generate */

#include "Rte_VCU_PowerMgmt.h"
#include "vcu_powermgmt.h"

/* ========== Runnable: RE_PowerOn (10ms) ========== */
void RE_PowerOn(void) {
    /* Read inputs from RTE */
    uint8_t hv_status = Rte_IRead_PwrStatus_P_HV_Status();
    uint16_t batt_voltage = Rte_IRead_PwrStatus_P_BattVoltage();

    /* TODO: Implement power-on logic */

    /* Write outputs to RTE */
    Rte_IWrite_PwrStatus_P_PowerMode(VCU_POWER_ON);
    Rte_IWrite_PwrStatus_P_VCU_Ready(1u);
}

/* ========== Runnable: RE_PowerOff (10ms) ========== */
void RE_PowerOff(void) {
    /* TODO: Implement power-off sequence */

    Rte_IWrite_PwrStatus_P_PowerMode(VCU_POWER_OFF);
    Rte_IWrite_PwrStatus_P_VCU_Ready(0u);
}

/* ========== Runnable: RE_FaultHandler (Event-triggered) ========== */
void RE_FaultHandler(void) {
    /* TODO: Implement fault handling */

    Rte_IWrite_PwrStatus_P_PowerMode(VCU_POWER_FAULT);
}
```

---

## 6. 依赖与构建

### 6.1 requirements.txt

```
# Core
PySide6>=6.6.0
lxml>=5.1.0
Jinja2>=3.1.3

# File format parsers
cantools>=39.4.0
odxtools>=0.7.0
python-can>=4.3.0

# Database
peewee>=3.17.0

# Utilities
openpyxl>=3.1.2          # Excel报告生成
click>=8.1.0             # CLI接口
rich>=13.7.0             # 终端输出美化
python-dotenv>=1.0.0

# Testing
pytest>=8.0.0
pytest-qt>=4.4.0
pytest-cov>=5.0.0
```

### 6.2 pyproject.toml

```toml
[project]
name = "vcu-devkit"
version = "0.1.0"
description = "VCU Software Development Assistant Toolkit"
requires-python = ">=3.11"

[project.scripts]
vcu-devkit = "main:main"
```

---

## 7. 开发规范

### 7.1 编码规范

- Python 3.11+，全程使用 type hints
- 遵循 PEP 8，行宽 100
- 使用 `dataclass` 定义数据模型，不使用 `dict` 传递结构化数据
- UI层与业务逻辑分离：`views/` 只负责展示，`controller.py` 处理逻辑
- 所有文件I/O通过 `pathlib.Path`

### 7.2 测试策略

| 层级 | 工具 | 覆盖目标 |
|------|------|----------|
| 单元测试 | pytest | 解析器、生成器、Diff引擎、规则引擎 |
| 集成测试 | pytest + 真实文件 | DBC→代码全流程、ARXML读写全流程 |
| UI测试 | pytest-qt | 关键交互流程 |

### 7.3 分支策略

```
main
├── develop
│   ├── feature/can-builder
│   ├── feature/swc-designer
│   ├── feature/diag-builder
│   └── ...
└── release/v0.1.0
```

---

## 8. 开发任务拆解

### Phase 1 任务列表（10周）

#### Sprint 0: Core Engine（第1-2周）

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 0.1 | 搭建项目骨架、PySide6主窗口、侧边栏导航 | 可运行的空壳应用 | 2d |
| 0.2 | DBC解析器（基于cantools封装） | DBCData数据模型 + 单元测试 | 2d |
| 0.3 | ARXML解析器基础框架 + DaVinci适配 | ARXMLData数据模型 + 单测 | 3d |
| 0.4 | Jinja2模板引擎封装 | 模板加载/渲染框架 | 1d |
| 0.5 | SQLite数据库初始化 + ORM | 数据表创建 + 基础CRUD | 2d |

#### Sprint 1: CAN Builder 基础（第3-4周）

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 1.1 | CAN Builder 视图：报文列表 + 信号表格 | UI可交互 | 3d |
| 1.2 | 信号编辑功能（单条/批量） | 可编辑DBC | 2d |
| 1.3 | DBC Diff引擎 | 版本对比功能 + 报告导出 | 3d |
| 1.4 | 信号位域重叠检测规则 | 校验功能 | 2d |

#### Sprint 2: CAN Builder 代码生成（第5-6周）

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 2.1 | C代码生成器：Pack/Unpack + 信号映射 | can_pack.h/.c | 3d |
| 2.2 | CAPL生成器 | can_node.can | 2d |
| 2.3 | 生成配置面板（产物选择、输出目录） | UI | 1d |
| 2.4 | Excel变更报告导出 | .xlsx报告 | 2d |
| 2.5 | CAN Builder集成测试 + Bug修复 | 可交付 | 2d |

#### Sprint 3: SWC Designer 基础（第7-8周）

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 3.1 | SWC树形视图 + 拖拽创建 | UI骨架 | 3d |
| 3.2 | Port/Interface编辑器 | 可配置Port | 2d |
| 3.3 | Runnable编辑器 | 可配置Runnable | 2d |
| 3.4 | ARXML解析器扩展：EB Tresos适配 | 双模式兼容 | 2d |
| 3.5 | SWC模板库（预置5个VCU常用模板） | 模板数据 | 1d |

#### Sprint 4: SWC Designer 生成 + 集成（第9-10周）

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 4.1 | ARXML生成器（DaVinci/EB双模式） | 可导出ARXML | 3d |
| 4.2 | SWC骨架C代码生成 | vcu_xxx.c/.h | 2d |
| 4.3 | 一致性检查规则（Port接口匹配等） | 校验功能 | 2d |
| 4.4 | Phase 1集成测试 + 文档 | 可交付v0.1 | 3d |

---

*下一步：确认技术设计后，启动Sprint 0开发。*
