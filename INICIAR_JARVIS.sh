#!/usr/bin/env bash

# ======================================================
# JARVIS - Launcher de Clique Duplo (Linux/macOS)
# ======================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "======================================================"
echo "  Iniciando o JARVIS (Clique Duplo Automação)"
echo "======================================================"
echo ""

# 1. Verificar se Python3 está disponível
if ! command -v python3 &> /dev/null; then
    echo "[ERRO] Python3 não encontrado no sistema."
    exit 1
fi

# 2. Instalar dependências se necessário
if [ -f "requirements.txt" ]; then
    echo "[INFO] Verificando dependências do sistema..."
    python3 -m pip install -r requirements.txt --quiet &> /dev/null || true
fi

# 3. Abrir o navegador em segundo plano
echo "[INFO] Abrindo Dashboard Web em http://localhost:8000/painel ..."
if command -v xdg-open &> /dev/null; then
    (sleep 2 && xdg-open "http://localhost:8000/painel") &
elif command -v open &> /dev/null; then
    (sleep 2 && open "http://localhost:8000/painel") &
fi

# 4. Iniciar servidor principal
echo "[INFO] Servidor JARVIS ativo."
python3 main.py
