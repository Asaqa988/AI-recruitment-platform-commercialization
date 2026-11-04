import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useApp } from '../App.jsx'
import { api, money } from '../api.js'

function Payment({ purchase, onChange }) {
  const { t, config, reloadUser } = useApp()
  const [ref, setRef] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const demo = config?.payment_mode === 'demo'

  const pay = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api(`/purchases/${purchase.id}/pay`, { method: 'POST', body: { reference: ref } })
      await onChange()
      reloadUser()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card pay">
      <h3 className="display">{t.credits.payTitle} · <span dir="ltr">{money(purchase.price_cents)}</span> · {purchase.credits} {t.pricing.credits}</h3>
      {purchase.status === 'payment_review' ? (
        <p>{t.credits.manualWait} <b dir="ltr">{purchase.payment_ref}</b></p>
      ) : demo ? (
        <form onSubmit={pay}>
          <p className="muted">{t.credits.payDemo}</p>
          <button className="btn" disabled={busy}>{t.credits.payBtn}</button>
        </form>
      ) : (
        <form onSubmit={pay} className="form">
          {config?.payment_instructions && <p>{config.payment_instructions}</p>}
          <label>{t.credits.manualRef}
            <input dir="ltr" value={ref} onChange={(e) => setRef(e.target.value)} required minLength={3} maxLength={120} />
          </label>
          <button className="btn" disabled={busy}>{t.credits.manualBtn}</button>
        </form>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  )
}

export default function Credits() {
  const { t, user, ready, config, lang } = useApp()
  const [purchases, setPurchases] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  const load = useCallback(() => api('/purchases').then(setPurchases).catch((e) => setError(e.message)), [])
  useEffect(() => {
    if (!user) return undefined
    load()
    const id = setInterval(load, 8000)
    return () => clearInterval(id)
  }, [user, load])

  if (!ready) return <p className="page muted">{t.common.loading}</p>
  if (!user) return <Navigate to="/auth" state={{ from: '/credits' }} replace />

  const buy = async (pkg) => {
    setBusy(pkg)
    setError('')
    try { await api('/purchases', { method: 'POST', body: { package: pkg } }); await load() } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  const pending = (purchases || []).filter((p) => p.status === 'awaiting_payment' || p.status === 'payment_review')
  const history = (purchases || []).filter((p) => p.status === 'paid')

  return (
    <section className="page">
      <h1 className="display page-title">{t.credits.title}</h1>
      <div className="stats">
        <div className="card"><span className="muted small">{t.credits.balance}</span><b className="display" dir="ltr">{user.credits}</b></div>
      </div>
      <p className="muted">{t.credits.explain}</p>
      {error && <p className="error" role="alert">{error}</p>}

      <div className="grid3">
        {(config?.packages || []).map((p, i) => (
          <article className={`card price ${i === 1 ? 'featured' : ''}`} key={p.id}>
            <h3 className="display">{t.pricing.names[p.id]}</h3>
            <div className="price-num display" dir="ltr">{money(p.price_cents, config.currency)}</div>
            <p className="price-lead"><b>{p.credits}</b> {t.pricing.credits}</p>
            <button className="btn btn-block" disabled={busy === p.id} onClick={() => buy(p.id)}>{t.credits.buy}</button>
          </article>
        ))}
      </div>

      {pending.map((p) => <Payment key={p.id} purchase={p} onChange={load} />)}

      {history.length > 0 && (
        <>
          <h2 className="display">{t.credits.history}</h2>
          <div className="list">
            {history.map((p) => (
              <div className="card row-card" key={p.id}>
                <div>
                  <b className="display">{t.pricing.names[p.package]} · {p.credits} {t.pricing.credits}</b>
                  <div className="muted small">{new Date(p.created_at * 1000).toLocaleDateString(lang === 'ar' ? 'ar-JO' : 'en-GB')} · #{p.id}</div>
                </div>
                <div className="row-end"><span dir="ltr">{money(p.price_cents)}</span><span className="badge s-paid">{t.credits.paid}</span></div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
