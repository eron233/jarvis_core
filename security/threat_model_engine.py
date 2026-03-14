"""Motor interno de modelagem de ameaca do JARVIS."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List

from security.security_knowledge_core import SecurityKnowledgeCore

RISK_LEVELS = ("baixo", "medio", "alto", "critico")

ASSET_TEMPLATES: List[Dict[str, Any]] = [
    {
        "asset_id": "semantic_memory",
        "nome": "Memoria semantica",
        "categoria": "memoria",
        "criticidade_base": 4,
        "superficies": ["persisted_files", "startup_shutdown", "docker_volumes"],
        "impactos": {
            "confidencialidade": "medio",
            "integridade": "alto",
            "disponibilidade": "alto",
            "rastreabilidade": "medio",
            "continuidade": "alto",
        },
    },
    {
        "asset_id": "task_queue",
        "nome": "Fila de tarefas",
        "categoria": "execucao",
        "criticidade_base": 4,
        "superficies": ["persisted_files", "api_http", "startup_shutdown", "docker_volumes"],
        "impactos": {
            "confidencialidade": "baixo",
            "integridade": "alto",
            "disponibilidade": "alto",
            "rastreabilidade": "medio",
            "continuidade": "alto",
        },
    },
    {
        "asset_id": "audit_log",
        "nome": "Auditoria interna",
        "categoria": "observabilidade",
        "criticidade_base": 5,
        "superficies": ["operational_logs", "startup_shutdown", "authentication_gate"],
        "impactos": {
            "confidencialidade": "medio",
            "integridade": "alto",
            "disponibilidade": "medio",
            "rastreabilidade": "critico",
            "continuidade": "medio",
        },
    },
    {
        "asset_id": "api_service",
        "nome": "API HTTP",
        "categoria": "aplicacao",
        "criticidade_base": 5,
        "superficies": ["api_http", "environment_variables", "authentication_gate"],
        "impactos": {
            "confidencialidade": "alto",
            "integridade": "alto",
            "disponibilidade": "alto",
            "rastreabilidade": "alto",
            "continuidade": "alto",
        },
    },
    {
        "asset_id": "dashboard",
        "nome": "Painel web",
        "categoria": "aplicacao",
        "criticidade_base": 4,
        "superficies": ["dashboard_web", "authentication_gate", "api_http"],
        "impactos": {
            "confidencialidade": "alto",
            "integridade": "medio",
            "disponibilidade": "medio",
            "rastreabilidade": "medio",
            "continuidade": "medio",
        },
    },
    {
        "asset_id": "environment_config",
        "nome": "Configuracao de ambiente",
        "categoria": "configuracao",
        "criticidade_base": 5,
        "superficies": ["environment_variables", "startup_shutdown", "docker_volumes"],
        "impactos": {
            "confidencialidade": "alto",
            "integridade": "alto",
            "disponibilidade": "alto",
            "rastreabilidade": "medio",
            "continuidade": "alto",
        },
    },
    {
        "asset_id": "access_token",
        "nome": "Token de acesso",
        "categoria": "identidade",
        "criticidade_base": 5,
        "superficies": ["environment_variables", "authentication_gate"],
        "impactos": {
            "confidencialidade": "critico",
            "integridade": "alto",
            "disponibilidade": "medio",
            "rastreabilidade": "alto",
            "continuidade": "alto",
        },
    },
    {
        "asset_id": "trusted_device",
        "nome": "Dispositivo confiavel",
        "categoria": "identidade",
        "criticidade_base": 4,
        "superficies": ["authentication_gate", "dashboard_web", "environment_variables"],
        "impactos": {
            "confidencialidade": "alto",
            "integridade": "alto",
            "disponibilidade": "medio",
            "rastreabilidade": "alto",
            "continuidade": "medio",
        },
    },
    {
        "asset_id": "goal_state",
        "nome": "Estado de objetivos",
        "categoria": "planejamento",
        "criticidade_base": 3,
        "superficies": ["persisted_files", "api_http", "startup_shutdown"],
        "impactos": {
            "confidencialidade": "baixo",
            "integridade": "alto",
            "disponibilidade": "medio",
            "rastreabilidade": "medio",
            "continuidade": "alto",
        },
    },
    {
        "asset_id": "runtime_state",
        "nome": "Estado operacional do runtime",
        "categoria": "execucao",
        "criticidade_base": 5,
        "superficies": ["startup_shutdown", "api_http", "operational_logs"],
        "impactos": {
            "confidencialidade": "medio",
            "integridade": "alto",
            "disponibilidade": "critico",
            "rastreabilidade": "alto",
            "continuidade": "critico",
        },
    },
]

SURFACE_TEMPLATES: List[Dict[str, Any]] = [
    {
        "surface_id": "api_http",
        "nome": "API HTTP",
        "exposicao_base": 4,
        "descricao": "Interface principal de operacao remota do sistema.",
    },
    {
        "surface_id": "dashboard_web",
        "nome": "Painel web",
        "exposicao_base": 3,
        "descricao": "Camada web mobile-first servida pela API.",
    },
    {
        "surface_id": "persisted_files",
        "nome": "Arquivos persistentes",
        "exposicao_base": 3,
        "descricao": "Fila, memoria e objetivos salvos em disco.",
    },
    {
        "surface_id": "environment_variables",
        "nome": "Variaveis de ambiente",
        "exposicao_base": 4,
        "descricao": "Segredos, host, porta e configuracoes sensiveis.",
    },
    {
        "surface_id": "startup_shutdown",
        "nome": "Startup e shutdown",
        "exposicao_base": 3,
        "descricao": "Bootstrap, retomada, persistencia e encerramento do processo.",
    },
    {
        "surface_id": "docker_volumes",
        "nome": "Volumes Docker",
        "exposicao_base": 2,
        "descricao": "Camada de persistencia montada no deploy.",
    },
    {
        "surface_id": "operational_logs",
        "nome": "Logs operacionais",
        "exposicao_base": 2,
        "descricao": "Rastros de startup, loop, healthcheck e encerramento.",
    },
    {
        "surface_id": "authentication_gate",
        "nome": "Autenticacao",
        "exposicao_base": 4,
        "descricao": "Validacao de token, device trust e sessao do painel.",
    },
]

CONSEQUENCE_CATALOG: List[Dict[str, Any]] = [
    {"tipo": "confidencialidade", "descricao": "Risco de acesso indevido a dados ou segredos."},
    {"tipo": "integridade", "descricao": "Risco de alteracao indevida de estado ou configuracao."},
    {"tipo": "disponibilidade", "descricao": "Risco de indisponibilidade operacional do sistema."},
    {"tipo": "rastreabilidade", "descricao": "Risco de perda de evidencias, auditoria ou explicabilidade."},
    {"tipo": "continuidade", "descricao": "Risco de perda de retomada segura e persistencia."},
]

DEPENDENCY_TEMPLATES: List[Dict[str, str]] = [
    {"dependency_id": "runtime", "nome": "Runtime"},
    {"dependency_id": "planner", "nome": "Planner"},
    {"dependency_id": "queue", "nome": "Fila"},
    {"dependency_id": "memory", "nome": "Memoria"},
    {"dependency_id": "api", "nome": "API"},
    {"dependency_id": "authentication", "nome": "Autenticacao"},
    {"dependency_id": "persistence", "nome": "Persistencia"},
]


@dataclass
class ThreatModelEngine:
    """Gera um modelo de ameaca interno com base no estado atual do JARVIS."""

    knowledge_core: SecurityKnowledgeCore = field(default_factory=SecurityKnowledgeCore)

    def build_asset_inventory(self) -> List[Dict[str, Any]]:
        """Retorna o inventario de ativos protegidos do sistema."""

        return [deepcopy(asset) for asset in ASSET_TEMPLATES]

    def build_surface_map(self, environment_report: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """Retorna as superficies de contato do sistema atual."""

        surfaces = [deepcopy(surface) for surface in SURFACE_TEMPLATES]
        auth_config = (environment_report or {}).get("autenticacao_configurada", {})
        dashboard_active = bool((environment_report or {}).get("painel_ativo", True))

        for surface in surfaces:
            if surface["surface_id"] == "authentication_gate":
                surface["protegida"] = bool(
                    auth_config.get("token_configurado") and auth_config.get("dispositivo_confiavel_configurado")
                )
            elif surface["surface_id"] == "dashboard_web":
                surface["ativa"] = dashboard_active
            else:
                surface["protegida"] = surface["surface_id"] not in {"api_http", "persisted_files", "operational_logs"}
        return surfaces

    def build_dependency_map(
        self,
        runtime_state: Dict[str, Any] | None = None,
        health_report: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """Retorna as dependencias criticas e o estado observado de cada uma."""

        runtime_state = runtime_state or {}
        health_report = health_report or {}
        dependency_health = {
            "runtime": runtime_state.get("status") == "initialized",
            "planner": health_report.get("planner_acoplado", runtime_state.get("planner") is not None),
            "queue": health_report.get("fila_carregada", runtime_state.get("queue_depth", 0) >= 0),
            "memory": health_report.get("memoria_carregada", bool(runtime_state.get("memory_modules"))),
            "api": health_report.get("api_ativa", True),
            "authentication": health_report.get("configuracao_minima_valida", False),
            "persistence": bool(
                runtime_state.get("queue_store")
                and runtime_state.get("semantic_store")
                and runtime_state.get("goal_store")
            ),
        }

        dependencies: List[Dict[str, Any]] = []
        for dependency in DEPENDENCY_TEMPLATES:
            dependencies.append(
                {
                    **dependency,
                    "estado": "saudavel" if dependency_health[dependency["dependency_id"]] else "degradado",
                }
            )
        return dependencies

    def classify_risks(
        self,
        runtime_state: Dict[str, Any] | None = None,
        health_report: Dict[str, Any] | None = None,
        environment_report: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """Classifica o risco por ativo e superficie em niveis baixos a criticos."""

        runtime_state = runtime_state or {}
        health_report = health_report or {}
        environment_report = environment_report or {}
        surfaces_by_id = {
            surface["surface_id"]: surface
            for surface in self.build_surface_map(environment_report=environment_report)
        }
        auth_config = environment_report.get("autenticacao_configurada", {})

        risks: List[Dict[str, Any]] = []
        for asset in self.build_asset_inventory():
            max_exposure = max(surfaces_by_id[surface_id]["exposicao_base"] for surface_id in asset["superficies"])
            score = asset["criticidade_base"] + max_exposure

            if asset["asset_id"] in {"access_token", "trusted_device", "api_service", "dashboard"}:
                if not auth_config.get("token_configurado", False):
                    score += 2
                if not auth_config.get("dispositivo_confiavel_configurado", False):
                    score += 2

            if asset["asset_id"] == "runtime_state" and runtime_state.get("status") != "initialized":
                score += 2
            if asset["asset_id"] == "task_queue" and not health_report.get("fila_carregada", False):
                score += 2
            if asset["asset_id"] == "semantic_memory" and not health_report.get("memoria_carregada", False):
                score += 2
            if asset["asset_id"] == "goal_state" and not health_report.get("objetivos_carregados", False):
                score += 2
            if asset["asset_id"] == "audit_log" and not health_report.get("configuracao_minima_valida", False):
                score += 1

            risk_level = self._score_to_level(score)
            risks.append(
                {
                    "asset_id": asset["asset_id"],
                    "nome": asset["nome"],
                    "nivel_risco": risk_level,
                    "score": score,
                    "superficies_relacionadas": list(asset["superficies"]),
                    "impactos": deepcopy(asset["impactos"]),
                    "consequencia_dominante": self._dominant_consequence(asset["impactos"]),
                }
            )

        risks.sort(key=lambda item: (-item["score"], item["asset_id"]))
        return risks

    def build_threat_model(
        self,
        runtime_state: Dict[str, Any] | None = None,
        health_report: Dict[str, Any] | None = None,
        environment_report: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Gera o modelo de ameaca interno do estado atual do JARVIS."""

        runtime_state = runtime_state or {}
        health_report = health_report or {}
        environment_report = environment_report or {}
        assets = self.build_asset_inventory()
        surfaces = self.build_surface_map(environment_report=environment_report)
        dependencies = self.build_dependency_map(runtime_state=runtime_state, health_report=health_report)
        risks = self.classify_risks(
            runtime_state=runtime_state,
            health_report=health_report,
            environment_report=environment_report,
        )
        risk_summary = self._summarize_risks(risks)

        return {
            "mensagem": "Modelo de ameaca interno do JARVIS gerado com sucesso.",
            "inventario_de_ativos": assets,
            "mapa_de_superficies": surfaces,
            "consequencias_de_falha": deepcopy(CONSEQUENCE_CATALOG),
            "dependencias_criticas": dependencies,
            "classificacao_de_risco": risks,
            "resumo_ptbr": {
                "risco_geral": risk_summary["risco_geral"],
                "total_ativos": len(assets),
                "total_superficies": len(surfaces),
                "ativos_criticos": risk_summary["critico"],
                "ativos_altos": risk_summary["alto"],
                "ativos_medios": risk_summary["medio"],
                "ativos_baixos": risk_summary["baixo"],
                "top_riscos": risks[:3],
            },
            "dominios_defensivos_relacionados": self.knowledge_core.list_domains(),
        }

    @staticmethod
    def _score_to_level(score: int) -> str:
        if score >= 9:
            return "critico"
        if score >= 7:
            return "alto"
        if score >= 5:
            return "medio"
        return "baixo"

    @staticmethod
    def _dominant_consequence(impactos: Dict[str, str]) -> str:
        impact_rank = {"baixo": 1, "medio": 2, "alto": 3, "critico": 4}
        return max(impactos, key=lambda item: impact_rank.get(impactos[item], 0))

    @staticmethod
    def _summarize_risks(risks: List[Dict[str, Any]]) -> Dict[str, Any]:
        counts = {level: 0 for level in RISK_LEVELS}
        for risk in risks:
            counts[risk["nivel_risco"]] += 1

        if counts["critico"] > 0:
            counts["risco_geral"] = "critico"
        elif counts["alto"] > 0:
            counts["risco_geral"] = "alto"
        elif counts["medio"] > 0:
            counts["risco_geral"] = "medio"
        else:
            counts["risco_geral"] = "baixo"
        return counts
