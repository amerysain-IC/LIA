param([string]$PythonExe = 'python')
$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
$venvPython = Join-Path $appRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $PythonExe -m venv (Join-Path $appRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create Python environment. Install Python 3.10+ first.' }
}
& $venvPython -m pip install -r (Join-Path $appRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check Git and network access to GitHub.' }
Push-Location $appRoot
try {
    & $venvPython -c 'import bridge_service'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency verification failed.' }
} finally { Pop-Location }
Write-Output 'Circuit Studio dependencies ready.'
Write-Output 'Next: configure bridge.env, then double-click Launch.cmd. See README.md.'
