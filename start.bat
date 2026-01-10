@echo off
title Agent Terminal
cd /d D:\code\agent-terminal

echo.
echo  ========================================
echo    Agent Terminal - Multi-Agent CLI
echo  ========================================
echo.

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

:: Open browser after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8090"

:: Start server
python server.py

pause
