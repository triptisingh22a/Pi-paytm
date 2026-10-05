"""Loads one SKU's price, stock and sales history from the live billing store or the synthetic pilot.

Observation row: day, price (paise), promo, units, opening stock, available (stock existed that day),
censored (stock ran out, so sales understate demand), assignment (randomized | observational | none), block.
A zero-sale day with stock on the shelf is kept; it is information, not a gap.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from threading import Lock
from app.config import DATA
from billing.store import connection, merchant
from pricing import pilot
from pricing.money import to_paise

PILOT_PATH = DATA / "pricing_pilot.sqlite3"
STATE_PATH = DATA / "pricing_state.sqlite3"
_lock = Lock()
DATASETS = ("live", "pilot")


@dataclass
class Series:
    dataset: str
    merchant: str
    product: str
    name: str
    family: str
    price: int  # current offered price, paise
    cost: int  # latest landed unit cost, paise
    on_hand: int
    rows: list
    cost_levels: int = 1
    policy: dict = field(default_factory=dict)  # known replenishment practice, if the data records one
    as_of: date = pilot.AS_OF


@contextmanager
def _pilot_db():
    with _lock:
        if not PILOT_PATH.exists():
            pilot.generate(PILOT_PATH)
    db = sqlite3.connect(PILOT_PATH)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def _check(dataset, mid):
    if dataset not in DATASETS:
        raise ValueError("Unknown dataset")
    if dataset == "pilot" and mid != pilot.MERCHANT:
        raise ValueError("The price-test pilot belongs to Asha Hypermarket")


def list_products(mid, dataset="live"):
    _check(dataset, mid)
    if dataset == "pilot":
        with _pilot_db() as db:
            return [dict(r) for r in db.execute("SELECT id,name,family,price_paise,cost_paise,on_hand,story FROM products ORDER BY id")]
    with connection() as db:
        shop = merchant(mid, db)
    return [
        dict(id=p["id"], name=p["name"], family=p["family"], price_paise=to_paise(p["price"]),
             cost_paise=to_paise(p["cost"]), on_hand=None, story=None)
        for p in shop["products"]
        if not p["candidate"]
    ]


def sku_catalogue(mid, dataset="live"):
    """SKUs the chat agent may name, in the same shape as the billing catalogue."""
    if dataset == "live":
        from billing.catalogue import catalogue

        return catalogue(mid)
    return [
        dict(id=p["id"], name=p["name"], family=p["family"], candidate=False,
             aliases=[p["name"], p["name"].lower().replace(" ", "-"), p["id"]])
        for p in list_products(mid, dataset)
    ]


def load(mid, product, dataset="live"):
    """Raises ValueError for an unknown dataset, merchant or SKU, including a SKU that belongs to another merchant."""
    _check(dataset, mid)
    if dataset == "pilot":
        with _pilot_db() as db:
            p = db.execute("SELECT * FROM products WHERE id=? AND merchant=?", (product, mid)).fetchone()
            if p is None:
                raise ValueError("Unknown product for this shop")
            obs = db.execute("SELECT * FROM obs WHERE merchant=? AND product=? ORDER BY day", (mid, product)).fetchall()
            costs = db.execute("SELECT COUNT(DISTINCT cost_paise) FROM stock_receipts WHERE merchant=? AND product=?",
                               (mid, product)).fetchone()[0]
        rows = [
            dict(day=date.fromisoformat(o["day"]), price=o["price_paise"], promo=o["promo"], units=o["units"],
                 opening=o["opening"], available=bool(o["available"]), censored=bool(o["censored"]),
                 assignment=o["assignment"], block=o["block"])
            for o in obs
        ]
        return Series("pilot", mid, product, p["name"], p["family"], p["price_paise"], p["cost_paise"], p["on_hand"], rows,
                      cost_levels=max(costs, 1),
                      policy=dict(kind="weekly order-up-to", weekday=p["restock_weekday"], level=p["order_up_to"]))
    with connection() as db:
        shop = merchant(mid, db)
        sku = next((x for x in shop["products"] if x["id"] == product and not x["candidate"]), None)
        if sku is None:
            raise ValueError("Unknown product for this shop")
        daily = db.execute(
            "SELECT day,units,exposure,opening,closing FROM daily WHERE merchant=? AND product=? ORDER BY day",
            (mid, product),
        ).fetchall()
        extra = db.execute(
            "SELECT COALESCE(SUM(qty),0) FROM stock_events WHERE merchant=? AND product=? AND source='confirmed demo import'",
            (mid, product),
        ).fetchone()[0]
        costs = db.execute("SELECT COUNT(DISTINCT cost) FROM stock_events WHERE merchant=? AND product=?", (mid, product)).fetchone()[0]
    price, cost = to_paise(sku["price"]), to_paise(sku["cost"])
    rows = [
        dict(day=date.fromisoformat(d[0]), price=price, promo=0, units=d[1], opening=d[3], available=d[2] > 0,
             censored=bool(d[2] > 0 and d[4] == 0), assignment="none", block=None)
        for d in daily
    ]
    return Series("live", mid, product, sku["name"], sku["family"], price, cost, daily[-1][4] + extra, rows,
                  cost_levels=max(costs, 1))


# ---- local scenario / experiment-plan storage (never touches a POS) ---------------------------------------------------

def _state():
    db = sqlite3.connect(STATE_PATH)
    db.execute(
        "CREATE TABLE IF NOT EXISTS scenarios(id INTEGER PRIMARY KEY AUTOINCREMENT, merchant TEXT, dataset TEXT, "
        "product TEXT, kind TEXT, payload TEXT, created TEXT)"
    )
    return db


def save_scenario(mid, dataset, product, kind, payload_json, created):
    db = _state()
    try:
        cur = db.execute("INSERT INTO scenarios(merchant,dataset,product,kind,payload,created) VALUES(?,?,?,?,?,?)",
                         (mid, dataset, product, kind, payload_json, created))
        db.commit()
        return cur.lastrowid
    finally:
        db.close()


def list_scenarios(mid, dataset):
    db = _state()
    try:
        return [dict(zip(("id", "product", "kind", "payload", "created"), r)) for r in db.execute(
            "SELECT id,product,kind,payload,created FROM scenarios WHERE merchant=? AND dataset=? ORDER BY id DESC LIMIT 20",
            (mid, dataset))]
    finally:
        db.close()
