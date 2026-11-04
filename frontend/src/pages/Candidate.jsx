import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useApp } from '../App.jsx'
import { amount, api, download } from '../api.js'
import Icon from '../components/icons.jsx'
import { CopyButton, CvBadge, DecisionBadge, Lines, Markdown, OutcomeBadge, Score, StageBadge } from '../components/ui.jsx'

const isActive = (s) => s && (s.status === 'queued' || s.status === 'running')

function StageCard({ id, title, hint, stage, locked, children, actions }) {
  const { t } = useApp()
  return (
    <article className={`card stage ${locked ? 'is-locked' : ''}`} id={id}>
      <div className="page-head">
        <h2 className="display">{title}</h2>
        {stage !== null && <StageBadge status={stage?.status} />}
      </div>
      {hint && <p className="muted">{hint}</p>}
      {stage?.status === 'failed' && <p className="error" role="alert">{t.cand.failed}: {stage.error}</p>}
      {stage?.is_demo && stage.status === 'completed' && <p className="banner">{t.cand.demo}</p>}
      {children}
      {actions && <div className="actions">{actions}</div>}
    </article>
  )
}

function RunButton({ stage, onRun, label, disabled, max, extra }) {
  const { t } = useApp()
  const active = isActive(stage)
  const used = stage?.attempts || 0
  const limited = used >= max
  return (
    <>
      <button className="btn" disabled={active || limited || disabled} onClick={onRun}>
        {active ? t.cand.working : stage?.status === 'completed' || stage?.status === 'failed' ? t.cand.rerun : label}
      </button>
      {extra}
      {limited && <span className="muted small">{t.cand.limit(max)}</span>}
    </>
  )
}

function ScreeningView({ r }) {
  const { t } = useApp()
  const s = r.screening
  const ex = s.extracted
  return (
    <>
      <div className="score-row">
        <Score value={s.score} label={t.cand.cvScore} />
        <CvBadge value={s.recommendation} />
      </div>
      {s.summary && <p>{s.summary}</p>}
      <div className="cols">
        <div><h4>{t.cand.education}</h4><Lines items={ex.education} /></div>
        <div><h4>{t.cand.experience}</h4><Lines items={ex.experience} /></div>
        <div><h4>{t.cand.skills}</h4><Lines items={ex.skills} /></div>
        <div><h4>{t.cand.certs}</h4><Lines items={ex.certifications} /></div>
        <div><h4>{t.cand.projects}</h4><Lines items={ex.projects} /></div>
        <div><h4>{t.cand.missing}</h4><Lines items={s.missing_qualifications} empty={t.cand.nothingMissing} /></div>
        <div><h4>{t.cand.evidence}</h4><Lines items={s.evidence} /></div>
      </div>
      <details className="log">
        <summary>{t.cand.questions} · {r.questions.items.length}</summary>
        <ol className="qlist">
          {r.questions.items.map((q) => (
            <li key={q.n}>
              <b>{q.question}</b>
              <div className="muted small">{q.type} · {q.difficulty}{q.follow_up_hint ? ` — ${q.follow_up_hint}` : ''}</div>
            </li>
          ))}
        </ol>
        {r.questions.invitation_note && <p className="muted small"><b>{t.cand.invite}:</b> {r.questions.invitation_note}</p>}
      </details>
    </>
  )
}

function EvaluationView({ r }) {
  const { t } = useApp()
  return (
    <>
      <div className="score-row">
        <Score value={r.interview_score} label={t.cand.interviewScore} />
        <div className="score"><b className="display" dir="ltr">{r.passing_score}</b><span className="muted small">{t.cand.passingScore}</span></div>
        <div><span className="muted small">{t.cand.aiRec}</span><br /><DecisionBadge value={r.decision} /></div>
      </div>
      {r.guard_notes.map((n, i) => <p className="banner" key={i}>{n}</p>)}
      {r.reasoning && <p>{r.reasoning}</p>}
      {r.summary && <p className="muted">{r.summary}</p>}
      <p className="muted small">{t.cand.advisory}</p>
      <details className="log">
        <summary>{t.cand.perAnswer} · {r.answers_found}/10</summary>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>#</th><th>{t.cand.answer}</th><th>{t.cand.score}</th><th>{t.cand.why}</th></tr></thead>
            <tbody>
              {r.items.map((i) => (
                <tr key={i.n}>
                  <td>{i.n}</td>
                  <td><b>{i.question}</b><div className="muted small">{i.unanswered ? t.cand.noAnswer : i.answer}</div></td>
                  <td dir="ltr"><b>{i.score}</b>/10</td>
                  <td>{i.explanation}
                    {i.strengths?.length > 0 && <div className="small"><b>+</b> {i.strengths.join('; ')}</div>}
                    {i.weaknesses?.length > 0 && <div className="small"><b>−</b> {i.weaknesses.join('; ')}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  )
}

function DraftView({ subject, body, note }) {
  const { t } = useApp()
  return (
    <div className="draft">
      {subject && <b>{subject}</b>}
      <pre dir="auto">{body}</pre>
      {note && <p className="muted small">{note}</p>}
      <CopyButton text={`${subject ? `${subject}\n\n` : ''}${body}`} label={t.cand.copyDraft} />
    </div>
  )
}

export default function Candidate() {
  const { id } = useParams()
  const { t, user, ready, config, reloadUser, lang } = useApp()
  const navigate = useNavigate()
  const location = useLocation()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(location.state?.notice ? { msg: location.state.notice, credits: true } : null)
  const dataRef = useRef(null)

  const [transcript, setTranscript] = useState(null)
  const [docsText, setDocsText] = useState(null)
  const [salary, setSalary] = useState(null)
  const [scenario, setScenario] = useState('application_received')
  const [outcome, setOutcome] = useState(null)
  const [note, setNote] = useState(null)
  const [emailDraft, setEmailDraft] = useState('')

  const load = useCallback(() => api(`/candidates/${id}`).then((d) => { dataRef.current = d; setData(d) }).catch((e) => setError(e.message)), [id])
  useEffect(() => {
    if (!user) return undefined
    load()
    // Fast while agents are working; slow otherwise, because the applicant can change things from their own account.
    const timer = setInterval(load, 3000)
    return () => clearInterval(timer)
  }, [user, load])

  // seed the editable fields once, from what the server holds
  useEffect(() => {
    if (!data) return
    const c = data.candidate
    setTranscript((v) => v ?? c.transcript)
    setDocsText((v) => v ?? c.submitted_documents.join('\n'))
    setSalary((v) => v ?? { amount: c.expected_salary ?? '', currency: c.currency || data.job.currency })
    setOutcome((v) => v ?? c.hr_outcome)
    setNote((v) => v ?? c.hr_note)
  }, [data])

  if (!ready) return <p className="page muted">{t.common.loading}</p>
  if (!user) return <Navigate to="/auth" state={{ from: `/candidates/${id}` }} replace />
  if (error) return <section className="page"><p className="error">{error}</p><Link to="/jobs" className="btn btn-sm">{t.job.back}</Link></section>
  if (!data || transcript === null || salary === null || note === null) return <p className="page muted">{t.common.loading}</p>

  const { candidate: c, job, stages, events } = data
  const max = data.max_attempts
  const done = (k) => stages[k]?.status === 'completed'
  const patch = (body) => api(`/candidates/${id}`, { method: 'PATCH', body })
  const run = async (stage, before, skipStage) => {
    setNotice(null)
    try {
      if (before) await before()
      if (!skipStage && stage) await api(`/candidates/${id}/stages/${stage}`, { method: 'POST' })
      await load()
      reloadUser()
    } catch (e) {
      setNotice({ msg: e.message, credits: e.status === 402 })
    }
  }
  const saveDecision = async (value) => {
    setNotice(null)
    try {
      await api(`/candidates/${id}/decision`, { method: 'POST', body: { outcome: value, note } })
      setOutcome(value === 'none' ? null : value)
      if (value === 'none') setNote('')
      await load()
    } catch (e) { setNotice({ msg: e.message }) }
  }
  const remove = async () => {
    if (!window.confirm(t.cand.confirmDelete)) return
    try { await api(`/candidates/${id}`, { method: 'DELETE' }); navigate(`/jobs/${job.id}`) } catch (e) { setNotice({ msg: e.message }) }
  }

  const emailStages = Object.entries(stages).filter(([k]) => k.startsWith('email:'))
  const gate = config?.hr_gated?.[scenario]
  const gateMissing = gate && c.hr_outcome !== gate
  const needsEval = scenario === 'passed' && !done('evaluate')
  const needsSalary = scenario === 'salary_discussion' && !done('salary')
  const needsDocs = scenario === 'missing_documents' && !done('documents')
  const emailBlocked = !c.email || gateMissing || needsEval || needsSalary || needsDocs
  const emailWhy = !c.email ? t.cand.needEmail : gateMissing ? t.cand.gate(t.outcome[gate]) : needsEval ? t.cand.needEval
    : needsSalary ? t.cand.needSalary : needsDocs ? t.cand.needDocs : ''
  const hasJobRange = job.salary_min != null
  const sal = stages.salary?.result
  const docs = stages.documents?.result
  const report = stages.report

  // One obvious "what now" for HR, so the next action is never buried below the results.
  const scrollTo = (anchor) => document.getElementById(anchor)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  let next = { key: 'after', anchor: 'emails' }
  if (isActive(stages.screen) || isActive(stages.evaluate)) next = { key: 'working' }
  else if (!done('screen')) next = { key: 'runScreen', anchor: 'screen' }
  else if (c.applicant && c.interview_status === 'none') next = { key: 'sendInterview', action: () => run('', () => api(`/candidates/${id}/interview/send`, { method: 'POST' }), true) }
  else if (c.applicant && c.interview_status === 'sent') next = { key: 'waiting' }
  else if (!done('evaluate')) next = { key: c.applicant ? 'runEval' : 'pasteTranscript', anchor: 'evaluate' }
  else if (!c.hr_outcome) next = { key: 'decide', anchor: 'decision' }

  return (
    <section className="page">
      <Link to={`/jobs/${job.id}`} className="back">← {job.title}</Link>
      <div className="page-head">
        <h1 className="display page-title">{c.name}</h1>
        <div className="row-end">
          <OutcomeBadge value={c.hr_outcome} />
          <button className="btn btn-sm btn-ghost" onClick={remove}><Icon name="trash" size={16} /> {t.cand.delete}</button>
        </div>
      </div>
      <p className="muted"><span dir="ltr">{c.email || t.cand.noEmail}</span> · {c.cv_filename || t.cand.pasted} · {c.cv_chars} {t.cand.chars}
        {c.applicant && <> · <span className="badge">{t.cand.applicantBadge}</span></>}</p>
      {notice && (
        <p className="banner" role="alert">
          {notice.msg} {notice.credits && <Link to="/credits" className="linkbtn">{t.jobs.buy}</Link>}
        </p>
      )}

      <div className="card nextstep" role="status">
        <div>
          <span className="muted small">{t.cand.nextLabel}</span>
          <p><b>{t.cand.next[next.key]}</b></p>
        </div>
        {next.action && <button className="btn" onClick={next.action}>{t.cand.sendInterview}</button>}
        {!next.action && next.anchor && <button className="btn btn-ghost" onClick={() => scrollTo(next.anchor)}>{t.cand.goTo}</button>}
      </div>

      <StageCard id="screen" title={`1 · ${t.stageNames.screen}`} hint={!stages.screen ? t.cand.screenHint : null} stage={stages.screen}
        actions={<RunButton stage={stages.screen} max={max} onRun={() => run('screen')}
          label={`${t.cand.runScreen}${c.credit_charged ? '' : ` (${t.cand.oneCredit})`}`} />}>
        {done('screen') && <ScreeningView r={stages.screen.result} />}
      </StageCard>

      <StageCard id="evaluate" title={`2 · ${t.stageNames.evaluate}`} hint={c.applicant ? t.cand.sendHint : t.cand.evalHint} stage={stages.evaluate} locked={!done('screen')}
        actions={c.applicant ? (
          <>
            {c.interview_status === 'none' && (
              <button className="btn" disabled={!done('screen')} onClick={() => run('', () => api(`/candidates/${id}/interview/send`, { method: 'POST' }), true)}>
                {t.cand.sendInterview}
              </button>
            )}
            {c.interview_status === 'sent' && <span className="banner">{t.cand.waitingAnswers}</span>}
            {c.interview_status === 'answered' && (
              <RunButton stage={stages.evaluate} max={max} disabled={!done('screen')} label={t.cand.runEval} onRun={() => run('evaluate')} />
            )}
          </>
        ) : (
          <RunButton stage={stages.evaluate} max={max} disabled={!done('screen') || transcript.trim().length < 80}
            label={t.cand.runEval} onRun={() => run('evaluate', () => patch({ transcript }))} />
        )}>
        {c.applicant ? (
          c.interview_status === 'answered' && (
            <details className="log" open={!done('evaluate')}>
              <summary>{t.cand.answeredByCand}</summary>
              <pre className="plain" dir="auto">{c.transcript}</pre>
            </details>
          )
        ) : (
          <label className="field">{t.cand.transcript}
            <textarea rows={8} value={transcript} onChange={(e) => setTranscript(e.target.value)} placeholder={t.cand.transcriptPh}
              disabled={!done('screen')} maxLength={30000} />
          </label>
        )}
        {done('evaluate') && <EvaluationView r={stages.evaluate.result} />}
      </StageCard>

      <StageCard id="decision" title={`3 · ${t.cand.hrTitle}`} hint={t.cand.hrHint} stage={null} locked={!done('screen')}>
        {done('evaluate') && (
          <p>{t.cand.aiSays}: <DecisionBadge value={stages.evaluate.result.decision} /> · <span className="muted">{t.cand.pending}</span></p>
        )}
        <div className="chips" role="group" aria-label={t.cand.hrTitle}>
          {['pass', 'fail', 'hold'].map((o) => (
            <button key={o} type="button" className={`chip ${outcome === o ? 'on' : ''}`} aria-pressed={outcome === o}
              disabled={!done('screen')} onClick={() => setOutcome(o)}>{t.outcome[o]}</button>
          ))}
        </div>
        <label className="field">{t.cand.hrNote}
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder={t.cand.hrNotePh} disabled={!done('screen')} />
        </label>
        <div className="actions">
          <button className="btn" disabled={!done('screen') || !outcome} onClick={() => saveDecision(outcome)}>{t.cand.hrSave}</button>
          {c.hr_outcome && <button className="btn btn-ghost" onClick={() => saveDecision('none')}>{t.cand.hrClear}</button>}
          {c.hr_outcome && <span className="muted small">{t.cand.hrRecorded}</span>}
        </div>
      </StageCard>

      <StageCard id="emails" title={`4 · ${t.stageNames.email}`} hint={t.cand.emailHint} stage={null}>
        <div className="row-inline">
          <label className="field grow">{t.cand.scenario}
            <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
              {(config?.email_scenarios || []).map((s) => (
                <option key={s} value={s}>{t.emailScn[s]}{config.hr_gated[s] ? ' 🔒' : ''}</option>
              ))}
            </select>
          </label>
          <button className="btn" disabled={emailBlocked || isActive(stages[`email:${scenario}`]) || (stages[`email:${scenario}`]?.attempts || 0) >= max}
            onClick={() => run(`email:${scenario}`)}>
            {isActive(stages[`email:${scenario}`]) ? t.cand.working : stages[`email:${scenario}`] ? t.cand.rerun : t.cand.draftEmail}
          </button>
        </div>
        {!c.email && (
          <form className="row-inline" onSubmit={async (e) => { e.preventDefault(); try { await patch({ email: emailDraft }); await load() } catch (err) { setNotice({ msg: err.message }) } }}>
            <label className="field grow">{t.cand.emailLabel}
              <input type="email" dir="ltr" value={emailDraft} onChange={(e) => setEmailDraft(e.target.value)} required />
            </label>
            <button className="btn btn-ghost">{t.cand.saveEmail}</button>
          </form>
        )}
        {emailWhy && <p className="banner"><Icon name="lock" size={16} /> {emailWhy}</p>}
        {emailStages.map(([k, s]) => (
          <div className="subcard" key={k}>
            <div className="page-head">
              <b>{t.emailScn[k.slice(6)]}</b>
              <div className="row-end">
                {s.result?.requires_hr_approval && (
                  <span className={`badge ${s.result.hr_approved ? 'o-pass' : 'o-fail'}`}>
                    {s.result.hr_approved ? t.cand.approvedBadge : t.cand.notApprovedBadge}
                  </span>
                )}
                <StageBadge status={s.status} />
              </div>
            </div>
            {s.status === 'failed' && <p className="error">{s.error}</p>}
            {s.result && <DraftView subject={s.result.subject} body={s.result.body} note={s.result.send_note} />}
          </div>
        ))}
        <p className="muted small">{t.cand.neverSend}</p>
      </StageCard>

      <StageCard id="salary" title={`5 · ${t.stageNames.salary}`} hint={hasJobRange ? t.cand.salaryHint(amount(job.salary_min, job.currency), amount(job.salary_max, job.currency)) : t.cand.salaryNoRange}
        stage={stages.salary}
        actions={<RunButton stage={stages.salary} max={max} disabled={!hasJobRange || salary.amount === ''} label={t.cand.runSalary}
          onRun={() => run('salary', () => patch({ expected_salary: Number(salary.amount), currency: salary.currency }))} />}>
        <div className="row3">
          <label className="field">{t.cand.expectedSalary}
            <input type="number" min={0} dir="ltr" value={salary.amount} onChange={(e) => setSalary({ ...salary, amount: e.target.value })} />
          </label>
          <label className="field">{t.job.currency}
            <input dir="ltr" maxLength={3} value={salary.currency} onChange={(e) => setSalary({ ...salary, currency: e.target.value.toUpperCase() })} />
          </label>
        </div>
        {sal && (
          <>
            <p><span className={`badge sal-${sal.scenario}`}>{t.salary[sal.scenario]}</span> {sal.note}</p>
            <DraftView subject={sal.reply_subject} body={sal.reply_body} note={sal.flexibility_question} />
          </>
        )}
      </StageCard>

      <StageCard id="documents" title={`6 · ${t.stageNames.documents}`}
        hint={job.required_documents.length ? `${t.cand.docsRequired}: ${job.required_documents.join(', ')}` : t.cand.docsNone} stage={stages.documents}
        actions={<RunButton stage={stages.documents} max={max} disabled={job.required_documents.length === 0} label={t.cand.runDocs}
          onRun={() => run('documents', c.applicant ? null : () => patch({ submitted_documents: docsText.split('\n').map((s) => s.trim()).filter(Boolean) }))} />}>
        {c.applicant ? (
          <div className="field">{t.cand.uploaded}
            {data.documents.length === 0 ? <p className="muted small">{t.cand.nothingUploaded}</p> : (
              <ul className="bullets">
                {data.documents.map((d) => (
                  <li key={d.id}>{d.name} <span className="muted small" dir="ltr">({Math.max(1, Math.round(d.size / 1024))} KB)</span>{' '}
                    <button className="linkbtn" onClick={() => download(`/candidates/${id}/documents/${d.id}`, d.name)}>{t.cand.download}</button></li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <label className="field">{t.cand.docsSubmitted}
            <textarea rows={4} value={docsText} onChange={(e) => setDocsText(e.target.value)} placeholder={t.cand.docsPh} />
          </label>
        )}
        {docs && (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>{t.cand.docName}</th><th>{t.cand.docStatus}</th></tr></thead>
                <tbody>
                  {docs.checklist.map((d) => (
                    <tr key={d.document}><td>{d.document}{d.matched && <div className="muted small">{d.matched}</div>}</td>
                      <td><span className={`badge ${d.status === 'Received' ? 'o-pass' : 'o-fail'}`}>{t.docStatus[d.status]}</span></td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            {docs.flags.length > 0 && <Lines items={docs.flags} />}
            {docs.reminder_body && <DraftView subject={docs.reminder_subject} body={docs.reminder_body} />}
            <p className="muted small">{t.cand.docsDisclaimer}</p>
          </>
        )}
      </StageCard>

      <StageCard id="report" title={`7 · ${t.stageNames.report}`} hint={t.cand.reportHint} stage={report} locked={!done('screen')}
        actions={<>
          <RunButton stage={report} max={max} disabled={!done('screen')} label={t.cand.runReport} onRun={() => run('report')} />
          {report?.status === 'completed' && (
            <>
              <button className="btn btn-ghost" onClick={() => download(`/candidates/${id}/report.md`, `hr-report-${c.name}.md`)}>
                <Icon name="download" size={16} /> {t.cand.download}
              </button>
              <CopyButton text={report.result.markdown} />
            </>
          )}
        </>}>
        {report?.status === 'completed' && <Markdown source={report.result.markdown} />}
      </StageCard>

      <details className="log card">
        <summary>{t.cand.log}</summary>
        <ul>
          {events.map((e, i) => (
            <li key={i}><time dir="ltr">{new Date(e.ts * 1000).toLocaleTimeString(lang === 'ar' ? 'ar-JO' : 'en-GB')}</time> <code>{e.stage}</code> {e.message}</li>
          ))}
        </ul>
      </details>
    </section>
  )
}
