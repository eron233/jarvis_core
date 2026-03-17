"""
JARVIS - Motor de Sincronizacao Autonoma

Responsavel por:
- observar o estado Git do projeto em ciclos periodicos
- coordenar locks de area entre dispositivos autorizados
- executar sincronizacao autonoma quando houver opt-in explicito para escrita Git
- registrar logs e checkpoints internos de continuidade de desenvolvimento

Integracoes principais:
- runtime.vital_organs.vital_organs_orchestrator
- runtime.internal_agent_runtime
- git local do repositorio Jarvis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Dict, Iterable, List, Sequence


AUTHORIZED_DEVICES = ("pc_esposa(voce)", "pc_melhor_amigo")


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "sim", "yes", "on"}:
        return True
    if normalized in {"0", "false", "nao", "no", "off"}:
        return False
    return default


@dataclass
class AutonomousSyncConfig:
    """Configuracao interna do motor de sincronizacao autonoma."""

    enabled: bool = False
    write_enabled: bool = False
    device_name: str | None = None
    peer_devices: tuple[str, ...] = AUTHORIZED_DEVICES
    sync_area: str = "global"
    sync_interval_seconds: int = 300
    lock_timeout_seconds: int = 1800
    remote_name: str = "origin"
    branch_name: str = "master"
    tests_command: tuple[str, ...] = field(
        default_factory=lambda: (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
    )

    @classmethod
    def from_env(cls) -> "AutonomousSyncConfig":
        """Carrega configuracao do ambiente sem expor essa camada na interface."""

        interval = int(os.environ.get("JARVIS_AUTONOMOUS_SYNC_INTERVAL_SECONDS", "300") or "300")
        interval = min(max(interval, 180), 420)
        return cls(
            enabled=_parse_bool(os.environ.get("JARVIS_AUTONOMOUS_SYNC_ENABLED"), False),
            write_enabled=_parse_bool(os.environ.get("JARVIS_AUTONOMOUS_SYNC_ALLOW_GIT_WRITE"), False),
            device_name=os.environ.get("JARVIS_SYNC_DEVICE_NAME"),
            sync_area=(os.environ.get("JARVIS_SYNC_AREA") or "global").strip() or "global",
            sync_interval_seconds=interval,
            lock_timeout_seconds=max(
                int(os.environ.get("JARVIS_AUTONOMOUS_SYNC_LOCK_TIMEOUT_SECONDS", "1800") or "1800"),
                300,
            ),
            remote_name=(os.environ.get("JARVIS_SYNC_REMOTE") or "origin").strip() or "origin",
            branch_name=(os.environ.get("JARVIS_SYNC_BRANCH") or "master").strip() or "master",
        )


@dataclass
class CommandResult:
    """Representa a execucao de um comando externo usado pelo sync."""

    command: List[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass
class AutonomousSyncEngine:
    """Coordena sincronizacao Git autonoma com protecoes defensivas."""

    project_root: Path
    config: AutonomousSyncConfig = field(default_factory=AutonomousSyncConfig.from_env)
    command_runner: Callable[[Sequence[str]], CommandResult] | None = None
    time_provider: Callable[[], float] = time.time
    last_run_epoch: float | None = None

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root)
        self.coordination_dir = self.project_root / "coordination"
        self.development_dir = self.project_root / "development"
        self.lock_path = self.coordination_dir / "TASK_LOCKS.json"
        self.checkpoint_path = self.coordination_dir / "SESSION_CHECKPOINT_PTBR.md"
        self.log_path = self.development_dir / "AUTONOMOUS_SYNC_LOG.txt"
        self.coordination_dir.mkdir(parents=True, exist_ok=True)
        self.development_dir.mkdir(parents=True, exist_ok=True)
        if not self.lock_path.exists():
            self._write_json(
                self.lock_path,
                {"updated_at": self._utc_now(), "locks": []},
            )
        if not self.checkpoint_path.exists():
            self.checkpoint_path.write_text(
                "# Session Checkpoint de Desenvolvimento\n\n",
                encoding="utf-8",
            )
        if not self.log_path.exists():
            self.log_path.write_text("", encoding="utf-8")
        if self.command_runner is None:
            self.command_runner = self._default_command_runner

    def run(self, runtime: Any) -> Dict[str, Any]:
        """Executa um ciclo de sincronizacao quando a janela temporal permitir."""

        if not self.config.enabled:
            return self._report(
                status="observacao",
                action="disabled",
                message="Sincronizacao autonoma instalada, mas desabilitada por ambiente.",
            )

        if not self.config.device_name:
            return self._report(
                status="observacao",
                action="missing_device_name",
                message="Sincronizacao autonoma aguardando JARVIS_SYNC_DEVICE_NAME.",
            )

        if self.config.device_name not in self.config.peer_devices:
            return self._report(
                status="critico",
                action="unauthorized_device",
                message="Dispositivo nao autorizado para cooperacao autonoma.",
                findings=[{"severity": "high", "message": "device_name fora da lista autorizada"}],
            )

        if not self._is_due():
            return self._report(
                status="observacao",
                action="waiting_interval",
                message="Janela de sincronizacao ainda nao venceu.",
            )

        self.last_run_epoch = self.time_provider()
        actions: List[Dict[str, Any]] = []
        findings: List[Dict[str, Any]] = []

        fetch_result = self._run(["git", "fetch", self.config.remote_name])
        actions.append(self._command_action("git_fetch", fetch_result))
        if not fetch_result.ok:
            return self._report(
                status="critico",
                action="git_fetch_failed",
                message="Nao foi possivel consultar alteracoes remotas.",
                actions=actions,
                findings=[{"severity": "high", "message": fetch_result.stderr.strip() or "git fetch falhou"}],
            )

        remote_state = self._read_remote_state()
        if not self.config.write_enabled:
            message = "Motor em modo seguro: apenas observacao e diagnostico Git."
            self._append_log(action="observe_only", result=message)
            return self._report(
                status="observacao",
                action="observe_only",
                message=message,
                actions=actions,
                findings=findings,
                metadata={"remote_state": remote_state},
            )

        lock_result = self._reserve_lock()
        if not lock_result["granted"]:
            findings.append(
                {
                    "severity": "medium",
                    "message": lock_result["message"],
                    "current_lock": lock_result.get("lock"),
                }
            )
            self._append_log(action="lock_denied", result=lock_result["message"])
            return self._report(
                status="atencao",
                action="lock_denied",
                message=lock_result["message"],
                actions=actions,
                findings=findings,
                metadata={"remote_state": remote_state},
            )

        try:
            rebase_result = self._run(
                ["git", "pull", "--rebase", self.config.remote_name, self.config.branch_name]
            )
            actions.append(self._command_action("git_pull_rebase", rebase_result))
            if not rebase_result.ok:
                self._run(["git", "rebase", "--abort"], tolerate_failure=True)
                self._append_log(action="rebase_conflict", result=rebase_result.stderr.strip() or "pull --rebase falhou")
                return self._report(
                    status="critico",
                    action="rebase_conflict",
                    message="Conflito ou falha durante git pull --rebase.",
                    actions=actions,
                    findings=[{"severity": "high", "message": rebase_result.stderr.strip() or "rebase falhou"}],
                    metadata={"remote_state": remote_state},
                )

            tests_result = self._run(list(self.config.tests_command))
            actions.append(self._command_action("tests", tests_result))
            if not tests_result.ok:
                self._append_log(action="tests_failed", result="Commit cancelado por falha na suite.")
                return self._report(
                    status="critico",
                    action="tests_failed",
                    message="A sincronizacao autonoma cancelou commit/push porque os testes falharam.",
                    actions=actions,
                    findings=[{"severity": "high", "message": "python -m unittest discover -s tests -v falhou"}],
                    metadata={"remote_state": remote_state},
                )

            changed_files = self._parse_changed_files()
            allowed_files, blocked_files = self._classify_changed_files(changed_files)
            if blocked_files:
                message = "Workspace contem mudancas fora da area reservada; commit automatico foi bloqueado."
                self._append_log(action="blocked_out_of_scope_changes", result=message)
                return self._report(
                    status="atencao",
                    action="blocked_out_of_scope_changes",
                    message=message,
                    actions=actions,
                    findings=[{"severity": "medium", "message": message, "files": blocked_files}],
                    metadata={"remote_state": remote_state, "allowed_files": allowed_files},
                )

            if not allowed_files:
                self._append_checkpoint(
                    task="sem_mudancas_commitaveis",
                    result="nenhuma_mudanca_relevante",
                    commit_sha=None,
                )
                self._append_log(action="no_changes", result="Nenhuma mudanca elegivel para commit.")
                return self._report(
                    status="saudavel",
                    action="no_changes",
                    message="Sincronizacao concluida sem mudancas locais elegiveis para commit.",
                    actions=actions,
                    metadata={"remote_state": remote_state},
                )

            add_result = self._run(["git", "add", "--", *allowed_files])
            actions.append(self._command_action("git_add", add_result))
            if not add_result.ok:
                return self._report(
                    status="critico",
                    action="git_add_failed",
                    message="Nao foi possivel preparar os arquivos para commit.",
                    actions=actions,
                    findings=[{"severity": "high", "message": add_result.stderr.strip() or "git add falhou"}],
                    metadata={"remote_state": remote_state},
                )

            commit_message = self._build_commit_message()
            commit_result = self._run(["git", "commit", "-m", commit_message])
            actions.append(self._command_action("git_commit", commit_result))
            if not commit_result.ok:
                return self._report(
                    status="atencao",
                    action="git_commit_skipped",
                    message="Nenhum commit foi gerado automaticamente neste ciclo.",
                    actions=actions,
                    findings=[{"severity": "medium", "message": commit_result.stderr.strip() or commit_result.stdout.strip() or "git commit sem alteracoes"}],
                    metadata={"remote_state": remote_state},
                )

            commit_sha = self._current_commit()
            push_result = self._run(["git", "push", self.config.remote_name, self.config.branch_name])
            actions.append(self._command_action("git_push", push_result))
            if not push_result.ok:
                self._append_checkpoint(
                    task=f"sincronizacao_autonoma:{self.config.sync_area}",
                    result="push_falhou",
                    commit_sha=commit_sha,
                )
                return self._report(
                    status="critico",
                    action="git_push_failed",
                    message="Commit local criado, mas o push remoto falhou.",
                    actions=actions,
                    findings=[{"severity": "high", "message": push_result.stderr.strip() or "git push falhou"}],
                    metadata={"remote_state": remote_state, "commit_sha": commit_sha},
                )

            self._append_checkpoint(
                task=f"sincronizacao_autonoma:{self.config.sync_area}",
                result="push_concluido",
                commit_sha=commit_sha,
            )
            self._append_log(
                action="sync_completed",
                result=f"Pull, testes, commit e push concluidos em {commit_sha}.",
            )
            return self._report(
                status="saudavel",
                action="sync_completed",
                message="Ciclo de sincronizacao autonoma concluido com sucesso.",
                actions=actions,
                metadata={"remote_state": remote_state, "commit_sha": commit_sha, "changed_files": allowed_files},
            )
        finally:
            self._release_lock()

    def run_autonomous_sync_loop(self, runtime: Any, stop_condition: Callable[[], bool] | None = None) -> None:
        """Loop continuo auxiliar para execucao isolada, quando necessario."""

        while True:
            if stop_condition is not None and stop_condition():
                break
            self.run(runtime)
            time.sleep(self.config.sync_interval_seconds)

    def _reserve_lock(self) -> Dict[str, Any]:
        snapshot = self._read_locks()
        now = self._utc_now()
        active_locks = []
        granted = True
        blocking_lock = None

        for lock in snapshot.get("locks", []):
            if not self._is_lock_stale(lock):
                active_locks.append(lock)
            if (
                lock.get("area") == self.config.sync_area
                and lock.get("device") != self.config.device_name
                and not self._is_lock_stale(lock)
            ):
                granted = False
                blocking_lock = lock

        if not granted:
            return {
                "granted": False,
                "message": f"Area {self.config.sync_area} reservada por {blocking_lock.get('device')}.",
                "lock": blocking_lock,
            }

        active_locks = [
            lock
            for lock in active_locks
            if not (lock.get("area") == self.config.sync_area and lock.get("device") == self.config.device_name)
        ]
        active_locks.append(
            {
                "area": self.config.sync_area,
                "device": self.config.device_name,
                "timestamp": now,
                "status": "working",
            }
        )
        self._write_json(
            self.lock_path,
            {"updated_at": now, "locks": active_locks},
        )
        return {"granted": True, "message": "Lock reservado com sucesso."}

    def _release_lock(self) -> None:
        snapshot = self._read_locks()
        remaining = [
            lock
            for lock in snapshot.get("locks", [])
            if not (lock.get("area") == self.config.sync_area and lock.get("device") == self.config.device_name)
        ]
        self._write_json(
            self.lock_path,
            {"updated_at": self._utc_now(), "locks": remaining},
        )

    def _read_locks(self) -> Dict[str, Any]:
        try:
            return json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {"updated_at": self._utc_now(), "locks": []}

    def _append_checkpoint(self, *, task: str, result: str, commit_sha: str | None) -> None:
        entry = (
            f"## {self._utc_now()}\n"
            f"- dispositivo: {self.config.device_name}\n"
            f"- area: {self.config.sync_area}\n"
            f"- branch: {self.config.branch_name}\n"
            f"- tarefa executada: {task}\n"
            f"- resultado: {result}\n"
            f"- commit gerado: {commit_sha or 'nenhum'}\n\n"
        )
        with self.checkpoint_path.open("a", encoding="utf-8") as handle:
            handle.write(entry)

    def _append_log(self, *, action: str, result: str) -> None:
        line = (
            f"{self._utc_now()} | dispositivo={self.config.device_name or 'indefinido'} | "
            f"acao={action} | resultado={result}\n"
        )
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def _read_remote_state(self) -> Dict[str, Any]:
        result = self._run(
            [
                "git",
                "rev-list",
                "--left-right",
                "--count",
                f"{self.config.remote_name}/{self.config.branch_name}...HEAD",
            ],
            tolerate_failure=True,
        )
        behind = 0
        ahead = 0
        if result.ok:
            parts = result.stdout.strip().split()
            if len(parts) == 2:
                behind = int(parts[0])
                ahead = int(parts[1])
        return {"ahead": ahead, "behind": behind}

    def _parse_changed_files(self) -> List[str]:
        result = self._run(["git", "status", "--porcelain"], tolerate_failure=True)
        if not result.ok:
            return []
        files: List[str] = []
        for line in result.stdout.splitlines():
            cleaned = line[3:].strip()
            if cleaned:
                files.append(cleaned)
        return files

    def _classify_changed_files(self, files: Iterable[str]) -> tuple[List[str], List[str]]:
        allowed_prefixes = self._allowed_prefixes()
        allowed: List[str] = []
        blocked: List[str] = []
        for file_path in files:
            normalized = file_path.replace("\\", "/")
            if any(
                normalized == prefix.rstrip("/")
                or normalized.startswith(prefix)
                for prefix in allowed_prefixes
            ):
                allowed.append(file_path)
            else:
                blocked.append(file_path)
        return allowed, blocked

    def _allowed_prefixes(self) -> List[str]:
        if self.config.sync_area == "global":
            return [""]
        return [
            f"{self.config.sync_area}/",
            "tests/",
            "README.md",
            "ARCHITECTURE.md",
            "CHANGELOG.md",
            "NEXT_STEPS.md",
            "SYSTEM_MATURITY_REPORT_PTBR.md",
            "system_capabilities_index.md",
            "coordination/TASK_LOCKS.json",
        ]

    def _build_commit_message(self) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"autonomous-sync({self.config.device_name}/{self.config.sync_area}): checkpoint {timestamp}"

    def _current_commit(self) -> str | None:
        result = self._run(["git", "rev-parse", "HEAD"], tolerate_failure=True)
        if not result.ok:
            return None
        return result.stdout.strip() or None

    def _is_due(self) -> bool:
        if self.last_run_epoch is None:
            return True
        return (self.time_provider() - self.last_run_epoch) >= self.config.sync_interval_seconds

    def _is_lock_stale(self, lock: Dict[str, Any]) -> bool:
        timestamp = lock.get("timestamp")
        try:
            moment = datetime.fromisoformat(str(timestamp))
        except ValueError:
            return True
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - moment.astimezone(timezone.utc)).total_seconds()
        return age > self.config.lock_timeout_seconds

    def _run(self, command: Sequence[str], tolerate_failure: bool = False) -> CommandResult:
        result = self.command_runner(command)
        if not tolerate_failure:
            self._append_log(action="command", result=f"{' '.join(command)} -> {result.returncode}")
        return result

    def _default_command_runner(self, command: Sequence[str]) -> CommandResult:
        completed = subprocess.run(
            list(command),
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        return CommandResult(
            command=list(command),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _command_action(self, action_id: str, result: CommandResult) -> Dict[str, Any]:
        return {
            "action_id": action_id,
            "returncode": result.returncode,
            "ok": result.ok,
            "stdout": result.stdout.strip()[:400],
            "stderr": result.stderr.strip()[:400],
        }

    def _report(
        self,
        *,
        status: str,
        action: str,
        message: str,
        actions: List[Dict[str, Any]] | None = None,
        findings: List[Dict[str, Any]] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return {
            "organ_id": "autonomous_sync_engine",
            "status": status,
            "executado_em": self._utc_now(),
            "acao": action,
            "mensagem": message,
            "achados": list(findings or []),
            "acoes_aplicadas": list(actions or []),
            "resumo": {
                "device": self.config.device_name,
                "area": self.config.sync_area,
                "write_enabled": self.config.write_enabled,
                "intervalo_segundos": self.config.sync_interval_seconds,
            },
            "metadata": dict(metadata or {}),
        }

    @staticmethod
    def _write_json(path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp_path, path)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
