# SWC 开发模块

SWC 开发模块用于可视化设计 AUTOSAR 软件组件（SWC），管理端口、接口和 Composition。

## 功能

- **SWC 列表**：TreeView 层级展示所有 SWC
- **接口面板**：SenderReceiver / ClientServer 接口管理
- **模板快速创建**：5 个内置 VCU SWC 模板
- **ARXML 导入/导出**：支持 AUTOSAR 4.2/4.3/4.4
- **端口连线**：Composition 内组件端口连接可视化
- **Composition 连线解析**：ASSEMBLY-SW-CONNECTOR / DELEGATION-SW-CONNECTOR

## 操作流程

### 导入 ARXML

1. 拖放 `.arxml` 文件到窗口
2. 自动解析 SWC、端口、接口、数据类型、Composition
3. 大文件（>5MB）自动使用流式解析

### 创建 SWC

1. 点击 **模板** 按钮选择内置模板
2. 或手动添加端口和 Runnable

### 编辑端口

- 选中 SWC 后，在端口面板添加 P-Port（Provider）或 R-Port（Requester）
- 关联到 SenderReceiver 或 ClientServer 接口

### 导出 ARXML

按 `F6` 或点击 **导出** 导出 ARXML 文件，支持 DaVinci 和 EB Tresos 两种目标格式。
