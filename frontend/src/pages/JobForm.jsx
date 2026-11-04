import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { useApp } from '../App.jsx'
import { api } from '../api.js'

const EMPTY = {
  title: '', company: '', description: '', passing_score: 70, currency: 'USD',
  salary_min: '', salary_max: '', required_documents: '', language: 'en', is_open: true,
}

export default function JobForm() {
  const { id } = useParams()
  const { t, user, ready, lang } = useApp()
  const navigate = useNavigate()
  const [form, setForm] = useState({ ...EMPTY, language: lang })
  const [loaded, setLoaded] = useState(!id)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id || !user) return
    api(`/jobs/${id}`).then(({ job }) => {
      setForm({
        ...job,
        salary_min: job.salary_min ?? '', salary_max: job.salary_max ?? '',
        required_documents: job.required_documents.join('\n'),
      })
      setLoaded(true)
    }).catch((e) => setError(e.message))
  }, [id, user])

  if (!ready) return <p className="page muted">{t.common.loading}</p>
  if (!user) return <Navigate to="/auth" state={{ from: id ? `/jobs/${id}/edit` : '/jobs/new' }} replace />

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    const num = (v) => (v === '' || v === null ? null : Number(v))
    const body = {
      title: form.title, company: form.company, description: form.description,
      passing_score: Number(form.passing_score), currency: form.currency,
      salary_min: num(form.salary_min), salary_max: num(form.salary_max),
      required_documents: form.required_documents.split('\n').map((s) => s.trim()).filter(Boolean),
      language: form.language, is_open: form.is_open,
    }
    try {
      const job = await api(id ? `/jobs/${id}` : '/jobs', { method: id ? 'PUT' : 'POST', body })
      navigate(`/jobs/${job.id}`)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <section className="page narrow-wide">
      <Link to={id ? `/jobs/${id}` : '/jobs'} className="back">← {t.job.back}</Link>
      <h1 className="display page-title">{id ? t.job.editTitle : t.job.newTitle}</h1>
      {!loaded && !error ? <p className="muted">{t.common.loading}</p> : (
        <form className="form card" onSubmit={submit}>
          <div className="row2">
            <label>{t.job.title}
              <input value={form.title} onChange={set('title')} required minLength={2} maxLength={120} placeholder={t.job.titlePh} />
            </label>
            <label>{t.job.company}
              <input value={form.company} onChange={set('company')} required maxLength={120} placeholder={t.job.companyPh} />
              <small className="muted">{t.job.companyHint}</small>
            </label>
          </div>
          <label>{t.job.description}
            <textarea rows={8} value={form.description} onChange={set('description')} required minLength={30} maxLength={8000} placeholder={t.job.descriptionPh} />
            <small className="muted">{t.job.descriptionHint}</small>
          </label>
          <div className="row2">
            <label>{t.job.passing}
              <input type="number" min={0} max={100} dir="ltr" value={form.passing_score} onChange={set('passing_score')} required />
              <small className="muted">{t.job.passingHint}</small>
            </label>
            <fieldset>
              <legend>{t.job.language}</legend>
              <div className="chips">
                {['en', 'ar'].map((l) => (
                  <button type="button" key={l} className={`chip ${form.language === l ? 'on' : ''}`} aria-pressed={form.language === l}
                    onClick={() => setForm({ ...form, language: l })}>{l === 'en' ? 'English' : 'العربية'}</button>
                ))}
              </div>
              <small className="muted">{t.job.languageHint}</small>
            </fieldset>
          </div>
          <div className="row3">
            <label>{t.job.salaryMin}
              <input type="number" min={0} dir="ltr" value={form.salary_min} onChange={set('salary_min')} />
            </label>
            <label>{t.job.salaryMax}
              <input type="number" min={0} dir="ltr" value={form.salary_max} onChange={set('salary_max')} />
            </label>
            <label>{t.job.currency}
              <input dir="ltr" maxLength={3} minLength={3} value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} required />
            </label>
          </div>
          <small className="muted">{t.job.salaryHint}</small>
          <label>{t.job.docs}
            <textarea rows={4} value={form.required_documents} onChange={set('required_documents')} placeholder={t.job.docsPh} />
            <small className="muted">{t.job.docsHint}</small>
          </label>
          <fieldset>
            <legend>{t.job.board}</legend>
            <div className="chips">
              {[true, false].map((v) => (
                <button type="button" key={String(v)} className={`chip ${form.is_open === v ? 'on' : ''}`} aria-pressed={form.is_open === v}
                  onClick={() => setForm({ ...form, is_open: v })}>{v ? t.job.open : t.job.closed}</button>
              ))}
            </div>
            <small className="muted">{t.job.boardHint}</small>
          </fieldset>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="btn" disabled={busy}>{busy ? t.common.saving : id ? t.job.save : t.job.create}</button>
        </form>
      )}
    </section>
  )
}
