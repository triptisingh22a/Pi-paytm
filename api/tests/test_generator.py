"""The synthetic billing data must not depend on the Python process (hash randomisation changed it once)."""

import subprocess
import sys
from pathlib import Path

CODE = (
    "import sqlite3,sys,tempfile;from pathlib import Path;from billing.generate import generate;"
    "p=Path(tempfile.mkdtemp())/'g.sqlite3';generate(p,limit=3);db=sqlite3.connect(p);"
    "print(dict(db.execute('select merchant,count(*) from bills group by merchant').fetchall()))"
)


def counts(hash_seed):
    env = {"PYTHONHASHSEED": str(hash_seed), "PYTHONUTF8": "1", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
    out = subprocess.run([sys.executable, "-c", CODE], cwd=Path(__file__).resolve().parents[1], env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    return out.stdout.strip()


def test_generation_is_identical_across_processes_and_matches_the_shipped_dataset():
    a, b = counts(1), counts(12345)
    assert a == b
    # first three shops of the original dataset (checked bill for bill against the CSV exports)
    assert "'hypermarket': 35262" in a and "'restaurant': 24850" in a and "'apparel': 9471" in a