"""Reproducible synthetic counts and explicitly stored planted effects."""

import json
from datetime import date, timedelta
import numpy as np
from app.config import DATA
from twin.customers import evolve

PERSONAS = {
    "kirana": (
        "Sharma Kirana",
        [("Atta", 93, 100, 18, 60), ("Namkeen", 65, 100, 12, 30), ("Milk", 54, 60, 24, 2)],
    ),
    "sweets": (
        "Joshi Sweets",
        [("Kaju katli", 65, 100, 18, 3), ("Ladoo", 55, 80, 20, 4), ("Gift box", 260, 400, 7, 14)],
    ),
    "electronics": (
        "Spark Accessories",
        [("Cable", 65, 100, 12, 365), ("Charger", 230, 400, 6, 365), ("Earbuds", 520, 800, 3, 365)],
    ),
    "vegetables": (
        "Fresh Market",
        [("Tomato", 27.9, 30, 35, 2), ("Potato", 23.25, 25, 30, 3), ("Spinach", 18.6, 20, 25, 1)],
    ),
}


# Illustrative event dates, configurable and not an authoritative festival calendar.
def generate(seed=42):
    rng = np.random.default_rng(seed)
    start = date(2025, 10, 2)
    events = {
        "2025-10-20": "Diwali",
        "2026-03-04": "Holi",
        "2026-03-20": "Eid",
        "2026-09-14": "Ganesh Chaturthi",
    }
    calendar = DATA / "calendar.json"
    if calendar.exists():
        events = json.loads(calendar.read_text())
    else:
        calendar.write_text(json.dumps(events, indent=2))
    shops = {}
    for kind, (name, specs) in PERSONAS.items():
        skus = []
        for idx, (label, cost, price, mean, shelf) in enumerate(specs):
            rows = []
            for day in range(365):
                dt = start + timedelta(days=day)
                fest = int(dt.isoformat() in events)
                payday = int(dt.day <= 5)
                mu = mean * (1 + 0.2 * (dt.weekday() >= 5)) * (1 + 0.15 * payday)
                mu *= 1 + fest * (2.5 if kind == "sweets" else 0.6)
                stockout = bool(rng.random() < 0.06)
                demand = int(rng.poisson(mu))
                stock = int(mean * 0.4) if stockout else int(mean * 8)
                rows.append(
                    {
                        "date": dt.isoformat(),
                        "weekday": dt.weekday(),
                        "festival": fest,
                        "payday": payday,
                        "sales": min(demand, stock),
                        "stockout": stockout,
                        "latent_demand": demand,
                    }
                )
            episodes = []
            # Randomized exchangeable episodes; complete episode is bootstrap unit.
            for _ in range(32):
                baseline = rng.poisson(mean * 7)
                control = rng.poisson(mean * 7)
                treated = rng.poisson(mean * 7 * 1.8)
                post_control = rng.poisson(mean * 7)
                post = rng.poisson(mean * 7 * 0.9)
                episodes.append(
                    {
                        "baseline": int(baseline),
                        "control": int(control),
                        "treated": int(treated),
                        "post_control": int(post_control),
                        "post": int(post),
                        "discount": 0.1,
                    }
                )
            skus.append(
                {
                    "id": f"{kind}-{idx}",
                    "name": label,
                    "cost": cost,
                    "price": price,
                    "mean": mean,
                    "shelf_life": shelf,
                    "lead_time": 1 if shelf < 5 else 2,
                    "stock": int(mean * (1 if shelf < 5 else 2)),
                    "history": rows,
                    "promo_episodes": episodes,
                }
            )
        cohorts = {"new": 25, "repeat": 70, "at_risk": 15, "inactive": 20}
        cohort_history = []
        for day in range(365):
            cohorts = evolve(cohorts, 1, seed=seed + 1000 + day + list(PERSONAS).index(kind) * 500)
            cohort_history.append({"date": (start + timedelta(days=day)).isoformat(), **cohorts})
        shops[kind] = {
            "id": kind,
            "name": name,
            "kind": kind,
            "cash": 1800 if kind == "sweets" else 6500,
            "pending": [1200, 900],
            "dues": [3800 if kind == "sweets" else 0, 0, 4500, 0, 8000, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "skus": skus,
            "repeat_rate": cohorts["repeat"] / max(1, sum(cohorts.values())),
            "customer_cohorts": cohorts,
            "customer_history": cohort_history,
            "as_of": "2026-10-02",
        }
    peers = []
    for i in range(200):
        kind = list(PERSONAS)[i % 4]
        peers.append(
            {
                "private_id": f"background-{i}",
                "kind": kind,
                "features": [
                    float(rng.uniform(60, 160)),
                    float(rng.uniform(30, 100)),
                    float(rng.uniform(0.2, 0.7)),
                    float(rng.uniform(0.1, 0.4)),
                ],
                "daily_units": float(rng.uniform(12, 28)),
            }
        )
    bundle = {"shops": shops, "peers": peers, "seed": seed}
    (DATA / "shops.json").write_text(json.dumps(bundle))
    (DATA / "ground_truth.json").write_text(
        json.dumps(
            {"seed": seed, "uplift": 0.8, "pull_forward": 0.1, "promo_discount": 0.1, "events": events},
            indent=2,
        )
    )
    return bundle


if __name__ == "__main__":
    generate()
    print("Seeded four personas, 365 days and 200 peers; simulated data.")
