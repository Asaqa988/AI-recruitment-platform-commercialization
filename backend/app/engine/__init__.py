"""Engines run one pipeline stage for one candidate.

Contract: run_stage(stage, ctx, emit) -> dict (JSON-serialisable result for that stage)
  ctx  = {"job": dict, "candidate": dict, "stages": {stage_key: stage_run}, "params": dict}
  emit = Callable[[stage, message], None]  progress reporting

Stage keys: screen, evaluate, salary, documents, report, and email:<scenario>.

The live engine (crew_engine) and the sample engine (demo) only produce what needs judgement or writing.
Deterministic parts (salary class, document checklist, interview score, decision guards, HR approval
gates) are computed here, in rules.py, so both engines obey the same policy.
"""
import importlib.util
import time

from .. import config
from . import rules


class StageNotReady(ValueError):
    """The stage cannot run yet; the message tells the customer what is missing."""


LLM_KEYS = {
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "anthropic": ("ANTHROPIC_API_KEY",),
}


def crew_available() -> tuple[bool, str]:
    if importlib.util.find_spec("crewai") is None:
        return False, "crewai is not installed (pip install -r requirements-crew.txt)"
    provider = config.CREW_MODEL.split("/", 1)[0]
    names = LLM_KEYS.get(provider, ())
    if names and not any(config.env(n) for n in names):
        return False, f"{' or '.join(names)} is not set (CREW_MODEL={config.CREW_MODEL})"
    return True, ""


def pick_engine() -> tuple[str, str]:
    """Returns (engine_name, reason)."""
    wanted = config.ENGINE
    ok, why = crew_available()
    if wanted == "demo":
        return "demo", "ENGINE=demo"
    if wanted == "crew":
        if not ok:
            raise RuntimeError(f"ENGINE=crew but {why}")
        return "crew", "ENGINE=crew"
    return ("crew", "live engine ready") if ok else ("demo", why)


def _impl():
    if pick_engine()[0] == "crew":
        from . import crew_engine
        return crew_engine
    from . import demo
    return demo


def check_ready(stage: str, candidate: dict, job: dict, stages: dict) -> str | None:
    """None when the stage can run, otherwise a human-readable reason. Used before queueing and again
    when the job starts, so the HR-approval gates cannot be bypassed from the API."""
    if not rules.valid_stage(stage):
        return "Unknown stage"

    def done(key: str) -> bool:
        return stages.get(key, {}).get("status") == "completed"

    if stage == "screen":
        if not candidate["cv_text"].strip():
            return "This candidate has no CV text."
    elif stage == "evaluate":
        if not done("screen"):
            return "Run the CV screening first."
        if len(candidate["transcript"].strip()) < 80:
            return "Paste the interview transcript first (questions and answers)."
    elif stage == "salary":
        if candidate["expected_salary"] is None:
            return "Record the candidate's expected salary first."
        if job["salary_min"] is None or job["salary_max"] is None:
            return "Set the approved salary range on the job first."
    elif stage == "documents":
        if not job["required_documents"]:
            return "This job has no required documents. Add them to the job first."
    elif stage == "report":
        if not done("screen"):
            return "Run the CV screening first."
    elif stage.startswith("email:"):
        scenario = stage[6:]
        if not candidate["email"]:
            return "Add the candidate's email address first."
        needed = rules.HR_GATED.get(scenario)
        if needed and candidate["hr_outcome"] != needed:
            return (f"This email needs a recorded HR decision of '{needed}'. "
                    "The platform never drafts a rejection or a hiring email without it.")
        if scenario == "passed" and not done("evaluate"):
            return "Evaluate the interview first."
        if scenario == "salary_discussion" and not done("salary"):
            return "Run the salary check first."
        if scenario == "missing_documents":
            docs = stages.get("documents", {})
            if docs.get("status") != "completed":
                return "Run the document check first."
            if docs["result"] and docs["result"].get("complete"):
                return "No documents are missing."
    return None


def _clean_list(values, limit: int = 12) -> list[str]:
    return [str(v).strip() for v in (values or []) if str(v).strip()][:limit]


def run_stage(stage: str, ctx: dict, emit) -> dict:
    problem = check_ready(stage, ctx["candidate"], ctx["job"], ctx["stages"])
    if problem:
        raise StageNotReady(problem)
    impl = _impl()
    job, cand, stages = ctx["job"], ctx["candidate"], ctx["stages"]

    if stage == "screen":
        raw = impl.screen(ctx, emit)
        s = raw["screening"]
        s["score"] = rules.clamp(s.get("score"), 0, 100)
        s["recommendation"] = rules.norm_cv_recommendation(s.get("recommendation", ""))
        for k in ("missing_qualifications", "evidence"):
            s[k] = _clean_list(s.get(k))
        ex = s.get("extracted") or {}
        s["extracted"] = {k: _clean_list(ex.get(k), 20) for k in ("education", "experience", "skills", "certifications", "projects")}
        qs = raw["questions"]["items"][: rules.QUESTIONS]
        for n, q in enumerate(qs, 1):
            q["n"] = n
        if len(qs) < rules.QUESTIONS:
            emit("screen", f"warning: only {len(qs)} interview questions were produced")
        return {"screening": s, "questions": {"items": qs, "invitation_note": raw["questions"].get("invitation_note", "")}}

    if stage == "evaluate":
        raw = impl.evaluate(ctx, emit)
        cv = stages["screen"]["result"]["screening"]
        result = rules.finalize_evaluation(raw["items"], cv, job["passing_score"], raw.get("decision", ""))
        result.update(
            summary=raw.get("summary", ""), reasoning=raw.get("reasoning", ""),
            strengths=_clean_list(raw.get("strengths")), weaknesses=_clean_list(raw.get("weaknesses")),
        )
        if result["guard_notes"]:
            emit("evaluate", "decision adjusted to Manual Review: " + " ".join(result["guard_notes"]))
        return result

    if stage == "salary":
        facts = rules.classify_salary(cand["expected_salary"], cand["currency"], job["currency"],
                                      job["salary_min"], job["salary_max"])
        emit("salary", f"classified as {facts['scenario']}")
        raw = impl.salary(ctx, facts, emit)
        return {**facts, "reply_subject": raw.get("reply_subject", ""), "reply_body": raw.get("reply_body", ""),
                "flexibility_question": raw.get("flexibility_question", "")}

    if stage == "documents":
        checklist = rules.match_documents(job["required_documents"], cand["submitted_documents"])
        missing = [c["document"] for c in checklist if c["status"] == "Missing"]
        emit("documents", f"{len(checklist) - len(missing)}/{len(checklist)} required documents received")
        raw = impl.documents(ctx, checklist, emit) if missing else {}
        return {
            "checklist": checklist, "complete": not missing, "missing": missing,
            "flags": _clean_list(raw.get("flags")),
            "reminder_subject": raw.get("reminder_subject", "") if missing else "",
            "reminder_body": raw.get("reminder_body", "") if missing else "",
            "disclaimer": "Completeness only. This check does not verify that any document is authentic.",
        }

    if stage.startswith("email:"):
        scenario = stage[6:]
        raw = impl.email(ctx, scenario, emit)
        gated = scenario in rules.HR_GATED
        return {
            "scenario": scenario, "subject": raw.get("subject", ""), "body": raw.get("body", ""),
            "requires_hr_approval": gated,
            "hr_approved": (not gated) or cand["hr_outcome"] == rules.HR_GATED[scenario],
            "send_note": raw.get("send_note", ""),
        }

    # report
    checklist = rules.stage_checklist(stages, cand, job["language"])
    emit("report", "compiling the HR report")
    raw = impl.report(ctx, checklist, emit)
    return {"checklist": checklist, "markdown": _assemble_report(ctx, checklist, raw.get("narrative", ""))}


def _assemble_report(ctx: dict, checklist: list[dict], narrative: str) -> str:
    job, cand = ctx["job"], ctx["candidate"]
    ar = job["language"] == "ar"
    t = {
        "title": "تقرير التوظيف" if ar else "HR onboarding report",
        "advisory": "هذا التقرير مُنشأ بالذكاء الاصطناعي واستشاري فقط. التوظيف النهائي يتطلب موافقة صريحة من الموارد البشرية."
        if ar else "AI-generated and advisory only. Final hiring requires explicit HR approval.",
        "stages": "مراحل العملية" if ar else "Stage checklist",
        "hr": "قرار الموارد البشرية" if ar else "HR decision",
        "none": "لم يُسجَّل بعد" if ar else "not recorded yet",
        "done": "مكتمل" if ar else "complete", "todo": "غير مكتمل" if ar else "not done",
    }
    outcome = {"pass": "Pass", "fail": "Fail", "hold": "On hold"}.get(cand["hr_outcome"] or "", t["none"])
    lines = [
        f"# {t['title']}: {cand['name']}", f"**{job['title']}** · {job['company']} · {time.strftime('%Y-%m-%d')}", "",
        f"> {t['advisory']}", "", f"## {t['stages']}", "",
    ]
    lines += [f"- [{'x' if r['done'] else ' '}] {r['label']} ({t['done'] if r['done'] else t['todo']})" for r in checklist]
    lines += ["", f"## {t['hr']}", "", f"**{outcome}**" + (f" — {cand['hr_note']}" if cand["hr_note"] else ""), "", narrative.strip()]
    return "\n".join(lines).strip() + "\n"
