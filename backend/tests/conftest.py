import os
import sys
import tempfile
from pathlib import Path

# Must be set before the app is imported: config reads the environment at import time.
_tmp = tempfile.mkdtemp(prefix="hire-test-")
os.environ.update(
    DB_PATH=str(Path(_tmp) / "test.db"), ENGINE="demo", PAYMENT_MODE="demo",
    ADMIN_EMAILS="admin@example.com,admin-cand@example.com", FREE_CREDITS="1", APP_SECRET="test-secret", SEED_DEMO_ACCOUNTS="0",
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
