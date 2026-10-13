"""REA experimental: analise estatica solicitada, jamais execucao do alvo.

Integra-se ao cliente MCP oficial do JARVIS. REA nao e sandbox; este adapter
so admite alvos dentro de um workspace aprovado e duas ferramentas de leitura.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from runtime.mcp_stack import OfficialMCPClientManager


class REAInvestigator:
    """Gate separado do MCP generico para investigacao de artefatos locais."""

    def __init__(self, mcp_manager: Optional[OfficialMCPClientManager] = None,
                 allowed_root: Optional[Path] = None) -> None:
        self.mcp_manager = mcp_manager or OfficialMCPClientManager()
        self.allowed_root = Path(allowed_root) if allowed_root else (
            Path(__file__).resolve().parents[1] / "data" / "rea_targets"
        )

    def inspect_static(self, path: str, kind: str,
                       *, approved: bool = False) -> Dict[str, Any]:
        """Nao abre o arquivo no Python nem executa bytes do alvo.

        `managed` => metadata de PE/.NET, `javascript` => diretorio ou ASAR.
        Operacoes de processo, depuracao ou mutacao sao propositalmente ausentes.
        """
        if approved is not True:
            return {"status": "aguardando_aprovacao", "executado": False,
                    "motivo": "Investigacao REA exige aprovacao explicita."}
        if kind not in {"managed", "javascript"} or not isinstance(path, str) or not path.strip():
            return {"status": "entrada_invalida", "executado": False}
        root = self.allowed_root.resolve()
        target = Path(path)
        if not target.is_absolute():
            target = root / target
        try:
            resolved = target.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError, RuntimeError):
            return {"status": "bloqueado", "executado": False,
                    "motivo": "Alvo ausente ou fora do workspace autorizado."}
        if target.is_symlink():
            return {"status": "bloqueado", "executado": False,
                    "motivo": "Links simbolicos como alvo nao sao admitidos."}
        if kind == "managed":
            if not resolved.is_file() or resolved.suffix.lower() not in {".dll", ".exe"}:
                return {"status": "entrada_invalida", "executado": False,
                        "motivo": "Analise managed exige DLL/EXE PE-CLI local."}
            tool, args = "inspect_managed_artifact", {"path": str(resolved), "detail": "summary"}
        else:
            if not (resolved.is_dir() or (resolved.is_file() and resolved.suffix.lower() == ".asar")):
                return {"status": "entrada_invalida", "executado": False,
                        "motivo": "JavaScript/Electron exige diretorio ou ASAR local."}
            tool, args = "analyze_javascript_application", {"input_path": str(resolved), "detail": "summary"}
        result = self.mcp_manager.call_tool("rea-investigation", tool, args)
        if result.get("status") != "sucesso":
            return {**result, "alvo": str(resolved),
                    "conteudo_de_alvo_nao_confiavel": True, "evidencia_validada": False}
        # Nada aqui interpreta pseudocodigo ou conteudo do binario como instrucao.
        return {
            "status": "resultado_recebido",
            "alvo": str(resolved),
            "ferramenta": tool,
            "resultado_mcp": result.get("resultado"),
            "truncado": bool(result.get("truncado", False)),
            "conteudo_de_alvo_nao_confiavel": True,
            "evidencia_validada": False,
            "execucao_do_alvo": False,
            "observacao": (
                "Analise estatica reportada pelo REA. Verificar cobertura, "
                "erros e proveniencia no Evidence retornado."
            ),
        }
