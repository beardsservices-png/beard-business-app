@echo off
title Beard's - Day Wrap-Up

:: Check if app is already running
powershell -command "try { Invoke-WebRequest -Uri 'http://localhost:5000/api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1

if %errorlevel%==0 (
    :: App already running - just open the browser to Day Wrap-Up
    start http://localhost:5173/day-wrapup
    exit
)

:: App not running - start it, then open to Day Wrap-Up
start "Flask API" /min cmd /k "cd /d %~dp0 && python api\app.py"
timeout /t 2 /nobreak >nul
start "React Frontend" /min cmd /k "cd /d %~dp0frontend && npm run dev -- --host"
timeout /t 4 /nobreak >nul
start http://localhost:5173/day-wrapup
exit
