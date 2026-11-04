import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useApp } from '../App.jsx'
import { api } from '../api.js'
import Icon from '../components/icons.jsx'

const ORDER = ['received', 'in_review', 'interview', 'interview_submitted', 'decided']

function Interview({ app, onDone }) {
  const { t } = useApp()
  const [answers, setAnswers] = useState(() => app.questions.map(() => ''))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api(`/portal/applications/${app.id}/interview`, { method: 'POST', body: { answers } })
      await onDone()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form className="form card stage" onSubmit={submit}>
      <h2 className="display">{t.apps.interviewTitle}</h2>
      <p className="muted">{t.apps.interviewHint}</p>
      {app.questions.map((q, i) => (
        <label className="field" key={i}><b>{i + 1}. {q}</b>
          <textarea rows={4} value={answers[i]} maxLength={3000} required minLength={2} placeholder={t.apps.answerN(i + 1)}
            onChange={(e) => setAnswers(answers.map((a, j) => (j === i ? e.target.value : a)))} />
        </label>
      ))}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="actions"><button className="btn" disabled={busy}>{busy ? t.apps.submitting : t.apps.submit}</button></div>
    </form>
  )
}

function Documents({ app, onChange }) {
  const { t } = useApp()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const input = useRef(null)

  const upload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      await api(`/portal/applications/${app.id}/documents`, { method: 'POST', form: fd })
      await onChange()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }
  const remove = async (id) => {
    try { await api(`/portal/applications/${app.id}/documents/${id}`, { method: 'DELETE' }); await onChange() } catch (err) { setError(err.message) }
  }

  return (
    <article className="card stage">
      <h2 className="display">{t.apps.docsTitle}</h2>
      <p className="muted">{t.apps.docsHint}</p>
      {app.job.required_documents.length > 0
        ? <p>{t.apps.docsRequested}: <b>{app.job.required_documents.join(', ')}</b></p>
        : <p className="muted small">{t.apps.docsNone}</p>}
      {app.documents.length > 0 && (
        <ul className="bullets">
          {app.documents.map((d) => (
            <li key={d.id}>{d.name} <span className="muted small" dir="ltr">({Math.max(1, Math.round(d.size / 1024))} KB)</span>{' '}
              <button className="linkbtn" onClick={() => remove(d.id)}>{t.apps.remove}</button></li>
          ))}
        </ul>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      <label className="field">{t.apps.upload}
        <input ref={input} type="file" accept=".pdf,.png,.jpg,.jpeg,.docx" onChange={upload} disabled={busy || app.documents.length >= app.max_docs} />
      </label>
    </article>
  )
}

export default function Application() {
  const { id } = useParams()
  const { t } = useApp()
  const navigate = useNavigate()
  const [app, setApp] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => api(`/portal/applications/${id}`).then(setApp).catch((e) => setError(e.message)), [id])
  useEffect(() => {
    load()
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  }, [load])

  if (error) return <section className="page"><p className="error">{error}</p><Link to="/applications" className="btn btn-sm">{t.apps.back}</Link></section>
  if (!app) return <p className="page muted">{t.common.loading}</p>

  const idx = ORDER.indexOf(app.status)
  const withdraw = async () => {
    if (!window.confirm(t.apps.confirmWithdraw)) return
    try { await api(`/portal/applications/${id}`, { method: 'DELETE' }); navigate('/applications') } catch (e) { setError(e.message) }
  }

  return (
    <section className="page">
      <Link to="/applications" className="back">← {t.apps.back}</Link>
      <div className="page-head">
        <h1 className="display page-title">{app.job.title}</h1>
        <span className={`badge a-${app.status}`}>{t.apps.status[app.status]}</span>
      </div>
      <p className="muted">{app.job.company}</p>

      <ol className="stages">
        {t.apps.timeline.map((label, i) => (
          <li key={label} className={i < idx || (app.status === 'decided' && i === idx) ? 'done' : i === idx ? 'active' : ''}>
            <span className="dot">{i < idx || (app.status === 'decided' && i === idx) ? <Icon name="check" size={16} /> : i + 1}</span>{label}
          </li>
        ))}
      </ol>

      {app.outcome && <p className="banner">{t.apps.outcome[app.outcome]}. {t.apps.nextHr}</p>}

      {app.interview_status === 'sent' && <Interview app={app} onDone={load} />}
      {app.interview_status === 'answered' && (
        <article className="card stage">
          <h2 className="display">{t.apps.interviewTitle}</h2>
          <p className="acid-text">{t.apps.submitted}</p>
          <details className="log">
            <summary>{t.apps.yourAnswers}</summary>
            <ol className="qlist">
              {app.questions.map((q, i) => <li key={i}><b>{q}</b><p className="plain" dir="auto">{app.answers[i]}</p></li>)}
            </ol>
          </details>
        </article>
      )}

      <Documents app={app} onChange={load} />

      <div><button className="btn btn-ghost" onClick={withdraw}><Icon name="trash" size={16} /> {t.apps.withdraw}</button></div>
    </section>
  )
}
