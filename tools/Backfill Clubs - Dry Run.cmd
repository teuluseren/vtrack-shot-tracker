@echo off
setlocal
cd /d "%~dp0"
py -3 "%~dp0backfill_vtrack_clubs.py"
pause
