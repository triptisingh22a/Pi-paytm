# Windows local development

The current checkout is the updated Pi.zip (20,794,421 bytes, saved October 3, 2026).
The source, datasets, and release docs are extracted into this folder. The older source files were backed up before replacement.

From this folder in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-Local.ps1
```

Open http://localhost:3000 and choose Enter demo, or go directly to http://localhost:3000/demo.
API documentation: http://localhost:8000/docs. Logs: local-logs/.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Stop-Local.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\Test-Local.ps1
```

Tests require ports 3000/8000 free. The test script uses an isolated legacy database and starts/stops its own local browser-test servers. Browser journeys mutate synthetic inventory; backend billing fixtures are isolated. Start the demo again after tests.

Python dependencies are installed in .venv and JavaScript dependencies in web/node_modules. local-runtime.json records the bundled Node/pnpm paths on this machine. Use pnpm with web/pnpm-lock.yaml for this checkout. The archive's npm lock remains for provenance.

Windows Application Control blocked SQLAlchemy's compiled extension. The same version was installed using its supported pure-Python build, without changing system policy:

```powershell
$env:DISABLE_SQLALCHEMY_CEXT='1'
.\.venv\Scripts\python.exe -m pip install --no-cache-dir --force-reinstall --no-binary=sqlalchemy sqlalchemy==2.1.2
```

The start script reads ignored .env. Credentials remain empty, so local constrained chat works without paid calls. To use live Sarvam, configure SARVAM_API_KEY (or SARVAM_API_KEY_FILE), SARVAM_CHAT_ENABLED=true, SARVAM_CHAT_MODEL=sarvam-105b, SARVAM_VOICE_ENABLED=true, SARVAM_STT_MODEL=saaras:v4, and restart. Explicit sends/voice operations can then consume provider credits. Do not add keys to frontend variables.

See LOCAL-VERIFICATION.md for local test results and docs/SARVAM_AGENT.md for live evaluation instructions.

Repricing uses `data/pricing_pilot.sqlite3` (synthetic, created on first use or by `make seed`) and writes saved scenarios to `data/pricing_state.sqlite3`. Neither touches `billing.sqlite3`. `eval/pricing_pilot_truth.json` holds the generator's hidden truth for evaluation only.
