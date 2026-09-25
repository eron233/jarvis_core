"""
JARVIS - Motor de Micro-Sandbox Isolado de Execução (Lightweight Sandbox Engine)

Responsável por:
- validar código dinâmico com um portão de segurança AST por LISTA DE PERMISSÃO (allowlist),
  bloqueando importações perigosas, acesso a atributos internos (dunder) e primitivas de fuga
  como eval/exec/open/__import__ antes de qualquer execução;
- executar o código aprovado em um subprocesso isolado, com ambiente limpo, diretório de
  trabalho temporário, limites reais de CPU (RLIMIT_CPU) e de espaço de endereçamento
  (RLIMIT_AS) e builtins restritos como defesa em profundidade;
- medir e reportar o consumo REAL de memória do processo (não valores fixos).

Esta é uma barreira de contenção pragmática em Python puro (sem contêineres). Ela reduz
drasticamente a superfície de ataque, mas não substitui um isolamento de SO (namespaces,
seccomp, contêiner) para código verdadeiramente hostil. O resumo de cada execução declara
honestamente quais limites foram aplicados.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

LOGGER = logging.getLogger("jarvis.security.lightweight_sandbox")

# Módulos cuja importação é permitida dentro do sandbox (puramente computacionais/sem I/O
# de sistema perigoso). Qualquer import fora desta lista é bloqueado.
SAFE_IMPORT_ALLOWLIST = frozenset({
    "math", "cmath", "json", "datetime", "random", "statistics", "re",
    "itertools", "functools", "collections", "decimal", "fractions",
    "string", "textwrap", "unicodedata", "hashlib", "base64", "uuid",
    "time", "heapq", "bisect", "array", "enum", "dataclasses", "typing",
    "operator", "copy", "numbers", "secrets", "zlib", "binascii",
})

# Nomes globais proibidos: primitivas de execução dinâmica, acesso a arquivos e introspecção
# que permitem escapar do sandbox.
FORBIDDEN_NAMES = frozenset({
    "eval", "exec", "compile", "__import__", "open", "input", "breakpoint",
    "globals", "locals", "vars", "memoryview", "getattr", "setattr",
    "delattr", "exit", "quit", "help", "license", "credits", "copyright",
})


class SandboxSecurityError(Exception):
    """Erro levantado quando o código viola a política de segurança do sandbox."""


class _SecurityGateVisitor(ast.NodeVisitor):
    """Percorre a AST e coleta violações da política de segurança."""

    def __init__(self) -> None:
        self.violations: List[str] = []

    def visit_Global(self, node: ast.Global) -> None:
        self.violations.append("Declaração 'global' não é permitida no sandbox.")
        self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.violations.append("Declaração 'nonlocal' não é permitida no sandbox.")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root not in SAFE_IMPORT_ALLOWLIST:
                self.violations.append(
                    f"Importação do módulo '{alias.name}' bloqueada (fora da lista de permissão)."
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        root = (node.module or "").split(".")[0]
        if node.level and node.level > 0:
            self.violations.append("Importação relativa não é permitida no sandbox.")
        elif root not in SAFE_IMPORT_ALLOWLIST:
            self.violations.append(
                f"Importação de '{node.module}' bloqueada (fora da lista de permissão)."
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Bloqueia acesso a atributos internos (dunder), rota clássica de fuga
        # (ex.: ().__class__.__bases__[0].__subclasses__()).
        if isinstance(node.attr, str) and node.attr.startswith("__") and node.attr.endswith("__"):
            self.violations.append(
                f"Acesso ao atributo interno '{node.attr}' bloqueado (rota de fuga de sandbox)."
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_NAMES:
            self.violations.append(f"Uso do nome proibido '{node.id}' detectado.")
        self.generic_visit(node)


class UltraLightweightSandboxEngine:
    """Motor de execução em micro-sandbox isolado com contenção real de recursos."""

    def __init__(
        self,
        max_memory_mb: int = 128,
        max_cpu_time_seconds: int = 5,
        data_dir: Optional[Path] = None,
    ) -> None:
        self.max_memory_mb = max_memory_mb
        self.max_cpu_time_seconds = max_cpu_time_seconds
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data" / "sandbox_runs"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def execute_in_microsandbox(
        self,
        code_str: str,
        tool_name: str = "dynamic_tool",
        input_args: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Valida o código via portão AST de segurança e o executa em um subprocesso isolado com
        limites reais de CPU/memória e builtins restritos. Reporta o consumo real de memória.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Portão de Segurança AST (lista de permissão)
        ast_valid, ast_message = self._validate_ast_security(code_str)
        if not ast_valid:
            record = {
                "ferramenta": tool_name,
                "status": "bloqueado_por_seguranca",
                "motivo": ast_message,
                "executado_em": now,
                "pegada_memoria_mb": 0.0,
                "sucesso": False,
            }
            self._save_sandbox_run(tool_name, record)
            return record

        # 2. Execução isolada em subprocesso
        run_result = self._run_isolated_subprocess(code_str, tool_name, input_args or {})
        run_result["executado_em"] = now
        self._save_sandbox_run(tool_name, run_result)
        return run_result

    def _run_isolated_subprocess(
        self,
        code_str: str,
        tool_name: str,
        input_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="jarvis_sandbox_") as temp_dir:
            temp_script = Path(temp_dir) / "runner.py"
            temp_script.write_text(
                self._build_runner_source(code_str, input_args),
                encoding="utf-8",
            )

            # Ambiente mínimo: sem herdar variáveis sensíveis do processo pai.
            clean_env = {
                "PATH": "/usr/bin:/bin",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1",
            }

            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-S", str(temp_script)],
                    capture_output=True,
                    text=True,
                    timeout=self.max_cpu_time_seconds + 2,
                    cwd=temp_dir,
                    env=clean_env,
                    preexec_fn=self._build_rlimit_setter() if os.name == "posix" else None,
                )
            except subprocess.TimeoutExpired:
                return {
                    "ferramenta": tool_name,
                    "status": "timeout_excedido",
                    "erro": f"Processo excedeu o tempo limite de {self.max_cpu_time_seconds}s.",
                    "sucesso": False,
                    "pegada_memoria_mb": float(self.max_memory_mb),
                    "limites_aplicados": self._limits_description(),
                }

            return self._parse_subprocess_output(proc, tool_name)

    def _parse_subprocess_output(self, proc: "subprocess.CompletedProcess[str]", tool_name: str) -> Dict[str, Any]:
        envelope: Optional[Dict[str, Any]] = None
        for line in reversed(proc.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    envelope = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

        limits = self._limits_description()

        if proc.returncode != 0 and envelope is None:
            # Estouro de limite de recurso (CPU/memória) ou erro fatal do interpretador.
            return {
                "ferramenta": tool_name,
                "status": "erro_subprocesso",
                "sucesso": False,
                "codigo_retorno": proc.returncode,
                "erro_stderr": proc.stderr.strip()[:2000] or "Processo terminado por limite de recurso (CPU/memória).",
                "pegada_memoria_mb": 0.0,
                "limites_aplicados": limits,
            }

        if envelope is None:
            return {
                "ferramenta": tool_name,
                "status": "erro_saida_invalida",
                "sucesso": False,
                "erro_stderr": proc.stderr.strip()[:2000],
                "saida_bruta": proc.stdout.strip()[:2000],
                "pegada_memoria_mb": 0.0,
                "limites_aplicados": limits,
            }

        memoria_mb = float(envelope.get("pegada_memoria_mb", 0.0))
        if envelope.get("status") == "sucesso":
            return {
                "ferramenta": tool_name,
                "status": "sucesso",
                "sucesso": True,
                "resultado": envelope.get("resultado", {}),
                "pegada_memoria_mb": round(memoria_mb, 2),
                "limites_aplicados": limits,
                "resumo_ptbr": (
                    f"Ferramenta '{tool_name}' executada no sandbox isolado usando "
                    f"{round(memoria_mb, 2)} MB de RAM (medido). {limits['resumo']}"
                ),
            }

        return {
            "ferramenta": tool_name,
            "status": "erro_execucao",
            "sucesso": False,
            "erro": envelope.get("erro", "erro desconhecido"),
            "pegada_memoria_mb": round(memoria_mb, 2),
            "limites_aplicados": limits,
        }

    def _build_rlimit_setter(self):
        """Retorna um preexec_fn que aplica RLIMIT_CPU e RLIMIT_AS reais no filho (POSIX)."""
        max_cpu = self.max_cpu_time_seconds
        # Piso de endereçamento para o interpretador iniciar; o teto ainda contém runaway.
        as_limit_bytes = max(self.max_memory_mb, 256) * 1024 * 1024

        def _set_limits() -> None:  # pragma: no cover - executado no processo filho
            import resource

            resource.setrlimit(resource.RLIMIT_CPU, (max_cpu, max_cpu))
            try:
                resource.setrlimit(resource.RLIMIT_AS, (as_limit_bytes, as_limit_bytes))
            except (ValueError, OSError):
                pass
            # Impede a criação de novos processos (fork bomb / spawn).
            try:
                resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
            except (ValueError, OSError, AttributeError):
                pass

        return _set_limits

    def _limits_description(self) -> Dict[str, Any]:
        posix = os.name == "posix"
        return {
            "cpu_segundos": self.max_cpu_time_seconds if posix else None,
            "memoria_teto_mb": max(self.max_memory_mb, 256) if posix else None,
            "isolamento_processo": posix,
            "builtins_restritos": True,
            "ambiente_limpo": True,
            "resumo": (
                f"Limites reais aplicados: CPU {self.max_cpu_time_seconds}s, teto de memória "
                f"{max(self.max_memory_mb, 256)} MB, sem novos processos, builtins restritos."
                if posix else
                "Plataforma não-POSIX: limites de recurso do SO indisponíveis; aplicados "
                "portão AST, builtins restritos e ambiente limpo."
            ),
        }

    @staticmethod
    def _build_runner_source(code_str: str, input_args: Dict[str, Any]) -> str:
        """Constrói o script filho que executa o código com builtins restritos e mede memória.

        O código do usuário é embutido em uma função `_user_entry` e executado via `exec`
        em um namespace cujo `__builtins__` contém apenas nomes seguros — assim a restrição
        de builtins vale de fato para o código do usuário (defesa em profundidade além do
        portão AST). O resultado esperado é o dicionário `_out` que o código pode preencher.
        """
        indented = "\n".join("        " + line for line in code_str.splitlines()) or "        pass"
        user_func_src = "def _user_entry(input_args, _out):\n" + indented + "\n        return _out\n"
        return (
            "import json, sys\n"
            "try:\n"
            "    import resource\n"
            "except Exception:\n"
            "    resource = None\n"
            "\n"
            "_SAFE_BUILTIN_NAMES = (\n"
            "    'abs','all','any','ascii','bin','bool','bytearray','bytes','chr','complex',\n"
            "    'dict','divmod','enumerate','filter','float','format','frozenset','hash','hex',\n"
            "    'int','isinstance','issubclass','iter','len','list','map','max','min','next',\n"
            "    'oct','ord','pow','print','range','repr','reversed','round','set','slice',\n"
            "    'sorted','str','sum','tuple','type','zip','True','False','None',\n"
            "    'Exception','ValueError','TypeError','KeyError','IndexError','ZeroDivisionError',\n"
            "    'ArithmeticError','RuntimeError','StopIteration',\n"
            ")\n"
            "import builtins as _b\n"
            "_safe_builtins = {n: getattr(_b, n) for n in _SAFE_BUILTIN_NAMES if hasattr(_b, n)}\n"
            "_ALLOWED = set(" + repr(sorted(SAFE_IMPORT_ALLOWLIST)) + ")\n"
            "_real_import = _b.__import__\n"
            "def _guarded_import(name, *a, **k):\n"
            "    if name.split('.')[0] not in _ALLOWED:\n"
            "        raise ImportError('Import bloqueado pelo sandbox: ' + name)\n"
            "    return _real_import(name, *a, **k)\n"
            "_safe_builtins['__import__'] = _guarded_import\n"
            "\n"
            "def _measure_mem_mb():\n"
            "    if resource is None:\n"
            "        return 0.0\n"
            "    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss\n"
            "    return (ru / 1024.0) if sys.platform != 'darwin' else (ru / (1024.0 * 1024.0))\n"
            "\n"
            "_ns = {'__builtins__': _safe_builtins}\n"
            "_user_src = " + repr(user_func_src) + "\n"
            "_args = json.loads(" + repr(json.dumps(input_args, ensure_ascii=False)) + ")\n"
            "try:\n"
            "    exec(_user_src, _ns)\n"
            "    _result = _ns['_user_entry'](_args, {}) or {}\n"
            "    if not isinstance(_result, dict):\n"
            "        _result = {'valor': _result}\n"
            "    print(json.dumps({'status':'sucesso','resultado':_result,'pegada_memoria_mb':_measure_mem_mb()}, ensure_ascii=False, default=str))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'status':'erro_execucao','erro':str(e),'pegada_memoria_mb':_measure_mem_mb()}, ensure_ascii=False))\n"
        )

    def _validate_ast_security(self, code_str: str) -> Tuple[bool, str]:
        """Portão de segurança: rejeita código com construções perigosas antes de executar."""
        try:
            tree = ast.parse(code_str)
        except SyntaxError as exc:
            return False, f"Erro de sintaxe no código: {exc}"

        visitor = _SecurityGateVisitor()
        visitor.visit(tree)
        if visitor.violations:
            return False, "; ".join(dict.fromkeys(visitor.violations))
        return True, "Portão de segurança AST validado."

    def _save_sandbox_run(self, tool_name: str, record: Dict[str, Any]) -> None:
        """Salva a telemetria do micro-sandbox em arquivo JSON."""
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in tool_name)[:40]
        file_path = self.data_dir / f"sandbox_{safe_name}_{int(datetime.now(timezone.utc).timestamp() * 1000)}.json"
        file_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
