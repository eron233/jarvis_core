"""Estados públicos da presença da Íris; sem telemetria inventada."""
from __future__ import annotations

STATES = {
    "offline": ("AGUARDANDO CONEXÃO", "Sem confirmação do runtime.", "#a3adba"),
    "idle": ("À DISPOSIÇÃO", "Pronta para conversar.", "#83d3e7"),
    "listening": ("OUVINDO", "Captura de áudio ativa.", "#92dce5"),
    "thinking": ("ANALISANDO", "Preparando resposta.", "#bdc6ff"),
    "working": ("EXECUTANDO", "Comando enviado ao runtime.", "#deb8ff"),
    "error": ("ATENÇÃO", "Não foi possível concluir a operação.", "#f4b6aa"),
}

def normalize_state(name: str) -> str:
    return name if name in STATES else "offline"

def state_metadata(name: str) -> tuple[str, str, str]:
    return STATES[normalize_state(name)]
