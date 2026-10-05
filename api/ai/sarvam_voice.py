"""Explicitly invoked speech calls only. No retries or paid business-chat calls."""

import base64
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import proxy_bypass
import httpx

LANGUAGES = (
    "en-IN",
    "hi-IN",
    "mr-IN",
    "bn-IN",
    "gu-IN",
    "kn-IN",
    "ml-IN",
    "od-IN",
    "pa-IN",
    "ta-IN",
    "te-IN",
)
STT_LANGUAGES = (
    *LANGUAGES,
    "as-IN",
    "ur-IN",
    "ne-IN",
    "kok-IN",
    "ks-IN",
    "sd-IN",
    "sa-IN",
    "sat-IN",
    "mni-IN",
    "brx-IN",
    "mai-IN",
    "doi-IN",
    "unknown",
)


def key(feature="voice"):
    if os.getenv("SARVAM_" + feature.upper() + "_ENABLED", "false").lower() != "true":
        return ""
    value = os.getenv("SARVAM_API_KEY", "")
    file = os.getenv("SARVAM_API_KEY_FILE", "")
    if not value and file:
        try:
            value = Path(file).read_text().strip()
        except OSError:
            return ""
    return value


def status():
    return {
        "enabled": bool(key()),
        "provider": "Sarvam",
        "stt_model": os.getenv("SARVAM_STT_MODEL", "saaras:v4"),
        "tts_model": "bulbul:v3",
        "fallback": "Text chat; optional browser speech synthesis",
        "automatic_paid_calls": False,
    }


def client_options():
    """Honor HTTPS/HTTP proxies without accidentally loading unrelated SOCKS settings."""
    explicit = os.getenv("SARVAM_HTTP_PROXY")
    if explicit is not None:
        proxy = explicit.strip()
    elif proxy_bypass("api.sarvam.ai"):
        proxy = ""
    else:
        proxy = (
            os.getenv("https_proxy")
            or os.getenv("HTTPS_PROXY")
            or os.getenv("http_proxy")
            or os.getenv("HTTP_PROXY")
            or ""
        ).strip()
    options = {"timeout": 35, "trust_env": False}
    if proxy:
        parsed = urlsplit(proxy)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError(
                "Configure an HTTP(S) Sarvam proxy, or use an empty override for a direct connection."
            )
        options["proxy"] = proxy
    return options


def request(endpoint, feature="voice", **kwargs):
    credential = key(feature)
    if not credential:
        raise ValueError("Sarvam is not configured. Local text tools remain available.")
    try:
        with httpx.Client(**client_options()) as client:
            res = client.post(
                "https://api.sarvam.ai/" + endpoint, headers={"api-subscription-key": credential}, **kwargs
            )
        if res.status_code != 200:
            raise ValueError(f"Sarvam request returned HTTP {res.status_code}. No retry was made.")
        return res.json()
    except httpx.HTTPError:
        raise ValueError("Sarvam connection failed. No retry was made.") from None


def transcribe(audio, filename="recording.webm", content_type="audio/webm", language="unknown"):
    if language not in STT_LANGUAGES or not 44 <= len(audio) <= 4_000_000:
        raise ValueError("Choose a supported language and an audio file under 4 MB")
    if content_type.split(";")[0] not in (
        "audio/wav",
        "audio/x-wav",
        "audio/webm",
        "audio/mpeg",
        "audio/mp4",
        "audio/ogg",
    ):
        raise ValueError("Unsupported audio format")
    result = request(
        "speech-to-text",
        files={"file": (filename, audio, content_type)},
        data={
            "model": os.getenv("SARVAM_STT_MODEL", "saaras:v4"),
            "language_code": language,
            "mode": "transcribe",
        },
    )
    if not isinstance(result.get("transcript"), str):
        raise ValueError("Sarvam returned an invalid transcript")
    return {
        "transcript": result["transcript"],
        "language_code": result.get("language_code"),
        "language_probability": result.get("language_probability"),
        "tts_supported": result.get("language_code") in LANGUAGES,
        "request_id": result.get("request_id"),
        "provider": "Sarvam",
    }


def synthesize(text, language="en-IN"):
    if not 1 <= len(text) <= 2500 or language not in LANGUAGES:
        raise ValueError("Speech text must contain 1–2500 characters in a supported language")
    result = request(
        "text-to-speech",
        json={
            "text": text,
            "language_code": language,
            "model": "bulbul:v3",
            "speaker": "shubh",
            "speech_sample_rate": 16000,
            "output_audio_codec": "wav",
        },
    )
    try:
        audio = base64.b64decode(result["audios"][0], validate=True)
    except (ValueError, KeyError, IndexError, TypeError):
        raise ValueError("Sarvam returned invalid audio") from None
    if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise ValueError("Sarvam returned a non-WAV audio container")
    return audio, result.get("request_id")
