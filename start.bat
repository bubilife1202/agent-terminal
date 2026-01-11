@echo off
setlocal EnableDelayedExpansion
title Agent Terminal
cd /d "%~dp0"

:: Check if this is a restart (flag file exists)
if exist ".restart-flag" (
    del ".restart-flag" >nul 2>&1
    echo  [Restarted] Resuming server...
    goto START_SERVER
)

echo.
echo  ========================================
echo    Agent Terminal - Multi-Agent CLI
echo  ========================================
echo.

:: Check if Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found in PATH
    echo  Please install Python or add it to PATH
    pause
    exit /b 1
)

:: Check if server.py exists
if not exist "server.py" (
    echo  ERROR: server.py not found
    pause
    exit /b 1
)

:: Kill existing process on port 8090
echo  Checking for existing sessions...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8090 ^| findstr LISTENING') do (
    echo  Killing existing process: %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo  Starting server on http://localhost:8090
echo  Press Ctrl+C to stop
echo.

:: Open browser after 2 seconds (only on first start)
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8090"

:START_SERVER
:: Run server
python server.py

:: Check for new-console restart flag
if exist ".restart-new-console" (
    echo.
    echo  [%TIME%] Restarting in new console...
    del ".restart-new-console" >nul 2>&1
    :: Create restart flag for new console
    echo restart > ".restart-flag"
    :: Start new console and exit this one completely
    start "Agent Terminal" cmd /k "cd /d "%~dp0" && call "%~f0""
    exit
)

:: Normal restart (server crashed)
echo.
echo  [%TIME%] Server stopped. Press any key to restart or Ctrl+C to exit.
pause >nul
goto START_SERVER
