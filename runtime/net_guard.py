"""
JARVIS - Guarda de rede para buscas externas (anti-SSRF)

Responsavel por:
- aceitar apenas URLs http/https com host publico
- recusar loopback, redes privadas, link-local (inclui metadata de nuvem 169.254.169.254) e reservados
- revalidar cada redirecionamento e limitar o tamanho baixado
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024


class BlockedUrlError(ValueError):
    """URL recusada pela politica de rede."""


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def validate_public_url(url: str) -> str:
    """Retorna a URL normalizada ou levanta BlockedUrlError."""

    parsed = urllib.parse.urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"}:
        raise BlockedUrlError("Somente URLs http/https sao permitidas.")
    if not parsed.hostname:
        raise BlockedUrlError("URL sem host.")
    if parsed.username or parsed.password:
        raise BlockedUrlError("URL com credenciais embutidas nao e permitida.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise BlockedUrlError(f"Host nao resolvido: {parsed.hostname}") from exc
    for info in infos:
        if not _is_public_address(info[4][0]):
            raise BlockedUrlError("Destino em rede interna/privada nao e permitido.")
    return parsed.geturl()


class _ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_ValidatingRedirectHandler())


def fetch_public_url(
    url: str,
    user_agent: str,
    timeout: float = 10.0,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    extra_headers: Optional[dict] = None,
) -> Tuple[str, str]:
    """Baixa URL publica e retorna (url_final, texto). Levanta BlockedUrlError ou URLError."""

    safe_url = validate_public_url(url)
    headers = {"User-Agent": user_agent}
    headers.update(extra_headers or {})
    request = urllib.request.Request(safe_url, headers=headers)
    with _OPENER.open(request, timeout=timeout) as response:
        raw = response.read(max_bytes + 1)
        final_url = response.geturl()
        charset = response.headers.get_content_charset() or "utf-8"
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
    return final_url, raw.decode(charset, errors="ignore")
