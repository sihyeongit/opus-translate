$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $projectRoot "run_opus_translate.bat"

$desktopCandidates = @(@(
    [Environment]::GetFolderPath("Desktop"),
    (Join-Path $env:USERPROFILE "OneDrive\Desktop"),
    (Join-Path $env:USERPROFILE "OneDrive\바탕 화면"),
    (Join-Path $env:USERPROFILE "Desktop")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique)

if (-not $desktopCandidates) {
    throw "Desktop folder not found."
}

$desktop = $desktopCandidates | Select-Object -First 1
$link = Join-Path $desktop "Opus Translate.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = "Launch Opus Translate"
$shortcut.IconLocation = "C:\Windows\System32\shell32.dll,220"
$shortcut.Save()

Write-Host "Created shortcut: $link"
