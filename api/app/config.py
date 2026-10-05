import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
DATA.mkdir(parents=True, exist_ok=True)
DEMO_MODE = os.getenv("DEMO_MODE", "cached")
BORROWING_COST = float(os.getenv("ASSUMED_BORROWING_COST", ".02"))
GAP_THRESHOLD = float(os.getenv("GAP_THRESHOLD", ".35"))
