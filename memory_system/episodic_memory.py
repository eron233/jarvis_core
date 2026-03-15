"""
JARVIS - Memoria Episodica

Responsavel por:
- registrar eventos do runtime em ordem temporal
- apoiar auditoria, replay e relatorios operacionais
- oferecer uma fila leve de eventos recentes para API e diagnostico

Integracoes principais:
- runtime.internal_agent_runtime
- executive_planner.audit
- interface.api.app
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
#
# JARVIS_MEMORY_SYSTEM
# ==================================================
# BLOCO: Registro linear de episodios
# ==================================================

class EpisodicMemory:
    """Mantem episodios recentes para replay e reflexao futura."""

    episodes: List[Dict[str, Any]] = field(default_factory=list)

    def remember(self, episode: Dict[str, Any]) -> None:
        """
        Armazena um novo episodio no historico em memoria.

        Parametros:
        - episode: evento estruturado do runtime ou da auditoria.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - adiciona o evento ao fim da lista cronologica.
        """

        self.episodes.append(episode)

    def recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Recupera os episodios mais recentes.

        Parametros:
        - limit: quantidade maxima de eventos retornados.

        Retorno:
        - lista com os episodios mais recentes.

        Efeitos no sistema:
        - nenhum; apenas leitura do historico.
        """

        return self.episodes[-limit:]
