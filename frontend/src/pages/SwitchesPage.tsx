import { useEffect, useState } from 'react'
import { api, ApiError, CompareSide } from '../api'
import { Empty } from '../components'
import { FamilyMember } from '../mock'

export default function SwitchesPage({ member }: { member: FamilyMember }) {
  const identity = { agent_id: member.agentId, branch_id: member.branchId }
  const [groups, setGroups] = useState<Record<string, { enabled_true?: CompareSide[]; enabled_false?: CompareSide[] }> | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setGroups(null)
    api.compare(identity).then(setGroups).catch((e) => setError(e instanceof ApiError ? e.message : '后端没有连上'))
    // identity is rebuilt each render; member is the real dependency
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [member])

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>截图与开关</h1>
          <p>开关只认结构化审计。搜索命中某个词，不代表规则已经打开或关闭。</p>
        </div>
      </div>
      {error && <div className="alert">{error}</div>}
      {groups && Object.keys(groups).length === 0 && (
        <Empty title={`${member.name} 的分支还没有结构化记录`}>带 OCR 的截图入库后，规则会出现在这里。</Empty>
      )}
      {groups &&
        Object.entries(groups).map(([name, sides]) => (
          <article key={name} className="card" style={{ marginBottom: 14 }}>
            <h3>{name}</h3>
            <div className="split">
              <Side title="已启用" tone="on" rows={sides.enabled_true ?? []} />
              <Side title="未启用" tone="off" rows={sides.enabled_false ?? []} />
            </div>
          </article>
        ))}
    </section>
  )
}

function Side({ title, tone, rows }: { title: string; tone: 'on' | 'off'; rows: CompareSide[] }) {
  return (
    <div className={`side ${tone}`}>
      <header>
        {title}
        <span>{rows.length}</span>
      </header>
      {rows.length === 0 && <p className="muted">没有</p>}
      {rows.map((r) => (
        <div key={r.record_id} className="side-row">
          <code>{r.evidence}</code>
          <span className="muted">{r.branch_id}</span>
        </div>
      ))}
    </div>
  )
}
