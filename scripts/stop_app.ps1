$ErrorActionPreference = 'Continue'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$state = Join-Path $root '.run-state'
foreach ($name in @('frontend','api')) {
    $pidFile = Join-Path $state "$name.pid"
    if (Test-Path $pidFile) {
        $processId = [int](Get-Content $pidFile -Raw).Trim()
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) { Stop-Process -Id $processId -ErrorAction SilentlyContinue; Write-Host "Stopped $name process ($processId)." }
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    }
}
