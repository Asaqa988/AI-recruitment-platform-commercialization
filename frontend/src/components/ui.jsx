import { useState } from 'react'
import { useApp } from '../App.jsx'

export function StageBadge({ status }) {
  const { t } = useApp()
  if (!status) return <span className="badge s-idle">{t.stageStatus.idle}</span>
  return <span className={`badge s-${status}`}>{t.stageStatus[status] || status}</span>
}

export function OutcomeBadge({ value }) {
  const { t } = useApp()
  if (!value) return <span className="muted">—</span>
  return <span className={`badge o-${value}`}>{t.outcome[value] || value}</span>
}

export function DecisionBadge({ value }) {
  const { t } = useApp()
  if (!value) return <span className="muted">—</span>
  const key = value === 'Pass' ? 'pass' : value === 'Fail' ? 'fail' : 'review'
  return <span className={`badge d-${key}`}>{t.decision[key]}</span>
}

export function CvBadge({ value }) {
  const { t } = useApp()
  if (!value) return <span className="muted">—</span>
  const key = value === 'Proceed' ? 'proceed' : value === 'Manual Review' ? 'review' : 'no'
  return <span className={`badge cv-${key}`}>{t.cvReco[key]}</span>
}

export function Lines({ items, empty }) {
  if (!items || items.length === 0) return <p className="muted small">{empty || '—'}</p>
  return <ul className="bullets">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
}

export function CopyButton({ text, label }) {
  const { t } = useApp()
  const [done, setDone] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setDone(true)
      setTimeout(() => setDone(false), 1500)
    } catch { /* clipboard unavailable */ }
  }
  return <button type="button" className="btn btn-sm btn-ghost" onClick={copy}>{done ? t.common.copied : label || t.common.copy}</button>
}

// Minimal markdown for the HR report: headings, lists, checkboxes, bold, tables are shown as text.
function inline(s) {
  return s.split(/(\*\*[^*]+\*\*)/g).map((p, i) => (p.startsWith('**') ? <b key={i}>{p.slice(2, -2)}</b> : p))
}

export function Markdown({ source }) {
  const blocks = []
  let list = []
  const flush = () => { if (list.length) { blocks.push(<ul className="bullets" key={`l${blocks.length}`}>{list}</ul>); list = [] } }
  source.split('\n').forEach((line, i) => {
    const l = line.trimEnd()
    if (/^\s*[-*] /.test(l)) { list.push(<li key={i}>{inline(l.replace(/^\s*[-*] (\[[ x]\] )?/, (m, box) => (box === '[x] ' ? '☑ ' : box ? '☐ ' : '')))}</li>); return }
    flush()
    if (!l.trim()) return
    const h = l.match(/^(#{1,4}) (.*)/)
    if (h) { const Tag = `h${Math.min(h[1].length + 1, 5)}`; blocks.push(<Tag key={i} className="md-h">{inline(h[2])}</Tag>); return }
    if (l.startsWith('>')) { blocks.push(<p key={i} className="banner">{inline(l.replace(/^>\s*/, ''))}</p>); return }
    blocks.push(<p key={i}>{inline(l)}</p>)
  })
  flush()
  return <div className="md">{blocks}</div>
}

export function Score({ value, of = 100, label }) {
  return (
    <div className="score">
      <b className="display" dir="ltr">{value ?? '—'}<small>/{of}</small></b>
      {label && <span className="muted small">{label}</span>}
    </div>
  )
}
