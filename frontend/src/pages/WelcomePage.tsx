import { FormEvent, useState } from 'react'
import { MockBadge } from '../components'
import { DemoUser } from '../mock'

export default function WelcomePage({ onEnter }: { onEnter: (u: DemoUser) => void }) {
  const [name, setName] = useState('')
  const [family, setFamily] = useState('Sweet Home')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (name.trim()) onEnter({ name: name.trim(), family: family.trim() || 'Sweet Home' })
  }

  return (
    <div className="welcome">
      <div className="welcome-sea" aria-hidden />
      <form className="card welcome-card" onSubmit={submit}>
        <div className="brand-mark big" aria-hidden>◐</div>
        <h1>心海</h1>
        <p className="muted">给 AI 伙伴的长期记忆。原文是真相，不确定的地方说出来。</p>
        <label>
          你的名字
          <input className="field" value={name} onChange={(e) => setName(e.target.value)} placeholder="比如：搭档" autoFocus />
        </label>
        <label>
          家庭组
          <input className="field" value={family} onChange={(e) => setFamily(e.target.value)} />
        </label>
        <button className="primary wide" disabled={!name.trim()}>
          注册并进入
        </button>
        <p className="small muted">
          <MockBadge /> 账号只存在这台浏览器里，没有密码，也不会发到后端。
        </p>
      </form>
    </div>
  )
}
