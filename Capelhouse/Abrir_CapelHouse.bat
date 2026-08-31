@echo off
set "PYTHON_EXE=C:\Users\LENOVO\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PYTHON_EXE%" (
  echo No se encontro Python 3.12 en la ruta configurada.
  pause
  exit /b 1
)
"%PYTHON_EXE%" "%~dp0CapelHouse_Qt.py"
if errorlevel 1 pause
