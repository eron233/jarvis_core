"""Conversas da Iris ligadas a um motor de inferencia autorizado.

Fluxo: inicia um turno -> worker nativo pareado processa -> finaliza o turno
-> checkpoint cifrado e isolado daquela instancia. Nem a Original nem outros
tenants podem ler este historico atraves do controlador.

Uma reserva CAS impede dois turnos simultaneos no mesmo dialogo. Um job pode
ficar orfao se outra escrita vencer o CAS; expira no broker em 10 minutos.
Nao ha migracao de KV-cache nem resposta garantida com hardware desligado.
"""
from __future__ import annotations

import re
from threading import RLock
from typing import Any

from device.iris_task_broker import IrisTaskBroker
from memory_system.iris_state_store import IrisEncryptedStateStore, StateConflictError
from device.iris_inference_tasks import validate_inference_request, validate_inference_result

_DIALOG_ID = re.compile(r"^[a-zA-Z0-9_-]{3,40}$")
_MAX_TURNS = 6


class IrisDialogueService:
    def __init__(self, broker: IrisTaskBroker, state: IrisEncryptedStateStore):
        if broker.mesh.authority is not state.authority:
            raise ValueError("Broker e memoria precisam da mesma autoridade Iris.")
        self.broker, self.state = broker, state
        self._lock = RLock()

    @staticmethod
    def _document_id(conversation_id: str) -> str:
        if not isinstance(conversation_id, str) or not _DIALOG_ID.fullmatch(conversation_id):
            raise ValueError("Identificador de conversa invalido.")
        return "dialogue." + conversation_id

    def _read(self, instance_id: str, token: str, conversation_id: str):
        doc_id = self._document_id(conversation_id)
        saved = self.state.get(instance_id, token, doc_id)
        default = {"schema": 1, "turns": [], "pending": None}
        data = saved["value"] if saved["found"] else default
        if (not isinstance(data, dict) or data.get("schema") != 1
            or not isinstance(data.get("turns"), list)
            or "pending" not in data):
            raise ValueError("Historico de conversa invalido.")
        return doc_id, saved["revision"], data

    def start(
        self, instance_id: str, token: str, *,
        conversation_id: str, text: str,
    ) -> dict[str, Any]:
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 800:
            raise ValueError("Mensagem precisa de 1 a 800 caracteres.")
        with self._lock:
            doc_id, revision, data = self._read(instance_id, token, conversation_id)
            if data["pending"] is not None:
                raise StateConflictError("Existe uma resposta pendente nesta conversa.")
            turns = data["turns"]
            if any(
                not isinstance(item, dict)
                or item.get("role") not in {"user", "assistant"}
                or not isinstance(item.get("content"), str)
                for item in turns
            ):
                raise ValueError("Historico invalido.")
            # Um modelo recebe apenas mensagens desta instancia, reduzidas.
            # O restante continua no proprio documento cifrado.
            context = [
                {"role": row["role"], "content": row["content"][:600]}
                for row in turns[-6:]
                if row["content"].strip()
            ]
            context.append({"role": "user", "content": text.strip()})
            payload = validate_inference_request({
                "messages": context, "tier": "general", "max_tokens": 192,
            })
            job = self.broker.submit(
                instance_id, token, operation="inference.chat", payload=payload,
            )
            if not job.get("submitted"):
                return {"status": "unavailable", "submitted": False}
            self.state.put(instance_id, token, doc_id, {
                "schema": 1, "turns": turns[-2 * _MAX_TURNS:],
                "pending": {"job_id": job["job_id"], "user_text": text.strip()},
            }, expected_revision=revision)
            return {
                "status": "queued", "submitted": True,
                "job_id": job["job_id"], "conversation_id": conversation_id,
            }

    def finish(
        self, instance_id: str, token: str, *, conversation_id: str,
    ) -> dict[str, Any]:
        with self._lock:
            doc_id, revision, data = self._read(instance_id, token, conversation_id)
            pending = data["pending"]
            if pending is None:
                return {"status": "idle"}
            job = self.broker.inspect(
                instance_id, token, job_id=pending["job_id"],
            )
            if job["status"] != "completed":
                return {"status": job["status"], "job_id": pending["job_id"]}
            answer = validate_inference_result(job["result"])
            turns = (data["turns"] + [
                {"role": "user", "content": pending["user_text"]},
                {"role": "assistant", "content": answer["content"]},
            ])[-2 * _MAX_TURNS:]
            self.state.put(instance_id, token, doc_id, {
                "schema": 1, "turns": turns, "pending": None,
            }, expected_revision=revision)
            return {
                "status": "completed", "model": answer["model"],
                "content": answer["content"], "conversation_id": conversation_id,
            }

    def history(
        self, instance_id: str, token: str, *, conversation_id: str,
    ) -> dict[str, Any]:
        with self._lock:
            _, revision, data = self._read(instance_id, token, conversation_id)
            return {
                "conversation_id": conversation_id,
                "revision": revision,
                "turns": list(data["turns"]),
                "has_pending": data["pending"] is not None,
            }
