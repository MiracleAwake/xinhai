import { useEffect, useState } from 'react'
import { api, ApiError, ConfigStatus, ConfigVersion } from '../api'
import { Empty } from '../components'

export default function ConfigPage() {
  const [current, setCurrent] = useState<ConfigStatus | null>(null)
  const [history, setHistory] = useState<ConfigVersion[]>([])
  const [older, setOlder] = useState('')
  const [newer, setNewer] = useState('')
  const [diff, setDiff] = useState<Record<string, { from: unknown; to: unknown }> | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.configCurrent(), api.configHistory()])
      .then(([c, h]) => {
        setCurrent(c)
        setHistory(h)
        if (h.length >= 2) {
          setOlder(h[1].version)
          setNewer(h[0].version)
        }
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : '后端没有连上'))
  }, [])

  async function loadDiff() {
    setError(null)
    try {
      setDiff(await api.configDiff(older, newer))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '对比失败')
    }
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>配置</h1>
          <p>只读。修改、激活和回滚仍在本机用脚本完成，这里只看结果。敏感值显示为 [REDACTED]。</p>
        </div>
      </div>
      {error && <div className="alert">{error}</div>}
      {current && !current.configured && <Empty title="还没有激活的配置" />}
      {current?.configured && (
        <article className="card" style={{ marginBottom: 14 }}>
          <div className="chips">
            <span className="chip layer-tag">{current.version}</span>
            <span className="chip ok">{current.validation_status}</span>
            <span className="chip soft">{current.scope}</span>
          </div>
          <p className="muted">当前配置 · {current.config_id}</p>
        </article>
      )}
      {history.length > 0 && (
        <div className="list" style={{ marginBottom: 14 }}>
          {history.map((v) => (
            <article key={v.config_id} className="card">
              <header className="evidence-head">
                <div className="chips">
                  <span className="chip layer-tag">{v.version}</span>
                  <span className="chip soft">{v.author}</span>
                </div>
                <span className="muted">{new Date(v.created_at).toLocaleString('zh-CN')}</span>
              </header>
              <p>{v.reason || '没有填写原因'}</p>
              <p className="small muted">
                父版本 {v.parent_version ?? '无'} · 校验 {v.checksum.slice(0, 12)}
              </p>
            </article>
          ))}
        </div>
      )}
      {history.length >= 2 && (
        <article className="card">
          <h3>版本差异</h3>
          <div className="actions">
            <select className="field" style={{ width: 'auto' }} value={older} onChange={(e) => setOlder(e.target.value)}>
              {history.map((v) => (
                <option key={v.version}>{v.version}</option>
              ))}
            </select>
            <span className="muted">对比</span>
            <select className="field" style={{ width: 'auto' }} value={newer} onChange={(e) => setNewer(e.target.value)}>
              {history.map((v) => (
                <option key={v.version}>{v.version}</option>
              ))}
            </select>
            <button className="primary" onClick={loadDiff}>
              查看差异
            </button>
          </div>
          {diff && Object.keys(diff).length === 0 && <p className="muted">这两个版本没有差异。</p>}
          {diff &&
            Object.entries(diff).map(([key, change]) => (
              <div key={key} className="diff">
                <strong>{key}</strong>
                <pre>{JSON.stringify(change.from, null, 2)}</pre>
                <pre>{JSON.stringify(change.to, null, 2)}</pre>
              </div>
            ))}
        </article>
      )}
    </section>
  )
}
