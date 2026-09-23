@echo off
rem Double-click to open the HåkonBench dashboard in your browser.
rem Close this window to stop the server.
cd /d "%~dp0"
python dashboard.py %*
if errorlevel 1 pause
