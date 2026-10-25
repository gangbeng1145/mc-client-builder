@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0MC客户端构建器.exe" --netdiag "%~dp0netdiag.txt"
