import json
import sqlite3
from contextlib import contextmanager
from threading import Lock
from app.config import DATA
from billing.generate import generate
from billing.habit_seed import seed_habits, seeded

PATH = DATA / "billing.sqlite3"
_seed_lock = Lock()


_habits_checked = False


def _ensure_habits(db):
    """Databases generated before customer rhythms existed are upgraded once, in place."""
    global _habits_checked
    if _habits_checked:
        return
    with _seed_lock:
        if not _habits_checked:
            if not seeded(db):
                seed_habits(db)
            _habits_checked = True


@contextmanager
def connection():
    if not PATH.exists():
        with _seed_lock:
            if not PATH.exists():
                generate(PATH)
    db = sqlite3.connect(PATH, timeout=30)
    _ensure_habits(db)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def merchant(mid, db):
    row = db.execute("SELECT * FROM merchants WHERE id=?", (mid,)).fetchone()
    if row is None:
        raise ValueError("Unknown merchant")
    result = dict(row)
    result["products"] = json.loads(row["products"])
    result["ingredients"] = json.loads(row["ingredients"])
    return result
