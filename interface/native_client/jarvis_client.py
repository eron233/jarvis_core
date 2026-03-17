"""
JARVIS - Cliente Nativo Leve

Responsavel por:
- enviar comandos textuais para a API local do Jarvis
- imprimir a resposta retornada pelo runtime
- servir como terminal leve de interacao sem processamento pesado

Integracoes principais:
- interface.api.app
- security.access_control
- runtime.internal_agent_runtime
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import uuid
from typing import Any, Dict, Optional
from urllib import error, request

from runtime.system_config import JarvisEnvironmentConfig

# JARVIS_API_LAYER
# ==================================================
# BLOCO: Cliente leve para comandos via API
# ==================================================

DEFAULT_COMMAND_URL = "http://localhost:8000/api/comando"


def load_client_defaults() -> dict[str, str]:
    """Carrega defaults reais do cliente a partir da configuracao efetiva do runtime."""

    config = JarvisEnvironmentConfig.from_env()
    command_url = os.environ.get(
        "JARVIS_CLIENT_URL",
        f"http://127.0.0.1:{config.api_port}/api/comando",
    )
    return {
        "url": command_url,
        "token": config.token,
        "device_id": config.trusted_device_id,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    """Monta o parser do cliente nativo."""

    defaults = load_client_defaults()
    parser = argparse.ArgumentParser(description="Cliente leve do Jarvis para envio de comandos.")
    parser.add_argument("--texto", help="Comando textual a ser enviado para o Jarvis.")
    parser.add_argument("--voz", dest="voz_identificada", help="Identidade de voz reconhecida.")
    parser.add_argument("--senha", help="Senha administrativa opcional.")
    parser.add_argument(
        "--url",
        default=defaults["url"] or DEFAULT_COMMAND_URL,
        help="URL do endpoint de comando da API.",
    )
    parser.add_argument(
        "--token",
        default=defaults["token"],
        help="Token da API do Jarvis.",
    )
    parser.add_argument(
        "--device-id",
        default=defaults["device_id"],
        help="Device id confiavel usado na autenticacao da API.",
    )
    parser.add_argument(
        "--modo-resposta",
        default="conversacional",
        choices=["conversacional", "tecnico"],
        help="Formato principal de retorno solicitado ao runtime.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Imprime o JSON bruto retornado pela API.",
    )
    return parser


def send_command(
    url: str,
    token: str,
    device_id: str,
    texto: str,
    voz_identificada: str | None = None,
    senha: str | None = None,
    modo_resposta: str = "conversacional",
) -> Dict[str, Any]:
    """Envia um comando para o endpoint local do Jarvis."""

    payload = json.dumps(
        {
            "texto": texto,
            "voz_identificada": voz_identificada,
            "senha": senha,
            "modo_resposta": modo_resposta,
        }
    ).encode("utf-8")
    auth_headers = build_authenticated_headers(token=token, device_id=device_id)
    req = request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", **auth_headers},
        method="POST",
    )

    with request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def build_authenticated_headers(
    token: str,
    device_id: str,
    nonce: str | None = None,
    timestamp: str | None = None,
) -> Dict[str, str]:
    """Monta os headers completos de autenticacao exigidos pela API atual."""

    return {
        "X-Jarvis-Token": token,
        "X-Jarvis-Device-Id": device_id,
        "X-Jarvis-Nonce": nonce or str(uuid.uuid4()),
        "X-Jarvis-Timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }


def main(argv: Optional[list[str]] = None) -> int:
    """Executa o cliente nativo em modo unitario."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    texto = args.texto or input("Comando para o Jarvis: ").strip()
    if not texto:
        print("Nenhum comando informado.")
        return 1

    if not args.token or not args.device_id:
        print("Token e device id sao obrigatorios para acessar a API do Jarvis.")
        return 2

    try:
        payload = send_command(
            url=args.url,
            token=args.token,
            device_id=args.device_id,
            texto=texto,
            voz_identificada=args.voz_identificada,
            senha=args.senha,
            modo_resposta=args.modo_resposta,
        )
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        print(f"Falha HTTP {exc.code}: {body}")
        return 3
    except error.URLError as exc:
        print(f"Falha ao conectar na API do Jarvis: {exc.reason}")
        return 4

    if args.raw:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    resposta = payload.get("resposta") or payload.get("mensagem") or "Resposta vazia."
    print(resposta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
