"""Entrypoint oficial do loop puro standalone do JARVIS."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import sys
import time
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from startup_bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from executive_planner.queue import LEGACY_STORAGE_PATH as LEGACY_QUEUE_STORAGE_PATH
from executive_planner.queue import TaskQueue
from executive_planner.audit import AuditLogger, traduzir_motivo, traduzir_status
from intent_layer.goal_manager import LEGACY_GOALS_PATH
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import LEGACY_STORAGE_PATH as LEGACY_SEMANTIC_STORAGE_PATH
from memory_system.semantic_memory import SemanticMemory
from device.device_registry import DeviceRegistry
from runtime.cognitive_evolution import CognitiveEvolutionTracker
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.system_config import JarvisEnvironmentConfig
from security.self_defense import SelfDefenseMonitor

MOTIVOS_ENCERRAMENTO_PTBR = {
    "requested": "encerramento_solicitado",
    "idle_queue": "fila_vazia",
    "max_cycles_reached": "limite_de_ciclos_atingido",
    "signal_sigint": "interrompido_por_sinal",
    "signal_sigterm": "encerrado_por_sinal",
}


@dataclass
class SystemLoopConfig:
    """Configuracao leve do processo continuo."""

    cycle_sleep_seconds: float = 1.0
    idle_sleep_seconds: float = 2.0
    max_cycles: Optional[int] = None
    stop_when_idle: bool = False
    install_signal_handlers: bool = True
    queue_storage_path: Optional[Path] = None
    semantic_storage_path: Optional[Path] = None
    procedural_storage_path: Optional[Path] = None
    goal_storage_path: Optional[Path] = None
    cognitive_evolution_storage_path: Optional[Path] = None
    audit_storage_path: Optional[Path] = None
    device_registry_path: Optional[Path] = None
    self_defense_report_path: Optional[Path] = None
    enable_vital_organs_background: bool = False


def bootstrap_runtime(
    runtime: Optional[InternalAgentRuntime] = None,
    config: Optional[SystemLoopConfig] = None,
    logger: Callable[[str], None] | None = None,
) -> tuple[InternalAgentRuntime, Dict[str, Any]]:
    """Prepara o runtime com os caminhos de persistencia desejados."""

    runtime = runtime or InternalAgentRuntime()
    original_config = config or SystemLoopConfig()
    deployment_config = JarvisEnvironmentConfig.from_env()

    config = SystemLoopConfig(
        cycle_sleep_seconds=original_config.cycle_sleep_seconds,
        idle_sleep_seconds=original_config.idle_sleep_seconds,
        max_cycles=original_config.max_cycles,
        stop_when_idle=original_config.stop_when_idle,
        install_signal_handlers=original_config.install_signal_handlers,
        queue_storage_path=original_config.queue_storage_path or deployment_config.queue_storage_path,
        semantic_storage_path=original_config.semantic_storage_path or deployment_config.semantic_storage_path,
        procedural_storage_path=original_config.procedural_storage_path or deployment_config.procedural_storage_path,
        goal_storage_path=original_config.goal_storage_path or deployment_config.goals_storage_path,
        cognitive_evolution_storage_path=(
            original_config.cognitive_evolution_storage_path or deployment_config.cognitive_evolution_storage_path
        ),
        audit_storage_path=original_config.audit_storage_path or deployment_config.audit_storage_path,
        device_registry_path=original_config.device_registry_path or deployment_config.device_registry_path,
        self_defense_report_path=original_config.self_defense_report_path or deployment_config.self_defense_report_path,
        enable_vital_organs_background=original_config.enable_vital_organs_background,
    )

    if original_config.queue_storage_path is not None or runtime.task_queue is None:
        runtime.task_queue = TaskQueue(storage_path=config.queue_storage_path)
        _load_queue_storage(runtime.task_queue, logger)

    if original_config.goal_storage_path is not None or runtime.goal_manager is None:
        runtime.goal_manager = _load_goal_manager(config.goal_storage_path, logger)

    if original_config.device_registry_path is not None or runtime.device_registry is None:
        runtime.device_registry = _load_device_registry(config.device_registry_path, logger)

    if original_config.cognitive_evolution_storage_path is not None or runtime.cognitive_evolution_tracker is None:
        runtime.cognitive_evolution_tracker = CognitiveEvolutionTracker(
            storage_path=config.cognitive_evolution_storage_path
        )
        _load_cognitive_evolution_storage(runtime.cognitive_evolution_tracker, logger)

    if original_config.audit_storage_path is not None or runtime.audit_logger is None:
        runtime.audit_logger = AuditLogger(storage_path=config.audit_storage_path)
        _load_audit_storage(runtime.audit_logger, logger)

    if original_config.self_defense_report_path is not None or runtime.self_defense_monitor is None:
        runtime.self_defense_monitor = SelfDefenseMonitor(report_path=config.self_defense_report_path)

    episodic_memory = runtime.memory.get("episodic") if runtime.memory else None
    procedural_memory = runtime.memory.get("procedural") if runtime.memory else None
    semantic_memory = runtime.memory.get("semantic") if runtime.memory else None

    if episodic_memory is None:
        episodic_memory = EpisodicMemory()

    if procedural_memory is None or original_config.procedural_storage_path is not None:
        procedural_path = config.procedural_storage_path or getattr(procedural_memory, "storage_path", None)
        procedural_memory = ProceduralMemory(storage_path=procedural_path)
        _load_procedural_storage(procedural_memory, logger)

    if semantic_memory is None or original_config.semantic_storage_path is not None:
        semantic_path = config.semantic_storage_path or getattr(semantic_memory, "storage_path", None)
        semantic_memory = SemanticMemory(storage_path=semantic_path) if semantic_path else SemanticMemory()
        _load_semantic_storage(semantic_memory, logger)

    runtime.memory = {
        "episodic": episodic_memory,
        "semantic": semantic_memory,
        "procedural": procedural_memory,
    }

    state = runtime.bootstrap()
    runtime.configure_vital_organs(
        project_root=PROJECT_ROOT,
        report_path=_resolve_vital_organs_report_path(config),
        official_paths=_build_vital_organs_official_paths(config),
        legacy_paths=_build_vital_organs_legacy_paths(),
        official_data_dir=_resolve_vital_organs_data_dir(config, deployment_config),
        official_reports_dir=config.self_defense_report_path.parent,
        cycle_interval_seconds=config.cycle_sleep_seconds,
        idle_sleep_seconds=config.idle_sleep_seconds,
        background_enabled=config.enable_vital_organs_background,
    )
    if config.enable_vital_organs_background:
        runtime.run_vital_organs_cycle_once()
        runtime.start_vital_organs()
    _log_message(
        logger,
        "[bootstrap] runtime={status} fila={queue_depth} memoria_semantica={memory_entries}".format(
            status=state["status_ptbr"],
            queue_depth=state["queue_depth"],
            memory_entries=len(runtime.memory["semantic"].entries),
        ),
    )
    return runtime, state


@dataclass
class JarvisSystemLoop:
    """Coordena o processo vivo inicial do sistema."""

    runtime: InternalAgentRuntime = field(default_factory=InternalAgentRuntime)
    config: SystemLoopConfig = field(default_factory=SystemLoopConfig)
    sleep_fn: Callable[[float], None] = time.sleep
    logger: Callable[[str], None] = print
    cycle_logs: List[Dict[str, Any]] = field(default_factory=list)
    shutdown_requested: bool = False
    shutdown_reason: Optional[str] = None
    _signal_handlers_installed: bool = False

    def bootstrap(self) -> Dict[str, Any]:
        """Inicializa o runtime e instala handlers de sinal quando permitido."""

        self.runtime, state = bootstrap_runtime(runtime=self.runtime, config=self.config, logger=self.logger)

        if self.config.install_signal_handlers and not self._signal_handlers_installed:
            self._install_signal_handlers()

        return state

    def request_shutdown(self, reason: str = "requested") -> None:
        """Solicita o encerramento gracioso do loop."""

        self.shutdown_requested = True
        self.shutdown_reason = reason

    def run(self) -> Dict[str, Any]:
        """Executa o loop continuo ate atingir uma condicao de parada."""

        bootstrap_state = self.bootstrap()

        while not self.shutdown_requested:
            if self.config.max_cycles is not None and len(self.cycle_logs) >= self.config.max_cycles:
                self.request_shutdown("max_cycles_reached")
                break

            cycle_id = len(self.cycle_logs) + 1
            try:
                cycle_result = self.runtime.run_planner_cycle()
                runtime_state = self.runtime.describe_state()
                cycle_log = self._record_cycle(
                    cycle_id=cycle_id,
                    cycle_result=cycle_result,
                    runtime_state=runtime_state,
                )
            except Exception as exc:  # pragma: no cover - exercitado por teste unitario dedicado
                runtime_state = self.runtime.describe_state()
                self.runtime.record_runtime_error(
                    context="system_loop_cycle",
                    error=exc,
                    metadata={"cycle_id": cycle_id},
                )
                cycle_result = {
                    "status": "failed",
                    "status_ptbr": traduzir_status("failed"),
                    "reason": "runtime_exception",
                    "reason_ptbr": traduzir_motivo("runtime_exception"),
                }
                cycle_log = self._record_cycle(
                    cycle_id=cycle_id,
                    cycle_result=cycle_result,
                    runtime_state=runtime_state,
                )

            if self.config.stop_when_idle and cycle_result["status"] == "idle":
                self.request_shutdown("idle_queue")
                break

            if self.config.max_cycles is not None and len(self.cycle_logs) >= self.config.max_cycles:
                self.request_shutdown("max_cycles_reached")
                break

            pause_seconds = (
                self.config.idle_sleep_seconds if cycle_result["status"] == "idle" else self.config.cycle_sleep_seconds
            )
            if pause_seconds > 0 and not self.shutdown_requested:
                self.sleep_fn(pause_seconds)

        persisted_state = self.runtime.persist_runtime_state()
        shutdown_summary = self._build_shutdown_summary(
            bootstrap_state=bootstrap_state,
            persisted_state=persisted_state,
            runtime_state=self.runtime.describe_state(),
        )
        self._log(self._format_shutdown_message(shutdown_summary))
        return shutdown_summary

    def _record_cycle(
        self,
        cycle_id: int,
        cycle_result: Dict[str, Any],
        runtime_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        selected_task = cycle_result.get("selected_task") or {}
        cycle_log = {
            "cycle_id": cycle_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": cycle_result["status"],
            "status_ptbr": cycle_result.get("status_ptbr"),
            "reason": cycle_result.get("reason"),
            "reason_ptbr": cycle_result.get("reason_ptbr"),
            "selected_task_id": selected_task.get("task_id"),
            "queue_depth": runtime_state["queue_depth"],
        }
        self.cycle_logs.append(cycle_log)
        self.runtime.memory["episodic"].remember(
            {
                "event": "system_cycle",
                "event_ptbr": "ciclo_sistema",
                **cycle_log,
            }
        )
        self._log(self._format_cycle_message(cycle_log))
        return cycle_log

    def _install_signal_handlers(self) -> None:
        for signame in ("SIGINT", "SIGTERM"):
            signum = getattr(signal, signame, None)
            if signum is None:
                continue
            signal.signal(signum, self._handle_signal)
        self._signal_handlers_installed = True

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        signal_name = signal.Signals(signum).name.lower()
        self.request_shutdown(f"signal_{signal_name}")

    def _build_shutdown_summary(
        self,
        bootstrap_state: Dict[str, Any],
        persisted_state: Dict[str, Any],
        runtime_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        reason = self.shutdown_reason or "requested"
        queue_snapshot = persisted_state.get("queue") or {}
        semantic_snapshot = persisted_state.get("semantic_memory") or {}

        return {
            "bootstrap_state": bootstrap_state,
            "runtime_state": runtime_state,
            "completed_cycles": len(self.cycle_logs),
            "cycle_logs": list(self.cycle_logs),
            "shutdown_reason": reason,
            "shutdown_reason_ptbr": MOTIVOS_ENCERRAMENTO_PTBR.get(reason, reason),
            "queue_saved_at": queue_snapshot.get("saved_at"),
            "semantic_entry_count": semantic_snapshot.get("entry_count", 0),
        }

    def _format_cycle_message(self, cycle_log: Dict[str, Any]) -> str:
        return (
            f"[ciclo {cycle_log['cycle_id']}] "
            f"status={cycle_log['status_ptbr']} "
            f"fila={cycle_log['queue_depth']} "
            f"tarefa={cycle_log['selected_task_id'] or 'nenhuma'}"
        )

    def _format_shutdown_message(self, summary: Dict[str, Any]) -> str:
        return (
            f"[encerramento] ciclos={summary['completed_cycles']} "
            f"motivo={summary['shutdown_reason_ptbr']} "
            f"fila={summary['runtime_state']['queue_depth']} "
            f"memoria_semantica={summary['semantic_entry_count']}"
        )

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger(message)


def build_arg_parser() -> argparse.ArgumentParser:
    """Monta o parser de argumentos do entrypoint."""

    parser = argparse.ArgumentParser(description="Executa o loop continuo inicial do JARVIS.")
    parser.add_argument("--sleep-seconds", type=float, default=1.0, help="Espera entre ciclos ativos.")
    parser.add_argument("--idle-sleep-seconds", type=float, default=2.0, help="Espera quando a fila estiver vazia.")
    parser.add_argument("--max-cycles", type=int, default=None, help="Limite opcional de ciclos para execucao.")
    parser.add_argument(
        "--stop-when-idle",
        action="store_true",
        help="Encerra quando o planner encontrar a fila vazia.",
    )
    parser.add_argument(
        "--queue-storage-path",
        type=Path,
        default=None,
        help="Caminho alternativo do arquivo de persistencia da fila.",
    )
    parser.add_argument(
        "--semantic-storage-path",
        type=Path,
        default=None,
        help="Caminho alternativo do arquivo de persistencia da memoria semantica.",
    )
    parser.add_argument(
        "--procedural-storage-path",
        type=Path,
        default=None,
        help="Caminho alternativo do arquivo de persistencia da memoria procedural.",
    )
    parser.add_argument(
        "--goal-storage-path",
        type=Path,
        default=None,
        help="Caminho alternativo do arquivo de persistencia dos objetivos.",
    )
    parser.add_argument(
        "--cognitive-evolution-storage-path",
        type=Path,
        default=None,
        help="Caminho alternativo do arquivo de persistencia da evolucao cognitiva.",
    )
    parser.add_argument(
        "--audit-storage-path",
        type=Path,
        default=None,
        help="Caminho alternativo do arquivo de persistencia da auditoria.",
    )
    parser.add_argument(
        "--device-registry-path",
        type=Path,
        default=None,
        help="Caminho alternativo do arquivo de persistencia do registro de dispositivos.",
    )
    parser.add_argument(
        "--self-defense-report-path",
        type=Path,
        default=None,
        help="Caminho alternativo do relatorio persistente de autodefesa.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Executa o entrypoint do processo continuo."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    deployment_config = JarvisEnvironmentConfig.from_env()

    config = SystemLoopConfig(
        cycle_sleep_seconds=args.sleep_seconds,
        idle_sleep_seconds=args.idle_sleep_seconds,
        max_cycles=args.max_cycles,
        stop_when_idle=args.stop_when_idle,
        queue_storage_path=args.queue_storage_path or deployment_config.queue_storage_path,
        semantic_storage_path=args.semantic_storage_path or deployment_config.semantic_storage_path,
        procedural_storage_path=args.procedural_storage_path or deployment_config.procedural_storage_path,
        goal_storage_path=args.goal_storage_path or deployment_config.goals_storage_path,
        cognitive_evolution_storage_path=(
            args.cognitive_evolution_storage_path or deployment_config.cognitive_evolution_storage_path
        ),
        audit_storage_path=args.audit_storage_path or deployment_config.audit_storage_path,
        device_registry_path=args.device_registry_path or deployment_config.device_registry_path,
        self_defense_report_path=args.self_defense_report_path or deployment_config.self_defense_report_path,
        enable_vital_organs_background=True,
    )
    loop = JarvisSystemLoop(config=config)
    try:
        loop.run()
    finally:
        loop.runtime.shutdown_vital_organs(reason="process_exit")
    return 0


def _build_vital_organs_official_paths(config: SystemLoopConfig) -> Dict[str, Path]:
    """Monta o mapa oficial de stores monitorados pelos orgaos vitais."""

    return {
        "queue_storage_path": Path(config.queue_storage_path),
        "semantic_storage_path": Path(config.semantic_storage_path),
        "procedural_storage_path": Path(config.procedural_storage_path),
        "goals_storage_path": Path(config.goal_storage_path),
        "device_registry_path": Path(config.device_registry_path),
        "cognitive_evolution_storage_path": Path(config.cognitive_evolution_storage_path),
        "audit_storage_path": Path(config.audit_storage_path),
        "self_defense_report_path": Path(config.self_defense_report_path),
    }


def _build_vital_organs_legacy_paths() -> Dict[str, Path]:
    """Retorna os stores legados ainda relevantes para vigilancia estrutural."""

    return {
        "queue_storage_path": LEGACY_QUEUE_STORAGE_PATH,
        "semantic_storage_path": LEGACY_SEMANTIC_STORAGE_PATH,
        "goals_storage_path": LEGACY_GOALS_PATH,
    }


def _resolve_vital_organs_data_dir(
    config: SystemLoopConfig,
    deployment_config: JarvisEnvironmentConfig,
) -> Path:
    """Resolve o diretorio oficial de dados observado pelos orgaos vitais."""

    candidate_parents = {
        Path(config.queue_storage_path).parent.resolve(),
        Path(config.semantic_storage_path).parent.resolve(),
        Path(config.procedural_storage_path).parent.resolve(),
        Path(config.goal_storage_path).parent.resolve(),
        Path(config.device_registry_path).parent.resolve(),
        Path(config.cognitive_evolution_storage_path).parent.resolve(),
        Path(config.audit_storage_path).parent.resolve(),
    }
    if len(candidate_parents) == 1:
        return next(iter(candidate_parents))
    return deployment_config.data_dir


def _resolve_vital_organs_report_path(config: SystemLoopConfig) -> Path:
    """Define o relatorio interno persistente dos orgaos vitais."""

    return Path(config.self_defense_report_path).parent / "vital_organs_status.json"


def _load_queue_storage(task_queue: TaskQueue, logger: Callable[[str], None] | None) -> None:
    task_queue.storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not task_queue.storage_path.exists():
        snapshot = task_queue.save_to_disk()
        _log_message(
            logger,
            f"[bootstrap] fila persistente criada em {task_queue.storage_path} com {snapshot['task_count']} tarefa(s).",
        )
        return

    try:
        snapshot = task_queue.load_from_disk()
    except json.JSONDecodeError:
        backup_path = _backup_corrupted_storage(task_queue.storage_path)
        _log_message(
            logger,
            f"[bootstrap] fila persistente corrompida. Backup salvo em {backup_path}. Reinicializando arquivo limpo.",
        )
        snapshot = task_queue.save_to_disk()

    _log_message(
        logger,
        f"[bootstrap] fila persistente carregada de {task_queue.storage_path} com {snapshot['task_count']} tarefa(s).",
    )


def _load_semantic_storage(
    semantic_memory: SemanticMemory,
    logger: Callable[[str], None] | None,
) -> None:
    semantic_memory.storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not semantic_memory.storage_path.exists():
        snapshot = semantic_memory.snapshot()
        _log_message(
            logger,
            "[bootstrap] memoria semantica criada em {path} com {count} entrada(s).".format(
                path=semantic_memory.storage_path,
                count=snapshot["entry_count"],
            ),
        )
        return

    try:
        snapshot = semantic_memory.load_snapshot()
    except json.JSONDecodeError:
        backup_path = _backup_corrupted_storage(semantic_memory.storage_path)
        _log_message(
            logger,
            "[bootstrap] memoria semantica corrompida. Backup salvo em {path}. Reinicializando armazenamento.".format(
                path=backup_path,
            ),
        )
        semantic_memory.entries = []
        semantic_memory.facts = {}
        snapshot = semantic_memory.snapshot()

    _log_message(
        logger,
        "[bootstrap] memoria semantica carregada de {path} com {count} entrada(s).".format(
            path=semantic_memory.storage_path,
            count=snapshot["entry_count"],
        ),
    )


def _load_procedural_storage(
    procedural_memory: ProceduralMemory,
    logger: Callable[[str], None] | None,
) -> None:
    if procedural_memory.storage_path is None:
        return

    procedural_memory.storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not procedural_memory.storage_path.exists():
        snapshot = procedural_memory.snapshot()
        _log_message(
            logger,
            "[bootstrap] memoria procedural criada em {path} com {count} procedimento(s).".format(
                path=procedural_memory.storage_path,
                count=snapshot["procedure_count"],
            ),
        )
        return

    try:
        snapshot = procedural_memory.load_snapshot()
    except json.JSONDecodeError:
        backup_path = _backup_corrupted_storage(procedural_memory.storage_path)
        _log_message(
            logger,
            "[bootstrap] memoria procedural corrompida. Backup salvo em {path}. Reinicializando armazenamento.".format(
                path=backup_path,
            ),
        )
        procedural_memory.procedures = {}
        snapshot = procedural_memory.snapshot()

    _log_message(
        logger,
        "[bootstrap] memoria procedural carregada de {path} com {count} procedimento(s).".format(
            path=procedural_memory.storage_path,
            count=snapshot["procedure_count"],
        ),
    )


def _load_cognitive_evolution_storage(
    cognitive_tracker: CognitiveEvolutionTracker,
    logger: Callable[[str], None] | None,
) -> None:
    if cognitive_tracker.storage_path is None:
        return

    cognitive_tracker.storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not cognitive_tracker.storage_path.exists():
        snapshot = cognitive_tracker.snapshot()
        _log_message(
            logger,
            "[bootstrap] evolucao cognitiva criada em {path} com {count} evento(s).".format(
                path=cognitive_tracker.storage_path,
                count=snapshot["event_count"],
            ),
        )
        return

    try:
        snapshot = cognitive_tracker.load_snapshot()
    except json.JSONDecodeError:
        backup_path = _backup_corrupted_storage(cognitive_tracker.storage_path)
        _log_message(
            logger,
            "[bootstrap] evolucao cognitiva corrompida. Backup salvo em {path}. Reinicializando armazenamento.".format(
                path=backup_path,
            ),
        )
        cognitive_tracker.events = []
        cognitive_tracker.last_updated_at = None
        snapshot = cognitive_tracker.snapshot()

    _log_message(
        logger,
        "[bootstrap] evolucao cognitiva carregada de {path} com {count} evento(s).".format(
            path=cognitive_tracker.storage_path,
            count=snapshot["event_count"],
        ),
    )


def _load_goal_manager(
    storage_path: Path,
    logger: Callable[[str], None] | None,
):
    from intent_layer.goal_manager import GoalManager

    storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not storage_path.exists():
        goal_manager = GoalManager(storage_path=storage_path)
        goal_manager.save()
        _log_message(logger, f"[bootstrap] camada de objetivos criada em {storage_path}.")
        return goal_manager

    try:
        goal_manager = GoalManager(storage_path=storage_path)
    except json.JSONDecodeError:
        backup_path = _backup_corrupted_storage(storage_path)
        _log_message(
            logger,
            f"[bootstrap] objetivos corrompidos. Backup salvo em {backup_path}. Reinicializando arquivo limpo.",
        )
        goal_manager = GoalManager(storage_path=storage_path)
        goal_manager.save()

    _log_message(
        logger,
        "[bootstrap] objetivos carregados de {path} com {count} objetivo(s) ativo(s).".format(
            path=storage_path,
            count=len(goal_manager.list_active_goals()),
        ),
    )
    return goal_manager


def _load_device_registry(
    storage_path: Path,
    logger: Callable[[str], None] | None,
):
    from device.device_registry import DeviceRegistry

    storage_path.parent.mkdir(parents=True, exist_ok=True)
    registry = DeviceRegistry(storage_path=storage_path)
    if not storage_path.exists():
        snapshot = registry.save()
        _log_message(
            logger,
            "[bootstrap] registro de dispositivos criado em {path} com {count} dispositivo(s).".format(
                path=storage_path,
                count=snapshot["device_count"],
            ),
        )
        return registry

    _log_message(
        logger,
        "[bootstrap] registro de dispositivos carregado de {path} com {count} dispositivo(s).".format(
            path=storage_path,
            count=registry.snapshot()["device_count"],
        ),
    )
    return registry


def _load_audit_storage(
    audit_logger: AuditLogger,
    logger: Callable[[str], None] | None,
) -> None:
    audit_logger.storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not audit_logger.storage_path.exists():
        snapshot = audit_logger.save_to_disk()
        _log_message(
            logger,
            "[bootstrap] auditoria persistente criada em {path} com {count} evento(s).".format(
                path=audit_logger.storage_path,
                count=snapshot["entry_count"],
            ),
        )
        audit_logger.auto_persist_on_change(True)
        return

    try:
        snapshot = audit_logger.load_snapshot()
    except json.JSONDecodeError:
        backup_path = _backup_corrupted_storage(audit_logger.storage_path)
        _log_message(
            logger,
            "[bootstrap] auditoria corrompida. Backup salvo em {path}. Reinicializando armazenamento.".format(
                path=backup_path,
            ),
        )
        audit_logger.entries = []
        snapshot = audit_logger.save_to_disk()

    audit_logger.auto_persist_on_change(True)
    _log_message(
        logger,
        "[bootstrap] auditoria persistente carregada de {path} com {count} evento(s).".format(
            path=audit_logger.storage_path,
            count=snapshot["entry_count"],
        ),
    )


def _backup_corrupted_storage(storage_path: Path) -> Path:
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_path = storage_path.with_name(f"{storage_path.stem}.corrompido-{suffix}{storage_path.suffix}")
    storage_path.rename(backup_path)
    return backup_path


def _log_message(logger: Callable[[str], None] | None, message: str) -> None:
    if logger is not None:
        logger(message)


if __name__ == "__main__":
    raise SystemExit(main())
