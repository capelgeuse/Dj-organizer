@echo off
setlocal
cd /d "%~dp0"
if exist "..\.venv\Scripts\pythonw.exe" (
    start "" "..\.venv\Scripts\pythonw.exe" "%~dp0CapelHouse_Qt.py"
    exit /b 0
)
if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" "%~dp0CapelHouse_Qt.py"
    if errorlevel 1 (pause & exit /b 1)
    exit /b 0
)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0CapelHouse_Qt.py"
    exit /b 0
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "%~dp0CapelHouse_Qt.py"
    if errorlevel 1 (pause & exit /b 1)
    exit /b 0
)
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        py -3 "%~dp0CapelHouse_Qt.py"
        if errorlevel 1 (pause & exit /b 1)
        exit /b 0
    )
)
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; assert sys.version_info.major == 3" >nul 2>&1
    if not errorlevel 1 (
        python "%~dp0CapelHouse_Qt.py"
        if errorlevel 1 (pause & exit /b 1)
        exit /b 0
    )
)
echo No se encontro Python 3. Instala Python 3 y ejecuta Instalar_CapelHouse.bat.
pause
exit /b 1
