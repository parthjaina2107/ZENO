@echo off
setlocal
cd /d "%~dp0\.."

set "TASK_NAME=ZENO_Assistant"
set "LAUNCH_CMD=\"%~dp0..\start_zeno.bat\" --background"

echo Registering Windows Task Scheduler entry for %TASK_NAME%...
schtasks /Create /TN "%TASK_NAME%" /TR "%LAUNCH_CMD%" /SC ONLOGON /RL HIGHEST /F

if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] %TASK_NAME% successfully registered to start at login without a terminal.
) else (
    echo [INFO] Retrying with standard user privileges...
    schtasks /Create /TN "%TASK_NAME%" /TR "%LAUNCH_CMD%" /SC ONLOGON /F
)
