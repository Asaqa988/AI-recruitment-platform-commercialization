import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../App.jsx'
import { api } from '../api.js'

export default function Applications() {
  const { t, lang } = useApp()
  const [apps, setApps] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = () => api('/portal/applications').then(setApps).catch((e) => setError(e.message))
    load()
    const id = setInterval(load, 8000)
    return () => clearInterval(id)
  }, [])

  return (
    <section className="page">
      <div className="page-head">
        <h1 className="display page-title">{t.apps.title}</h1>
        <Link to="/portal" className="btn btn-sm">{t.apps.browse}</Link>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {!apps ? <p className="muted">{t.common.loading}</p> : apps.length === 0 ? <p className="muted">{t.apps.empty}</p> : (
        <div className="list">
          {apps.map((a) => (
            <Link to={`/applications/${a.id}`} className="card row-card flood" key={a.id}>
              <div>
                <b className="display">{a.job_title}</b>
                <div className="muted small">{a.company} · {new Date(a.created_at * 1000).toLocaleDateString(lang === 'ar' ? 'ar-JO' : 'en-GB')}</div>
              </div>
              <div className="row-end"><span className={`badge a-${a.status}`}>{t.apps.status[a.status]}</span></div>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}
