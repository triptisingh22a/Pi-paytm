import ast
import copy
import itertools
import json
from pathlib import Path
import numpy as np
import pytest
from integrations.paytm_pos_sim import PaytmPOSAdapter
from engine.allocator import allocate
from engine.cash_runway import runway
from engine.demand import forecast
from engine.margins import margin
from engine.overview import overview
from engine.promo_uplift import promo
from engine.loan_nudge import loan_nudge
from engine.ranker import rank
from engine.receipts import Receipt
from twin.simulator import simulate
from twin.lookalikes import peers
from twin.state import from_shop
from ai.number_guard import check, guarded
from ai.tools import route
from ai.llm_adapter import LLMAdapter
from app.config import DATA


@pytest.fixture
def adapter():
    return PaytmPOSAdapter()


@pytest.fixture
def shop(adapter):
    return adapter.merchant("kirana")


@pytest.mark.parametrize("kind", ["kirana", "sweets", "electronics", "vegetables"])
def test_forecast_and_promo(adapter, kind):
    shop = adapter.merchant(kind)
    sku = shop["skus"][0]
    f = forecast(sku)
    assert len(f.p50) == 7
    assert all(a <= b <= c for a, b, c in zip(f.p10, f.p50, f.p90))
    assert f.output["backtest_pinball_loss"] >= 0
    assert f.model_dump() == forecast(sku).model_dump()
    p = promo(sku)
    assert p.p10 <= p.p50 <= p.p90
    assert check(LLMAdapter().explain("promo", p), p.model_dump())


def test_opposite_verdicts(adapter):
    assert promo(adapter.merchant("electronics")["skus"][0]).output["verdict"] == "DO"
    assert promo(adapter.merchant("kirana")["skus"][0]).output["verdict"] == "DON'T"


def test_censored_observations_ignored(shop):
    changed = copy.deepcopy(shop["skus"][0])
    for row in changed["history"]:
        if row["stockout"]:
            row["sales"] = 99999
    assert forecast(changed).output == forecast(shop["skus"][0]).output


def test_cold_start(shop):
    sku = copy.deepcopy(shop["skus"][0])
    sku["history"] = []
    r = forecast(sku, peer_prior=17)
    assert r.output["mean_daily"] == [17] * 7
    assert "COLD_START_PEER_PRIOR" in r.data_quality_flags


def test_allocator_budget_and_zero(shop):
    r = allocate(shop, 1500)
    assert r.output["spend"] <= 1500 + 0.01
    assert r.output["expected_incremental_profit"] >= 0
    assert all(isinstance(o["quantity"], int) for o in r.output["orders"])
    assert allocate(shop, 0).output["spend"] == 0
    assert allocate(shop, 0).output["orders"] == []
    assert r.output["next_1000_profit"] >= 0
    assert r.model_dump() == allocate(shop, 1500).model_dump()
    with pytest.raises(ValueError):
        allocate(shop, -1)
    with pytest.raises(ValueError):
        allocate(shop, float("nan"))


def test_integer_solver_against_exhaustive(shop):
    # Two long-lived items, exactly known 2-unit demand, heterogeneous costs.
    skus = copy.deepcopy(shop["skus"][:2])
    for s, c, p in zip(skus, [6, 4], [12, 7]):
        s.update(cost=c, price=p, stock=0, lead_time=0, mean=0.1)
        s["history"] = []
    small = {**shop, "skus": skus}
    # Reproduce sampled demand using the same seed and specified cold prior.
    rng = np.random.default_rng(42)
    demands = [rng.poisson(140, 2048), rng.poisson(140, 2048)]
    best = max(
        sum(
            s["price"] * np.minimum(d, q).mean() - s["cost"] * np.minimum(d, q).mean()
            for s, d, q in zip(skus, demands, qs)
        )
        for qs in itertools.product(range(4), repeat=2)
        if sum(s["cost"] * q for s, q in zip(skus, qs)) <= 14
    )
    r = allocate(small, 14)
    assert r.output["expected_incremental_profit"] == pytest.approx(best, abs=0.01)


def test_missing_inputs_and_tier_a(shop, adapter):
    a = adapter.merchant("kirana", "A")
    assert not a["skus"]
    assert runway(a).data_tier == "A"
    assert allocate(a, 1000).output["verdict"] == "INSUFFICIENT_DATA"
    assert simulate(a, {"type": "hold"}).output["verdict"] == "INSUFFICIENT_DATA"
    assert promo(None, tier="A").output["verdict"] == "INSUFFICIENT_DATA"
    assert rank(a, allocate(a, 0)).output["actions"][0]["roi"] is None
    missing = copy.deepcopy(shop)
    missing["skus"][0]["cost"] = None
    assert allocate(missing, 1000).output["verdict"] == "INSUFFICIENT_DATA"
    assert promo(missing["skus"][0]).output["verdict"] == "INSUFFICIENT_DATA"
    missing["skus"][0]["cost"] = 0
    assert allocate(missing, 1000).output["verdict"] == "INSUFFICIENT_DATA"


def test_runway(shop):
    r = runway(shop)
    assert 0 <= r.output["gap_probability"] <= 1
    assert 0 <= r.output["safe_to_commit"] <= shop["cash"]
    assert len(r.p50) == 14
    assert r.model_dump() == runway(shop).model_dump()
    for args in [{"risk": 0}, {"horizon": 15}, {"n_paths": 100}]:
        with pytest.raises(ValueError):
            runway(shop, **args)
    broke = copy.deepcopy(shop)
    broke.update(cash=10, pending=[0, 0], dues=[100000] + [0] * 13)
    b = runway(broke)
    assert b.output["gap_probability"] == 1
    assert b.output["safe_to_commit"] == 0
    assert b.output["earliest_likely_gap_day"] == 1


def test_promo_edge_cases(shop):
    sku = copy.deepcopy(shop["skus"][0])
    sku["promo_episodes"] = []
    assert promo(sku).output["verdict"] == "INSUFFICIENT_DATA"
    assert promo(shop["skus"][0], 0.2).output["verdict"] == "INSUFFICIENT_DATA"
    with pytest.raises(ValueError):
        promo(shop["skus"][0], 1)


def test_margins():
    assert margin(65, 100).output["margin"] == 0.35
    for c, p, t in [(None, 100, "B"), (0, 0, "B"), (-1, 3, "B"), (5, 10, "A")]:
        assert margin(c, p, t).output["verdict"] == "INSUFFICIENT_DATA"


def test_peer_privacy(shop, adapter):
    p = peers(shop, adapter.bundle["peers"])
    text = p.model_dump_json()
    assert p.output["group_size"] >= 10
    assert "private_id" not in text and "background-" not in text and "features" not in text
    with pytest.raises(ValueError):
        peers(shop, adapter.bundle["peers"], k=9)
    assert peers(shop, []).output["verdict"] == "INSUFFICIENT_DATA"


def test_twin_paired_paths_and_cash(shop):
    h = simulate(shop, {"type": "hold"}, n_paths=32)
    assert h.output["expected_incremental_profit"] == 0
    assert h.p10 == h.p90 == 0
    initial = copy.deepcopy(shop)
    action = {"type": "restock", "orders": [{"sku_id": shop["skus"][0]["id"], "quantity": 10}]}
    r = simulate(shop, action, n_paths=32)
    assert r.p10 <= r.p50 <= r.p90
    assert shop == initial
    assert r.model_dump() == simulate(shop, action, n_paths=32).model_dump()
    assert r.output["action_stockouts"] <= r.output["baseline_stockouts"]
    for action in [
        {"type": "invalid"},
        {"type": "restock", "orders": [{"sku_id": "unknown", "quantity": 2}]},
        {"type": "restock", "orders": [{"sku_id": shop["skus"][0]["id"], "quantity": 999999}]},
    ]:
        with pytest.raises(ValueError):
            simulate(shop, action, n_paths=1)
    with pytest.raises(ValueError):
        simulate(shop, {"type": "hold"}, horizon_days=0)
    credit = simulate(shop, {"type": "credit", "amount": 1000, "cost_fraction": 0.02}, n_paths=2)
    assert credit.output["expected_incremental_profit"] == -20
    assert credit.output["action_cash"] == pytest.approx(credit.output["baseline_cash"] - 20)
    promo_r = simulate(
        shop,
        {
            "type": "promo",
            "sku_id": shop["skus"][0]["id"],
            "discount": 0.1,
            "uplift": 0.5,
            "pull_forward": 0.1,
        },
        n_paths=2,
    )
    assert promo_r.output["probability_loss"] >= 0
    assert from_shop(shop).cash == shop["cash"]


def test_overview_and_rank(shop):
    for period in ["day", "week", "month", "festival"]:
        assert overview(shop, period).output["sales"] >= 0
    basket = allocate(shop, 1000)
    actions = rank(shop, basket).output["actions"]
    assert len(actions) <= 5
    assert actions[-1]["roi"] is None


def test_responsible_loan(shop):
    cash = Receipt(formula_text="test", output={"gap_size": 500, "gap_probability": 0.8})
    action = Receipt(
        formula_text="test", output={"spend": shop["cash"] + 500, "expected_incremental_profit": 100}
    )
    r = loan_nudge(shop, cash, action)
    assert r.output["show"] and r.output["amount"] == 500
    assert not loan_nudge({**shop, "data_tier": "A"}, cash, action).output["show"]
    assert not loan_nudge(shop, cash, action, assumed_cost=1).output["show"]


@pytest.mark.parametrize(
    "reply,ok",
    [
        ("₹42,300", True),
        ("Rs 42.3K", True),
        ("42.3k", True),
        ("४२३००", True),
        ("10%", True),
        ("2026-10-02", True),
        ("2026-10-03", False),
        ("₹99,000", False),
        ("-42,300", False),
        ("Guaranteed 100%", False),
        ("7 days", True),
    ],
)
def test_number_guard(reply, ok):
    assert check(reply, {"cash": 42300, "risk": 0.1, "horizon": 7, "date": "2026-10-02"}) is ok


def test_guard_fallback():
    assert guarded("₹999", {"profit": 100}, "₹100") == ("₹100", True)
    assert guarded("₹100", {"profit": 100}, "₹100") == ("₹100", False)
    with pytest.raises(ValueError):
        guarded("₹999", {}, "₹123")


def test_no_ai_imports():
    forbidden = {"ai", "openai", "sarvam", "langchain", "anthropic", "cognee"}
    for folder in ["engine", "twin"]:
        for file in Path(folder).glob("*.py"):
            tree = ast.parse(file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                assert all(n.split(".")[0] not in forbidden for n in names), file


def test_router():
    cases = {
        "10 percent discount": "promo",
        "cash gap": "cash",
        "restock namkeen": "allocate",
        "aaj kaisa raha": "overview",
        "similar shops": "peers",
        "loan chahiye": "loan",
        "weather": "out_of_scope",
    }
    for q, tool in cases.items():
        assert route(q) == tool


def test_snapshot(shop):
    actual = promo(shop["skus"][0]).model_dump()
    snap = Path("tests/snapshots/promo.json")
    assert json.loads(snap.read_text(encoding="utf-8")) == actual
    assert json.loads((DATA / "ground_truth.json").read_text())["uplift"] == 0.8


def test_empty_uncensored_holdout(shop):
    sku = copy.deepcopy(shop["skus"][0])
    for row in sku["history"][-28:]:
        row["stockout"] = True
    r = forecast(sku)
    assert r.output["backtest_pinball_loss"] is None
    assert "NO_UNCENSORED_HOLDOUT" in r.data_quality_flags


def test_guard_scientific_and_spelled_numbers():
    assert check("INR 1e3", {"amount": 1000})
    assert not check("INR 1e3", {"amount": 1})
    assert not check("fifty percent guaranteed", {"profit": 100})


def test_synthetic_cohort_transition():
    from twin.customers import evolve

    c = {"new": 25, "repeat": 70, "at_risk": 15, "inactive": 20}
    out = evolve(c, 30)
    assert all(v >= 0 for v in out.values())
    assert sum(out.values()) >= sum(c.values())
    assert evolve(c, 30) == out
    assert c["new"] == 25
