@echo off
setlocal
rem O usuario precisa executar este arquivo. Download sozinho nunca inicia programas.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Instalar-Iris.ps1"
if errorlevel 1 (
  echo A instalacao falhou. Verifique a extracao do pacote e tente novamente.
  pause
  exit /b 1
)
endlocal
