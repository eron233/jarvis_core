"""
JARVIS - Inteligencia Estrutural do Proprio Codigo

Dois niveis complementares:
1. fallback AST local, deterministico e sem dependencias externas, focado em Python;
2. backend codebase-memory-mcp via MCP oficial, quando explicitamente provisionado.

O fallback nao tenta competir com Tree-sitter/LSP em centenas de linguagens.
Ele existe para garantir autoconsciencia estrutural minima e verificavel do
proprio JARVIS mesmo sem o binario externo.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, Iterable, List, Mapping, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "codebase_intelligence.sqlite3"

_DEFAULT_IGNORES = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "data",
    "logs",
    "reports",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


@dataclass(frozen=True)
class CodebaseIntelligenceConfig:
    project_root: Path = PROJECT_ROOT
    db_path: Path = DEFAULT_DB
    local_ast_enabled: bool = True
    external_mcp_enabled: bool = False
    mcp_server_name: str = "codebase-memory"
    mcp_project_name: str = "jarvis_core"
    external_auto_index: bool = False
    max_files: int = 5000
    max_file_bytes: int = 1_500_000

    @classmethod
    def from_env(
        cls,
        environ: Optional[Mapping[str, str]] = None,
        project_root: Optional[Path] = None,
    ) -> "CodebaseIntelligenceConfig":
        env = dict(environ or os.environ)
        root = Path(project_root or PROJECT_ROOT).resolve()
        db_raw = (env.get("JARVIS_CODEBASE_DB_PATH") or "").strip()
        db_path = Path(db_raw) if db_raw else root / "data" / "codebase_intelligence.sqlite3"
        if not db_path.is_absolute():
            db_path = root / db_path
        return cls(
            project_root=root,
            db_path=db_path,
            local_ast_enabled=_env_bool(env.get("JARVIS_CODEBASE_AST_ENABLED"), True),
            external_mcp_enabled=_env_bool(env.get("JARVIS_CODEBASE_MCP_ENABLED"), False),
            mcp_server_name=(env.get("JARVIS_CODEBASE_MCP_SERVER") or "codebase-memory").strip(),
            mcp_project_name=(env.get("JARVIS_CODEBASE_MCP_PROJECT") or root.name).strip(),
            external_auto_index=_env_bool(env.get("JARVIS_CODEBASE_MCP_AUTO_INDEX"), False),
            max_files=max(10, int(env.get("JARVIS_CODEBASE_MAX_FILES", "5000"))),
            max_file_bytes=max(4096, int(env.get("JARVIS_CODEBASE_MAX_FILE_BYTES", "1500000"))),
        )


def _call_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _call_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return None


def _decorator_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return _call_name(node)


def _safe_rel(path: Path, root: Path) -> Optional[str]:
    try:
        resolved = path.resolve()
        rel = resolved.relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    return rel.as_posix()


class LocalPythonCodeGraph:
    """Grafo estrutural Python persistente com evidencias path/linha."""

    def __init__(self, config: CodebaseIntelligenceConfig) -> None:
        self.config = config
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.config.db_path), timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS code_files (
                    path TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS code_symbols (
                    symbol_id TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    qualified_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    lineno INTEGER NOT NULL,
                    end_lineno INTEGER,
                    parent_qualified TEXT,
                    decorators_json TEXT NOT NULL,
                    FOREIGN KEY(path) REFERENCES code_files(path)
                );

                CREATE INDEX IF NOT EXISTS idx_code_symbols_name
                ON code_symbols(name);
                CREATE INDEX IF NOT EXISTS idx_code_symbols_path
                ON code_symbols(path);

                CREATE TABLE IF NOT EXISTS code_edges (
                    edge_id TEXT PRIMARY KEY,
                    source_symbol_id TEXT,
                    target_symbol_id TEXT,
                    target_text TEXT,
                    relation TEXT NOT NULL,
                    evidence_path TEXT NOT NULL,
                    evidence_lineno INTEGER,
                    resolution TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_code_edges_src
                ON code_edges(source_symbol_id, relation);
                CREATE INDEX IF NOT EXISTS idx_code_edges_dst
                ON code_edges(target_symbol_id, relation);

                CREATE TABLE IF NOT EXISTS code_routes (
                    route_id TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    symbol_id TEXT NOT NULL,
                    http_method TEXT,
                    route_path TEXT,
                    decorator TEXT NOT NULL,
                    lineno INTEGER NOT NULL
                );
                """
            )
            conn.commit()

    def _iter_python_files(self) -> Iterable[Path]:
        count = 0
        root = self.config.project_root
        for path in sorted(root.rglob("*.py")):
            rel = _safe_rel(path, root)
            if rel is None:
                continue
            if any(part in _DEFAULT_IGNORES for part in Path(rel).parts):
                continue
            try:
                if path.is_symlink() or path.stat().st_size > self.config.max_file_bytes:
                    continue
            except OSError:
                continue
            yield path
            count += 1
            if count >= self.config.max_files:
                break

    @staticmethod
    def _symbol_id(path: str, qualified: str, lineno: int) -> str:
        raw = f"{path}:{qualified}:{lineno}".encode("utf-8")
        return "sym_" + sha256(raw).hexdigest()[:24]

    def index(self) -> Dict[str, Any]:
        if not self.config.local_ast_enabled:
            return {"status": "indisponivel", "motivo": "Fallback AST local desativado."}

        root = self.config.project_root
        parsed_files: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        definitions: Dict[str, List[Dict[str, Any]]] = {}
        file_modules: Dict[str, str] = {}

        for path in self._iter_python_files():
            rel = _safe_rel(path, root)
            if rel is None:
                continue
            try:
                raw = path.read_bytes()
                text = raw.decode("utf-8")
                tree = ast.parse(text, filename=rel)
            except Exception as exc:
                errors.append({"path": rel, "erro": f"{exc.__class__.__name__}: {exc}"})
                continue

            module = rel[:-3].replace("/", ".")
            if module.endswith(".__init__"):
                module = module[:-9]
            file_modules[module] = rel
            visitor = _PythonStructureVisitor(rel, module)
            visitor.visit(tree)
            parsed_files.append(
                {
                    "path": rel,
                    "sha256": sha256(raw).hexdigest(),
                    "size_bytes": len(raw),
                    "symbols": visitor.symbols,
                    "calls": visitor.calls,
                    "imports": visitor.imports,
                    "routes": visitor.routes,
                }
            )
            for symbol in visitor.symbols:
                definitions.setdefault(symbol["name"], []).append(symbol)

        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM code_routes")
            conn.execute("DELETE FROM code_edges")
            conn.execute("DELETE FROM code_symbols")
            conn.execute("DELETE FROM code_files")

            for file_data in parsed_files:
                conn.execute(
                    "INSERT INTO code_files(path, sha256, size_bytes, indexed_at) VALUES (?, ?, ?, ?)",
                    (file_data["path"], file_data["sha256"], file_data["size_bytes"], now),
                )
                for symbol in file_data["symbols"]:
                    conn.execute(
                        """
                        INSERT INTO code_symbols(
                            symbol_id,path,name,qualified_name,kind,lineno,end_lineno,
                            parent_qualified,decorators_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            symbol["symbol_id"], symbol["path"], symbol["name"],
                            symbol["qualified_name"], symbol["kind"], symbol["lineno"],
                            symbol["end_lineno"], symbol["parent_qualified"],
                            json.dumps(symbol["decorators"], ensure_ascii=False),
                        ),
                    )

            for file_data in parsed_files:
                for call in file_data["calls"]:
                    candidates = definitions.get(call["target_short"], [])
                    target_id = candidates[0]["symbol_id"] if len(candidates) == 1 else None
                    resolution = "unique_name" if target_id else "unresolved_or_ambiguous"
                    edge_raw = (
                        f"{call['source_symbol_id']}:{call['target_text']}:"
                        f"{call['path']}:{call['lineno']}:CALLS"
                    )
                    conn.execute(
                        """
                        INSERT INTO code_edges(
                            edge_id,source_symbol_id,target_symbol_id,target_text,relation,
                            evidence_path,evidence_lineno,resolution
                        ) VALUES (?, ?, ?, ?, 'CALLS', ?, ?, ?)
                        """,
                        (
                            "edge_" + sha256(edge_raw.encode()).hexdigest()[:24],
                            call["source_symbol_id"], target_id, call["target_text"],
                            call["path"], call["lineno"], resolution,
                        ),
                    )

                for imported in file_data["imports"]:
                    target_path = None
                    module = imported["module"]
                    if module in file_modules:
                        target_path = file_modules[module]
                    elif module and module.split(".")[0] in file_modules:
                        target_path = file_modules[module.split(".")[0]]
                    edge_raw = f"{file_data['path']}:{module}:{imported['lineno']}:IMPORTS"
                    conn.execute(
                        """
                        INSERT INTO code_edges(
                            edge_id,source_symbol_id,target_symbol_id,target_text,relation,
                            evidence_path,evidence_lineno,resolution
                        ) VALUES (?, NULL, NULL, ?, 'IMPORTS', ?, ?, ?)
                        """,
                        (
                            "edge_" + sha256(edge_raw.encode()).hexdigest()[:24],
                            target_path or module,
                            file_data["path"],
                            imported["lineno"],
                            "module_path" if target_path else "module_text",
                        ),
                    )

                symbols_by_q = {item["qualified_name"]: item for item in file_data["symbols"]}
                for route in file_data["routes"]:
                    symbol = symbols_by_q.get(route["qualified_name"])
                    if symbol is None:
                        continue
                    route_raw = f"{route['path']}:{route['qualified_name']}:{route['decorator']}"
                    conn.execute(
                        """
                        INSERT INTO code_routes(
                            route_id,path,symbol_id,http_method,route_path,decorator,lineno
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "route_" + sha256(route_raw.encode()).hexdigest()[:24],
                            route["path"], symbol["symbol_id"], route["http_method"],
                            route["route_path"], route["decorator"], route["lineno"],
                        ),
                    )
            conn.commit()

        stats = self.architecture()
        return {
            "status": "sucesso",
            "backend": "python_ast_local",
            "project_root": str(root),
            "indexed_at": now,
            "arquivos_indexados": len(parsed_files),
            "erros_parse": errors,
            "estatisticas": stats.get("estatisticas", {}),
        }

    def architecture(self) -> Dict[str, Any]:
        with self._connect() as conn:
            files = conn.execute("SELECT COUNT(*) AS n FROM code_files").fetchone()["n"]
            symbols = conn.execute("SELECT COUNT(*) AS n FROM code_symbols").fetchone()["n"]
            calls = conn.execute(
                "SELECT COUNT(*) AS n FROM code_edges WHERE relation='CALLS'"
            ).fetchone()["n"]
            imports = conn.execute(
                "SELECT COUNT(*) AS n FROM code_edges WHERE relation='IMPORTS'"
            ).fetchone()["n"]
            routes = conn.execute("SELECT COUNT(*) AS n FROM code_routes").fetchone()["n"]
            kinds = conn.execute(
                "SELECT kind, COUNT(*) AS n FROM code_symbols GROUP BY kind ORDER BY n DESC"
            ).fetchall()
            hotspots = conn.execute(
                """
                SELECT s.qualified_name, s.path, COUNT(e.edge_id) AS inbound_calls
                FROM code_symbols s
                LEFT JOIN code_edges e ON e.target_symbol_id=s.symbol_id AND e.relation='CALLS'
                GROUP BY s.symbol_id
                ORDER BY inbound_calls DESC, s.qualified_name
                LIMIT 20
                """
            ).fetchall()

        return {
            "status": "sucesso",
            "backend": "python_ast_local",
            "estatisticas": {
                "arquivos": files,
                "simbolos": symbols,
                "calls": calls,
                "imports": imports,
                "rotas_http": routes,
                "tipos_simbolo": {row["kind"]: row["n"] for row in kinds},
            },
            "hotspots": [dict(row) for row in hotspots],
            "limites": (
                "Fallback sintatico Python. Chamadas dinamicas, dispatch indireto, aliases "
                "complexos e outras linguagens exigem backend estrutural externo."
            ),
        }

    def search(self, query: str, limit: int = 30) -> Dict[str, Any]:
        clean = str(query).strip()
        if not clean:
            return {"status": "erro", "resultados": [], "motivo": "Consulta vazia."}
        pattern = f"%{clean.lower()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT symbol_id,path,name,qualified_name,kind,lineno,end_lineno,parent_qualified
                FROM code_symbols
                WHERE LOWER(name) LIKE ? OR LOWER(qualified_name) LIKE ? OR LOWER(path) LIKE ?
                ORDER BY
                    CASE WHEN LOWER(name)=? THEN 0 ELSE 1 END,
                    path, lineno
                LIMIT ?
                """,
                (pattern, pattern, pattern, clean.lower(), max(1, int(limit))),
            ).fetchall()
        return {
            "status": "sucesso",
            "backend": "python_ast_local",
            "resultados": [dict(row) for row in rows],
            "quantidade": len(rows),
        }

    def trace(self, symbol_name: str, direction: str = "both", depth: int = 3) -> Dict[str, Any]:
        matches = self.search(symbol_name, limit=20)
        exact = [item for item in matches.get("resultados", []) if item["name"] == symbol_name or item["qualified_name"] == symbol_name]
        if len(exact) != 1:
            return {
                "status": "indisponivel",
                "backend": "python_ast_local",
                "motivo": "Simbolo nao encontrado de forma unica.",
                "candidatos": exact or matches.get("resultados", []),
            }
        origin = exact[0]
        allowed = {"inbound", "outbound", "both"}
        direction = direction if direction in allowed else "both"
        max_depth = max(1, min(5, int(depth)))

        visited = {origin["symbol_id"]}
        frontier = [(origin["symbol_id"], 0)]
        edges_out: List[Dict[str, Any]] = []

        with self._connect() as conn:
            while frontier:
                current, current_depth = frontier.pop(0)
                if current_depth >= max_depth:
                    continue
                clauses = []
                params: List[Any] = []
                if direction in {"outbound", "both"}:
                    clauses.append("source_symbol_id=?")
                    params.append(current)
                if direction in {"inbound", "both"}:
                    clauses.append("target_symbol_id=?")
                    params.append(current)
                rows = conn.execute(
                    f"""
                    SELECT e.*, s1.qualified_name AS source_name, s2.qualified_name AS target_name
                    FROM code_edges e
                    LEFT JOIN code_symbols s1 ON s1.symbol_id=e.source_symbol_id
                    LEFT JOIN code_symbols s2 ON s2.symbol_id=e.target_symbol_id
                    WHERE e.relation='CALLS' AND ({' OR '.join(clauses)})
                    """,
                    params,
                ).fetchall()
                for row in rows:
                    item = dict(row)
                    item["depth"] = current_depth + 1
                    edges_out.append(item)
                    for neighbor in (row["source_symbol_id"], row["target_symbol_id"]):
                        if neighbor and neighbor not in visited:
                            visited.add(neighbor)
                            frontier.append((neighbor, current_depth + 1))

        return {
            "status": "sucesso",
            "backend": "python_ast_local",
            "origem": origin,
            "direction": direction,
            "depth": max_depth,
            "arestas": edges_out,
            "simbolos_visitados": len(visited),
        }

    def impact(self, symbol_name: str, depth: int = 3) -> Dict[str, Any]:
        trace = self.trace(symbol_name, direction="inbound", depth=depth)
        if trace.get("status") != "sucesso":
            return trace
        affected = {}
        for edge in trace["arestas"]:
            source_id = edge.get("source_symbol_id")
            if not source_id:
                continue
            affected[source_id] = {
                "symbol_id": source_id,
                "qualified_name": edge.get("source_name"),
                "evidence_path": edge.get("evidence_path"),
                "evidence_lineno": edge.get("evidence_lineno"),
                "depth": edge.get("depth"),
            }
        return {
            "status": "sucesso",
            "backend": "python_ast_local",
            "simbolo": symbol_name,
            "impacto_direto_indireto": list(affected.values()),
            "quantidade": len(affected),
            "classificacao_risco": None,
            "observacao": (
                "O fallback relata dependencias estruturais observadas. Ele nao inventa "
                "classificacao de risco; risco exige contexto/testes adicionais."
            ),
        }

    def snippet(self, symbol_name: str, context_lines: int = 2) -> Dict[str, Any]:
        matches = self.search(symbol_name, limit=20)
        exact = [item for item in matches.get("resultados", []) if item["name"] == symbol_name or item["qualified_name"] == symbol_name]
        if len(exact) != 1:
            return {"status": "indisponivel", "motivo": "Simbolo nao encontrado de forma unica.", "candidatos": exact}
        item = exact[0]
        path = self.config.project_root / item["path"]
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            return {"status": "erro", "motivo": f"{exc.__class__.__name__}: {exc}"}
        start = max(1, int(item["lineno"]) - max(0, int(context_lines)))
        end_line = int(item["end_lineno"] or item["lineno"])
        end = min(len(lines), end_line + max(0, int(context_lines)))
        return {
            "status": "sucesso",
            "path": item["path"],
            "qualified_name": item["qualified_name"],
            "start_line": start,
            "end_line": end,
            "conteudo": "\n".join(lines[start - 1:end]),
        }


class _PythonStructureVisitor(ast.NodeVisitor):
    def __init__(self, path: str, module: str) -> None:
        self.path = path
        self.module = module
        self.scope: List[str] = []
        self.symbol_stack: List[Optional[str]] = []
        self.symbols: List[Dict[str, Any]] = []
        self.calls: List[Dict[str, Any]] = []
        self.imports: List[Dict[str, Any]] = []
        self.routes: List[Dict[str, Any]] = []

    def _qualified(self, name: str) -> str:
        parts = [self.module] + self.scope + [name]
        return ".".join(part for part in parts if part)

    def _add_symbol(self, node: ast.AST, name: str, kind: str, decorators: List[str]) -> str:
        qualified = self._qualified(name)
        symbol_id = LocalPythonCodeGraph._symbol_id(self.path, qualified, int(getattr(node, "lineno", 1)))
        parent = ".".join([self.module] + self.scope) if self.scope else self.module
        self.symbols.append(
            {
                "symbol_id": symbol_id,
                "path": self.path,
                "name": name,
                "qualified_name": qualified,
                "kind": kind,
                "lineno": int(getattr(node, "lineno", 1)),
                "end_lineno": int(getattr(node, "end_lineno", getattr(node, "lineno", 1))),
                "parent_qualified": parent or None,
                "decorators": decorators,
            }
        )
        return symbol_id

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        decorators = [name for item in node.decorator_list if (name := _decorator_name(item))]
        symbol_id = self._add_symbol(node, node.name, "class", decorators)
        self.scope.append(node.name)
        self.symbol_stack.append(symbol_id)
        self.generic_visit(node)
        self.symbol_stack.pop()
        self.scope.pop()

    def _visit_function(self, node: Any, kind: str) -> Any:
        decorators = [name for item in node.decorator_list if (name := _decorator_name(item))]
        qualified = self._qualified(node.name)
        symbol_id = self._add_symbol(node, node.name, kind, decorators)
        for decorator_node, decorator in zip(node.decorator_list, decorators):
            lower = decorator.lower()
            method = None
            for candidate in ("get", "post", "put", "patch", "delete", "options", "head"):
                if lower.endswith("." + candidate):
                    method = candidate.upper()
                    break
            if method:
                route_path = None
                if isinstance(decorator_node, ast.Call) and decorator_node.args:
                    first = decorator_node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        route_path = first.value
                self.routes.append(
                    {
                        "path": self.path,
                        "qualified_name": qualified,
                        "http_method": method,
                        "route_path": route_path,
                        "decorator": decorator,
                        "lineno": int(getattr(node, "lineno", 1)),
                    }
                )
        self.scope.append(node.name)
        self.symbol_stack.append(symbol_id)
        self.generic_visit(node)
        self.symbol_stack.pop()
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        return self._visit_function(node, "function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        return self._visit_function(node, "async_function")

    def visit_Call(self, node: ast.Call) -> Any:
        target = _call_name(node.func)
        source = self.symbol_stack[-1] if self.symbol_stack else None
        if target and source:
            self.calls.append(
                {
                    "source_symbol_id": source,
                    "target_text": target,
                    "target_short": target.split(".")[-1],
                    "path": self.path,
                    "lineno": int(getattr(node, "lineno", 1)),
                }
            )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            self.imports.append(
                {
                    "module": alias.name,
                    "lineno": int(getattr(node, "lineno", 1)),
                }
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        self.imports.append(
            {
                "module": node.module or "",
                "lineno": int(getattr(node, "lineno", 1)),
            }
        )


class CodebaseMemoryMCPAdapter:
    """Adapter conservador do codebase-memory-mcp via MCP oficial."""

    def __init__(self, config: CodebaseIntelligenceConfig, mcp_manager: Any) -> None:
        self.config = config
        self.mcp_manager = mcp_manager

    @property
    def enabled(self) -> bool:
        return bool(self.config.external_mcp_enabled and self.mcp_manager is not None)

    def discover(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "indisponivel", "motivo": "Backend codebase-memory MCP desativado."}
        return self.mcp_manager.discover(self.config.mcp_server_name)

    def index(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "indisponivel", "motivo": "Backend codebase-memory MCP desativado."}
        if not self.config.external_auto_index:
            return {
                "status": "bloqueado",
                "motivo": "Auto-index MCP desativado; habilite explicitamente após provisionar o servidor.",
            }
        return self.mcp_manager.call_tool(
            self.config.mcp_server_name,
            "index_repository",
            {
                "repo_path": str(self.config.project_root),
                "name": self.config.mcp_project_name,
                "persistence": False,
            },
        )

    def architecture(self) -> Dict[str, Any]:
        return self.mcp_manager.call_tool(
            self.config.mcp_server_name,
            "get_architecture",
            {"project": self.config.mcp_project_name},
        )

    def search(self, name_pattern: str, label: Optional[str] = None, limit: int = 30) -> Dict[str, Any]:
        args: Dict[str, Any] = {
            "project": self.config.mcp_project_name,
            "name_pattern": name_pattern,
            "limit": max(1, int(limit)),
        }
        if label:
            args["label"] = label
        return self.mcp_manager.call_tool(
            self.config.mcp_server_name,
            "search_graph",
            args,
        )

    def trace(self, function_name: str, direction: str = "both", depth: int = 3) -> Dict[str, Any]:
        return self.mcp_manager.call_tool(
            self.config.mcp_server_name,
            "trace_path",
            {
                "project": self.config.mcp_project_name,
                "function_name": function_name,
                "direction": direction,
                "depth": max(1, min(5, int(depth))),
            },
        )


class CodebaseIntelligenceEngine:
    """Facade: codebase-memory-mcp quando disponível, AST local como baseline."""

    def __init__(
        self,
        config: Optional[CodebaseIntelligenceConfig] = None,
        mcp_manager: Any = None,
    ) -> None:
        self.config = config or CodebaseIntelligenceConfig.from_env()
        self.local = LocalPythonCodeGraph(self.config)
        self.external = CodebaseMemoryMCPAdapter(self.config, mcp_manager)

    def index(self, prefer_external: bool = True) -> Dict[str, Any]:
        external = None
        if prefer_external and self.external.enabled:
            external = self.external.index()
            if external.get("status") == "sucesso":
                return {
                    "status": "sucesso",
                    "backend": "codebase-memory-mcp",
                    "resultado": external,
                }
        local = self.local.index()
        if external is not None:
            local["external_attempt"] = external
        return local

    def architecture(self, prefer_external: bool = True) -> Dict[str, Any]:
        if prefer_external and self.external.enabled:
            result = self.external.architecture()
            if result.get("status") == "sucesso":
                return {"status": "sucesso", "backend": "codebase-memory-mcp", "resultado": result}
        return self.local.architecture()

    def search(self, query: str, limit: int = 30, prefer_external: bool = True) -> Dict[str, Any]:
        if prefer_external and self.external.enabled:
            result = self.external.search(query, limit=limit)
            if result.get("status") == "sucesso":
                return {"status": "sucesso", "backend": "codebase-memory-mcp", "resultado": result}
        return self.local.search(query, limit=limit)

    def trace(self, symbol_name: str, direction: str = "both", depth: int = 3, prefer_external: bool = True) -> Dict[str, Any]:
        if prefer_external and self.external.enabled:
            result = self.external.trace(symbol_name, direction=direction, depth=depth)
            if result.get("status") == "sucesso":
                return {"status": "sucesso", "backend": "codebase-memory-mcp", "resultado": result}
        return self.local.trace(symbol_name, direction=direction, depth=depth)

    def impact(self, symbol_name: str, depth: int = 3) -> Dict[str, Any]:
        return self.local.impact(symbol_name, depth=depth)

    def snippet(self, symbol_name: str) -> Dict[str, Any]:
        return self.local.snippet(symbol_name)

    def status(self) -> Dict[str, Any]:
        external_discovery = None
        if self.external.enabled:
            external_discovery = self.external.discover()
        return {
            "project_root": str(self.config.project_root),
            "db_path": str(self.config.db_path),
            "local_ast_enabled": self.config.local_ast_enabled,
            "external_mcp_enabled": self.config.external_mcp_enabled,
            "external_server": self.config.mcp_server_name,
            "external_project": self.config.mcp_project_name,
            "external_auto_index": self.config.external_auto_index,
            "external_discovery": external_discovery,
            "baseline": "python_ast_local",
            "preferred_backend": "codebase-memory-mcp",
            "claims_verified_locally": False,
        }
