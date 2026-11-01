@echo off
rem OpenTransit H-1 daily refresh, run by the Windows scheduled task "OpenTransit H-1 daily refresh"
rem at 06:30 local. Runs from a frozen export of the repository (D:\ot\src-<commit>), never from a
rem working checkout. Steps, logs and stop-at-first-failure: deploy\aws\tools\daily_refresh.py.
setlocal
set ROOT=%~dp0..\..\..
if not exist D:\ot\logs mkdir D:\ot\logs
"C:\Users\nhenr\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe" run --project "%ROOT%\services\api" --locked python "%ROOT%\deploy\aws\tools\daily_refresh.py" %* >> D:\ot\logs\daily-scheduler.log 2>&1
echo %DATE% %TIME% exit %ERRORLEVEL% >> D:\ot\logs\daily-scheduler.log
exit /b %ERRORLEVEL%
