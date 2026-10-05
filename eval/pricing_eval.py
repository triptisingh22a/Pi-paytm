"""Evaluation of the repricing model on the synthetic pilot, where the true price response is known.

Run from the project root:  python eval/pricing_eval.py
Reads eval/pricing_pilot_truth.json (written by the generator). Nothing in the app reads that file.

Reported separately, because a good sales forecast does not validate a counterfactual price decision:
  1. recovery of the hidden price sensitivity (randomized items)
  2. future-period holdout demand forecast vs simple baselines, and predictive-interval coverage
  3. coverage of the uncertainty interval for the contribution change against the true change
  4. decision regret on held-out candidate prices vs keeping the price and simple policies
  5. confounding stress test (observational item)
"""

import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
import numpy as np
from scipy.stats import nbinom

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
from pricing import data, model, pilot, recommend, service, simulate  # noqa: E402
from pricing.evidence import assess  # noqa: E402

MID = pilot.MERCHANT
HORIZON = 7
HOLDOUT = 28


def true_week_units(t):
    mean_weekday = float(np.mean(t["weekday"]))
    return t["base_per_day"] * mean_weekday * HORIZON


def true_delta(t, price, base_units):
    """True expected contribution change (paise) for a price, scaled to `base_units` at the current price. No stock cap."""
    p0, c = t["current_price_paise"], t["cost_paise"]
    return base_units * ((price / p0) ** (-t["eta"]) * (price - c) - (p0 - c))


def main(out=None):
    tmp = Path(tempfile.mkdtemp())
    truth_path = tmp / "truth.json"
    db = pilot.generate(tmp / "pilot.sqlite3", truth_path)
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    data.PILOT_PATH = db  # evaluation never touches the shipped pilot database
    service._pooled_prior.cache_clear()
    report = dict(seed=pilot.SEED, horizon_days=HORIZON, holdout_days=HOLDOUT, items={})
    recovery, forecasts, coverage_hits, coverage_n, regrets = [], [], 0, 0, {"keep": [], "pi": [], "model_top": [], "cut_5pct": []}
    for pid, t in truth.items():
        s = data.load(MID, pid, "pilot")
        ev = assess(s)
        item = dict(name=t["name"], design=t["design"], evidence_state=ev["state"], true_eta=t["eta"])
        fitted = service._fit_if_supported(s, ev, MID, "pilot")
        if not fitted:
            item["note"] = "no fit: evidence insufficient (correctly withheld)"
            report["items"][pid] = item
            continue
        item.update(eta_hat=round(fitted["eta"], 3), eta_se=round(fitted["eta_se"], 3),
                    eta_error=round(fitted["eta"] - t["eta"], 3),
                    within_2se=bool(abs(fitted["eta"] - t["eta"]) <= 2 * fitted["eta_se"]))
        if t["design"] == "randomized":
            recovery.append(abs(fitted["eta"] - t["eta"]))
        # 2. holdout forecast: fit on the earlier days only, predict the last 28 with their actual prices and promotions
        cutoff = s.rows[-HOLDOUT - 1]["day"]
        train = model.fit(s, service._pooled_prior("pilot", MID, pid), last_day=cutoff)
        test = [r for r in s.rows[-HOLDOUT:] if r["available"] and not r["censored"]]
        if train and test:
            rng = np.random.default_rng(7)
            thetas = model.draw_parameters(train, 300, rng)
            X = model.features([r["day"] for r in test], [r["price"] for r in test], [r["promo"] for r in test], s.price)
            mu = np.exp(thetas[:, :-1] @ X.T)
            r_ = 1 / np.exp(thetas[:, -1])[:, None]
            draws = nbinom.rvs(r_, r_ / (r_ + mu), random_state=rng)
            y = np.array([r["units"] for r in test], float)
            lo, hi = np.percentile(draws, [10, 90], axis=0)
            pred = mu.mean(axis=0)
            hist = np.mean([r["units"] for r in s.rows[: -HOLDOUT] if r["available"] and not r["censored"]][-28:])
            item["holdout"] = dict(
                days=len(test), mae_model=round(float(np.abs(pred - y).mean()), 2),
                mae_last28_mean=round(float(np.abs(hist - y).mean()), 2),
                interval80_coverage=round(float(((y >= lo) & (y <= hi)).mean()), 3),
            )
            forecasts.append((item["holdout"]["mae_model"], item["holdout"]["mae_last28_mean"], item["holdout"]["interval80_coverage"]))
        # 3 and 4. decisions over a candidate grid
        grid, _ = recommend.candidate_grid(s.price, s.cost, 0)
        days = service._days(s, HORIZON)
        huge = 10_000_000  # remove the stock cap so the model change is comparable with the true unconstrained change
        sim = simulate.run(fitted, days, grid, s.cost, 0, huge)
        base_units = float(sim[s.price]["units"].mean())
        summ = {p: simulate.summarise(sim, s.price, p) for p in grid}
        true_d = {p: true_delta(t, p, base_units) for p in grid}
        in_support = [p for p in grid if p != s.price and assess(s, p)["support"]["kind"] == "interpolation"]
        hits = sum(summ[p]["delta_mean_interval"][0] <= true_d[p] <= summ[p]["delta_mean_interval"][1] for p in in_support)
        item["delta_interval_coverage"] = dict(candidates=len(in_support), covered=hits)
        if t["design"] == "randomized":
            coverage_hits += hits
            coverage_n += len(in_support)
        labels = {p: recommend.decide(ev | {"support": assess(s, p)["support"]}, summ[p]) for p in grid if p != s.price}
        best_true = max([0.0] + [true_d[p] for p in grid])
        top = max((p for p in grid if p != s.price), key=lambda p: summ[p]["delta_contribution_paise"])
        confident = [p for p in labels if labels[p] == "likely_improves"]
        pi_pick = max(confident, key=lambda p: summ[p]["delta_contribution_paise"]) if confident else None
        cut = max((p for p in grid if p < s.price), default=None)
        cut = min(grid, key=lambda p: abs(p - 0.95 * s.price))
        picks = dict(keep=None, pi=pi_pick, model_top=top, cut_5pct=cut)
        item["decisions"] = dict(
            best_true_gain_rupees=round(best_true / 100), top_model_price=top // 100,
            true_gain_at_top_rupees=round(true_d[top] / 100), pi_choice=(pi_pick // 100) if pi_pick else "keep price",
            labels_confident=len(confident),
        )
        for name, p in picks.items():
            gain = true_d[p] if p else 0.0
            regrets[name].append((best_true - gain) / 100)
        report["items"][pid] = item
    # 5. confounding stress: the observational item must not reach a confident label
    conf = report["items"].get("pilot-04", {})
    s4 = data.load(MID, "pilot-04", "pilot")
    stress = service.recommend_price(MID, "pilot-04", HORIZON, "pilot")
    conf["stress"] = dict(
        true_eta=truth["pilot-04"]["eta"], estimated_eta=conf.get("eta_hat"),
        any_confident_label=any(c["decision"]["id"] == "likely_improves" for c in stress["candidates"]),
        overall_label=stress["decision"]["id"],
    )
    report["summary"] = dict(
        randomized_items=len(recovery),
        mean_abs_eta_error_randomized=round(float(np.mean(recovery)), 3),
        holdout_mae_model=round(float(np.mean([f[0] for f in forecasts])), 2),
        holdout_mae_last28_mean=round(float(np.mean([f[1] for f in forecasts])), 2),
        holdout_interval80_coverage=round(float(np.mean([f[2] for f in forecasts])), 3),
        delta_interval80_coverage=round(coverage_hits / max(coverage_n, 1), 3),
        delta_interval_cases=coverage_n,
        mean_regret_rupees={k: round(float(np.mean(v)), 1) for k, v in regrets.items() if v},
        note="Synthetic pilot only. These results do not establish accuracy on real merchants or causal effects of observational history.",
    )
    text = json.dumps(report, indent=1, ensure_ascii=False)
    (out or ROOT / "eval" / "pricing_eval.json").write_text(text, encoding="utf-8")
    return report


if __name__ == "__main__":
    r = main()
    for pid, it in r["items"].items():
        print(pid, it["name"], "|", it["evidence_state"], "| eta true", it["true_eta"], "est", it.get("eta_hat"), "+/-", it.get("eta_se"))
    print(json.dumps(r["summary"], indent=1))
    print(json.dumps(r["items"]["pilot-04"]["stress"], indent=1))
