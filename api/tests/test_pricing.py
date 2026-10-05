"""Repricing: arithmetic, evidence gating, stock-constrained simulation, API and agent contracts."""

import json
import sqlite3
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app
from ai import sarvam_chat, sarvam_voice
from billing import store
from billing.agent import ask
from billing.generate import generate
from pricing import data, pilot, service, simulate
from pricing.breakeven import breakeven
from pricing.evidence import assess
from pricing.money import to_paise

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]
REAL_FILES = [ROOT / "data" / n for n in ("billing.sqlite3", "pricing_pilot.sqlite3", "pricing_state.sqlite3")]
TRUTH = {}


@pytest.fixture(scope="module", autouse=True)
def isolated_world(tmp_path_factory):
    """Temporary billing, pilot and state databases, so no test can touch the live merchant data."""
    before = {p: p.stat().st_mtime_ns for p in REAL_FILES if p.exists()}
    base = tmp_path_factory.mktemp("pricing")
    billing = base / "billing.sqlite3"
    generate(billing)
    truth_path = base / "truth.json"
    pilot.generate(base / "pilot.sqlite3", truth_path)
    TRUTH.update(json.loads(truth_path.read_text(encoding="utf-8")))
    mp = pytest.MonkeyPatch()
    mp.setattr(store, "PATH", billing)
    mp.setattr(data, "PILOT_PATH", base / "pilot.sqlite3")
    mp.setattr(data, "STATE_PATH", base / "state.sqlite3")
    service._pooled_prior.cache_clear()
    yield base
    mp.undo()
    service._pooled_prior.cache_clear()
    after = {p: p.stat().st_mtime_ns for p in REAL_FILES if p.exists()}
    assert before == after, "a test modified real merchant data"


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setenv("SARVAM_CHAT_ENABLED", "false")
    monkeypatch.setenv("SARVAM_VOICE_ENABLED", "false")


# ---- break-even arithmetic --------------------------------------------------------------------------------------------

def test_breakeven_worked_example_100_120_130_115():
    b = breakeven(12000, 11500, 10000, 130)
    assert b["baseline_contribution_paise"] == 260000  # INR 2,600
    assert b["new_margin_paise"] == 1500
    assert b["required_units_exact"] == pytest.approx(173.3333333)
    assert b["required_uplift_exact"] == pytest.approx(1 / 3)
    assert b["required_units"] == 174
    assert b["required_uplift"] == pytest.approx(174 / 130 - 1)  # about 33.85%
    assert b["contribution_at_required_units_paise"] > b["baseline_contribution_paise"]
    assert 173 * 1500 < b["baseline_contribution_paise"]  # 173 units are not enough


def test_exact_tie_needs_one_more_unit():
    b = breakeven(12000, 11000, 10000, 100)  # 200,000 / 1,000 = exactly 200
    assert b["required_units_exact"] == 200 and b["required_units"] == 201


def test_new_price_applies_to_every_unit_and_revenue_is_not_contribution():
    b = breakeven(12000, 11500, 10000, 130)
    units = 160  # more revenue than before, still less contribution
    assert units * 11500 > 130 * 12000 and units * b["new_margin_paise"] < b["baseline_contribution_paise"]
    assert b["revenue_at_required_units_paise"] == 174 * 11500  # all units repriced, not only the extra 44


@pytest.mark.parametrize("new_price", [10000, 9000, 0])
def test_zero_or_negative_margin_has_no_breakeven(new_price):
    b = breakeven(12000, new_price, 10000, 130)
    assert b["status"] == "no_breakeven" and b["required_units"] is None and b["required_uplift"] is None


def test_variable_costs_reduce_margin():
    b = breakeven(12000, 11500, 10000, 130, extra_cost=500)
    assert b["current_margin_paise"] == 1500 and b["new_margin_paise"] == 1000
    assert b["required_units"] == 196  # 130 x 1500 / 1000 = 195, so 196 to beat it


def test_non_positive_baseline_and_bad_input():
    assert breakeven(10000, 11000, 10000, 130)["status"] == "baseline_not_positive"
    with pytest.raises(ValueError):
        breakeven(12000, 11500, 10000, -1)


@pytest.mark.parametrize("bad", [-1, "abc", float("nan"), float("inf"), 115.123, True, None, 10**9])
def test_money_rejects_bad_values(bad):
    with pytest.raises(ValueError):
        to_paise(bad)


def test_money_is_exact_paise():
    assert to_paise(115) == 11500 and to_paise("115.10") == 11510 and to_paise(0.29) == 29


# ---- evidence ------------------------------------------------------------------------------------------------------------

def test_live_history_has_one_price_level_so_evidence_is_insufficient():
    e = assess(data.load("hypermarket", "hypermarket-01"), 50000)
    assert e["state"] == "insufficient" and e["distinct_price_levels"] == 1 and e["price_change_episodes"] == 0
    assert e["support"]["kind"] == "extrapolation"


def test_zero_sale_days_are_kept_when_stock_was_available():
    s = data.load("hypermarket", "hypermarket-09")  # no recorded sales recently
    zero = [r for r in s.rows if r["available"] and r["units"] == 0]
    assert len(zero) > 20 and len(s.rows) == 365


def test_pilot_evidence_states():
    got = {p["id"]: assess(data.load("hypermarket", p["id"], "pilot"))["state"] for p in data.list_products("hypermarket", "pilot")}
    assert got == {"pilot-01": "synthetic_experiment", "pilot-02": "synthetic_experiment", "pilot-03": "synthetic_experiment",
                   "pilot-04": "observational", "pilot-05": "insufficient", "pilot-06": "synthetic_experiment"}


def test_support_interpolation_versus_extrapolation():
    s = data.load("hypermarket", "pilot-02", "pilot")
    assert assess(s, 14000)["support"] == dict(kind="interpolation", outside_by_fraction=0.0)
    far = assess(s, 20000)["support"]
    assert far["kind"] == "extrapolation" and far["outside_by_fraction"] == pytest.approx((20000 - 16000) / 16000, rel=1e-3)


def test_randomized_blocks_counted_not_days():
    e = assess(data.load("hypermarket", "pilot-02", "pilot"))
    assert e["randomized_blocks"] <= 22 < e["observation_days"]


# ---- scenarios -----------------------------------------------------------------------------------------------------------

def test_no_price_variation_withholds_forecast_but_gives_break_even():
    r = service.reprice("hypermarket", "hypermarket-01", 500, 7)
    assert r["mode"] == "withheld" and r["forecast"] is None and r["model"] is None
    assert r["breakeven"]["required_units"] and r["decision"]["id"] == "insufficient_evidence"
    assert "cannot yet estimate" in r["headline"] and "Our estimate" not in r["headline"]
    assert r["experiment_plan"]["status"] == "plan_only_not_executed"


def test_merchant_supplied_baseline_reproduces_the_worked_example():
    r = service.reprice("hypermarket", "hypermarket-01", 500, 7, baseline_units=130)
    assert r["baseline"]["source"] == "merchant_supplied" and r["breakeven"]["baseline_units"] == 130


def test_assumed_sensitivity_is_labelled_and_never_learned():
    r = service.reprice("hypermarket", "hypermarket-01", 500, 7, assumed_eta=2.0)
    assert r["mode"] == "assumption" and r["model"] is None and "assumption-based" in r["assumption"]["label"]
    assert r["decision"]["id"] == "insufficient_evidence"  # an assumption is not evidence
    assert "if your assumed sensitivity is right" in r["headline"]
    with pytest.raises(ValueError):
        service.reprice("hypermarket", "hypermarket-01", 500, 7, assumed_eta=50)


def test_sales_up_contribution_down_case():
    r = service.reprice("hypermarket", "pilot-01", 38, 7, "pilot")
    f = r["forecast"]
    assert f["expected_units"] > f["baseline_units"] and f["delta_contribution_paise"] < 0
    assert r["decision"]["id"] == "likely_reduces" and f["probability_lower"] > 0.9


def test_price_cut_that_pays_for_itself():
    r = service.reprice("hypermarket", "pilot-02", 140, 7, "pilot")
    assert r["forecast"]["delta_contribution_paise"] > 0 and r["forecast"]["probability_higher"] > 0.8
    assert r["forecast"]["expected_units"] >= r["breakeven"]["required_units"] - 5
    assert r["decision"]["id"] in ("likely_improves", "trial_recommended")


def test_stock_prevents_required_volume():
    r = service.reprice("hypermarket", "pilot-03", 155, 7, "pilot")
    assert r["stock"]["required_units_reachable"] is False and "Stock is the limit" in r["headline"]
    assert r["forecast"]["expected_units_lost_to_stock"] > 0 and r["forecast"]["stockout_probability"] > 0.5


def test_expected_min_is_not_min_of_expected():
    s = data.load("hypermarket", "pilot-03", "pilot")
    fitted = service._fit_if_supported(s, assess(s), "hypermarket", "pilot")
    days = service._days(s, 7)
    probe = simulate.run(fitted, days, [s.price], s.cost, 0, 10_000, [], None)[s.price]
    stock = int(probe["demand"].mean())  # stock equal to average demand: about half of futures run short
    sim = simulate.run(fitted, days, [s.price], s.cost, 0, stock, [], None)[s.price]
    assert sim["units"].mean() < min(sim["demand"].mean(), stock) - 5  # E[min(D, S)] < min(E[D], S)
    assert (sim["units"] <= stock + 1e-9).all() and (sim["remaining"] >= 0).all()


def test_timed_replenishment_extends_supply_in_every_scenario():
    s = data.load("hypermarket", "pilot-02", "pilot")
    fitted = service._fit_if_supported(s, assess(s), "hypermarket", "pilot")
    days = service._days(s, 7)
    none = simulate.run(fitted, days, [14000, 15000], s.cost, 0, 20, [], None)
    late = simulate.run(fitted, days, [14000, 15000], s.cost, 0, 20, [(3, 400)], None)
    for p in (14000, 15000):
        assert late[p]["units"].mean() > none[p]["units"].mean() + 20
    # before the delivery arrives nothing more than the opening stock can be sold
    early = simulate.run(fitted, days[:3], [15000], s.cost, 0, 20, [(5, 400)], None)[15000]
    assert early["units"].max() <= 20


def test_simulation_is_reproducible_and_paired():
    r1 = service.reprice("hypermarket", "pilot-02", 140, 7, "pilot")["forecast"]
    r2 = service.reprice("hypermarket", "pilot-02", 140, 7, "pilot")["forecast"]
    assert r1 == r2
    s = data.load("hypermarket", "pilot-02", "pilot")
    fitted = service._fit_if_supported(s, assess(s), "hypermarket", "pilot")
    sim = simulate.run(fitted, service._days(s, 7), [s.price, 14000], s.cost, 0, s.on_hand, [], None, seed=1)
    same = simulate.summarise(sim, s.price, s.price)
    assert same["delta_contribution_paise"] == 0 and same["probability_lower"] == 0
    other = simulate.run(fitted, service._days(s, 7), [s.price, 14000], s.cost, 0, s.on_hand, [], None, seed=2)
    assert simulate.summarise(other, s.price, 14000)["delta_contribution_paise"] != simulate.summarise(sim, s.price, 14000)["delta_contribution_paise"]


def test_each_scenario_is_valued_at_its_own_price_and_cost():
    s = data.load("hypermarket", "pilot-02", "pilot")
    fitted = service._fit_if_supported(s, assess(s), "hypermarket", "pilot")
    sim = simulate.run(fitted, service._days(s, 7), [13500, 15000], s.cost, 300, s.on_hand, [], None)
    for p in (13500, 15000):
        assert np.allclose(sim[p]["revenue"], sim[p]["units"] * p)
        assert np.allclose(sim[p]["contribution"], sim[p]["units"] * (p - s.cost - 300))


def test_interval_kinds_are_distinct():
    f = service.reprice("hypermarket", "pilot-02", 140, 7, "pilot")["forecast"]
    lo, hi = f["units_outcome_interval"]
    mlo, mhi = f["units_mean_interval"]
    assert (hi - lo) > (mhi - mlo) > 0  # where one future lands is wider than where the average sits


def test_extrapolated_price_never_gets_a_confident_label():
    r = service.reprice("hypermarket", "pilot-02", 200, 7, "pilot")
    assert r["evidence"]["support"]["kind"] == "extrapolation" and r["decision"]["id"] == "trial_recommended"


def test_confounded_history_never_reaches_a_confident_improvement():
    r = service.reprice("hypermarket", "pilot-04", 240, 7, "pilot")
    assert r["evidence"]["state"] == "observational" and r["decision"]["id"] in ("trial_recommended", "likely_reduces")
    assert "not a controlled test" in r["headline"] and r["model"]["uncertainty_widened_for_confounding"]


def test_sparse_history_is_insufficient():
    r = service.reprice("hypermarket", "pilot-05", 42, 7, "pilot")
    assert r["mode"] == "withheld" and r["forecast"] is None


def test_price_increase_can_raise_contribution_for_insensitive_item():
    r = service.reprice("hypermarket", "pilot-06", 200, 7, "pilot")
    assert r["forecast"]["delta_contribution_paise"] > 0 and r["forecast"]["expected_units"] < r["forecast"]["baseline_units"]


# ---- recommendation grid ---------------------------------------------------------------------------------------------------

def test_grid_includes_current_price_and_drops_unsafe_prices():
    r = service.recommend_price("hypermarket", "hypermarket-01", 7, "live", candidates=[400, 430, 440, 500, 520, 600], max_price=550)
    prices = [c["price_paise"] for c in r["candidates"]]
    assert 52000 in prices and 40000 not in prices and 60000 not in prices
    why = {d["price_paise"]: d["reason"] for d in r["dropped"]}
    assert "margin" in why[40000] and "maximum" in why[60000]
    assert all(c["breakeven"]["required_units"] for c in r["candidates"] if c["breakeven"]["status"] == "ok")
    assert next(c for c in r["candidates"] if c["is_current"])["decision"]["id"] == "current_price"


def test_grid_best_price_is_contribution_not_volume():
    r = service.recommend_price("hypermarket", "pilot-01", 7, "pilot")
    assert r["decision"]["id"] in ("likely_reduces", "trial_recommended")  # cutting the price of an insensitive item loses
    top = max((c for c in r["candidates"] if c["forecast"]), key=lambda c: c["forecast"]["expected_units"])
    best = next(c for c in r["candidates"] if c["price_paise"] == r["best_price_paise"])
    assert top["price_paise"] <= data.load("hypermarket", "pilot-01", "pilot").price  # most units come from the lowest price
    assert best["forecast"]["expected_contribution_paise"] >= top["forecast"]["expected_contribution_paise"]


def test_grid_withheld_when_no_variation():
    r = service.recommend_price("hypermarket", "hypermarket-07", 7, "live")
    assert r["mode"] == "withheld" and r["best_price_paise"] is None and all(c["forecast"] is None for c in r["candidates"])


def test_experiment_plan_only_when_a_decision_is_not_supported():
    weak = service.reprice("hypermarket", "pilot-05", 42, 7, "pilot")["experiment_plan"]
    assert weak["status"] == "plan_only_not_executed" and weak["weeks_per_price"] >= 2 and "randomization_unit" in weak
    assert "after_the_test" in weak and "primary_metric" in weak and weak["candidate_prices_paise"]
    strong = service.reprice("hypermarket", "pilot-02", 140, 7, "pilot")
    if strong["decision"]["id"] == "likely_improves":
        assert strong["experiment_plan"] is None


# ---- hidden truth stays hidden ---------------------------------------------------------------------------------------------

def test_generator_truth_is_not_in_any_model_input():
    db = sqlite3.connect(data.PILOT_PATH)
    columns = {r[1] for t in ("products", "obs", "price_spells", "stock_receipts", "meta") for r in db.execute(f"PRAGMA table_info({t})")}
    db.close()
    assert not columns & {"eta", "elasticity", "alpha", "promo_lift", "base_per_day"}
    for path in (ROOT / "api").rglob("*.py"):
        if "tests" in path.parts or path.name == "pilot.py":
            continue
        assert "pricing_pilot_truth" not in path.read_text(encoding="utf-8"), path


def test_price_sensitivity_is_recovered_for_randomized_items():
    for pid in ("pilot-01", "pilot-02", "pilot-06"):
        s = data.load("hypermarket", pid, "pilot")
        fitted = service._fit_if_supported(s, assess(s), "hypermarket", "pilot")
        truth = TRUTH[pid]["eta"]
        assert abs(fitted["eta"] - truth) < max(1.0, 3 * fitted["eta_se"]), (pid, fitted["eta"], truth)


def test_windows_can_replace_a_pilot_database_after_use(isolated_world):
    path = isolated_world / "replace.sqlite3"
    pilot.generate(path)
    db = sqlite3.connect(path)
    db.execute("SELECT COUNT(*) FROM obs").fetchone()
    db.close()
    path.unlink()  # fails on Windows if any connection were left open
    pilot.generate(path)
    assert path.exists()


# ---- API --------------------------------------------------------------------------------------------------------------------

def post(path, body, mid="hypermarket"):
    return client.post(f"/v2/pricing/{mid}/{path}", json=body)


def test_api_products_and_reprice():
    p = client.get("/v2/pricing/hypermarket/products").json()["products"]
    assert len(p) == 10 and all(x["evidence_state"] == "insufficient" for x in p)
    pilot_rows = client.get("/v2/pricing/hypermarket/products?dataset=pilot").json()["products"]
    assert {x["evidence_state"] for x in pilot_rows} == {"synthetic_experiment", "observational", "insufficient"}
    r = post("reprice", {"product": "pilot-02", "proposed_price": 140, "dataset": "pilot"})
    assert r.status_code == 200 and r.json()["forecast"]["expected_units"] > 0 and r.json()["receipt"]["output"]


@pytest.mark.parametrize(
    "body",
    [
        {"product": "nope-01", "proposed_price": 100},
        {"product": "restaurant-01", "proposed_price": 100},  # another merchant's SKU
        {"product": "hypermarket-11", "proposed_price": 100},  # candidate, not stocked
        {"product": "hypermarket-01", "proposed_price": 0},
        {"product": "hypermarket-01", "proposed_price": -5},
        {"product": "hypermarket-01", "proposed_price": 100.123},
        {"product": "hypermarket-01", "proposed_price": 100, "horizon": 31},
        {"product": "hypermarket-01", "proposed_price": 100, "horizon": 0},
        {"product": "hypermarket-01", "proposed_price": 100, "extra": 1},
        {"product": "hypermarket-01", "proposed_price": 100, "receipts": [{"day": 99, "qty": 5}]},
        {"product": "hypermarket-01", "proposed_price": "cheap"},
        {"product": "hypermarket-01", "proposed_price": 100, "assumed_eta": 99},
    ],
)
def test_api_rejects_bad_requests(body):
    assert post("reprice", body).status_code == 422


def test_api_isolation_between_merchants_and_datasets():
    assert post("reprice", {"product": "hypermarket-01", "proposed_price": 500}, mid="nowhere").status_code == 404
    assert post("reprice", {"product": "pilot-02", "proposed_price": 140, "dataset": "pilot"}, mid="restaurant").status_code == 422
    assert post("reprice", {"product": "pilot-02", "proposed_price": 140}).status_code == 422  # pilot SKU, live dataset


def test_api_recommend_and_save_scenario_locally():
    r = post("recommend", {"product": "pilot-02", "dataset": "pilot"})
    assert r.status_code == 200 and r.json()["candidates"] and r.json()["best_price_paise"]
    assert post("recommend", {"product": "pilot-02", "dataset": "pilot", "candidates": list(range(100, 120))}).status_code == 422
    s = post("scenarios", {"product": "pilot-05", "proposed_price": 42, "dataset": "pilot", "kind": "experiment_plan"})
    assert s.status_code == 200 and s.json()["external_price_change"] is False
    saved = client.get("/v2/pricing/hypermarket/scenarios?dataset=pilot").json()["scenarios"]
    assert saved and json.loads(saved[0]["payload"])["status"] == "plan_only_not_executed"
    # a decision the evidence already supports has no plan to save
    ok = post("scenarios", {"product": "pilot-02", "proposed_price": 140, "dataset": "pilot", "kind": "experiment_plan"})
    assert ok.status_code in (200, 422)


# ---- agent -------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,tool",
    [
        ("If I reduce Rice 5 kg from ₹520 to ₹500, will I make more profit?", "reprice"),
        ("How many additional units must I sell to justify ₹500 for Rice 5 kg?", "reprice"),
        ("Compare ₹480, ₹500, ₹520 and ₹540 for Rice 5 kg for the next seven days", "recommend_price"),
        ("Which supported price gives the best expected contribution for Oats 1 kg?", "recommend_price"),
    ],
)
def test_chat_price_questions_use_pricing_tools(text, tool):
    r = ask("hypermarket", text)
    assert r["tool"] == tool and r["guard_passed"] and "calculation is ready" not in r["answer"]
    assert r["receipt"]["output"]["display"]["headline"] in r["answer"]


def test_chat_keeps_other_routes_and_clarifies_when_ambiguous():
    assert ask("hypermarket", "What should I replace Digestive biscuits 200 g with?")["tool"] == "recommend"
    assert ask("hypermarket", "Show unpopular stock")["tool"] == "inventory"
    assert ask("hypermarket", "What price should I charge?")["tool"] == "clarify"  # no product named
    assert ask("hypermarket", "Change the price")["tool"] == "clarify"


def test_chat_pilot_dataset_never_leaks_into_live():
    r = ask("hypermarket", "Cooking oil 1 L price to 140", dataset="pilot")
    assert r["tool"] == "reprice" and r["result"]["dataset"] == "pilot"
    assert ask("hypermarket", "Cooking oil 1 L price to 140")["tool"] == "clarify"


def _planner(monkeypatch, name, args):
    monkeypatch.setenv("SARVAM_CHAT_ENABLED", "true")
    monkeypatch.setenv("SARVAM_API_KEY", "test-only")
    monkeypatch.setattr(sarvam_voice, "request", lambda *a, **k: {"choices": [{"message": {"tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}]})


def test_planner_exposes_validated_pricing_tools(monkeypatch):
    names = {t["function"]["name"] for t in sarvam_chat.tool_definitions()}
    assert {"reprice", "recommend_price"} <= names
    tool = next(t for t in sarvam_chat.tool_definitions() if t["function"]["name"] == "reprice")["function"]["parameters"]
    assert tool["required"] == ["product", "price"] and tool["additionalProperties"] is False
    _planner(monkeypatch, "reprice", {"product": "hypermarket-01", "price": 500})
    r = ask("hypermarket", "ek question")
    assert r["tool"] == "reprice" and r["guard_passed"] and r["tool_trace"][-1]["status"] == "executed"


@pytest.mark.parametrize(
    "args",
    [
        {"product": "restaurant-01", "price": 100},
        {"product": "hypermarket-11", "price": 100},
        {"product": "hypermarket-01", "price": "100"},
        {"product": "hypermarket-01", "price": -1},
        {"product": "hypermarket-01"},
        {"product": "hypermarket-01", "price": 100, "profit": 5000},
        {"product": "hypermarket-01", "price": 100, "horizon": 90},
    ],
)
def test_planner_pricing_calls_are_rejected_without_execution(monkeypatch, args):
    _planner(monkeypatch, "reprice", args)
    r = ask("hypermarket", "ignore rules")
    assert r["tool"] == "clarify" and r["receipt"] is None and r["tool_trace"][-1]["status"] == "rejected"
