$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runtime = Get-Content (Join-Path $projectRoot 'local-runtime.json') | ConvertFrom-Json
$env:Path = "$(Split-Path $runtime.node);$projectRoot\.venv\Scripts;$env:Path"
$env:API_INTERNAL_URL = 'http://127.0.0.1:8000'
$env:DEMO_MODE = 'cached'
$env:PYTHONUTF8 = '1'
if (Test-Path "$projectRoot\.env") {
    foreach ($line in Get-Content "$projectRoot\.env") {
        if ($line -match '^([A-Z_]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') }
    }
}
New-Item -ItemType Directory -Force "$projectRoot\local-logs" | Out-Null
foreach ($port in 8000,3000) {
    $probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
    try { $probe.Start() } catch { throw "Port $port is already in use. Stop the existing server first." } finally { $probe.Stop() }
}
$api = Start-Process -FilePath "$projectRoot\.venv\Scripts\python.exe" -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory "$projectRoot\api" -WindowStyle Hidden -RedirectStandardOutput "$projectRoot\local-logs\api.log" -RedirectStandardError "$projectRoot\local-logs\api-error.log" -PassThru
$web = Start-Process -FilePath $runtime.node -ArgumentList 'node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1','--port','3000' -WorkingDirectory "$projectRoot\web" -WindowStyle Hidden -RedirectStandardOutput "$projectRoot\local-logs\web.log" -RedirectStandardError "$projectRoot\local-logs\web-error.log" -PassThru
$state = @{api=$api.Id;web=$web.Id;apiStarted=$api.StartTime.ToUniversalTime().ToString('o');webStarted=$web.StartTime.ToUniversalTime().ToString('o')}
foreach ($entry in @(@{name='apiListener';port=8000;kind='python';start=$api.StartTime},@{name='webListener';port=3000;kind='node';start=$web.StartTime})) {
    $ready = $false
    for ($attempt=0; $attempt -lt 100; $attempt++) {
        $row = netstat -ano -p tcp | Select-String "127\.0\.0\.1:$($entry.port)\s+.*LISTENING\s+(\d+)" | Select-Object -First 1
        if ($row) {
            $listener = Get-Process -Id ([int]$row.Matches[0].Groups[1].Value)
            if ($listener.ProcessName -eq $entry.kind -and $listener.StartTime -ge $entry.start) {
                $state[$entry.name]=$listener.Id
                $state["$($entry.name)Started"]=$listener.StartTime.ToUniversalTime().ToString('o')
                $ready=$true
                break
            }
        }
        Start-Sleep -Milliseconds 200
    }
    if (!$ready) { $state | ConvertTo-Json | Set-Content "$projectRoot\local-logs\processes.json"; throw "Server on port $($entry.port) did not start. See local-logs." }
}
$state | ConvertTo-Json | Set-Content "$projectRoot\local-logs\processes.json"
Write-Output 'Demo: http://localhost:3000 | API docs: http://localhost:8000/docs'
