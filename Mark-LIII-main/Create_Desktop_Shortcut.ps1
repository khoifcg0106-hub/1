# ============================================================
#  Tao icon "Mark LIII" ngoai Desktop, tro thang vao Run_MarkLIII.bat
#  Chay 1 lan: chuot phai -> "Run with PowerShell"
# ============================================================
$ErrorActionPreference = "Stop"
$AppDir   = $PSScriptRoot
$Target   = Join-Path $AppDir "Run_MarkLIII.bat"
$IconPath = Join-Path $AppDir "config\jarvis.ico"
$Desktop  = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Mark LIII.lnk"

$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Target
$Shortcut.WorkingDirectory = $AppDir
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}
$Shortcut.Save()

Write-Host "Da tao icon 'Mark LIII' ngoai Desktop. Bam vao do la mo app." -ForegroundColor Green
Read-Host "Nhan Enter de dong"
