"""
JARVIS - Governanca de Contexto para Agentes de Desenvolvimento

Baseline local:
- bloqueia secrets/binarios/lockfiles/build output/minificados;
- full content apenas para arquivos pequenos;
- outline estrutural para arquivos grandes;
- read_range limitado;
- recibos por leitura e contabilidade de sessao.

Backend preferido opcional:
- @flyingrobots/graft v0.14.0 via MCP oficial;
- somente surfaces read-only ficam na allowlist padrao;
- nenhuma inicializacao/hook/escrita automatica no repositorio.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from fnmatch import fnmatch
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Mapping, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]

_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip",
    ".wasm", ".bin", ".sqlite", ".db", ".mp4", ".mov", ".ico",
    ".exe", ".dll", ".so", ".dylib", ".pyc",
}
_LOCKFILES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "Gemfile.lock", "poetry.lock", "Cargo.lock",
    "composer.lock", "Pipfile.lock",
}
_BUILD_PREFIXES = ("dist/", "build/", ".next/", "out/", "target/")
_MAX_RANGE_LINES = 250


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


@dataclass(frozen=True)
class DevelopmentContextConfig:
    project_root: Path = PROJECT_ROOT
    max_full_lines: int = 150
    max_full_bytes: int = 12_288
    early_session_byte_cap: int = 20_480
    mid_session_byte_cap: int = 10_240
    late_session_byte_cap: int = 4_096
    max_range_lines: int = _MAX_RANGE_LINES
    local_enabled: bool = True
    external_graft_enabled: bool = False
    graft_server_name: str = "graft-context"
    prefer_external: bool = True

    @classmethod
    def from_env(
        cls,
        environ: Optional[Mapping[str, str]] = None,
        project_root: Optional[Path] = None,
    ) -> "DevelopmentContextConfig":
        env = dict(environ or os.environ)
        root = Path(project_root or PROJECT_ROOT).resolve()
        return cls(
            project_root=root,
            max_full_lines=max(10, int(env.get("JARVIS_DEV_CONTEXT_MAX_FULL_LINES", "150"))),
            max_full_bytes=max(1024, int(env.get("JARVIS_DEV_CONTEXT_MAX_FULL_BYTES", "12288"))),
            early_session_byte_cap=max(1024, int(env.get("JARVIS_DEV_CONTEXT_EARLY_BYTES", "20480"))),
            mid_session_byte_cap=max(1024, int(env.get("JARVIS_DEV_CONTEXT_MID_BYTES", "10240"))),
            late_session_byte_cap=max(512, int(env.get("JARVIS_DEV_CONTEXT_LATE_BYTES", "4096"))),
            max_range_lines=max(1, min(500, int(env.get("JARVIS_DEV_CONTEXT_MAX_RANGE_LINES", "250")))),
            local_enabled=_env_bool(env.get("JARVIS_DEV_CONTEXT_LOCAL_ENABLED"), True),
            external_graft_enabled=_env_bool(env.get("JARVIS_GRAFT_CONTEXT_ENABLED"), False),
            graft_server_name=(env.get("JARVIS_GRAFT_CONTEXT_SERVER") or "graft-context").strip(),
            prefer_external=_env_bool(env.get("JARVIS_DEV_CONTEXT_PREFER_EXTERNAL"), True),
        )


class _SessionLedger:
    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def record(
        self,
        session_id: str,
        *,
        path: str,
        projection: str,
        bytes_returned: int,
        bytes_avoided: int,
        decision: str,
    ) -> Dict[str, Any]:
        sid = str(session_id or "default")
        with self._lock:
            state = self._sessions.setdefault(
                sid,
                {
                    "calls": 0,
                    "bytes_returned": 0,
                    "bytes_avoided": 0,
                    "reads": 0,
                    "outlines": 0,
                    "refusals": 0,
                    "ranges": 0,
                    "paths": {},
                    "tripwires": [],
                },
            )
            state["calls"] += 1
            state["bytes_returned"] += max(0, int(bytes_returned))
            state["bytes_avoided"] += max(0, int(bytes_avoided))
            state["paths"][path] = int(state["paths"].get(path, 0)) + 1
            if projection == "content":
                state["reads"] += 1
            elif projection == "outline":
                state["outlines"] += 1
            elif projection == "refused":
                state["refusals"] += 1
            elif projection == "range":
                state["ranges"] += 1

            tripwires: List[str] = []
            if state["paths"][path] >= 4:
                tripwires.append("REPEATED_PATH_READ")
            if state["calls"] >= 30:
                tripwires.append("RUNAWAY_READ_LOOP")
            for item in tripwires:
                if item not in state["tripwires"]:
                    state["tripwires"].append(item)

            return {
                "session_id": sid,
                "decision": decision,
                "bytes_returned": max(0, int(bytes_returned)),
                "bytes_avoided": max(0, int(bytes_avoided)),
                "path_read_count": state["paths"][path],
                "cumulative": {
                    "calls": state["calls"],
                    "bytes_returned": state["bytes_returned"],
                    "bytes_avoided": state["bytes_avoided"],
                    "tripwires": list(state["tripwires"]),
                },
            }

    def status(self, session_id: str) -> Dict[str, Any]:
        sid = str(session_id or "default")
        with self._lock:
            state = self._sessions.get(sid)
            if state is None:
                return {
                    "session_id": sid,
                    "calls": 0,
                    "bytes_returned": 0,
                    "bytes_avoided": 0,
                    "tripwires": [],
                }
            return json.loads(json.dumps({"session_id": sid, **state}))


class LocalDevelopmentContextGovernor:
    """Politica de leitura local deterministica e auditavel."""

    def __init__(self, config: DevelopmentContextConfig) -> None:
        self.config = config
        self.ledger = _SessionLedger()

    def _resolve(self, requested: str) -> tuple[Optional[Path], Optional[str]]:
        raw = str(requested).strip().replace("\\", "/")
        if not raw:
            return None, "EMPTY_PATH"
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.config.project_root / candidate
        try:
            if candidate.exists() and candidate.is_symlink():
                return None, "SYMLINK_REFUSED"
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(self.config.project_root.resolve())
        except (ValueError, OSError):
            return None, "OUTSIDE_PROJECT"
        return resolved, None

    def _graftignore_patterns(self) -> List[str]:
        path = self.config.project_root / ".graftignore"
        if not path.exists():
            return []
        try:
            return [
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
        except OSError:
            return []

    @staticmethod
    def _secret_reason(rel: str) -> Optional[str]:
        name = Path(rel).name
        lower = name.lower()
        if lower == ".env" or (lower.startswith(".env.") and not lower.endswith(".example")):
            return "SECRET"
        if lower.endswith((".pem", ".key", ".p12", ".pfx")):
            return "SECRET"
        if lower.startswith("credentials."):
            return "SECRET"
        return None

    def _ban_reason(self, rel: str, raw: bytes) -> Optional[str]:
        lower_rel = rel.lower()
        name = Path(rel).name
        suffix = Path(rel).suffix.lower()

        secret = self._secret_reason(rel)
        if secret:
            return secret
        if name in _LOCKFILES:
            return "LOCKFILE"
        if name.endswith(".min.js") or name.endswith(".min.css"):
            return "MINIFIED"
        if suffix in _BINARY_EXTENSIONS or b"\x00" in raw[:8192]:
            return "BINARY"
        if any(lower_rel.startswith(prefix) or f"/{prefix}" in lower_rel for prefix in _BUILD_PREFIXES):
            return "BUILD_OUTPUT"
        for pattern in self._graftignore_patterns():
            if fnmatch(rel, pattern):
                return "GRAFTIGNORE"
        return None

    def _effective_byte_cap(
        self,
        session_depth: str,
        budget_remaining: Optional[int],
    ) -> tuple[int, Optional[str]]:
        depth = str(session_depth or "unknown").lower()
        if depth == "early":
            cap = self.config.early_session_byte_cap
            reason = "SESSION_CAP"
        elif depth == "mid":
            cap = self.config.mid_session_byte_cap
            reason = "SESSION_CAP"
        elif depth == "late":
            cap = self.config.late_session_byte_cap
            reason = "SESSION_CAP"
        else:
            cap = self.config.max_full_bytes
            reason = None

        if budget_remaining is not None and int(budget_remaining) >= 0:
            budget_cap = max(0, int(int(budget_remaining) * 0.05))
            if budget_cap < cap:
                return budget_cap, "BUDGET_CAP"
        return cap, reason

    @staticmethod
    def _python_outline(text: str) -> List[Dict[str, Any]]:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []
        outline: List[Dict[str, Any]] = []

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.parents: List[str] = []

            def _add(self, node: Any, kind: str) -> None:
                name = str(node.name)
                qualified = ".".join(self.parents + [name])
                outline.append(
                    {
                        "name": name,
                        "qualified_name": qualified,
                        "kind": kind,
                        "start_line": int(getattr(node, "lineno", 1)),
                        "end_line": int(getattr(node, "end_lineno", getattr(node, "lineno", 1))),
                    }
                )

            def visit_ClassDef(self, node: ast.ClassDef) -> Any:
                self._add(node, "class")
                self.parents.append(node.name)
                self.generic_visit(node)
                self.parents.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
                self._add(node, "function")
                self.parents.append(node.name)
                self.generic_visit(node)
                self.parents.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
                self._add(node, "async_function")
                self.parents.append(node.name)
                self.generic_visit(node)
                self.parents.pop()

        Visitor().visit(tree)
        return outline

    @staticmethod
    def _markdown_outline(text: str) -> List[Dict[str, Any]]:
        result = []
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                title = stripped[level:].strip()
                if title:
                    result.append(
                        {
                            "name": title,
                            "kind": f"heading_{min(level, 6)}",
                            "start_line": index,
                            "end_line": index,
                        }
                    )
        return result

    def _outline(self, rel: str, text: str) -> List[Dict[str, Any]]:
        suffix = Path(rel).suffix.lower()
        if suffix == ".py":
            return self._python_outline(text)
        if suffix in {".md", ".markdown"}:
            return self._markdown_outline(text)
        return []

    def safe_read(
        self,
        path: str,
        *,
        session_id: str = "default",
        session_depth: str = "unknown",
        budget_remaining: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not self.config.local_enabled:
            return {"status": "indisponivel", "motivo": "Governor local desativado."}

        resolved, path_error = self._resolve(path)
        if resolved is None:
            return {
                "status": "bloqueado",
                "projection": "refused",
                "reason": path_error,
                "path": str(path),
            }
        if not resolved.exists() or not resolved.is_file():
            return {
                "status": "erro",
                "projection": "refused",
                "reason": "NOT_FOUND",
                "path": str(path),
            }

        rel = resolved.relative_to(self.config.project_root).as_posix()
        try:
            raw = resolved.read_bytes()
        except OSError as exc:
            return {
                "status": "erro",
                "projection": "refused",
                "reason": "READ_ERROR",
                "motivo": f"{exc.__class__.__name__}: {exc}",
                "path": rel,
            }

        ban = self._ban_reason(rel, raw)
        if ban:
            receipt = self.ledger.record(
                session_id,
                path=rel,
                projection="refused",
                bytes_returned=0,
                bytes_avoided=len(raw),
                decision=ban,
            )
            return {
                "status": "bloqueado",
                "backend": "local_context_governor",
                "projection": "refused",
                "reason": ban,
                "path": rel,
                "actual": {"bytes": len(raw), "lines": 0},
                "_receipt": receipt,
            }

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            receipt = self.ledger.record(
                session_id,
                path=rel,
                projection="refused",
                bytes_returned=0,
                bytes_avoided=len(raw),
                decision="BINARY",
            )
            return {
                "status": "bloqueado",
                "backend": "local_context_governor",
                "projection": "refused",
                "reason": "BINARY",
                "path": rel,
                "_receipt": receipt,
            }

        line_count = len(text.splitlines())
        effective_cap, cap_reason = self._effective_byte_cap(session_depth, budget_remaining)
        full_allowed = (
            line_count <= self.config.max_full_lines
            and len(raw) <= effective_cap
        )

        if full_allowed:
            receipt = self.ledger.record(
                session_id,
                path=rel,
                projection="content",
                bytes_returned=len(raw),
                bytes_avoided=0,
                decision="CONTENT",
            )
            return {
                "status": "sucesso",
                "backend": "local_context_governor",
                "projection": "content",
                "reason": "CONTENT",
                "path": rel,
                "content": text,
                "actual": {"bytes": len(raw), "lines": line_count},
                "thresholds": {
                    "lines": self.config.max_full_lines,
                    "bytes": effective_cap,
                },
                "_receipt": receipt,
            }

        outline = self._outline(rel, text)
        returned = len(json.dumps(outline, ensure_ascii=False).encode("utf-8"))
        reason = (
            cap_reason
            if len(raw) > effective_cap and cap_reason
            else "OUTLINE"
        )
        receipt = self.ledger.record(
            session_id,
            path=rel,
            projection="outline",
            bytes_returned=returned,
            bytes_avoided=max(0, len(raw) - returned),
            decision=reason,
        )
        return {
            "status": "sucesso",
            "backend": "local_context_governor",
            "projection": "outline",
            "reason": reason,
            "path": rel,
            "outline": outline,
            "actual": {"bytes": len(raw), "lines": line_count},
            "thresholds": {
                "lines": self.config.max_full_lines,
                "bytes": effective_cap,
            },
            "_receipt": receipt,
            "observacao": (
                "Outline vazio significa apenas que o baseline local nao possui parser "
                "estrutural para este formato; nao e inferida estrutura inexistente."
            ),
        }

    def file_outline(
        self,
        path: str,
        *,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        resolved, path_error = self._resolve(path)
        if resolved is None:
            return {"status": "bloqueado", "projection": "refused", "reason": path_error}
        if not resolved.exists() or not resolved.is_file():
            return {"status": "erro", "projection": "refused", "reason": "NOT_FOUND"}

        rel = resolved.relative_to(self.config.project_root).as_posix()
        raw = resolved.read_bytes()
        ban = self._ban_reason(rel, raw)
        if ban:
            receipt = self.ledger.record(
                session_id,
                path=rel,
                projection="refused",
                bytes_returned=0,
                bytes_avoided=len(raw),
                decision=ban,
            )
            return {
                "status": "bloqueado",
                "projection": "refused",
                "reason": ban,
                "path": rel,
                "_receipt": receipt,
            }
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return {"status": "bloqueado", "projection": "refused", "reason": "BINARY"}

        outline = self._outline(rel, text)
        returned = len(json.dumps(outline, ensure_ascii=False).encode("utf-8"))
        receipt = self.ledger.record(
            session_id,
            path=rel,
            projection="outline",
            bytes_returned=returned,
            bytes_avoided=max(0, len(raw) - returned),
            decision="OUTLINE",
        )
        return {
            "status": "sucesso",
            "backend": "local_context_governor",
            "projection": "outline",
            "path": rel,
            "outline": outline,
            "_receipt": receipt,
        }

    def read_range(
        self,
        path: str,
        start: int,
        end: int,
        *,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        start_line = max(1, int(start))
        end_line = max(start_line, int(end))
        if end_line - start_line + 1 > self.config.max_range_lines:
            return {
                "status": "bloqueado",
                "projection": "refused",
                "reason": "RANGE_TOO_LARGE",
                "max_lines": self.config.max_range_lines,
            }

        resolved, path_error = self._resolve(path)
        if resolved is None:
            return {"status": "bloqueado", "projection": "refused", "reason": path_error}
        if not resolved.exists() or not resolved.is_file():
            return {"status": "erro", "projection": "refused", "reason": "NOT_FOUND"}

        rel = resolved.relative_to(self.config.project_root).as_posix()
        raw = resolved.read_bytes()
        ban = self._ban_reason(rel, raw)
        if ban:
            receipt = self.ledger.record(
                session_id,
                path=rel,
                projection="refused",
                bytes_returned=0,
                bytes_avoided=len(raw),
                decision=ban,
            )
            return {
                "status": "bloqueado",
                "projection": "refused",
                "reason": ban,
                "path": rel,
                "_receipt": receipt,
            }

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return {"status": "bloqueado", "projection": "refused", "reason": "BINARY"}

        lines = text.splitlines()
        bounded_end = min(end_line, len(lines))
        selected = "\n".join(lines[start_line - 1:bounded_end])
        selected_bytes = len(selected.encode("utf-8"))
        receipt = self.ledger.record(
            session_id,
            path=rel,
            projection="range",
            bytes_returned=selected_bytes,
            bytes_avoided=max(0, len(raw) - selected_bytes),
            decision="RANGE",
        )
        return {
            "status": "sucesso",
            "backend": "local_context_governor",
            "projection": "range",
            "path": rel,
            "start": start_line,
            "end": bounded_end,
            "content": selected,
            "_receipt": receipt,
        }

    def session_status(self, session_id: str) -> Dict[str, Any]:
        return self.ledger.status(session_id)


class FlyingRobotsGraftAdapter:
    """Adapter read-only do @flyingrobots/graft via MCP oficial."""

    def __init__(
        self,
        config: DevelopmentContextConfig,
        mcp_manager: Any,
    ) -> None:
        self.config = config
        self.mcp_manager = mcp_manager

    @property
    def enabled(self) -> bool:
        return bool(self.config.external_graft_enabled and self.mcp_manager is not None)

    def discover(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "indisponivel", "motivo": "Graft externo desativado."}
        return self.mcp_manager.discover(self.config.graft_server_name)

    def _call(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "indisponivel", "motivo": "Graft externo desativado."}
        # No modo repo-local, o processo `graft serve` ja e iniciado com cwd
        # na raiz autorizada. Nao roteamos cwd por chamada; isso e reservado
        # para uma futura integracao daemon/multi-repo explicitamente governada.
        return self.mcp_manager.call_tool(
            self.config.graft_server_name,
            tool,
            dict(arguments),
        )

    def safe_read(self, path: str, intent: Optional[str] = None) -> Dict[str, Any]:
        args: Dict[str, Any] = {"path": path}
        if intent:
            args["intent"] = intent
        return self._call("safe_read", args)

    def file_outline(self, path: str) -> Dict[str, Any]:
        return self._call("file_outline", {"path": path})

    def read_range(self, path: str, start: int, end: int) -> Dict[str, Any]:
        return self._call(
            "read_range",
            {"path": path, "start": int(start), "end": int(end)},
        )

    def changed_since(self, path: str) -> Dict[str, Any]:
        return self._call("changed_since", {"path": path})


class DevelopmentContextEngine:
    """Facade de contexto governado para agentes de desenvolvimento."""

    def __init__(
        self,
        config: Optional[DevelopmentContextConfig] = None,
        mcp_manager: Any = None,
    ) -> None:
        self.config = config or DevelopmentContextConfig.from_env()
        self.local = LocalDevelopmentContextGovernor(self.config)
        self.external = FlyingRobotsGraftAdapter(self.config, mcp_manager)

    def safe_read(
        self,
        path: str,
        *,
        session_id: str = "default",
        session_depth: str = "unknown",
        budget_remaining: Optional[int] = None,
        intent: Optional[str] = None,
        prefer_external: Optional[bool] = None,
    ) -> Dict[str, Any]:
        use_external = (
            self.config.prefer_external
            if prefer_external is None
            else bool(prefer_external)
        )
        if use_external and self.external.enabled:
            result = self.external.safe_read(path, intent=intent)
            if result.get("status") == "sucesso":
                return {
                    "status": "sucesso",
                    "backend": "flyingrobots-graft",
                    "resultado": result,
                }
        return self.local.safe_read(
            path,
            session_id=session_id,
            session_depth=session_depth,
            budget_remaining=budget_remaining,
        )

    def file_outline(
        self,
        path: str,
        *,
        session_id: str = "default",
        prefer_external: Optional[bool] = None,
    ) -> Dict[str, Any]:
        use_external = self.config.prefer_external if prefer_external is None else bool(prefer_external)
        if use_external and self.external.enabled:
            result = self.external.file_outline(path)
            if result.get("status") == "sucesso":
                return {"status": "sucesso", "backend": "flyingrobots-graft", "resultado": result}
        return self.local.file_outline(path, session_id=session_id)

    def read_range(
        self,
        path: str,
        start: int,
        end: int,
        *,
        session_id: str = "default",
        prefer_external: Optional[bool] = None,
    ) -> Dict[str, Any]:
        use_external = self.config.prefer_external if prefer_external is None else bool(prefer_external)
        if use_external and self.external.enabled:
            result = self.external.read_range(path, start, end)
            if result.get("status") == "sucesso":
                return {"status": "sucesso", "backend": "flyingrobots-graft", "resultado": result}
        return self.local.read_range(path, start, end, session_id=session_id)

    def session_status(self, session_id: str) -> Dict[str, Any]:
        return self.local.session_status(session_id)

    def status(self) -> Dict[str, Any]:
        external = self.external.discover() if self.external.enabled else None
        return {
            "baseline": "local_context_governor",
            "preferred_backend": "flyingrobots-graft",
            "pinned_external_release": "v0.14.0",
            "local_enabled": self.config.local_enabled,
            "external_enabled": self.config.external_graft_enabled,
            "external_server": self.config.graft_server_name,
            "prefer_external": self.config.prefer_external,
            "thresholds": {
                "full_lines": self.config.max_full_lines,
                "full_bytes": self.config.max_full_bytes,
                "max_range_lines": self.config.max_range_lines,
                "session_caps": {
                    "early": self.config.early_session_byte_cap,
                    "mid": self.config.mid_session_byte_cap,
                    "late": self.config.late_session_byte_cap,
                },
            },
            "external_discovery": external,
            "trailhq_graft_role": "challenger_overlap_with_point_8_not_core",
        }
