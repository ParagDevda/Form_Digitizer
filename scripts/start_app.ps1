param([ValidateRange(1024,65535)][int]$ApiPort = 8000, [ValidateRange(1024,65535)][int]$FrontendPort = 5173, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$node = (Get-Command node -ErrorAction SilentlyContinue).Source
$vite = Join-Path $root 'frontend\node_modules\vite\bin\vite.js'
$state = Join-Path $root '.run-state'
$logs = Join-Path $state 'logs'

if (-not (Test-Path $python)) { throw 'Backend environment missing. Follow the first-time setup in README.md.' }
if (-not $node -or -not (Test-Path $vite)) { throw 'Frontend dependencies missing. Run npm install in the frontend folder.' }
New-Item -ItemType Directory -Force -Path $logs | Out-Null

$api = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory (Join-Path $root 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs 'api.log') -RedirectStandardError (Join-Path $logs 'api-error.log')
$priorProxyTarget = $env:VITE_API_PROXY_TARGET
$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$ApiPort"
$ui = Start-Process -FilePath $node -ArgumentList @($vite,'--host','127.0.0.1','--port',"$FrontendPort",'--strictPort') -WorkingDirectory (Join-Path $root 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs 'frontend.log') -RedirectStandardError (Join-Path $logs 'frontend-error.log')
if ($null -eq $priorProxyTarget) { Remove-Item Env:\VITE_API_PROXY_TARGET -ErrorAction SilentlyContinue } else { $env:VITE_API_PROXY_TARGET = $priorProxyTarget }
Set-Content -Path (Join-Path $state 'api.pid') -Value $api.Id
Set-Content -Path (Join-Path $state 'frontend.pid') -Value $ui.Id

$ready = $false
$apiReady = $false
$uiReady = $false
$lastCheckError = 'Services are still starting.'
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try { Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/health" -TimeoutSec 2 | Out-Null; $apiReady = $true } catch { $lastCheckError = $_.Exception.Message }
    try { Invoke-WebRequest "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 2 | Out-Null; $uiReady = $true } catch { $lastCheckError = $_.Exception.Message }
    if ($apiReady -and $uiReady) { $ready = $true; break }
    if ($api.HasExited -or $ui.HasExited) { break }
}
if (-not $ready) { & (Join-Path $PSScriptRoot 'stop_app.ps1'); throw "Services did not become ready (API: $apiReady, frontend: $uiReady): $lastCheckError. Review logs in $logs." }
if (-not $NoBrowser) { Start-Process "http://localhost:$FrontendPort" }
Write-Host "Student Form Digitizer is running at http://localhost:$FrontendPort"
Write-Host "API docs: http://127.0.0.1:$ApiPort/docs"
Write-Host 'Run stop_app.bat to stop these services.'
