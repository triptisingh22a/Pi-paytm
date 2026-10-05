import base64
import io
import json
import sqlite3
import wave
from datetime import timedelta
import numpy as np
import pytest
import httpx
from fastapi.testclient import TestClient
from app.main import app
from billing import store
from billing.catalogue import catalogue, resolve
from billing.generate import AS_OF, START, generate
from billing.services import overview, peers, replacement, recommend
from billing.agent import ask, ToolCall, gemini_route
from ai import sarvam_voice

client = TestClient(app)


@pytest.fixture(scope="module")
def billing_db(tmp_path_factory):
    p = tmp_path_factory.mktemp("billing") / "test.sqlite3"
    generate(p)
    return p


@pytest.fixture(autouse=True)
def isolated(billing_db, monkeypatch):
    monkeypatch.setattr(store, "PATH", billing_db)
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.setenv("SARVAM_VOICE_ENABLED", "false")
    monkeypatch.setenv("SARVAM_CHAT_ENABLED", "false")
    peers.cache_clear()


def test_data_identity_and_balances(billing_db):
    db = sqlite3.connect(billing_db)
    assert db.execute("SELECT COUNT(DISTINCT kind) FROM merchants").fetchone()[0] == 7
    assert db.execute("SELECT MIN(day),MAX(day),COUNT(DISTINCT day) FROM daily").fetchone() == (
        str(START),
        str(AS_OF),
        365,
    )
    assert db.execute("SELECT COUNT(*) FROM daily WHERE opening-units-waste<>closing").fetchone()[0] == 0
    assert (
        db.execute(
            "SELECT COUNT(*) FROM daily WHERE opening<0 OR closing<0 OR units<0 OR exposure<0"
        ).fetchone()[0]
        == 0
    )
    assert db.execute("SELECT COUNT(*) FROM lines WHERE qty<=0 OR price<cost").fetchone()[0] == 0
    for mid in ("hypermarket", "restaurant", "apparel"):
        stock = db.execute(
            "SELECT SUM(qty) FROM stock_events WHERE merchant=? AND source='synthetic supplier bill'", (mid,)
        ).fetchone()[0]
        sales = db.execute("SELECT SUM(units) FROM daily WHERE merchant=?", (mid,)).fetchone()[0]
        closing = db.execute(
            "SELECT SUM(closing) FROM daily WHERE merchant=? AND day=?", (mid, str(AS_OF))
        ).fetchone()[0]
        assert stock == sales + closing
    # All POS lines reconcile to all daily unit/revenue aggregates by canonical product.
    assert (
        db.execute("SELECT SUM(qty*price) FROM lines").fetchone()[0]
        == db.execute("SELECT SUM(revenue) FROM daily").fetchone()[0]
    )
    assert resolve("Milk 1 L", "hypermarket")["id"] == "hypermarket-03"
    assert resolve("Milk 200 ml", "hypermarket") is None
    assert resolve("tee", "apparel") is None
    assert resolve("restaurant-11", "hypermarket") is None


@pytest.mark.parametrize(
    "mid", ["hypermarket", "restaurant", "apparel", "kirana", "pharmacy", "bakery", "electronics"]
)
@pytest.mark.parametrize("period", ["day", "week", "month"])
def test_overview_reconciliation(mid, period):
    d = overview(mid, period)
    assert d["revenue"] == sum(p["revenue"] for p in d["inventory"]) == sum(x["revenue"] for x in d["chart"])
    assert d["units"] == sum(p["units"] for p in d["inventory"])
    assert sum(x["bills"] for x in d["customer_profiles"]) == d["bills"]
    assert d["known_bills"] + d["anonymous_bills"] == d["bills"]
    assert d["returning_bills"] <= d["known_bills"]
    assert all(p["exposure"] > 0 and p["units"] == 0 for p in d["dead"])
    assert d["receipt"]["output"]["revenue"] == d["revenue"]
    assert "demographics" in d["receipt"]["assumptions"][0] or "gender" in d["receipt"]["assumptions"][0]


def test_peer_eligibility_aggregation_and_no_future(billing_db):
    p = peers("hypermarket", "hypermarket-11", "hypermarket-09")
    assert p["verdict"] == "SUPPORTED" and 10 <= p["peer_count"] <= 30
    assert 1 <= p["effective_peers"] <= p["peer_count"]
    assert p["rate_p10"] < p["rate"] < p["rate_p90"]
    assert p["local_exposure"] == 0
    assert "D000" not in json.dumps(p)
    early = str(AS_OF - timedelta(days=60))
    before = peers("hypermarket", "hypermarket-11", "hypermarket-09", early)
    db = sqlite3.connect(billing_db)
    db.execute("BEGIN")
    # Mutating hidden future candidate outcomes cannot affect past inference.
    db.execute("UPDATE peer_weeks SET units=units+5000 WHERE week>?", (early,))
    db.commit()
    peers.cache_clear()
    after = peers("hypermarket", "hypermarket-11", "hypermarket-09", early)
    assert before == after
    db.execute("UPDATE peer_weeks SET units=units-5000 WHERE week>?", (early,))
    db.commit()
    # Cohort suppression for insufficient eligible donors.
    db.execute(
        "UPDATE peer_weeks SET exposure=0 WHERE kind='hypermarket' AND product='hypermarket-11' AND peer NOT LIKE '%D00%'"
    )
    db.commit()
    peers.cache_clear()
    assert peers("hypermarket", "hypermarket-11")["verdict"] == "INSUFFICIENT_DATA"
    # Restore fixture after mutation.
    db.close()  # Windows cannot replace a SQLite file with an open connection.
    generate(billing_db)


@pytest.mark.parametrize("mid", ["hypermarket", "restaurant", "apparel"])
def test_twin_paired_accounting_and_constraints(mid):
    cat = catalogue(mid)
    y = next(p for p in cat if p["trend"] == "dead")
    x = next(p for p in cat if p["candidate"])
    r = replacement(mid, y["id"], x["id"], quantity=20, budget=20000, paths=128)
    assert r == replacement(mid, y["id"], x["id"], quantity=20, budget=20000, paths=128)
    assert r["candidate_units"] <= 20
    assert r["p10"] <= r["p50"] <= r["p90"]
    assert abs(sum(p["revenue_delta"] for p in r["products"]) - r["incremental_revenue"]) < 0.05
    assert abs(r["scenario_revenue"] - r["baseline_revenue"] - r["incremental_revenue"]) < 0.02
    assert r["incremental_cash_after_purchase"] == round(r["incremental_revenue"] - r["purchase_cost"], 2)
    assert all(p["scenario_units"] == 0 for p in r["products"] if p["name"] == y["name"])
    assert all(i["scenario_kg"] >= -1e-6 for i in r["ingredient_remaining"])
    assert r["chart"][-1]["day"] == 7
    assert abs(r["chart"][-1]["scenario"] - r["scenario_revenue"]) < 0.02
    assert len(r["sensitivity"]) == 3
    ranked = recommend(mid, y["id"], 20, 20000)
    assert ranked["candidates"][0]["p10"] >= ranked["candidates"][-1]["p10"]


def test_twin_refuses_unsupported_and_over_budget():
    with pytest.raises(ValueError):
        replacement("hypermarket", "hypermarket-01", "hypermarket-11")
    with pytest.raises(ValueError):
        replacement("hypermarket", "hypermarket-09", "hypermarket-11", budget=1)
    with pytest.raises(ValueError):
        replacement("hypermarket", "hypermarket-09", "hypermarket-09")
    with pytest.raises(ValueError):
        replacement("hypermarket", "hypermarket-09", "hypermarket-11", horizon=0)
    assert (
        client.post(
            "/v2/twin/hypermarket",
            json={"remove": "hypermarket-09", "replace": "hypermarket-11", "quantity": 501},
        ).status_code
        == 422
    )
    assert client.get("/v2/dashboard/missing").status_code == 422
    assert client.get("/v2/dashboard/hypermarket?period=year").status_code == 422


def test_grounded_routes():
    d = overview("hypermarket", "month")
    a = ask("hypermarket", "Give me monthly sales and customer overview")
    assert a["tool"] == "overview"
    assert f"₹{d['revenue']:,.0f}" in a["answer"]
    assert a["result"]["revenue"] == a["receipt"]["output"]["revenue"]
    assert ask("hypermarket", "Show unpopular stock")["tool"] == "inventory"
    assert ask("hypermarket", "lookalike shops")["tool"] == "peers"
    assert ask("hypermarket", "What should I replace Digestive biscuits 200 g with?")["tool"] == "recommend"
    assert ask("restaurant", "What if I replace Cream pasta with Paneer grain bowl?")["tool"] == "replace"
    assert ask("hypermarket", "Replace something")["tool"] == "clarify"
    assert ask("hypermarket", "What is the weather?")["tool"] == "clarify"
    assert (
        client.post("/v2/ask/hypermarket", json={"text": "today sales", "execute": "order"}).status_code
        == 422
    )
    assert client.get("/v2/merchants").json()["days"] == 365


def test_invoice_confirmation_transaction_and_idempotence():
    mid = "electronics"
    old = overview(mid)["inventory"][0]["on_hand"]
    bill = {
        "invoice_id": "TEST-001",
        "lines": [{"product": "electronics-01", "quantity": 7, "unit_cost": 130}],
        "confirmed": False,
    }
    assert client.post("/v2/invoices/" + mid + "/confirm", json=bill).status_code == 422
    bill["confirmed"] = True
    assert client.post("/v2/invoices/" + mid + "/confirm", json=bill).json()["imported"]
    assert overview(mid)["inventory"][0]["on_hand"] == old + 7
    assert client.post("/v2/invoices/" + mid + "/confirm", json=bill).json()["duplicate"]
    bill["lines"][0]["quantity"] = 8
    assert client.post("/v2/invoices/" + mid + "/confirm", json=bill).status_code == 409
    bad = {
        "invoice_id": "TEST-002",
        "lines": [
            {"product": "electronics-01", "quantity": 3, "unit_cost": 130},
            {"product": "unknown", "quantity": 1, "unit_cost": 1},
        ],
        "confirmed": True,
    }
    assert client.post("/v2/invoices/" + mid + "/confirm", json=bad).status_code == 422
    assert overview(mid)["inventory"][0]["on_hand"] == old + 7
    assert client.get("/v2/invoices/restaurant/sample").json()["status"] == "CACHED_SAMPLE_EXTRACTION"


def test_gemini_route_validation_and_fallback(monkeypatch):
    class Fake:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, url, **kw):
            assert kw["headers"]["x-goog-api-key"] == "test-only"
            assert len(kw["json"]["tools"]) == 1
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": "merchant_decision",
                                            "args": {"tool": "overview", "period": "week"},
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                },
                request=httpx.Request("POST", url),
            )

    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setattr(httpx, "Client", Fake)
    assert gemini_route("sales", "hypermarket", "day") == ToolCall(tool="overview", period="week")
    with pytest.raises(ValueError):
        ToolCall(tool="send_payment")
    with pytest.raises(ValueError):
        ToolCall(tool="overview", unapproved=1)
    monkeypatch.setenv("GEMINI_MODEL", "bad/model")
    assert gemini_route("sales", "hypermarket", "day") is None


def wav():
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(np.zeros(1600, dtype=np.int16).tobytes())
    return b.getvalue()


def test_sarvam_exact_schemas_no_auto_calls_and_failures(monkeypatch):
    assert not sarvam_voice.status()["enabled"]
    assert client.post("/v2/voice/tts", json={"text": "hello"}).status_code == 503
    assert client.post("/v2/voice/stt", files={"file": ("test.wav", wav(), "audio/wav")}).status_code == 503
    monkeypatch.setenv("SARVAM_VOICE_ENABLED", "true")
    monkeypatch.setenv("SARVAM_API_KEY", "test-only")
    requests = []

    class Fake:
        def __init__(self, **kw):
            assert kw["trust_env"] is False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, url, **kw):
            requests.append((url, kw))
            assert kw["headers"] == {"api-subscription-key": "test-only"}
            if url.endswith("text-to-speech"):
                assert kw["json"] == {
                    "text": "hello",
                    "language_code": "en-IN",
                    "model": "bulbul:v3",
                    "speaker": "shubh",
                    "speech_sample_rate": 16000,
                    "output_audio_codec": "wav",
                }
                return httpx.Response(
                    200, json={"request_id": "tts-1", "audios": [base64.b64encode(wav()).decode()]}
                )
            assert kw["data"]["model"] == "saaras:v4"
            return httpx.Response(
                200, json={"request_id": "stt-1", "transcript": "hello", "language_code": "en-IN"}
            )

    monkeypatch.setattr(httpx, "Client", Fake)
    assert client.post("/v2/voice/tts", json={"text": "hello"}).content == wav()
    assert (
        client.post("/v2/voice/stt", files={"file": ("test.wav", wav(), "audio/wav")}).json()["transcript"]
        == "hello"
    )
    assert len(requests) == 2
    with pytest.raises(ValueError):
        sarvam_voice.synthesize("x" * 2501)
    with pytest.raises(ValueError):
        sarvam_voice.transcribe(b"bad", content_type="text/plain")

    class Fail(Fake):
        def post(self, url, **kw):
            requests.append((url, kw))
            return httpx.Response(403, json={"secret": "must-not-escape"})

    monkeypatch.setattr(httpx, "Client", Fail)
    with pytest.raises(ValueError, match="HTTP 403") as e:
        sarvam_voice.synthesize("hello")
    assert "secret" not in str(e.value) and len(requests) == 3


@pytest.mark.parametrize("mid", ["hypermarket", "restaurant", "apparel"])
@pytest.mark.parametrize("period", ["day", "week", "month"])
def test_billing_explanations_pass_numeric_guard(mid, period):
    from ai.number_guard import check

    result = ask(mid, f"{period} sales and customer overview")
    assert result["guard_passed"]
    assert "recorded revenue" in result["answer"]
    assert check(result["answer"], result["receipt"])
    assert not check("Revenue was ₹9,999,999,999", result["receipt"])


def test_speech_proxy_configuration_preserves_network_policy(monkeypatch):
    # Configuration only: no DNS, socket, provider or credential requests.
    for name in (
        "https_proxy",
        "HTTPS_PROXY",
        "http_proxy",
        "HTTP_PROXY",
        "SARVAM_HTTP_PROXY",
        "no_proxy",
        "NO_PROXY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ALL_PROXY", "socks5h://unrelated.invalid:9999")
    assert sarvam_voice.client_options() == {"timeout": 35, "trust_env": False}
    monkeypatch.setenv("HTTPS_PROXY", "http://network-policy.invalid:8080")
    assert sarvam_voice.client_options()["proxy"] == "http://network-policy.invalid:8080"
    monkeypatch.setenv("NO_PROXY", "api.sarvam.ai")
    assert "proxy" not in sarvam_voice.client_options()
    monkeypatch.setenv("SARVAM_HTTP_PROXY", "http://explicit.invalid:8081")
    assert sarvam_voice.client_options()["proxy"] == "http://explicit.invalid:8081"
    monkeypatch.setenv("SARVAM_HTTP_PROXY", "")
    assert "proxy" not in sarvam_voice.client_options()
    monkeypatch.setenv("SARVAM_HTTP_PROXY", "socks5://not-supported.invalid:1")
    with pytest.raises(ValueError, match="HTTP"):
        sarvam_voice.client_options()
