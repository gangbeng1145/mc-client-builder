@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call run.bat
  exit /b %errorlevel%
)
".venv\Scripts\python.exe" app.py
echo.
echo 程序已退出，上面的信息可用于排查问题。
pause
