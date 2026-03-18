"""
JARVIS - Motor de Higiene do Runtime

Responsavel por:
- validar separacao entre codigo versionado e estado vivo operacional
- confirmar que stores oficiais estao em locais coerentes
- detectar risco de sujeira de Git causada por artefatos vivos

Integracoes principais:
- runtime.internal_agent_runtime
- runtime.system_config
- executive_planner.queue
- memory_system.semantic_memory
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any, Dict, Iterable, List


@dataclass
class RuntimeHygieneEngine:
    """Monitora higiene de stores e separacao entre codigo e estado vivo."""

    project_root: Path
    official_data_dir: Path
    official_reports_dir: Path
    operational_paths: Dict[str, Path]

    def run(self, runtime: Any) -> Dict[str, Any]:
        """Executa verificacoes de higiene do runtime e do repositorio local."""

        findings: List[Dict[str, Any]] = []

        for label, path in self.operational_paths.items():
            if label.endswith("_report_path"):
                expected_parent = self.official_reports_dir
            else:
                expected_parent = self.official_data_dir

            if path.parent.resolve() != expected_parent.resolve():
                findings.append(
                    {
                        "finding_id": f"{label}_outside_official_dir",
                        "severity": "high",
                        "message": f"{label} esta fora do diretorio oficial esperado.",
                        "caminho_observado": str(path),
                        "diretorio_esperado": str(expected_parent),
                    }
                )

        tracked_live_state = [
            {
                "label": label,
                "path": str(path),
            }
            for label, path in self.operational_paths.items()
            if self._git_is_tracked(path)
        ]
        if tracked_live_state:
            findings.append(
                {
                    "finding_id": "tracked_operational_state",
                    "severity": "high",
                    "message": "Ha stores operacionais vivos rastreados pelo Git.",
                    "itens": tracked_live_state,
                }
            )

        dirty_live_state = self._git_dirty_entries(self._paths_for_git())
        if dirty_live_state:
            findings.append(
                {
                    "finding_id": "dirty_operational_paths",
                    "severity": "medium",
                    "message": "Arquivos operacionais estao sujando a arvore Git no projeto atual.",
                    "itens": dirty_live_state,
                }
            )

        git_available = self._git_available()
        if not git_available:
            findings.append(
                {
                    "finding_id": "git_unavailable_for_hygiene",
                    "severity": "medium",
                    "message": "Nao foi possivel consultar o Git para validar a higiene operacional.",
                }
            )

        status = "saudavel"
        if any(item["severity"] == "high" for item in findings):
            status = "critico"
        elif findings:
            status = "atencao"

        return {
            "organ_id": "runtime_hygiene_engine",
            "status": status,
            "executado_em": runtime._utc_now(),
            "achados": findings,
            "resumo": {
                "total_achados": len(findings),
                "data_dir_oficial": str(self.official_data_dir),
                "reports_dir_oficial": str(self.official_reports_dir),
                "git_disponivel": git_available,
            },
        }

    def _paths_for_git(self) -> List[Path]:
        """Executa a rotina interna de paths for git."""
        return list(self.operational_paths.values()) + [self.official_data_dir, self.official_reports_dir]

    def _git_available(self) -> bool:
        """Executa a rotina interna de git available."""
        try:
            subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return False

    def _git_is_tracked(self, path: Path) -> bool:
        """Executa a rotina interna de git is tracked."""
        try:
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(path)],
                cwd=self.project_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return False

    def _git_dirty_entries(self, paths: Iterable[Path]) -> List[str]:
        """Executa a rotina interna de git dirty entries."""
        try:
            command = ["git", "status", "--porcelain", "--"]
            command.extend(str(path) for path in paths)
            result = subprocess.run(
                command,
                cwd=self.project_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return []
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return []
