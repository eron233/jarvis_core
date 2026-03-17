"""
JARVIS - Monitor de Integridade Estrutural

Responsavel por:
- comparar configuracao declarada com o estado real do runtime
- detectar stores legados, caminhos duplicados e defaults silenciosos
- produzir violacoes estruturais internas para auditoria tecnica

Integracoes principais:
- runtime.internal_agent_runtime
- runtime.system_config
- executive_planner.queue
- memory_system.semantic_memory
- intent_layer.goal_manager
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class StructuralIntegrityMonitor:
    """Monitora coerencia entre runtime, configuracao oficial e stores legados."""

    project_root: Path
    official_paths: Dict[str, Path]
    legacy_paths: Dict[str, Path]

    def run(self, runtime: Any) -> Dict[str, Any]:
        """Executa uma rodada de verificacao estrutural silenciosa."""

        runtime_state = runtime.describe_state()
        runtime_paths = {
            "queue_storage_path": self._as_path(runtime_state.get("queue_store")),
            "semantic_storage_path": self._as_path(runtime_state.get("semantic_store")),
            "procedural_storage_path": self._as_path(runtime_state.get("procedural_store")),
            "goals_storage_path": self._as_path(runtime_state.get("goal_store")),
            "device_registry_path": self._as_path(runtime_state.get("device_registry_store")),
            "audit_storage_path": self._as_path(runtime_state.get("audit_store")),
            "cognitive_evolution_storage_path": self._as_path(runtime_state.get("cognitive_evolution_store")),
            "self_defense_report_path": self._as_path(runtime_state.get("self_defense_report_path")),
        }

        violations: List[Dict[str, Any]] = []

        for label, expected_path in self.official_paths.items():
            actual_path = runtime_paths.get(label)
            if actual_path is None:
                violations.append(
                    self._violation(
                        violation_id=f"{label}_missing_runtime_path",
                        severity="high",
                        kind="runtime_path_missing",
                        message=f"O runtime nao expos o caminho real de {label}.",
                        expected_path=expected_path,
                    )
                )
                continue

            if actual_path != expected_path:
                violations.append(
                    self._violation(
                        violation_id=f"{label}_mismatch",
                        severity="high",
                        kind="runtime_path_mismatch",
                        message=f"O runtime esta usando {actual_path} em vez do caminho oficial {expected_path}.",
                        expected_path=expected_path,
                        actual_path=actual_path,
                    )
                )

        path_index: Dict[str, List[str]] = {}
        for label, path in self.official_paths.items():
            normalized = str(path.resolve())
            path_index.setdefault(normalized, []).append(label)

        for normalized_path, labels in path_index.items():
            if len(labels) <= 1:
                continue
            violations.append(
                self._violation(
                    violation_id=f"duplicated_store_{len(violations) + 1}",
                    severity="medium",
                    kind="duplicated_store_path",
                    message=(
                        "Mais de uma responsabilidade estrutural aponta para o mesmo arquivo persistente: "
                        + ", ".join(labels)
                    ),
                    actual_path=Path(normalized_path),
                    labels=labels,
                )
            )

        for label, legacy_path in self.legacy_paths.items():
            if not legacy_path.exists():
                continue
            violations.append(
                self._violation(
                    violation_id=f"{label}_legacy_store_present",
                    severity="medium",
                    kind="legacy_store_present",
                    message=f"Store legado ainda presente em {legacy_path}.",
                    actual_path=legacy_path,
                )
            )

        overall_status = "saudavel"
        if any(item["severity"] == "high" for item in violations):
            overall_status = "critico"
        elif violations:
            overall_status = "atencao"

        return {
            "organ_id": "structural_integrity_monitor",
            "status": overall_status,
            "executado_em": runtime._utc_now(),
            "violacoes": violations,
            "resumo": {
                "total_violacoes": len(violations),
                "stores_oficiais": {label: str(path) for label, path in self.official_paths.items()},
                "stores_legados_monitorados": {label: str(path) for label, path in self.legacy_paths.items()},
            },
        }

    @staticmethod
    def _as_path(value: Any) -> Path | None:
        if value in (None, ""):
            return None
        return Path(str(value)).resolve()

    @staticmethod
    def _violation(
        *,
        violation_id: str,
        severity: str,
        kind: str,
        message: str,
        expected_path: Path | None = None,
        actual_path: Path | None = None,
        labels: List[str] | None = None,
    ) -> Dict[str, Any]:
        return {
            "violation_id": violation_id,
            "severity": severity,
            "kind": kind,
            "message": message,
            "expected_path": str(expected_path) if expected_path is not None else None,
            "actual_path": str(actual_path) if actual_path is not None else None,
            "labels": list(labels or []),
        }
