$ErrorActionPreference = 'Stop'
$workspace = $PSScriptRoot
$pidFile = Join-Path $workspace '.demo/server.pid'
if (Test-Path -LiteralPath $pidFile) {
    $serverId = [int](Get-Content -LiteralPath $pidFile)
    $server = Get-CimInstance Win32_Process -Filter "ProcessId=$serverId" -ErrorAction SilentlyContinue
    if ($server) {
        if ($server.CommandLine -notlike "*$workspace*" -or $server.CommandLine -notlike '*uvicorn*') { throw 'Refusing to stop a process outside this demo.' }
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$serverId" | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
        Stop-Process -Id $serverId -ErrorAction SilentlyContinue
    }
}
Write-Host 'Demo server stopped. Close the sharing terminal to stop its public tunnel.'
