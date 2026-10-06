# ============================================================
#  Mark LIII - PowerShell setup script (chay 1 lan duy nhat)
#  Cach chay: chuot phai vao file nay -> "Run with PowerShell"
#  Neu bao loi "chan script" thi mo PowerShell (khong can Admin) roi go:
#      Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#  sau do chay lai file nay.
# ============================================================

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "[1/3] Kiem tra Python..." -ForegroundColor Cyan
try {
    python --version
} catch {
    Write-Host "Khong tim thay Python. Cai Python 3.11/3.12 tu python.org truoc (nho tick 'Add to PATH')." -ForegroundColor Red
    Read-Host "Nhan Enter de thoat"
    exit 1
}

Write-Host "[2/3] Tao virtual environment (venv)..." -ForegroundColor Cyan
if (-Not (Test-Path ".\venv")) {
    python -m venv venv
}
.\venv\Scripts\Activate.ps1

Write-Host "[3/3] Cai dat thu vien (setup.py tu loc theo Windows)..." -ForegroundColor Cyan
python setup.py

Write-Host ""
Write-Host "XONG! Dung tu day, chi can double-click 'Run_MarkLIII.bat' de mo app." -ForegroundColor Green
Read-Host "Nhan Enter de dong"
