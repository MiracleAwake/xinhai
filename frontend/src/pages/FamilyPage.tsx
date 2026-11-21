import { useMemo, useState } from 'react'
import { api } from '../api'
import { MockBadge, WORKSPACE } from '../components'
import { CLIENTS, ClientKind, DEFAULT_LAYERS, draftLayer, FamilyMember, LayerTemplate } from '../mock'

const STEPS = ['选择客户端', '基本信息', '接入 MCP', '记忆分层', '导入对话']

export default function FamilyPage({ members, onAdd }: { members: FamilyMember[]; onAdd: (m: FamilyMember) => void }) {
  const [creating, setCreating] = useState(false)

  if (creating) {
    return (
      <NewMemberWizard
        onCancel={() => setCreating(false)}
        onDone={(m) => {
          onAdd(m)
          setCreating(false)
        }}
      />
    )
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>
            家庭组 <MockBadge />
          </h1>
          <p>每位家人有自己的分支，记忆互不串线。家庭组和账号目前是演示数据。</p>
        </div>
        <button className="primary" onClick={() => setCreating(true)}>
          新建家人
        </button>
      </div>
      <div className="grid">
        {members.map((m) => {
          const client = CLIENTS.find((c) => c.id === m.client)
          return (
            <article key={m.id} className="card member">
              <div className="avatar">{m.name.slice(0, 1)}</div>
              <div className="member-body">
                <h3>{m.name}</h3>
                <p className="muted">{m.intro}</p>
                <div className="chips">
                  <span className="chip soft">{client?.name ?? m.client}</span>
                  <span className="chip branch">{m.branchId}</span>
                  <span className={m.connected ? 'chip ok' : 'chip care'}>{m.connected ? '已接入' : '未确认接入'}</span>
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function NewMemberWizard({ onCancel, onDone }: { onCancel: () => void; onDone: (m: FamilyMember) => void }) {
  const [step, setStep] = useState(0)
  const [search, setSearch] = useState('')
  const [client, setClient] = useState<ClientKind | null>(null)
  const [name, setName] = useState('')
  const [intro, setIntro] = useState('')
  const [probe, setProbe] = useState<'idle' | 'waiting' | 'ok' | 'fail'>('idle')
  const [layers, setLayers] = useState<LayerTemplate[]>(DEFAULT_LAYERS)
  const [draftName, setDraftName] = useState('')
  const [draftIntro, setDraftIntro] = useState('')
  const [draft, setDraft] = useState<LayerTemplate | null>(null)

  const filtered = useMemo(
    () => CLIENTS.filter((c) => `${c.name}${c.vendor}`.toLowerCase().includes(search.toLowerCase())),
    [search],
  )
  const agentId = client?.id ?? ''
  const branchId = name ? `${agentId}-${name}` : ''

  async function checkConnection() {
    setProbe('waiting')
    try {
      const rows = await api.list({ agent_id: agentId, workspace_id: WORKSPACE, branch_id: branchId, limit: 1 })
      setProbe(rows.length > 0 ? 'ok' : 'fail')
    } catch {
      setProbe('fail')
    }
  }

  const canNext = [!!client, !!name.trim(), true, layers.length > 0, true][step]

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>新建家人</h1>
          <p>一步一步把新伙伴接进心海。</p>
        </div>
        <button className="ghost" onClick={onCancel}>
          返回家庭组
        </button>
      </div>

      <ol className="steps">
        {STEPS.map((s, i) => (
          <li key={s} className={i === step ? 'current' : i < step ? 'done' : ''}>
            <span>{i + 1}</span>
            {s}
          </li>
        ))}
      </ol>

      <div className="card wizard">
        {step === 0 && (
          <>
            <input className="field" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索客户端，比如 ZCode" />
            <div className="grid compact">
              {filtered.map((c) => (
                <button key={c.id} className={client?.id === c.id ? 'pick selected' : 'pick'} onClick={() => setClient(c)}>
                  <strong>{c.name}</strong>
                  <span className="muted">{c.vendor}</span>
                </button>
              ))}
            </div>
          </>
        )}

        {step === 1 && (
          <div className="form">
            <label>
              名字
              <input className="field" value={name} onChange={(e) => setName(e.target.value)} placeholder="比如：蒲兰" />
            </label>
            <label>
              简介
              <textarea className="field" value={intro} onChange={(e) => setIntro(e.target.value)} placeholder="她在家里做什么，性格怎样" />
            </label>
            {name && (
              <p className="muted">
                身份会是 <code>agent_id={agentId}</code>，分支 <code>{branchId}</code>。
              </p>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="form">
            <p>
              把下面这段配置加进 {client?.name}。{client?.hint}。
            </p>
            <pre className="code">{mcpSnippet(client?.id ?? '')}</pre>
            <p>
              配好后，请 {name || '她'} 调用一次 <code>remember</code>，带上分支 <code>{branchId}</code>。
              心海能查到这条记录，才算真的接通。
            </p>
            <div className="actions">
              <button className="primary" onClick={checkConnection} disabled={probe === 'waiting'}>
                {probe === 'waiting' ? '查找中…' : '检查是否接通'}
              </button>
              {probe === 'ok' && <span className="chip ok">已在心海里查到她的第一条记录</span>}
              {probe === 'fail' && <span className="chip care">还没查到。可以先跳过，之后再确认</span>}
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="form">
            <p>默认带上知遥的五层模板，也可以加自己的分层。</p>
            <div className="layers">
              {layers.map((l) => (
                <div key={l.id} className={l.builtin ? 'layer' : 'layer custom'}>
                  <div>
                    <strong>{l.name}</strong>
                    <p className="muted">{l.intro}</p>
                    <p className="small">收录：{l.prompt}</p>
                    <div className="chips">
                      {l.tags.map((t) => (
                        <span key={t} className="chip soft">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                  <button className="ghost small" onClick={() => setLayers(layers.filter((x) => x.id !== l.id))}>
                    移除
                  </button>
                </div>
              ))}
            </div>

            <div className="card inset">
              <h3>
                新的分层 <MockBadge />
              </h3>
              <input className="field" value={draftName} onChange={(e) => setDraftName(e.target.value)} placeholder="名称，比如：回忆录" />
              <textarea
                className="field"
                value={draftIntro}
                onChange={(e) => setDraftIntro(e.target.value)}
                placeholder="简介，比如：搭档分享过的歌、诗词，以及我对它们的评价"
              />
              <div className="actions">
                <button className="ghost" disabled={!draftName.trim()} onClick={() => setDraft(draftLayer(draftName.trim(), draftIntro.trim()))}>
                  请秘书起草收录规则
                </button>
              </div>
              {draft && (
                <div className="draft">
                  <span className="chip care">秘书草稿，确认后才生效</span>
                  <label>
                    收录提示词
                    <input className="field" value={draft.prompt} onChange={(e) => setDraft({ ...draft, prompt: e.target.value })} />
                  </label>
                  <label>
                    检索标签（用顿号分隔）
                    <input
                      className="field"
                      value={draft.tags.join('、')}
                      onChange={(e) => setDraft({ ...draft, tags: e.target.value.split(/[、,，]/).filter(Boolean) })}
                    />
                  </label>
                  <button
                    className="primary"
                    onClick={() => {
                      setLayers([...layers, draft])
                      setDraft(null)
                      setDraftName('')
                      setDraftIntro('')
                    }}
                  >
                    确认加入
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="form">
            <h3>
              读取对话原文 <MockBadge />
            </h3>
            <p>
              导入时先把整段对话原文存进心海，再按 {layers.length} 个分层总结、打标签。总结出错也能从原文重做。
            </p>
            <p className="muted">会话导入的后端接口还没有，{client?.name} 的会话格式也要先侦查。这一步现在只做展示。</p>
            <div className="dropzone">把会话文件拖到这里（暂不可用）</div>
          </div>
        )}
      </div>

      <div className="wizard-nav">
        <button className="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>
          上一步
        </button>
        {step < STEPS.length - 1 ? (
          <button className="primary" disabled={!canNext} onClick={() => setStep(step + 1)}>
            下一步
          </button>
        ) : (
          <button
            className="primary"
            onClick={() =>
              onDone({
                id: `${agentId}-${Date.now()}`,
                name: name.trim(),
                client: agentId,
                intro: intro.trim(),
                agentId,
                branchId,
                connected: probe === 'ok',
              })
            }
          >
            完成
          </button>
        )}
      </div>
    </section>
  )
}

function mcpSnippet(client: string) {
  const env = `PYTHONPATH = "<DeepSea>/src"`
  if (client === 'codex') {
    return `[mcp_servers.xinhai_local]\ncommand = "python"\nargs = ["-m", "xinhai.mcp_server"]\n\n[mcp_servers.xinhai_local.env]\n${env}`
  }
  return JSON.stringify(
    { mcpServers: { xinhai: { command: 'python', args: ['-m', 'xinhai.mcp_server'], env: { PYTHONPATH: '<DeepSea>/src' } } } },
    null,
    2,
  )
}
