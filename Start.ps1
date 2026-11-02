param([switch]$NoWindow)
$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
$runtimeDir = Join-Path $appRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$launchMutex = New-Object System.Threading.Mutex($false, 'Local\CircuitStudioLauncher')
$hasLock = $false
try {
    $hasLock = $launchMutex.WaitOne(20000)
    if (-not $hasLock) { throw 'Another Circuit Studio launcher is still starting.' }
    $pythonExe = if ($env:CIRCUIT_PYTHON_EXE) { $env:CIRCUIT_PYTHON_EXE } else { Join-Path $appRoot '.venv\Scripts\python.exe' }
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        if ($env:CIRCUIT_PYTHON_EXE) { throw 'CIRCUIT_PYTHON_EXE does not exist.' }
        $pythonExe = Join-Path (Split-Path $appRoot -Parent) 'virtuoso-bridge-lite\.venv\Scripts\python.exe'
    }
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Python environment is missing. Run Install.ps1 first.' }
    $isReady = $false
    try { $isReady = (Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 2).app -eq 'Circuit Studio' } catch {}
    if (-not $isReady) {
        $serverFile = Join-Path $appRoot 'server.py'
        $serverProcess = Start-Process -FilePath $pythonExe -ArgumentList @('"' + $serverFile + '"','--port','8765') -WorkingDirectory $appRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'server.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'server.stderr.log')
        $serverProcess.Id | Set-Content -LiteralPath (Join-Path $runtimeDir 'server.pid')
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Milliseconds 300
            try { $isReady = (Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 2).app -eq 'Circuit Studio' } catch {}
            if ($isReady) { break }
            if ($serverProcess.HasExited) { throw 'Local service failed to start. See runtime/server.stderr.log.' }
        }
    }
    if (-not $isReady) { throw 'Local service is not ready. Port 8765 may be occupied.' }
    if (-not $NoWindow) {
        $edgeExe = Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'
        if (Test-Path -LiteralPath $edgeExe) {
            Start-Process -FilePath $edgeExe -ArgumentList @('--app=http://127.0.0.1:8765','--window-size=1540,1080')
        } else { Start-Process 'http://127.0.0.1:8765' }
    }
    Write-Output 'Circuit Studio: http://127.0.0.1:8765'
} catch {
    $_ | Out-String | Add-Content -LiteralPath (Join-Path $runtimeDir 'launcher-error.log')
    if ($NoWindow) { throw }
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(('Circuit Studio could not start.' + [Environment]::NewLine + $_.Exception.Message + [Environment]::NewLine + 'Log: ' + (Join-Path $runtimeDir 'launcher-error.log')), 'Circuit Studio', 'OK', 'Error') | Out-Null
    exit 1
} finally {
    if ($hasLock) { $launchMutex.ReleaseMutex() }
    $launchMutex.Dispose()
}
