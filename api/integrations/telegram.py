"""Official Bot API sendMessage + inline keyboard schema verified. No live send performed."""

import os
import httpx


class TelegramAdapter:
    def __init__(self, client=None):
        self.client = client

    def proposal(self, text, proposal_id):
        payload = {
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
            "text": text,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "Approve simulation", "callback_data": "approve:" + proposal_id},
                        {"text": "Skip", "callback_data": "skip:" + proposal_id},
                    ]
                ]
            },
        }
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if os.getenv("DEMO_MODE", "cached") != "live" or not token or not payload["chat_id"]:
            return {"delivered": False, "mode": "MOCKED preview", "payload": payload}
        try:
            r = (self.client or httpx.Client(timeout=4)).post(
                f"https://api.telegram.org/bot{token}/sendMessage", json=payload
            )
            r.raise_for_status()
            data = r.json()
            if data.get("ok"):
                return {"delivered": True, "mode": "live", "message_id": data["result"]["message_id"]}
        except (httpx.HTTPError, KeyError, ValueError, ImportError):
            pass
        return {"delivered": False, "mode": "MOCKED preview after network failure", "payload": payload}

    def acknowledge(self, callback_id, text):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if os.getenv("DEMO_MODE", "cached") != "live" or not token:
            return False
        try:
            r = (self.client or httpx.Client(timeout=4)).post(
                f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": text},
            )
            return r.status_code == 200 and r.json().get("ok", False)
        except (httpx.HTTPError, ValueError, ImportError):
            return False

    def message(self, text):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat = os.getenv("TELEGRAM_CHAT_ID", "")
        payload = {"chat_id": chat, "text": text}
        if os.getenv("DEMO_MODE", "cached") != "live" or not token or not chat:
            return {"delivered": False, "mode": "MOCKED preview", "payload": payload}
        try:
            r = (self.client or httpx.Client(timeout=4)).post(
                f"https://api.telegram.org/bot{token}/sendMessage", json=payload
            )
            r.raise_for_status()
            return {"delivered": bool(r.json().get("ok")), "mode": "live"}
        except (httpx.HTTPError, ValueError, ImportError):
            return {"delivered": False, "mode": "MOCKED preview after failure", "payload": payload}
