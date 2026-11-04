import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { api, getToken, setToken } from './api.js'
import { translations } from './i18n.js'
import Layout from './components/Layout.jsx'
import Home from './pages/Home.jsx'
import Auth from './pages/Auth.jsx'
import Credits from './pages/Credits.jsx'
import Jobs from './pages/Jobs.jsx'
import JobForm from './pages/JobForm.jsx'
import JobDetail from './pages/JobDetail.jsx'
import Candidate from './pages/Candidate.jsx'
import Admin from './pages/Admin.jsx'
import Portal from './pages/Portal.jsx'
import Applications from './pages/Applications.jsx'
import Application from './pages/Application.jsx'

const Ctx = createContext(null)
export const useApp = () => useContext(Ctx)

export const homeFor = (user) => (user?.role === 'candidate' ? '/portal' : '/jobs')

function readLang() {
  try { return localStorage.getItem('zh_lang') || 'en' } catch { return 'en' }
}

// HR pages are for HR accounts and the portal pages for candidate accounts; anyone else is sent to their own area.
function Guard({ role, children }) {
  const { user, ready, t } = useApp()
  const { pathname } = useLocation()
  if (!ready) return <p className="page muted">{t.common.loading}</p>
  if (!user) return <Navigate to="/auth" state={{ from: pathname }} replace />
  if (user.role !== role) return <Navigate to={homeFor(user)} replace />
  return children
}

export default function App() {
  const [lang, setLang] = useState(readLang)
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)
  const [config, setConfig] = useState(null)
  const { pathname } = useLocation()

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr'
    try { localStorage.setItem('zh_lang', lang) } catch { /* ignore */ }
  }, [lang])

  useEffect(() => { window.scrollTo(0, 0) }, [pathname])

  useEffect(() => {
    api('/config').then(setConfig).catch(() => {})
    if (!getToken()) { setReady(true); return }
    api('/me').then(setUser).catch(() => setToken('')).finally(() => setReady(true))
  }, [])

  const signIn = useCallback((res) => { setToken(res.token); setUser(res.user) }, [])
  const signOut = useCallback(() => { setToken(''); setUser(null) }, [])
  const reloadUser = useCallback(() => api('/me').then(setUser).catch(() => {}), [])
  const t = translations[lang]
  const value = useMemo(
    () => ({ lang, setLang, t, user, signIn, signOut, reloadUser, config, ready }),
    [lang, t, user, signIn, signOut, reloadUser, config, ready],
  )
  const hr = (el) => <Guard role="hr">{el}</Guard>
  const cand = (el) => <Guard role="candidate">{el}</Guard>

  return (
    <Ctx.Provider value={value}>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/auth" element={<Auth />} />
          <Route path="/portal" element={<Portal />} />
          <Route path="/applications" element={cand(<Applications />)} />
          <Route path="/applications/:id" element={cand(<Application />)} />
          <Route path="/credits" element={hr(<Credits />)} />
          <Route path="/jobs" element={hr(<Jobs />)} />
          <Route path="/jobs/new" element={hr(<JobForm />)} />
          <Route path="/jobs/:id" element={hr(<JobDetail />)} />
          <Route path="/jobs/:id/edit" element={hr(<JobForm />)} />
          <Route path="/candidates/:id" element={hr(<Candidate />)} />
          <Route path="/admin" element={hr(<Admin />)} />
          <Route path="*" element={<Home />} />
        </Routes>
      </Layout>
    </Ctx.Provider>
  )
}
