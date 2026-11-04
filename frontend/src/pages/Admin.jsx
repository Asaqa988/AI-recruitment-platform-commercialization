import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useApp } from '../App.jsx'
import { api, money } from '../api.js'

export default function Admin() {
  const { t, user, ready } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [grant, setGrant] = useState({ email: '', credits: 5 })
  const [msg, setMsg] = useState('')

  const load = useCallback(() => api('/admin/overview').then(setData).catch((e) => setError(e.message)), [])
  useEffect(() => {
    if (!user?.is_admin) return undefined
    load()
    const id = setInterval(load, 8000)
    return () => clearInterval(id)
  }, [user, load])

  const approve = async (id) => {
    try { await api(`/admin/purchases/${id}/approve`, { method: 'POST' }); await load() } catch (e) { setError(e.message) }
  }
  const give = async (e) => {
    e.preventDefault()
    setMsg('')
    setError('')
    try {
      await api('/admin/grant', { method: 'POST', body: { email: grant.email, credits: Number(grant.credits) } })
      setMsg(t.admin.granted)
    } catch (err) { setError(err.message) }
  }

  if (!ready) return <p className="page muted">{t.common.loading}</p>
  if (!user?.is_admin) return <Navigate to="/" replace />

  return (
    <section className="page">
      <h1 className="display page-title">{t.admin.title}</h1>
      <p className="muted">{t.admin.privacy}</p>
      {error && <p className="error" role="alert">{error}</p>}
      {data && (
        <>
          <div className="stats">
            <div className="card"><span className="muted small">{t.admin.revenue}</span><b className="display" dir="ltr">{money(data.revenue_cents)}</b></div>
            <div className="card"><span className="muted small">{t.admin.users}</span><b className="display">{data.users}</b></div>
            <div className="card"><span className="muted small">{t.admin.candidates}</span><b className="display">{data.candidates}</b></div>
            <div className="card"><span className="muted small">{t.admin.runs}</span>
              <span dir="ltr">{Object.entries(data.runs).map(([k, v]) => `${k}: ${v}`).join(' · ') || '—'}</span></div>
          </div>

          <h2 className="display">{t.admin.purchases}</h2>
          {data.purchases.length === 0 ? <p className="muted">{t.admin.none}</p> : (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>#</th><th>{t.admin.customer}</th><th>{t.admin.pack}</th><th>{t.admin.amount}</th><th>{t.admin.ref}</th><th></th><th></th></tr></thead>
                <tbody>
                  {data.purchases.map((p) => (
                    <tr key={p.id}>
                      <td>{p.id}</td>
                      <td dir="ltr">{p.user_email}</td>
                      <td>{t.pricing.names[p.package]} · {p.credits}</td>
                      <td dir="ltr">{money(p.price_cents)}</td>
                      <td dir="ltr">{p.payment_ref}</td>
                      <td><span className={`badge s-${p.status}`}>{t.admin.status[p.status] || p.status}</span></td>
                      <td>{(p.status === 'payment_review' || p.status === 'awaiting_payment') &&
                        <button className="btn btn-sm" onClick={() => approve(p.id)}>{t.admin.approve}</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2 className="display">{t.admin.grantTitle}</h2>
          <form className="form card" onSubmit={give}>
            <div className="row2">
              <label>{t.auth.email}<input type="email" dir="ltr" required value={grant.email} onChange={(e) => setGrant({ ...grant, email: e.target.value })} /></label>
              <label>{t.admin.creditsLabel}<input type="number" min={1} max={1000} dir="ltr" required value={grant.credits} onChange={(e) => setGrant({ ...grant, credits: e.target.value })} /></label>
            </div>
            {msg && <p className="acid-text">{msg}</p>}
            <button className="btn">{t.admin.grant}</button>
          </form>

          {data.failed.length > 0 && (
            <>
              <h2 className="display">{t.admin.failed}</h2>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>{t.admin.customer}</th><th>{t.admin.stage}</th><th>{t.admin.error}</th></tr></thead>
                  <tbody>
                    {data.failed.map((f, i) => (
                      <tr key={i}><td dir="ltr">{f.user_email}</td><td dir="ltr">{f.stage}</td><td>{f.error}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </section>
  )
}
