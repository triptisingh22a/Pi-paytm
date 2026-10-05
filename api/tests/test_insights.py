"""Pi insight tools, customer rhythms and the payments-only view."""

import sqlite3
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from ai import sarvam_chat
from billing import insights, store
from billing.agent import ask
from billing.generate import AS_OF, generate
from billing.habits import classify, customer_habits, WINDOW
from billing.payments_only import payments_only
from billing.services import overview

client = TestClient(app)
MERCHANTS = ("hypermarket", "restaurant", "apparel", "kirana", "pharmacy", "bakery", "electronics")


@pytest.fixture(scope="module")
def billing_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("insights") / "test.sqlite3"
    generate(path)
    return path


@pytest.fixture(autouse=True)
def isolated(billing_db, monkeypatch):
    monkeypatch.setattr(store, "PATH", billing_db)
    monkeypatch.setenv("SARVAM_CHAT_ENABLED", "false")
    monkeypatch.setenv("SARVAM_VOICE_ENABLED", "false")
    insights._cache.clear()


def days(*offsets):
    return [AS_OF - timedelta(days=o) for o in sorted(offsets, reverse=True)]


def test_seeding_only_relabels_customers(billing_db):
    db = sqlite3.connect(billing_db)
    lines = db.execute("SELECT SUM(qty*price) FROM lines").fetchone()[0]
    daily = db.execute("SELECT SUM(revenue) FROM daily").fetchone()[0]
    assert lines == pytest.approx(daily)
    assert db.execute("SELECT COUNT(DISTINCT customer) FROM bills WHERE customer LIKE 'L-%-09__'").fetchone()[0] > 30


def test_classify_names_rhythms_and_rejects_noise():
    assert classify(days(*range(0, 110)))[:2] == ("daily", "Every day")
    assert classify(days(*range(3, 119, 7)))[0] == "weekday"
    assert classify(days(*range(0, 100, 10)))[1:] == ("Every 10 days", 10)
    assert classify(days(*range(0, 112, 14)))[1] == "Every 2 weeks"
    # few visits, or visits at uneven gaps, are not a rhythm
    assert classify(days(0, 9, 31, 33)) is None
    assert classify(days(0, 4, 13, 40, 41, 77, 90)) is None


def test_habits_find_seeded_regulars_and_nothing_spurious():
    h = customer_habits("hypermarket")
    top = h["groups"][0]
    assert (top["product_name"], top["cadence"]) == ("Milk 1 L", "Every day") and top["customers"] >= 6
    assert h["summary"]["regular_customers"] == len({x["customer"] for x in h["habits"]})
    assert h["summary"]["habits"] == len(h["habits"]) < 60
    assert {g["cadence"] for g in h["groups"]} >= {"Every Sunday", "Every Saturday", "Every 3 days", "Every 2 weeks"}
    assert all(x["customer"].split("-")[-1].startswith("09") for x in h["habits"])
    assert h["receipt"]["assumptions"] and h["window"] == [str(AS_OF - timedelta(days=WINDOW - 1)), str(AS_OF)]


@pytest.mark.parametrize("mid", MERCHANTS)
@pytest.mark.parametrize("period", ["day", "week", "month"])
def test_every_insight_is_grounded_and_guarded(mid, period):
    from ai.number_guard import check

    feed = insights.get_insights(mid, period)
    assert [i["id"] for i in feed["insights"]] == insights.IDS
    for item in feed["insights"]:
        assert item["headline"] and item["receipt"]["output"]
        assert check(f"{item['title']}: {item['headline']}. {item['detail']}", item["receipt"]), item["id"]


def test_restock_topup_matches_cover_rule():
    feed = insights.get_insights("hypermarket", "day")
    restock = next(i for i in feed["insights"] if i["id"] == "restock")
    inv = {p["name"]: p for p in overview("hypermarket", "day")["inventory"]}
    assert restock["facts"]["items"]
    for row in restock["facts"]["items"]:
        p = inv[row["name"]]
        rate = p["on_hand"] / p["days_cover"]
        assert p["days_cover"] < 7 and row["topup"] >= rate * 14 - p["on_hand"] > row["topup"] - 2


def test_cache_scheduled_and_manual_refresh():
    first = insights.get_insights("hypermarket", "day")
    assert first["trigger"] == "first load"
    assert insights.get_insights("hypermarket", "day") is first
    manual = insights.get_insights("hypermarket", "day", refresh=True)
    assert manual["trigger"] == "manual refresh" and manual is not first
    insights._build("hypermarket", "day", "scheduled refresh")
    assert insights.get_insights("hypermarket", "day")["trigger"] == "scheduled refresh"
    insights.invalidate("hypermarket")
    assert insights.get_insights("hypermarket", "day")["trigger"] == "first load"


@pytest.mark.parametrize(
    "question,insight",
    [
        ("Who are my regular customers?", "regulars"),
        ("Which customers come back every week?", "regulars"),
        ("What do I need to replenish soon?", "restock"),
        ("What is my most sold item?", "most_sold"),
        ("Which product is losing traction?", "falling"),
        ("Which product is rising?", "rising"),
        ("Which item brings in the most revenue?", "revenue_leader"),
        ("Which shelf should I check?", "dead_shelf"),
    ],
)
def test_chat_calls_the_same_insight_tools(question, insight):
    r = ask("hypermarket", question)
    assert r["tool"] == "insight" and r["arguments"]["insight"] == insight
    assert r["guard_passed"] and r["receipt"]["output"]
    assert "calculation is ready" not in r["answer"]


def test_inventory_answer_says_how_much_to_order():
    r = ask("hypermarket", "What should I restock this week and how much?")
    assert r["tool"] == "inventory" and r["guard_passed"] and "more to reach 14 days" in r["answer"]


def test_overview_answer_no_longer_reports_returning_bills():
    r = ask("hypermarket", "Give me monthly sales and customer overview")
    assert r["tool"] == "overview" and "returning" not in r["answer"].lower()


def test_planner_exposes_insight_tool_with_closed_enum():
    tool = next(t for t in sarvam_chat.tool_definitions() if t["function"]["name"] == "insight")
    props = tool["function"]["parameters"]
    assert props["required"] == ["insight"] and props["additionalProperties"] is False
    assert set(props["properties"]["insight"]["enum"]) == set(insights.IDS)
    call = sarvam_chat.validate_call("insight", {"insight": "restock"}, "hypermarket", "week")
    assert call.tool == "insight" and call.period == "week"
    for bad in ({"insight": "drop_table"}, {}, {"insight": "restock", "sql": "x"}):
        with pytest.raises(Exception):
            sarvam_chat.validate_call("insight", bad, "hypermarket", "day")


def test_payments_only_reads_amounts_and_times_only():
    p = payments_only("hypermarket")
    assert p["last7"] > 0 and 0 <= p["change_fraction"] < 1 and p["payments_7d"] > 0
    assert p["outlook"]["low"] <= p["outlook"]["expected"] <= p["outlook"]["high"]
    assert len(p["chart"]) == 28 and len(p["peak_hours"]) == 3
    assert p["receipt"]["data_tier"] == "A" and "PAYMENTS_ONLY" in p["receipt"]["data_quality_flags"]
    caps = {c["id"]: c["available"] for c in p["capabilities"]}
    assert sum(caps.values()) == 3 and not caps["sellers"] and not caps["restock"] and not caps["rhythms"]
    assert "inventory" not in p and "products" not in p
    # the 7-day total equals the item-level overview for the same days
    assert p["last7"] == pytest.approx(overview("hypermarket", "week")["revenue"], abs=1)


def test_api_endpoints():
    feed = client.get("/v2/insights/hypermarket?period=week").json()
    assert feed["period"] == "week" and len(feed["insights"]) == len(insights.IDS)
    refreshed = client.post("/v2/insights/hypermarket/refresh?period=week").json()
    assert refreshed["trigger"] == "manual refresh"
    assert client.get("/v2/habits/restaurant").json()["groups"]
    assert client.get("/v2/payments-only/kirana").json()["capabilities"]
    assert client.get("/v2/insights/nowhere").status_code in (404, 422, 500)
    assert client.get("/v2/insights/hypermarket?period=year").status_code == 422
