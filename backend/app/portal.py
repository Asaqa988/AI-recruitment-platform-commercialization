"""The applicant side. A candidate account sees open jobs, applies, answers the interview the HR released
and uploads documents. It never sees scores, AI output, the passing score or the salary range, only its own
data and a simple status."""
import json
import secrets
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from . import config, cv, db
from .deps import candidate_user, optional_user
from .hiring import _EMAIL, _clean, _clean_multiline, _delete_candidates, _num, queue_stage

router = APIRouter(prefix="/api/portal")

MAX_DOCS = 10
_MAGIC = {".pdf": (b"%PDF",), ".png": (b"\x89PNG",), ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".docx": (b"PK",)}


def _public_job(j: dict) -> dict:
    return {k: j[k] for k in ("id", "title", "company", "description", "language", "required_documents")}


@router.get("/jobs")
def open_jobs(user: dict | None = Depends(optional_user)):
    with db.conn() as c:
        jobs = [db.job_row(r) for r in c.execute("SELECT * FROM jobs WHERE is_open=1 ORDER BY created_at DESC")]
        mine: dict[str, str] = {}
        if user and user["role"] == "candidate":
            mine = {r["job_id"]: r["id"] for r in c.execute("SELECT id, job_id FROM candidates WHERE applicant_id=?", (user["id"],))}
    return [{**_public_job(j), "application_id": mine.get(j["id"])} for j in jobs]


def _my_candidate(c, app_id: str, user: dict) -> dict:
    row = c.execute("SELECT * FROM candidates WHERE id=? AND applicant_id=?", (app_id, user["id"])).fetchone()
    if row is None:
        raise HTTPException(404, "Application not found")
    return db.candidate_row(row)


@router.post("/jobs/{job_id}/apply")
async def apply(
    job_id: str,
    name: str = Form(...),
    email: str = Form(""),
    expected_salary: str = Form(""),
    currency: str = Form(""),
    cv_text: str = Form(""),
    cv_file: UploadFile | None = File(None),
    user: dict = Depends(candidate_user),
):
    with db.conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=? AND is_open=1", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "This job is closed or does not exist")
        job = db.job_row(row)
        if c.execute("SELECT 1 FROM candidates WHERE job_id=? AND applicant_id=?", (job_id, user["id"])).fetchone():
            raise HTTPException(409, "You have already applied to this job")
    name = _clean(name, 100)
    email = (email.strip() or user["email"]).lower()[:200]
    if len(name) < 2:
        raise HTTPException(422, "Enter your full name")
    if not _EMAIL.fullmatch(email):
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
        raise HTTPException(422, "Upload your CV or paste its text")
    app_id = secrets.token_hex(5)
    with db.conn() as c:
        c.execute(
            """INSERT INTO candidates (id,job_id,user_id,applicant_id,name,email,cv_text,cv_filename,expected_salary,currency,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (app_id, job_id, job["user_id"], user["id"], name, email, text, filename, _num(expected_salary),
             currency.strip().upper()[:3], time.time()),
        )
    db.add_event(app_id, "created", "candidate applied")
    try:  # screen right away on the HR's credit; if they have none it waits for them
        queue_stage(app_id, "screen", job["user_id"])
    except HTTPException as exc:
        db.add_event(app_id, "screen", f"waiting for HR: {exc.detail}")
    return {"id": app_id}


def _status(cand: dict, screened: bool) -> str:
    if cand["hr_outcome"]:
        return "decided"
    if cand["interview_status"] == "answered":
        return "interview_submitted"
    if cand["interview_status"] == "sent":
        return "interview"
    return "in_review" if screened else "received"


@router.get("/applications")
def my_applications(user: dict = Depends(candidate_user)):
    with db.conn() as c:
        rows = c.execute(
            """SELECT c.*, j.title AS job_title, j.company AS job_company,
                      (SELECT status FROM stage_runs s WHERE s.candidate_id=c.id AND s.stage='screen') AS screen_status
               FROM candidates c JOIN jobs j ON j.id=c.job_id WHERE c.applicant_id=? ORDER BY c.created_at DESC""",
            (user["id"],)).fetchall()
    out = []
    for r in rows:
        cand = db.candidate_row(r)
        out.append({"id": cand["id"], "job_title": r["job_title"], "company": r["job_company"], "created_at": cand["created_at"],
                    "status": _status(cand, r["screen_status"] == "completed")})
    return out


@router.get("/applications/{app_id}")
def application_detail(app_id: str, user: dict = Depends(candidate_user)):
    with db.conn() as c:
        cand = _my_candidate(c, app_id, user)
        job = db.job_row(c.execute("SELECT * FROM jobs WHERE id=?", (cand["job_id"],)).fetchone())
        stages = db.stage_map(c, app_id)
        docs = [dict(r) for r in c.execute("SELECT id,name,size FROM documents WHERE candidate_id=? ORDER BY id", (app_id,))]
    screen = stages.get("screen")
    questions = []
    if cand["interview_status"] in ("sent", "answered") and screen and screen["result"]:
        questions = [q["question"] for q in screen["result"]["questions"]["items"]]  # text only: no hints, no difficulty
    return {
        "id": cand["id"], "name": cand["name"], "email": cand["email"], "created_at": cand["created_at"],
        "expected_salary": cand["expected_salary"], "currency": cand["currency"],
        "job": _public_job(job),
        "status": _status(cand, bool(screen and screen["status"] == "completed")),
        "outcome": cand["hr_outcome"],
        "interview_status": cand["interview_status"], "questions": questions,
        "answers": cand["interview_answers"] if cand["interview_status"] == "answered" else [],
        "documents": docs, "max_docs": MAX_DOCS,
    }


class AnswersIn(BaseModel):
    answers: list[str] = Field(max_length=10)


@router.post("/applications/{app_id}/interview")
def submit_interview(app_id: str, body: AnswersIn, user: dict = Depends(candidate_user)):
    with db.conn() as c:
        cand = _my_candidate(c, app_id, user)
        if cand["interview_status"] != "sent":
            raise HTTPException(409, "There is no interview waiting for your answers")
        screen = c.execute("SELECT result FROM stage_runs WHERE candidate_id=? AND stage='screen'", (app_id,)).fetchone()
        questions = [q["question"] for q in json.loads(screen["result"])["questions"]["items"]]
        if len(body.answers) != len(questions):
            raise HTTPException(422, "Answer every question")
        answers = [_clean_multiline(a, 3000) for a in body.answers]
        if any(len(a) < 2 for a in answers):
            raise HTTPException(422, "Answer every question")
        transcript = "\n".join(f"Q{n}: {q}\nA{n}: {a}" for n, (q, a) in enumerate(zip(questions, answers), 1))
        c.execute("UPDATE candidates SET interview_status='answered', interview_answers=?, transcript=? WHERE id=?",
                  (json.dumps(answers, ensure_ascii=False), transcript[:30000], app_id))
    db.add_event(app_id, "interview", "candidate submitted the answers")
    try:  # scoring costs the HR nothing extra: it is part of the candidate's credit
        queue_stage(app_id, "evaluate", cand["user_id"])
    except HTTPException as exc:
        db.add_event(app_id, "evaluate", f"not started: {exc.detail}")
    return {"ok": True}


def _sync_documents(c, app_id: str) -> None:
    names = [r["name"] for r in c.execute("SELECT name FROM documents WHERE candidate_id=? ORDER BY id", (app_id,))]
    c.execute("UPDATE candidates SET submitted_documents=? WHERE id=?", (json.dumps(names, ensure_ascii=False), app_id))


@router.post("/applications/{app_id}/documents")
async def upload_document(app_id: str, file: UploadFile = File(...), user: dict = Depends(candidate_user)):
    with db.conn() as c:
        _my_candidate(c, app_id, user)
        if c.execute("SELECT COUNT(*) n FROM documents WHERE candidate_id=?", (app_id,)).fetchone()["n"] >= MAX_DOCS:
            raise HTTPException(409, f"You can upload up to {MAX_DOCS} documents")
    name = _clean(file.filename or "", 120)
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in _MAGIC:
        raise HTTPException(422, "Upload a PDF, PNG, JPG or DOCX file")
    data = await file.read(config.MAX_CV_BYTES + 1)
    if len(data) > config.MAX_CV_BYTES:
        raise HTTPException(413, f"The file is larger than {config.MAX_CV_BYTES // (1024 * 1024)} MB")
    if not any(data.startswith(m) for m in _MAGIC[ext]):
        raise HTTPException(422, "The file content does not match its type")
    with db.conn() as c:
        c.execute("INSERT INTO documents (candidate_id,name,size,content,created_at) VALUES (?,?,?,?,?)",
                  (app_id, name, len(data), data, time.time()))
        _sync_documents(c, app_id)
    db.add_event(app_id, "documents", f"candidate uploaded {name}")
    return {"ok": True}


@router.delete("/applications/{app_id}/documents/{doc_id}")
def delete_document(app_id: str, doc_id: int, user: dict = Depends(candidate_user)):
    with db.conn() as c:
        _my_candidate(c, app_id, user)
        c.execute("DELETE FROM documents WHERE id=? AND candidate_id=?", (doc_id, app_id))
        _sync_documents(c, app_id)
    return {"ok": True}


@router.delete("/applications/{app_id}")
def withdraw(app_id: str, user: dict = Depends(candidate_user)):
    """Withdraw and erase: the application, the CV, the answers and the documents."""
    with db.conn() as c:
        _my_candidate(c, app_id, user)
        busy = c.execute("SELECT 1 FROM stage_runs WHERE candidate_id=? AND status IN ('queued','running')", (app_id,)).fetchone()
        if busy:
            raise HTTPException(409, "Your application is being processed. Try again in a minute.")
        _delete_candidates(c, "id=?", (app_id,))
    return {"ok": True}
