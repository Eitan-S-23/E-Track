@echo off
setlocal
cd /d "%~dp0"
if defined P34_PYTHON (
  "%P34_PYTHON%" -I -S -B -X utf8 Tools\ota\p34_session.py --root "%CD%" %*
) else (
  python -I -S -B -X utf8 Tools\ota\p34_session.py --root "%CD%" %*
)
exit /b %errorlevel%
