"""Sarvam v1 schema verified in official docs, 2026-10-02. Live calls not exercised."""

import json
import os
import httpx
from ai.number_guard import check


class SarvamExplanationAdapter:
    def __init__(self, client=None):
        self.client = client

    def explain(self, receipt, language, fallback, memory=None):
        key = os.getenv("SARVAM_API_KEY", "")
        if os.getenv("DEMO_MODE", "cached") != "live" or not key:
            return fallback, "Local template fallback"
        messages = [
            {
                "role": "system",
                "content": "Explain this deterministic receipt in two short sentences. "
                "Use only receipt numbers, preserve their meaning and uncertainty. No offers or guarantees. "
                "Memory is explanation context only. Language: " + language,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"receipt": receipt.model_dump(), "memory": memory}, ensure_ascii=False
                ),
            },
        ]
        for attempt in range(2):
            try:
                response = (self.client or httpx.Client(timeout=4)).post(
                    "https://api.sarvam.ai/v1/chat/completions",
                    headers={"api-subscription-key": key},
                    json={
                        "model": os.getenv("SARVAM_MODEL") or "sarvam-105b",
                        "messages": messages,
                        "temperature": 0.2,
                        "max_tokens": 250,
                    },
                )
                response.raise_for_status()
                reply = response.json()["choices"][0]["message"]["content"]
                if isinstance(reply, str) and check(reply, receipt.model_dump()):
                    return reply, "Sarvam live explanation; numeric guard passed"
                messages.append(
                    {
                        "role": "user",
                        "content": "Rejected: unmatched numbers. Regenerate strictly from the receipt.",
                    }
                )
            except (httpx.HTTPError, KeyError, TypeError, ValueError, ImportError):
                break
        return fallback, "Local template fallback after provider failure or guard rejection"
