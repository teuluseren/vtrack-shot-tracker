@echo off
setlocal
cd /d "%~dp0"
echo This updates only blank club/player-state columns in the existing archive DB.
echo It matches historical GSPro shot timestamps exactly.
echo.
set /p ok=Type YES to continue: 
if /I not "%ok%"=="YES" exit /b 0
py -3 "%~dp0backfill_vtrack_clubs.py" --apply
pause
