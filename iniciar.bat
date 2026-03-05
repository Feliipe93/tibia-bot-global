@echo off
chcp 65001 >nul 2>&1
title Tibia Auto Healer
color 0A

echo ===================================================
echo        ⚔️  TIBIA AUTO HEALER - Launcher
echo ===================================================
echo.

:: Ir al directorio del script
cd /d "%~dp0"

:: Verificar si existe el entorno virtual
if exist ".venv\Scripts\python.exe" (
    echo [OK] Entorno virtual encontrado.
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    echo [!] No se encontro entorno virtual .venv
    echo     Buscando Python en el sistema...
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python no encontrado. Instalalo desde python.org
        pause
        exit /b 1
    )
    set "PYTHON=python"
)

:: Verificar dependencias
echo.
echo Verificando dependencias...
%PYTHON% -c "import obsws_python, cv2, numpy, win32gui, win32api, keyboard, customtkinter, PIL" 2>nul
if errorlevel 1 (
    echo [!] Faltan dependencias. Instalando...
    echo.
    %PYTHON% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Fallo al instalar dependencias.
        echo Intenta manualmente: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo.
    echo [OK] Dependencias instaladas correctamente.
)
echo [OK] Todas las dependencias presentes.

:: Crear carpetas necesarias
if not exist "logs" mkdir logs
if not exist "debug" mkdir debug

:: Lanzar el bot
echo.
echo ===================================================
echo   Iniciando Tibia Auto Healer...
echo   F9  = Activar / Desactivar healer
echo   F10 = Cerrar el bot
echo ===================================================
echo.

%PYTHON% main.py

:: Si se cierra, pausar para ver errores
echo.
echo ===================================================
echo   Bot cerrado.
echo ===================================================
pause
