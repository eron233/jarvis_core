"""
Launcher do servidor MCP oficial read-only do JARVIS.

Uso:
    python -m runtime.mcp_server
    JARVIS_MCP_SERVER_TRANSPORT=streamable-http python -m runtime.mcp_server
"""

from __future__ import annotations

import ipaddress
import os
import socket

from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.mcp_stack import build_jarvis_mcp_server


def main() -> None:
    runtime = InternalAgentRuntime()
    runtime.bootstrap()
    server = build_jarvis_mcp_server(runtime)

    transport = (os.environ.get("JARVIS_MCP_SERVER_TRANSPORT") or "stdio").strip().lower()
    if transport == "stdio":
        server.run(transport="stdio")
        return

    if transport == "streamable-http":
        host = (os.environ.get("JARVIS_MCP_SERVER_HOST") or "127.0.0.1").strip()
        allow_remote_bind = (os.environ.get("JARVIS_MCP_SERVER_ALLOW_REMOTE_BIND") or "false").strip().lower() in {"1", "true", "yes", "sim", "on"}
        if not allow_remote_bind:
            allowed = False
            if host.lower() in {"localhost", "localhost.localdomain"}:
                allowed = True
            else:
                try:
                    allowed = ipaddress.ip_address(host.strip("[]")).is_loopback
                except ValueError:
                    try:
                        resolved = {
                            info[4][0]
                            for info in socket.getaddrinfo(host, None)
                            if info and info[4]
                        }
                        allowed = bool(resolved) and all(
                            ipaddress.ip_address(address).is_loopback
                            for address in resolved
                        )
                    except (socket.gaierror, ValueError):
                        allowed = False
            if not allowed:
                raise SystemExit(
                    "Bind MCP remoto bloqueado. Use JARVIS_MCP_SERVER_ALLOW_REMOTE_BIND=true conscientemente."
                )

        port = int(os.environ.get("JARVIS_MCP_SERVER_PORT", "8765"))
        path = (os.environ.get("JARVIS_MCP_SERVER_PATH") or "/mcp").strip()
        if not path.startswith("/"):
            path = "/" + path
        server.run(
            transport="streamable-http",
            host=host,
            port=port,
            streamable_http_path=path,
            stateless_http=True,
            json_response=True,
        )
        return

    raise SystemExit(
        "JARVIS_MCP_SERVER_TRANSPORT deve ser 'stdio' ou 'streamable-http'."
    )


if __name__ == "__main__":
    main()
