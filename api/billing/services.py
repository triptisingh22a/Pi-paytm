"""Deterministic tools. Generated explanations bind directly to calculated outputs."""

from collections import Counter
from datetime import timedelta
from functools import lru_cache
import numpy as np
from scipy.stats import gamma
from billing.catalogue import resolve
from billing.generate import AS_OF
from billing.store import connection, merchant

PERIODS = {"day": 1, "week": 7, "month": 30}


def receipt(inputs, formula, output, assumptions=None, steps=None):
    return dict(
        inputs=inputs,
        formula_text=formula,
        output=output,
        steps=steps or [],
        assumptions=assumptions or [],
        data_tier="B",
        data_quality_flags=["SIMULATED_DATA", "POS_BILLS_NOT_VISITOR_COUNTS"],
    )


def overview(mid, period="day"):
    if period not in PERIODS:
        raise ValueError("Choose day, week or month")
    days = PERIODS[period]
    start = str(AS_OF - timedelta(days=days - 1))
    end = str(AS_OF)
    with connection() as db:
        shop = merchant(mid, db)
        bills = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM bills WHERE merchant=? AND timestamp>=? AND timestamp<? ORDER BY timestamp",
                (mid, start, str(AS_OF + timedelta(days=1))),
            )
        ]
        totals = db.execute(
            "SELECT SUM(l.qty*l.price),SUM(l.qty*l.cost),SUM(l.qty) FROM lines l JOIN bills b ON b.id=l.bill WHERE b.merchant=? AND b.timestamp>=? AND b.timestamp<?",
            (mid, start, str(AS_OF + timedelta(days=1))),
        ).fetchone()
        revenue = float(totals[0] or 0)
        cost = float(totals[1] or 0)
        inventory = []
        for p in shop["products"]:
            current = db.execute(
                "SELECT closing FROM daily WHERE merchant=? AND product=? ORDER BY day DESC LIMIT 1",
                (mid, p["id"]),
            ).fetchone()[0]
            extra = db.execute(
                "SELECT COALESCE(SUM(qty),0) FROM stock_events WHERE merchant=? AND product=? AND source='confirmed demo import'",
                (mid, p["id"]),
            ).fetchone()[0]
            stats = db.execute(
                "SELECT SUM(units),SUM(revenue),SUM(exposure) FROM daily WHERE merchant=? AND product=? AND day>=?",
                (mid, p["id"], start),
            ).fetchone()
            recent = db.execute(
                "SELECT SUM(units),SUM(exposure) FROM daily WHERE merchant=? AND product=? AND day>=?",
                (mid, p["id"], str(AS_OF - timedelta(days=6))),
            ).fetchone()
            prior = db.execute(
                "SELECT SUM(units),SUM(exposure) FROM daily WHERE merchant=? AND product=? AND day>=? AND day<?",
                (mid, p["id"], str(AS_OF - timedelta(days=13)), str(AS_OF - timedelta(days=6))),
            ).fetchone()
            rate = float(recent[0] or 0) / max(float(recent[1] or 0), 1)
            prev = float(prior[0] or 0) / max(float(prior[1] or 0), 1)
            change = (rate / prev - 1) * 100 if prev else None
            cover = (current + extra) / (float(recent[0] or 0) / 7) if recent[0] else None
            health = (
                "not stocked"
                if p["candidate"] and current + extra == 0
                else "no recorded sales"
                if stats[0] == 0 and stats[2] > 0
                else "restock soon"
                if cover is not None and cover < 7
                else "slow moving"
                if change is not None and change < -25
                else "healthy"
            )
            inventory.append(
                {
                    **p,
                    "on_hand": current + extra,
                    "units": stats[0] or 0,
                    "revenue": stats[1] or 0,
                    "exposure": stats[2] or 0,
                    "days_cover": round(cover, 1) if cover is not None else None,
                    "rate_change_pct": round(change, 1) if change is not None else None,
                    "health": health,
                    "revenue_share": round(100 * (stats[1] or 0) / max(revenue, 1), 1),
                }
            )
        profiles = Counter(b["profile"] for b in bills)
        known = [b for b in bills if b["customer"]]
        previous = {
            r[0]
            for r in db.execute(
                "SELECT DISTINCT customer FROM bills WHERE merchant=? AND timestamp<? AND customer IS NOT NULL",
                (mid, start),
            )
        }
        returning = sum(1 for b in known if b["customer"] in previous)
        chart = []
        if period == "day":
            for hour in range(10, 22):
                value = db.execute(
                    "SELECT COALESCE(SUM(l.qty*l.price),0) FROM lines l JOIN bills b ON b.id=l.bill WHERE b.merchant=? AND substr(b.timestamp,1,10)=? AND substr(b.timestamp,12,2)=?",
                    (mid, end, f"{hour:02}"),
                ).fetchone()[0]
                chart.append({"label": f"{hour}:00", "revenue": value})
        else:
            for n in range(days):
                day = AS_OF - timedelta(days=days - 1 - n)
                value = (
                    db.execute(
                        "SELECT SUM(revenue) FROM daily WHERE merchant=? AND day=?", (mid, str(day))
                    ).fetchone()[0]
                    or 0
                )
                chart.append({"label": day.strftime("%d %b"), "revenue": value})
        top_units = sorted([p for p in inventory if p["units"]], key=lambda p: p["units"], reverse=True)[:3]
        top_revenue = sorted(
            [p for p in inventory if p["revenue"]], key=lambda p: p["revenue"], reverse=True
        )[:3]
        rising = sorted(
            [p for p in inventory if p["rate_change_pct"] is not None and p["rate_change_pct"] > 15],
            key=lambda p: p["rate_change_pct"],
            reverse=True,
        )[:2]
        falling = sorted(
            [p for p in inventory if p["rate_change_pct"] is not None and p["rate_change_pct"] < -15],
            key=lambda p: p["rate_change_pct"],
        )[:2]
        dead = [p for p in inventory if p["units"] == 0 and p["exposure"] > 0]
        result = dict(
            merchant=shop["id"],
            name=shop["name"],
            kind=shop["kind"],
            period=period,
            start=start,
            end=end,
            revenue=revenue,
            contribution=revenue - cost,
            bills=len(bills),
            units=int(totals[2] or 0),
            ticket=round(revenue / max(len(bills), 1), 2),
            known_bills=len(known),
            returning_bills=returning,
            anonymous_bills=len(bills) - len(known),
            customer_profiles=[
                {"profile": k, "bills": v, "share": round(v / max(len(bills), 1) * 100, 1)}
                for k, v in profiles.most_common()
            ],
            inventory=inventory,
            chart=chart,
            top_units=top_units,
            top_revenue=top_revenue,
            rising=rising,
            falling=falling,
            dead=dead,
            nudges=[
                dict(
                    product=p["id"],
                    name=p["name"],
                    reason=p["health"],
                    on_hand=p["on_hand"],
                    days_cover=p["days_cover"],
                )
                for p in inventory
                if p["health"] in ("restock soon", "slow moving", "no recorded sales")
            ],
            ingredients=shop["ingredients"],
            simulated=True,
        )
        compact = {k: v for k, v in result.items() if k not in ("inventory", "ingredients", "chart")}
        compact.update(
            top_units=[{"name": p["name"], "units": p["units"]} for p in top_units],
            top_revenue=[{"name": p["name"], "revenue": p["revenue"]} for p in top_revenue],
            rising=[{"name": p["name"], "rate_change_pct": p["rate_change_pct"]} for p in rising],
            falling=[{"name": p["name"], "rate_change_pct": p["rate_change_pct"]} for p in falling],
            dead=[p["name"] for p in dead],
        )
        result["receipt"] = receipt(
            {
                "merchant": mid,
                "window": [start, end],
                "bill_count": len(bills),
                "source": "billing.sqlite3: bills + lines + daily availability",
            },
            "Revenue = Σ(quantity × realized unit price); contribution = revenue − supplied landed ingredient/item costs; rate = units / available bill opportunities",
            compact,
            [
                "Customer profiles describe purchased basket categories, not age, gender, income or all visitors.",
                "Returning bills use recorded synthetic loyalty IDs seen before this window; anonymous bills are not classified.",
                "Trends compare the latest 7 days with the previous 7 using availability-adjusted rates, independently of overview period.",
                "Contribution excludes rent, wages, overhead and tax; it is not net profit. Availability is a synthetic per-bill log.",
                "Dead segments means zero recorded units during this window while available, not proven zero demand.",
            ],
        )
        return result


@lru_cache(maxsize=128)
def peers(mid, product, exclude=None, cutoff=str(AS_OF)):
    cutoff_date = AS_OF.fromisoformat(cutoff)
    # Only fully completed weekly bins enter peer inference, including future-holdout evaluations.
    since = str(cutoff_date - timedelta(days=91))
    through = str(cutoff_date - timedelta(days=6))
    with connection() as db:
        shop = merchant(mid, db)
        p = resolve(product, mid)
        if not p:
            raise ValueError("Product needs an exact canonical SKU/alias match")
        ids = [x["id"] for x in shop["products"] if not x["candidate"] and x["id"] not in (p["id"], exclude)]
        families = sorted({x["family"] for x in shop["products"]})
        family_by_id = {x["id"]: x["family"] for x in shop["products"]}
        target = {
            r["product"]: dict(r)
            for r in db.execute(
                "SELECT product,SUM(units) units,SUM(exposure) exposure FROM daily WHERE merchant=? AND day>=? AND day<=? GROUP BY product",
                (mid, since, cutoff),
            )
        }
        target_mix = np.array(
            [sum(target[i]["units"] for i in ids if family_by_id[i] == f) for f in families], dtype=float
        )
        target_mix /= max(target_mix.sum(), 1)
        rows = db.execute(
            "SELECT peer,product,SUM(units) units,SUM(exposure) exposure,AVG(ticket) ticket FROM peer_weeks WHERE kind=? AND week>=? AND week<=? GROUP BY peer,product",
            (mid, since, through),
        ).fetchall()
        donors = {}
        for row in rows:
            donors.setdefault(row["peer"], {})[row["product"]] = dict(row)
        candidates = []
        for donor, data in donors.items():
            evidence = data.get(p["id"], {})
            if evidence.get("exposure", 0) < 200:
                continue
            mix = np.array(
                [sum(data[i]["units"] for i in ids if i in data and family_by_id[i] == f) for f in families],
                dtype=float,
            )
            mix /= max(mix.sum(), 1)
            # Category-weighted exact rerank. Candidate/Y outcomes do not enter similarity.
            distance = float(
                np.linalg.norm(mix - target_mix)
                + abs(mix[families.index(p["family"])] - target_mix[families.index(p["family"])])
            )
            candidates.append(
                {"distance": distance, "units": evidence["units"], "exposure": evidence["exposure"]}
            )
        candidates.sort(key=lambda x: x["distance"])
        selected = candidates[:30]
        if len(selected) < 10:
            return {
                "verdict": "INSUFFICIENT_DATA",
                "reason": "Fewer than 10 eligible same-type donors with known availability",
                "peer_count": len(selected),
                "product": p["id"],
            }
        weights = np.exp(-np.array([d["distance"] for d in selected]) * 8)
        weights /= weights.sum()
        effective = float(1 / (weights @ weights))
        weighted_units = float(sum(w * d["units"] for w, d in zip(weights, selected)))
        weighted_exposure = float(sum(w * d["exposure"] for w, d in zip(weights, selected)))
        rate = weighted_units / weighted_exposure
        prior_strength = min(500.0, weighted_exposure)
        local_row = db.execute(
            "SELECT SUM(units),SUM(exposure) FROM daily WHERE merchant=? AND product=? AND day>=? AND day<=?",
            (mid, p["id"], str(cutoff_date - timedelta(days=27)), cutoff),
        ).fetchone()
        local = {"units": int(local_row[0] or 0), "exposure": int(local_row[1] or 0)}
        alpha = 0.5 + rate * prior_strength + local["units"]
        beta = 1 + prior_strength + local["exposure"]
        result = dict(
            verdict="SUPPORTED",
            product=p["id"],
            name=p["name"],
            family=p["family"],
            peer_count=len(selected),
            eligible_count=len(candidates),
            effective_peers=round(effective, 2),
            mapping_confidence=p["mapping_confidence"],
            peer_rate_per_100_bills=round(rate * 100, 3),
            rate=alpha / beta,
            rate_p10=float(gamma.ppf(0.1, alpha, scale=1 / beta)),
            rate_p90=float(gamma.ppf(0.9, alpha, scale=1 / beta)),
            alpha=alpha,
            beta=beta,
            local_units=local["units"],
            local_exposure=local["exposure"],
            weighted_units=round(weighted_units, 2),
            weighted_exposure=round(weighted_exposure, 2),
            prior_strength=prior_strength,
            window=[since, cutoff],
            similarity_features=[
                "same business type",
                "non-candidate category mix",
                "replacement category weighting",
            ],
            anonymized=True,
        )
        result["receipt"] = receipt(
            {
                "merchant": mid,
                "product": p["id"],
                "excluded_from_similarity": [p["id"], exclude],
                "window": [since, cutoff],
                "completed_peer_week_start_at_most": through,
            },
            "w ∝ exp(−8d); ESS=1/Σw²; α=0.5 + capped prior exposure × weighted peer rate + local units; β=1 + capped prior exposure + local availability exposure",
            {k: v for k, v in result.items() if k != "receipt"},
            [
                "Same-type, known-exposure donors only; missing offer exposure is not a zero sale. Cohorts below 10 abstain.",
                "Exact nearest-neighbour reranking of this small demo cohort; production retrieval should use a category ANN index before reranking.",
                "Canonical identity uses curated exact IDs and pack/variant-preserving aliases. Family membership only proposes substitutes.",
                "Gamma–Poisson predictive shrinkage is a conditional transfer assumption, not causal demand identification.",
            ],
        )
        return result


def replacement(mid, remove, replace, quantity=50, horizon=7, budget=10000.0, paths=1024, outside=1.0):
    if not (1 <= horizon <= 30 and 1 <= quantity <= 500 and budget >= 0 and 0.25 <= outside <= 4):
        raise ValueError("Invalid horizon, stock quantity, budget or outside-option factor")
    d = overview(mid, "month")
    products = d["inventory"]
    y = resolve(remove, mid)
    x = resolve(replace, mid)
    if not x or not y or x["id"] == y["id"]:
        raise ValueError("Choose two distinct canonical products")
    if x["family"] != y["family"]:
        raise ValueError(
            "Replacement must be in the same substitute family; cross-category utility is not identified"
        )
    supported = peers(mid, x["id"], y["id"])
    if supported["verdict"] != "SUPPORTED":
        return supported
    family = [p for p in products if p["family"] == y["family"] and not p["candidate"]]
    if y["id"] not in [p["id"] for p in family]:
        raise ValueError("Remove an existing stocked assortment item")
    if x["id"] in [p["id"] for p in family]:
        raise ValueError("Introduce a not-yet-offered candidate")
    purchase_cost = quantity * x["cost"]
    if purchase_cost > budget:
        raise ValueError(f"Supplied cost requires ₹{purchase_cost:,.0f}; budget is ₹{budget:,.0f}")
    if mid == "restaurant":
        missing = [ingredient for ingredient in x["recipe"] if ingredient not in d["ingredients"]]
        if missing:
            raise ValueError("Recipe ingredient availability is missing")
    # Conditional on a fixed schedule of completed-bill opportunities, not inferred visitor arrivals.
    opportunities = max(1, round(d["bills"] / 30 * horizon))
    rng = np.random.default_rng(92341)
    rates = {p["id"]: peers(mid, p["id"], y["id"]) for p in family}
    choices = family + [dict(x, on_hand=quantity)]
    count = len(choices)
    utilities = np.zeros((paths, count))
    for j, p in enumerate(choices):
        info = supported if p["id"] == x["id"] else rates[p["id"]]
        if info["verdict"] != "SUPPORTED":
            return info
        utilities[:, j] = rng.gamma(info["alpha"], 1 / info["beta"], size=paths)
    # The rate calibration gives current-family share, with a documented cap for multi-item bills.
    baseline_share = np.clip(utilities[:, :-1].sum(axis=1), 0.01, 0.8)
    utilities = utilities / np.maximum(1 - baseline_share[:, None], 0.2)
    caps0 = np.array([p["on_hand"] for p in choices], dtype=int)
    caps0[-1] = 0
    caps1 = caps0.copy()
    yi = next(j for j, p in enumerate(choices) if p["id"] == y["id"])
    caps1[yi] = 0
    caps1[-1] = quantity
    prices = np.array([p["price"] for p in choices])
    costs = np.array([p["cost"] for p in choices])
    opening_ingredients = d["ingredients"]
    ingredient_names = list(opening_ingredients)
    recipe = np.array(
        [[p.get("recipe", {}).get(i, 0) for i in ingredient_names] for p in choices], dtype=float
    )

    def run(outside_weight, collect=False):
        stocks = [np.tile(caps, (paths, 1)) for caps in (caps0, caps1)]
        sold = [np.zeros((paths, count), dtype=int), np.zeros((paths, count), dtype=int)]
        ingredient_stocks = [
            np.tile(list(opening_ingredients.values()), (paths, 1)).astype(float) for _ in range(2)
        ]
        daily = []
        # Identical fixed draws within every scenario and sensitivity run.
        random = np.random.default_rng(8421).random((opportunities, paths))
        boundaries = {int(np.ceil(day * opportunities / horizon)): day for day in range(1, horizon + 1)}
        for n in range(opportunities):
            for branch in range(2):
                available = stocks[branch] > 0
                if ingredient_names:
                    recipe_ok = (ingredient_stocks[branch][:, None, :] + 1e-9 >= recipe[None, :, :]).all(
                        axis=2
                    )
                    available &= recipe_ok
                u = utilities * available
                probabilities = u / (outside_weight + u.sum(axis=1))[:, None]
                cumulative = np.cumsum(probabilities, axis=1)
                chosen = (random[n, :, None] > cumulative).sum(axis=1)
                bought = chosen < count
                rows = np.flatnonzero(bought)
                columns = chosen[bought]
                stocks[branch][rows, columns] -= 1
                sold[branch][rows, columns] += 1
                if ingredient_names:
                    ingredient_stocks[branch][rows] -= recipe[columns]
            if collect and n + 1 in boundaries:
                daily.append(
                    {
                        "day": boundaries[n + 1],
                        "baseline": round(float((sold[0] @ prices).mean()), 2),
                        "scenario": round(float((sold[1] @ prices).mean()), 2),
                    }
                )
        if collect and len(daily) < horizon:
            daily.append(
                {
                    "day": horizon,
                    "baseline": round(float((sold[0] @ prices).mean()), 2),
                    "scenario": round(float((sold[1] @ prices).mean()), 2),
                }
            )
        return sold, daily, ingredient_stocks

    sold, chart, remaining = run(outside, True)
    base_revenue = sold[0] @ prices
    action_revenue = sold[1] @ prices
    delta = action_revenue - base_revenue
    margin_delta = (sold[1] - sold[0]) @ (prices - costs)
    candidate_sold = sold[1][:, -1]
    sensitivity = []
    for factor in (0.5, 1.0, 2.0):
        s, _, _ = run(factor)
        sensitivity.append(
            {
                "outside_factor": factor,
                "incremental_revenue": round(float(((s[1] - s[0]) @ prices).mean()), 2),
            }
        )
    remaining_value = (quantity - candidate_sold) * x["cost"]
    result = dict(
        verdict="SCENARIO",
        remove=y["name"],
        replace=x["name"],
        remove_id=y["id"],
        replace_id=x["id"],
        family=x["family"],
        horizon=horizon,
        quantity=quantity,
        budget=budget,
        purchase_cost=purchase_cost,
        opportunities=opportunities,
        paths=paths,
        baseline_revenue=round(float(base_revenue.mean()), 2),
        scenario_revenue=round(float(action_revenue.mean()), 2),
        incremental_revenue=round(float(delta.mean()), 2),
        p10=round(float(np.quantile(delta, 0.1)), 2),
        p50=round(float(np.quantile(delta, 0.5)), 2),
        p90=round(float(np.quantile(delta, 0.9)), 2),
        incremental_contribution=round(float(margin_delta.mean()), 2),
        probability_revenue_loss=round(float((delta < 0).mean()), 4),
        candidate_units=round(float(candidate_sold.mean()), 2),
        unsold_candidate_value=round(float(remaining_value.mean()), 2),
        # Upfront purchases are cash; costs of units sold define contribution, so do not subtract both.
        incremental_cash_after_purchase=round(float(delta.mean() - purchase_cost), 2),
        peer_count=supported["peer_count"],
        effective_peers=supported["effective_peers"],
        mapping_confidence=x["mapping_confidence"],
        chart=chart,
        sensitivity=sensitivity,
        products=[
            {
                "name": p["name"],
                "baseline_units": round(float(sold[0][:, j].mean()), 2),
                "scenario_units": round(float(sold[1][:, j].mean()), 2),
                "revenue_delta": round(float(((sold[1][:, j] - sold[0][:, j]) * p["price"]).mean()), 2),
            }
            for j, p in enumerate(choices)
        ],
        ingredient_remaining=[
            {
                "ingredient": i,
                "baseline_kg": round(float(remaining[0][:, j].mean()), 3),
                "scenario_kg": round(float(remaining[1][:, j].mean()), 3),
            }
            for j, i in enumerate(ingredient_names)
        ],
        peer_evidence=supported,
        simulated=True,
    )
    result["receipt"] = receipt(
        {
            "merchant": mid,
            "remove": y["id"],
            "replace": x["id"],
            "supplied_unit_price": x["price"],
            "supplied_unit_cost": x["cost"],
            "stock_caps_baseline": caps0.tolist(),
            "stock_caps_scenario": caps1.tolist(),
            "fixed_bill_opportunities": opportunities,
            "quantity": quantity,
            "budget": budget,
            "horizon": horizon,
            "outside_factor": outside,
            "seed": 92341,
            "draw_seed": 8421,
            "paths": paths,
            "ingredients_kg": opening_ingredients,
            "recipes_kg": {p["name"]: p["recipe"] for p in choices},
        },
        "P(i | available) = u_i / (outside_weight + Σ available u_j); paired draws → stock/BOM decrement → revenue = Σ units × price; delta = scenario − baseline; contribution delta = Σ delta units × (price − cost)",
        {k: v for k, v in result.items() if k not in ("receipt", "peer_evidence")},
        [
            "Conditional 7/30-day bill schedule is fixed across branches; it is not an estimate of all visitors. Only this substitute family is modeled; other categories cancel.",
            "Peer-informed demand with Gamma–Poisson uncertainty. Outside option, IIA and no replenishment during this trial are assumptions; sensitivity is not a confidence interval.",
            "Stockouts remove products from the choice set. Restaurant choices also consume shared recipe ingredients; quantities/costs are supplied synthetic inputs, never inferred from peers.",
            "Existing Y stock is set aside, with no resale, salvage or disposal claim. Purchase cash is paid once; unsold X remains inventory and has no assumed terminal sale.",
            "P10–P90 describe this model and seed, not calibrated causal uplift. Validate with a small randomized assortment trial. Expiry, staffing, shelf volume and promotion effects are outside this narrow trial.",
        ],
    )
    return result


def recommend(mid, remove, quantity=50, budget=10000, horizon=7):
    y = resolve(remove, mid)
    if not y:
        raise ValueError("Identify the product to remove")
    d = overview(mid, "day")
    rows = []
    for x in d["inventory"]:
        if x["candidate"] and x["family"] == y["family"] and x["cost"] * quantity <= budget:
            rows.append(replacement(mid, y["id"], x["id"], quantity, horizon, budget))
    rows = [r for r in rows if r["verdict"] == "SCENARIO"]
    rows.sort(key=lambda r: r["p10"], reverse=True)
    return dict(
        verdict="RANKED" if rows else "INSUFFICIENT_DATA",
        objective="highest P10 incremental revenue among eligible candidates",
        candidates=rows,
        reason=None if rows else "No supported same-family candidates within budget",
    )
