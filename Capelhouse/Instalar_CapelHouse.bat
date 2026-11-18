@echo off
setlocal
cd /d "%~dp0"
set "VENV_PATH=..\.venv"
if exist "%VENV_PATH%\Scripts\python.exe" goto install
if exist ".venv\Scripts\python.exe" (
    set "VENV_PATH=.venv"
    goto install
)
where py >nul 2>&1
if errorlevel 1 goto try_python
py -3 -c "import sys" >nul 2>&1
if errorlevel 1 goto try_python
py -3 -m venv "%VENV_PATH%"
if errorlevel 1 goto venv_error
goto install
:try_python
where python >nul 2>&1
if errorlevel 1 goto no_python
python -c "import sys; assert sys.version_info.major == 3" >nul 2>&1
if errorlevel 1 goto no_python
python -m venv "%VENV_PATH%"
if errorlevel 1 goto venv_error
:install
"%VENV_PATH%\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto install_error
echo Instalacion terminada. Abre Abrir_CapelHouse.bat para iniciar.
pause
exit /b 0
:no_python
echo No se encontro Python 3. Instalalo y vuelve a intentarlo.
pause
exit /b 1
:venv_error
echo No se pudo crear .venv. Comprueba Python y los permisos de esta carpeta.
pause
exit /b 1
:install_error
echo No se pudieron instalar las dependencias. Comprueba la conexion y el error anterior.
pause
exit /b 1
