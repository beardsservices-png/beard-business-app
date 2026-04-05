@echo off
echo Creating desktop shortcuts for Beard's Home Services...

:: Get the folder this script lives in
set APP_DIR=%~dp0
:: Remove trailing backslash
if "%APP_DIR:~-1%"=="\" set APP_DIR=%APP_DIR:~0,-1%

:: Get Desktop path
for /f "tokens=*" %%i in ('powershell -command "[Environment]::GetFolderPath(\"Desktop\")"') do set DESKTOP=%%i

:: ── Shortcut 1: Main App ──────────────────────────────────────────────────────
powershell -command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\Beards Home Services.lnk'); $s.TargetPath = '%APP_DIR%\start_app.bat'; $s.WorkingDirectory = '%APP_DIR%'; $s.WindowStyle = 7; $s.IconLocation = 'shell32.dll,13'; $s.Description = 'Open Beards Home Services App'; $s.Save()"

:: ── Shortcut 2: Day Wrap-Up ───────────────────────────────────────────────────
powershell -command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\Day Wrap-Up.lnk'); $s.TargetPath = '%APP_DIR%\start_wrapup.bat'; $s.WorkingDirectory = '%APP_DIR%'; $s.WindowStyle = 7; $s.IconLocation = 'shell32.dll,238'; $s.Description = 'End of day wrap-up for Beards Home Services'; $s.Save()"

echo.
echo  Done! Two shortcuts added to your desktop:
echo.
echo   "Beards Home Services"  -- opens the full app
echo   "Day Wrap-Up"           -- goes straight to the wrap-up form
echo.
echo  Double-click either one any time. If the app is already
echo  running it just opens your browser -- no duplicate windows.
echo.
pause
