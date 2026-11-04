import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from . import db, engine

_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="stage")


def enqueue(candidate_id: str, stage: str) -> None:
    _pool.submit(_process, candidate_id, stage)


def resume_pending() -> None:
    """After a restart, anything queued or interrupted mid-run goes back on the queue."""
    with db.conn() as c:
        c.execute("UPDATE stage_runs SET status='queued' WHERE status='running'")
        rows = [(r["candidate_id"], r["stage"]) for r in c.execute("SELECT candidate_id, stage FROM stage_runs WHERE status='queued'")]
    for candidate_id, stage in rows:
        enqueue(candidate_id, stage)


def _fail(candidate_id: str, stage: str, message: str) -> None:
    """Mark the stage failed. If this run took the candidate's credit (first screening), give it back."""
    with db.conn() as c:
        row = c.execute("SELECT charged FROM stage_runs WHERE candidate_id=? AND stage=?", (candidate_id, stage)).fetchone()
        c.execute(
            "UPDATE stage_runs SET status='failed', error=?, finished_at=?, charged=0 WHERE candidate_id=? AND stage=?",
            (message[:500], time.time(), candidate_id, stage),
        )
        if row is not None and row["charged"]:
            cand = c.execute("SELECT user_id FROM candidates WHERE id=?", (candidate_id,)).fetchone()
            if cand is not None:
                db.grant_credits(c, cand["user_id"], 1, "refund: screening failed", candidate_id)
                c.execute("UPDATE candidates SET credit_charged=0 WHERE id=?", (candidate_id,))
    db.add_event(candidate_id, stage, f"failed: {message[:300]}")


def _process(candidate_id: str, stage: str) -> None:
    with db.conn() as c:
        run = c.execute("SELECT * FROM stage_runs WHERE candidate_id=? AND stage=?", (candidate_id, stage)).fetchone()
        if run is None or run["status"] != "queued":
            return
        cand_row = c.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if cand_row is None:
            return
        cand = db.candidate_row(cand_row)
        job = db.job_row(c.execute("SELECT * FROM jobs WHERE id=?", (cand["job_id"],)).fetchone())
        stages = db.stage_map(c, candidate_id)
        params = json.loads(run["params"] or "{}")
        try:
            name, reason = engine.pick_engine()
        except RuntimeError as exc:
            name, reason, engine_error = "", "", str(exc)
        else:
            engine_error = ""
            c.execute(
                "UPDATE stage_runs SET status='running', engine=?, is_demo=?, error=NULL WHERE candidate_id=? AND stage=?",
                (name, 1 if name == "demo" else 0, candidate_id, stage),
            )
    if engine_error:
        _fail(candidate_id, stage, engine_error)
        return
    db.add_event(candidate_id, stage, f"started (engine={name}: {reason})")

    def emit(sub_stage: str, message: str) -> None:
        db.add_event(candidate_id, stage, message)

    try:
        result = engine.run_stage(stage, {"job": job, "candidate": cand, "stages": stages, "params": params}, emit)
    except engine.StageNotReady as exc:
        _fail(candidate_id, stage, str(exc))
        return
    except Exception as exc:  # noqa: BLE001 - surface any engine failure on the stage
        traceback.print_exc()
        _fail(candidate_id, stage, str(exc) or exc.__class__.__name__)
        return
    with db.conn() as c:
        c.execute(
            "UPDATE stage_runs SET status='completed', result=?, error=NULL, finished_at=? WHERE candidate_id=? AND stage=?",
            (json.dumps(result, ensure_ascii=False), time.time(), candidate_id, stage),
        )
    db.add_event(candidate_id, stage, "completed")
