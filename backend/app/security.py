import base64
import hashlib
import hmac
import json
import os
import time
from collections import defaultdict, deque

from .config import APP_SECRET

TOKEN_TTL = 60 * 60 * 24 * 14


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 240_000)
    return digest.hex(), salt


def verify_password(password: str, pw_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, pw_hash)


def _sign(payload: bytes) -> str:
    return hmac.new(APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()


def make_token(user_id: int) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"uid": user_id, "exp": int(time.time()) + TOKEN_TTL}).encode()
    )
    return f"{payload.decode()}.{_sign(payload)}"


def read_token(token: str) -> int | None:
    try:
        payload_b64, sig = token.split(".", 1)
        payload = payload_b64.encode()
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload))
        if data["exp"] < time.time():
            return None
        return int(data["uid"])
    except Exception:
        return None


# ---- login throttling (in memory: fine for one process; use a shared store if you run several) ----

_FAILS: dict[str, deque] = defaultdict(deque)
LOGIN_WINDOW = 15 * 60
LOGIN_MAX_FAILS = 8


def login_blocked(key: str) -> bool:
    q = _FAILS[key]
    cutoff = time.time() - LOGIN_WINDOW
    while q and q[0] < cutoff:
        q.popleft()
    return len(q) >= LOGIN_MAX_FAILS


def login_failed(key: str) -> None:
    _FAILS[key].append(time.time())


def login_ok(key: str) -> None:
    _FAILS.pop(key, None)
