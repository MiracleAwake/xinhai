# DeepSea 工程目录

代码根目录。设计文档和参考资料位于上级目录的 `开发者文档/` 与 `参考资料/`。

当前已实现：SQLite WAL、records 真相表、FTS5、分层记忆、Evidence、多模态字段、结构化 OCR、MCP/HTTP 与版本化配置只读接口。
后续按 `src/xinhai/` 的分层逐步实现，不为尚未实现的模块伪造功能。

## MCP 接入

本地 MCP Server 入口：`python -m xinhai.mcp_server`。先设置 `PYTHONPATH=src`，客户端通过 stdio 连接。

Codex 注册示例：

```powershell
codex mcp add xinhai_local --env "PYTHONPATH=D:\AI\DeepSea · 基于RAG+Agent构建的云端长期记忆库平台\DeepSea\src" -- python -m xinhai.mcp_server
```

可用工具包括：`remember`、`confirm`、`recall`、`recall_evidence`、`recall_structured`、`compare_structured`、`auto_recall`、`checkpoint`、`history`、`forget`，以及只读配置工具 `config_status`、`config_history`、`config_diff`。

MCP 只提供工具调用，不会自动读取宿主聊天历史；自动对话接入需要客户端事件适配器或显式调用。
