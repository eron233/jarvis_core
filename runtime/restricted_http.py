"""Transportes sem proxy, com DNS validado no endereço usado pelo socket."""
from __future__ import annotations

from functools import partial
import http.client
import ipaddress
import socket
import time
import urllib.request


def _connect(host, port, timeout, source_address, *, loopback_only):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses:
        raise OSError("DNS sem endereços.")
    for _, _, _, _, target in addresses:
        ip = ipaddress.ip_address(target[0])
        permitted = ip.is_loopback if loopback_only else ip.is_global and not ip.is_multicast
        if not permitted:
            raise OSError("Endereço fora da política do transporte.")
    # Usa o sockaddr já validado. Nunca resolve o nome novamente no connect.
    effective_timeout = socket.getdefaulttimeout() if timeout is socket._GLOBAL_DEFAULT_TIMEOUT else timeout
    deadline = None if effective_timeout is None else time.monotonic() + effective_timeout
    last_error = None
    for family, socktype, protocol, _, target in addresses:
        remaining = None if deadline is None else deadline - time.monotonic()
        if remaining is not None and remaining <= 0:
            raise TimeoutError("Tempo de conexão esgotado.")
        connection = None
        try:
            connection = socket.socket(family, socktype, protocol)
            connection.settimeout(remaining)
            if source_address:
                connection.bind(source_address)
            connection.connect(target)
            return connection
        except OSError as exc:
            last_error = exc
            if connection is not None:
                connection.close()
        except BaseException:
            if connection is not None:
                connection.close()
            raise
    raise last_error or OSError("Nenhum endereço acessível.")


class _RestrictedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args, loopback_only, **kwargs):
        self.loopback_only = loopback_only
        super().__init__(*args, **kwargs)

    def connect(self):
        if self._tunnel_host:
            raise OSError("Túneis não permitidos.")
        self.sock = _connect(self.host, self.port, self.timeout, self.source_address,
                             loopback_only=self.loopback_only)


class _RestrictedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, loopback_only, **kwargs):
        self.loopback_only = loopback_only
        super().__init__(*args, **kwargs)

    def connect(self):
        if self._tunnel_host:
            raise OSError("Túneis não permitidos.")
        connection = _connect(self.host, self.port, self.timeout, self.source_address,
                              loopback_only=self.loopback_only)
        try:
            # O IP é fixado na conexão, mas TLS verifica o hostname original.
            self.sock = self._context.wrap_socket(connection, server_hostname=self.host)
        except BaseException:
            connection.close()
            raise


class _HTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, loopback_only):
        super().__init__()
        self.loopback_only = loopback_only

    def http_open(self, req):
        return self.do_open(partial(_RestrictedHTTPConnection,
                                   loopback_only=self.loopback_only), req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, loopback_only):
        super().__init__()
        self.loopback_only = loopback_only

    def https_open(self, req):
        return self.do_open(partial(_RestrictedHTTPSConnection,
            loopback_only=self.loopback_only), req, context=self._context)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def restricted_opener(*, loopback_only: bool, redirect_handler=None):
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),
        _HTTPHandler(loopback_only), _HTTPSHandler(loopback_only),
        redirect_handler if redirect_handler is not None else _NoRedirect())
