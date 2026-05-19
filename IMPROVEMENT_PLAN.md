# VCU DevKit 改进计划

> 基于 v0.1.0 架构评估，总分 7.275/10，目标 3 个月内提升至 8.5+
>
> **状态标记：** ✅ 已完成 | 🔄 进行中 | ⬜ 待开始

---

## 阶段一：打通核心闭环（第 1-4 周）

> 目标：用户打开应用能看到真实功能，完成一次完整的 DBC → 校验 → 代码生成 流程

### 1.1 CAN Builder 视图实现 [P0] ✅

**实际情况：** 视图已完整实现（445 行），含 TreeView/PropertyPanel/TableEditor/Toolbar/Filter/DiffViewer

| # | 任务 | 状态 |
|---|------|------|
| 1 | TreeView 消息/信号树（按 sender 分组） | ✅ |
| 2 | PropertyPanel 信号属性展示（12 个字段可编辑） | ✅ |
| 3 | TableEditor 信号列表（可排序、可过滤） | ✅ |
| 4 | Toolbar（打开/保存/Diff/校验/生成/批量编辑） | ✅ |
| 5 | Controller 绑定（load_dbc/save_dbc/add_signal/remove_signal） | ✅ |
| 6 | 拖放加载 + 全局搜索过滤 | ✅ |

---

### 1.1b DBC 格式回写 [P0] ✅

| # | 任务 | 状态 |
|---|------|------|
| 1 | save_dbc() 使用 cantools 格式回写 | ✅ |
| 2 | 保留 save_json_snapshot() 作为 JSON 快照 | ✅ |
| 3 | _on_save 文件对话框支持 .dbc/.json 双格式 | ✅ |
### 1.2 SWC Designer 视图实现 [P0] ✅

**实际情况：** 视图已完整实现（795 行）

| # | 任务 | 状态 |
|---|------|------|
| 1 | SWC 列表视图 + TreeView 层级展示 | ✅ |
| 2 | 接口面板（SenderReceiver / ClientServer） | ✅ |
| 3 | 模板快速创建（5 个内置 VCU SWC 模板） | ✅ |
| 4 | ARXML 导入/导出绑定 | ✅ |
| 5 | 端口连线可视化 | ✅ |

---

### 1.3 Diag Builder 视图实现 [P1] ✅

**实际情况：** 视图已完整实现（656 行）

| # | 任务 | 状态 |
|---|------|------|
| 1 | DTC 列表视图（TableEditor） | ✅ |
| 2 | UDS 服务编辑面板（13 项服务模板） | ✅ |
| 3 | ODX 导入向导 | ✅ |
| 4 | DTC 快照/扩展数据编辑 | ✅ |

---

### 1.4 Calib Manager 视图实现 [P1] ✅

**实际情况：** 视图已完整实现（489 行）

| # | 任务 | 状态 |
|---|------|------|
| 1 | 参数列表视图（按 Group 分组，搜索过滤） | ✅ |
| 2 | 参数详情面板 | ✅ |
| 3 | 变更历史面板 | ✅ |
| 4 | A2L 导入向导 | ✅ |

---

### 1.5 Test Generator 视图实现 [P1] ✅

**实际情况：** 视图已完整实现（403 行）

---

### 1.6 Trace Matrix 视图实现 [P1] ✅

**实际情况：** 视图已完整实现（556 行）

---

### 1.7 主窗口功能按钮绑定 [P0] ✅

| # | 任务 | 状态 |
|---|------|------|
| 1 | 保存按钮 → 委托到当前模块 controller | ✅ |
| 2 | 校验按钮 → 调用 controller.validate() | ✅ |
| 3 | 生成按钮 → 调用 controller.generate_code()/export_*() | ✅ |
| 4 | 导出菜单 → 动态构建支持格式列表 | ✅ |
| 5 | 撤销/重做框架（Command 模式） | ✅ |
| 6 | 撤销/重做集成到 CAN Builder（Ctrl+Z/Y） | ✅ |

---

### 1.5 Test Generator 视图实现 [P1]

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | 测试用例列表（TableEditor，按分类/优先级过滤） | `modules/test_generator/views/test_generator_view.py` | 3h |
| 2 | 用例详情面板（前置条件/测试步骤/预期结果/关联信号） | 同上 | 2h |
| 3 | 覆盖率仪表盘（饼图或进度条显示信号覆盖率） | 同上 + 新 widget | 3h |
| 4 | 一键生成 + 导出 Excel 按钮绑定 | 同上 | 1h |

---

### 1.6 Trace Matrix 视图实现 [P1]

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | 追溯矩阵表格（需求 × 链接类型的交叉表，红绿色标记） | `modules/trace_matrix/views/trace_matrix_view.py` | 4h |
| 2 | 需求详情面板 + 链接管理（添加/删除 SWC/信号/DTC/测试用例链接） | 同上 | 3h |
| 3 | 统计仪表盘（追溯覆盖率、未追溯需求列表） | 同上 | 2h |
| 4 | Excel 导出按钮绑定 | 同上 | 1h |

---

### 1.7 主窗口功能按钮绑定 [P0]

**当前状态：** `_on_save` / `_on_check` / `_on_generate` 仅修改状态栏文字

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | 保存按钮 → 调用当前模块 controller 的 save 方法 | `ui/main_window.py` | 2h |
| 2 | 校验按钮 → 调用 RuleEngine.check_dbc / check_arxml | 同上 | 2h |
| 3 | 生成按钮 → 弹出导出对话框，调用对应 generator | 同上 | 2h |
| 4 | 导出菜单 → 绑定 C 代码/CAPL/Excel/ARXML 各格式导出 | 同上 | 2h |
| 5 | 撤销/重做框架（Command 模式） | 新建 `core/commands/` | 6h |

---

## 阶段二：功能深化与测试补全（第 5-8 周）

> 目标：补全核心功能短板，测试覆盖率达到 80%+

### 2.1 DBC 格式完整回写 [P0]

**当前状态：** `save_dbc()` 仅保存 JSON 快照

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | 利用 `cantools.Database.dump()` 实现 DBC 格式回写 | `modules/can_builder/controller.py` | 3h |
| 2 | 处理 cantools 不支持的字段（comment、value_descriptions）的自定义序列化 | 同上 | 2h |
| 3 | 保存前自动校验（DLC、信号重叠、值域）并弹出警告 | 同上 | 2h |
| 4 | 测试：编辑信号 → 保存 → 重新加载 → 验证数据一致性 | `tests/test_generators/test_dbc_roundtrip.py` | 2h |

---

### 2.2 AUTOSAR 数据类型解析补全 [P1]

**当前状态：** `DataTypeDef` 的 `base_type` / `size` / `encoding` 始终为空

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | 解析 `APPLICATION-PRIMITIVE-DATA-TYPE` 的 `SW-DATA-DEF-PROPS` | `core/parsers/arxml_parser.py` | 3h |
| 2 | 解析 `BASE-TYPE-REF` → 获取 base type name/size/encoding | 同上 | 2h |
| 3 | 解析 `COMPU-METHOD-REF` → 关联值域转换 | 同上 | 2h |
| 4 | 更新 ARXML 生成器，输出完整的数据类型定义 | `core/generators/arxml_generator.py` | 2h |

---

### 2.3 SWC Composition 连线修复 [P1]

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | 解析 `ASSEMBLY-SW-CONNECTOR`（provider → requester 端口连接） | `core/parsers/arxml_parser.py` | 3h |
| 2 | 解析 `DELEGATION-SW-CONNECTOR`（内部端口委托到 composition 端口） | 同上 | 2h |
| 3 | 在 CompositionDef 中存储 connectors 列表 | 同上 + `arxml_parser.py` 数据类 | 1h |
| 4 | ARXML 生成器输出 connectors | `core/generators/arxml_generator.py` | 2h |

---

### 2.4 A2L 导出为 INCA 兼容格式 [P1]

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | 实现 A2L 文本生成器（/begin CHARACTERISTIC ... /end CHARACTERISTIC 格式） | 新建 `core/generators/a2l_generator.py` | 4h |
| 2 | 支持 COMPU_METHOD 导出（RAT_FUNC / LINEAR / FORM） | 同上 | 2h |
| 3 | 支持 MEASUREMENT 导出 | 同上 | 2h |
| 4 | 与 CalibManager Controller 集成 | `modules/calib_manager/controller.py` | 1h |

---

### 2.5 测试补全 [P0]

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | `tests/test_diff/` — DBC diff 引擎测试（新增/删除/修改信号、消息级 diff） | `tests/test_diff/test_dbc_diff.py` | 3h |
| 2 | `tests/test_generators/` — C 代码生成器测试（大小端、有符号、边界值） | `tests/test_generators/test_c_generator.py` | 3h |
| 3 | `tests/test_generators/` — ARXML 生成器测试（SWC/接口/Composition 输出验证） | `tests/test_generators/test_arxml_generator.py` | 2h |
| 4 | `tests/test_rules/` — 规则引擎全规则测试（12 条规则逐条覆盖） | `tests/test_rules/test_rule_engine.py` | 3h |
| 5 | `tests/test_modules/` — 各 controller 集成测试（DBC → 测试生成 → 追溯矩阵数据流） | `tests/test_modules/test_integration.py` | 4h |
| 6 | 负面路径测试（畸形 DBC、超大文件、编码异常、空文件） | `tests/test_parsers/test_edge_cases.py` | 3h |
| 7 | pytest-qt GUI 冒烟测试（窗口启动、模块切换、拖放） | `tests/test_ui/test_smoke.py` | 3h |

**验收标准：** `pytest tests/ -v --cov` 覆盖率 ≥ 80%，空目录全部有实际测试

---

## 阶段三：工程化与体验提升（第 9-12 周）

> 目标：可独立交付、可打包、用户体验达到生产级

### 3.1 CI/CD 配置 [P0]

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | GitHub Actions workflow：lint（ruff）+ test（pytest）+ coverage | `.github/workflows/ci.yml` | 2h |
| 2 | PR 自动运行测试 + 覆盖率报告 | 同上 | 1h |
| 3 | Release 时自动打包（PyInstaller） | `.github/workflows/release.yml` | 3h |

---

### 3.2 用户操作手册 [P1]

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | 快速入门（安装 → 拖入 DBC → 查看信号 → 生成代码） | `docs/quickstart.md` | 2h |
| 2 | CAN Builder 操作指南 | `docs/modules/can_builder.md` | 2h |
| 3 | SWC Designer 操作指南 | `docs/modules/swc_designer.md` | 2h |
| 4 | 其余 4 个模块各一份操作指南 | `docs/modules/*.md` | 4h |
| 5 | 飞书使用手册同步更新 | 飞书文档 | 2h |

---

### 3.3 大文件处理优化 [P1]

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | DBC 解析移到 QThread（FileWorker 已有框架，接入即可） | `modules/can_builder/controller.py` + view | 2h |
| 2 | 进度条对话框（解析中... 已完成 60%） | 新建 `ui/widgets/progress_dialog.py` | 2h |
| 3 | ARXML 大文件分段解析（lxml.iterparse 流式处理） | `core/parsers/arxml_parser.py` | 3h |
| 4 | Excel 导出异步化 | 各 controller 的 `export_excel` | 2h |

---

### 3.4 打包为独立可执行文件 [P2]

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | PyInstaller spec 文件（包含资源文件、QSS、图标） | `vcu_devkit.spec` | 2h |
| 2 | Windows 打包测试 + 修复路径问题 | — | 2h |
| 3 | 启动脚本更新（bat 指向 dist/ 目录） | `启动VCU-DevKit.bat` | 0.5h |
| 4 | 版本号自动注入（从 pyproject.toml 读取） | `build.py` | 1h |

---

### 3.5 新用户引导流程 [P2]

| # | 任务 | 涉及文件 | 预估工时 |
|---|------|---------|---------|
| 1 | 首次启动欢迎对话框（3 步引导：导入文件 → 选择模块 → 开始工作） | 新建 `ui/widgets/welcome_dialog.py` | 3h |
| 2 | 最近文件列表（侧边栏底部或文件菜单） | `ui/sidebar.py` + `ui/main_window.py` | 2h |
| 3 | 工具提示（Tooltip）覆盖所有按钮和快捷键 | 各 view 文件 | 1h |

---

## 阶段四：能力扩展（第 13-24 周）

> 目标：从"辅助工具"升级为"专业工具"

### 4.1 CAN FD 支持 [P2]

| # | 任务 | 预估工时 |
|---|------|---------|
| 1 | DBC 解析支持 CAN FD 64 字节 DLC | 3h |
| 2 | C 代码生成支持 CAN FD（64 字节 buffer） | 2h |
| 3 | BRS/CRC 信号标记 | 1h |

### 4.2 J1939 协议支持 [P2]

| # | 任务 | 预估工时 |
|---|------|---------|
| 1 | J1939 DBC 解析（PGN/SPN 映射） | 4h |
| 2 | J1939 传输协议（多帧 BAM/RTS-CTS） | 4h |
| 3 | J1939 诊断（DM1/DM2 故障码） | 3h |

### 4.3 XCP/CCP 标定协议基础 [P3]

| # | 任务 | 预估工时 |
|---|------|---------|
| 1 | XCP 协议帧定义（CONNECT/GET_STATUS/SHORT_UPLOAD） | 4h |
| 2 | A2L → XCP 映射（地址 → 信号关联） | 3h |
| 3 | 在线标定参数读写框架 | 4h |

### 4.4 飞书多维表格同步 [P3]

| # | 任务 | 预估工时 |
|---|------|---------|
| 1 | 需求数据从飞书多维表格导入到 TraceMatrix | 3h |
| 2 | 追溯结果回写到飞书多维表格 | 2h |
| 3 | 定时同步 + 冲突处理 | 3h |

### 4.5 插件化架构 [P3]

| # | 任务 | 预估工时 |
|---|------|---------|
| 1 | 插件接口定义（BasePlugin: parser/generator/rule） | 3h |
| 2 | 插件发现机制（扫描 plugins/ 目录） | 2h |
| 3 | 插件注册到对应的 registry（parser_registry / generator_registry） | 2h |
| 4 | 插件配置 UI（启用/禁用/排序） | 3h |

---

## 工时汇总

| 阶段 | 周期 | 总工时 | 核心产出 |
|------|------|--------|---------|
| 阶段一 | 第 1-4 周 | ~70h | 6 个模块真实 UI + 功能按钮绑定 |
| 阶段二 | 第 5-8 周 | ~40h | DBC 回写 + AUTOSAR 补全 + 测试 ≥80% |
| 阶段三 | 第 9-12 周 | ~30h | CI/CD + 用户手册 + 打包 |
| 阶段四 | 第 13-24 周 | ~45h | CAN FD + J1939 + 插件化 |
| **总计** | **24 周** | **~185h** | |

---

## 里程碑

| 里程碑 | 时间 | 验收标准 |
|--------|------|---------|
| **M1 — 可用** | 第 4 周末 | 6 个模块 UI 可操作，完成 DBC → 校验 → C 代码 完整流程 |
| **M2 — 可靠** | 第 8 周末 | DBC 回写可用，测试覆盖率 ≥ 80%，空目录全部有测试 |
| **M3 — 可交付** | 第 12 周末 | CI/CD 绿灯，用户手册完成，PyInstaller 打包成功 |
| **M4 — 专业** | 第 24 周末 | CAN FD + J1939 可用，插件架构就位，飞书同步上线 |
