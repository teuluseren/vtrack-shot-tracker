@echo off
setlocal
cd /d "%~dp0.."
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher ^(py^) was not found.
  pause
  exit /b 1
)
py -3 "%~dp0..\vtrack_shot_tracker.py" review
if errorlevel 1 pause
