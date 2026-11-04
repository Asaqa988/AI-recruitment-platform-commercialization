"""Jobs, candidates and pipeline stages. Everything here is owner-only: even admins cannot read
another customer's candidates, because the data is personal."""
import csv
import io
import json
import re
import secrets
import time
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator

from . import config, cv, db, engine, runner
from .deps import hr_user as current_user
from .engine import rules

router = APIRouter(prefix="/api")


def _clean(s: str, limit: int) -> str:
    return re.sub(r"\s+", " ", s or "").strip()[:limit]


def _clean_multiline(s: str, limit: int) -> str:
    return re.sub(r"\n{3,}", "\n\n", (s or "").replace("\r", "")).strip()[:limit]


# ---------- jobs ----------

class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    company: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=30, max_length=8000)
    passing_score: int = Field(default=70, ge=0, le=100)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    required_documents: list[str] = Field(default_factory=list, max_length=12)
    language: Literal["en", "ar"] = "en"
    is_open: bool = True

    @field_validator("currency")
    @classmethod
    def _cur(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _range(self):
        if (self.salary_min is None) != (self.salary_max is None):
            raise ValueError("Set both the minimum and the maximum salary, or neither")
        if self.salary_min is not None and self.salary_min > self.salary_max:
            raise ValueError("Minimum salary is above the maximum")
        return self


def _job_values(body: JobIn) -> dict:
    docs = [_clean(d, 80) for d in body.required_documents if d.strip()]
    return dict(
        title=_clean(body.title, 120), company=_clean(body.company, 120),
        description=_clean_multiline(body.description, 8000), passing_score=body.passing_score,
        currency=body.currency, salary_min=body.salary_min, salary_max=body.salary_max,
        required_documents=json.dumps(docs, ensure_ascii=False), language=body.language,
        is_open=1 if body.is_open else 0,
    )


def _public_job(j: dict) -> dict:
    return {k: j[k] for k in ("id", "title", "company", "description", "passing_score", "currency", "salary_min",
                              "salary_max", "required_documents", "language", "is_open", "created_at")}


def _get_job(job_id: str, user: dict) -> dict:
    with db.conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, user["id"])).fetchone()
    if row is None:
        raise HTTPException(404, "Job not found")
    return db.job_row(row)


@router.post("/jobs")
def create_job(body: JobIn, user: dict = Depends(current_user)):
    job_id = secrets.token_hex(5)
    v = _job_values(body)
    with db.conn() as c:
        c.execute(
            """INSERT INTO jobs (id,user_id,title,company,description,passing_score,currency,salary_min,salary_max,
               required_documents,language,is_open,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (job_id, user["id"], v["title"], v["company"], v["description"], v["passing_score"], v["currency"],
             v["salary_min"], v["salary_max"], v["required_documents"], v["language"], v["is_open"], time.time()),
        )
    return _public_job(_get_job(job_id, user))


@router.put("/jobs/{job_id}")
def update_job(job_id: str, body: JobIn, user: dict = Depends(current_user)):
    _get_job(job_id, user)
    v = _job_values(body)
    with db.conn() as c:
        c.execute(
            """UPDATE jobs SET title=?,company=?,description=?,passing_score=?,currency=?,salary_min=?,salary_max=?,
               required_documents=?,language=?,is_open=? WHERE id=?""",
            (v["title"], v["company"], v["description"], v["passing_score"], v["currency"], v["salary_min"],
             v["salary_max"], v["required_documents"], v["language"], v["is_open"], job_id),
        )
    return _public_job(_get_job(job_id, user))


@router.get("/jobs")
def list_jobs(user: dict = Depends(current_user)):
    with db.conn() as c:
        rows = c.execute(
            """SELECT j.*, (SELECT COUNT(*) FROM candidates c WHERE c.job_id=j.id) AS candidate_count
               FROM jobs j WHERE j.user_id=? ORDER BY j.created_at DESC""", (user["id"],)).fetchall()
    return [{**_public_job(db.job_row(r)), "candidate_count": r["candidate_count"]} for r in rows]


def _busy(c, where: str, args: tuple) -> bool:
    return c.execute(
        f"SELECT 1 FROM stage_runs WHERE candidate_id IN (SELECT id FROM candidates WHERE {where}) "
        "AND status IN ('queued','running') LIMIT 1", args).fetchone() is not None


def _delete_candidates(c, where: str, args: tuple) -> None:
    sub = f"SELECT id FROM candidates WHERE {where}"
    c.execute(f"DELETE FROM documents WHERE candidate_id IN ({sub})", args)
    c.execute(f"DELETE FROM events WHERE candidate_id IN ({sub})", args)
    c.execute(f"DELETE FROM stage_runs WHERE candidate_id IN ({sub})", args)
    c.execute(f"DELETE FROM candidates WHERE {where}", args)


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, user: dict = Depends(current_user)):
    _get_job(job_id, user)
    with db.conn() as c:
        if _busy(c, "job_id=?", (job_id,)):
            raise HTTPException(409, "Wait for the running stages to finish first")
        _delete_candidates(c, "job_id=?", (job_id,))
        c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    return {"ok": True}


# ---------- candidates ----------

def _summary(cand: dict, stages: dict) -> dict:
    screen = (stages.get("screen") or {}).get("result") or {}
    ev = (stages.get("evaluate") or {}).get("result") or {}
    return {
        "id": cand["id"], "name": cand["name"], "email": cand["email"], "created_at": cand["created_at"],
        "hr_outcome": cand["hr_outcome"], "applicant": cand["applicant_id"] is not None,
        "interview_status": cand["interview_status"],
        "cv_score": (screen.get("screening") or {}).get("score"),
        "cv_recommendation": (screen.get("screening") or {}).get("recommendation"),
        "interview_score": ev.get("interview_score"),
        "decision": ev.get("decision"),
        "stages": {k: s["status"] for k, s in stages.items()},
        "is_demo": any(s["is_demo"] for s in stages.values()),
    }


def _all_stages(c, job_id: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in c.execute(
        "SELECT s.* FROM stage_runs s JOIN candidates c ON c.id=s.candidate_id WHERE c.job_id=?", (job_id,)):
        d = dict(r)
        d["result"] = json.loads(d["result"]) if d["result"] else None
        d["is_demo"] = bool(d["is_demo"])
        out.setdefault(d["candidate_id"], {})[d["stage"]] = d
    return out


@router.get("/jobs/{job_id}")
def job_detail(job_id: str, user: dict = Depends(current_user)):
    job = _get_job(job_id, user)
    with db.conn() as c:
        cands = [db.candidate_row(r) for r in c.execute(
            "SELECT * FROM candidates WHERE job_id=? ORDER BY created_at DESC", (job_id,))]
        by_cand = _all_stages(c, job_id)
    return {"job": _public_job(job), "candidates": [_summary(cd, by_cand.get(cd["id"], {})) for cd in cands]}


def _num(s: str) -> float | None:
    s = (s or "").strip().replace(",", "")
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        raise HTTPException(422, "Expected salary must be a number") from None
    if v < 0 or v > 1e9:
        raise HTTPException(422, "Expected salary is out of range")
    return v


_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


@router.post("/jobs/{job_id}/candidates")
async def add_candidate(
    job_id: str,
    name: str = Form(...),
    email: str = Form(""),
    expected_salary: str = Form(""),
    currency: str = Form(""),
    cv_text: str = Form(""),
    cv_file: UploadFile | None = File(None),
    user: dict = Depends(current_user),
):
    _get_job(job_id, user)
    name = _clean(name, 100)
    email = email.strip().lower()[:200]
    if len(name) < 2:
        raise HTTPException(422, "Enter the candidate's name")
    if email and not _EMAIL.fullmatch(email):
        raise HTTPException(422, "Invalid email address")
    filename, text = "", _clean_multiline(cv_text, cv.MAX_TEXT)
    if cv_file is not None and cv_file.filename:
        data = await cv_file.read(config.MAX_CV_BYTES + 1)
        if len(data) > config.MAX_CV_BYTES:
            raise HTTPException(413, f"The CV file is larger than {config.MAX_CV_BYTES // (1024 * 1024)} MB")
        try:
            text = cv.extract_text(cv_file.filename, data)
        except cv.CVError as exc:
            raise HTTPException(422, str(exc)) from None
        filename = _clean(cv_file.filename, 120)
    if len(text) < 40:
        raise HTTPException(422, "Upload a CV file or paste the CV text")
    cand_id = secrets.token_hex(5)
    with db.conn() as c:
        c.execute(
            """INSERT INTO candidates (id,job_id,user_id,name,email,cv_text,cv_filename,expected_salary,currency,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (cand_id, job_id, user["id"], name, email, text, filename, _num(expected_salary),
             currency.strip().upper()[:3], time.time()),
        )
    db.add_event(cand_id, "created", "candidate added")
    return {"id": cand_id}


def _get_candidate(cand_id: str, user: dict) -> tuple[dict, dict]:
    with db.conn() as c:
        row = c.execute("SELECT * FROM candidates WHERE id=? AND user_id=?", (cand_id, user["id"])).fetchone()
        if row is None:
            raise HTTPException(404, "Candidate not found")
        cand = db.candidate_row(row)
        job = db.job_row(c.execute("SELECT * FROM jobs WHERE id=?", (cand["job_id"],)).fetchone())
    return cand, job


def _public_stage(key: str, s: dict, cand: dict) -> dict:
    result = s["result"]
    if key.startswith("email:") and result:  # approval can change after the draft was written
        needed = rules.HR_GATED.get(key[6:])
        result = {**result, "hr_approved": needed is None or cand["hr_outcome"] == needed}
    return {"status": s["status"], "result": result, "error": s["error"], "is_demo": s["is_demo"],
            "attempts": s["attempts"], "finished_at": s["finished_at"]}


@router.get("/candidates/{cand_id}")
def candidate_detail(cand_id: str, user: dict = Depends(current_user)):
    cand, job = _get_candidate(cand_id, user)
    with db.conn() as c:
        stages = db.stage_map(c, cand_id)
        events = [dict(r) for r in c.execute(
            "SELECT ts,stage,message FROM events WHERE candidate_id=? ORDER BY id", (cand_id,))]
        documents = [dict(r) for r in c.execute(
            "SELECT id,name,size,created_at FROM documents WHERE candidate_id=? ORDER BY id", (cand_id,))]
    return {
        "candidate": {
            "id": cand["id"], "job_id": cand["job_id"], "name": cand["name"], "email": cand["email"],
            "cv_excerpt": cand["cv_text"][:1500], "cv_chars": len(cand["cv_text"]), "cv_filename": cand["cv_filename"],
            "expected_salary": cand["expected_salary"], "currency": cand["currency"], "transcript": cand["transcript"],
            "submitted_documents": cand["submitted_documents"], "hr_outcome": cand["hr_outcome"],
            "hr_note": cand["hr_note"], "hr_at": cand["hr_at"], "created_at": cand["created_at"],
            "credit_charged": bool(cand["credit_charged"]), "applicant": cand["applicant_id"] is not None,
            "interview_status": cand["interview_status"], "interview_answers": cand["interview_answers"],
        },
        "documents": documents,
        "job": _public_job(job),
        "stages": {k: _public_stage(k, s, cand) for k, s in stages.items()},
        "events": events,
        "max_attempts": config.MAX_STAGE_ATTEMPTS,
    }


class CandidatePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    expected_salary: float | None = Field(default=None, ge=0, le=1e9)
    currency: str | None = Field(default=None, max_length=3)
    transcript: str | None = Field(default=None, max_length=30000)
    submitted_documents: list[str] | None = Field(default=None, max_length=30)


@router.patch("/candidates/{cand_id}")
def update_candidate(cand_id: str, body: CandidatePatch, user: dict = Depends(current_user)):
    _get_candidate(cand_id, user)
    sent = body.model_fields_set
    sets: dict = {}
    if "name" in sent and body.name:
        sets["name"] = _clean(body.name, 100)
    if "email" in sent:
        email = (body.email or "").strip().lower()
        if email and not _EMAIL.fullmatch(email):
            raise HTTPException(422, "Invalid email address")
        sets["email"] = email
    if "expected_salary" in sent:
        sets["expected_salary"] = body.expected_salary
    if "currency" in sent:
        sets["currency"] = (body.currency or "").strip().upper()
    if "transcript" in sent:
        sets["transcript"] = _clean_multiline(body.transcript or "", 30000)
    if "submitted_documents" in sent:
        sets["submitted_documents"] = json.dumps(
            [_clean(d, 120) for d in (body.submitted_documents or []) if d.strip()], ensure_ascii=False)
    if sets:
        with db.conn() as c:
            c.execute(f"UPDATE candidates SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), cand_id))
    return {"ok": True}


@router.delete("/candidates/{cand_id}")
def delete_candidate(cand_id: str, user: dict = Depends(current_user)):
    _get_candidate(cand_id, user)
    with db.conn() as c:
        if _busy(c, "id=?", (cand_id,)):
            raise HTTPException(409, "Wait for the running stages to finish first")
        _delete_candidates(c, "id=?", (cand_id,))
    return {"ok": True}


# ---------- stages ----------

def queue_stage(cand_id: str, stage: str, owner_id: int) -> None:
    """Checks readiness and limits, charges the owner's credit for a candidate's first screening, and queues the run.
    Raises HTTPException with a customer-readable message when the stage cannot run."""
    if not rules.valid_stage(stage):
        raise HTTPException(404, "Unknown stage")
    with db.conn() as c:
        row = c.execute("SELECT * FROM candidates WHERE id=? AND user_id=?", (cand_id, owner_id)).fetchone()
        if row is None:
            raise HTTPException(404, "Candidate not found")
        cand = db.candidate_row(row)
        job = db.job_row(c.execute("SELECT * FROM jobs WHERE id=?", (cand["job_id"],)).fetchone())
        charged = 0
        stages = db.stage_map(c, cand_id)
        cur = stages.get(stage)
        if cur and cur["status"] in ("queued", "running"):
            raise HTTPException(409, "This stage is already running")
        problem = engine.check_ready(stage, cand, job, stages)
        if problem:
            raise HTTPException(409, problem)
        attempts = cur["attempts"] if cur else 0
        if attempts >= config.MAX_STAGE_ATTEMPTS:
            raise HTTPException(429, f"This stage has already run {attempts} times for this candidate")
        if stage == "screen" and not cand["credit_charged"]:
            if not db.spend_credit(c, owner_id, "candidate pipeline", cand_id):
                raise HTTPException(402, "No credits left. Buy a credit pack to take another candidate through the pipeline.")
            c.execute("UPDATE candidates SET credit_charged=1 WHERE id=?", (cand_id,))
            charged = 1
        c.execute(
            """INSERT INTO stage_runs (candidate_id,stage,status,attempts,charged,created_at) VALUES (?,?,?,?,?,?)
               ON CONFLICT(candidate_id,stage) DO UPDATE SET status='queued', error=NULL, attempts=?, charged=?, created_at=?""",
            (cand_id, stage, "queued", attempts + 1, charged, time.time(), attempts + 1, charged, time.time()),
        )
    db.add_event(cand_id, stage, "queued")
    runner.enqueue(cand_id, stage)


@router.post("/candidates/{cand_id}/stages/{stage}")
def run_stage(cand_id: str, stage: str, user: dict = Depends(current_user)):
    _get_candidate(cand_id, user)
    queue_stage(cand_id, stage, user["id"])
    return {"ok": True}


@router.post("/candidates/{cand_id}/interview/send")
def send_interview(cand_id: str, user: dict = Depends(current_user)):
    """Release the prepared questions to the applicant, who answers them in their own account."""
    cand, _ = _get_candidate(cand_id, user)
    if cand["applicant_id"] is None:
        raise HTTPException(409, "This candidate was added manually and has no account. Paste the transcript instead.")
    with db.conn() as c:
        screen = c.execute("SELECT status FROM stage_runs WHERE candidate_id=? AND stage='screen'", (cand_id,)).fetchone()
        if screen is None or screen["status"] != "completed":
            raise HTTPException(409, "Run the CV screening first")
        if cand["interview_status"] == "answered":
            raise HTTPException(409, "The candidate has already answered")
        c.execute("UPDATE candidates SET interview_status='sent' WHERE id=?", (cand_id,))
    db.add_event(cand_id, "interview", "questions sent to the candidate")
    return {"ok": True}


@router.get("/candidates/{cand_id}/documents/{doc_id}")
def download_document(cand_id: str, doc_id: int, user: dict = Depends(current_user)):
    _get_candidate(cand_id, user)
    with db.conn() as c:
        row = c.execute("SELECT name,content FROM documents WHERE id=? AND candidate_id=?", (doc_id, cand_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Document not found")
    safe = re.sub(r"[^\w.\- ]+", "_", row["name"])[:100] or "document"
    return Response(bytes(row["content"]), media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{safe}"', "X-Content-Type-Options": "nosniff"})


class DecisionIn(BaseModel):
    outcome: Literal["pass", "fail", "hold", "none"]
    note: str = Field(default="", max_length=500)


@router.post("/candidates/{cand_id}/decision")
def record_decision(cand_id: str, body: DecisionIn, user: dict = Depends(current_user)):
    """The HR decision. The AI only recommends: nothing marked pass/fail happens without this call."""
    _get_candidate(cand_id, user)
    with db.conn() as c:
        screen = c.execute("SELECT status FROM stage_runs WHERE candidate_id=? AND stage='screen'", (cand_id,)).fetchone()
        if screen is None or screen["status"] != "completed":
            raise HTTPException(409, "Run the CV screening before recording a decision")
        outcome = None if body.outcome == "none" else body.outcome
        c.execute(
            "UPDATE candidates SET hr_outcome=?, hr_note=?, hr_at=? WHERE id=?",
            (outcome, _clean(body.note, 500) if outcome else "", time.time() if outcome else None, cand_id),
        )
    db.add_event(cand_id, "decision", f"HR decision: {outcome or 'cleared'}")
    return {"ok": True}


@router.get("/candidates/{cand_id}/report.md")
def report_markdown(cand_id: str, user: dict = Depends(current_user)):
    cand, _ = _get_candidate(cand_id, user)
    with db.conn() as c:
        row = c.execute("SELECT status,result FROM stage_runs WHERE candidate_id=? AND stage='report'", (cand_id,)).fetchone()
    if row is None or row["status"] != "completed" or not row["result"]:
        raise HTTPException(409, "The report has not been generated yet")
    md = json.loads(row["result"])["markdown"]
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", cand["name"]).strip("-") or cand_id
    return Response(md.encode("utf-8"), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="hr-report-{safe}.md"'})


# ---------- export ----------

def _safe_cell(v) -> str:
    """Neutralise spreadsheet formula injection: CV-derived text must not run as a formula."""
    s = " | ".join(v) if isinstance(v, list) else str(v if v is not None else "")
    if s[:1] in ("=", "+", "-", "@", "\t", "\r") and not re.fullmatch(r"\+?[\d\s()-]+", s):
        return "'" + s
    return s


@router.get("/jobs/{job_id}/export.csv")
def export_job(job_id: str, user: dict = Depends(current_user)):
    job = _get_job(job_id, user)
    with db.conn() as c:
        cands = [db.candidate_row(r) for r in c.execute(
            "SELECT * FROM candidates WHERE job_id=? ORDER BY created_at", (job_id,))]
        by_cand = _all_stages(c, job_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Candidate", "Email", "CV score", "CV recommendation", "Interview score", f"AI recommendation (passing {job['passing_score']})",
                "HR decision", "HR note", "Salary vs range", "Documents complete"])
    for cd in cands:
        st = by_cand.get(cd["id"], {})
        s = _summary(cd, st)
        sal = (st.get("salary") or {}).get("result") or {}
        docs = (st.get("documents") or {}).get("result") or {}
        w.writerow([_safe_cell(x) for x in (
            cd["name"], cd["email"], s["cv_score"], s["cv_recommendation"], s["interview_score"], s["decision"],
            cd["hr_outcome"] or "", cd["hr_note"], sal.get("scenario", ""),
            "" if not docs else ("yes" if docs.get("complete") else "no"))])
    body = "﻿" + buf.getvalue()  # BOM so Excel opens Arabic correctly
    return Response(body.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="candidates-{job_id}.csv"'})
