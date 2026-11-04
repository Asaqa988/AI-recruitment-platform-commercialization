import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { useApp } from '../App.jsx'
import { amount, api, download } from '../api.js'
import Icon from '../components/icons.jsx'
import { CvBadge, DecisionBadge, OutcomeBadge } from '../components/ui.jsx'

const STAGE_KEYS = ['screen', 'evaluate', 'salary', 'documents', 'report']

export default function JobDetail() {
  const { id } = useParams()
  const { t, user, ready, lang } = useApp()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => api(`/jobs/${id}`).then(setData).catch((e) => setError(e.message)), [id])
  const activeRef = useRef(false)
  useEffect(() => {
    if (!user) return undefined
    load()
    const timer = setInterval(() => { if (activeRef.current) load() }, 3000)
    return () => clearInterval(timer)
  }, [user, load])
  useEffect(() => {
    activeRef.current = !!data?.candidates.some((c) => Object.values(c.stages).some((s) => s === 'queued' || s === 'running'))
  }, [data])

  if (!ready) return <p className="page muted">{t.common.loading}</p>
  if (!user) return <Navigate to="/auth" state={{ from: `/jobs/${id}` }} replace />
  if (error) return <section className="page"><p className="error">{error}</p><Link to="/jobs" className="btn btn-sm">{t.job.back}</Link></section>
  if (!data) return <p className="page muted">{t.common.loading}</p>

  const { job, candidates } = data
  const remove = async () => {
    if (!window.confirm(t.job.confirmDelete)) return
    try { await api(`/jobs/${id}`, { method: 'DELETE' }); navigate('/jobs') } catch (e) { setError(e.message) }
  }

  return (
    <section className="page">
      <Link to="/jobs" className="back">← {t.job.back}</Link>
      <div className="page-head">
        <h1 className="display page-title">{job.title}</h1>
        <div className="row-end">
          <Link to={`/jobs/${id}/edit`} className="btn btn-sm btn-ghost"><Icon name="edit" size={16} /> {t.job.edit}</Link>
          <button className="btn btn-sm btn-ghost" onClick={remove}><Icon name="trash" size={16} /> {t.job.delete}</button>
        </div>
      </div>
      <p className="muted">
        <span className={`badge ${job.is_open ? 'o-pass' : 'o-hold'}`}>{job.is_open ? t.job.statusOpen : t.job.statusClosed}</span>{' '}
        {job.company} · {t.jobs.passing} {job.passing_score} · {job.language === 'ar' ? 'العربية' : 'English'}
        {job.salary_min != null && <> · <span dir="ltr">{amount(job.salary_min, job.currency)} – {amount(job.salary_max, job.currency)}</span></>}
        {job.required_documents.length > 0 && <> · {t.job.docsShort}: {job.required_documents.join(', ')}</>}
      </p>
      {user.credits === 0 && <p className="banner">{t.jobs.noCredits} <Link to="/credits" className="linkbtn">{t.jobs.buy}</Link></p>}

      <div className="page-head">
        <h2 className="display">{t.job.candidates} · {candidates.length}</h2>
        <div className="row-end">
          {candidates.length > 0 && (
            <button className="btn btn-sm btn-ghost" onClick={() => download(`/jobs/${id}/export.csv`, `candidates-${id}.csv`)}>
              <Icon name="download" size={16} /> {t.job.exportCsv}
            </button>
          )}
        </div>
      </div>

      {candidates.length === 0 && <div className="card empty"><p className="muted">{t.job.noApplicants}</p></div>}

      {candidates.length > 0 && (
        <div className="table-wrap">
          <table className="table cand-table">
            <thead><tr>
              <th>{t.job.cols.name}</th><th>{t.job.cols.progress}</th><th>{t.job.cols.cv}</th>
              <th>{t.job.cols.interview}</th><th>{t.job.cols.ai}</th><th>{t.job.cols.hr}</th>
            </tr></thead>
            <tbody>
              {candidates.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link to={`/candidates/${c.id}`} className="linkbtn"><b>{c.name}</b></Link>
                    <div className="muted small" dir="ltr">{c.email}</div>
                    <div className="muted small">{new Date(c.created_at * 1000).toLocaleDateString(lang === 'ar' ? 'ar-JO' : 'en-GB')}
                      {c.applicant ? ` · ${t.cand.interviewState[c.interview_status]}` : ''}</div>
                    <div><Link to={`/candidates/${c.id}`} className="badge a-interview">{t.job.open_candidate}</Link></div>
                  </td>
                  <td>
                    <span className="dots">
                      {STAGE_KEYS.map((k) => (
                        <i key={k} className={`dot-s s-${c.stages[k] || 'idle'}`} title={`${t.stageNames[k]}: ${t.stageStatus[c.stages[k] || 'idle']}`} />
                      ))}
                    </span>
                  </td>
                  <td>{c.cv_score != null ? <><b dir="ltr">{c.cv_score}</b> <CvBadge value={c.cv_recommendation} /></> : '—'}</td>
                  <td>{c.interview_score != null ? <b dir="ltr">{c.interview_score}</b> : '—'}</td>
                  <td><DecisionBadge value={c.decision} /></td>
                  <td><OutcomeBadge value={c.hr_outcome} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
