@echo off
setlocal
rem CMD and Explorer double-click entry point. Resolve the PS1 beside this file.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-PGOS.ps1" %*
set "pgos_exit=%errorlevel%"
if not "%pgos_exit%"=="0" (
    echo Personal Growth OS could not start. See the error above.
    pause
)
exit /b %pgos_exit%
