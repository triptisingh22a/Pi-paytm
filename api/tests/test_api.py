from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_full_journey():
    client.post("/reset/kirana")
    d = client.get("/dashboard/kirana").json()
    assert d["simulated"]
    for text in [
        "10% discount doon?",
        "cash gap",
        "aaj kaisa raha",
        "similar shops",
        "loan chahiye",
        "restock budget",
        "weather",
    ]:
        r = client.post("/ask/kirana", json={"text": text}).json()
        assert r["guard_passed"]
    a = d["ranked"]["output"]["actions"][0]["action"]
    assert client.post("/simulate/kirana", json={"action": a}).status_code == 200
    assert client.post("/approve/kirana", json={"action": a}).status_code == 200
    assert client.post("/approve/kirana", json={"action": a}).status_code == 409
    result = client.post("/advance/kirana").json()
    assert result["day"] == 7
    d2 = client.get("/dashboard/kirana").json()
    assert d2["memory"] and not d2["pending_action"]
    assert d2["cash"] == result["receipt"]["output"]["simulated_realized_cash"]
    result2 = client.post("/advance/kirana").json()
    assert result2["receipt"]["inputs"]["action"] == {"type": "hold"}
    assert result2["earned"] == result["earned"]
    assert client.post("/reset/kirana").json()["reset"]
    assert client.get("/dashboard/kirana?tier=A").json()["stock"] == []
    r = client.post("/ask/kirana", json={"text": "10% discount", "tier": "A"}).json()
    assert r["receipt"]["output"]["verdict"] == "INSUFFICIENT_DATA"


def test_validation_and_languages():
    for tier in ["A", "B"]:
        for lang in ["en", "hi", "mr"]:
            r = client.post("/ask/electronics", json={"text": "discount", "tier": tier, "language": lang})
            assert r.status_code == 200
    assert client.get("/dashboard/unknown").status_code == 404
    assert client.get("/dashboard/kirana?tier=C").status_code == 422
    assert client.post("/ask/kirana", json={"text": "", "budget": -1}).status_code == 422
    assert client.post("/approve/kirana", json={"action": {"type": "hold"}, "tier": "A"}).status_code == 422
    assert client.post("/simulate/kirana", json={"action": {"type": "invalid"}}).status_code == 422
    assert client.get("/health").status_code == 200
    assert client.get("/integration-status").status_code == 200
    assert client.get("/briefing/kirana").status_code == 200
    assert client.post("/skip/kirana").status_code == 200
