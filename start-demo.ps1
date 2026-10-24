param([switch]$Share)
$ErrorActionPreference = 'Stop'
$workspace = $PSScriptRoot
$runtimeDir = Join-Path $workspace '.demo'
$pythonExe = Join-Path $workspace '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Install backend dependencies in .venv first; see DEMO.md.' }
if (-not (Test-Path -LiteralPath (Join-Path $workspace 'frontend/dist/index.html'))) { throw 'Build the frontend first: cd frontend; npm ci; npm run build' }
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$pidFile = Join-Path $runtimeDir 'server.pid'
$running = $null
if (Test-Path -LiteralPath $pidFile) {
    $serverId = [int](Get-Content -LiteralPath $pidFile)
    $running = Get-CimInstance Win32_Process -Filter "ProcessId=$serverId" -ErrorAction SilentlyContinue
    if ($running -and ($running.CommandLine -notlike "*$workspace*" -or $running.CommandLine -notlike '*uvicorn*')) { throw 'Stored PID belongs to a different process. Inspect .demo/server.pid.' }
}
if (-not $running) {
    $server = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8080') `
        -WorkingDirectory (Join-Path $workspace 'backend') -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeDir 'server.log') `
        -RedirectStandardError (Join-Path $runtimeDir 'server-error.log') -PassThru
    $server.Id | Set-Content -LiteralPath $pidFile
}
Write-Host 'Application: http://127.0.0.1:8080'
Write-Host 'Demo credentials: .demo/access.json'
if ($Share) {
    Push-Location $runtimeDir
    try {
        Write-Host 'The public HTTPS address will appear below. Keep this terminal and the computer running.'
        & ssh.exe -T -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=known_hosts `
            -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 80:127.0.0.1:8080 nokey@localhost.run
    } finally { Pop-Location }
}
