@echo off
title SECOP2 Agent — Vector Pro Services
cd /d "%~dp0"

echo.
echo  ===================================================
echo   SECOP2 Agent — Vector Pro Services S.A.S.
echo  ===================================================
echo.

:: Activa el entorno virtual
call .venv\Scripts\activate.bat

:: Inicia el API del dashboard en una ventana separada
start "SECOP2 Dashboard API" cmd /k "cd /d "%~dp0" && call .venv\Scripts\activate.bat && python dashboard_api.py"

:: Espera 2 segundos para que el API arranque
timeout /t 2 /nobreak >nul

:: Abre el dashboard en el navegador
start "" "dashboard.html"

:: Inicia el bot en esta ventana
echo  Iniciando bot Telegram...
echo  Dashboard: http://localhost:8000
echo  Credenciales: las de DASHBOARD_USER / DASHBOARD_PASS en .env
echo.
python main.py
