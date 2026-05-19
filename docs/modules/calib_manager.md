# 标定管理模块

标定管理模块用于管理标定参数，支持 A2L 文件导入导出。

## 功能

- **参数列表**：按 Group 分组，支持搜索过滤
- **参数详情**：名称、数据类型、默认值、最小值、最大值、单位、描述
- **变更历史**：记录每次参数修改的时间、操作人、原因
- **A2L 导入**：从 ASAP2 格式文件导入 CHARACTERISTIC 和 MEASUREMENT
- **多格式导出**：JSON、A2L（INCA/CANape 兼容）、A2L 摘要

## 操作流程

### 导入 A2L

1. 拖放 `.a2l` 文件到窗口
2. 自动解析 CHARACTERISTIC、MEASUREMENT、COMPU_METHOD
3. 点击 **导入到数据库** 将参数写入本地 DB

### 添加参数

1. 点击 **+** 按钮
2. 填写参数属性

### 导出

| 格式 | 说明 |
|------|------|
| JSON | 完整参数数据 + 变更历史 |
| A2L | ASAP2 标准格式（/begin CHARACTERISTIC ...） |
| A2L 摘要 | 精简版 A2L，仅包含核心字段 |

A2L 导出支持 COMPU_METHOD 类型：IDENTICAL、LINEAR、RAT_FUNC、FORM。
