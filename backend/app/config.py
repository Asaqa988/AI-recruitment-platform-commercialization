import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


APP_ENV = env("APP_ENV", "dev")  # dev | production
_DEFAULT_SECRET = "dev-secret-change-me"
APP_SECRET = env("APP_SECRET", _DEFAULT_SECRET)
if APP_ENV == "production" and APP_SECRET == _DEFAULT_SECRET:
    raise RuntimeError("APP_ENV=production requires APP_SECRET to be set to a long random string")

ADMIN_EMAILS = {e.strip().lower() for e in env("ADMIN_EMAILS").split(",") if e.strip()}
DB_PATH = Path(env("DB_PATH", "data/hire.db"))
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH

PAYMENT_MODE = env("PAYMENT_MODE", "manual")  # demo | manual
PAYMENT_INSTRUCTIONS = env("PAYMENT_INSTRUCTIONS", "")
FREE_CREDITS = int(env("FREE_CREDITS", "1"))  # one free candidate pipeline for every new account

ENGINE = env("ENGINE", "auto")  # auto | demo | crew
CREW_MODEL = env("CREW_MODEL", "openai/gpt-4o-mini")
# Candidate-facing writing (emails, the HR report) can use a stronger model than scoring does.
CREW_WRITER_MODEL = env("CREW_WRITER_MODEL", CREW_MODEL)

MAX_CV_BYTES = 5 * 1024 * 1024
MAX_STAGE_ATTEMPTS = int(env("MAX_STAGE_ATTEMPTS", "5"))  # runs of one stage per candidate (cost control)

FRONTEND_DIST = ROOT.parent / "frontend" / "dist"
