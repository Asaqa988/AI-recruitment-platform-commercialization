"""Deterministic rules shared by every engine.

The agents write, extract and judge; these functions do the arithmetic and enforce the policy the original
crew only asked for in prose: advisory-only decisions, HR approval gates, and consistent scores.
"""
import re

STAGES = ("screen", "evaluate", "salary", "documents", "report")
EMAIL_SCENARIOS = (
    "application_received", "interview_invitation", "passed", "not_passed",
    "salary_discussion", "document_request", "missing_documents", "final_hiring",
)
# Emails that communicate a final outcome need a recorded HR outcome that matches.
HR_GATED = {"not_passed": "fail", "final_hiring": "pass"}
HR_OUTCOMES = ("pass", "fail", "hold")

CV_RECOMMENDATIONS = ("Proceed", "Manual Review", "Does Not Meet Criteria")
DECISIONS = ("Pass", "Fail", "Manual Review")
QUESTIONS = 10


def valid_stage(key: str) -> bool:
    return key in STAGES or (key.startswith("email:") and key[6:] in EMAIL_SCENARIOS)


def clamp(value, lo: int, hi: int) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, n))


def norm_cv_recommendation(s: str) -> str:
    low = (s or "").lower()
    if "not meet" in low or "does not" in low or "reject" in low:
        return "Does Not Meet Criteria"
    if "proceed" in low:
        return "Proceed"
    return "Manual Review"


def norm_decision(s: str) -> str:
    low = (s or "").strip().lower()
    if low.startswith("pass"):
        return "Pass"
    if low.startswith("fail"):
        return "Fail"
    return "Manual Review"


# ---------- salary ----------

def _num(x) -> float | None:
    try:
        return None if x is None or x == "" else float(x)
    except (TypeError, ValueError):
        return None


def classify_salary(expected, currency: str, job_currency: str, lo, hi) -> dict:
    e, lo, hi = _num(expected), _num(lo), _num(hi)
    if e is None:
        return {"scenario": "unknown", "note": "No expected salary is recorded for this candidate."}
    if lo is None or hi is None:
        return {"scenario": "unknown", "note": "The job has no approved salary range."}
    if currency and job_currency and currency.upper() != job_currency.upper():
        return {"scenario": "unknown", "note": f"Currencies differ ({currency} vs {job_currency}); HR must compare manually."}
    scenario = "below" if e < lo else "above" if e > hi else "within"
    return {"scenario": scenario, "expected": e, "range": [lo, hi], "currency": job_currency or currency, "note": ""}


# ---------- documents ----------

_DOC_SYNONYMS = {"resume": "cv", "curriculum": "cv", "vitae": "cv"}
_DOC_NOISE = {"copy", "scan", "scanned", "of", "the", "a", "file", "document", "doc", "pdf", "docx", "jpg", "jpeg", "png"}


def _tokens(s: str) -> set[str]:
    words = re.findall(r"[^\W_]+", (s or "").lower())  # underscores split too: jane_cv.pdf -> jane, cv
    return {_DOC_SYNONYMS.get(w, w) for w in words} - _DOC_NOISE


def match_documents(required: list[str], submitted: list[str]) -> list[dict]:
    """Checks completeness only: a required document counts as received when a submitted
    file name or description mentions all of its words. It says nothing about authenticity."""
    sub = [(s, _tokens(s)) for s in submitted]
    out = []
    for r in required:
        rt = _tokens(r)
        hit = next((s for s, t in sub if rt and rt <= t), None)
        out.append({"document": r, "status": "Received" if hit else "Missing", "matched": hit or ""})
    return out


# ---------- interview evaluation ----------

def split_answers(transcript: str) -> list[str]:
    """Best-effort split of a pasted Q&A transcript into answers. Used by the sample engine; the
    live engine lets the model read the transcript."""
    parts = re.split(r"(?im)^\s*(?:a|answer|ans)\s*\d*\s*[:.)\-]\s*", transcript)
    return [p.strip() for p in parts[1:] if p.strip()]


def finalize_evaluation(items: list[dict], cv: dict, passing_score: int, agent_decision: str) -> dict:
    """Interview score = sum of ten 0-10 answer scores (computed here, not trusted from the model).
    The decision is advisory and is forced to Manual Review whenever the evidence is inconsistent."""
    items = [dict(i) for i in items[:QUESTIONS]]
    for n, i in enumerate(items, 1):
        i["n"] = n
        i["score"] = clamp(i.get("score"), 0, 10)
    answered = sum(1 for i in items if str(i.get("answer", "")).strip() and not i.get("unanswered"))
    final = sum(i["score"] for i in items)
    incomplete = answered < QUESTIONS
    cv_reco = cv.get("recommendation", "Manual Review")
    decision = norm_decision(agent_decision)
    notes: list[str] = []
    if incomplete:
        decision = "Manual Review"
        notes.append(f"Only {answered} of {QUESTIONS} answers were found in the transcript, so the interview score is partial.")
    elif decision == "Pass" and final < passing_score:
        decision = "Manual Review"
        notes.append(f"The model suggested Pass but the interview score {final} is below the passing score {passing_score}.")
    elif decision == "Pass" and cv_reco == "Does Not Meet Criteria":
        decision = "Manual Review"
        notes.append("The model suggested Pass but the CV screening found the candidate does not meet the criteria.")
    elif decision == "Fail" and final >= passing_score and cv_reco != "Does Not Meet Criteria":
        decision = "Manual Review"
        notes.append(f"The model suggested Fail but the interview score {final} meets the passing score {passing_score}.")
    return {
        "items": items,
        "interview_score": final,
        "answers_found": answered,
        "incomplete": incomplete,
        "decision": decision,
        "guard_notes": notes,
        "passing_score": passing_score,
        "cv_score": cv.get("score"),
        "cv_recommendation": cv_reco,
        "requires_hr_approval": True,
    }


# ---------- report checklist ----------

STAGE_LABELS = {
    "en": {"screen": "CV screening and interview questions", "evaluate": "Interview evaluation and recommendation",
           "salary": "Salary expectation", "documents": "Document check", "hr": "HR decision recorded"},
    "ar": {"screen": "فرز السيرة الذاتية وأسئلة المقابلة", "evaluate": "تقييم المقابلة والتوصية",
           "salary": "التوقع الراتبي", "documents": "فحص المستندات", "hr": "تسجيل قرار الموارد البشرية"},
}


def stage_checklist(stages: dict, candidate: dict, language: str = "en") -> list[dict]:
    labels = STAGE_LABELS.get(language, STAGE_LABELS["en"])
    rows = []
    for key in ("screen", "evaluate", "salary", "documents"):
        s = stages.get(key)
        rows.append({"stage": key, "label": labels[key], "done": bool(s and s["status"] == "completed")})
    rows.append({"stage": "hr", "label": labels["hr"], "done": bool(candidate.get("hr_outcome"))})
    return rows
