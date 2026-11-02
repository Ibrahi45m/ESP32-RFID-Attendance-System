@echo off
cd /d "%~dp0"
REM full = toute la seance ; half = premiere moitie ; 15 = premieres 15 minutes
set "RFID_SCAN_WINDOW=half"
set "RFID_PORT=COM7"
python rfid_auto_worker.py
if errorlevel 1 pause
