# Final minimal Sarvam speech test

**NOT_VERIFIED** · 1 live request attempts · no retries · no chat calls.

Input: `Pi voice is ready.` (22 characters).

```json
{
  "test": "One short TTS followed by STT of that same WAV; no retries or chat calls.",
  "input_text": "Pi voice is ready.",
  "characters": 22,
  "tts": {
    "app_http_status": 422,
    "elapsed_ms": 55.3,
    "model": "bulbul:v3",
    "safe_error": "Sarvam voice connection failed. No retry was made."
  },
  "stt": {
    "skipped": "TTS failed; no additional request was made"
  },
  "live_calls_attempted": 1,
  "limitations": "Generated English audio roundtrip only. Microphone, Hinglish, Marathi/Hindi and real bill-asking accuracy are not verified.",
  "status": "NOT_VERIFIED"
}
```

Generated English audio roundtrip only. Microphone, Hinglish, Marathi/Hindi and real bill-asking accuracy are not verified.

Credentials were read server-side from a private file outside the project and are excluded from source, recordings and the release archive. The private test credential was deleted after the release audit. Voice remains off by default to avoid unattended credit use.

## Offline continuation — 2026-10-03

The original speech client used `trust_env=False` without an explicit proxy, so it ignored the HTTP(S) proxy configured in the execution environment. The adapter now selects HTTP(S) proxy configuration explicitly, respects `NO_PROXY`, ignores unrelated `ALL_PROXY` SOCKS settings, and accepts an optional `SARVAM_HTTP_PROXY` override. An explicitly empty override selects direct access. Mock/configuration tests cover these branches without network or credentials.

This environment's advertised network allowlist does not include `api.sarvam.ai`. The proxy fix does not change that policy. No additional live request was made, no credential was reused, and the provider/key remain **NOT_VERIFIED**. The original one-attempt result above is unchanged.

Reference: https://www.python-httpx.org/environment_variables/ and https://www.python-httpx.org/advanced/proxies/.

## Live check - 2026-10-03 (later)

With a Sarvam key supplied by the project owner and `SARVAM_VOICE_ENABLED=true`, one TTS request (`Pi voice is ready. Oats need restocking.`, English) returned 79 KB of valid WAV in about 0.9 s, and one STT request on that same audio returned `Pi Voice is ready. Ports need restocking.` with `en-IN` at probability 1.0 (Oats was heard as "Ports"). So the adapter, key and network path now work end to end for English generated audio. Still unverified: real microphone input, Hinglish/Hindi/Marathi speech, noisy shop conditions and spoken questions about real bills. Text chat with Sarvam-105B tool calling was also exercised live the same day on about ten English, Hindi and Hinglish questions; no accuracy rate is claimed from that.