"""Synthetic price-test pilot for Asha Hypermarket. Separate database; the live billing data is never changed.

The generator knows the true price response of each product. That truth is written to
`eval/pricing_pilot_truth.json`, which only the evaluation reads. Model, API and agent code never open it.
"""

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
import numpy as np

AS_OF = date(2026, 10, 2)
DAYS = 150
SEED = 2026
WEEKDAY = [0.90, 0.90, 0.95, 1.00, 1.15, 1.30, 1.10]  # Mon..Sun demand multipliers (true, hidden)
MERCHANT = "hypermarket"

SCHEMA = """
CREATE TABLE products(id TEXT PRIMARY KEY, merchant TEXT, name TEXT, family TEXT, price_paise INTEGER,
  cost_paise INTEGER, on_hand INTEGER, order_up_to INTEGER, restock_weekday INTEGER, story TEXT);
CREATE TABLE price_spells(merchant TEXT, product TEXT, start_day TEXT, end_day TEXT, price_paise INTEGER,
  reason TEXT, assignment TEXT);
CREATE TABLE obs(merchant TEXT, product TEXT, day TEXT, price_paise INTEGER, promo INTEGER, units INTEGER,
  opening INTEGER, available INTEGER, censored INTEGER, assignment TEXT, block INTEGER);
CREATE TABLE stock_receipts(merchant TEXT, product TEXT, day TEXT, qty INTEGER, cost_paise INTEGER);
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX obs_query ON obs(merchant, product, day);
"""

# id, name, family, current price, unit cost (paise), base units/day at current price, true eta, price levels (rupees),
# design, weekly order-up-to (units), story shown in the UI
SKUS = [
    ("pilot-01", "Branded biscuits 100 g", "snacks", 4000, 3200, 55, 1.1, [36, 38, 40, 42], "randomized", 520,
     "Randomized price blocks. Customers barely react, so a cut mostly gives margin away."),
    ("pilot-02", "Cooking oil 1 L", "essentials", 15000, 10500, 22, 4.0, [135, 140, 150, 160], "randomized", 210,
     "Randomized price blocks. Customers react strongly, so a modest cut can pay for itself."),
    ("pilot-03", "Toor dal 1 kg", "essentials", 16000, 11800, 30, 3.2, [150, 155, 160, 170], "randomized", 150,
     "Randomized price blocks, but supply is tight: stock runs out before extra demand can be served."),
    ("pilot-04", "Premium tea 250 g", "beverages", 22000, 15000, 18, 2.5, [210, 220, 240], "confounded", 190,
     "Prices were changed by hand, mostly in busy weeks. Price and demand moved together, so the history misleads."),
    ("pilot-05", "Soap bar", "care", 4500, 3000, 40, 1.8, [42, 45], "sparse", 400,
     "One short price change five days long. Not enough to say anything about price response."),
    ("pilot-06", "Instant coffee 50 g", "beverages", 19000, 12000, 15, 0.8, [180, 190, 200, 210], "randomized", 150,
     "Randomized price blocks. Customers barely notice price, so a rise can raise contribution."),
]
ALPHA = 0.12  # true negative-binomial overdispersion
PROMO_LIFT = 1.25  # true promotion/display lift, independent of price


def _day(i):
    return AS_OF - timedelta(days=DAYS - 1 - i)


def _prices(design, levels, current, rng):
    """Offered price per day and block id, according to the design."""
    n_blocks = (DAYS + 6) // 7
    if design == "randomized":
        order = []
        while len(order) < n_blocks:  # balanced cycles: every price appears once per cycle, random order
            cycle = list(levels)
            rng.shuffle(cycle)
            order += cycle
        block_price = order[:n_blocks]
        # make sure the final block runs at the current price so "today" is unambiguous
        block_price[-1] = current // 100
        return [block_price[i // 7] * 100 for i in range(DAYS)], [i // 7 for i in range(DAYS)], "randomized"
    if design == "sparse":
        prices = [current] * DAYS
        for i in range(DAYS - 40, DAYS - 35):
            prices[i] = levels[0] * 100
        return prices, [None] * DAYS, "none"
    return None, [None] * DAYS, "observational"


def generate(path, truth_path=None, seed=SEED):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    rng = np.random.default_rng(seed)
    conn = sqlite3.connect(tmp)
    conn.executescript(SCHEMA)
    truth = {}
    festival = rng.random((DAYS + 6) // 7) < 0.25  # hidden demand shocks that nobody records
    for pid, name, family, current, cost, base, eta, levels, design, order_up_to, story in SKUS:
        prices, blocks, assignment = _prices(design, levels, current, rng)
        promo_days = (rng.random(DAYS) < 0.12) if design == "randomized" else np.zeros(DAYS, bool)
        stock = order_up_to // 2
        rows, receipts, spells = [], [], []
        for i in range(DAYS):
            d = _day(i)
            shock = 1.6 if festival[i // 7] else 1.0
            if prices is None:  # confounded: the shop raises the price in the busy (festival) weeks
                p = (levels[2] if festival[i // 7] else levels[1] if rng.random() < 0.7 else levels[0]) * 100
                if i >= DAYS - 7:
                    p = current
            else:
                p = prices[i]
            if d.weekday() == 0 or stock < base * 0.3:  # weekly restock, or an emergency top-up
                add = max(0, order_up_to - stock)
                if add:
                    stock += add
                    receipts.append((MERCHANT, pid, str(d), int(add), cost))
            opening = stock
            seasonal = 1 + 0.08 * np.sin(2 * np.pi * i / 90)
            mu = base * WEEKDAY[d.weekday()] * seasonal * shock * (p / current) ** (-eta)
            mu *= PROMO_LIFT if promo_days[i] else 1.0
            r = 1 / ALPHA
            demand = int(rng.poisson(rng.gamma(r, mu / r)))
            sold = min(demand, stock)
            stock -= sold
            censored = int(demand >= opening and opening > 0)
            rows.append((MERCHANT, pid, str(d), int(p), int(promo_days[i]), int(sold), int(opening), int(opening > 0),
                         censored, assignment, blocks[i]))
        run_start = 0
        for i in range(1, DAYS + 1):
            if i == DAYS or rows[i][3] != rows[run_start][3]:
                reason = {"randomized": "randomized price test", "sparse": "short trial"}.get(design, "set by hand")
                spells.append((MERCHANT, pid, rows[run_start][2], rows[i - 1][2], rows[run_start][3], reason, assignment))
                run_start = i
        conn.executemany("INSERT INTO obs VALUES(?,?,?,?,?,?,?,?,?,?,?)", rows)
        conn.executemany("INSERT INTO stock_receipts VALUES(?,?,?,?,?)", receipts)
        conn.executemany("INSERT INTO price_spells VALUES(?,?,?,?,?,?,?)", spells)
        conn.execute("INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (pid, MERCHANT, name, family, current, cost, int(stock), order_up_to, 0, story))
        truth[pid] = dict(name=name, eta=eta, base_per_day=base, alpha=ALPHA, promo_lift=PROMO_LIFT,
                          weekday=WEEKDAY, design=design, current_price_paise=current, cost_paise=cost,
                          order_up_to=order_up_to)
    conn.execute("INSERT INTO meta VALUES('seed',?)", (str(seed),))
    conn.execute("INSERT INTO meta VALUES('as_of',?)", (str(AS_OF),))
    conn.execute("INSERT INTO meta VALUES('kind','synthetic pricing pilot - not real merchant data')")
    conn.commit()
    conn.close()
    tmp.replace(path)
    if truth_path:
        Path(truth_path).parent.mkdir(parents=True, exist_ok=True)
        Path(truth_path).write_text(json.dumps(truth, indent=1), encoding="utf-8")
    return path


if __name__ == "__main__":
    from app.config import DATA, ROOT

    print(generate(DATA / "pricing_pilot.sqlite3", ROOT / "eval" / "pricing_pilot_truth.json"))
