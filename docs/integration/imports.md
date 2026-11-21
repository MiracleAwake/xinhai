# 分层与通用文本导入（本地原型）

身份参数 workspace_id、agent_id 是调用方过滤，不是认证。当前仅用于受信任本地原型。浏览器提交文件名和完整UTF-8文本content，不允许传服务器路径读取文件。

- POST /layers：workspace_id、agent_id、name、description、prompt、tags、keywords；初始draft。
- GET /layers?workspace_id=&agent_id=：查看自定义层。
- POST /layers/{id}/confirm?workspace_id=&agent_id=：激活关键词规则。prompt仅保存，尚不执行语义规则。
- POST /imports：workspace_id、agent_id、branch_id、session_id、client_type、filename、content；先完整归档，返回id。
- GET /imports?workspace_id=&agent_id=：任务列表，含失败项。
- GET /imports/{id}?workspace_id=&agent_id=：状态、错误类型、record_id、段落完成数/总数。
- GET /imports/{id}/original?workspace_id=&agent_id=：原文与哈希。
- POST /imports/{id}/process?workspace_id=&agent_id=：同步执行/重试，已完成段不重复处理。
- POST /imports/{id}/start?workspace_id=&agent_id=：202提交进程内后台处理；不是持久队列，重启后须手动重试。
- GET /imports/{id}/drafts?workspace_id=&agent_id=：段落草稿、标签、层引用、原文字符[start_offset,end_offset)与来源id。

无模型时明确返回verbatim_excerpt原文摘录，不能称模型总结；配置模型时为model_draft。所有派生结果均draft且is_verified=false，多层关键词可同时命中。未匹配时layer_ids为空。当前按500字符切片，尚不是客户端事件/分支解析器。

限制：默认模板安装、自定义层语义分类、版本审批审计、草稿确认成文、持久异步队列、真实客户端接入探针和ZCode格式适配仍待实现。completed仅表示当前原型归档与派生步骤结束，不代表上述完整产品能力完成。

CORS用XINHAI_CORS_ORIGINS配置逗号分隔的明确来源；默认不开跨域，不接受星号。
Codex/Cursor可提交format=xinhai-session-v1的显式交换文件，content为JSON，包含format、client_type、messages数组，每条含speaker(user/assistant/tool/system)和text；额外字段保留。当前仅校验格式并完整归档，尚未将messages映射到独立事件记录，段落偏移仍指向原JSON字符。客户端私有会话数据库/原生文件格式仍未适配，不能把交换格式称为真实原生导入。
交换格式摘要现在按消息切片：明确duplicate/transient排除，needs_review保留。draft.source包含message_index、message_start/message_end、speaker、screen_status与offset_basis=message_text；外层start_offset/end_offset仅为派生流位置，不得用于切原JSON。普通text格式仍为archive_text偏移。此前已完成任务不自动重算旧草稿。
新增POST /layers/install-defaults?workspace_id=&agent_id=，幂等安装五层draft；新增POST /imports/{id}/drafts/{offset}/confirm确认草稿为可检索派生记录（仍is_verified=false），GET /layers/{id}/document读取确认段落及来源。分层文档目前为结构化sections，不是磁盘Markdown。
队列更新：POST /imports/{id}/start现在只持久入SQLite队列，返回queued，不再立即后台执行。使用相同XINHAI_DB等环境运行python scripts/import_worker.py单次消费。仅支持单worker，不是跨进程并发队列；进程中断时queued保留，已完成段跳过。failed任务检查后可再次start重试，状态接口含queue_state。
预防性加固：worker通过SQLite条件更新领取1800秒租约并记录attempts；有效租约时跳过，重复start返回409；租约过期后可领取processing任务。此为基础恢复机制，尚无执行中续租/每段写入fencing，因此仍限定单worker，长任务超过租约及多进程真实竞争尚未验收。直接/process是同步维护入口，不应与worker并发调用。
新导入归档前用 SQLite Backup API 创建数据库旁 import-snapshots/<job_id>.sqlite 并执行 quick_check。快照失败返回 503。重复提交沿用原任务。确认原文、派生结果及原有记录无误后，才可手动删除对应快照。恢复先在独立位置打开或恢复副本核对，勿直接覆盖运行中的库或丢弃快照以后其他写入。此快照覆盖 SQLite，不含外部文件。早期任务如没有快照，正式继续处理前先另做备份。
早期归档任务若缺快照，处理入口会先生成处理前快照。失败时任务标记 failed / SnapshotFailed，可修复后重试。新生成的快照先在同目录临时文件中完成备份和完整性检查，再发布正式文件名。
处理前以只读方式检查已有快照的 SQLite 完整性和 records 表。损坏快照保留供排查，任务标记 SnapshotFailed。提供有效快照后可重试。
同步 /process 与队列 worker 共用任务租约。已有有效租约时同步入口返回 409。租约到期后的旧进程写入保护仍待实现。
导入在数据库写入前校验租约所有者与有效期，并在同一事务续期。模型返回后如租约已失效，旧执行者停止写入，直接处理返回 409。续期发生在写入边界，单次模型调用期间没有后台心跳。
Codex 原生文本首版使用 client_type=codex 和 format=codex-session-jsonl。保留完整上传原文与快照，派生只取 response_item 中的用户和助手文本，草稿 source_line 为原文件行号。身份由请求指定，工具事件与图片仍留在原件。当前适配基于本机样本结构只读核对及合成文件联测。
GET /layers/{layer_id}/document 接受可选 branch_id；省略仍返回该伙伴的汇总。按分支浏览时请传实际 branch_id。

### 跟随指定 Codex 线程的已完成问答

准备隔离的心海 HTTP 服务和可读取指定线程的本机 Codex App Server。安装项目的 `codex-capture` 可选依赖后，从 DeepSea 工程目录运行以下示例。将地址和标识替换成该次隔离试用的实际值。

```text
python scripts/import_codex_app_capture.py --follow --app-server ws://127.0.0.1:45123 --endpoint http://127.0.0.1:45124 --thread-id <thread-id> --workspace-id rehearsal --agent-id codex --branch-id probe
```

该命令启动时读取一次历史，此后约每 15 秒查询一次。每轮读取指定线程里可见的已完成轮次。归档成功时输出轮次、消息及导入任务 ID。若客户端另有持续追加的 JSONL 日志，可把日志路径作为位置参数加入同一命令，以便完成事件到达时直接归档。

只用历史跟随时，可恢复的内容取决于宿主持久化的已完成文本。中断前缀和非文本附件需要另有采集来源。
