import re
import secrets
from typing import Literal
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import config, db, engine, hiring, portal, pricing, runner, security, seed
from .deps import admin_user, current_user, hr_user, public_user


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init()
    seed.run()
    runner.resume_pending()
    yield


app = FastAPI(title="Zyndesk Hire", lifespan=lifespan)
app.include_router(hiring.router)
app.include_router(portal.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


# ---------- auth ----------

class RegisterIn(BaseModel):
    email: str = Field(max_length=200)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)
    role: Literal["hr", "candidate"] = "hr"

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("Invalid email")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/api/auth/register")
def register(body: RegisterIn):
    pw_hash, salt = security.hash_password(body.password)
    is_admin = 1 if body.role == "hr" and body.email in config.ADMIN_EMAILS else 0
    with db.conn() as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (body.email,)).fetchone():
            raise HTTPException(409, "Email already registered")
        cur = c.execute(
            "INSERT INTO users (email,name,pw_hash,salt,is_admin,role,created_at) VALUES (?,?,?,?,?,?,?)",
            (body.email, body.name.strip(), pw_hash, salt, is_admin, body.role, time.time()),
        )
        if body.role == "hr" and config.FREE_CREDITS > 0:
            db.grant_credits(c, cur.lastrowid, config.FREE_CREDITS, "welcome credit")
        row = c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    return {"token": security.make_token(row["id"]), "user": public_user(dict(row))}


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request):
    email = body.email.strip().lower()
    key = f"{email}|{request.client.host if request.client else ''}"
    if security.login_blocked(key):
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
    with db.conn() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if row is None or not security.verify_password(body.password, row["pw_hash"], row["salt"]):
        security.login_failed(key)
        raise HTTPException(401, "Wrong email or password")
    security.login_ok(key)
    return {"token": security.make_token(row["id"]), "user": public_user(dict(row))}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return public_user(user)


# ---------- public config ----------

@app.get("/api/config")
def get_config():
    name, _reason = engine.pick_engine() if config.ENGINE != "crew" else ("crew", "")
    return {
        "packages": [{"id": k, **v} for k, v in pricing.PACKAGES.items()],
        "currency": pricing.CURRENCY,
        "payment_mode": config.PAYMENT_MODE,
        "payment_instructions": config.PAYMENT_INSTRUCTIONS,
        "engine": name,
        "free_credits": config.FREE_CREDITS,
        "email_scenarios": list(engine.rules.EMAIL_SCENARIOS),
        "hr_gated": engine.rules.HR_GATED,
        "max_cv_mb": config.MAX_CV_BYTES // (1024 * 1024),
        "max_attempts": config.MAX_STAGE_ATTEMPTS,
    }


# ---------- credit purchases ----------

class PurchaseIn(BaseModel):
    package: str

    @field_validator("package")
    @classmethod
    def _pkg(cls, v: str) -> str:
        if v not in pricing.PACKAGES:
            raise ValueError("Unknown package")
        return v


class PayIn(BaseModel):
    reference: str = Field(default="", max_length=120)


def _public_purchase(p: dict) -> dict:
    return {k: p[k] for k in ("id", "package", "credits", "price_cents", "status", "payment_ref", "created_at", "paid_at")}


def _get_purchase(purchase_id: str, user: dict) -> dict:
    with db.conn() as c:
        row = c.execute("SELECT * FROM purchases WHERE id=? AND user_id=?", (purchase_id, user["id"])).fetchone()
    if row is None:
        raise HTTPException(404, "Purchase not found")
    return dict(row)


def _mark_paid(purchase_id: str) -> None:
    """Idempotent: credits are granted only by the call that moves the purchase to 'paid'."""
    with db.conn() as c:
        row = c.execute("SELECT * FROM purchases WHERE id=?", (purchase_id,)).fetchone()
        cur = c.execute(
            "UPDATE purchases SET status='paid', paid_at=? WHERE id=? AND status IN ('awaiting_payment','payment_review')",
            (time.time(), purchase_id),
        )
        if cur.rowcount == 1:
            db.grant_credits(c, row["user_id"], row["credits"], f"purchase {row['package']}", purchase_id)


@app.post("/api/purchases")
def create_purchase(body: PurchaseIn, user: dict = Depends(hr_user)):
    pkg = pricing.PACKAGES[body.package]
    purchase_id = secrets.token_hex(5)
    with db.conn() as c:
        c.execute(
            "INSERT INTO purchases (id,user_id,package,credits,price_cents,status,created_at) VALUES (?,?,?,?,?,?,?)",
            (purchase_id, user["id"], body.package, pkg["credits"], pkg["price_cents"], "awaiting_payment", time.time()),
        )
    return _public_purchase(_get_purchase(purchase_id, user))


@app.get("/api/purchases")
def list_purchases(user: dict = Depends(hr_user)):
    with db.conn() as c:
        rows = c.execute("SELECT * FROM purchases WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
    return [_public_purchase(dict(r)) for r in rows]


@app.post("/api/purchases/{purchase_id}/pay")
def pay(purchase_id: str, body: PayIn, user: dict = Depends(hr_user)):
    purchase = _get_purchase(purchase_id, user)
    if purchase["status"] not in ("awaiting_payment", "payment_review"):
        raise HTTPException(409, "Purchase is already paid")
    if config.PAYMENT_MODE == "demo":
        _mark_paid(purchase_id)
    else:
        ref = re.sub(r"\s+", " ", body.reference).strip()[:120]
        if len(ref) < 3:
            raise HTTPException(422, "Enter your transfer reference")
        with db.conn() as c:
            c.execute("UPDATE purchases SET status='payment_review', payment_ref=? WHERE id=?", (ref, purchase_id))
    return _public_purchase(_get_purchase(purchase_id, user))


# ---------- admin (metadata only: no candidate or CV data) ----------

@app.get("/api/admin/overview")
def admin_overview(_: dict = Depends(admin_user)):
    with db.conn() as c:
        purchases = [dict(r) for r in c.execute(
            "SELECT p.*, u.email AS user_email FROM purchases p JOIN users u ON u.id=p.user_id ORDER BY p.created_at DESC")]
        revenue = c.execute("SELECT COALESCE(SUM(price_cents),0) s FROM purchases WHERE status='paid'").fetchone()["s"]
        users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        candidates = c.execute("SELECT COUNT(*) n FROM candidates").fetchone()["n"]
        runs = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) n FROM stage_runs GROUP BY status")}
        failed = [dict(r) for r in c.execute(
            """SELECT s.candidate_id, s.stage, s.error, s.finished_at, u.email AS user_email
               FROM stage_runs s JOIN candidates c ON c.id=s.candidate_id JOIN users u ON u.id=c.user_id
               WHERE s.status='failed' ORDER BY s.finished_at DESC LIMIT 20""")]
    return {
        "purchases": [{**_public_purchase(p), "user_email": p["user_email"]} for p in purchases],
        "revenue_cents": revenue, "users": users, "candidates": candidates, "runs": runs, "failed": failed,
    }


@app.post("/api/admin/purchases/{purchase_id}/approve")
def admin_approve(purchase_id: str, _: dict = Depends(admin_user)):
    with db.conn() as c:
        row = c.execute("SELECT status FROM purchases WHERE id=?", (purchase_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Purchase not found")
    if row["status"] not in ("awaiting_payment", "payment_review"):
        raise HTTPException(409, "Purchase is not waiting for payment")
    _mark_paid(purchase_id)
    return {"ok": True}


class GrantIn(BaseModel):
    email: str
    credits: int = Field(ge=1, le=1000)
    reason: str = Field(default="admin grant", max_length=120)


@app.post("/api/admin/grant")
def admin_grant(body: GrantIn, admin: dict = Depends(admin_user)):
    with db.conn() as c:
        row = c.execute("SELECT id FROM users WHERE email=?", (body.email.strip().lower(),)).fetchone()
        if row is None:
            raise HTTPException(404, "No user with that email")
        db.grant_credits(c, row["id"], body.credits, body.reason, f"by {admin['email']}")
    return {"ok": True}


# ---------- frontend (built SPA) ----------

if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = (config.FRONTEND_DIST / path).resolve()
        if path and f.is_file() and config.FRONTEND_DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
