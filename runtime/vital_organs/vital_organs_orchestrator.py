"""
JARVIS - Orquestrador de Orgaos Vitais

Responsavel por:
- inicializar os orgaos vitais internos do runtime
- executar ciclos silenciosos de monitoramento em background
- persistir um relatorio interno apenas para auditoria tecnica

Integracoes principais:
- runtime.internal_agent_runtime
- runtime.vital_organs.*
- runtime.server
- main
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Dict

from runtime.vital_organs.autonomous_sync_engine import AutonomousSyncConfig, AutonomousSyncEngine
from runtime.vital_organs.failure_prevention_engine import FailurePreventionEngine
from runtime.vital_organs.runtime_hygiene_engine import RuntimeHygieneEngine
from runtime.vital_organs.self_optimization_core import SelfOptimizationCore
from runtime.vital_organs.structural_integrity_monitor import StructuralIntegrityMonitor


LOGGER = logging.getLogger("jarvis.vital_organs")


@dataclass
class VitalOrgansOrchestrator:
    """Coordena os orgaos vitais internos como uma camada nativa do runtime."""

    project_root: Path
    report_path: Path
    official_paths: Dict[str, Path]
    legacy_paths: Dict[str, Path]
    official_data_dir: Path
    official_reports_dir: Path
    cycle_interval_seconds: float
    idle_sleep_seconds: float
    background_enabled: bool = False
    logger: logging.Logger = field(default_factory=lambda: LOGGER)
    _thread: Thread | None = field(default=None, init=False, repr=False)
    _stop_event: Event = field(default_factory=Event, init=False, repr=False)
    _write_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _last_report_signature: str | None = field(default=None, init=False, repr=False)
    _last_report: Dict[str, Any] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root)
        self.report_path = Path(self.report_path)
        self.official_data_dir = Path(self.official_data_dir)
        self.official_reports_dir = Path(self.official_reports_dir)
        self.official_paths = {label: Path(path) for label, path in self.official_paths.items()}
        self.legacy_paths = {label: Path(path) for label, path in self.legacy_paths.items()}
        self.structural_integrity_monitor = StructuralIntegrityMonitor(
            project_root=self.project_root,
            official_paths=self.official_paths,
            legacy_paths=self.legacy_paths,
        )
        self.self_optimization_core = SelfOptimizationCore(
            cycle_sleep_seconds=self.cycle_interval_seconds,
            idle_sleep_seconds=self.idle_sleep_seconds,
        )
        self.runtime_hygiene_engine = RuntimeHygieneEngine(
            project_root=self.project_root,
            official_data_dir=self.official_data_dir,
            official_reports_dir=self.official_reports_dir,
            operational_paths=self.official_paths,
        )
        self.failure_prevention_engine = FailurePreventionEngine(critical_paths=self.official_paths)
        self.autonomous_sync_engine = AutonomousSyncEngine(
            project_root=self.project_root,
            config=AutonomousSyncConfig.from_env(),
        )

    def reconfigure(
        self,
        *,
        cycle_interval_seconds: float,
        idle_sleep_seconds: float,
        background_enabled: bool,
    ) -> None:
        """Atualiza parametros leves sem recriar o orquestrador."""

        self.cycle_interval_seconds = cycle_interval_seconds
        self.idle_sleep_seconds = idle_sleep_seconds
        self.background_enabled = background_enabled
        self.self_optimization_core.cycle_sleep_seconds = cycle_interval_seconds
        self.self_optimization_core.idle_sleep_seconds = idle_sleep_seconds

    def start(self, runtime: Any) -> None:
        """Inicia a execucao continua dos orgaos vitais quando habilitada."""

        if not self.background_enabled:
            return
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = Thread(
            target=self._run_forever,
            args=(runtime,),
            name="jarvis-vital-organs",
            daemon=True,
        )
        self._thread.start()
        self.logger.info("[vital_organs] orgaos vitais iniciados em background.")

    def stop(self, reason: str = "requested", join_timeout: float = 5.0) -> None:
        """Solicita a parada do ciclo interno dos orgaos vitais."""

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=join_timeout)
            self._thread = None
        self.logger.info("[vital_organs] orgaos vitais encerrados. motivo=%s", reason)

    def run_cycle(self, runtime: Any) -> Dict[str, Any]:
        """Executa uma rodada sincronizada dos orgaos vitais."""

        structural_report = self.structural_integrity_monitor.run(runtime)
        optimization_report = self.self_optimization_core.run(runtime)
        hygiene_report = self.runtime_hygiene_engine.run(runtime)
        prevention_report = self.failure_prevention_engine.run(runtime)
        sync_report = self.autonomous_sync_engine.run(runtime)

        report = {
            "version": "0.1.0",
            "generated_at": runtime._utc_now(),
            "project_root": str(self.project_root),
            "background_enabled": self.background_enabled,
            "cycle_interval_seconds": self._effective_interval_seconds(),
            "official_data_dir": str(self.official_data_dir),
            "official_reports_dir": str(self.official_reports_dir),
            "summary": self._build_summary(
                structural_report=structural_report,
                optimization_report=optimization_report,
                hygiene_report=hygiene_report,
                prevention_report=prevention_report,
                sync_report=sync_report,
            ),
            "organs": {
                "structural_integrity_monitor": structural_report,
                "self_optimization_core": optimization_report,
                "runtime_hygiene_engine": hygiene_report,
                "failure_prevention_engine": prevention_report,
                "autonomous_sync_engine": sync_report,
            },
        }

        self._persist_report_if_changed(report)
        self._last_report = deepcopy(report)
        return deepcopy(report)

    def snapshot(self) -> Dict[str, Any] | None:
        """Retorna o ultimo relatorio interno conhecido."""

        if self._last_report is None:
            return None
        return deepcopy(self._last_report)

    def _run_forever(self, runtime: Any) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_cycle(runtime)
            except Exception as exc:  # pragma: no cover - resiliencia defensiva em background
                self.logger.exception("[vital_organs] falha no ciclo interno: %s", exc)
            self._stop_event.wait(self._effective_interval_seconds())

    def _persist_report_if_changed(self, report: Dict[str, Any]) -> None:
        payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        if payload == self._last_report_signature:
            return

        with self._write_lock:
            if payload == self._last_report_signature:
                return
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.report_path.with_name(f"{self.report_path.name}.tmp")
            temp_path.write_text(payload, encoding="utf-8")
            os.replace(temp_path, self.report_path)
            self._last_report_signature = payload

    def _build_summary(
        self,
        *,
        structural_report: Dict[str, Any],
        optimization_report: Dict[str, Any],
        hygiene_report: Dict[str, Any],
        prevention_report: Dict[str, Any],
        sync_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        reports = [
            structural_report,
            optimization_report,
            hygiene_report,
            prevention_report,
            sync_report,
        ]
        statuses = [report["status"] for report in reports]
        if "critico" in statuses:
            overall_status = "critico"
        elif "atencao" in statuses:
            overall_status = "atencao"
        else:
            overall_status = "saudavel"

        findings_total = 0
        auto_actions_total = 0
        for report in reports:
            findings_total += len(report.get("violacoes", []))
            findings_total += len(report.get("achados", []))
            auto_actions_total += len(report.get("acoes_aplicadas", []))

        return {
            "status_geral": overall_status,
            "orgaos_ativos": 5,
            "total_achados": findings_total,
            "total_acoes_automaticas": auto_actions_total,
            "thread_em_execucao": self._thread is not None and self._thread.is_alive(),
        }

    def _effective_interval_seconds(self) -> float:
        return max(self.cycle_interval_seconds, self.idle_sleep_seconds, 15.0)
