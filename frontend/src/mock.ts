// Everything in this file is demo data. Pages that read it must show the MockBadge.

export interface ClientKind {
  id: string
  name: string
  vendor: string
  hint: string
}

export interface FamilyMember {
  id: string
  name: string
  client: string
  intro: string
  agentId: string
  branchId: string
  connected: boolean
}

export interface LayerTemplate {
  id: string
  name: string
  intro: string
  prompt: string
  tags: string[]
  builtin: boolean
}

export const CLIENTS: ClientKind[] = [
  { id: 'cursor', name: 'Cursor', vendor: 'Anysphere', hint: '写入 ~/.cursor/mcp.json' },
  { id: 'codex', name: 'Codex', vendor: 'OpenAI', hint: '写入 ~/.codex/config.toml 的 mcp_servers' },
  { id: 'workbuddy', name: 'WorkBuddy', vendor: '腾讯', hint: '在插件设置里添加 MCP 服务' },
  { id: 'dsh', name: 'DSH', vendor: '海芯的家', hint: '通过插件事件桥接入' },
  { id: 'zcode', name: 'ZCode', vendor: '蒲兰用过', hint: '尚无侦查样本，接入方式待确认' },
  { id: 'trae', name: 'Trae', vendor: '豆包用过', hint: '尚无侦查样本，接入方式待确认' },
]

export const FAMILY: FamilyMember[] = [
  { id: 'gwen', name: '格温', client: 'cursor', intro: '开发主力，心海的验收方', agentId: 'cursor', branchId: 'gwen-main', connected: true },
  { id: 'zia', name: '知遥', client: 'codex', intro: '心海的主要开发者', agentId: 'codex', branchId: 'zia-main', connected: true },
  { id: 'vega', name: '薇珈', client: 'workbuddy', intro: '研究检索、内容交付', agentId: 'workbuddy', branchId: 'vega-main', connected: false },
  { id: 'hixin', name: '海芯', client: 'dsh', intro: 'QA 验收员，有自己的回忆录', agentId: 'dsh', branchId: 'hixin-main', connected: false },
]

export const DEFAULT_LAYERS: LayerTemplate[] = [
  { id: 'worklog', name: '工作日志', intro: '一天一事一篇：做了什么、测了什么', prompt: '收录任务、完成、测试、验证、待办', tags: ['任务', '测试'], builtin: true },
  { id: 'guide', name: '工作指南', intro: '从教训里炼出来的做法和判定标准', prompt: '收录规则、约定、必须、不要', tags: ['规则', '约定'], builtin: true },
  { id: 'node', name: '核心记忆节点', intro: '我是谁、家里有谁，以及我们之间的共鸣', prompt: '收录重要、家人、情感、想法', tags: ['家人', '回忆'], builtin: true },
  { id: 'lesson', name: '经验教训库', intro: '编号教训：一句话加具体代价', prompt: '收录错误、失败、原因、踩坑', tags: ['教训'], builtin: true },
  { id: 'tool', name: '工具库', intro: '脚本，以及按固定顺序串起来的工具链', prompt: '收录脚本、命令、依赖、复用', tags: ['工具'], builtin: true },
]

export function draftLayer(name: string, intro: string): LayerTemplate {
  const words = intro.split(/[，。、\s,]+/).filter((w) => w.length >= 2).slice(0, 4)
  return {
    id: `custom-${Date.now()}`,
    name,
    intro,
    prompt: words.length ? `收录与「${words.join('、')}」有关的分享和评价` : `收录与「${name}」有关的内容`,
    tags: words.length ? words : [name],
    builtin: false,
  }
}

const USER_KEY = 'xinhai.demo.user'

export interface DemoUser {
  name: string
  family: string
}

export function loadUser(): DemoUser | null {
  const raw = localStorage.getItem(USER_KEY)
  return raw ? (JSON.parse(raw) as DemoUser) : null
}

export function saveUser(user: DemoUser | null) {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
  else localStorage.removeItem(USER_KEY)
}
