export type MatchKind = 'literal_query' | 'term_fallback' | 'vector' | 'source_context'

export interface MatchReason {
  kind: MatchKind
  terms: string[]
  channels?: string[]
  structured_state_verified: boolean
}

export interface StructuredFact {
  rule_name?: string
  enabled?: boolean
  action?: string
  direction?: string
  evidence?: string
}

export interface SecretaryEvidence {
  uncertainty: string
  summary: string | null
  provider: string | null
  result: string
  is_verified: boolean
}

export interface Evidence {
  record_id: string
  text: string
  modality: string
  asset_ref: string | null
  source_ref: string | null
  ocr_text: string | null
  visual_summary: string | null
  structured_facts: StructuredFact[]
  score: number | null
  quality_status: string | null
  context_status: string | null
  route_reason: string | null
  branch_id: string | null
  workspace_id: string | null
  secretary_evidence?: SecretaryEvidence
  match_reason?: MatchReason
  route_weights?: { text: number; vector: number }
  weight_source?: string
}

export interface MemoryRecord {
  id: string
  text: string
  status: 'candidate' | 'active' | 'obsolete'
  layer_id: string | null
  tags_json: string
  branch_id: string | null
  agent_id: string | null
  workspace_id: string | null
  session_id: string | null
  source_id: string | null
  modality: string | null
  ts: string
  obsolete_reason: string | null
  scope?: string
}

export interface MemoryProvenance {
  relations: {
    from_id: string
    type: 'covers' | 'supersedes'
    to_id: string
    metadata: {
      reason?: string
      start?: number
      end?: number
      message_start?: number
      message_end?: number
      source_line?: number
      ranges?: { start: number; end: number }[]
    }
  }[]
  events: {
    action: 'verify' | 'summary_rebuild'
    actor: string
    created_at: string
    details: { evidence_id?: string; conclusion?: string; reason?: string; uncertainty?: string }
  }[]
}

export interface Identity {
  agent_id?: string
  workspace_id?: string
  branch_id?: string
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message)
  }
}

function query(params: object) {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  }
  return q.toString()
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const err = body?.error
    throw new ApiError(res.status, err?.code ?? 'HTTP_ERROR', err?.message ?? `请求失败（${res.status}）`)
  }
  return body as T
}

export const api = {
  memoryProvenance: (id: string, identity: Identity & { scope?: string }) =>
    request<MemoryProvenance>(`/memory-maintenance/${encodeURIComponent(id)}?${query(identity)}`),
  health: () => request<{ status: string }>('/health'),

  evidence: (q: string, identity: Identity, opts: { limit?: number; expand_source?: boolean } = {}) =>
    request<Evidence[]>(`/memories/evidence?${query({ q, ...identity, ...opts })}`),

  list: (filters: Identity & { status?: string; layer_id?: string; tag?: string; limit?: number }) =>
    request<MemoryRecord[]>(`/memories?${query(filters)}`),

  confirm: (record_id: string) =>
    request<MemoryRecord>('/memories/confirm', { method: 'POST', body: JSON.stringify({ record_id }) }),

  forget: (record_id: string, reason: string) =>
    request<MemoryRecord>('/memories/forget', { method: 'POST', body: JSON.stringify({ record_id, reason }) }),

  remember: (text: string, identity: Identity, extra: Record<string, string> = {}) =>
    request<{ decision: string; record: MemoryRecord | null }>('/memories', {
      method: 'POST',
      body: JSON.stringify({ text, ...identity, ...extra }),
    }),

  structured: (identity: Identity, enabled?: boolean) =>
    request<MemoryRecord[]>(`/memories/structured?${query({ ...identity, enabled })}`),

  compare: (identity: Identity, rule_name?: string) =>
    request<Record<string, { enabled_true?: CompareSide[]; enabled_false?: CompareSide[] }>>(
      `/memories/structured/compare?${query({ ...identity, rule_name })}`,
    ),

  configCurrent: () => request<ConfigStatus>('/config/current'),
  configHistory: () => request<ConfigVersion[]>('/config/history'),
  configDiff: (older: string, newer: string) =>
    request<Record<string, { from: unknown; to: unknown }>>(`/config/diff?${query({ older, newer })}`),

  checkpoint: (body: { session_id: string; goal: string; pending: string[]; unknown: string[]; next_step?: string }) =>
    request<Checkpoint>('/checkpoints', { method: 'POST', body: JSON.stringify(body) }),
}

export interface CompareSide {
  record_id: string
  asset_ref: string | null
  branch_id: string | null
  evidence: string
}

export interface ConfigStatus {
  configured: boolean
  version: string | null
  config_id: string | null
  scope: string | null
  validation_status: string | null
}

export interface ConfigVersion {
  config_id: string
  version: string
  created_at: string
  author: string
  reason: string
  scope: string
  parent_version: string | null
  checksum: string
  validation_status: string
}

export interface Checkpoint {
  id: string
  session_id: string
  goal: string
  pending: string[]
  unknown: string[]
  next_step: string | null
  created_at: string
}

export function parseTags(record: MemoryRecord): string[] {
  try {
    return JSON.parse(record.tags_json)
  } catch {
    return []
  }
}
