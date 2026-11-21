import { FormEvent, useState } from 'react'
import { api, ApiError, Checkpoint } from '../api'
import { MockBadge } from '../components'
import { FamilyMember } from '../mock'

export default function CheckpointPage({ member }: { member: FamilyMember }) {
  const [goal, setGoal] = useState('')
  const [pending, setPending] = useState('')
  const [unknown, setUnknown] = useState('')
  const [next, setNext] = useState('')
  const [saved, setSaved] = useState<Checkpoint[]>([])
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const row = await api.checkpoint({
        // TODO(session): 这是分支 id，不是会话 id。接口要求真实 session_id（min_length=1），
        // 拿它冒充会查不到该查的东西。等有了会话来源（导入管道 / 会话表）就换掉 —— 见交接单 08 第七节第 5 条。
        session_id: member.branchId,
        goal: goal.trim(),
        pending: split(pending),
        unknown: split(unknown),
        next_step: next.trim() || undefined,
      })
      setSaved([row, ...saved])
      setGoal('')
      setPending('')
      setUnknown('')
      setNext('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '没有保存成功')
    }
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>检查点</h1>
          <p>
            记下这一轮的目标、还没做的和还不知道的，新伙伴进来能接着做。
            <MockBadge /> 历史接口已存在（<code>GET /checkpoints</code>），但需要真实会话 id 才查得到；
            这里只显示本次打开页面后记下的。
          </p>
        </div>
      </div>
      <form className="card form" onSubmit={submit}>
        <label>
          目标
          <input className="field" value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="这一轮要完成什么" />
        </label>
        <label>
          还没做的（一行一件）
          <textarea className="field" value={pending} onChange={(e) => setPending(e.target.value)} />
        </label>
        <label>
          还不知道的（一行一件）
          <textarea className="field" value={unknown} onChange={(e) => setUnknown(e.target.value)} />
        </label>
        <label>
          下一步
          <input className="field" value={next} onChange={(e) => setNext(e.target.value)} />
        </label>
        <button className="primary" disabled={!goal.trim()}>
          记下检查点
        </button>
        {error && <div className="alert">{error}</div>}
      </form>
      <div className="list" style={{ marginTop: 14 }}>
        {saved.map((c) => (
          <article key={c.id} className="card">
            <header className="evidence-head">
              <span className="chip layer-tag">{c.session_id}</span>
              <span className="muted">{new Date(c.created_at).toLocaleString('zh-CN')}</span>
            </header>
            <p className="original">{c.goal}</p>
            {c.pending.length > 0 && <p>还没做：{c.pending.join('、')}</p>}
            {c.unknown.length > 0 && <p className="care" style={{ padding: '4px 10px', borderRadius: 999 }}>还不知道：{c.unknown.join('、')}</p>}
            {c.next_step && <p className="muted">下一步：{c.next_step}</p>}
          </article>
        ))}
      </div>
    </section>
  )
}

function split(text: string) {
  return text.split(/\n+/).map((s) => s.trim()).filter(Boolean)
}
