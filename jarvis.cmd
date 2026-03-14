@echo off
setlocal

set "PROJECT_ROOT=%~dp0"

if "%~1"=="" goto :usage

set "MODE=%~1"
shift
set "FORWARDED_ARGS="

:collect_args
if "%~1"=="" goto :dispatch
set "FORWARDED_ARGS=%FORWARDED_ARGS% "%~1""
shift
goto :collect_args

:dispatch
call :find_python
if errorlevel 1 exit /b 1

if /I "%MODE%"=="loop" goto :loop
if /I "%MODE%"=="server" goto :server
if /I "%MODE%"=="api-direct" goto :api_direct
if /I "%MODE%"=="check-config" goto :check_config

echo Modo invalido: %MODE%
goto :usage

:loop
"%PYTHON_BIN%" "%PROJECT_ROOT%main.py" %FORWARDED_ARGS%
exit /b %errorlevel%

:server
"%PYTHON_BIN%" "%PROJECT_ROOT%runtime\server.py" %FORWARDED_ARGS%
exit /b %errorlevel%

:api_direct
"%PYTHON_BIN%" -m uvicorn interface.api.app:app --app-dir "%PROJECT_ROOT%" %FORWARDED_ARGS%
exit /b %errorlevel%

:check_config
"%PYTHON_BIN%" "%PROJECT_ROOT%runtime\server.py" --check-config %FORWARDED_ARGS%
exit /b %errorlevel%

:find_python
if defined PYTHON_BIN exit /b 0

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_BIN=python"
    exit /b 0
)

if exist "%ProgramFiles%\PostgreSQL\17\pgAdmin 4\python\python.exe" (
    set "PYTHON_BIN=%ProgramFiles%\PostgreSQL\17\pgAdmin 4\python\python.exe"
    exit /b 0
)

echo Nenhum interpretador Python compativel foi encontrado.
echo Defina PYTHON_BIN ou instale um interpretador acessivel.
exit /b 1

:usage
echo Uso: jarvis.cmd ^<loop^|server^|api-direct^|check-config^> [argumentos]
exit /b 1
