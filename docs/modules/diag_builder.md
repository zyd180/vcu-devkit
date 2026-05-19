# 诊断配置模块

诊断配置模块用于管理 UDS 诊断服务和 DTC（故障码）配置。

## 功能

- **DTC 列表**：TableEditor 展示所有故障码，支持搜索过滤
- **UDS 服务编辑**：13 项标准服务模板（0x10-0x3E）
- **ODX 导入**：从 ODX/CDD 文件导入诊断配置
- **DTC 快照/扩展数据**：编辑故障码的环境数据

## 操作流程

### 导入 ODX

1. 拖放 `.odx` / `.odx-d` / `.cdd` 文件到窗口
2. 自动解析 DTC 列表和服务定义

### 添加 DTC

1. 点击 **+** 按钮
2. 填写 DTC 编号、描述、严重级别、快照数据

### 配置 UDS 服务

从 13 项标准服务模板中选择：
- 0x10 DiagnosticSessionControl
- 0x11 ECUReset
- 0x14 ClearDiagnosticInformation
- 0x19 ReadDTCInformation
- 0x22 ReadDataByIdentifier
- 0x2E WriteDataByIdentifier
- 0x27 SecurityAccess
- 0x28 CommunicationControl
- 0x3E TesterPresent
- 等等

### 导出

支持导出为 JSON 格式。
