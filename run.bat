@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo 首次运行：正在创建虚拟环境并安装依赖...
  python -m venv .venv
  if errorlevel 1 goto :err
  ".venv\Scripts\python.exe" -m pip install --isolated -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
  if errorlevel 1 goto :err
)
start "" ".venv\Scripts\pythonw.exe" app.py
exit /b 0

:err
echo.
echo 初始化失败：请确认已安装 Python 3.10+ 并勾选 Add to PATH。
pause
exit /b 1
