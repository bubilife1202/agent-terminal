@echo off
title Agent Terminal Server
cd /d D:\code\agent-terminal

echo ========================================
echo   Agent Terminal Server Starting...
echo ========================================
echo.

:: Check if port 8090 is in use and kill the process
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8090 ^| findstr LISTENING') do (
    echo Killing existing server process: %%a
    taskkill /PID %%a /F >nul 2>&1
)

timeout /t 1 /nobreak >nul

python server.py
