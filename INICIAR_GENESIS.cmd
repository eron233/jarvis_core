@echo off
setlocal
set "ROOT=%~dp0"
if exist "%ROOT%dist\Genesis\Genesis.exe" (
  start "" "%ROOT%dist\Genesis\Genesis.exe"
  exit /b 0
)
if exist "%ROOT%Genesis.exe" (
  start "" "%ROOT%Genesis.exe"
  exit /b 0
)
echo GÊNESIS / ÍRIS
echo O executavel ainda nao foi extraido aqui. Tentando a versao Python...
if not exist "%ROOT%genesis_launcher.py" (
  echo ERRO: arquivos do programa nao encontrados.
  exit /b 2
)
where python >nul 2>nul
if errorlevel 1 (
  echo ERRO: Python nao encontrado. Instale a distribuicao Genesis-win64.zip.
  exit /b 1
)
python "%ROOT%genesis_launcher.py"
exit /b %errorlevel%
