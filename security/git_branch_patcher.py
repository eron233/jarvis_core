"""
JARVIS - Pre-validacao de patch de seguranca (dry-run)

Responsavel por:
- validar a sintaxe Python de um patch proposto para um arquivo do projeto
- gerar um diff unificado real entre o arquivo atual e o patch
- registrar a proposta para revisao humana

NAO cria branch, NAO grava o arquivo e NAO roda a suite de testes: a aplicacao
fica com o dono, via git, depois de revisar o diff.
"""

from __future__ import annotations

from datetime import datetime, timezone
import difflib
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("jarvis.security.git_patcher")


class GitBranchPatcherEngine:
    """Motor de aplicação e validação autônoma de correções de segurança em branch isolada."""

    def __init__(self, project_root: Optional[Path] = None, data_dir: Optional[Path] = None) -> None:
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parents[1]
        self.data_dir = Path(data_dir) if data_dir else self.project_root / "data" / "git_patches"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def apply_patch_in_isolated_branch(
        self,
        vulnerability_id: str,
        target_filepath: str,
        patch_content: str,
        run_tests: bool = True,
    ) -> Dict[str, Any]:
        """
        Cria uma nova branch isolada, aplica as modificações, roda testes e prepara o Diff para aprovação.
        """
        now = datetime.now(timezone.utc).isoformat()
        clean_vuln_id = re.sub(r"[^a-z0-9_-]", "-", vulnerability_id.lower())[:60] or "patch"
        branch_name = f"jarvis/fix-{clean_vuln_id}"

        root = self.project_root.resolve()
        target_path = (root / target_filepath).resolve()
        if target_path != root and root not in target_path.parents:
            return {
                "id_vulnerabilidade": vulnerability_id,
                "caminho_arquivo": target_filepath,
                "status_patch": "bloqueado",
                "motivo": "Arquivo fora da raiz do projeto.",
            }

        original_code = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""

        syntax_ok = True
        syntax_output = "Sintaxe Python valida."
        if target_filepath.endswith(".py"):
            try:
                compile(patch_content, filename=target_filepath, mode="exec")
            except SyntaxError as exc:
                syntax_ok = False
                syntax_output = f"Erro de sintaxe no patch fornecido: {exc}"
        else:
            syntax_output = "Arquivo nao-Python: sintaxe nao verificada."

        diff_lines = list(
            difflib.unified_diff(
                original_code.splitlines(keepends=True),
                patch_content.splitlines(keepends=True),
                fromfile=f"a/{target_filepath}",
                tofile=f"b/{target_filepath}",
            )
        )

        report = {
            "id_vulnerabilidade": vulnerability_id,
            "caminho_arquivo": target_filepath,
            "arquivo_existe": target_path.is_file(),
            "nome_branch_sugerida": branch_name,
            "branch_criada": False,
            "arquivo_alterado": False,
            "testes_executados": False,
            "gerado_em": now,
            "status_patch": "pronto_para_revisao" if syntax_ok else "erro_de_sintaxe",
            "sintaxe_valida": syntax_ok,
            "saida_validacao": syntax_output,
            "linhas_diff": len(diff_lines),
            "diff": "".join(diff_lines)[:20000],
            "acao_requerida": (
                f"Revisar o diff, criar a branch '{branch_name}', aplicar e rodar os testes manualmente."
            ),
            "resumo_ptbr": (
                f"Proposta de patch para '{vulnerability_id}' validada ({'sintaxe OK' if syntax_ok else 'sintaxe invalida'}). "
                "Nada foi aplicado ao repositorio."
            ),
        }

        self._save_patch_report(vulnerability_id, report)
        return report

    def _save_patch_report(self, vuln_id: str, report: Dict[str, Any]) -> None:
        """Salva o relatório de patch em arquivo JSON."""
        clean_id = re.sub(r"[^A-Za-z0-9_-]", "_", vuln_id)[:60] or "patch"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        file_path = self.data_dir / f"patch_{clean_id}_{timestamp}.json"
        file_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
