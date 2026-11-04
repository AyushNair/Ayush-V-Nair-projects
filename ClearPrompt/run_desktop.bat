@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating the project environment...
  py -m venv .venv
  if errorlevel 1 goto failed
)
echo Starting ClearPrompt desktop app...
.venv\Scripts\python.exe desktop_app.py
if errorlevel 1 goto failed
goto end
:failed
echo.
echo ClearPrompt could not start. Check that Python 3.10 or newer is installed.
pause
:end
endlocal
