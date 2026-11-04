from fastapi import Depends, Header, HTTPException

from . import db, security


def _user_from(authorization: str | None) -> dict | None:
    token = (authorization or "").removeprefix("Bearer ").strip()
    uid = security.read_token(token) if token else None
    if uid is None:
        return None
    with db.conn() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def current_user(authorization: str | None = Header(default=None)) -> dict:
    user = _user_from(authorization)
    if user is None:
        raise HTTPException(401, "Not signed in")
    return user


def optional_user(authorization: str | None = Header(default=None)) -> dict | None:
    return _user_from(authorization)


def hr_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "hr":
        raise HTTPException(403, "This page is for HR accounts")
    return user


def candidate_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "candidate":
        raise HTTPException(403, "This page is for candidate accounts")
    return user


def admin_user(user: dict = Depends(hr_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(403, "Admins only")
    return user


def public_user(u: dict) -> dict:
    return {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"],
            "is_admin": bool(u["is_admin"]), "credits": u["credits"]}
