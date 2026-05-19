# VCU DevKit 快速入门

## 安装

```bash
# 克隆项目
git clone https://github.com/zyd180/vcu-devkit.git
cd vcu-devkit

# 安装依赖
pip install -e ".[full,dev]"

# 启动
python main.py
```

Windows 用户也可双击 `启动VCU-DevKit.bat`。

## 5 分钟上手

### 1. 打开 DBC 文件

- **拖放**：直接将 `.dbc` 文件拖入窗口
- **菜单**：`文件 → 打开项目` 选择目录
- **快捷键**：`Ctrl+O`

打开后自动进入 **CAN 开发** 模块，左侧显示报文/信号树。

### 2. 浏览和编辑信号

- 点击报文名展开信号列表
- 选中信号后，右侧属性面板显示 12 个可编辑字段
- 修改后按 `Ctrl+Z` 撤销、`Ctrl+Y` 重做

### 3. 校验配置

- 点击工具栏 **校验** 按钮 或按 `F5`
- 检查信号重叠、DLC 不足、命名规范等 12 条规则
- 结果显示在状态栏

### 4. 生成代码

- 点击工具栏 **生成** 按钮 或按 `F6`
- 选择输出目录，自动生成 C 头文件（`can_pack.h`、`can_signals.h`、`can_messages.h`）

### 5. 导出

点击 **导出** 按钮，选择格式：

| 格式 | 说明 |
|------|------|
| C 代码 | Pack/Unpack 函数 |
| CAPL | CANoe 仿真节点代码 |
| Excel | 信号矩阵报告 |
| ARXML | AUTOSAR SWC 描述 |
| A2L | INCA/CANape 标定文件 |
| JSON | 数据快照 |

## 模块概览

| 模块 | 功能 | 支持格式 |
|------|------|---------|
| CAN 开发 | DBC 配置与代码生成 | .dbc, C, CAPL, Excel |
| SWC 开发 | AUTOSAR SWC 可视化 | .arxml |
| 诊断配置 | UDS/DTC 配置 | .odx, .cdd |
| 标定管理 | 参数管理与导出 | .a2l, JSON |
| 测试生成 | 用例自动生成 | Excel, JSON |
| 需求追溯 | 需求与工件追溯 | Excel |

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+O` | 打开项目目录 |
| `Ctrl+S` | 保存 |
| `Ctrl+Z` | 撤销 |
| `Ctrl+Y` | 重做 |
| `Ctrl+F` | 搜索 |
| `F5` | 校验 |
| `F6` | 生成代码 |
