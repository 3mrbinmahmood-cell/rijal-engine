@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (python extraction_launch.py --open) else (py -3 extraction_launch.py --open)
pause
