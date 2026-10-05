"""Seeds recurring-customer rhythms into the synthetic POS history.

Only the loyalty ID on bills that already contain the product is re-labelled, so revenue,
units, stock and availability are unchanged. Idempotent: skipped once habitual IDs exist.
"""

import hashlib
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from billing.catalogue import catalogue

AS_OF = date(2026, 10, 2)
START = AS_OF - timedelta(days=364)
FIRST_HABIT = 901  # ordinary synthetic loyalty IDs stop at 349
MISS_PERCENT = 8  # habitual customers occasionally skip a visit

# (product name, rhythm, argument, customers): "every" = every N days, "weekdays" = those weekdays (Mon=0)
HABITS = {
    "hypermarket": [
        ("Milk 1 L", "every", 1, 9),
        ("Oats 1 kg", "weekdays", [6], 6),
        ("Potato chips 50 g", "every", 3, 4),
        ("Sunflower oil 1 L", "every", 14, 4),
        ("Chocolate 100 g", "weekdays", [5], 5),
        ("Rice 5 kg", "every", 10, 3),
        ("Instant noodles 280 g", "weekdays", [2], 4),
    ],
    "restaurant": [
        ("Filter coffee", "every", 1, 6),
        ("Veg thali", "weekdays", [0, 1, 2, 3, 4], 5),
        ("Masala dosa", "weekdays", [6], 5),
        ("Lime soda", "every", 2, 3),
    ],
    "apparel": [("Cotton tee M", "every", 14, 2), ("Socks pair", "every", 20, 2), ("Leggings M", "every", 21, 2)],
    "kirana": [
        ("Biscuits 100 g", "every", 1, 7),
        ("Rice 1 kg", "weekdays", [5], 5),
        ("Toor dal 1 kg", "weekdays", [6], 4),
        ("Tea 250 g", "every", 2, 4),
    ],
    "pharmacy": [
        ("Paracetamol strip", "every", 7, 3),
        ("Soap bar", "every", 14, 3),
        ("ORS sachet", "every", 10, 2),
    ],
    "bakery": [
        ("Milk bread loaf", "every", 1, 8),
        ("Veg puff", "weekdays", [0, 1, 2, 3, 4], 5),
        ("Sourdough loaf", "weekdays", [6], 4),
    ],
    "electronics": [("USB C cable 1 m", "every", 20, 2), ("Phone stand", "every", 24, 2)],
}


def _is_visit(rhythm, arg, offset, d):
    n = (d - START).days
    return n % arg == offset % arg if rhythm == "every" else d.weekday() in arg


def _skipped(customer, d):
    digest = hashlib.sha256(f"{customer}/{d}".encode()).digest()
    return digest[0] % 100 < MISS_PERCENT


def seeded(conn):
    return conn.execute("SELECT 1 FROM bills WHERE customer LIKE 'L-%-09__' LIMIT 1").fetchone() is not None


def seed_habits(conn):
    if seeded(conn):
        return 0
    claimed = set()
    changed = 0
    for kind, habits in HABITS.items():
        ids = {p["name"]: p["id"] for p in catalogue(kind)}
        serial = 0
        for name, rhythm, arg, people in habits:
            by_day = {}
            for bill, day in conn.execute(
                "SELECT b.id, substr(b.timestamp,1,10) FROM bills b JOIN lines l ON l.bill=b.id "
                "WHERE b.merchant=? AND l.product=? ORDER BY b.id",
                (kind, ids[name]),
            ):
                by_day.setdefault(day, []).append(bill)
            for person in range(people):
                customer = f"L-{kind}-{FIRST_HABIT + serial:04}"
                serial += 1
                for n in range(365):
                    d = START + timedelta(days=n)
                    options = [b for b in by_day.get(str(d), []) if b not in claimed]
                    if not options or not _is_visit(rhythm, arg, person * 3 + serial, d) or _skipped(customer, d):
                        continue
                    pick = options[hashlib.sha256(f"{customer}/{d}/pick".encode()).digest()[0] % len(options)]
                    claimed.add(pick)
                    conn.execute("UPDATE bills SET customer=? WHERE id=?", (customer, pick))
                    changed += 1
    conn.commit()
    return changed


if __name__ == "__main__":
    target = Path(sys.argv[1])
    db = sqlite3.connect(target, timeout=60)
    print(f"re-labelled {seed_habits(db)} bills")
    db.close()
