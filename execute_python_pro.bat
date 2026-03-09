@echo off
setlocal enabledelayedexpansion

:main
rem Inicializar un contador
set count=0

rem Listar archivos .py en el directorio actual
echo Listado de archivos Python:
for %%f in (*.py) do (
    set /a count+=1
    echo !count!: %%f
)

rem Comprobar si hay archivos .py
if %count%==0 (
    echo No se encontraron archivos .py en el directorio actual.
    pause
    exit /b
)

rem Preguntar al usuario por el número del archivo a ejecutar
set /p choice="Elige el número del archivo que deseas ejecutar: "

rem Comprobar si la elección es válida
if !choice! lss 1 (
    echo Opción no válida.
    goto main
)

if !choice! gtr %count% (
    echo Opción no válida.
    goto main
)

rem Obtener el nombre del archivo correspondiente
set index=0
for %%f in (*.py) do (
    set /a index+=1
    if !index! equ !choice! (
        set selected_file=%%f
    )
)

rem Ejecutar el archivo seleccionado con Python
echo Ejecutando el archivo: !selected_file!
python !selected_file!

rem Comprobar el código de salida del script
if errorlevel 1 (
    echo El script produjo un error. Presiona [E] para salir o cualquier otra tecla para volver a la lista.
    set /p option="Opción: "
    if /i "!option!"=="E" (
        exit /b
    ) else (
        goto main
    )
)

rem Esperar antes de volver al menú
pause
goto main