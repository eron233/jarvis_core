"""
JARVIS - Motor de Micro-Sandbox Ultraleve de Execução Isolada (Ultra-Lightweight Sandbox Engine)

Responsável por:
- executar ferramentas e códigos dinâmicos em um processo separado com limites de CPU e memória
- ser mais leve que um daemon de contêiner, preservando a diretriz de zero-bloat
- aplicar RLIMIT_CPU e RLIMIT_AS, diretório temporário isolado e um portão AST

Limites conhecidos: o isolamento é um processo com limites de recurso, não uma
máquina virtual nem um contêiner. O portão AST recusa importações de sistema,
execução dinâmica e acesso a atributos internos, mas análise estática não é
prova de segurança. O consumo medido de um processo Python fica na casa das
dezenas de MB; o número relatado é o pico real, não uma estimativa.
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
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("jarvis.security.lightweight_sandbox")

# Primitivas AST proibidas para segurança estrita do sandbox
FORBIDDEN_AST_NODES = (
    ast.Global,
    ast.Nonlocal,
)

# Modulos que dao acesso ao sistema, a rede ou ao proprio interpretador. Sem
# esta lista o portao AST recusava apenas `global` e `nonlocal`, que nao tem
# relacao com seguranca, enquanto `import os` e `import subprocess` entravam.
FORBIDDEN_IMPORTS = frozenset({
    "os", "sys", "subprocess", "shutil", "socket", "signal", "ctypes", "mmap",
    "importlib", "builtins", "resource", "multiprocessing", "threading",
    "pty", "fcntl", "pickle", "marshal", "shelve", "http", "urllib", "ftplib",
    "telnetlib", "smtplib", "webbrowser", "pathlib", "glob", "tempfile",
})

# Builtins que carregam ou executam codigo novo, contornando a analise estatica.
FORBIDDEN_CALLS = frozenset({
    "eval", "exec", "compile", "__import__", "open", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr", "memoryview",
})


class UltraLightweightSandboxEngine:
    """Motor de execução em micro-sandbox isolado de baixíssimo consumo de memória e CPU."""

    def __init__(
        self,
        max_memory_mb: int = 64,
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
        Valida o código via AST estático e executa em um micro-processo isolado com limites estritos de memória e CPU.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Análise Estática AST de Segurança
        ast_valid, ast_message = self._validate_ast_security(code_str)
        if not ast_valid:
            return {
                "ferramenta": tool_name,
                "status": "bloqueado_por_seguranca",
                "motivo": ast_message,
                "executado_em": now,
                "pegada_memoria_mb": 0.0,
                "sucesso": False,
            }

        # 2. Criação do Script Temp Isolado
        with tempfile.TemporaryDirectory(prefix="jarvis_sandbox_") as temp_dir:
            temp_script = Path(temp_dir) / f"{tool_name}.py"

            # Identação de todas as linhas de code_str para encaixar no bloco try
            indented_code = "\n".join("    " + line for line in code_str.splitlines())

            # `input_args` era aceito e descartado em silencio: a ferramenta rodava
            # sem as entradas que o chamador enviou. Os argumentos vao num arquivo
            # JSON ao lado do script, e nao interpolados no codigo gerado, para que
            # o conteudo do chamador nunca vire codigo.
            args_file = Path(temp_dir) / "entrada.json"
            try:
                args_file.write_text(json.dumps(input_args or {}, ensure_ascii=False), encoding="utf-8")
                args_error = None
            except (TypeError, ValueError) as erro:
                return {
                    "ferramenta": tool_name,
                    "status": "entrada_invalida",
                    "motivo": f"Os argumentos de entrada nao sao serializaveis em JSON: {erro}",
                    "executado_em": now,
                    "pegada_memoria_mb": None,
                    "memoria_medida": False,
                    "sucesso": False,
                }

            # Invólucro com limites de recursos do SO e medição real de memória.
            # `max_memory_mb` era guardado e nunca aplicado, e o limite de CPU
            # sozinho nao impede uma ferramenta de alocar toda a RAM disponivel.
            runner_wrapper = (
                "import sys, json\n"
                # A ferramenta recebe os argumentos do chamador em `entrada`.
                f"entrada = json.load(open({str(args_file)!r}, encoding='utf-8'))\n"
                "_limites = []\n"
                "try:\n"
                "    import resource\n"
                f"    resource.setrlimit(resource.RLIMIT_CPU, ({self.max_cpu_time_seconds}, {self.max_cpu_time_seconds}))\n"
                "    _limites.append('RLIMIT_CPU')\n"
                f"    _bytes = {self.max_memory_mb} * 1024 * 1024\n"
                "    resource.setrlimit(resource.RLIMIT_AS, (_bytes, _bytes))\n"
                "    _limites.append('RLIMIT_AS')\n"
                "except (ImportError, ValueError, OSError):\n"
                "    pass\n"
                "def _pico_memoria_mb():\n"
                "    try:\n"
                "        import resource as _r\n"
                "        _bruto = _r.getrusage(_r.RUSAGE_SELF).ru_maxrss\n"
                "        # Linux informa em KB; macOS em bytes.\n"
                "        return round(_bruto / (1024 * 1024), 2) if sys.platform == 'darwin' else round(_bruto / 1024, 2)\n"
                "    except Exception:\n"
                "        return None\n"
                "try:\n"
                f"{indented_code}\n"
                "    print(json.dumps({'status': 'sucesso', 'saida': 'Execução no micro-sandbox concluída sem violações.', 'pico_memoria_mb': _pico_memoria_mb(), 'limites_aplicados': _limites}))\n"
                "except MemoryError:\n"
                "    print(json.dumps({'status': 'limite_memoria_excedido', 'erro': 'A ferramenta excedeu o limite de memoria do sandbox.', 'pico_memoria_mb': _pico_memoria_mb(), 'limites_aplicados': _limites}))\n"
                "except Exception as e:\n"
                "    print(json.dumps({'status': 'erro_execucao', 'erro': str(e), 'pico_memoria_mb': _pico_memoria_mb(), 'limites_aplicados': _limites}))\n"
            )

            temp_script.write_text(runner_wrapper, encoding="utf-8")

            # 3. Execução em Subprocesso Isolado
            try:
                proc = subprocess.run(
                    [sys.executable, str(temp_script)],
                    capture_output=True,
                    text=True,
                    timeout=self.max_cpu_time_seconds + 2,
                    cwd=temp_dir,
                )

                if proc.returncode == 0:
                    try:
                        output_data = json.loads(proc.stdout.strip().splitlines()[-1])
                    except Exception:
                        output_data = {"status": "sucesso", "saida_bruta": proc.stdout.strip()}

                    # O valor relatado passa a ser o pico medido pelo proprio
                    # processo filho. Antes era uma constante apresentada como
                    # medicao, junto de um resumo que afirmava um consumo que
                    # nunca foi observado.
                    pico_medido = output_data.get("pico_memoria_mb") if isinstance(output_data, dict) else None
                    limites = output_data.get("limites_aplicados", []) if isinstance(output_data, dict) else []
                    # O status interno precisa chegar ao status externo: uma
                    # ferramenta que levantou excecao dentro do sandbox era
                    # reportada como "sucesso" na resposta ao chamador.
                    status_interno = output_data.get("status", "sucesso") if isinstance(output_data, dict) else "sucesso"
                    executou_dentro_do_limite = status_interno == "sucesso"
                    run_result = {
                        "ferramenta": tool_name,
                        "status": status_interno,
                        "executado_em": now,
                        "pegada_memoria_mb": pico_medido,
                        "memoria_medida": pico_medido is not None,
                        "memoria_observacao": (
                            "Pico residente do processo inteiro, incluindo a inicializacao do "
                            "interpretador, que ocorre antes de o limite ser imposto."
                        ),
                        "limite_memoria_mb": self.max_memory_mb,
                        "limites_aplicados": limites,
                        "sucesso": executou_dentro_do_limite,
                        "resultado": output_data,
                        "resumo_ptbr": (
                            f"Ferramenta '{tool_name}' executada no micro-sandbox com pico medido de {pico_medido} MB."
                            if pico_medido is not None
                            else f"Ferramenta '{tool_name}' executada no micro-sandbox; esta plataforma nao expoe medicao de memoria."
                        ),
                    }
                else:
                    run_result = {
                        "ferramenta": tool_name,
                        "status": "erro_subprocesso",
                        "executado_em": now,
                        "erro_stderr": proc.stderr.strip(),
                        "sucesso": False,
                        "pegada_memoria_mb": None,
                        "memoria_medida": False,
                    }

            except subprocess.TimeoutExpired:
                run_result = {
                    "ferramenta": tool_name,
                    "status": "timeout_excedido",
                    "executado_em": now,
                    "erro": f"Processo excedeu o tempo limite de {self.max_cpu_time_seconds}s.",
                    "sucesso": False,
                    "pegada_memoria_mb": None,
                    "memoria_medida": False,
                }

        self._save_sandbox_run(tool_name, run_result)
        return run_result

    def _validate_ast_security(self, code_str: str) -> tuple[bool, str]:
        """
        Garante que o codigo nao possui construcoes perigosas.

        Parametros:
        - code_str: codigo da ferramenta dinamica a ser executada.

        Retorno:
        - par (aprovado, mensagem) descrevendo a decisao.

        Efeitos no sistema:
        - nenhum; apenas inspeciona a arvore sintatica antes da execucao.
        """

        try:
            tree = ast.parse(code_str)
        except SyntaxError as erro:
            return False, f"Erro de sintaxe no código: {erro}"

        for node in ast.walk(tree):
            if isinstance(node, FORBIDDEN_AST_NODES):
                return False, f"Nó AST proibido detectado: {type(node).__name__}"

            if isinstance(node, ast.Import):
                for alias in node.names:
                    raiz = alias.name.split(".")[0]
                    if raiz in FORBIDDEN_IMPORTS:
                        return False, f"Importação proibida no sandbox: '{alias.name}'."

            if isinstance(node, ast.ImportFrom):
                raiz = (node.module or "").split(".")[0]
                if raiz in FORBIDDEN_IMPORTS:
                    return False, f"Importação proibida no sandbox: '{node.module}'."

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALLS:
                    return False, f"Chamada proibida no sandbox: '{node.func.id}'."

            # Atributos com duplo sublinhado abrem caminho de volta aos builtins
            # a partir de qualquer objeto, por exemplo `().__class__.__bases__`.
            if isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr.endswith("__"):
                return False, f"Acesso a atributo interno proibido no sandbox: '{node.attr}'."

        return True, "AST de segurança validado."

    def _save_sandbox_run(self, tool_name: str, record: Dict[str, Any]) -> None:
        """Salva a telemetria do micro-sandbox em arquivo JSON."""
        file_path = self.data_dir / f"sandbox_{tool_name}_{int(datetime.now(timezone.utc).timestamp())}.json"
        file_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
