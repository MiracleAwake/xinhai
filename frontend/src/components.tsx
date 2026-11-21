import { Evidence, MatchKind } from './api'

export const WORKSPACE = 'xinhai-demo'

export function MockBadge() {
  return <span className="badge mock" title="这一块是演示数据，后端还没有对应接口">模拟</span>
}

const MATCH_LABEL: Record<MatchKind, string> = {
  literal_query: '整句命中',
  term_fallback: '拆词命中',
  vector: '语义相近',
  source_context: '同来源展开',
}

const CHANNEL_LABEL: Record<string, string> = { text: '文字', vector: '向量' }

export function EvidenceCard({ item }: { item: Evidence }) {
  const reason = item.match_reason
  const sec = item.secretary_evidence
  const uncertain = sec && sec.uncertainty && sec.uncertainty !== 'unknown'
  return (
    <article className="card evidence">
      <header className="evidence-head">
        <div className="chips">
          {reason && (
            <span className={`chip match-${reason.kind}`}>
              {MATCH_LABEL[reason.kind] ?? reason.kind}
              {reason.terms.length > 0 && reason.kind !== 'literal_query' && `：${reason.terms.join('、')}`}
            </span>
          )}
          {reason?.channels?.map((c) => (
            <span key={c} className="chip soft">
              {CHANNEL_LABEL[c] ?? c}
            </span>
          ))}
          {item.modality !== 'text' && <span className="chip soft">{item.modality === 'image' ? '截图' : item.modality}</span>}
        </div>
        <div className="meta">
          {item.score !== null && <span>相似度 {item.score.toFixed(3)}</span>}
          {item.branch_id && <span className="branch">{item.branch_id}</span>}
        </div>
      </header>

      <p className="original">{item.text}</p>

      {(item.ocr_text || item.visual_summary) && (
        <dl className="extra">
          {item.ocr_text && (
            <>
              <dt>OCR 文本</dt>
              <dd>{item.ocr_text}</dd>
            </>
          )}
          {item.visual_summary && (
            <>
              <dt>视觉摘要</dt>
              <dd>{item.visual_summary}</dd>
            </>
          )}
        </dl>
      )}

      {item.structured_facts.length > 0 && (
        <div className="facts">
          {item.structured_facts.map((f, i) => (
            <span key={i} className={f.enabled ? 'fact on' : 'fact off'}>
              {f.rule_name ?? '规则'} · {f.enabled ? '已启用' : '未启用'} · {f.action} {f.direction}
            </span>
          ))}
          <span className="hint">开关状态来自结构化审计，不由这次搜索命中决定。</span>
        </div>
      )}

      <footer className="evidence-foot">
        {uncertain ? (
          <span className="care">秘书疑问：{sec!.uncertainty}</span>
        ) : (
          <span className="muted">
            {!sec || sec.result === 'unknown' ? '没有秘书审计' : sec.result === 'disabled' ? '秘书未启用模型' : '秘书未提出疑问'}
          </span>
        )}
        {(reason?.structured_state_verified === false || sec?.is_verified === false) && <span className="care">未核实</span>}
        {item.source_ref && <span className="muted">来源 {item.source_ref}</span>}
        {item.weight_source && (
          <span className="muted">
            权重 文{item.route_weights?.text} / 向{item.route_weights?.vector}（{weightSourceLabel(item.weight_source)}）
          </span>
        )}
      </footer>
    </article>
  )
}

function weightSourceLabel(s: string) {
  return s === 'request' ? '本次指定' : s === 'config' ? '来自配置' : '按查询形状'
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-wave" aria-hidden />
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  )
}
