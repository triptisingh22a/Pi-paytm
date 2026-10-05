# Sarvam merchant agent — contract and verification

The merchant workspace now uses a Sarvam-only cascade: **Saaras v4 → Sarvam-105B → Bulbul v3**. This is application-orchestrated speech/text/speech, not a claim of native speech-to-speech support. Sarvam's public V1 chat reference recommends `sarvam-105b` for complex agentic tasks and lists `sarvam-105b-conversations` for voice/conversational workloads. We default to 105B; the conversation model can be selected explicitly after measuring routing accuracy and latency.

## What owns each decision

| Stage | Owner | Contract |
|---|---|---|
| Transcript | Saaras v4 + merchant review | `unknown` detects predominant language; original-language `transcribe`, no silent English translation. Merchant reviews before sending. |
| Language | STT metadata or Sarvam `/text-lid` | Explicit selection overrides auto detection. Text detection covers the 11 listed core languages; uncertain detection falls back to English. |
| Tool discovery | Application function registry | Catalogue, overview, inventory, peers, replace, recommend have separate descriptions and JSON schemas. Catalogue exposes canonical IDs, aliases and existing/candidate roles for the selected shop. |
| Tool selection | Sarvam-105B | Up to two planner calls: optional catalogue discovery, then one business tool. No model prose displayed. No retry, arbitrary SQL, payments, orders or loans. |
| Validation | Application | Strict types/bounds, no extra fields, no parallel calls, selected merchant fixed by server, exact canonical IDs and existing/candidate role checks. Missing/invalid products clarify or return a reviewable error. |
| Calculation | POS services and twin | Engines calculate all totals and scenario distributions. The planner cannot supply result numbers. |
| Explanation | Application | Input-bound English templates and calculation receipts pass numeric authorization. Execution trace identifies the tool and validated arguments. |
| Localization | Sarvam Translate v1 | At most one translation call, exact numeric/date multiset preservation plus receipt authorization; reject malformed or altered numbers. Canonical English retained for audit. Semantic fidelity is **not** proven by a numeric gate. |
| Speech | Bulbul v3 | Explicit Read aloud, using actual answer language. Failed/unsupported localization produces English with English TTS. |

STT supports English plus 22 Indic languages. Our end-to-end reply/TTS dropdown supports the intersection of English, Hindi, Marathi, Bengali, Gujarati, Kannada, Malayalam, Odia, Punjabi, Tamil and Telugu. A detected language outside that intersection is retained as requested language, with an explicit English reply fallback. Predominant-language detection is not per-word code-switch identification or guaranteed dialect recognition. No automatic microphone sending or automatic audio playback occurs.

The flow handles one supported merchant decision per send and is stateless. It does not yet execute arbitrary multi-tool plans or resolve implicit references to previous turns. Unsupported demographics, unknown products and requests to take external action must clarify. The local router is explicitly labeled when no configured key is available. Once a live planner is configured, a provider failure/invalid selection clarifies rather than silently invoking keyword routing and reporting model success.

## Credit budget

`SARVAM_CHAT_ENABLED=true` and a server-side `SARVAM_API_KEY` or private `SARVAM_API_KEY_FILE` enable chat. `SARVAM_VOICE_ENABLED=true` enables microphone/TTS separately. HTTP proxy controls are shared by text and speech.

Each manual send: at most one text-language request, two planner requests, one translation request. English with explicitly selected language and direct tool selection needs one planner request. Each microphone recording needs one STT call; each Read aloud needs one TTS call. No request is retried. Tool execution itself uses local synthetic data. The existing legacy Decision lab explanation adapter is separate from this merchant agent and is not the path evaluated here.

## Distinguish three kinds of evidence

1. **Deterministic tools:** POS reconciliation, twin accounting, receipt/number gates and service constraints are covered by the full backend tests.
2. **Mocked orchestration:** `api/tests/test_sarvam_agent.py` supplies fake provider wire responses. It verifies discovery tool messages, all five business tools, strict rejection, call budget, localized numeric rejection and original-language auto STT. It cannot measure whether Sarvam chooses the right tool for a natural-language question.
3. **Live model evaluation:** `eval/sarvam_tool_cases.json` holds ten English/Hindi/Marathi and adversarial cases with expected tools and numeric constraints. `eval/sarvam_tool_calls.py` compares actual model calls/arguments and executes the selected tool to check its receipt guard. `--limit` defaults to three; provider/contract failure stops further requests. Each case can use up to two planner requests. No translation/STT/TTS calls are made by this evaluator.

Run only in an environment with permitted Sarvam connectivity and a configured private credential:

```bash
SARVAM_CHAT_ENABLED=true python eval/sarvam_tool_calls.py --live --limit 3
```

Run without `--live` for a zero-call configuration check. Accuracy on a handful of cases is only a smoke test; full ten-case coverage, paraphrases, native-speaker review, product ambiguity, code mixing and recorded noisy microphone cases are needed before claiming reliable deployment. Schema validity does not imply intent correctness. Numeric authorization does not imply semantic truth.

**Live validation status for this revision: NOT RUN.** The execution environment restricts `api.sarvam.ai`; no Sarvam credential is configured. No provider request or credential reuse was made. The previously failed speech connectivity test remains historical evidence, not a text-model validation.

## Official references checked 2026-10-03

- [Chat Completion V1](https://docs.sarvam.ai/api-reference/chat/chat-completions-v1): models, function tools and tool choice.
- [STT REST](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe): Saaras v4, unknown-language detection, predominant-language output.
- [TTS REST](https://docs.sarvam.ai/api-reference/text-to-speech/convert): Bulbul v3, explicit language code and length limits.
- [Language detection](https://docs.sarvam.ai/api-reference/text/identify-language).
- [Translation](https://docs.sarvam.ai/api-reference/text/translate-text).


## Reply writing (added 2026-10-03)

The model no longer only picks a tool. After the tool runs, Pi sends the merchant's question and the tool's own answer (`TOOL_RESULT`) to `sarvam-105b-conversations` (override with `SARVAM_REPLY_MODEL`), which writes a short, conversational reply in the merchant's language. That reply is accepted only if every number and date in it is authorised by the tool's receipt (the numeric guard), it is under 900 characters, has no links, and was not cut off. Otherwise Pi falls back to the engine's own template (translated if the merchant wrote in another language). The tool's canonical English answer and receipt are always kept and shown under "Answer evidence". The planner stays on the reasoning model `sarvam-105b`; the reasoning model is not used for phrasing because it can spend its whole token budget thinking and return nothing.

Provider calls per question are now at most: language detection (Auto only), up to two planner calls, one reply call, and, only if the reply is rejected and the language is not English, one translation call. No retries. The guard checks numbers and dates, not meaning: it cannot prove a sentence says nothing misleading, which is why the canonical answer stays one tap away.