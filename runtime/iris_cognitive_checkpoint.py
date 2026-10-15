"""Checkpoint opt-in de memorias cognitivas reais da Iris.

Captura snapshots *em memoria* sem gravar copias em JSON plaintext, cifra em
IrisEncryptedStateStore e permite restauro por instancia. Em seguida a malha
pode replicar o documento cifrado para um segundo computador.

Nao migra pesos LLM, KV cache, processos, comandos, credenciais, objetivos de
outros tenants nem altera automaticamente o runtime global JARVIS.
"""
from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from memory_system.iris_state_store import IrisEncryptedStateStore, StateConflictError

_COMPONENTS = frozenset({"semantic", "procedural", "episodic", "evolution"})
_DOCUMENT_ID = "cognitive.checkpoint"


class IrisCognitiveCheckpoint:
    """Restauro de componentes preparados para uma identidade, de forma isolada."""

    def __init__(
        self, store: IrisEncryptedStateStore, instance_id: str,
        token: str, *, components: dict[str, Any],
    ) -> None:
        if not components or set(components) - _COMPONENTS:
            raise ValueError("Componentes de memoria desconhecidos ou ausentes.")
        if any(
            not callable(getattr(c, "_build_snapshot", None))
            or not callable(getattr(c, "load_snapshot", None))
            for c in components.values()
        ):
            raise ValueError("Componente sem snapshot/restauro suportado.")
        store.authority.require(instance_id, token, "memory.own")
        self.store = store
        self.instance_id, self.token = instance_id, token
        self.components = dict(components)
        self._lock = RLock()

    def capture(self, *, expected_revision: int) -> dict[str, Any]:
        """Grava um pacote atomico (ate 64 KiB) com revisao otimista."""
        with self._lock:
            # _build_snapshot, nao snapshot(): evita efeitos de escrita
            # em stores legados plaintext no computador.
            package = {
                "schema": 1,
                "components": {
                    kind: deepcopy(component._build_snapshot())
                    for kind, component in self.components.items()
                },
            }
            return self.store.put(
                self.instance_id, self.token, _DOCUMENT_ID,
                package, expected_revision=expected_revision,
            )

    def restore(self) -> dict[str, Any]:
        """Valida o checkpoint e restaura; volta ao estado anterior em erro."""
        with self._lock:
            document = self.store.get(self.instance_id, self.token, _DOCUMENT_ID)
            if not document["found"]:
                return {"restored": False, "revision": 0}
            payload = document["value"]
            if (
                not isinstance(payload, dict) or payload.get("schema") != 1
                or not isinstance(payload.get("components"), dict)
                or set(payload["components"]) != set(self.components)
                or any(not isinstance(value, dict)
                       for value in payload["components"].values())
            ):
                raise ValueError("Checkpoint cognitivo invalido ou incompleto.")
            before = {
                kind: deepcopy(component._build_snapshot())
                for kind, component in self.components.items()
            }
            try:
                for kind, component in self.components.items():
                    component.load_snapshot(deepcopy(payload["components"][kind]))
            except BaseException:
                for kind, component in self.components.items():
                    component.load_snapshot(deepcopy(before[kind]))
                raise
            return {
                "restored": True, "revision": document["revision"],
                "components": sorted(self.components),
            }
