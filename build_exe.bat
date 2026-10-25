@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo 首次构建：创建虚拟环境...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --isolated -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
)

".venv\Scripts\python.exe" -m pip install --isolated -i https://pypi.tuna.tsinghua.edu.cn/simple pyinstaller pillow
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "MC客户端构建器" --icon "assets\icon.ico" --add-data "assets;assets" app.py

echo.
echo 构建完成：dist\MC客户端构建器.exe
pause
