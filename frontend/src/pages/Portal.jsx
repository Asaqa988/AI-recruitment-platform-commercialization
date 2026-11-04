import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../App.jsx'
import { api } from '../api.js'

function ApplyForm({ job, onCancel }) {
  const { t, user, config } = useApp()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: user.name, email: user.email, expected_salary: '', currency: 'USD', cv_text: '' })
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const fd = new FormData()
      Object.entries(form).forEach(([k, v]) => fd.append(k, v))
      if (file) fd.append('cv_file', file)
      const { id } = await api(`/portal/jobs/${job.id}/apply`, { method: 'POST', form: fd })
      navigate(`/applications/${id}`)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form className="form subcard" onSubmit={submit}>
      <h3 className="display">{t.portal.formTitle}</h3>
      {job.required_documents.length > 0 && <p className="muted small">{t.portal.requested}: {job.required_documents.join(', ')}</p>}
      <div className="row2">
        <label>{t.portal.name}<input value={form.name} onChange={set('name')} required minLength={2} maxLength={100} /></label>
        <label>{t.portal.email}<input type="email" dir="ltr" value={form.email} onChange={set('email')} required /></label>
      </div>
      <div className="row2">
        <label>{t.portal.salary}<input type="number" min={0} dir="ltr" value={form.expected_salary} onChange={set('expected_salary')} /></label>
        <label>{t.portal.currency}<input dir="ltr" maxLength={3} value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} /></label>
      </div>
      <label>{t.portal.cvFile}
        <input type="file" accept=".pdf,.docx,.txt,.md" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <small className="muted">{t.portal.cvFileHint(config?.max_cv_mb || 5)}</small>
      </label>
      <label>{t.portal.cvText}
        <textarea rows={5} value={form.cv_text} onChange={set('cv_text')} />
      </label>
      <p className="muted small">{t.portal.privacy}</p>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="actions">
        <button className="btn" disabled={busy}>{busy ? t.portal.sending : t.portal.submit}</button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>{t.portal.cancel}</button>
      </div>
    </form>
  )
}

export default function Portal() {
  const { t, user, ready } = useApp()
  const [jobs, setJobs] = useState(null)
  const [error, setError] = useState('')
  const [applying, setApplying] = useState(null)

  useEffect(() => {
    if (!ready) return
    api('/portal/jobs').then(setJobs).catch((e) => setError(e.message))
  }, [ready, user])

  return (
    <section className="page">
      <h1 className="display page-title">{t.portal.title}</h1>
      <p className="muted">{t.portal.sub}</p>
      {user?.role === 'hr' && <p className="banner">{t.portal.hrWarn}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {!jobs ? <p className="muted">{t.common.loading}</p> : jobs.length === 0 ? <p className="muted">{t.portal.empty}</p> : (
        <div className="list">
          {jobs.map((j) => (
            <article className="card stage" key={j.id}>
              <div className="page-head">
                <div>
                  <h2 className="display">{j.title}</h2>
                  <span className="muted">{j.company}</span>
                </div>
                {user?.role === 'candidate' ? (
                  j.application_id
                    ? <Link to={`/applications/${j.application_id}`} className="btn btn-sm btn-ghost">{t.portal.view}</Link>
                    : <button className="btn btn-sm" onClick={() => setApplying(applying === j.id ? null : j.id)}>{t.portal.apply}</button>
                ) : user ? null : (
                  <Link to="/auth?role=candidate" className="btn btn-sm">{t.portal.needAccount}</Link>
                )}
              </div>
              <details>
                <summary className="muted">{t.job.description}</summary>
                <p className="plain">{j.description}</p>
              </details>
              {applying === j.id && !j.application_id && <ApplyForm job={j} onCancel={() => setApplying(null)} />}
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
