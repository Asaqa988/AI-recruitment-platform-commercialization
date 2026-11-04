import { useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../App.jsx'
import Icon from './icons.jsx'

export function goSection(navigate, pathname, id) {
  const scroll = () => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  if (pathname !== '/') {
    navigate('/')
    setTimeout(scroll, 120)
  } else {
    scroll()
  }
}

export default function Layout({ children }) {
  const { t, lang, setLang, user, signOut } = useApp()
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const section = (id) => () => { setOpen(false); goSection(navigate, pathname, id) }
  const close = () => setOpen(false)

  return (
    <>
      <a className="skip" href="#main">{t.nav.skip}</a>
      <header className="nav">
        <Link to="/" className="logo" onClick={close}>
          <span className="logo-mark">Z</span>
          <span className="display">{t.brand}</span>
        </Link>
        {user && <span className="badge role-badge">{user.role === 'hr' ? 'HR' : t.nav.candidateTag}</span>}
        <button className="nav-toggle" aria-label="Menu" aria-expanded={open} onClick={() => setOpen(!open)}>
          <Icon name={open ? 'close' : 'menu'} />
        </button>
        <nav className={`nav-links ${open ? 'open' : ''}`}>
          <button className="linkbtn" onClick={section('how')}>{t.nav.how}</button>
          <button className="linkbtn" onClick={section('pricing')}>{t.nav.pricing}</button>
          <button className="linkbtn" onClick={section('faq')}>{t.nav.faq}</button>
          {user?.role !== 'hr' && <NavLink to="/portal" onClick={close}>{t.nav.portal}</NavLink>}
          {user?.role === 'candidate' && <NavLink to="/applications" onClick={close}>{t.nav.applications}</NavLink>}
          {user?.role === 'hr' && <NavLink to="/jobs" onClick={close}>{t.nav.jobs}</NavLink>}
          {user?.role === 'hr' && <NavLink to="/credits" onClick={close}>{t.nav.credits}: <b>{user.credits}</b></NavLink>}
          {user?.is_admin && <NavLink to="/admin" onClick={close}>{t.nav.admin}</NavLink>}
          <button className="linkbtn lang" onClick={() => setLang(lang === 'en' ? 'ar' : 'en')}>{t.nav.lang}</button>
          {user
            ? <button className="linkbtn" onClick={() => { signOut(); close(); navigate('/') }}>{t.nav.logout}</button>
            : <NavLink to="/auth" onClick={close}>{t.nav.login}</NavLink>}
          {user?.role !== 'candidate' && <Link to={user ? '/jobs/new' : '/auth'} className="btn btn-sm" onClick={close}>{t.nav.start}</Link>}
        </nav>
      </header>
      <main id="main">{children}</main>
      <footer className="footer">
        <div className="display footer-brand">{t.brand}</div>
        <div className="footer-meta">
          <span>{t.footer.loc}</span>
          <span dir="ltr">+962 7 9770 0235</span>
          <span>© {new Date().getFullYear()} {t.footer.rights}</span>
        </div>
        <p className="muted small">{t.footer.advisory}</p>
      </footer>
    </>
  )
}
