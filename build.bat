@echo off
rem Build the EXE: dist\BlindIntervalPractice.exe
rem Requires: pip install pyinstaller pillow
rem (Comments are ASCII on purpose: cmd misreads UTF-8 text in .bat files.)
setlocal
cd /d "%~dp0"
set "NAME=BlindIntervalPractice"
set "WORK=%TEMP%\%NAME%_build"

python tools\make_icon.py || exit /b 1

rem Build in %TEMP%: synced folders (OneDrive) can't be cleaned, and an open EXE can't be overwritten
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --workpath "%WORK%" --specpath "%WORK%" --distpath "%WORK%\dist" ^
  --name %NAME% --icon "%~dp0icon.ico" interval_trainer.pyw || exit /b 1

if not exist dist mkdir dist
rem Remove EXEs moved aside by earlier builds (ones still running stay until next time)
del /q "dist\%NAME%.old-*.exe" 2>nul
rem A running EXE can't be overwritten but can be renamed, so if the copy fails move it aside and retry
copy /y "%WORK%\dist\%NAME%.exe" "dist\%NAME%.exe" >nul 2>nul || (ren "dist\%NAME%.exe" "%NAME%.old-%RANDOM%.exe" && copy /y "%WORK%\dist\%NAME%.exe" "dist\%NAME%.exe" >nul) || exit /b 1
echo Built: dist\%NAME%.exe
