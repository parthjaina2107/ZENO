@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
set "PYTHONW_EXE=%~dp0.venv\Scripts\pythonw.exe"

if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
    set "PYTHONW_EXE=pythonw"
)

if "%1"=="--background" (
    shift
    start "" "%PYTHONW_EXE%" main.py --mode all %*
) else if "%1"=="-b" (
    shift
    start "" "%PYTHONW_EXE%" main.py --mode all %*
) else (
    "%PYTHON_EXE%" main.py %*
)
