@echo off
setlocal
cd /d "%~dp0"
REM Prefer a known-supported Python runtime; no fragile venv/ensurepip step.
where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 --version >nul 2>nul
  if not errorlevel 1 (
    set "PYRUN=py -3.12"
  )
)
if not defined PYRUN set "PYRUN=python"
%PYRUN% --version >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 is required. Install it from python.org or use GitHub Codespaces.
  pause
  exit /b 1
)
%PYRUN% -m pip --version >nul 2>nul
if errorlevel 1 (
  echo pip is not available. Use GitHub Codespaces if your local Python installation is incomplete.
  pause
  exit /b 1
)
%PYRUN% -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Try Codespaces or check the error above.
  pause
  exit /b 1
)
%PYRUN% run.py
if errorlevel 1 echo Application stopped with an error. See the message above.
pause
