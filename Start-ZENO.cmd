@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Create the project virtual environment and install requirements first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -c "import PySide6.QtWidgets" >nul 2>&1
if errorlevel 1 (
    echo Install requirements-desktop.txt in the project virtual environment first.
    pause
    exit /b 1
)
start "ZENO" ".venv\Scripts\pythonw.exe" main.py --desktop
