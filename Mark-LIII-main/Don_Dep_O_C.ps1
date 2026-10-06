# ============================================================
#  Don dep o C: - CHI xoa file rac/tam, KHONG dung cham vao
#  Desktop, Documents, Downloads hay bat ky file ca nhan nao.
#  Cach chay: chuot phai vao file nay -> "Run with PowerShell"
# ============================================================

$ErrorActionPreference = "SilentlyContinue"

function Get-FreeGB {
    $d = Get-PSDrive C
    return [math]::Round($d.Free / 1GB, 2)
}

Write-Host "Dung luong trong truoc khi don: $(Get-FreeGB) GB" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/5] Don Thung rac..." -ForegroundColor Yellow
Clear-RecycleBin -DriveLetter C -Force

Write-Host "[2/5] Don file tam cua user (%TEMP%)..." -ForegroundColor Yellow
Remove-Item -Path "$env:TEMP\*" -Recurse -Force

Write-Host "[3/5] Don file tam he thong (C:\Windows\Temp)..." -ForegroundColor Yellow
Remove-Item -Path "C:\Windows\Temp\*" -Recurse -Force

Write-Host "[4/5] Don cache Windows Update da tai ve (se tu tai lai khi can)..." -ForegroundColor Yellow
Stop-Service -Name wuauserv -Force
Remove-Item -Path "C:\Windows\SoftwareDistribution\Download\*" -Recurse -Force
Start-Service -Name wuauserv

Write-Host "[5/5] Don cache trinh duyet Edge/Chrome (khong dong lai lich su/mat khau da luu)..." -ForegroundColor Yellow
$edgeCache = "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache"
$chromeCache = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache"
if (Test-Path $edgeCache)   { Remove-Item -Path "$edgeCache\*" -Recurse -Force }
if (Test-Path $chromeCache) { Remove-Item -Path "$chromeCache\*" -Recurse -Force }

Write-Host ""
Write-Host "Dung luong trong sau khi don: $(Get-FreeGB) GB" -ForegroundColor Green
Write-Host ""
Write-Host "XONG. File Desktop/Documents/Downloads va du lieu ca nhan khong bi dong den." -ForegroundColor Green
Read-Host "Nhan Enter de dong"
