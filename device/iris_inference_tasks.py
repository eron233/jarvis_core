"""Contrato estrito de inferencia da Iris entre nos nativos autorizados.

Nao ha execucao remota de codigo, ferramentas, comandos, links, modelos
arbitrarios nem envio de chats a gateways externos. O modelo REAL deve estar
configurado localmente no no executor (llama.cpp/Ollama). Na ausencia dele,
a tarefa falha explicitamente, nunca produz uma resposta ficticia.
"""
from __future__ import annotations

import json
import math
from typing import Any


_ALLOWED_ROLES = frozenset({"user", "assistant"})
_ALLOWED_TIERS = frozenset({"light", "general", "reasoning"})
_MAX_MESSAGES = 8
_MAX_CONTENT = 1200
_MAX_RESULT = 3000
_MAX_PAYLOAD = 4096


class IrisInferenceUnavailable(RuntimeError):
    """Nenhum motor local autorizado concluiu a inferencia."""


def validate_inference_request(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"messages", "tier", "max_tokens"}:
        raise ValueError("Formato de inferencia invalido.")
    messages = payload["messages"]
    if not isinstance(messages, list) or not 1 <= len(messages) <= _MAX_MESSAGES:
        raise ValueError("Quantidade de mensagens invalida.")
    clean: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise ValueError("Mensagem invalida.")
        role, content = message["role"], message["content"]
        if role not in _ALLOWED_ROLES or not isinstance(content, str):
            raise ValueError("Papel ou conteudo proibido.")
        if not content.strip() or len(content) > _MAX_CONTENT:
            raise ValueError("Mensagem sem texto ou muito extensa.")
        clean.append({"role": role, "content": content})
    if clean[-1]["role"] != "user":
        raise ValueError("Ultimo turno deve partir do usuario.")
    tier = payload["tier"]
    if tier not in _ALLOWED_TIERS:
        raise ValueError("Tier de inferencia desconhecido.")
    tokens = payload["max_tokens"]
    if type(tokens) is not int or not 1 <= tokens <= 256:
        raise ValueError("max_tokens deve estar entre 1 e 256.")
    safe = {"messages": clean, "tier": tier, "max_tokens": tokens}
    if len(json.dumps(safe, ensure_ascii=False).encode("utf-8")) > _MAX_PAYLOAD:
        raise ValueError("Prompt excedeu o limite do transporte.")
    return safe


def validate_inference_result(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"content", "model"}:
        raise ValueError("Resultado de inferencia invalido.")
    content, model = value["content"], value["model"]
    if (not isinstance(content, str) or not content.strip()
        or len(content) > _MAX_RESULT):
        raise ValueError("Resposta do modelo invalida.")
    if not isinstance(model, str) or not 1 <= len(model) <= 120:
        raise ValueError("Identificacao do modelo invalida.")
    return {"content": content, "model": model}


class IrisLocalInferenceExecutor:
    """Executa no runtime local ja configurado, nunca na API central."""

    def __init__(self, router: Any | None = None):
        if router is None:
            from runtime.inference_stack import LocalInferenceRouter
            router = LocalInferenceRouter()
        self.router = router

    def execute(self, payload: Any) -> dict[str, str]:
        safe = validate_inference_request(payload)
        config = getattr(self.router, "config", None)
        if (
            config is None
            or getattr(config, "enabled", False) is not True
            or getattr(config, "offline_mode", False) is not True
            or getattr(config, "allow_remote_endpoints", None) is not False
        ):
            raise IrisInferenceUnavailable(
                "Inferencia remota ou motor local desativado: privacidade preservada."
            )
        # Sem tools, tool_choice, scripts, funcoes ou contexto global.
        result = self.router.chat(
            messages=safe["messages"],
            tier=safe["tier"],
            max_tokens=safe["max_tokens"],
            allow_external=False,
            data_classification="private",
        )
        if not isinstance(result, dict) or result.get("status") != "sucesso":
            raise IrisInferenceUnavailable("Nenhum modelo local concluiu a solicitacao.")
        return validate_inference_result({
            "content": result.get("conteudo"),
            "model": result.get("modelo"),
        })
