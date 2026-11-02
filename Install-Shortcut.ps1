$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
$assetDir = Join-Path $appRoot 'assets'
New-Item -ItemType Directory -Path $assetDir -Force | Out-Null
$iconFile = Join-Path $assetDir 'circuit-studio.ico'
Add-Type -AssemblyName System.Drawing
$bitmap = New-Object System.Drawing.Bitmap 64,64
$g = [System.Drawing.Graphics]::FromImage($bitmap)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::Transparent)
$shape = New-Object System.Drawing.Drawing2D.GraphicsPath
$shape.AddArc(1,1,23,23,180,90); $shape.AddArc(40,1,23,23,270,90)
$shape.AddArc(40,40,23,23,0,90); $shape.AddArc(1,40,23,23,90,90); $shape.CloseFigure()
$brush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(38,63,56))
$g.FillPath($brush,$shape)
$pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(246,250,247)),3
$g.DrawRectangle($pen,24,24,16,16)
$g.DrawEllipse($pen,10,10,14,14);$g.DrawEllipse($pen,40,10,14,14)
$g.DrawEllipse($pen,10,40,14,14);$g.DrawEllipse($pen,40,40,14,14)
$g.DrawLine($pen,24,17,24,47);$g.DrawLine($pen,40,17,40,47)
$g.DrawLine($pen,17,24,47,24);$g.DrawLine($pen,17,40,47,40)
$icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
$stream = [System.IO.File]::Create($iconFile)
try {$icon.Save($stream)} finally {$stream.Dispose();$g.Dispose();$bitmap.Dispose();$pen.Dispose();$brush.Dispose();$shape.Dispose()}
$shell = New-Object -ComObject WScript.Shell
$desktopPath = [Environment]::GetFolderPath('Desktop')
$targets = @((Join-Path (Split-Path $appRoot -Parent) 'Circuit Studio.lnk'),(Join-Path $desktopPath 'Circuit Studio.lnk'))
foreach ($shortcutPath in $targets) {
    if (Test-Path -LiteralPath $shortcutPath) {
        $prior = $shell.CreateShortcut($shortcutPath)
        if ($prior.Arguments -notlike ('*' + $appRoot + '*')) { throw "Refusing to replace unrelated shortcut: $shortcutPath" }
    }
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $appRoot 'Start.ps1') + '"'
    $shortcut.WorkingDirectory = $appRoot
    $shortcut.IconLocation = $iconFile + ',0'
    $shortcut.Description = 'Circuit Studio - local Virtuoso circuit tutor'
    $shortcut.Save()
    Write-Output $shortcutPath
}
