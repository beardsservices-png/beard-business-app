@echo off
title Beard's Home Services App

:: Check if app is already running
powershell -command "try { Invoke-WebRequest -Uri 'http://localhost:5000/api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1

if %errorlevel%==0 (
    :: App already running - just open the browser
    start http://localhost:5173
    exit
)

:: App not running - start everything
echo.
echo  ============================================
echo   Beard's Home Services - Starting App...
echo  ============================================
echo.

:: Start Flask API in minimized window
start "Flask API" /min cmd /k "cd /d %~dp0 && python api\app.py"

:: Wait for Flask
timeout /t 2 /nobreak >nul

:: Start Vite frontend in minimized window
start "React Frontend" /min cmd /k "cd /d %~dp0frontend && npm run dev -- --host"

:: Wait for Vite
timeout /t 4 /nobreak >nul

:: Get local IP for phone access
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4 Address"') do (
    set LOCAL_IP=%%a
    goto :found_ip
)
:found_ip
set LOCAL_IP=%LOCAL_IP: =%

echo  App is running!
echo.
echo   Computer:  http://localhost:5173
echo   Phone:     http://%LOCAL_IP%:5173
echo.
echo  Two windows started (Flask API + React Frontend).
echo  Minimize them. Close them to stop the app.
echo.

:: Open browser
start http://localhost:5173

pause
