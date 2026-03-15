"""
JARVIS - Controle de Acesso Unificado

Responsavel por:
- classificar acesso administrativo ou guest
- tratar voz declarada apenas como contexto auxiliar, nao como prova administrativa
- validar acesso administrativo real por senha
- tratar a frase especial reservada do sistema

Integracoes principais:
- interface.api.app
- runtime.internal_agent_runtime
- device.device_registry
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict


# JARVIS_SECURITY_GATE
# ==================================================
# BLOCO: Politica inicial de acesso administrativo
# ==================================================

DEFAULT_ADMIN_VOICE = "eron"
DEFAULT_ADMIN_PASSWORD = "alter ego"
SPECIAL_WAKE_PHRASE = "jarvis ta ai"


def _normalize_text(value: str | None) -> str:
    """Normaliza strings de acesso para comparacoes deterministicas."""

    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


@dataclass
class AccessControl:
    """Aplica as regras iniciais de acesso do Jarvis sem criar contas multiplas."""

    admin_voice: str = DEFAULT_ADMIN_VOICE
    admin_password: str = DEFAULT_ADMIN_PASSWORD

    @classmethod
    def from_env(cls) -> "AccessControl":
        """Constroi o controle de acesso a partir do ambiente."""

        return cls(
            admin_voice=str(os.environ.get("JARVIS_ADMIN_VOICE", DEFAULT_ADMIN_VOICE)),
            admin_password=str(os.environ.get("JARVIS_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)),
        )

    def evaluate(
        self,
        phrase: str | None = None,
        voice_id: str | None = None,
        password: str | None = None,
    ) -> Dict[str, Any]:
        """Avalia o contexto de acesso de um comando do sistema."""

        normalized_phrase = _normalize_text(phrase)
        normalized_voice = _normalize_text(voice_id)
        normalized_password = _normalize_text(password)
        authorized_methods: list[str] = []

        voice_matches_admin = bool(
            normalized_voice and normalized_voice == _normalize_text(self.admin_voice)
        )
        if normalized_password and normalized_password == _normalize_text(self.admin_password):
            authorized_methods.append("senha")

        access_level = "admin" if authorized_methods else "guest"
        is_special_wake_phrase = normalized_phrase == SPECIAL_WAKE_PHRASE
        should_ignore = is_special_wake_phrase and not voice_matches_admin
        special_response = None
        if is_special_wake_phrase and voice_matches_admin:
            special_response = "Sim, Sr. Maciel."

        return {
            "access_level": access_level,
            "admin_access": access_level == "admin",
            "authenticated_by": authorized_methods or ["guest"],
            "recognized_voice": normalized_voice or None,
            "recognized_voice_matches_admin": voice_matches_admin,
            "voice_is_informative_only": True,
            "special_wake_phrase": is_special_wake_phrase,
            "should_ignore": should_ignore,
            "special_response": special_response,
        }

    def can_execute_sensitive_action(self, access_context: Dict[str, Any]) -> bool:
        """Informa se o contexto atual pode executar acoes mutantes ou sensiveis."""

        return bool(access_context.get("admin_access"))
