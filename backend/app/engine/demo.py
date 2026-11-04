"""Sample-data engine: lets the whole platform be demonstrated without API keys.

It is not an LLM. Screening scores keyword overlap between the CV and the job description and the
other stages fill templates, so every output is labelled "[sample]" and the stage run is flagged is_demo.
"""
import re
import time

from . import rules

_STOP = set("""a an and are as at be by for from has have in is it of on or that the their this to with will you your we our
about into more most other such than then them they these those who whom which while would should could can may might must
work working experience years year role team skills ability strong good excellent responsible including etc able""".split())


def _keywords(text: str) -> list[str]:
    words = [w.strip(".-") for w in re.findall(r"[a-zA-Z][a-zA-Z+#.\-]{2,}", text.lower())]
    words = [w for w in words if len(w) > 2 and w not in _STOP]
    seen: dict[str, int] = {}
    for w in words:
        seen[w] = seen.get(w, 0) + 1
    return sorted(seen, key=lambda w: (-seen[w], w))[:25]


def _lines(text: str, pattern: str, limit: int = 4) -> list[str]:
    rx = re.compile(pattern, re.I)
    return [ln.strip(" -•*\t")[:160] for ln in text.splitlines() if rx.search(ln) and ln.strip()][:limit]


def screen(ctx: dict, emit) -> dict:
    job, cv = ctx["job"], ctx["candidate"]["cv_text"]
    emit("screen", "[sample] screening the CV against the job requirements")
    time.sleep(0.8)
    wanted = _keywords(job["title"] + " " + job["description"])
    low = cv.lower()
    hit = [w for w in wanted if w in low]
    miss = [w for w in wanted if w not in low]
    overlap = len(hit) / max(1, len(wanted))
    score = rules.clamp(30 + overlap * 65, 0, 100)
    reco = "Proceed" if score >= 70 else "Manual Review" if score >= 45 else "Does Not Meet Criteria"
    screening = {
        "extracted": {
            "education": _lines(cv, r"universit|bachelor|master|b\.?sc|m\.?sc|degree|diploma|college"),
            "experience": _lines(cv, r"\b(19|20)\d{2}\b.*(–|-|to|present)|\d+\+?\s*years"),
            "skills": hit[:10],
            "certifications": _lines(cv, r"certif|licen[sc]e"),
            "projects": _lines(cv, r"project"),
        },
        "score": score,
        "missing_qualifications": miss[:6],
        "evidence": [f"The CV mentions '{w}', which the job asks for." for w in hit[:4]],
        "recommendation": reco,
        "summary": f"[sample] {len(hit)} of {len(wanted)} job keywords appear in the CV.",
    }
    emit("questions", "[sample] preparing interview questions")
    time.sleep(0.6)
    topics = (hit + miss + ["teamwork", "delivery", "quality"])[:10]
    kinds = ["technical", "technical", "technical", "practical", "practical", "behavioral", "behavioral", "technical", "practical", "behavioral"]
    levels = ["easy", "easy", "medium", "medium", "medium", "medium", "hard", "hard", "hard", "medium"]
    items = [
        {"n": i + 1, "type": kinds[i], "difficulty": levels[i],
         "question": f"[sample] Tell us about a time you used or learned {topics[i]} in a {job['title']} context.",
         "follow_up_hint": "Ask for a concrete result, number or trade-off."}
        for i in range(10)
    ]
    return {"screening": screening,
            "questions": {"items": items, "invitation_note": "[sample] Invite the candidate for a 45-minute interview; share the format in advance."}}


def evaluate(ctx: dict, emit) -> dict:
    emit("evaluate", "[sample] evaluating the interview answers")
    time.sleep(0.8)
    questions = ctx["stages"]["screen"]["result"]["questions"]["items"]
    answers = rules.split_answers(ctx["candidate"]["transcript"])
    items = []
    for i, q in enumerate(questions):
        ans = answers[i] if i < len(answers) else ""
        words = len(ans.split())
        score = 0 if not words else min(10, 3 + words // 12)
        items.append({
            "n": i + 1, "question": q["question"], "answer": ans, "unanswered": not words, "score": score,
            "explanation": "[sample] Scored on answer length only; a live run scores accuracy, reasoning and communication." if words else "No answer found in the transcript.",
            "strengths": ["Detailed answer"] if words > 40 else [], "weaknesses": [] if words > 15 else ["Very short or missing answer"],
        })
    total = sum(i["score"] for i in items)
    return {
        "items": items, "summary": f"[sample] {len(answers)} answers found; total score {total}/100.",
        "strengths": ["[sample] Answers were provided"] if answers else [], "weaknesses": [],
        "decision": "Pass" if total >= ctx["job"]["passing_score"] else "Fail",
        "reasoning": "[sample] Based on the interview score against the passing score.",
    }


def salary(ctx: dict, facts: dict, emit) -> dict:
    emit("salary", "[sample] drafting the salary reply")
    name, scenario = ctx["candidate"]["name"], facts["scenario"]
    body = {
        "within": "your expectation fits the approved range for this role",
        "below": "your expectation is below the range we budgeted for this role",
        "above": "your expectation is above the range we budgeted for this role",
        "unknown": "we need to confirm the salary details with you",
    }[scenario]
    return {
        "reply_subject": f"[sample] Salary discussion: {ctx['job']['title']}",
        "reply_body": f"Dear {name},\n\n[sample] Thank you for sharing your salary expectation. We have reviewed it and {body}. "
                      "This is not an offer; any offer needs HR approval.\n\nBest regards,\n" + ctx["job"]["company"],
        "flexibility_question": "Is there any flexibility on your expectation?" if scenario == "above" else "",
    }


def documents(ctx: dict, checklist: list[dict], emit) -> dict:
    emit("documents", "[sample] drafting the document reminder")
    missing = [c["document"] for c in checklist if c["status"] == "Missing"]
    return {
        "flags": [],
        "reminder_subject": f"[sample] Documents still needed: {ctx['job']['title']}",
        "reminder_body": f"Dear {ctx['candidate']['name']},\n\n[sample] We have not yet received: " + ", ".join(missing)
                         + ".\nPlease send them at your earliest convenience.\n\nBest regards,\n" + ctx["job"]["company"],
    }


def email(ctx: dict, scenario: str, emit) -> dict:
    emit("email", f"[sample] drafting the '{scenario}' email")
    job, cand = ctx["job"], ctx["candidate"]
    topic = scenario.replace("_", " ")
    return {
        "subject": f"[sample] {topic.capitalize()}: {job['title']}",
        "body": f"Dear {cand['name']},\n\n[sample] This is a placeholder '{topic}' email for the {job['title']} role.\n\n"
                f"Best regards,\n{job['company']}",
        "send_note": "[sample] Review before sending. The platform never sends email itself.",
    }


def report(ctx: dict, checklist: list[dict], emit) -> dict:
    stages = ctx["stages"]
    out = ["## Summary", "", "[sample] Generated by the sample engine from the stage results below.", ""]
    s = stages.get("screen", {}).get("result")
    if s:
        out += ["### CV screening", f"Score {s['screening']['score']}/100, recommendation: {s['screening']['recommendation']}.", ""]
    e = stages.get("evaluate", {}).get("result")
    if e:
        out += ["### Interview", f"Interview score {e['interview_score']}/100 (passing score {e['passing_score']}). AI recommendation: {e['decision']}, pending HR approval.", ""]
    sal = stages.get("salary", {}).get("result")
    if sal:
        out += ["### Salary", f"Expectation is {sal['scenario']} the approved range.", ""]
    d = stages.get("documents", {}).get("result")
    if d:
        out += ["### Documents", "Complete." if d["complete"] else "Missing: " + ", ".join(d["missing"]) + ".", ""]
    open_items = [r["label"] for r in checklist if not r["done"]]
    out += ["### Open items", ("- " + "\n- ".join(open_items)) if open_items else "None."]
    return {"narrative": "\n".join(out)}
