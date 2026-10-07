"""
JARVIS - Stack MCP Oficial

Integra o SDK Python oficial do Model Context Protocol v2.

Politica:
- servidores MCP sao cadastrados explicitamente;
- descoberta nao concede permissao de execucao;
- tools/resources/prompts possuem allowlists por servidor;
- stdio nunca usa shell=True;
- ambiente do subprocesso e explicitamente selecionado;
- Streamable HTTP remoto e bloqueado por padrao;
- nenhuma resposta MCP e fabricada quando o SDK/backend esta ausente.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import socket
import threading
from typing import Any, Callable, Dict, List, Mapping, Optional
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = PROJECT_ROOT / "data" / "mcp_servers.json"


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _csv(value: Optional[str], default: str = "") -> List[str]:
    raw = value if value is not None else default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return _serialize(value.model_dump(mode="json"))
        except TypeError:
            return _serialize(value.model_dump())
    if hasattr(value, "__dict__"):
        return {
            str(key): _serialize(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


def _run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: Dict[str, Any] = {}
    error: Dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:
            error["value"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error["value"]
    return result.get("value")


def _exception_message(exc: BaseException) -> str:
    """Preserva causas internas, inclusive ExceptionGroup/TaskGroup."""

    parts = [f"{exc.__class__.__name__}: {exc}"]
    nested = getattr(exc, "exceptions", None)
    if isinstance(nested, (list, tuple)):
        for child in nested:
            if isinstance(child, BaseException):
                parts.append(_exception_message(child))
    cause = getattr(exc, "__cause__", None)
    if isinstance(cause, BaseException):
        parts.append("caused_by=" + _exception_message(cause))
    return " | ".join(dict.fromkeys(parts))


@dataclass(frozen=True)
class MCPStackConfig:
    enabled: bool = False
    registry_path: Path = DEFAULT_REGISTRY
    allow_remote_http: bool = False
    allowed_stdio_commands: tuple[str, ...] = ("python", "python3", "uv", "uvx")
    max_result_chars: int = 200_000

    @classmethod
    def from_env(
        cls,
        environ: Optional[Mapping[str, str]] = None,
        project_root: Optional[Path] = None,
    ) -> "MCPStackConfig":
        env = dict(environ or os.environ)
        root = Path(project_root or PROJECT_ROOT)
        registry_raw = (env.get("JARVIS_MCP_REGISTRY_PATH") or "").strip()
        registry = Path(registry_raw) if registry_raw else DEFAULT_REGISTRY
        if not registry.is_absolute():
            registry = root / registry

        commands = tuple(
            _csv(
                env.get("JARVIS_MCP_ALLOWED_STDIO_COMMANDS"),
                "python,python3,uv,uvx",
            )
        )
        return cls(
            enabled=_env_bool(env.get("JARVIS_MCP_ENABLED"), False),
            registry_path=registry,
            allow_remote_http=_env_bool(env.get("JARVIS_MCP_ALLOW_REMOTE_HTTP"), False),
            allowed_stdio_commands=commands or ("python", "python3", "uv", "uvx"),
            max_result_chars=max(
                10_000,
                int(env.get("JARVIS_MCP_MAX_RESULT_CHARS", "200000")),
            ),
        )


def validate_mcp_http_url(url: str, allow_remote: bool = False) -> Optional[str]:
    try:
        parsed = urlparse(str(url).strip())
    except ValueError:
        return "URL MCP invalida."
    if parsed.scheme not in {"http", "https"}:
        return "Streamable HTTP MCP exige http/https."
    if not parsed.hostname:
        return "Servidor MCP HTTP sem host."
    if parsed.username is not None or parsed.password is not None:
        return "Credenciais embutidas na URL MCP nao sao permitidas."
    if allow_remote:
        return None

    host = parsed.hostname.strip("[]").lower()
    if host in {"localhost", "localhost.localdomain"}:
        return None
    try:
        ip = ipaddress.ip_address(host)
        return None if ip.is_loopback else "MCP HTTP remoto bloqueado por padrao."
    except ValueError:
        pass

    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(
                host,
                parsed.port or (443 if parsed.scheme == "https" else 80),
            )
            if info and info[4]
        }
    except socket.gaierror:
        return "Host MCP nao resolve localmente."

    if addresses and all(ipaddress.ip_address(item).is_loopback for item in addresses):
        return None
    return "MCP HTTP remoto bloqueado por padrao."


class MCPRegistry:
    """Registro persistente de servidores e permissoes MCP."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": "1.0",
                "servers": {},
            }
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "schema_version": "1.0",
                "servers": {},
                "_error": f"{exc.__class__.__name__}: {exc}",
            }
        if not isinstance(payload, dict) or not isinstance(payload.get("servers", {}), dict):
            return {
                "schema_version": "1.0",
                "servers": {},
                "_error": "Registro MCP invalido.",
            }
        payload.setdefault("schema_version", "1.0")
        payload.setdefault("servers", {})
        return payload

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        payload = self.load()
        server = payload.get("servers", {}).get(str(name))
        return dict(server) if isinstance(server, dict) else None


class OfficialMCPClientManager:
    """Cliente MCP com least privilege e allowlists explicitas."""

    def __init__(
        self,
        config: Optional[MCPStackConfig] = None,
        client_factory: Optional[Callable[[Any], Any]] = None,
        stdio_target_factory: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        self.config = config or MCPStackConfig.from_env()
        self.registry = MCPRegistry(self.config.registry_path)
        self._client_factory = client_factory
        self._stdio_target_factory = stdio_target_factory

    @property
    def sdk_available(self) -> bool:
        return importlib.util.find_spec("mcp") is not None

    def _client_class(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory
        if not self.sdk_available:
            return None
        from mcp import Client
        return Client

    def _build_target(self, server: Dict[str, Any]) -> Dict[str, Any]:
        transport = str(server.get("transport") or "").strip().lower()

        if transport in {"streamable-http", "http", "https"}:
            url = str(server.get("url") or "").strip()
            reason = validate_mcp_http_url(
                url,
                allow_remote=self.config.allow_remote_http,
            )
            if reason:
                return {"status": "bloqueado", "motivo": reason}
            return {"status": "sucesso", "target": url, "transport": "streamable-http"}

        if transport == "stdio":
            command = str(server.get("command") or "").strip()
            if not command:
                return {"status": "erro", "motivo": "Servidor stdio sem command."}
            command_name = Path(command).name.lower()
            allowed = {Path(item).name.lower() for item in self.config.allowed_stdio_commands}
            if command_name not in allowed:
                return {
                    "status": "bloqueado",
                    "motivo": f"Comando stdio MCP '{command_name}' nao esta na allowlist.",
                }

            args = server.get("args") or []
            if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
                return {"status": "erro", "motivo": "args do servidor stdio devem ser lista de strings."}

            env_names = server.get("env_allowlist") or []
            if not isinstance(env_names, list):
                return {"status": "erro", "motivo": "env_allowlist deve ser lista."}
            env = {
                str(name): os.environ[str(name)]
                for name in env_names
                if isinstance(name, str) and str(name) in os.environ
            }

            cwd = server.get("cwd")
            if cwd:
                cwd_path = Path(str(cwd))
                if not cwd_path.is_absolute():
                    cwd_path = PROJECT_ROOT / cwd_path
                try:
                    cwd_path.resolve().relative_to(PROJECT_ROOT.resolve())
                except ValueError:
                    return {
                        "status": "bloqueado",
                        "motivo": "cwd do servidor MCP deve permanecer dentro do projeto.",
                    }
                cwd = str(cwd_path)

            payload = {
                "command": command,
                "args": list(args),
                "env": env,
                "cwd": cwd,
            }
            if self._stdio_target_factory is not None:
                target = self._stdio_target_factory(payload)
            else:
                if not self.sdk_available:
                    return {"status": "indisponivel", "motivo": "SDK MCP oficial nao instalado."}
                from mcp import StdioServerParameters
                target = StdioServerParameters(**payload)
            return {"status": "sucesso", "target": target, "transport": "stdio"}

        return {
            "status": "erro",
            "motivo": f"Transporte MCP desconhecido: {transport or 'vazio'}.",
        }

    def _prepare_server(self, server_name: str) -> Dict[str, Any]:
        if not self.config.enabled:
            return {"status": "indisponivel", "motivo": "MCP oficial esta desativado."}

        server = self.registry.get_server(server_name)
        if server is None:
            return {"status": "erro", "motivo": f"Servidor MCP '{server_name}' nao cadastrado."}
        if not bool(server.get("enabled", False)):
            return {"status": "bloqueado", "motivo": f"Servidor MCP '{server_name}' esta desabilitado."}

        built = self._build_target(server)
        if built.get("status") != "sucesso":
            return built

        client_factory = self._client_class()
        if client_factory is None:
            return {"status": "indisponivel", "motivo": "SDK MCP oficial nao instalado."}

        return {
            "status": "sucesso",
            "server": server,
            "target": built["target"],
            "transport": built["transport"],
            "client_factory": client_factory,
        }

    @staticmethod
    def _allowed(server: Dict[str, Any], key: str, name: str) -> bool:
        values = server.get(key) or []
        return isinstance(values, list) and str(name) in {str(item) for item in values}

    async def _discover_async(self, prepared: Dict[str, Any]) -> Dict[str, Any]:
        factory = prepared["client_factory"]
        async with factory(prepared["target"]) as client:
            tools_result = await client.list_tools()
            resources_result = await client.list_resources()
            prompts_result = await client.list_prompts()

            tools = [_serialize(item) for item in getattr(tools_result, "tools", [])]
            resources = [_serialize(item) for item in getattr(resources_result, "resources", [])]
            prompts = [_serialize(item) for item in getattr(prompts_result, "prompts", [])]

            return {
                "status": "sucesso",
                "protocol_version": getattr(client, "protocol_version", None),
                "server_info": _serialize(getattr(client, "server_info", None)),
                "server_capabilities": _serialize(getattr(client, "server_capabilities", None)),
                "instructions": getattr(client, "instructions", None),
                "tools": tools,
                "resources": resources,
                "prompts": prompts,
            }

    def discover(self, server_name: str) -> Dict[str, Any]:
        prepared = self._prepare_server(server_name)
        if prepared.get("status") != "sucesso":
            return {**prepared, "server": server_name}
        try:
            result = _run_async(self._discover_async(prepared))
            return {
                **result,
                "server": server_name,
                "transport": prepared["transport"],
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "status": "erro",
                "server": server_name,
                "motivo": f"Falha real no MCP discover: {_exception_message(exc)}",
            }

    async def _call_tool_async(
        self,
        prepared: Dict[str, Any],
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        factory = prepared["client_factory"]
        async with factory(prepared["target"]) as client:
            result = await client.call_tool(tool_name, arguments)
            return _serialize(result)

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prepared = self._prepare_server(server_name)
        if prepared.get("status") != "sucesso":
            return {**prepared, "server": server_name, "tool": tool_name}
        if not self._allowed(prepared["server"], "allowed_tools", tool_name):
            return {
                "status": "bloqueado",
                "server": server_name,
                "tool": tool_name,
                "motivo": "Tool MCP nao esta na allowlist deste servidor.",
            }

        try:
            payload = _run_async(
                self._call_tool_async(prepared, tool_name, dict(arguments or {}))
            )
            serialized = json.dumps(payload, ensure_ascii=False)
            protocol_error = bool(
                isinstance(payload, dict)
                and (
                    payload.get("isError") is True
                    or payload.get("is_error") is True
                )
            )
            truncated = len(serialized) > self.config.max_result_chars
            if truncated:
                payload = {
                    "truncated": True,
                    "preview": serialized[: self.config.max_result_chars],
                    "is_error": protocol_error,
                }
            return {
                "status": "erro" if protocol_error else "sucesso",
                "server": server_name,
                "tool": tool_name,
                "resultado": payload,
                "truncado": truncated,
                "motivo": (
                    "Servidor MCP retornou isError=true."
                    if protocol_error
                    else None
                ),
                "executado_em": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "status": "erro",
                "server": server_name,
                "tool": tool_name,
                "motivo": f"Falha real na tool MCP: {_exception_message(exc)}",
            }

    async def _read_resource_async(self, prepared: Dict[str, Any], uri: str) -> Dict[str, Any]:
        factory = prepared["client_factory"]
        async with factory(prepared["target"]) as client:
            return _serialize(await client.read_resource(uri))

    def read_resource(self, server_name: str, uri: str) -> Dict[str, Any]:
        prepared = self._prepare_server(server_name)
        if prepared.get("status") != "sucesso":
            return {**prepared, "server": server_name, "uri": uri}
        if not self._allowed(prepared["server"], "allowed_resources", uri):
            return {
                "status": "bloqueado",
                "server": server_name,
                "uri": uri,
                "motivo": "Resource MCP nao esta na allowlist deste servidor.",
            }
        try:
            return {
                "status": "sucesso",
                "server": server_name,
                "uri": uri,
                "resultado": _run_async(self._read_resource_async(prepared, uri)),
            }
        except Exception as exc:
            return {
                "status": "erro",
                "server": server_name,
                "uri": uri,
                "motivo": f"Falha real ao ler resource MCP: {_exception_message(exc)}",
            }

    async def _get_prompt_async(
        self,
        prepared: Dict[str, Any],
        prompt_name: str,
        arguments: Dict[str, str],
    ) -> Dict[str, Any]:
        factory = prepared["client_factory"]
        async with factory(prepared["target"]) as client:
            return _serialize(await client.get_prompt(prompt_name, arguments))

    def get_prompt(
        self,
        server_name: str,
        prompt_name: str,
        arguments: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        prepared = self._prepare_server(server_name)
        if prepared.get("status") != "sucesso":
            return {**prepared, "server": server_name, "prompt": prompt_name}
        if not self._allowed(prepared["server"], "allowed_prompts", prompt_name):
            return {
                "status": "bloqueado",
                "server": server_name,
                "prompt": prompt_name,
                "motivo": "Prompt MCP nao esta na allowlist deste servidor.",
            }
        try:
            return {
                "status": "sucesso",
                "server": server_name,
                "prompt": prompt_name,
                "resultado": _run_async(
                    self._get_prompt_async(
                        prepared,
                        prompt_name,
                        dict(arguments or {}),
                    )
                ),
            }
        except Exception as exc:
            return {
                "status": "erro",
                "server": server_name,
                "prompt": prompt_name,
                "motivo": f"Falha real ao obter prompt MCP: {_exception_message(exc)}",
            }

    def status(self) -> Dict[str, Any]:
        registry = self.registry.load()
        servers = {}
        for name, server in registry.get("servers", {}).items():
            if not isinstance(server, dict):
                continue
            servers[name] = {
                "enabled": bool(server.get("enabled", False)),
                "transport": server.get("transport"),
                "allowed_tools": len(server.get("allowed_tools") or []),
                "allowed_resources": len(server.get("allowed_resources") or []),
                "allowed_prompts": len(server.get("allowed_prompts") or []),
            }
        return {
            "enabled": self.config.enabled,
            "sdk_available": self.sdk_available,
            "registry_path": str(self.config.registry_path),
            "registry_error": registry.get("_error"),
            "servers": servers,
            "allow_remote_http": self.config.allow_remote_http,
            "allowed_stdio_commands": list(self.config.allowed_stdio_commands),
            "official_protocol": True,
            "fabricated_mcp": False,
        }


def build_jarvis_mcp_server(runtime: Any) -> Any:
    """Cria servidor MCP oficial read-only para introspeccao segura do JARVIS."""

    if importlib.util.find_spec("mcp") is None:
        raise RuntimeError("SDK MCP oficial nao instalado.")

    from mcp.server import MCPServer

    mcp = MCPServer(
        "jarvis-core",
        instructions=(
            "Servidor MCP oficial do JARVIS. As ferramentas expostas aqui sao "
            "somente de introspeccao/read-only; mutacoes continuam sob o planner constitucional."
        ),
    )

    @mcp.tool()
    def runtime_status() -> Dict[str, Any]:
        """Retorna estado operacional resumido do runtime sem executar mutacoes."""
        state = runtime.describe_state()
        return {
            "status": state.get("status"),
            "started_at": state.get("started_at"),
            "total_cycles_executed": state.get("total_cycles_executed"),
        }

    @mcp.resource("jarvis://capabilities")
    def capabilities() -> str:
        """Lista capacidades tecnicas publicadas pelo runtime."""
        payload = {
            "inference": runtime.inference_router.status(probe=False)
            if hasattr(runtime, "inference_router")
            else None,
            "web": runtime.web_browser_engine.describe_capabilities()
            if hasattr(runtime, "web_browser_engine")
            else None,
            "voice": runtime.voice_engine.describe_capabilities()
            if hasattr(runtime, "voice_engine")
            else None,
            "vision": runtime.image_vision_engine.describe_capabilities()
            if hasattr(runtime, "image_vision_engine")
            else None,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    return mcp
