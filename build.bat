@echo off
rem EXE を作る: dist\BlindIntervalPractice.exe
rem 必要なもの: pip install pyinstaller pillow
cd /d "%~dp0"
python tools\make_icon.py || exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name BlindIntervalPractice --icon icon.ico interval_trainer.pyw
