$ErrorActionPreference = 'Stop'
$bridgeEnv = if ($env:CIRCUIT_BRIDGE_ENV) { $env:CIRCUIT_BRIDGE_ENV } else { Join-Path $PSScriptRoot 'bridge.env' }
$bridgeExe = Join-Path $PSScriptRoot '.venv\Scripts\virtuoso-bridge.exe'
if ($env:CIRCUIT_PYTHON_EXE) { $bridgeExe = Join-Path (Split-Path $env:CIRCUIT_PYTHON_EXE -Parent) 'virtuoso-bridge.exe' }
if (-not (Test-Path -LiteralPath $bridgeEnv)) { throw 'Configure bridge.env using bridge.env.example or virtuoso-bridge init first.' }
if (-not (Test-Path -LiteralPath $bridgeExe)) { throw 'Run Install.ps1 first.' }
# Standard upstream startup: establish/reuse tunnel and print the exact CIW load instruction.
# Starting a site-specific Virtuoso GUI process belongs in a private CIRCUIT_BRIDGE_LAUNCHER.
& $bridgeExe start --env $bridgeEnv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $bridgeExe eval '1+2' --env $bridgeEnv
exit $LASTEXITCODE
