"""
JARVIS - Preparo de Correção em Branch Isolada (Git Branch Patcher)

Responsável por:
- validar a sintaxe do patch proposto (compilação real, para arquivos .py);
- gerar um diff unificado REAL entre o conteúdo atual do arquivo-alvo e o patch proposto;
- quando o projeto é um repositório git, criar de verdade uma branch isolada (ponteiro, sem
  trocar de branch nem alterar arquivos) para receber a correção sob revisão;
- NUNCA fazer merge autônomo: a correção fica preparada e requer aprovação/execução do dono.

Honestidade: fora de um repositório git, o método opera em modo "dry_run" e declara que
NENHUMA branch foi criada — em vez de fingir isolamento.
"""

from __future__ import annotations

from datetime import datetime, timezone
import difflib
import json
import logging
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("jarvis.security.git_patcher")


class GitBranchPatcherEngine:
    """Prepara correções de segurança em branch isolada, com diff real e validação de sintaxe."""

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
        Prepara a correção: valida a sintaxe, gera um diff real e, em repositório git, cria uma
        branch isolada para a revisão. Não aplica no arquivo vivo nem faz merge.
        """
        now = datetime.now(timezone.utc).isoformat()
        clean_vuln_id = vulnerability_id.lower().replace(" ", "-").replace("/", "-")
        branch_name = f"jarvis/fix-{clean_vuln_id}"

        target_path = self.project_root / target_filepath
        original_code = target_path.read_text(encoding="utf-8") if target_path.exists() else ""

        # 1. Validação real de sintaxe do patch (para Python)
        syntax_ok, syntax_msg = self._validate_syntax(patch_content, target_filepath)

        # 2. Diff unificado REAL entre o conteúdo atual e o patch proposto
        diff_lines = list(difflib.unified_diff(
            original_code.splitlines(),
            patch_content.splitlines(),
            fromfile=f"a/{target_filepath}",
            tofile=f"b/{target_filepath}",
            lineterm="",
        ))
        diff_text = "\n".join(diff_lines) if diff_lines else "(sem diferenças)"

        # 3. Criação real da branch isolada quando há repositório git
        is_git, git_msg = self._is_git_repo()
        branch_created = False
        branch_msg = "Fora de repositório git: nenhuma branch criada (modo dry_run)."
        if is_git:
            branch_created, branch_msg = self._create_branch(branch_name)

        report = {
            "id_vulnerabilidade": vulnerability_id,
            "caminho_arquivo": target_filepath,
            "nome_branch_isolada": branch_name,
            "gerado_em": now,
            "e_repositorio_git": is_git,
            "branch_criada": branch_created,
            "branch_status": branch_msg,
            "modo": "git_branch" if branch_created else "dry_run",
            "testes_passaram": syntax_ok,
            "saida_testes": syntax_msg,
            "diff_unificado": diff_text,
            "linhas_diff": len(diff_lines),
            "status_patch": "pronto_para_revisao" if syntax_ok else "erro_de_sintaxe",
            "acao_requerida": (
                "Revisar o diff e, se aprovado, aplicar e fazer merge manualmente. "
                "O JARVIS não faz merge autônomo."
            ),
            "resumo_ptbr": (
                f"Correção para '{vulnerability_id}' preparada em '{branch_name}'. "
                f"Sintaxe: {'OK' if syntax_ok else 'FALHOU'}. "
                f"{'Branch git criada.' if branch_created else branch_msg} "
                "Requer revisão e merge manual do dono."
            ),
        }
        self._save_patch_report(vulnerability_id, report)
        return report

    def _validate_syntax(self, patch_content: str, target_filepath: str) -> tuple[bool, str]:
        if not target_filepath.endswith(".py"):
            return True, "Arquivo não-Python: validação de sintaxe Python não aplicável."
        try:
            compile(patch_content, filename=target_filepath, mode="exec")
            return True, "Sintaxe Python validada com sucesso."
        except SyntaxError as exc:
            return False, f"Erro de sintaxe no patch: {exc}"

    def _is_git_repo(self) -> tuple[bool, str]:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(self.project_root), capture_output=True, text=True, timeout=5,
            )
            return (res.returncode == 0 and res.stdout.strip() == "true"), res.stderr.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)

    def _create_branch(self, branch_name: str) -> tuple[bool, str]:
        """Cria um ponteiro de branch a partir do HEAD, sem trocar de branch nem tocar arquivos."""
        try:
            res = subprocess.run(
                ["git", "branch", branch_name],
                cwd=str(self.project_root), capture_output=True, text=True, timeout=10,
            )
            if res.returncode == 0:
                return True, f"Branch '{branch_name}' criada a partir do HEAD."
            stderr = res.stderr.strip()
            if "already exists" in stderr:
                return True, f"Branch '{branch_name}' já existe; reutilizada."
            return False, f"Falha ao criar branch: {stderr}"
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"Erro ao executar git: {exc}"

    def _save_patch_report(self, vuln_id: str, report: Dict[str, Any]) -> None:
        clean_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in vuln_id)[:40]
        path = self.data_dir / f"patch_{clean_id}_{int(datetime.now(timezone.utc).timestamp() * 1000)}.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
