# MCP 接入与后端边界

## 当前能力

心海以 stdio 提供记忆、证据、结构化事实和只读配置 MCP 工具。工具调用进入 `MemoryMCPAdapter`，再进入 `MemoryService` 或 `ConfigManager`，经过 Secretary、Retriever、Gatekeeper 和 SQLite/配置 manifest。

## Codex

在 Codex 环境注册：

```powershell
codex mcp add xinhai_local --env "PYTHONPATH=<DeepSea>\src" -- python -m xinhai.mcp_server
```

注册后需要新建或重启对话，让客户端重新发现工具。真实对话不会自动进入心海；需要显式调用 `remember`，或未来接入宿主事件。

## 业务约定

- `remember` 默认产生 candidate。
- `confirm` 才能进入 active 和 Markdown。
- `recall` 默认只返回 active，并经过门卫预算。
- `forget` 保留原文，只标记 obsolete。
- `checkpoint` 保存压缩恢复所需状态。
- `recall_evidence` 返回包含原文、来源、OCR、视觉摘要和结构化事实的统一证据。
- `recall_structured` / `compare_structured` 只按结构化 OCR 事实判断状态，不把普通文本命中当成事实。
- `config_status` / `config_history` / `config_diff` 只读配置 manifest，不修改记忆库。

## 后端演进

先稳定 stdio 和 MemoryService，再增加 HTTP API。HTTP 层只调用 MemoryService，不直接访问 SQLite；前端和其他客户端都走同一业务边界。

## Secretary 派生证据

recall_evidence 新增 secretary_evidence：uncertainty、summary、provider、result、is_verified。它说明秘书草稿及其疑问，不是原文事实核实；is_verified 固定为 false，确认记忆不代表模型草稿已被核实。旧记录无审计时 uncertainty 为 unknown。审计只关联本次身份过滤后命中的记录。

Evidence 新增 match_reason：literal_query 表示原查询字面命中，term_fallback 表示拆词回退，并列出实际命中的 terms；structured_state_verified 固定 false。查询路由 route_reason 不是命中解释；开关判断继续使用结构化事实。
`n服务层融合权重优先级：recall(weights=...) > manifest retrieval.weights > QueryPlanner 路由权重。配置权重直接替代路由数值，不与路由相乘；route_reason仍说明查询类型，weight_source说明实际权重来源。Evidence返回route_weights与weight_source。当前显式weights仅服务层支持，MCP/HTTP尚未暴露。权重须为正有限数字。
MCP recall/recall_evidence与HTTP search/evidence现已支持text_weight/vector_weight：两者省略采用配置，同时提供时覆盖；单边或非正有限值返回INVALID_WEIGHTS（HTTP 422）。真实stdio复测命令：python scripts/check_mcp_weights.py，使用临时库，不加载嵌入模型；排序验证由固定向量单测覆盖。
