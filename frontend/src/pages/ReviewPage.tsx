import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, MemoryProvenance, MemoryRecord, parseTags } from '../api'
import { Empty, WORKSPACE } from '../components'
import { DEFAULT_LAYERS, FamilyMember } from '../mock'

type StatusFilter = 'candidate' | 'active' | 'obsolete'

const STATUS_LABEL: Record<StatusFilter, string> = { candidate: '待确认', active: '已确认', obsolete: '已废弃' }

function layerName(id: string | null) {
  return DEFAULT_LAYERS.find((l) => l.id === id)?.name ?? id ?? '未分层'
}

const CONCLUSIONS: Record<string, string> = {
  supported: '证据支持', contradicted: '证据反驳', inconclusive: '尚无结论',
}

function Provenance({ record }: { record: MemoryRecord }) {
  const [value, setValue] = useState<MemoryProvenance | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { id, workspace_id, agent_id, branch_id, scope } = record
  if (!workspace_id || !agent_id || !branch_id) return null
  const identity = { workspace_id, agent_id, branch_id, scope }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setValue(await api.memoryProvenance(id, identity))
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : '无法读取追溯记录')
    } finally {
      setLoading(false)
    }
  }

  return (
    <details className="memory-provenance" onToggle={(event) => {
      if (event.currentTarget.open && !loading && !value && !error) void load()
    }}>
      <summary>版本、来源与核验</summary>
      {loading && <p className="muted" role="status">读取中…</p>}
      {error && <p role="alert">{error} <button className="ghost" onClick={() => void load()}>重试</button></p>}
      {value && value.relations.length === 0 && value.events.length === 0 && (
        <p className="muted">暂无追溯记录。</p>
      )}
      {value && (value.relations.length > 0 || value.events.length > 0) && (
        <ul>
          {value.relations.map(({ from_id, to_id, type, metadata }) => {
            const start = metadata.start ?? metadata.message_start
            const end = metadata.end ?? metadata.message_end
            const ranges = metadata.ranges ?? (start !== undefined && end !== undefined ? [{ start, end }] : [])
            return (
              <li key={`${from_id}-${type}-${to_id}`}>
                {type === 'covers' ? '覆盖来源 ' : from_id === id ? '替代旧版 ' : '新版记录 '}
                <code>{type === 'supersedes' && from_id !== id ? from_id : to_id}</code>
                {ranges.length > 0 && ` · 字符区间 ${ranges.map((range) => `[${range.start}, ${range.end})`).join('、')}`}
                {metadata.source_line !== undefined && ` · 原文第 ${metadata.source_line} 行`}
                {metadata.reason && ` · ${metadata.reason}`}
              </li>
            )
          })}
          {value.events.map(({ action, actor, created_at, details }, index) => (
            <li key={`${action}-${created_at}-${index}`}>
              {action === 'verify' ? (CONCLUSIONS[details.conclusion ?? ''] ?? '核验记录') : '摘要重建'}
              {' · '}{actor}
              {details.evidence_id && <> · 证据 <code>{details.evidence_id}</code></>}
              {details.reason && ` · ${details.reason}`}
              {details.uncertainty && ` · ${details.uncertainty}`}
            </li>
          ))}
        </ul>
      )}
    </details>
  )
}

export default function ReviewPage({ member }: { member: FamilyMember }) {
  const [status, setStatus] = useState<StatusFilter>('candidate')
  const [rows, setRows] = useState<MemoryRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [forgetting, setForgetting] = useState<string | null>(null)
  const [reason, setReason] = useState('')

  const load = useCallback(async () => {
    setError(null)
    setRows(null)
    try {
      setRows(await api.list({ status, agent_id: member.agentId, workspace_id: WORKSPACE, branch_id: member.branchId, limit: 100 }))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '后端没有连上')
      setRows([])
    }
  }, [status, member])

  useEffect(() => {
    load()
  }, [load])

  async function confirm(id: string) {
    await api.confirm(id)
    load()
  }

  async function forget(id: string) {
    if (!reason.trim()) return
    await api.forget(id, reason.trim())
    setForgetting(null)
    setReason('')
    load()
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>候选审核</h1>
          <p>秘书收进来的记忆先是候选。确认后才算正式记忆；废弃要写理由，原文不会删除。</p>
        </div>
        <div className="segmented">
          {(Object.keys(STATUS_LABEL) as StatusFilter[]).map((s) => (
            <button key={s} className={status === s ? 'active' : ''} onClick={() => setStatus(s)}>
              {STATUS_LABEL[s]}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="alert">{error}</div>}
      {rows === null && !error && <p className="muted">读取中…</p>}
      {!error && rows?.length === 0 && <Empty title={`${member.name} 的分支里没有${STATUS_LABEL[status]}的记忆`} />}

      <div className="list">
        {rows?.map((r) => (
          <article key={r.id} className={`card record ${r.status}`}>
            <header className="evidence-head">
              <div className="chips">
                <span className="chip layer-tag">{layerName(r.layer_id)}</span>
                {parseTags(r)
                  .filter((t) => !t.startsWith('layer:') && !t.startsWith('event:'))
                  .map((t) => (
                    <span key={t} className="chip soft">
                      {t}
                    </span>
                  ))}
              </div>
              <div className="meta">
                <span>{new Date(r.ts).toLocaleString('zh-CN')}</span>
              </div>
            </header>
            <p className="original">{r.text}</p>
            {r.obsolete_reason && <p className="muted">废弃理由：{r.obsolete_reason}</p>}
            <Provenance record={r} />

            {r.status === 'candidate' && (
              <footer className="actions">
                {forgetting === r.id ? (
                  <>
                    <input
                      className="reason"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="为什么不收这一条？"
                      autoFocus
                    />
                    <button className="danger" disabled={!reason.trim()} onClick={() => forget(r.id)}>
                      确认废弃
                    </button>
                    <button className="ghost" onClick={() => setForgetting(null)}>
                      取消
                    </button>
                  </>
                ) : (
                  <>
                    <button className="primary" onClick={() => confirm(r.id)}>
                      确认收录
                    </button>
                    <button className="ghost" onClick={() => setForgetting(r.id)}>
                      不收
                    </button>
                  </>
                )}
              </footer>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
