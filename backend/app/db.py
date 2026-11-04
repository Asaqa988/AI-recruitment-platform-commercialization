import json
import sqlite3
import time
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  pw_hash TEXT NOT NULL,
  salt TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,
  role TEXT NOT NULL DEFAULT 'hr',
  credits INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS credit_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  delta INTEGER NOT NULL,
  reason TEXT NOT NULL,
  ref TEXT NOT NULL DEFAULT '',
  ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS purchases (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  package TEXT NOT NULL,
  credits INTEGER NOT NULL,
  price_cents INTEGER NOT NULL,
  status TEXT NOT NULL,
  payment_ref TEXT,
  created_at REAL NOT NULL,
  paid_at REAL
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  title TEXT NOT NULL,
  company TEXT NOT NULL,
  description TEXT NOT NULL,
  passing_score INTEGER NOT NULL,
  currency TEXT NOT NULL,
  salary_min REAL,
  salary_max REAL,
  required_documents TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'en',
  is_open INTEGER NOT NULL DEFAULT 1,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES jobs(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  email TEXT NOT NULL DEFAULT '',
  cv_text TEXT NOT NULL,
  cv_filename TEXT NOT NULL DEFAULT '',
  expected_salary REAL,
  currency TEXT NOT NULL DEFAULT '',
  transcript TEXT NOT NULL DEFAULT '',
  submitted_documents TEXT NOT NULL DEFAULT '[]',
  credit_charged INTEGER NOT NULL DEFAULT 0,
  hr_outcome TEXT,
  hr_note TEXT NOT NULL DEFAULT '',
  hr_at REAL,
  applicant_id INTEGER REFERENCES users(id),
  interview_status TEXT NOT NULL DEFAULT 'none',
  interview_answers TEXT NOT NULL DEFAULT '[]',
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id TEXT NOT NULL REFERENCES candidates(id),
  name TEXT NOT NULL,
  size INTEGER NOT NULL,
  content BLOB NOT NULL,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_docs_cand ON documents(candidate_id);
CREATE TABLE IF NOT EXISTS stage_runs (
  candidate_id TEXT NOT NULL REFERENCES candidates(id),
  stage TEXT NOT NULL,
  status TEXT NOT NULL,
  params TEXT NOT NULL DEFAULT '{}',
  result TEXT,
  engine TEXT,
  is_demo INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  charged INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL,
  finished_at REAL,
  PRIMARY KEY (candidate_id, stage)
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id TEXT NOT NULL REFERENCES candidates(id),
  ts REAL NOT NULL,
  stage TEXT NOT NULL,
  message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_cand_job ON candidates(job_id);
CREATE INDEX IF NOT EXISTS idx_cand_user ON candidates(user_id);
CREATE INDEX IF NOT EXISTS idx_events_cand ON events(candidate_id);
CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases(user_id);
"""


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA journal_mode = WAL")
    try:
        yield c
        c.commit()
    finally:
        c.close()


MIGRATIONS = [  # columns added after the first release: (table, column, ddl)
    ("users", "role", "TEXT NOT NULL DEFAULT 'hr'"),
    ("jobs", "is_open", "INTEGER NOT NULL DEFAULT 1"),
    ("candidates", "applicant_id", "INTEGER REFERENCES users(id)"),
    ("candidates", "interview_status", "TEXT NOT NULL DEFAULT 'none'"),
    ("candidates", "interview_answers", "TEXT NOT NULL DEFAULT '[]'"),
]


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)
        for table, column, ddl in MIGRATIONS:
            cols = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cand_applicant ON candidates(applicant_id)")


# ---------- credits ----------

def grant_credits(c: sqlite3.Connection, user_id: int, delta: int, reason: str, ref: str = "") -> None:
    c.execute("UPDATE users SET credits = credits + ? WHERE id=?", (delta, user_id))
    c.execute(
        "INSERT INTO credit_ledger (user_id, delta, reason, ref, ts) VALUES (?,?,?,?,?)",
        (user_id, delta, reason, ref, time.time()),
    )


def spend_credit(c: sqlite3.Connection, user_id: int, reason: str, ref: str = "") -> bool:
    """Atomic: the WHERE clause stops the balance going negative under concurrent requests."""
    cur = c.execute("UPDATE users SET credits = credits - 1 WHERE id=? AND credits >= 1", (user_id,))
    if cur.rowcount != 1:
        return False
    c.execute(
        "INSERT INTO credit_ledger (user_id, delta, reason, ref, ts) VALUES (?,?,?,?,?)",
        (user_id, -1, reason, ref, time.time()),
    )
    return True


# ---------- row helpers ----------

def job_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["required_documents"] = json.loads(d["required_documents"])
    d["is_open"] = bool(d["is_open"])
    return d


def candidate_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["submitted_documents"] = json.loads(d["submitted_documents"])
    d["interview_answers"] = json.loads(d["interview_answers"])
    return d


def stage_map(c: sqlite3.Connection, candidate_id: str) -> dict[str, dict]:
    out = {}
    for r in c.execute("SELECT * FROM stage_runs WHERE candidate_id=?", (candidate_id,)):
        d = dict(r)
        d["params"] = json.loads(d["params"] or "{}")
        d["result"] = json.loads(d["result"]) if d["result"] else None
        d["is_demo"] = bool(d["is_demo"])
        out[d["stage"]] = d
    return out


def add_event(candidate_id: str, stage: str, message: str) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO events (candidate_id, ts, stage, message) VALUES (?,?,?,?)",
            (candidate_id, time.time(), stage, message[:400]),
        )
