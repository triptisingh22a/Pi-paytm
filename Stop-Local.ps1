$ErrorActionPreference = 'Stop'
$statePath = Join-Path $PSScriptRoot 'local-logs\processes.json'
if (!(Test-Path $statePath)) { return }
$state = Get-Content $statePath | ConvertFrom-Json
foreach ($name in 'webListener','apiListener','web','api') {
    if (!$state.$name) { continue }
    $process = Get-Process -Id $state.$name -ErrorAction SilentlyContinue
    $started = $state."${name}Started"
    if ($process -and $process.StartTime.ToUniversalTime().ToString('o') -eq $started) { Stop-Process -Id $process.Id }
}
Remove-Item -LiteralPath $statePath
