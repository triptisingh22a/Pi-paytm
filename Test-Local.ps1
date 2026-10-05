$ErrorActionPreference = 'Stop'
$runtime = Get-Content "$PSScriptRoot\local-runtime.json" | ConvertFrom-Json
$env:Path = "$(Split-Path $runtime.node);$PSScriptRoot\.venv\Scripts;$env:Path"
$env:PLAYWRIGHT_BROWSERS_PATH = [IO.Path]::GetFullPath("$PSScriptRoot\..\..\work\browsers")
$env:DEMO_MODE = 'cached'
$env:PYTHONUTF8 = '1'
$previousDatabase = $env:DATABASE_URL
New-Item -ItemType Directory -Force "$PSScriptRoot\local-logs" | Out-Null
$testDatabase = "$PSScriptRoot/local-logs/test-$([guid]::NewGuid().ToString('N')).db" -replace '\\','/'
$env:DATABASE_URL = "sqlite:///$testDatabase"
Push-Location "$PSScriptRoot\api"
try {
    python -m pytest --cov=engine --cov-report=term-missing --cov-fail-under=85 -q
    if ($LASTEXITCODE) { throw 'Backend tests failed' }
    python -m ruff check .
    if ($LASTEXITCODE) { throw 'Backend lint failed' }
    python -m mypy engine/receipts.py app/schemas.py twin/state.py
    if ($LASTEXITCODE) { throw 'Schema type checks failed' }
} finally { Pop-Location; $env:DATABASE_URL = $previousDatabase }
Push-Location "$PSScriptRoot\web"
try {
    node node_modules/typescript/bin/tsc --noEmit
    if ($LASTEXITCODE) { throw 'Frontend type check failed' }
    & "$PSScriptRoot\Start-Local.ps1"
    try {
        $env:E2E_REUSE_SERVER = '1'
        node node_modules/@playwright/test/cli.js test
        if ($LASTEXITCODE) { throw 'Browser journey failed' }
    } finally { & "$PSScriptRoot\Stop-Local.ps1" }
} finally { Pop-Location }
