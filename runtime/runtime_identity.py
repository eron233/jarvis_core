"""
JARVIS - Identidade de Build e Runtime

Responsavel por:
- identificar qual revisao do codigo esta rodando de fato
- expor commit, estado do repositorio e metadados do processo
- reduzir ambiguidade entre repositrio, testes e runtime vivo

Integracoes principais:
- runtime.internal_agent_runtime
- runtime.server
- interface.api.app
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict
import uuid


# JARVIS_RUNTIME_ENTRYPOINT
# ==================================================
# BLOCO: Descoberta de identidade de build e processo
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_VERSION = "0.1.0"
IDENTITY_SOURCE_FILES = (
    PROJECT_ROOT / "interface" / "api" / "app.py",
    PROJECT_ROOT / "main.py",
    PROJECT_ROOT / "runtime" / "internal_agent_runtime.py",
    PROJECT_ROOT / "runtime" / "server.py",
)


def _run_git_command(*args: str) -> str | None:
    """Executa um comando git curto para montar a identidade do runtime."""

    try:
        completed = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def load_build_metadata() -> Dict[str, Any]:
    """Carrega metadados de build a partir do ambiente e do repositorio local."""

    commit = os.environ.get("JARVIS_BUILD_COMMIT") or _run_git_command("rev-parse", "HEAD") or "desconhecido"
    commit_short = (
        os.environ.get("JARVIS_BUILD_COMMIT_SHORT")
        or _run_git_command("rev-parse", "--short", "HEAD")
        or commit[:8]
    )
    commit_timestamp = (
        os.environ.get("JARVIS_BUILD_TIMESTAMP")
        or _run_git_command("show", "-s", "--format=%cI", "HEAD")
        or _fallback_build_timestamp()
    )
    dirty_output = _run_git_command("status", "--porcelain")
    repo_dirty = bool(dirty_output)

    return {
        "runtime_version": RUNTIME_VERSION,
        "commit": commit,
        "commit_curto": commit_short,
        "build_timestamp": commit_timestamp,
        "repositorio_sujo": repo_dirty,
        "fonte_identidade": "git_local" if commit != "desconhecido" else "fallback_local",
        "project_root": str(PROJECT_ROOT),
    }


def build_runtime_identity(
    *,
    entrypoint: str,
    environment: Dict[str, Any] | None = None,
    loaded_config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Monta o payload completo de identidade do runtime atualmente em execucao."""

    build_metadata = load_build_metadata()
    return {
        **build_metadata,
        "boot_id": str(uuid.uuid4()),
        "boot_timestamp": datetime.now(timezone.utc).isoformat(),
        "entrypoint": entrypoint,
        "process_id": os.getpid(),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "environment": environment or {},
        "configuracao_resumida": loaded_config or {},
    }


@dataclass(frozen=True)
class RuntimeIdentityComparison:
    """Representa a comparacao entre identidade esperada e observada."""

    expected_commit: str
    observed_commit: str
    expected_entrypoint: str
    observed_entrypoint: str

    def matches(self) -> bool:
        """Indica se commit e entrypoint observados batem com o esperado."""

        return (
            self.expected_commit == self.observed_commit
            and self.expected_entrypoint == self.observed_entrypoint
        )


def _fallback_build_timestamp() -> str:
    """Gera um timestamp de fallback a partir dos arquivos centrais do runtime."""

    mtimes = []
    for path in IDENTITY_SOURCE_FILES:
        if path.exists():
            mtimes.append(path.stat().st_mtime)

    if not mtimes:
        return datetime.now(timezone.utc).isoformat()

    latest_mtime = max(mtimes)
    return datetime.fromtimestamp(latest_mtime, tz=timezone.utc).isoformat()
