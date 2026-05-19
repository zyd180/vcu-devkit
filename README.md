# VCU DevKit

汽车VCU（整车控制器）软件开发辅助工具 — Vector工具链的效率放大器

基于 PySide6 构建的桌面应用，覆盖 CAN 通信配置、AUTOSAR SWC 设计、诊断配置、标定管理、测试用例生成和需求追溯六大核心场景。

## 功能模块

| 模块 | 说明 |
|------|------|
| **CAN开发** | DBC 文件解析、信号编辑、校验规则、差异对比、C 代码生成（can_pack.h / can_signals.h / can_messages.h） |
| **SWC开发** | AUTOSAR SWC 可视化设计、端口/Runnable/接口管理、内置 5 个 VCU 模板、ARXML 导出 |
| **诊断配置** | DTC 定义与管理、13 项标准 UDS 服务模板、快照配置、ODX/CDD/JSON 导入导出 |
| **标定管理** | A2L 文件解析、参数树管理、分组/SWC 关联、变更历史、JSON/A2L 导出 |
| **测试生成** | 从 DBC 自动生成测试用例（边界值/正常范围/错误注入/信号超时）、覆盖率统计、Excel 导出 |
| **需求追溯** | 需求与 SWC/信号/DTC/测试用例的追溯矩阵、自动匹配、缺口分析、Excel 导出 |

## 快速开始

### 环境要求

- Python 3.10+
- Windows 10/11（PySide6）

### 安装

```bash
git clone https://github.com/zyd180/vcu-devkit.git
cd vcu-devkit
pip install -r requirements.txt
```

### 启动

```bash
python main.py
```

或双击 `启动VCU-DevKit.bat`

## 项目结构

```
vcu-devkit/
├── main.py                          # 应用入口
├── config/
│   └── settings.py                  # 应用配置
├── core/
│   ├── parsers/                     # 文件解析器
│   │   ├── dbc_parser.py            # DBC 解析（cantools）
│   │   ├── arxml_parser.py          # ARXML 解析（lxml + XXE防护）
│   │   ├── odx_parser.py            # ODX/CDD 诊断文件解析
│   │   └── a2l_parser.py            # A2L 标定文件解析
│   ├── generators/                  # 代码生成器
│   │   ├── c_generator.py           # C 头文件生成
│   │   ├── arxml_generator.py       # ARXML 导出
│   │   └── capl_generator.py        # CAPL 脚本生成
│   ├── rules/
│   │   └── engine.py                # 校验规则引擎
│   ├── diff/
│   │   └── dbc_diff.py              # DBC 差异对比
│   └── db/
│       ├── models.py                # 数据库模型（peewee ORM）
│       └── manager.py               # 数据库管理
├── modules/
│   ├── can_builder/                 # CAN开发模块
│   ├── swc_designer/                # SWC开发模块
│   ├── diag_builder/                # 诊断配置模块
│   ├── calib_manager/               # 标定管理模块
│   ├── test_generator/              # 测试生成模块
│   └── trace_matrix/                # 需求追溯模块
├── ui/
│   ├── main_window.py               # 主窗口
│   ├── sidebar.py                   # 侧边栏导航
│   ├── icons.py                     # SVG 图标管理
│   ├── icons/                       # 自定义 SVG 图标（21个）
│   ├── themes/                      # 浅色/暗色主题 QSS
│   └── widgets/                     # 通用 UI 组件
├── tests/
│   └── test_full_coverage.py        # 156 项自动化测试
└── requirements.txt
```

## 支持的文件格式

**输入：**
- `.dbc` — Vector DBC（CAN 数据库），支持拖拽加载
- `.arxml` — AUTOSAR XML，支持拖拽加载
- `.odx` / `.cdd` — ODX 2.2（诊断数据库），支持拖拽加载
- `.a2l` — ASAP2（标定文件），支持拖拽加载
- `.json` — 通用配置导入

**输出：**
- `.h` — C 头文件（信号打包/解包）
- `.arxml` — AUTOSAR ARXML
- `.json` — 各模块配置导出
- `.xlsx` — Excel 测试用例 / 追溯矩阵
- `.a2l` — A2L 标定参数摘要

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+O` | 打开项目目录 |
| `Ctrl+S` | 保存 |
| `Ctrl+Shift+S` | 全部保存 |
| `Ctrl+F` | 全局搜索 |
| `F5` | 校验当前配置 |
| `F6` | 生成代码 |
| `Ctrl+Z` / `Ctrl+Y` | 撤销 / 重做 |

## 特性亮点

- **拖拽加载** — 直接拖入 `.dbc` / `.arxml` / `.odx` / `.a2l` 文件，自动切换到对应模块并加载
- **全局搜索** — 工具栏搜索框或 `Ctrl+F`，实时过滤当前模块的信号/DTC/参数
- **ODX/CDD 导入** — 诊断配置模块直接导入 ODX 2.2 / CDD 文件，自动提取 DTC 和诊断服务
- **暗色主题** — 工具 > 暗色主题 切换，侧边栏、表格、树形视图全面适配

## 技术栈

- **GUI**: PySide6 (Qt for Python)
- **解析**: cantools, lxml
- **数据库**: SQLite + peewee ORM
- **导出**: openpyxl (Excel), Jinja2 (代码模板)
- **安全**: XML 外部实体 (XXE) 防护
- **异步**: QThread 文件 I/O（大文件不阻塞界面）

## 测试

```bash
python -m pytest tests/ -v
```

158 项测试覆盖：模块导入、控制器逻辑、解析器功能、XXE 防护、UI 组件、数据库操作、主题文件、规则引擎、代码生成、ODX 导入。

## License

MIT
