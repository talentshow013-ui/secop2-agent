@echo off
title SECOP2 Agent
cd /d "%~dp0"

echo.
echo  ===================================================
echo   SECOP2 Agent - monitoreo SECOP II + Telegram
echo  ===================================================
echo.

call .venv\Scripts\activate.bat
echo  Iniciando bot Telegram y programador (08:00 / 14:00 / 20:00)...
echo.
python main.py
