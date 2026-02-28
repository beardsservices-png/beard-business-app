@echo off
title Beard's Home Services App
echo.
echo  ============================================
echo   Beard's Home Services - Starting App...
echo  ============================================
echo.

:: Start Flask API (backend)
start "Flask API" cmd /k "cd /d %~dp0 && python api\app.py"

:: Wait for Flask to be ready
timeout /t 2 /nobreak >nul

:: Start Vite frontend (with --host so phone can connect)
start "React Frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- --host"

:: Wait for Vite to start
timeout /t 3 /nobreak >nul

:: Get local IP for phone access
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4 Address"') do (
    set LOCAL_IP=%%a
    goto :found_ip
)
:found_ip
set LOCAL_IP=%LOCAL_IP: =%

echo.
echo  ============================================
echo   App is running!
echo  ============================================
echo.
echo   On this computer:
echo     http://localhost:5173
echo.
echo   On your phone (must be on same WiFi):
echo     http://%LOCAL_IP%:5173
echo.
echo  ============================================
echo   To stop: close the Flask API and
echo            React Frontend windows
echo  ============================================
echo.

:: Open browser automatically on this computer
start http://localhost:5173

pause
