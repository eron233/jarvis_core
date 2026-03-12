"""Entrypoint do processo continuo inicial do JARVIS."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import signal
import time
from typing import Any, Callable, Dict, List, Optional

from executive_planner.queue import TaskQueue
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime

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


def bootstrap_runtime(
    runtime: Optional[InternalAgentRuntime] = None,
    config: Optional[SystemLoopConfig] = None,
) -> tuple[InternalAgentRuntime, Dict[str, Any]]:
    """Prepara o runtime com os caminhos de persistencia desejados."""

    runtime = runtime or InternalAgentRuntime()
    config = config or SystemLoopConfig()

    if config.queue_storage_path is not None:
        runtime.task_queue = TaskQueue(storage_path=config.queue_storage_path)

    episodic_memory = runtime.memory.get("episodic") if runtime.memory else None
    procedural_memory = runtime.memory.get("procedural") if runtime.memory else None
    semantic_memory = runtime.memory.get("semantic") if runtime.memory else None

    if episodic_memory is None:
        episodic_memory = EpisodicMemory()

    if procedural_memory is None:
        procedural_memory = ProceduralMemory()

    if semantic_memory is None or config.semantic_storage_path is not None:
        semantic_path = config.semantic_storage_path or getattr(semantic_memory, "storage_path", None)
        semantic_memory = SemanticMemory(storage_path=semantic_path) if semantic_path else SemanticMemory()

    runtime.memory = {
        "episodic": episodic_memory,
        "semantic": semantic_memory,
        "procedural": procedural_memory,
    }

    return runtime, runtime.bootstrap()


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

        self.runtime, state = bootstrap_runtime(runtime=self.runtime, config=self.config)

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
            cycle_result = self.runtime.run_planner_cycle()
            runtime_state = self.runtime.describe_state()
            cycle_log = self._record_cycle(cycle_id=cycle_id, cycle_result=cycle_result, runtime_state=runtime_state)

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
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Executa o entrypoint do processo continuo."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    config = SystemLoopConfig(
        cycle_sleep_seconds=args.sleep_seconds,
        idle_sleep_seconds=args.idle_sleep_seconds,
        max_cycles=args.max_cycles,
        stop_when_idle=args.stop_when_idle,
        queue_storage_path=args.queue_storage_path,
        semantic_storage_path=args.semantic_storage_path,
    )
    loop = JarvisSystemLoop(config=config)
    loop.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
