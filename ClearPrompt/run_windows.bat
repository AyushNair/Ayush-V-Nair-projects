@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating the project environment...
  py -m venv .venv
  if errorlevel 1 goto failed
)

echo Checking project dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo.
echo ClearPrompt is starting at http://127.0.0.1:5000
echo Keep this window open while using the app. Press Ctrl+C to stop it.
echo.
.venv\Scripts\python.exe app.py
goto end

:failed
echo.
echo Setup failed. Check that Python 3.10 or newer is installed and internet is available for the first install.
pause

:end
endlocal
