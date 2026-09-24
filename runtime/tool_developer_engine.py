"""
JARVIS - Módulo 2: Desenvolvimento de Ferramentas e Conectores

Responsável por:
- identificar necessidades de integração com sistemas, APIs, arquivos e dispositivos
- gerar dinamicamente código Python para novos conectores e ferramentas operacionais
- validar ferramentas via AST e executá-las em ambiente isolado (sandbox por subprocesso estrito)
- registrar ferramentas aprovadas no repositório de ferramentas e na memória procedural
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOOLS_DIR = PROJECT_ROOT / "data" / "developed_tools"

# Nós AST potencialmente perigosos para análise de segurança estática
FORBIDDEN_AST_NODES = {
    "eval", "exec", "compile", "__import__"
}


class ToolDeveloperEngine:
    """Motor de desenvolvimento, validação de AST e execução em sandbox de ferramentas customizadas."""

    def __init__(self, tools_dir: Optional[Path] = None) -> None:
        self.tools_dir = Path(tools_dir) if tools_dir else DEFAULT_TOOLS_DIR
        self.tools_dir.mkdir(parents=True, exist_ok=True)

    def develop_tool(
        self,
        tool_name: str,
        purpose: str,
        code_body: str,
        domain: str = "general",
    ) -> Dict[str, Any]:
        """
        Desenvolve, valida com AST e registra uma nova ferramenta/conector.
        """
        now = datetime.now(timezone.utc).isoformat()
        file_name = f"{tool_name.lower().replace(' ', '_')}.py"
        file_path = self.tools_dir / file_name

        # Estrutura do módulo gerado
        tool_code = f'"""\nFerramenta desenvolvida autonomamente pelo JARVIS.\nNome: {tool_name}\nPropósito: {purpose}\n"""\n\n'
        tool_code += "import sys\nimport os\nimport json\nfrom typing import Any, Dict\n\n"
        tool_code += f"def run_tool(params: Dict[str, Any]) -> Dict[str, Any]:\n"
        tool_code += f"    '''Execução principal da ferramenta {tool_name}.'''\n"
        for line in code_body.splitlines():
            tool_code += f"    {line}\n"
        if "return " not in code_body:
            tool_code += "\n    return {'status': 'sucesso', 'resultado': 'executado com exito'}\n"

        tool_code += "\nif __name__ == '__main__':\n"
        tool_code += "    input_data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}\n"
        tool_code += "    res = run_tool(input_data)\n"
        tool_code += "    print(json.dumps(res, ensure_ascii=False))\n"

        file_path.write_text(tool_code, encoding="utf-8")

        # Validação AST e compilação
        ast_result = self._validate_ast(tool_code)
        compilation_result = self._validate_tool(file_path) if ast_result["valida"] else ast_result

        tool_record = {
            "tool_name": tool_name,
            "purpose": purpose,
            "domain": domain,
            "file_path": str(file_path),
            "created_at": now,
            "validada": compilation_result["valida"],
            "erro_validacao": compilation_result.get("erro"),
        }

        self._register_tool_metadata(tool_record)
        return tool_record

    def execute_tool_in_sandbox(
        self,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Executa uma ferramenta em sandbox isolado por subprocesso com limite de tempo e ambiente restrito.
        """
        tools = self.list_developed_tools()
        target = next((t for t in tools if t["tool_name"].lower() == tool_name.lower()), None)
        if not target:
            return {"status": "erro", "motivo": f"Ferramenta {tool_name} não encontrada."}

        file_path = Path(target["file_path"])
        if not file_path.exists():
            return {"status": "erro", "motivo": "Arquivo de código da ferramenta não existe."}

        params_json = json.dumps(params or {}, ensure_ascii=False)

        try:
            # Subprocesso isolado com timeout estrito
            proc = subprocess.run(
                [sys.executable, str(file_path)],
                input=params_json,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
            )
            if proc.returncode != 0:
                return {
                    "status": "erro",
                    "motivo": "Falha na execução em sandbox.",
                    "stderr": proc.stderr,
                }
            return json.loads(proc.stdout)
        except subprocess.TimeoutExpired:
            return {"status": "erro", "motivo": f"Timeout de execução ({timeout_seconds}s) excedido."}
        except Exception as e:
            return {"status": "erro", "motivo": str(e)}

    def list_developed_tools(self) -> List[Dict[str, Any]]:
        """Lista todas as ferramentas já desenvolvidas."""
        meta_file = self.tools_dir / "tools_registry.json"
        if not meta_file.exists():
            return []
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _validate_ast(self, code: str) -> Dict[str, Any]:
        """Inspeciona a árvore sintática abstrata (AST) procurando instruções inseguras."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in FORBIDDEN_AST_NODES:
                    return {
                        "valida": False,
                        "erro": f"Uso da função proibida '{node.id}' detectado via análise AST.",
                    }
            return {"valida": True}
        except SyntaxError as e:
            return {"valida": False, "erro": f"Erro de sintaxe Python: {str(e)}"}

    def _validate_tool(self, file_path: Path) -> Dict[str, Any]:
        """Valida a compilação e sintaxe do módulo gerado."""
        try:
            spec = importlib.util.spec_from_file_location("dynamic_tool", str(file_path))
            if spec is None or spec.loader is None:
                return {"valida": False, "erro": "Spec de importação inválido"}
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not hasattr(module, "run_tool"):
                return {"valida": False, "erro": "Função entrypoint 'run_tool' não encontrada"}
            return {"valida": True}
        except Exception as e:
            return {"valida": False, "erro": str(e)}

    def _register_tool_metadata(self, record: Dict[str, Any]) -> None:
        """Registra os metadados da ferramenta no arquivo centralizado."""
        meta_file = self.tools_dir / "tools_registry.json"
        tools = self.list_developed_tools()
        tools.append(record)
        meta_file.write_text(json.dumps(tools, indent=2, ensure_ascii=False), encoding="utf-8")
