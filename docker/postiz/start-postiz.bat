@echo off
echo Starting Postiz Docker Stack...
cd /d "%~dp0"
docker compose up -d
echo.
echo Postiz stack is starting.
echo Access Postiz UI at: http://localhost:4007
echo.
pause
