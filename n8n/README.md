# n8n orchestration exports

Four inactive native-format exports are provided. HTTP, Schedule, Webhook and Manual Trigger parameter names were inspected in the published `n8n-nodes-base@2.15.1` package before writing these files. They have not been imported or executed in n8n in this environment.

Start the optional container with `docker compose --profile automation up --build`. Open http://localhost:5678, finish local owner setup, import each JSON, inspect URLs, and activate only after testing. The `api` hostname works on the Compose network. No credentials are embedded.

- `daily_briefing`: daily 09:00 Asia/Kolkata → receipt → Telegram live or preview. Voice/TTS delivery is not implemented.
- `restock_alert`: daily check → only create proposal when forecast cover < supplier lead time and a profitable cash-safe action exists.
- `approval_action`: Telegram Update webhook → forward secret header/body → API validates secret, allowed chat, expiry, and single-use proposal. An approval sets a synthetic pending action only.
- `outcome_measure`: manual trigger → +7 simulated days → paired outcome → SQL memory. This does not claim observed real outcomes or an automatic elapsed-time job.

For live Telegram, configure `DEMO_MODE=live`, bot token, private chat ID and webhook secret in API environment. The Docker Compose default leaves those empty; set them in your local .env before testing live operation. Register the Telegram webhook yourself using its official `setWebhook` endpoint and `secret_token`. A public HTTPS endpoint/tunnel is required; none is provisioned. Default UI approval is the fully verified fallback. Do not expose the otherwise unauthenticated demo API to the internet.

The webhook token is passed through, not stored in export JSON. Never put bot tokens in node parameters. The API binds approvals to a stored proposal ID and allowed chat, and consumes them atomically. No lending, real restock or WhatsApp action is executed.
