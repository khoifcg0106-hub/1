@echo off
REM ============================================================
REM  Mark LIII - Launcher: double-click file nay de mo app
REM  (Chay setup.ps1 mot lan truoc do de cai dat)
REM ============================================================
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Chua thay venv. Hay chay setup.ps1 truoc ^(chuot phai -^> Run with PowerShell^).
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python main.py
pause
