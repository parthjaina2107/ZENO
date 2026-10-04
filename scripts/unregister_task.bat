@echo off
setlocal

set "TASK_NAME=ZENO_Assistant"
echo Removing Windows Task Scheduler entry for %TASK_NAME%...
schtasks /Delete /TN "%TASK_NAME%" /F
if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] %TASK_NAME% Task Scheduler entry removed.
) else (
    echo [INFO] Task not found or already removed.
)
