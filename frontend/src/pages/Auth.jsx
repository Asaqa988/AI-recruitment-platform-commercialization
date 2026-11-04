import { useState } from 'react'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { homeFor, useApp } from '../App.jsx'
import { api } from '../api.js'

export default function Auth() {
  const { t, user, signIn, config } = useApp()
  const navigate = useNavigate()
  const { state } = useLocation()
  const [params] = useSearchParams()
  const [mode, setMode] = useState(params.get('role') ? 'register' : 'login')
  const [form, setForm] = useState({ name: '', email: '', password: '', role: params.get('role') === 'candidate' ? 'candidate' : 'hr' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (user) return <Navigate to={state?.from || homeFor(user)} replace />

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await api(`/auth/${mode}`, { method: 'POST', body: mode === 'login' ? { email: form.email, password: form.password } : form })
      signIn(res)
      navigate(state?.from || homeFor(res.user), { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="page narrow">
      <h1 className="display page-title">{mode === 'login' ? t.auth.loginTitle : t.auth.registerTitle}</h1>
      {mode === 'register' && form.role === 'hr' && config?.free_credits > 0 && <p className="banner">{t.auth.bonus(config.free_credits)}</p>}
      <form className="form card" onSubmit={submit}>
        {mode === 'register' && (
          <fieldset>
            <legend>{t.auth.role}</legend>
            <div className="chips">
              {['hr', 'candidate'].map((r) => (
                <button type="button" key={r} className={`chip ${form.role === r ? 'on' : ''}`} aria-pressed={form.role === r}
                  onClick={() => setForm({ ...form, role: r })}>{r === 'hr' ? t.auth.roleHr : t.auth.roleCandidate}</button>
              ))}
            </div>
            <small className="muted">{t.auth.roleHint}</small>
          </fieldset>
        )}
        {mode === 'register' && (
          <label>{t.auth.name}
            <input value={form.name} onChange={set('name')} required maxLength={100} autoComplete="name" />
          </label>
        )}
        <label>{t.auth.email}
          <input type="email" dir="ltr" value={form.email} onChange={set('email')} required autoComplete="email" />
        </label>
        <label>{t.auth.password}
          <input type="password" dir="ltr" value={form.password} onChange={set('password')} required minLength={8}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
          {mode === 'register' && <small className="muted">{t.auth.passwordHint}</small>}
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn btn-block" disabled={busy}>
          {busy ? t.auth.working : mode === 'login' ? t.auth.login : t.auth.register}
        </button>
        <button type="button" className="linkbtn center" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
          {mode === 'login' ? t.auth.toRegister : t.auth.toLogin}
        </button>
      </form>
    </section>
  )
}
