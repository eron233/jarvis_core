"""
JARVIS - Módulo 2: Desenvolvimento de Ferramentas e Conectores

Responsável por:
- identificar necessidades de integração com sistemas, APIs, arquivos e dispositivos
- gerar dinamicamente código Python para novos conectores e ferramentas operacionais
- validar ferramentas via AST e executar somente em container Docker explicitamente habilitado
- registrar ferramentas aprovadas no repositório de ferramentas e na memória procedural
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from security.container_executor import ContainerExecutor

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
        """Prepara ferramenta e verifica somente sintaxe, sem importar codigo gerado."""
        now = datetime.now(timezone.utc).isoformat()
        if not isinstance(tool_name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,79}", tool_name):
            return {
                "tool_name": tool_name,
                "status": "nome_invalido",
                "validada": False,
                "codigo_executado": False,
                "erro_validacao": "Nome deve ter 1 a 80 caracteres ASCII: letras, numeros, espacos, _ ou -.",
            }
        file_path = self.tools_dir / f"{tool_name.lower().replace(' ', '_')}.py"
        # repr protege contra quebra de docstring e injecao de codigo pelos metadados.
        tool_code = f"TOOL_METADATA = {{'name': {tool_name!r}, 'purpose': {purpose!r}}}\n"
        tool_code += "import sys\nimport json\nfrom typing import Any, Dict\n\n"
        tool_code += "def run_tool(params: Dict[str, Any]) -> Dict[str, Any]:\n"
        for line in code_body.splitlines():
            tool_code += f"    {line}\n"
        # Nunca inventar sucesso quando o codigo da ferramenta nao retorna nada.
        tool_code += (
            "    return {'status': 'sem_resultado', "
            "'motivo': 'A ferramenta terminou sem retorno explicito.'}\n"
        )
        tool_code += "\nif __name__ == '__main__':\n"
        tool_code += "    input_data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}\n"
        tool_code += "    res = run_tool(input_data)\n"
        tool_code += "    print(json.dumps(res, ensure_ascii=False))\n"

        ast_result = self._validate_ast(tool_code)
        validation = self._validate_tool(tool_code, file_path) if ast_result["valida"] else ast_result
        if validation["valida"]:
            file_path.write_text(tool_code, encoding="utf-8")
        record = {
            "tool_name": tool_name,
            "purpose": purpose,
            "domain": domain,
            "file_path": str(file_path) if validation["valida"] else None,
            "created_at": now,
            "validada": validation["valida"],  # compatibilidade: somente sintaxe
            "sintaxe_valida": validation["valida"],
            "codigo_executado": False,
            "isolamento_validado": False,
            "erro_validacao": validation.get("erro"),
        }
        self._register_tool_metadata(record)
        return record

    def execute_tool_in_sandbox(
        self,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 5.0,
    ) -> Dict[str, Any]:
        """Executa somente com consentimento explicito e container confinado.

        O nome legado permanece para compatibilidade, mas jamais usa subprocesso
        direto como fallback. Sem Docker local, imagem pinada e opt-in: bloqueia.
        """
        if not isinstance(tool_name, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9 _-]{0,79}", tool_name
        ):
            return {"status": "nome_invalido", "executado": False}
        tools = self.list_developed_tools()
        target = next(
            (t for t in tools if t.get("tool_name", "").lower() == tool_name.lower()),
            None,
        )
        if target is None:
            return {"status": "erro", "motivo": f"Ferramenta {tool_name} nao encontrada.", "executado": False}
        if not target.get("sintaxe_valida", target.get("validada", False)):
            return {"status": "bloqueado_por_seguranca", "executado": False,
                    "motivo": "Ferramenta sem validacao sintatica."}

        filename = f"{tool_name.lower().replace(' ', '_')}.py"
        try:
            root = self.tools_dir.resolve(strict=True)
            script = (root / filename).resolve(strict=True)
            if script.parent != root or not script.is_file():
                raise ValueError("Arquivo nao confiavel")
            source = script.read_text(encoding="utf-8")
        except (OSError, ValueError, UnicodeError):
            return {"status": "bloqueado_por_seguranca", "executado": False,
                    "motivo": "Codigo de ferramenta ausente ou fora do diretorio permitido."}

        executor = ContainerExecutor(
            enabled=os.environ.get("JARVIS_TWIN_DOCKER_ENABLED", "").lower() == "true",
            image=os.environ.get("JARVIS_TWIN_DOCKER_IMAGE", ""),
        )
        report = executor.execute(source, params=params, timeout_seconds=timeout_seconds)
        return {"tool_name": tool_name, **report}

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

    def _validate_tool(self, code: str, file_path: Path) -> Dict[str, Any]:
        """Compila o AST sem importar o modulo ou executar seus efeitos colaterais."""
        try:
            tree = ast.parse(code, filename=str(file_path))
            if not any(
                isinstance(node, ast.FunctionDef) and node.name == "run_tool"
                for node in tree.body
            ):
                return {"valida": False, "erro": "Funcao run_tool nao encontrada."}
            compile(tree, str(file_path), "exec")
            return {"valida": True}
        except (SyntaxError, ValueError, TypeError) as erro:
            return {"valida": False, "erro": str(erro)}

    def _register_tool_metadata(self, record: Dict[str, Any]) -> None:
        """Registra os metadados da ferramenta no arquivo centralizado."""
        meta_file = self.tools_dir / "tools_registry.json"
        tools = self.list_developed_tools()
        tools.append(record)
        meta_file.write_text(json.dumps(tools, indent=2, ensure_ascii=False), encoding="utf-8")
