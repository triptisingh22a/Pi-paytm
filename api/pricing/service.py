"""Repricing scenarios and price comparisons. Read-only: nothing here changes a price or places an order."""

import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from statistics import pstdev
import numpy as np
from billing.services import receipt
from pricing import data, model, recommend as rec, simulate
from pricing.breakeven import breakeven
from pricing.evidence import assess
from pricing.money import to_paise

MODEL_VERSION = "pricing-nb-1"
MAX_HORIZON = 30
ETA_RANGE = (0.1, 8.0)
OBSERVATIONAL_SD_INFLATION = 4.0  # price-coefficient standard deviation multiplier for non-randomized history
SCOPE = "Own item only. Shoppers switching to or from similar items (category spillovers) are not included."


def _horizon(h):
    if not isinstance(h, int) or isinstance(h, bool) or not 1 <= h <= MAX_HORIZON:
        raise ValueError(f"Horizon must be a whole number of days from 1 to {MAX_HORIZON}")
    return h


def _history_daily(series):
    """Average units per day over the latest 28 days with stock that were not cut short by a stockout."""
    ok = [r["units"] for r in series.rows if r["available"] and not r["censored"]][-28:]
    return (sum(ok) / len(ok)) if ok else 0.0


@lru_cache(maxsize=32)
def _pooled_prior(dataset, mid, exclude):
    """Prior for the price coefficient, centred on items with randomized price tests (never on peers' sales rates)."""
    etas = []
    for p in data.list_products(mid, dataset):
        if p["id"] == exclude:
            continue
        s = data.load(mid, p["id"], dataset)
        if assess(s)["state"] in ("synthetic_experiment", "real_experiment"):
            f = model.fit(s)
            if f:
                etas.append(f["eta"])
    if len(etas) < 2:
        return model.FLAT_PRIOR
    # coefficient b_price = -eta
    return (-float(np.mean(etas)), max(1.0, float(np.std(etas)) * 1.5))


def _days(series, horizon):
    return [series.as_of + timedelta(days=i + 1) for i in range(horizon)]


def _stock(series, horizon, receipts, use_policy):
    receipts = receipts or []
    for r in receipts:
        if not (isinstance(r.get("day"), int) and 1 <= r["day"] <= horizon and isinstance(r.get("qty"), int) and 0 < r["qty"] <= 100000):
            raise ValueError("Each arrival needs a day within the horizon and a whole quantity")
    policy = series.policy if (use_policy and series.policy) else None
    return dict(
        opening=series.on_hand,
        receipts=[(r["day"] - 1, r["qty"]) for r in receipts],
        policy=dict(weekday=policy["weekday"], level=policy["level"]) if policy else None,
        description=(
            f"opening stock {series.on_hand}"
            + (f", order up to {policy['level']} each week" if policy else ", no further deliveries assumed")
            + (f", plus {sum(r['qty'] for r in receipts)} units you listed" if receipts else "")
        ),
    )


def _prep(mid, product, dataset, horizon, extra_cost, receipts, use_policy, proposed=None):
    horizon = _horizon(horizon)
    series = data.load(mid, product, dataset)
    extra = to_paise(extra_cost, "other cost per unit") if extra_cost else 0
    evidence = assess(series, proposed)
    stock = _stock(series, horizon, receipts, use_policy)
    return series, horizon, extra, evidence, stock


def _fit_if_supported(series, evidence, mid, dataset):
    if evidence["state"] == "insufficient":
        return None
    fitted = model.fit(series, _pooled_prior(dataset, mid, series.product))
    if fitted and evidence["state"] == "observational":
        # Price moved with other things; widen the price coefficient so the intervals admit that (a product choice).
        cov = fitted["cov"].copy()
        cov[1, :] *= OBSERVATIONAL_SD_INFLATION
        cov[:, 1] *= OBSERVATIONAL_SD_INFLATION
        fitted = dict(fitted, cov=cov, eta_se=fitted["eta_se"] * OBSERVATIONAL_SD_INFLATION, inflated=True)
    return fitted


def _model_card(fitted):
    if not fitted:
        return None
    return dict(
        price_sensitivity=round(fitted["eta"], 3), price_sensitivity_se=round(fitted["eta_se"], 3),
        overdispersion=round(fitted["alpha"], 3), observations=fitted["n_obs"], stockout_days_modelled=fitted["n_censored"],
        converged=fitted["converged"], prior_weight=round(fitted["prior"]["weight"], 3),
        uncertainty_widened_for_confounding=bool(fitted.get("inflated")),
        prior_mean_sensitivity=round(-fitted["prior"]["mean"], 3), version=MODEL_VERSION,
        note="Price sensitivity is the % fall in expected units for a 1% rise in price, near the current price.",
    )


def _forecast_inputs(series, evidence, fitted, assumed_eta):
    """Returns (mode, simulation model). Never invents a forecast for an item with no price evidence."""
    if fitted:
        return "model", fitted
    if assumed_eta is not None:
        if not ETA_RANGE[0] <= assumed_eta <= ETA_RANGE[1]:
            raise ValueError(f"Assumed price sensitivity must be between {ETA_RANGE[0]} and {ETA_RANGE[1]}")
        daily = _history_daily(series)
        if daily <= 0:
            return "withheld", None
        return "assumption", simulate.assumption_model(daily, assumed_eta, series.price)
    return "withheld", None


def _contribution_sd(series):
    ok = [r["units"] for r in series.rows if r["available"] and not r["censored"]][-56:]
    margin = series.price - series.cost
    return (pstdev(ok) * margin) if len(ok) > 1 else 0.0


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def reprice(mid, product, proposed_price, horizon=7, dataset="live", extra_cost=0, receipts=None, use_policy=True,
            baseline_units=None, assumed_eta=None):
    proposed = to_paise(proposed_price, "proposed price")
    series, horizon, extra, evidence, stock = _prep(mid, product, dataset, horizon, extra_cost, receipts, use_policy, proposed)
    fitted = _fit_if_supported(series, evidence, mid, dataset)
    mode, sim_model = _forecast_inputs(series, evidence, fitted, assumed_eta)
    days = _days(series, horizon)
    summary, supply, sim_baseline_units = None, stock["opening"] + sum(q for _, q in stock["receipts"]), None
    if mode != "withheld" and proposed != series.price:
        sim = simulate.run(sim_model, days, [series.price, proposed], series.cost, extra, stock["opening"],
                           stock["receipts"], stock["policy"])
        summary = simulate.summarise(sim, series.price, proposed)
        sim_baseline_units = summary["baseline_units"]
        supply = float((sim[series.price]["units"] + sim[series.price]["remaining"]).mean())
    elif mode != "withheld":
        sim = simulate.run(sim_model, days, [series.price], series.cost, extra, stock["opening"], stock["receipts"], stock["policy"])
        sim_baseline_units = float(sim[series.price]["units"].mean())
    # Baseline for break-even: what the merchant says, else the stock-limited forecast, else history (not a forecast).
    if baseline_units is not None:
        if not isinstance(baseline_units, (int, float)) or isinstance(baseline_units, bool) or not 0 <= baseline_units <= 1_000_000:
            raise ValueError("Baseline units must be a number from 0 to 1,000,000")
        base_units, base_source = float(baseline_units), "merchant_supplied"
    elif sim_baseline_units is not None:
        base_units, base_source = round(sim_baseline_units, 2), "model_forecast" if mode == "model" else "assumption_scenario"
    else:
        base_units, base_source = round(_history_daily(series) * horizon), "historical_average"
    be = breakeven(series.price, proposed, series.cost, base_units, extra)
    feasible = None if be["required_units"] is None else be["required_units"] <= supply
    decision_id = rec.decide(evidence, summary if mode == "model" else None)
    reason = _reason(decision_id, mode, evidence, summary, be, feasible)
    plan = None
    if decision_id in ("insufficient_evidence", "trial_recommended"):
        plan = rec.experiment_plan(series, [proposed], [summary] if summary else [], horizon,
                                   (series.price - series.cost - extra) * _history_daily(series), _contribution_sd(series),
                                   series.cost, extra)
    result = dict(
        kind="reprice", dataset=dataset, merchant=mid, currency="INR", model_version=MODEL_VERSION,
        data_cutoff=str(series.as_of), generated_at=_stamp(), horizon=horizon,
        window=[str(days[0]), str(days[-1])], scope=SCOPE,
        product=dict(id=series.product, name=series.name, family=series.family, price_paise=series.price,
                     cost_paise=series.cost, on_hand=series.on_hand, extra_cost_paise=extra),
        proposed_price_paise=proposed,
        baseline=dict(units=base_units, source=base_source, contribution_paise=be["baseline_contribution_paise"],
                      revenue_paise=be["baseline_revenue_paise"]),
        breakeven=be, stock=dict(opening=stock["opening"], description=stock["description"],
                                 expected_supply=round(supply, 1), required_units_reachable=feasible),
        evidence=evidence, mode=mode,
        assumption=dict(price_sensitivity=assumed_eta, label="assumption-based scenario: you chose this sensitivity; it was not learned")
        if mode == "assumption" else None,
        forecast=summary if mode != "withheld" else None,
        model=_model_card(fitted), policy=rec.POLICY,
        decision=dict(id=decision_id, label=rec.LABELS[decision_id], reason=reason),
        experiment_plan=plan,
    )
    result["headline"], result["numbers"] = _headline(result)
    result["receipt"] = _receipt(result)
    return result


def recommend_price(mid, product, horizon=7, dataset="live", candidates=None, low=None, high=None, step=None,
                    max_price=None, min_margin_fraction=None, extra_cost=0, receipts=None, use_policy=True,
                    assumed_eta=None):
    series, horizon, extra, evidence, stock = _prep(mid, product, dataset, horizon, extra_cost, receipts, use_policy)
    explicit = [to_paise(c, "candidate price") for c in candidates] if candidates else None
    if explicit is not None and not 1 <= len(explicit) <= rec.POLICY["max_candidates"]:
        raise ValueError(f"Give between 1 and {rec.POLICY['max_candidates']} candidate prices")
    prices, dropped = rec.candidate_grid(
        series.price, series.cost, extra, step=to_paise(step, "step") if step else None,
        low=to_paise(low, "lowest price") if low is not None else None,
        high=to_paise(high, "highest price") if high is not None else None,
        explicit=explicit, max_price=to_paise(max_price, "maximum price") if max_price is not None else None,
        min_margin_fraction=min_margin_fraction,
    )
    fitted = _fit_if_supported(series, evidence, mid, dataset)
    mode, sim_model = _forecast_inputs(series, evidence, fitted, assumed_eta)
    days = _days(series, horizon)
    sim = None
    if mode != "withheld":
        sim = simulate.run(sim_model, days, prices, series.cost, extra, stock["opening"], stock["receipts"], stock["policy"])
    base_units = round(sim_summary_units(sim, series.price) if sim else _history_daily(series) * horizon, 2)
    rows, summaries = [], []
    for p in prices:
        evid = assess(series, p)
        be = breakeven(series.price, p, series.cost, base_units, extra)
        s = simulate.summarise(sim, series.price, p) if sim else None
        label = rec.decide(evid, s if mode == "model" else None)
        if s:
            summaries.append(s)
        rows.append(dict(price_paise=p, is_current=p == series.price, breakeven=be, forecast=s,
                         support=evid["support"],
                         decision=dict(id="current_price", label="Current price") if p == series.price else dict(id=label, label=rec.LABELS[label])))
    best = None
    if mode == "model":
        challengers = [r for r in rows if not r["is_current"] and r["forecast"]]
        if challengers:
            best = max(challengers, key=lambda r: r["forecast"]["delta_contribution_paise"])
    overall = best["decision"]["id"] if best else "insufficient_evidence"
    if mode == "model" and best and best["forecast"]["delta_contribution_paise"] <= 0:
        overall = "trial_recommended" if overall == "trial_recommended" else overall
    summaries.sort(key=lambda s: s["delta_contribution_paise"])
    plan = None
    if overall in ("insufficient_evidence", "trial_recommended"):
        plan = rec.experiment_plan(series, [r["price_paise"] for r in rows if not r["is_current"]][:3], summaries, horizon,
                                   (series.price - series.cost - extra) * _history_daily(series), _contribution_sd(series),
                                   series.cost, extra)
    result = dict(
        kind="recommend_price", dataset=dataset, merchant=mid, currency="INR", model_version=MODEL_VERSION,
        data_cutoff=str(series.as_of), generated_at=_stamp(), horizon=horizon, window=[str(days[0]), str(days[-1])],
        scope=SCOPE,
        product=dict(id=series.product, name=series.name, family=series.family, price_paise=series.price,
                     cost_paise=series.cost, on_hand=series.on_hand, extra_cost_paise=extra),
        baseline=dict(units=base_units, source="model_forecast" if mode == "model" else
                      "assumption_scenario" if mode == "assumption" else "historical_average"),
        stock=dict(opening=stock["opening"], description=stock["description"]),
        evidence=evidence, mode=mode, candidates=rows,
        dropped=[dict(price_paise=p, reason=why) for p, why in dropped],
        best_price_paise=best["price_paise"] if best else None,
        assumption=dict(price_sensitivity=assumed_eta, label="assumption-based scenario: you chose this sensitivity; it was not learned")
        if mode == "assumption" else None,
        model=_model_card(fitted), policy=rec.POLICY,
        decision=dict(id=overall, label=rec.LABELS[overall], reason=_grid_reason(overall, mode, evidence, best)),
        experiment_plan=plan,
    )
    result["headline"], result["numbers"] = _grid_headline(result)
    result["receipt"] = _receipt(result)
    return result


def sim_summary_units(sim, price):
    return float(sim[price]["units"].mean())


def _inr(paise, digits=0):
    return f"{'-' if paise < 0 else ''}₹{abs(paise) / 100:,.{digits}f}"


def _reason(decision_id, mode, evidence, summary, be, feasible):
    if mode == "withheld":
        return evidence["explanation"] + " Pi can show what you would need to sell, but will not guess what you would sell."
    if mode == "assumption":
        return "This uses a price sensitivity you chose, not one learned from this item's history, so it is a what-if only."
    if (evidence["support"] or {}).get("kind") == "extrapolation":
        return "This price is outside the range ever tested for this item, so the forecast is a stretch; try a small trial first."
    if decision_id == "likely_improves":
        return "Randomized price tests inside the tested range show contribution rising in most simulated futures."
    if decision_id == "likely_reduces":
        return "Contribution falls in most simulated futures even though units may rise."
    return evidence["explanation"] if evidence["state"] == "observational" else "The result is too uncertain to call; a short, controlled trial would settle it."


def _grid_reason(overall, mode, evidence, best):
    if mode == "withheld":
        return evidence["explanation"] + " Break-even volumes are shown for each price; demand forecasts are withheld."
    if mode == "assumption":
        return "Every forecast here depends on a sensitivity you chose; none is learned from this item's history."
    return {
        "likely_improves": "The best price improves contribution in most simulated futures, inside the tested price range.",
        "likely_reduces": "Every alternative price lowers expected contribution; keep the current price.",
        "trial_recommended": "No price clears the bar for a confident change. Run a short trial rather than switching outright.",
    }.get(overall, evidence["explanation"])


class Say:
    """Formats numbers for display and remembers each one, so the numeric guard can authorise exactly what is shown."""

    def __init__(self):
        self.numbers = []

    def n(self, x, digits=0):
        v = round(x, digits)
        self.numbers.append(v)
        return f"{v:,.{digits}f}"

    def inr(self, paise, digits=0):
        v = round(abs(paise) / 100, digits)
        self.numbers.append(v)
        return f"{'-' if paise < 0 else ''}₹{v:,.{digits}f}"

    def pct(self, fraction, digits=1):
        v = round(fraction * 100, digits)
        self.numbers.append(round(v / 100, 6))
        return f"{v:+.{digits}f}%"

    def lit(self, x):
        self.numbers.append(x)
        return str(x)


def _headline(r):
    s = Say()
    be, p, name = r["breakeven"], r["proposed_price_paise"], r["product"]["name"]
    if p == r["product"]["price_paise"]:
        return f"{name} is already priced at {s.inr(p)}. Pick a different price to compare.", s.numbers
    if be["status"] == "no_breakeven":
        return (f"At {s.inr(p)}, {name} earns {s.inr(be['new_margin_paise'], 2)} per unit after cost, so no sales volume can "
                f"beat today's {s.inr(be['baseline_contribution_paise'])}."), s.numbers
    if be["status"] == "baseline_not_positive":
        return f"{name} earns nothing per unit at today's price, so any sale at {s.inr(p)} improves on it.", s.numbers
    need = (f"At {s.inr(p)} you need at least {s.n(be['required_units'])} sales to beat {s.inr(be['baseline_contribution_paise'])} contribution")
    if be["baseline_units"]:
        need += f" ({s.pct(be['required_uplift'])} on {s.n(be['baseline_units'], 0 if float(be['baseline_units']).is_integer() else 1)} units)"
    f = r["forecast"]
    if r["mode"] == "withheld":
        return need + ". This item has no price history to learn from, so we cannot yet estimate whether that is achievable.", s.numbers
    if r["stock"]["required_units_reachable"] is False:
        return need + f". Stock is the limit: only about {s.n(r['stock']['expected_supply'])} units are available over {s.lit(r['horizon'])} days.", s.numbers
    tail = (f". Our estimate is {s.n(f['expected_units'])} units (middle {s.lit(80)}% of outcomes: {s.n(f['units_outcome_interval'][0])} to "
            f"{s.n(f['units_outcome_interval'][1])}), a contribution change of {s.inr(f['delta_contribution_paise'])}")
    s.numbers.append(0.8)
    if r["mode"] == "assumption":
        tail += " if your assumed sensitivity is right"
    elif r["evidence"]["state"] == "observational":
        tail += ", but the price history was not a controlled test, so treat this as a scenario"
    return need + tail + ".", s.numbers


def _grid_headline(r):
    s = Say()
    name = r["product"]["name"]
    if r["mode"] == "withheld":
        return f"{name} has no usable price history, so Pi shows break-even volumes for each price but no demand forecast.", s.numbers
    if r["best_price_paise"] is None:
        return f"No candidate price other than today's {s.inr(r['product']['price_paise'])} is allowed.", s.numbers
    best = next(c for c in r["candidates"] if c["price_paise"] == r["best_price_paise"])
    f = best["forecast"]
    verdict = {"likely_improves": "likely improves contribution", "likely_reduces": "all alternatives look worse than keeping the price",
               "trial_recommended": "a trial is recommended"}.get(r["decision"]["id"], r["decision"]["label"].lower())
    return (f"Best supported alternative for {name}: {s.inr(r['best_price_paise'])}, expected contribution change "
            f"{s.inr(f['delta_contribution_paise'])} over {s.lit(r['horizon'])} days; {verdict}."), s.numbers

def _receipt(r):
    if r["kind"] == "reprice":
        out = dict(
            proposed_price_paise=r["proposed_price_paise"], current_price_paise=r["product"]["price_paise"],
            unit_cost_paise=r["product"]["cost_paise"], horizon_days=r["horizon"], breakeven=r["breakeven"],
            baseline=r["baseline"], forecast=r["forecast"], evidence_state=r["evidence"]["state"], mode=r["mode"],
            decision=r["decision"]["id"],
            display=dict(headline=r["headline"], numbers=r["numbers"], product_name=r["product"]["name"]),
        )
    else:
        out = dict(horizon_days=r["horizon"], current_price_paise=r["product"]["price_paise"], mode=r["mode"],
                   decision=r["decision"]["id"], best_price_paise=r["best_price_paise"],
                   candidates=[dict(price_paise=c["price_paise"], breakeven=c["breakeven"], forecast=c["forecast"],
                                    decision=c["decision"]["id"]) for c in r["candidates"]],
                   display=dict(headline=r["headline"], numbers=r["numbers"], product_name=r["product"]["name"]))
    return receipt(
        dict(merchant=r["merchant"], dataset=r["dataset"], product=r["product"]["id"], data_cutoff=r["data_cutoff"],
             model_version=r["model_version"], evidence=dict(
                 state=r["evidence"]["state"], levels=r["evidence"]["distinct_price_levels"],
                 episodes=r["evidence"]["price_change_episodes"], range_paise=r["evidence"]["price_range_paise"],
                 support=r["evidence"]["support"], stockout_share=r["evidence"]["stockout_share"]),
             model=r["model"], stock=r["stock"]["description"]),
        "Gross contribution = units x (price - landed unit cost - other variable cost). Break-even units = baseline contribution "
        "/ new unit margin, rounded up to the next whole unit. Forecast units = E[min(demand, stock)] over simulated paths, with "
        "demand ~ NegBin(baseline x (p/p_now)^(-eta)). Contribution change = scenario contribution - baseline contribution, paired path by path.",
        out,
        [
            "Gross contribution is revenue minus landed item cost and any other variable cost you entered. It is not net profit.",
            "The new price applies to every unit sold, including units that would have sold at the old price.",
            "Both prices use the same opening stock and replenishment, so existing stock is not charged twice.",
            r["scope"],
            "Intervals: 'outcomes' describe where one future could land (random demand plus parameter uncertainty); "
            "'mean' intervals describe uncertainty about the average only.",
            "Thresholds in the decision labels are product choices, not statistical guarantees.",
        ] + ([r["assumption"]["label"]] if r.get("assumption") else []),
        [dict(step="evidence", detail=r["evidence"]["explanation"])],
    ) | {"data_quality_flags": ["SIMULATED_DATA", *r["evidence"]["flags"]]}


def save(mid, dataset, product, kind, payload):
    """Stores a scenario or experiment plan locally. It never reaches a POS."""
    if kind not in ("scenario", "experiment_plan"):
        raise ValueError("Unknown kind")
    data.load(mid, product, dataset)  # validates ownership
    return data.save_scenario(mid, dataset, product, kind, json.dumps(payload, default=float), _stamp())
