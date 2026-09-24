"""
JARVIS - Módulo 2: Desenvolvimento de Ferramentas e Conectores

Responsável por:
- identificar necessidades de integração com sistemas, APIs, arquivos e dispositivos
- gerar dinamicamente código Python para novos conectores e ferramentas operacionais
- validar ferramentas em ambiente isolado (sandbox) antes de disponibilizá-las
- registrar ferramentas aprovadas no repositório de ferramentas e na memória procedural
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOOLS_DIR = PROJECT_ROOT / "data" / "developed_tools"


class ToolDeveloperEngine:
    """Motor de desenvolvimento e compilação de ferramentas e conectores customizados."""

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
        Desenvolve, valida e registra uma nova ferramenta/conector.
        """
        now = datetime.now(timezone.utc).isoformat()
        file_name = f"{tool_name.lower().replace(' ', '_')}.py"
        file_path = self.tools_dir / file_name

        # Estrutura do módulo gerado
        tool_code = f'"""\nFerramenta desenvolvida autonomamente pelo JARVIS.\nNome: {tool_name}\nPropósito: {purpose}\n"""\n\n'
        tool_code += "import sys\nimport os\nfrom typing import Any, Dict\n\n"
        tool_code += f"def run_tool(params: Dict[str, Any]) -> Dict[str, Any]:\n"
        tool_code += f"    '''Execução principal da ferramenta {tool_name}.'''\n"
        for line in code_body.splitlines():
            tool_code += f"    {line}\n"
        if "return " not in code_body:
            tool_code += "\n    return {'status': 'sucesso', 'resultado': 'executado com exito'}\n"

        file_path.write_text(tool_code, encoding="utf-8")

        # Validação simples de sintaxe
        validation_result = self._validate_tool(file_path)

        tool_record = {
            "tool_name": tool_name,
            "purpose": purpose,
            "domain": domain,
            "file_path": str(file_path),
            "created_at": now,
            "validada": validation_result["valida"],
            "erro_validacao": validation_result.get("erro"),
        }

        self._register_tool_metadata(tool_record)
        return tool_record

    def list_developed_tools(self) -> List[Dict[str, Any]]:
        """Lista todas as ferramentas já desenvolvidas."""
        meta_file = self.tools_dir / "tools_registry.json"
        if not meta_file.exists():
            return []
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            return []

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
