@echo off
chcp 65001 >nul
cd /d %~dp0
echo QQ Voice Bot v1.1 starting...
echo.
python qq-voice-bot.py
pause