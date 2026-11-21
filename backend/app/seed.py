"""Demo accounts: one HR with a large credit balance and one candidate, created or refreshed on every start.
Idempotent: running it twice changes nothing. Disabled in production (see config.SEED_DEMO_ACCOUNTS)."""
import time

from . import config, db, security


def _ensure(role: str, email: str, name: str, password: str, credits: int) -> None:
    pw_hash, salt = security.hash_password(password)
    with db.conn() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row is None:
            cur = c.execute(
                "INSERT INTO users (email,name,pw_hash,salt,is_admin,role,created_at) VALUES (?,?,?,?,0,?,?)",
                (email, name, pw_hash, salt, role, time.time()),
            )
            user_id, balance = cur.lastrowid, 0
        else:
            user_id, balance = row["id"], row["credits"]
            c.execute("UPDATE users SET pw_hash=?, salt=?, role=? WHERE id=?", (pw_hash, salt, role, user_id))
        if role == "hr" and balance < credits:
            db.grant_credits(c, user_id, credits - balance, "demo account top-up")


def run() -> None:
    if not config.SEED_DEMO_ACCOUNTS:
        return
    _ensure("hr", config.DEMO_HR_EMAIL, "Demo HR", config.DEMO_HR_PASSWORD, config.DEMO_CREDITS)
    _ensure("candidate", config.DEMO_CANDIDATE_EMAIL, "Demo Candidate", config.DEMO_CANDIDATE_PASSWORD, 0)
