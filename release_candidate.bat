@echo off
setlocal
cd /d "%~dp0"
python -I -S -B -X utf8 Tools\ota\release_candidate.py %*
exit /b %errorlevel%
