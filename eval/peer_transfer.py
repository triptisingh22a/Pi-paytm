"""Cold-start item and merchant-held-out future evaluation on simulated donors."""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import nbinom

root = Path(__file__).resolve().parents[1]
db = sqlite3.connect(root / "data/billing.sqlite3")
db.row_factory = sqlite3.Row
cutoff = "2026-08-28"
results = []
for merchant in db.execute("SELECT * FROM merchants"):
    products = json.loads(merchant["products"])
    kind = merchant["kind"]
    families = sorted({p["family"] for p in products})
    by_id = {p["id"]: p for p in products}
    train = defaultdict(dict)
    future = defaultdict(dict)
    for row in db.execute(
        "SELECT peer,product,SUM(units) units,SUM(exposure) exposure FROM peer_weeks WHERE kind=? AND week>=? AND week<=? GROUP BY peer,product",
        (kind, "2026-05-30", "2026-08-22"),
    ):
        train[row["peer"]][row["product"]] = dict(row)
    for row in db.execute(
        "SELECT peer,product,SUM(units) units,SUM(exposure) exposure FROM peer_weeks WHERE kind=? AND week>? AND week<=? GROUP BY peer,product",
        (kind, cutoff, "2026-09-26"),
    ):
        future[row["peer"]][row["product"]] = dict(row)

    def feature(rows, by_id=by_id, families=families):
        mix = np.array(
            [
                sum(
                    r["units"]
                    for pid, r in rows.items()
                    if not by_id[pid]["candidate"] and by_id[pid]["family"] == family
                )
                for family in families
            ],
            dtype=float,
        )
        return mix / max(mix.sum(), 1)

    for target, observed in train.items():
        mix = feature(observed)
        for candidate in [p for p in products if p["candidate"]]:
            pid = candidate["id"]
            actual = future[target][pid]
            if actual["exposure"] < 200:
                continue
            others = [
                (peer, rows)
                for peer, rows in train.items()
                if peer != target and rows[pid]["exposure"] >= 200
            ]
            ranked = sorted(
                [
                    (
                        float(
                            np.linalg.norm(feature(rows) - mix)
                            + abs(
                                feature(rows)[families.index(candidate["family"])]
                                - mix[families.index(candidate["family"])]
                            )
                        ),
                        rows[pid],
                    )
                    for peer, rows in others
                ],
                key=lambda x: x[0],
            )[:30]
            weights = np.exp(-8 * np.array([r[0] for r in ranked]))
            weights /= weights.sum()
            rate = sum(w * r[1]["units"] for w, r in zip(weights, ranked)) / sum(
                w * r[1]["exposure"] for w, r in zip(weights, ranked)
            )
            pooled = sum(rows[pid]["units"] for peer, rows in others) / sum(
                rows[pid]["exposure"] for peer, rows in others
            )
            alpha = 0.5 + rate * 500
            beta = 501.0
            exposure = actual["exposure"]
            lower, upper = nbinom.ppf([0.1, 0.9], alpha, beta / (beta + exposure))
            truth = actual["units"] / exposure * 100
            results.append(
                {
                    "kind": kind,
                    "truth_per_100": truth,
                    "peer_per_100": alpha / beta * 100,
                    "type_item_mean_per_100": pooled * 100,
                    "covered": bool(lower <= actual["units"] <= upper),
                }
            )
truth = np.array([r["truth_per_100"] for r in results])
report = {
    "simulated": True,
    "cutoff": cutoff,
    "evaluation": "Target merchant entirely excluded as donor; candidate outcomes excluded from target/peer similarity; completed future weeks only used for scoring.",
    "cases": len(results),
    "weighted_peer_rmse_units_per_100_bills": float(
        np.sqrt(np.mean((truth - np.array([r["peer_per_100"] for r in results])) ** 2))
    ),
    "type_item_mean_rmse_units_per_100_bills": float(
        np.sqrt(
            np.mean(
                (truth - np.array([r["type_item_mean_per_100"] for r in results])) ** 2
            )
        )
    ),
    "no_history_zero_baseline_rmse": float(np.sqrt(np.mean(truth**2))),
    "model_predictive_p10_p90_coverage": float(
        np.mean([r["covered"] for r in results])
    ),
    "limitation": "Synthetic transfer diagnostic only. Generator exchangeability, seasonality and assortment selection differ from real shops. No causal replacement uplift or real-world calibration is established.",
}
(root / "eval/peer_transfer.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
assert results and all(np.isfinite(truth))
