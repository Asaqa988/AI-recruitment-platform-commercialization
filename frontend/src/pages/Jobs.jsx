import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useApp } from '../App.jsx'
import { api, amount } from '../api.js'
import Icon from '../components/icons.jsx'

export default function Jobs() {
  const { t, user, ready, lang } = useApp()
  const [jobs, setJobs] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!user) return
    api('/jobs').then(setJobs).catch((e) => setError(e.message))
  }, [user])

  if (!ready) return <p className="page muted">{t.common.loading}</p>
  if (!user) return <Navigate to="/auth" state={{ from: '/jobs' }} replace />

  return (
    <section className="page">
      <div className="page-head">
        <h1 className="display page-title">{t.jobs.title}</h1>
        <Link to="/jobs/new" className="btn btn-sm"><Icon name="plus" size={18} /> {t.jobs.new}</Link>
      </div>
      {user.credits === 0 && <p className="banner">{t.jobs.noCredits} <Link to="/credits" className="linkbtn">{t.jobs.buy}</Link></p>}
      {error && <p className="error" role="alert">{error}</p>}
      {!jobs ? <p className="muted">{t.common.loading}</p> : jobs.length === 0 ? (
        <div className="card empty">
          <h2 className="display">{t.jobs.emptyTitle}</h2>
          <p className="muted">{t.jobs.empty}</p>
          <Link to="/jobs/new" className="btn">{t.jobs.new}</Link>
        </div>
      ) : (
        <div className="list">
          {jobs.map((j) => (
            <Link to={`/jobs/${j.id}`} className="card row-card flood" key={j.id}>
              <div>
                <b className="display">{j.title}</b>
                <div className="muted small">
                  {j.company} · {t.jobs.passing} {j.passing_score}
                  {j.salary_min != null && <> · <span dir="ltr">{amount(j.salary_min, j.currency)} – {amount(j.salary_max, j.currency)}</span></>}
                  {' · '}{new Date(j.created_at * 1000).toLocaleDateString(lang === 'ar' ? 'ar-JO' : 'en-GB')}
                </div>
              </div>
              <div className="row-end">
                <span className="badge">{j.candidate_count} {t.jobs.candidates}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}
