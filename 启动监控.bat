@echo off
chcp 65001 >nul
title position.json 自动监控器
echo ====================================
echo   position.json 自动监控器
echo ====================================
echo.
echo  修改 position.json 后自动更新表格和网页
echo  关闭此窗口即停止监控
echo.
cd /d "%~dp0"
.\venv\Scripts\python watchdog.py
pause
