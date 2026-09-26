"""
JARVIS - Motor de Correção Automatizada de Git por Branch Isolada (Git Branch Patcher)

Responsável por:
- criar uma branch isolada temporária (ex: `jarvis/fix-vulnerability-zday`) ao encontrar uma vulnerabilidade
- aplicar a correção no código-fonte
- executar a suíte de testes de validação no ambiente isolado
- gerar um relatório de Pull Request/Diff para aprovação do proprietário antes do merge final
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import difflib
import sys
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("jarvis.security.git_patcher")


class GitBranchPatcherEngine:
    """Verifica patches de seguranca propostos e prepara o material para revisao humana."""

    def __init__(self, project_root: Optional[Path] = None, data_dir: Optional[Path] = None) -> None:
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parents[1]
        self.data_dir = Path(data_dir) if data_dir else self.project_root / "data" / "git_patches"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def prepare_patch_for_review(
        self,
        vulnerability_id: str,
        target_filepath: str,
        patch_content: str,
        run_tests: bool = True,
    ) -> Dict[str, Any]:
        """
        Verifica um patch proposto e monta o material para revisao humana.

        Parametros:
        - vulnerability_id: identificador da vulnerabilidade tratada.
        - target_filepath: arquivo que o patch pretende alterar, relativo a raiz.
        - patch_content: conteudo proposto para o arquivo.
        - run_tests: intencao de executar a suite; registrada no relatorio.

        Retorno:
        - relatorio com o diff real, a verificacao de sintaxe e o que nao foi feito.

        Efeitos no sistema:
        - grava o relatorio em disco. Nao cria branch, nao altera o arquivo alvo
          e nao executa testes.

        O metodo anterior se chamava `apply_patch_in_isolated_branch` e a
        docstring dizia que criava a branch, aplicava a modificacao e rodava os
        testes. Nada disso acontecia: nenhum comando git era executado, o
        arquivo alvo nunca era escrito, `run_tests` era ignorado e o diff era um
        texto fixo. Ainda assim o relatorio dizia "Testes: APROVADO" e pedia ao
        dono que fizesse merge de uma branch que nao existia.
        """

        now = datetime.now(timezone.utc).isoformat()
        clean_vuln_id = vulnerability_id.lower().replace(" ", "-").replace("/", "-")
        branch_name = f"jarvis/fix-{clean_vuln_id}"
        target_path = self.project_root / target_filepath

        original_code = target_path.read_text(encoding="utf-8") if target_path.exists() else ""

        sintaxe_valida = True
        saida_sintaxe = "O patch proposto compila."
        try:
            compile(patch_content, filename=target_filepath, mode="exec")
        except SyntaxError as erro:
            sintaxe_valida = False
            saida_sintaxe = f"Erro de sintaxe no patch proposto: {erro}"

        # Diff real entre o arquivo atual e o conteudo proposto, no lugar do
        # texto fixo que a versao anterior devolvia como se fosse um diff.
        diff = "\n".join(
            difflib.unified_diff(
                original_code.splitlines(),
                patch_content.splitlines(),
                fromfile=f"a/{target_filepath}",
                tofile=f"b/{target_filepath}",
                lineterm="",
            )
        )

        report = {
            "id_vulnerabilidade": vulnerability_id,
            "caminho_arquivo": target_filepath,
            "arquivo_alvo_existe": target_path.exists(),
            "nome_branch_sugerida": branch_name,
            "branch_criada": False,
            "patch_aplicado": False,
            "gerado_em": now,
            "status_patch": "proposta_verificada" if sintaxe_valida else "erro_de_sintaxe",
            "sintaxe_valida": sintaxe_valida,
            "saida_sintaxe": saida_sintaxe,
            "testes_executados": False,
            "testes_solicitados": bool(run_tests),
            "motivo_testes": (
                "A execucao de testes nao esta implementada neste motor; a verificacao "
                "cobre apenas a sintaxe do patch proposto."
            ),
            "diff_unificado": diff,
            "acao_requerida": (
                "Revisar o diff e, se aprovado, criar a branch, aplicar o patch e rodar "
                "a suite manualmente. Nada foi alterado no repositorio."
            ),
            "resumo_ptbr": (
                f"Proposta de patch para '{vulnerability_id}' verificada. "
                f"Sintaxe: {'valida' if sintaxe_valida else 'invalida'}. "
                f"Branch sugerida '{branch_name}' ainda nao existe e o arquivo nao foi alterado."
            ),
        }

        self._save_patch_report(vulnerability_id, report)
        return report

    def apply_patch_in_isolated_branch(
        self,
        vulnerability_id: str,
        target_filepath: str,
        patch_content: str,
        run_tests: bool = True,
    ) -> Dict[str, Any]:
        """
        Nome antigo, mantido para nao quebrar chamadores externos.

        O nome prometia criar branch e aplicar o patch, o que nunca aconteceu.
        Encaminha para `prepare_patch_for_review`.
        """

        return self.prepare_patch_for_review(
            vulnerability_id=vulnerability_id,
            target_filepath=target_filepath,
            patch_content=patch_content,
            run_tests=run_tests,
        )

    def _save_patch_report(self, vuln_id: str, report: Dict[str, Any]) -> None:
        """Salva o relatório de patch em arquivo JSON."""
        clean_id = vuln_id.replace(" ", "_").replace("/", "_")
        file_path = self.data_dir / f"patch_{clean_id}_{int(datetime.now(timezone.utc).timestamp())}.json"
        file_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
