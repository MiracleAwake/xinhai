import { useEffect, useState } from 'react'
import { api } from './api'
import { DemoUser, FAMILY, FamilyMember, loadUser, saveUser } from './mock'
import { MockBadge } from './components'
import SeaPage from './pages/SeaPage'
import ReviewPage from './pages/ReviewPage'
import FamilyPage from './pages/FamilyPage'
import WelcomePage from './pages/WelcomePage'
import SwitchesPage from './pages/SwitchesPage'
import ConfigPage from './pages/ConfigPage'
import CheckpointPage from './pages/CheckpointPage'

type Tab = 'sea' | 'review' | 'switches' | 'config' | 'checkpoint' | 'family'

const TABS: { id: Tab; label: string }[] = [
  { id: 'sea', label: '记忆海面' },
  { id: 'review', label: '候选审核' },
  { id: 'switches', label: '截图与开关' },
  { id: 'config', label: '配置' },
  { id: 'checkpoint', label: '检查点' },
  { id: 'family', label: '家庭组' },
]

export default function App() {
  const [user, setUser] = useState<DemoUser | null>(loadUser)
  const [tab, setTab] = useState<Tab>('sea')
  const [members, setMembers] = useState<FamilyMember[]>(FAMILY)
  const [current, setCurrent] = useState<FamilyMember>(FAMILY[0])
  const [online, setOnline] = useState<boolean | null>(null)

  useEffect(() => {
    api.health().then(() => setOnline(true)).catch(() => setOnline(false))
  }, [])

  if (!user) {
    return (
      <WelcomePage
        onEnter={(u) => {
          saveUser(u)
          setUser(u)
        }}
      />
    )
  }

  return (
    <div className="shell">
      <div className="sea-surface" aria-hidden />
      <div className="orb orb-1" aria-hidden />
      <div className="orb orb-2" aria-hidden />
      <div className="orb orb-3" aria-hidden />
      <header className="topbar">
        <div className="glass nav-pill">
        <div className="brand">
          <span className="brand-mark" aria-hidden>◐</span>
          <div>
            <div className="brand-name">心海</div>
            <div className="brand-sub">{user.family}</div>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button key={t.id} className={tab === t.id ? 'tab active' : 'tab'} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="topbar-right">
          <label className="identity">
            <span>以谁的身份</span>
            <select
              value={current.id}
              onChange={(e) => setCurrent(members.find((m) => m.id === e.target.value) ?? members[0])}
            >
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} · {m.branchId}
                </option>
              ))}
            </select>
          </label>
          <span className={online ? 'status ok' : online === false ? 'status down' : 'status'}>
            {online ? '后端在线' : online === false ? '后端未连接' : '检查中'}
          </span>
          <button
            className="ghost small"
            onClick={() => {
              saveUser(null)
              setUser(null)
            }}
          >
            {user.name} · 退出
            <MockBadge />
          </button>
        </div>
        </div>
      </header>
      <main className="content">
        {/* 每页都要带 key：换人时不重建，上一位的结果会留在页面上 */}
        {tab === 'sea' && <SeaPage key={current.id} member={current} />}
        {tab === 'review' && <ReviewPage key={current.id} member={current} />}
        {tab === 'switches' && <SwitchesPage key={current.id} member={current} />}
        {tab === 'config' && <ConfigPage />}
        {tab === 'checkpoint' && <CheckpointPage key={current.id} member={current} />}
        {tab === 'family' && (
          <FamilyPage
            members={members}
            onAdd={(m) => {
              setMembers((prev) => [...prev, m])
              setCurrent(m)
            }}
          />
        )}
      </main>
    </div>
  )
}
