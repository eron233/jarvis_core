"""
JARVIS - Orgaos Vitais do Runtime

Responsavel por:
- agrupar monitores internos de estabilidade e higiene operacional
- coordenar verificacoes silenciosas de integridade do runtime
- manter relatorios internos sem expor essa camada ao usuario final

Integracoes principais:
- runtime.internal_agent_runtime
- runtime.server
- main
"""

from runtime.vital_organs.failure_prevention_engine import FailurePreventionEngine
from runtime.vital_organs.autonomous_sync_engine import AutonomousSyncConfig, AutonomousSyncEngine
from runtime.vital_organs.runtime_hygiene_engine import RuntimeHygieneEngine
from runtime.vital_organs.self_optimization_core import SelfOptimizationCore
from runtime.vital_organs.structural_integrity_monitor import StructuralIntegrityMonitor
from runtime.vital_organs.vital_organs_orchestrator import VitalOrgansOrchestrator

__all__ = [
    "AutonomousSyncConfig",
    "AutonomousSyncEngine",
    "FailurePreventionEngine",
    "RuntimeHygieneEngine",
    "SelfOptimizationCore",
    "StructuralIntegrityMonitor",
    "VitalOrgansOrchestrator",
]
