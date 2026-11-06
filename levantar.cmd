@echo off
rem Lanzador de levantar.ps1 para Windows: no requiere cambiar la politica de ejecucion.
rem Uso: levantar.cmd [opciones]   (las mismas de levantar.sh; ver levantar.cmd --ayuda)
setlocal
where pwsh >/dev/null 2>nul
if %errorlevel%==0 (set "MS_PS=pwsh") else (set "MS_PS=powershell")
%MS_PS% -NoProfile -ExecutionPolicy Bypass -File "%~dp0levantar.ps1" %*
exit /b %errorlevel%
