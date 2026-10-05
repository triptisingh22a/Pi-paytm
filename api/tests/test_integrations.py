import httpx
from ai.provider_adapter import SarvamExplanationAdapter
from integrations.telegram import TelegramAdapter
from engine.receipts import Receipt


def test_provider_retries_and_fallback(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "live")
    monkeypatch.setenv("SARVAM_API_KEY", "test-only")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "₹99999 guaranteed"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    r = Receipt(formula_text="test", output={"profit": 100})
    text, provider = SarvamExplanationAdapter(client).explain(r, "en", "₹100")
    assert text == "₹100" and len(calls) == 2 and "fallback" in provider
    assert calls[0].headers["api-subscription-key"] == "test-only"


def test_provider_valid_and_failure(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "live")
    monkeypatch.setenv("SARVAM_API_KEY", "test-only")
    r = Receipt(formula_text="test", output={"profit": 100})
    for status, reply, expected in [(200, "₹100", "₹100"), (500, "bad", "fallback")]:
        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(status, json={"choices": [{"message": {"content": reply}}]})
            )
        )
        assert SarvamExplanationAdapter(client).explain(r, "en", "fallback")[0] == expected
    monkeypatch.setenv("DEMO_MODE", "cached")
    assert SarvamExplanationAdapter().explain(r, "en", "fallback")[0] == "fallback"


def test_telegram_mock_and_schema(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "cached")
    result = TelegramAdapter().proposal("Simulated plan", "abc")
    assert not result["delivered"]
    assert result["payload"]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "approve:abc"
    monkeypatch.setenv("DEMO_MODE", "live")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-only")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"ok": True, "result": {"message_id": 12}})
        )
    )
    assert TelegramAdapter(client).proposal("Simulated plan", "abc")["delivered"]
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(500, json={})))
    assert not TelegramAdapter(client).proposal("Simulated plan", "abc")["delivered"]


def test_telegram_authenticated_idempotent_callback(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setenv("DEMO_MODE", "cached")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
    client = TestClient(app)
    client.post("/reset/kirana")
    result = client.post("/channels/telegram/proposal/kirana").json()
    assert result["created"] and not result["delivery"]["delivered"]
    body = {
        "callback_query": {
            "id": "cb-test",
            "data": "approve:" + result["proposal_id"],
            "message": {"chat": {"id": 123}},
        }
    }
    assert client.post("/channels/telegram/webhook", json=body).status_code == 403
    headers = {"x-telegram-bot-api-secret-token": "test-secret"}
    a = client.post("/channels/telegram/webhook", json=body, headers=headers)
    assert a.status_code == 200 and not a.json()["duplicate"]
    assert client.post("/channels/telegram/webhook", json=body, headers=headers).json()["duplicate"]
    assert client.get("/dashboard/kirana").json()["pending_action"]
    client.post("/reset/kirana")
    r = client.post("/channels/telegram/proposal/kirana").json()
    body["callback_query"]["data"] = "skip:" + r["proposal_id"]
    assert client.post("/channels/telegram/webhook", json=body, headers=headers).json()["action"] == "skip"
    assert not client.get("/dashboard/kirana").json()["pending_action"]
    assert client.get("/restock-alert/kirana").status_code == 200


def test_workflow_exports_and_fallback_briefing():
    import json
    from pathlib import Path
    from fastapi.testclient import TestClient
    from app.main import app

    for path in Path("../n8n/workflows").glob("*.json"):
        w = json.loads(path.read_text())
        assert w["active"] is False
        names = {n["name"] for n in w["nodes"]}
        for name, connection in w["connections"].items():
            assert name in names
            for group in connection["main"]:
                assert all(c["node"] in names for c in group)
    r = TestClient(app).post("/channels/telegram/briefing/kirana").json()
    assert not r["delivery"]["delivered"]
