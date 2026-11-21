import { FormEvent, useState } from 'react'
import { api, ApiError, Evidence } from '../api'
import { Empty, EvidenceCard, WORKSPACE } from '../components'
import { FamilyMember } from '../mock'

const SUGGESTIONS = ['心海', '配置回滚', 'Block Outbound', '回忆录']

export default function SeaPage({ member }: { member: FamilyMember }) {
  const [q, setQ] = useState('')
  const [expand, setExpand] = useState(false)
  const [rows, setRows] = useState<Evidence[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function search(text: string) {
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.evidence(
        text.trim(),
        { agent_id: member.agentId, workspace_id: WORKSPACE, branch_id: member.branchId },
        expand ? { expand_source: true } : {},
      )
      setRows(result)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '后端没有连上，确认演示后端已经启动')
      setRows(null)
    } finally {
      setLoading(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    search(q)
  }

  return (
    <section>
      <div className="hero">
        <p className="eyebrow">Memory · 潮汐之下</p>
        <h1 className="hero-title">在心海里找一段记忆</h1>
        <p>
          当前以 <strong>{member.name}</strong> 的身份，只在分支 <code>{member.branchId}</code> 里查找。
          结果先给原文，再说明是怎么找到的。
        </p>
        <form className="searchbar" onSubmit={onSubmit}>
          <span className="ripple ripple-1" aria-hidden />
          <span className="ripple ripple-2" aria-hidden />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="输入关键词、标签或一句话"
            autoFocus
          />
          <button className="primary" disabled={loading}>
            {loading ? '查找中…' : '查找'}
          </button>
        </form>
        <div className="hero-row">
          <label className="toggle">
            <input type="checkbox" checked={expand} onChange={(e) => setExpand(e.target.checked)} />
            连同一来源的其他段落一起带出
          </label>
          <div className="suggest">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                className="ghost small"
                onClick={() => {
                  setQ(s)
                  search(s)
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      {rows === null && !error && (
        <Empty title="海面很平静">输入一个词开始。拆词命中和语义相近的结果会单独标出来，不当成确定的结论。</Empty>
      )}
      {rows !== null && rows.length === 0 && (
        <Empty title="这个分支里没有找到">换个说法，或切换到别的家人的分支看看。</Empty>
      )}
      {rows !== null && rows.length > 0 && (
        <div className="list">
          <div className="list-head">找到 {rows.length} 条</div>
          {rows.map((r) => (
            <EvidenceCard key={r.record_id} item={r} />
          ))}
        </div>
      )}
    </section>
  )
}
