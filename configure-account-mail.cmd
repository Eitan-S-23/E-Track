@echo off
setlocal
cd /d "%~dp0"
title E-Track QQ Mail Setup
python -I -S -B Tools\cloudflare\configure_account_mail.py --configure
set "RESULT=%ERRORLEVEL%"
echo.
echo Please tell the agent the result above. Do not send the authorization code.
pause
exit /b %RESULT%
