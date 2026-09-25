"""
JARVIS - Execucao de codigo em subprocesso restrito (micro-sandbox)

Responsavel por:
- executar trechos curtos de Python em um subprocesso separado, com limites de recursos
- bloquear, por analise estatica, imports e construcoes que dao acesso ao sistema
- registrar cada execucao para auditoria

Limites honestos:
- NAO e uma fronteira de seguranca equivalente a container/VM. O filtro AST e os
  builtins reduzidos elevam muito o custo de um abuso, mas codigo hostil e
  determinado pode encontrar brechas no interpretador. Por isso a execucao vem
  DESLIGADA por padrao e so liga com JARVIS_ENABLE_CODE_SANDBOX=true.
- Limites de CPU, memoria, arquivos e processos so existem em Linux/macOS
  (modulo `resource`). No Windows restam o filtro AST e o timeout, e a resposta
  informa isso em `limites_de_recursos_aplicados`.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, Optional

LOGGER = logging.getLogger("jarvis.security.lightweight_sandbox")

ALLOWED_IMPORTS = frozenset(
    {
        "math", "cmath", "statistics", "decimal", "fractions", "random", "json", "re",
        "string", "itertools", "functools", "collections", "datetime", "heapq", "bisect",
    }
)
FORBIDDEN_NAMES = frozenset(
    {
        "eval", "exec", "compile", "open", "__import__", "globals", "locals", "vars",
        "getattr", "setattr", "delattr", "input", "breakpoint", "exit", "quit", "help",
        "memoryview", "super", "type", "object", "classmethod", "staticmethod", "property",
    }
)
FORBIDDEN_AST_NODES = (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await)
MAX_CODE_CHARS = 20_000
MAX_OUTPUT_CHARS = 16_000

# Executado com `python -I -S`: sem site-packages, sem variaveis PYTHON*, sem cwd no path.
_RUNNER_SOURCE = r'''
import builtins, io, json, sys, contextlib
ALLOWED_IMPORTS = set(json.loads(sys.argv[2]))
_real_import = builtins.__import__

def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level != 0 or name.split(".")[0] not in ALLOWED_IMPORTS:
        raise ImportError(f"import bloqueado no sandbox: {name}")
    return _real_import(name, globals, locals, fromlist, level)

SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in (
        "abs", "all", "any", "bool", "bytes", "chr", "dict", "divmod", "enumerate", "filter",
        "float", "format", "frozenset", "hash", "int", "isinstance", "issubclass", "iter", "len",
        "list", "map", "max", "min", "next", "ord", "pow", "print", "range", "repr", "reversed",
        "round", "set", "slice", "sorted", "str", "sum", "tuple", "zip",
        "Exception", "ValueError", "TypeError", "KeyError", "IndexError", "ZeroDivisionError",
        "ArithmeticError", "RuntimeError", "StopIteration", "AssertionError", "ImportError",
    )
}
SAFE_BUILTINS["__import__"] = _guarded_import

source = open(sys.argv[1], encoding="utf-8").read()
buffer = io.StringIO()
result = {"status": "sucesso"}
try:
    with contextlib.redirect_stdout(buffer):
        exec(compile(source, "<sandbox>", "exec"), {"__builtins__": SAFE_BUILTINS, "__name__": "__sandbox__"})
except BaseException as exc:
    result = {"status": "erro_execucao", "erro": f"{type(exc).__name__}: {exc}"}
result["saida"] = buffer.getvalue()[-%d:]
sys.__stdout__.write("\n" + json.dumps(result, ensure_ascii=False))
''' % MAX_OUTPUT_CHARS


def _sandbox_enabled_from_env() -> bool:
    return str(os.environ.get("JARVIS_ENABLE_CODE_SANDBOX", "")).strip().lower() in {"1", "true", "yes", "sim"}


class UltraLightweightSandboxEngine:
    """Executa codigo curto em subprocesso isolado com filtro AST e limites de recursos."""

    def __init__(
        self,
        max_memory_mb: int = 128,
        max_cpu_time_seconds: int = 5,
        data_dir: Optional[Path] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self.max_memory_mb = max_memory_mb
        self.max_cpu_time_seconds = max_cpu_time_seconds
        self.enabled = _sandbox_enabled_from_env() if enabled is None else bool(enabled)
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data" / "sandbox_runs"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def resource_limits_supported(self) -> bool:
        return os.name == "posix"

    def execute_in_microsandbox(
        self,
        code_str: str,
        tool_name: str = "dynamic_tool",
        input_args: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Valida o codigo e executa em subprocesso separado com limites."""

        now = datetime.now(timezone.utc).isoformat()
        safe_tool_name = re.sub(r"[^A-Za-z0-9_-]", "_", tool_name or "ferramenta")[:64] or "ferramenta"
        base = {"ferramenta": safe_tool_name, "executado_em": now}

        if not self.enabled:
            return {
                **base,
                "status": "desativado",
                "motivo": "Execucao de codigo desligada. Defina JARVIS_ENABLE_CODE_SANDBOX=true para habilitar.",
                "sucesso": False,
            }

        ast_valid, ast_message = self._validate_ast_security(code_str)
        if not ast_valid:
            return {**base, "status": "bloqueado_por_seguranca", "motivo": ast_message, "sucesso": False}

        with tempfile.TemporaryDirectory(prefix="jarvis_sandbox_") as temp_dir:
            code_file = Path(temp_dir) / "codigo.py"
            runner_file = Path(temp_dir) / "runner.py"
            code_file.write_text(code_str, encoding="utf-8")
            runner_file.write_text(_RUNNER_SOURCE, encoding="utf-8")

            popen_kwargs: Dict[str, Any] = {}
            if self.resource_limits_supported:
                popen_kwargs["preexec_fn"] = self._apply_resource_limits
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-S", str(runner_file), str(code_file), json.dumps(sorted(ALLOWED_IMPORTS))],
                    capture_output=True,
                    text=True,
                    timeout=self.max_cpu_time_seconds + 2,
                    cwd=temp_dir,
                    env={"PYTHONIOENCODING": "utf-8"},
                    **popen_kwargs,
                )
            except subprocess.TimeoutExpired:
                run_result = {
                    **base,
                    "status": "timeout_excedido",
                    "erro": f"Processo excedeu o tempo limite de {self.max_cpu_time_seconds}s.",
                    "sucesso": False,
                }
            else:
                run_result = self._interpret_process(base, proc)

        run_result["limites_de_recursos_aplicados"] = self.resource_limits_supported
        self._save_sandbox_run(safe_tool_name, run_result)
        return run_result

    def _interpret_process(self, base: Dict[str, Any], proc: subprocess.CompletedProcess) -> Dict[str, Any]:
        last_line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        try:
            output_data = json.loads(last_line)
        except ValueError:
            output_data = None

        if proc.returncode == 0 and isinstance(output_data, dict):
            succeeded = output_data.get("status") == "sucesso"
            return {
                **base,
                "status": "sucesso" if succeeded else "erro_execucao",
                "sucesso": succeeded,
                "resultado": output_data,
            }
        return {
            **base,
            "status": "erro_subprocesso",
            "codigo_saida": proc.returncode,
            "erro_stderr": proc.stderr.strip()[-MAX_OUTPUT_CHARS:],
            "sucesso": False,
        }

    def _apply_resource_limits(self) -> None:  # pragma: no cover - roda no processo filho
        import resource

        memory_bytes = self.max_memory_mb * 1024 * 1024
        limits = [
            (resource.RLIMIT_CPU, self.max_cpu_time_seconds),
            (resource.RLIMIT_AS, memory_bytes),
            (resource.RLIMIT_FSIZE, 1024 * 1024),
            (resource.RLIMIT_NOFILE, 32),
            (resource.RLIMIT_CORE, 0),
        ]
        if hasattr(resource, "RLIMIT_NPROC"):
            limits.append((resource.RLIMIT_NPROC, 0))
        for limit, value in limits:
            try:
                resource.setrlimit(limit, (value, value))
            except (ValueError, OSError):
                pass
        os.setsid()

    def _validate_ast_security(self, code_str: str) -> tuple[bool, str]:
        """Recusa imports fora da lista, acesso a atributos privados e builtins perigosos."""

        if len(code_str) > MAX_CODE_CHARS:
            return False, f"Codigo excede {MAX_CODE_CHARS} caracteres."
        try:
            tree = ast.parse(code_str)
        except SyntaxError as exc:
            return False, f"Erro de sintaxe no codigo: {exc}"

        for node in ast.walk(tree):
            if isinstance(node, FORBIDDEN_AST_NODES):
                return False, f"No AST proibido detectado: {type(node).__name__}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                        return False, f"Import nao permitido: {alias.name}"
            if isinstance(node, ast.ImportFrom):
                if node.level or (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                    return False, f"Import nao permitido: {node.module}"
            if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                return False, f"Acesso a atributo privado nao permitido: {node.attr}"
            if isinstance(node, ast.Name) and (node.id in FORBIDDEN_NAMES or node.id.startswith("__")):
                return False, f"Nome nao permitido: {node.id}"
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value:
                return False, "Strings com '__' nao sao permitidas."
        return True, "AST de seguranca validado."

    def _save_sandbox_run(self, tool_name: str, record: Dict[str, Any]) -> None:
        """Salva a telemetria da execucao em arquivo JSON."""

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        file_path = self.data_dir / f"sandbox_{tool_name}_{timestamp}.json"
        file_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
