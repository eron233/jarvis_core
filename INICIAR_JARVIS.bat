@echo off
setlocal enabledelayedexpansion

:: ======================================================
:: JARVIS - Launcher de Clique Duplo Automático (Windows)
:: ======================================================

title JARVIS - Sistema Cognitivo Operacional
cd /d "%~dp0"

echo ======================================================
echo   Iniciando o JARVIS (Clique Duplo Automacao)
echo ======================================================
echo.

:: 1. Verificar se Python esta instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Interpretador Python nao encontrado no sistema.
    echo Por favor, instale o Python 3.10+ marcando "Add Python to PATH".
    echo Pressione qualquer tecla para sair...
    pause >nul
    exit /b 1
)

:: 2. Instalar dependencias automaticamente se necessario
if exist "requirements.txt" (
    echo [INFO] Verificando dependencias do sistema...
    python -m pip install -r requirements.txt --quiet >nul 2>&1
)

:: 3. Abrir o navegador automaticamente em 3 segundos
echo [INFO] Abrindo a Dashboard Web em http://localhost:8000/painel ...
start "" "http://localhost:8000/painel"

:: 4. Iniciar o servidor unificado do JARVIS
echo [INFO] Servidor JARVIS iniciado com sucesso na porta 8000.
echo [INFO] Para encerrar, feche esta janela do prompt.
echo.

python main.py

pause
