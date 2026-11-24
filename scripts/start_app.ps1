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

$api = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory (Join-Path $root 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs 'api.log') -RedirectStandardError (Join-Path $logs 'api-error.log')
$ui = Start-Process -FilePath $node -ArgumentList @($vite,'--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $root 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs 'frontend.log') -RedirectStandardError (Join-Path $logs 'frontend-error.log')
Set-Content -Path (Join-Path $state 'api.pid') -Value $api.Id
Set-Content -Path (Join-Path $state 'frontend.pid') -Value $ui.Id

$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try { Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 1 | Out-Null; $ready = $true; break } catch { }
    if ($api.HasExited -or $ui.HasExited) { break }
}
if (-not $ready) { & (Join-Path $PSScriptRoot 'stop_app.ps1'); throw "Services did not become ready. Review logs in $logs." }
Start-Process 'http://localhost:5173'
Write-Host 'Student Form Digitizer is running at http://localhost:5173'
Write-Host 'API docs: http://127.0.0.1:8000/docs'
Write-Host 'Run stop_app.bat to stop these services.'
