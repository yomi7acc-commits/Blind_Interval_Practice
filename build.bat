@echo off
rem EXE を作る: dist\BlindIntervalPractice.exe
rem 必要なもの: pip install pyinstaller pillow
cd /d "%~dp0"
python tools\make_icon.py || exit /b 1
rem 作業ファイルは %TEMP% に置く（OneDrive などの同期フォルダーだと削除できず失敗するため）
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --workpath "%TEMP%\BlindIntervalPractice_build" --specpath "%TEMP%\BlindIntervalPractice_build" ^
  --name BlindIntervalPractice --icon "%~dp0icon.ico" interval_trainer.pyw
