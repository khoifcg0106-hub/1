@echo off
REM ============================================================
REM  Mark LIII - Windows build script
REM  Chay file nay TREN WINDOWS, trong thu muc goc cua repo
REM  (noi co main.py, ui.py, setup.py...)
REM ============================================================

echo [1/4] Tao virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo [2/4] Cai dat dependencies (setup.py tu loc theo Windows)...
python setup.py
pip install pyinstaller

echo [3/4] Dong goi thanh .exe (che do onedir - giu config/memory o dang file that)...
pyinstaller ^
  --name "MarkLIII" ^
  --windowed ^
  --onedir ^
  --icon "config\jarvis.ico" ^
  --add-data "config;config" ^
  --add-data "dashboard\static;dashboard\static" ^
  --add-data "core\prompt.txt;core" ^
  --add-data "plugins;plugins" ^
  --collect-all google.genai ^
  --collect-all sounddevice ^
  --hidden-import "win32com.client" ^
  --hidden-import "win32api" ^
  --hidden-import "win32con" ^
  main.py

echo [4/4] Xong! File .exe nam trong: dist\MarkLIII\MarkLIII.exe
echo Copy ca thu muc dist\MarkLIII sang may khac neu can - dung tach rieng file .exe.
pause
