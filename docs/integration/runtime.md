# MCP 后端运行时

心海 MCP Server 支持通过环境变量隔离数据：

- `XINHAI_ROOT`：工程根目录
- `XINHAI_DB`：SQLite 文件
- `XINHAI_LAYERS`：memory_layers.yaml
- `XINHAI_MARKDOWN_ROOT`：Markdown 回填根目录
- `XINHAI_MODEL_PROVIDER=ollama`：显式启用本地 Ollama 记忆秘书；未设置时保持规则版
- `XINHAI_OLLAMA_MODEL`：模型名，默认 `qwen2.5vl:3b`
- `XINHAI_OLLAMA_HOST`：Ollama 地址，默认 `http://127.0.0.1:11434`
- `XINHAI_VECTOR_CANDIDATE_LIMIT`：向量融合前候选上限，默认 `1000`；最终返回仍受调用方 `limit` 限制
- `XINHAI_EMBEDDING_PROVIDER=sentence-transformers`：显式启用本地文本向量；默认关闭
- `XINHAI_EMBEDDING_MODEL`：embedding 模型名，默认 `BAAI/bge-m3`

客户端测试和生产运行应使用不同的数据库路径。MCP Server 本身不读取当前宿主聊天历史，只有工具调用才会进入 MemoryService。
测试结束或服务关闭时应调用 `MemoryService.close()`，释放 SQLite 连接，避免 Windows 临时目录或数据库文件被锁定。

## HTTP API

当前 HTTP 接口：

- `GET /health`
- `POST /memories`
- `POST /memories/confirm`
- `GET /memories/search`
- `POST /memories/auto-recall`
- `GET /memories`
- `POST /memories/forget`
- `POST /checkpoints`

`GET /memories/search` 支持 `modality`、`source_id` 和 `expand_source`；MCP `recall` 使用同名参数。`expand_source` 默认关闭，开启后会在 Gatekeeper 后展开同一来源的切片。

`POST /memories/auto-recall` 的请求体支持 `text`、`agent_id`、`workspace_id`、`branch_id`、`session_id`、`thread_id`、`task_id` 和 `scope`；字段会原样进入自动召回和服务端身份过滤。MCP `auto_recall` 使用同一组身份字段。

示例请求：

```json
{
  "text": "继续刚才的工作",
  "agent_id": "cursor",
  "workspace_id": "deepsea",
  "branch_id": "GO-CURSOR-A",
  "session_id": "session-1",
  "thread_id": "thread-1",
  "task_id": "task-1",
  "scope": "personal"
}
```

HTTP 层只调用 MemoryService。SQLite 连接允许 FastAPI 线程池访问；并发写入仍需在后续压力测试中验证。

## HTTP 错误契约

错误统一返回：

```json
{"ok":false,"error":{"code":"RECORD_NOT_FOUND","message":"...","retryable":false,"request_id":"...","record_id":"..."}}
```

当前已定义 `RECORD_NOT_FOUND`、`SCOPE_DENIED`、`DATABASE_BUSY` 等错误类型。客户端可按 `retryable` 决定是否重试。

## 本机已验证的 BGE-M3 离线路径（2026-11-10）

Cursor 验收进程设置如下环境变量，无需再次下载：

```text
XINHAI_EMBEDDING_PROVIDER=sentence-transformers
XINHAI_EMBEDDING_MODEL=D:\AI\DeepSea · 基于RAG+Agent构建的云端长期记忆库平台\DeepSea\data\models\huggingface\hub\models--BAAI--bge-m3\snapshots\5617a9f61b028005a4858fdac845db406aefb181
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

使用 C:\AcoPythonlab\python.exe 已验证严格离线加载和编码，输出 shape=(1,1024)。另一个仅含 model.safetensors 的快照不是完整加载目录，不要单独指向它。当前默认缓存与 DeepSea 专用缓存不同；找不到默认缓存不等于本机没有模型。既有记录不会自动补向量，验收需写入新的隔离样本。
向量质量过滤：XINHAI_VECTOR_MIN_SIMILARITY 为可选 [-1,1] 原始余弦相似度下限，未设置时关闭；过滤在 RRF 前执行，只影响向量路，FTS 精确命中保留。0.8 仅用于确定性测试，不是 BGE-M3 生产推荐值。阈值需按相关/无关真实样本校准。
软门控第一版：recall 每条返回新增 vector_similarity、quality_status、quality_reason、retrieval_channels。XINHAI_VECTOR_REVIEW_BELOW 默认0.55，仅将低分标记 needs_verification，不丢弃、不改变融合排序；高分仍为 candidate，并非已核验。这里的candidate是召回质量标记，不是数据库status。显式硬过滤 XINHAI_VECTOR_MIN_SIMILARITY 仍可用，测试软门控前应移除此变量。此版未实现上下文充分性判定或模型复核，也不把无关记录自动判定为应删除。
候选审核列表：GET /memories 支持 limit、branch_id、status(candidate/active/obsolete)、layer_id、tag、agent_id、workspace_id、scope；过滤条件按AND组合，tag精确匹配。原文保留于text。此为调用方过滤，不是用户鉴权；未传身份条件不会自动绑定用户。
检查点历史通过 GET /checkpoints?session_id=<实际会话ID>&thread_id=<可选线程ID>&limit=50 读取。按最新优先排序，limit 取 1 到 200。前端使用实际会话 ID，分支 ID 应单独保存。接口用于本地可信调用，session_id 是查询条件。

## 记忆维护

以下 HTTP 操作用于本地受信任的维护流程。请求需明确给出 workspace_id、agent_id、branch_id 和 scope（默认 personal）。这些字段限定操作范围，客户端鉴权由部署层提供。

- POST /memory-maintenance/vectors 按记录 ID 分页重算当前索引中的向量。提供 limit 和上页返回的 next_after 继续。逐条返回 ready 或 pending，失败时可重跑该页。该入口复用已配置的 Embedding 和现有索引，切换模型或维度需要单独迁移。
- POST /memory-maintenance/{record_id}/summary-drafts 从指定原文记录生成候选摘要。相同 request_id 可重试并复用草稿。候选稿关联原文字符范围，核验状态和不确定性随审计保留。
- POST /memory-maintenance/{record_id}/supersede 提供 replacement_id 和 reason，确认候选替换当前正式记录。事务同时更新两条记录的状态并追加 supersedes 关系。旧正文可从历史回读。
- 导入草稿确认时写入 covers 关系，关联导入任务及相应的原文或消息字符范围。已确认的旧草稿可再次确认以补齐该关系。
- POST /memory-maintenance/{record_id}/verify 提供同范围独立记录的 evidence_id、verifier、conclusion 和 reason，写入核验审计。conclusion 接受 supported、contradicted、inconclusive。此处保存提交者声明的结论，已有召回质量标记按既有规则生成。
- GET /memory-maintenance/{record_id} 带同样的范围参数，读取版本、覆盖关系和核验记录。

### 多来源覆盖、MCP 与审核页

- POST /memory-maintenance/{record_id}/covers 为派生摘要追加来源。sources 中每项提供 record_id、start、end。范围以 Unicode 字符计，为左闭右开区间。同分支且同 scope 的来源可一次提交，多段和重复重试均保留一份对应范围，任一来源校验失败会撤销整批。
- MCP 暴露 rebuild_vectors、rebuild_summary、supersede、cover_memory、verify_memory、memory_provenance。写操作的 body 结构与 HTTP 请求体一致。
- 审核页的「版本、来源与核验」读取同一追溯接口。展开后显示版本关系、覆盖范围及核验依据。

### 在独立副本上迁移向量模型

从 DeepSea 工程目录，在可导入 xinhai 的 Python 环境运行 scripts/migrate_vector_index.py，依次提供源 SQLite 文件、尚不存在的目标文件及 --model 本地模型目录。脚本使用 SQLite 在线备份取得一致副本，在目标目录的临时文件中重建 active 和 candidate 记录的向量。索引计数及完整性检查通过后发布目标文件。目标目录所在文件系统需支持硬链接。

切换前在隔离环境配对新库和目标 Embedding 模型验收召回。副本取自备份时点，涉及正式切换时应停止写入后取得最终副本并保留旧库，以供回退。
