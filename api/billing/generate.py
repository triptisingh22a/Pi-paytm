"""365 days of reproducible POS bills, stock receipts and audited availability facts."""

import json
import math
import sqlite3
from datetime import date, timedelta
from pathlib import Path
import numpy as np
from billing.catalogue import catalogue, NAMES, INGREDIENTS
from billing.habit_seed import seed_habits

AS_OF = date(2026, 10, 2)
START = AS_OF - timedelta(days=364)
SCHEMA = """
CREATE TABLE merchants(id TEXT PRIMARY KEY,name TEXT,kind TEXT,products TEXT,ingredients TEXT);
CREATE TABLE bills(id TEXT PRIMARY KEY,merchant TEXT,timestamp TEXT,customer TEXT,profile TEXT);
CREATE TABLE lines(bill TEXT,product TEXT,qty INTEGER,price REAL,cost REAL);
CREATE TABLE stock_events(id TEXT PRIMARY KEY,merchant TEXT,product TEXT,timestamp TEXT,qty INTEGER,cost REAL,source TEXT);
CREATE TABLE daily(merchant TEXT,day TEXT,product TEXT,units INTEGER,revenue REAL,cost REAL,exposure INTEGER,opening INTEGER,closing INTEGER,waste INTEGER);
CREATE TABLE peer_weeks(peer TEXT,kind TEXT,week TEXT,product TEXT,units INTEGER,exposure INTEGER,bills INTEGER,ticket REAL,feature TEXT);
CREATE INDEX bill_period ON bills(merchant,timestamp);
CREATE INDEX line_bill ON lines(bill);
CREATE INDEX daily_query ON daily(merchant,day,product);
CREATE INDEX peers_query ON peer_weeks(kind,product,week);
"""


def propensity(p, day, donor=False):
    fraction = day / 364
    trend = {
        "steady": 1.0,
        "rising": 0.55 + 1.5 * fraction,
        "falling": 1.3 - 0.95 * fraction,
        "dead": 0.0 if day >= 335 and not donor else 0.65,
        "candidate": 1.0,
    }[p["trend"]]
    if day >= 358 and p["trend"] == "falling":
        trend *= 0.3
    if day >= 358 and p["trend"] == "rising":
        trend *= 1.6
    return p["propensity"] * trend


# Order in which donor shops draw their per-family bias. A plain set of strings iterates in a different order in every
# Python process (hash randomisation), which silently changed the random stream for every shop after the first.
# These orders reproduce the dataset the project originally shipped (they were recovered by matching its CSV exports
# bill for bill), and are now fixed so `make seed` gives the same data on every run. A kind missing here falls back to
# sorted order.
FAMILY_ORDER = {
    "hypermarket": ["breakfast", "snacks", "drinks", "pantry", "essentials", "chilled"],
    "restaurant": ["desserts", "drinks", "sides", "mains"],
    "apparel": ["ethnic", "accessories", "bottoms", "casual"],
    "kirana": ["pantry", "staples", "snacks"],
    "pharmacy": ["hygiene", "first-aid", "care", "otc"],
    "bakery": ["cake", "savoury", "pastry", "bread"],
    "electronics": ["accessories", "audio"],
}


def families(kind, products):
    return list(FAMILY_ORDER.get(kind) or sorted({p["family"] for p in products}))


def generate(path: Path, seed=731, limit=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    rng = np.random.default_rng(seed)
    conn = sqlite3.connect(tmp)
    conn.executescript(SCHEMA)
    for kind, name in list(NAMES.items())[:limit]:
        products = catalogue(kind)
        conn.execute(
            "INSERT INTO merchants VALUES(?,?,?,?,?)",
            (kind, name, kind, json.dumps(products), json.dumps(INGREDIENTS if kind == "restaurant" else {})),
        )
        current = {p["id"]: 0 for p in products}
        opening = {}
        base = {
            "hypermarket": 90,
            "restaurant": 64,
            "apparel": 24,
            "kirana": 48,
            "pharmacy": 30,
            "bakery": 42,
            "electronics": 18,
        }[kind]
        for d in range(365):
            day = START + timedelta(days=d)
            season = (
                1
                + 0.15 * math.sin(2 * math.pi * d / 365)
                + (0.22 if day.weekday() >= 5 else 0)
                + (0.2 if 280 <= d <= 310 else 0)
            )
            n = int(rng.poisson(base * season))
            for p in products:
                if not p["candidate"] and (d % 7 == 0 or current[p["id"]] < 5):
                    qty = max(1, int(base * max(propensity(p, d), 0.035) * 8))
                    current[p["id"]] += qty
                    conn.execute(
                        "INSERT INTO stock_events VALUES(?,?,?,?,?,?,?)",
                        (
                            f"ST-{kind}-{d}-{p['id']}",
                            kind,
                            p["id"],
                            f"{day}T08:00:00+05:30",
                            qty,
                            p["cost"],
                            "synthetic supplier bill",
                        ),
                    )
                opening[p["id"]] = current[p["id"]]
            units = {p["id"]: 0 for p in products}
            exposures = {p["id"]: 0 for p in products}
            for b in range(n):
                minute = 10 * 60 + min(719, int((b + float(rng.random())) / max(n, 1) * 720))
                timestamp = f"{day}T{minute // 60:02}:{minute % 60:02}:00+05:30"
                basket = []
                for p in products:
                    if p["candidate"] or current[p["id"]] <= 0:
                        continue
                    exposures[p["id"]] += 1
                    if rng.random() < propensity(p, d):
                        qty = min(current[p["id"]], 1 + int(rng.random() < 0.11))
                        current[p["id"]] -= qty
                        units[p["id"]] += qty
                        basket.append((p, qty))
                if not basket:
                    # Generator samples completed bills; force one in-stock item.
                    eligible = [
                        p
                        for p in products
                        if not p["candidate"] and current[p["id"]] > 0 and propensity(p, d) > 0
                    ]
                    if not eligible:
                        continue
                    p = eligible[int(rng.integers(len(eligible)))]
                    current[p["id"]] -= 1
                    units[p["id"]] += 1
                    basket = [(p, 1)]
                bill = f"POS-{kind}-{d:03}-{b:03}"
                customer = f"L-{kind}-{int(rng.integers(1, 350)):04}" if rng.random() < 0.65 else None
                family = max(
                    {p["family"] for p, q in basket},
                    key=lambda f: sum(q * p["price"] for p, q in basket if p["family"] == f),
                )
                conn.execute("INSERT INTO bills VALUES(?,?,?,?,?)", (bill, kind, timestamp, customer, family))
                conn.executemany(
                    "INSERT INTO lines VALUES(?,?,?,?,?)",
                    [(bill, p["id"], q, p["price"], p["cost"]) for p, q in basket],
                )
            for p in products:
                conn.execute(
                    "INSERT INTO daily VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        kind,
                        str(day),
                        p["id"],
                        units[p["id"]],
                        units[p["id"]] * p["price"],
                        units[p["id"]] * p["cost"],
                        exposures[p["id"]],
                        opening[p["id"]],
                        current[p["id"]],
                        0,
                    ),
                )
        # Donor facts are derived simulated bill-opportunities; keep raw focal bills separate.
        for donor in range(40):
            scale = float(rng.lognormal(0, 0.3))
            family_bias = {f: float(rng.uniform(0.8, 1.2)) for f in families(kind, products)}
            feature = [family_bias[f] for f in sorted(family_bias)]
            for w in range(53):
                wd = w * 7
                if wd >= 365:
                    continue
                days = min(7, 365 - wd)
                bills = int(rng.poisson(base * days * scale))
                ticket = float(np.mean([p["price"] for p in products]) * rng.uniform(1.7, 2.3))
                for p in products:
                    # Assortment variation is observed. Not offered != zero demand.
                    offered = not (p["candidate"] and donor % 8 == 0)
                    exposure = int(bills * rng.uniform(0.88, 1.0)) if offered else 0
                    mu = propensity(p, wd, True) * family_bias[p["family"]] * exposure * 1.11
                    sold = int(rng.poisson(mu)) if exposure else 0
                    conn.execute(
                        "INSERT INTO peer_weeks VALUES(?,?,?,?,?,?,?,?,?)",
                        (
                            f"{kind}-D{donor:03}",
                            kind,
                            str(START + timedelta(days=wd)),
                            p["id"],
                            sold,
                            exposure,
                            bills,
                            ticket,
                            json.dumps(feature),
                        ),
                    )
    conn.commit()
    seed_habits(conn)
    conn.execute("ANALYZE")
    conn.close()
    tmp.replace(path)
    return path


if __name__ == "__main__":
    from app.config import DATA

    print(generate(DATA / "billing.sqlite3"))
