"""Final opt-in credit-bounded speech smoke: one short TTS, then one STT, no retries."""

import io
import json
import sys
import time
import wave
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "api"))
from ai.sarvam_voice import status
from app.main import app
from fastapi.testclient import TestClient

if not status()["enabled"]:
    raise SystemExit(
        "Enable voice and supply a private server-side key to run this explicit test."
    )
client = TestClient(app)
text = "Munshi voice is ready."
result = {
    "test": "One short TTS followed by STT of that same WAV; no retries or chat calls.",
    "input_text": text,
    "characters": len(text),
    "tts": {},
    "stt": {},
    "live_calls_attempted": 0,
    "limitations": "Generated English audio roundtrip only. Microphone, Hinglish, Marathi/Hindi and real bill-asking accuracy are not verified.",
}
start = time.perf_counter()
result["live_calls_attempted"] += 1
response = client.post("/v2/voice/tts", json={"text": text, "language": "en-IN"})
result["tts"] = {
    "app_http_status": response.status_code,
    "elapsed_ms": round((time.perf_counter() - start) * 1000, 1),
    "model": "bulbul:v3",
}
if response.status_code == 200:
    result["tts"].update(
        provider_http_status=200,
        request_id=response.headers.get("x-speech-request-id"),
        audio_bytes=len(response.content),
    )
    try:
        with wave.open(io.BytesIO(response.content), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
            result["tts"].update(
                duration_seconds=round(duration, 3),
                sample_rate=wav.getframerate(),
                channels=wav.getnchannels(),
            )
        if duration > 10:
            result["stt"] = {"skipped": "TTS audio exceeds minimal-test duration cap"}
        else:
            start = time.perf_counter()
            result["live_calls_attempted"] += 1
            stt = client.post(
                "/v2/voice/stt",
                files={"file": ("minimal.wav", response.content, "audio/wav")},
                data={"language": "en-IN"},
            )
            result["stt"] = {
                "app_http_status": stt.status_code,
                "elapsed_ms": round((time.perf_counter() - start) * 1000, 1),
                "model": "saaras:v4",
            }
            if stt.status_code == 200:
                data = stt.json()
                result["stt"].update(
                    provider_http_status=200,
                    request_id=data.get("request_id"),
                    transcript=data.get("transcript"),
                    language_code=data.get("language_code"),
                )
            else:
                result["stt"]["safe_error"] = stt.json().get("detail", "Request failed")
    except (wave.Error, EOFError):
        result["stt"] = {"skipped": "TTS WAV container could not be decoded locally"}
else:
    result["tts"]["safe_error"] = response.json().get("detail", "Request failed")
    result["stt"] = {"skipped": "TTS failed; no additional request was made"}
passed = (
    result["tts"].get("provider_http_status") == 200
    and result["stt"].get("provider_http_status") == 200
)
result["status"] = "PASS" if passed else "NOT_VERIFIED"
report = root / "demo/verification/sarvam-voice.json"
report.write_text(json.dumps(result, indent=2))
md = [
    "# Final minimal Sarvam speech test",
    "",
    f"**{result['status']}** · {result['live_calls_attempted']} live request attempts · no retries · no chat calls.",
    "",
    f"Input: `{text}` ({len(text)} characters).",
    "",
    "```json",
    json.dumps(result, indent=2),
    "```",
    "",
    result["limitations"],
    "",
    "Credentials were read server-side from a private file outside the project and are excluded from source, recordings and the release archive. Voice remains off by default to avoid unattended credit use.",
]
(root / "docs/VOICE_TEST.md").write_text("\n".join(md) + "\n")
print(json.dumps(result, indent=2))
