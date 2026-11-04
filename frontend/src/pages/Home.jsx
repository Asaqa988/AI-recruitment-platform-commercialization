import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../App.jsx'
import { money } from '../api.js'
import Icon from '../components/icons.jsx'
import { goSection } from '../components/Layout.jsx'

const FALLBACK = {
  packages: [
    { id: 'starter', credits: 10, price_cents: 4900 },
    { id: 'growth', credits: 50, price_cents: 19900 },
    { id: 'scale', credits: 200, price_cents: 59900 },
  ],
  currency: 'USD',
  free_credits: 1,
}
const STEP_ICONS = ['search', 'chat', 'scale', 'shield', 'mail', 'file']
const arDigits = (n) => String(n).padStart(2, '0').replace(/\d/g, (d) => '٠١٢٣٤٥٦٧٨٩'[d])

export default function Home() {
  const { t, lang, config, user } = useApp()
  const navigate = useNavigate()
  const cfg = config || FALLBACK
  const start = user ? (user.role === 'hr' ? '/jobs/new' : '/portal') : '/auth'
  const marquee = [...t.hero.marquee, ...t.hero.marquee, ...t.hero.marquee, ...t.hero.marquee]

  return (
    <>
      <section className="hero">
        <p className="kicker">{t.hero.kicker}</p>
        <h1 className="display hero-title">
          <span>{t.hero.l1}</span>
          <span className="hollow">{t.hero.l2}</span>
          <span className="acid-text">{t.hero.l3}</span>
        </h1>
        <p className="hero-sub">{t.hero.sub}</p>
        <div className="hero-actions">
          <Link to={start} className="btn">{t.hero.cta} <Icon name="arrow" size={20} /></Link>
          <button className="btn btn-ghost" onClick={() => goSection(navigate, '/', 'how')}>{t.hero.cta2}</button>
          <Link to="/portal" className="btn btn-ghost">{t.hero.cta3}</Link>
        </div>
      </section>

      <div className="marquee" aria-hidden="true">
        <div className="marquee-track">
          {marquee.concat(marquee).map((w, i) => <span key={i} className="display">{w}<i /></span>)}
        </div>
      </div>

      <section className="section" id="how">
        <h2 className="display sec-title">{t.how.title}</h2>
        <p className="sec-sub">{t.how.sub}</p>
        <div className="grid3">
          {t.how.steps.map((s, i) => (
            <article className="card flood" key={s.t}>
              <div className="card-top">
                <span className="num">{lang === 'ar' ? arDigits(i + 1) : String(i + 1).padStart(2, '0')}</span>
                <Icon name={STEP_ICONS[i]} size={28} />
              </div>
              <h3 className="display">{s.t}</h3>
              <p>{s.d}</p>
              <p className="muted small agents">{s.a}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section alt" id="control">
        <h2 className="display sec-title">{t.control.title}</h2>
        <p className="sec-sub">{t.control.sub}</p>
        <div className="grid4">
          {t.control.items.map((c) => (
            <article className="card" key={c.t}>
              <h3 className="display">{c.t}</h3>
              <p>{c.d}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section" id="sample">
        <h2 className="display sec-title">{t.sample.title}</h2>
        <p className="sec-sub">{t.sample.sub}</p>
        <div className="table-wrap">
          <table className="table">
            <thead><tr>{t.sample.cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>
              {t.sample.rows.map((r, i) => (
                <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">{t.sample.note}</p>
      </section>

      <section className="section alt" id="pricing">
        <h2 className="display sec-title">{t.pricing.title}</h2>
        <p className="sec-sub">{t.pricing.sub}</p>
        <div className="grid3">
          {cfg.packages.map((p, i) => (
            <article className={`card price ${i === 1 ? 'featured' : ''}`} key={p.id}>
              <h3 className="display">{t.pricing.names[p.id]}</h3>
              <div className="price-num display" dir="ltr">{money(p.price_cents, cfg.currency)}</div>
              <p className="price-lead"><b>{p.credits}</b> {t.pricing.credits}</p>
              <p className="muted small" dir="ltr">{money(Math.round(p.price_cents / p.credits), cfg.currency)} / {t.pricing.perCandidate}</p>
              <Link to={user ? '/credits' : '/auth'} className="btn btn-block">{t.pricing.pick}</Link>
            </article>
          ))}
        </div>
        {cfg.free_credits > 0 && <p className="addon"><Icon name="plus" size={18} /> {t.pricing.free(cfg.free_credits)}</p>}
      </section>

      <section className="section" id="faq">
        <h2 className="display sec-title">{t.faq.title}</h2>
        <div className="faq">
          {t.faq.items.map((f) => (
            <details key={f.q}>
              <summary>{f.q}</summary>
              <p>{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="cta">
        <h2 className="display">{t.cta.title}</h2>
        <p>{t.cta.sub}</p>
        <Link to={start} className="btn btn-ink">{t.cta.btn} <Icon name="arrow" size={20} /></Link>
      </section>
    </>
  )
}
