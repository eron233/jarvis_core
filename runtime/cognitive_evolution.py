"""
JARVIS - Mapa Evolutivo Cognitivo

Responsavel por:
- registrar eventos de crescimento cognitivo do Jarvis
- persistir historico de evolucao em arquivo JSON
- resumir aprendizado acumulado por regiao cerebral simulada
- gerar payloads para visualizacao no brain avatar e para analise interna

Integracoes principais:
- runtime.internal_agent_runtime
- interface.api.app
- interface.brain_avatar
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

#
# JARVIS_MEMORY_SYSTEM
# JARVIS_CORE_COMPONENT
# ==================================================
# BLOCO: Constantes estruturais do mapa evolutivo
# ==================================================

DEFAULT_STORAGE_PATH = Path(__file__).resolve().parents[1] / "data" / "cognitive_evolution_history.json"

EVENT_METADATA = {
    "EVENT_NEW_KNOWLEDGE": {
        "tipo_aprendizado": "novo_conhecimento",
        "cor": "#d4af37",
        "descricao": "Aprendizado novo consolidado na memoria do sistema.",
    },
    "EVENT_PATTERN_DISCOVERED": {
        "tipo_aprendizado": "padrao_descoberto",
        "cor": "#fff7dd",
        "descricao": "Padrao reutilizavel identificado a partir de execucoes anteriores.",
    },
    "EVENT_SKILL_IMPROVED": {
        "tipo_aprendizado": "habilidade_reforcada",
        "cor": "#ffffff",
        "descricao": "Heuristica ou habilidade operacional fortalecida.",
    },
    "EVENT_MEMORY_CONSOLIDATED": {
        "tipo_aprendizado": "memoria_consolidada",
        "cor": "#e9d8a6",
        "descricao": "Informacao reorganizada e consolidada no historico cognitivo.",
    },
    "EVENT_NETWORK_RESTRUCTURE": {
        "tipo_aprendizado": "reestruturacao_de_rede",
        "cor": "#4cc9f0",
        "descricao": "Reorganizacao da topologia cognitiva ativa.",
    },
}

LEVEL_WINDOWS = {
    "recente": timedelta(hours=24),
    "semanal": timedelta(days=7),
    "mensal": timedelta(days=30),
    "historica": None,
}

LEVEL_LABELS_PTBR = {
    "recente": "Nivel 1 - evolucao recente",
    "semanal": "Nivel 2 - evolucao semanal",
    "mensal": "Nivel 3 - evolucao mensal",
    "historica": "Nivel 4 - evolucao historica completa",
}

REGION_LAYOUT = [
    {
        "region_id": "cerebro_estrutural",
        "label": "Cerebro Estrutural",
        "x": 0.18,
        "y": 0.52,
        "base_neurons": 1700,
        "aliases": {"system", "runtime", "core", "general"},
    },
    {
        "region_id": "rede_neural_procedural",
        "label": "Rede Neural Procedural",
        "x": 0.35,
        "y": 0.32,
        "base_neurons": 1800,
        "aliases": {"study", "finance", "studio", "procedural"},
    },
    {
        "region_id": "campos_neurais_dinamicos",
        "label": "Campos Neurais Dinamicos",
        "x": 0.50,
        "y": 0.58,
        "base_neurons": 1600,
        "aliases": {"planner", "queue", "goal", "intent"},
    },
    {
        "region_id": "plasticidade_sinaptica",
        "label": "Plasticidade Sinaptica",
        "x": 0.66,
        "y": 0.30,
        "base_neurons": 1700,
        "aliases": {"memory", "semantic", "procedural_memory", "plasticity"},
    },
    {
        "region_id": "mapa_de_consciencia",
        "label": "Mapa de Consciencia",
        "x": 0.78,
        "y": 0.54,
        "base_neurons": 1500,
        "aliases": {"security", "self_defense", "policy", "audit"},
    },
    {
        "region_id": "mapa_evolutivo",
        "label": "Mapa Evolutivo",
        "x": 0.50,
        "y": 0.14,
        "base_neurons": 1700,
        "aliases": {"evolution", "history", "brain"},
    },
]

TRAIL_BLUEPRINTS = [
    ("cerebro_estrutural", "rede_neural_procedural"),
    ("rede_neural_procedural", "plasticidade_sinaptica"),
    ("plasticidade_sinaptica", "mapa_evolutivo"),
    ("campos_neurais_dinamicos", "mapa_evolutivo"),
    ("mapa_de_consciencia", "mapa_evolutivo"),
    ("cerebro_estrutural", "campos_neurais_dinamicos"),
]


@dataclass
class CognitiveEvolutionTracker:
    """Mantem o historico persistente do crescimento cognitivo do Jarvis."""

    storage_path: Path | None = field(default_factory=lambda: DEFAULT_STORAGE_PATH)
    auto_persist: bool = True
    events: List[Dict[str, Any]] = field(default_factory=list)
    last_updated_at: str | None = None

    def __post_init__(self) -> None:
        """Normaliza o caminho de persistencia logo apos a construcao."""

        if self.storage_path is not None:
            self.storage_path = Path(self.storage_path)

    def load_snapshot(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Carrega o historico evolutivo do arquivo ou de um snapshot fornecido.

        Parametros:
        - snapshot: payload opcional ja desserializado.

        Retorno:
        - snapshot normalizado do historico carregado.

        Efeitos no sistema:
        - atualiza a lista interna de eventos cognitivos.
        """

        if snapshot is None:
            if self.storage_path is None or not self.storage_path.exists():
                self.events = []
                self.last_updated_at = None
                return self._build_snapshot()
            snapshot = json.loads(self.storage_path.read_text(encoding="utf-8"))

        loaded_events = snapshot.get("events", [])
        self.events = [self._normalize_event(event) for event in loaded_events]
        self.last_updated_at = snapshot.get("last_updated_at")
        return self._build_snapshot()

    def snapshot(self) -> Dict[str, Any]:
        """
        Retorna e persiste o snapshot completo do historico evolutivo.

        Parametros:
        - nenhum.

        Retorno:
        - payload serializavel do historico cognitivo.

        Efeitos no sistema:
        - persiste o estado atual em disco.
        """

        snapshot = self._build_snapshot()
        if self.storage_path is not None:
            self._write_storage(snapshot)
        return snapshot

    def record_event(
        self,
        event_type: str,
        region: str,
        connections_created: int = 0,
        connections_strengthened: int = 0,
        estimated_cognitive_impact: float = 0.0,
        learning_type: Optional[str] = None,
        created_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Registra um novo evento de evolucao cognitiva.

        Parametros:
        - event_type: tipo do evento evolutivo.
        - region: regiao cerebral simulada envolvida.
        - connections_created: quantidade de novas conexoes estimadas.
        - connections_strengthened: quantidade de conexoes reforcadas.
        - estimated_cognitive_impact: score estimado de impacto cognitivo.
        - learning_type: tipo de aprendizado, quando quiser sobrescrever o padrao.
        - created_at: instante do evento, opcional.
        - metadata: dados tecnicos complementares.

        Retorno:
        - evento registrado e pronto para auditoria/API.

        Efeitos no sistema:
        - adiciona o evento ao historico e persiste quando configurado.
        """

        metadata_template = EVENT_METADATA.get(event_type, EVENT_METADATA["EVENT_NEW_KNOWLEDGE"])
        normalized_region = self._normalize_region(region)
        event = {
            "event_id": f"evolution-{len(self.events) + 1:05d}",
            "data_evento": created_at or self._utc_now(),
            "tipo_evento": event_type,
            "tipo_aprendizado": learning_type or metadata_template["tipo_aprendizado"],
            "regiao_cerebral": normalized_region["region_id"],
            "regiao_cerebral_ptbr": normalized_region["label"],
            "quantidade_conexoes_criadas": max(int(connections_created), 0),
            "quantidade_conexoes_reforcadas": max(int(connections_strengthened), 0),
            "impacto_cognitivo_estimado": round(float(max(estimated_cognitive_impact, 0.0)), 3),
            "cor_evento": metadata_template["cor"],
            "descricao_evento": metadata_template["descricao"],
            "metadata": deepcopy(metadata or {}),
        }
        self.events.append(event)
        self.last_updated_at = event["data_evento"]
        if self.auto_persist:
            self._write_storage()
        return deepcopy(event)

    def recent_events(self, level: str = "historica", limit: int = 20) -> List[Dict[str, Any]]:
        """Retorna eventos filtrados por nivel temporal, do mais novo para o mais antigo."""

        filtered_events = self._events_for_level(level)
        filtered_events.sort(key=lambda item: item["data_evento"], reverse=True)
        return [deepcopy(event) for event in filtered_events[: max(limit, 0)]]

    def build_visualization_payload(self, level: str = "historica") -> Dict[str, Any]:
        """
        Gera o payload pronto para a camada visual do brain avatar.

        Parametros:
        - level: faixa temporal desejada.

        Retorno:
        - dicionario com regioes, trilhas, indicadores visuais e resumo.

        Efeitos no sistema:
        - nenhum; apenas leitura e agregacao do historico.
        """

        normalized_level = self._normalize_level(level)
        filtered_events = self._events_for_level(normalized_level)
        region_metrics = self._build_region_metrics(filtered_events)
        trails = self._build_learning_trails(region_metrics)
        total_neurons = min(10000, sum(metric["logical_neurons"] for metric in region_metrics.values()))
        render_neurons = min(1600, max(240, total_neurons // 6 if total_neurons else 240))

        return {
            "mensagem": "Mapa evolutivo cognitivo preparado para visualizacao.",
            "nivel": normalized_level,
            "nivel_ptbr": LEVEL_LABELS_PTBR[normalized_level],
            "intervalo": self._build_interval_metadata(normalized_level, filtered_events),
            "eventos_considerados": len(filtered_events),
            "ultima_atualizacao": self.last_updated_at,
            "neuronios_simulados": total_neurons,
            "neuronios_renderizados": render_neurons,
            "regioes": list(region_metrics.values()),
            "trilhas_aprendizado": trails,
            "indicadores_visuais": {
                "aprendizado_novo": "#d4af37",
                "reforco_sinaptico": "#ffffff",
                "reestruturacao_de_rede": "#4cc9f0",
                "esquecimento_controlado": "#0a2342",
            },
            "resumo": self.build_summary(level=normalized_level),
        }

    def build_analysis(self, level: str = "historica") -> Dict[str, Any]:
        """
        Gera uma analise interna da evolucao cognitiva para introspeccao do Jarvis.

        Parametros:
        - level: recorte temporal a ser avaliado.

        Retorno:
        - analise consolidada das regioes e conexoes mais relevantes.

        Efeitos no sistema:
        - nenhum; somente processamento do historico carregado.
        """

        normalized_level = self._normalize_level(level)
        filtered_events = self._events_for_level(normalized_level)
        region_metrics = list(self._build_region_metrics(filtered_events).values())
        region_metrics.sort(key=lambda item: item["growth_score"], reverse=True)
        learning_trails = self._build_learning_trails({item["region_id"]: item for item in region_metrics})
        learning_trails.sort(key=lambda item: item["intensidade"], reverse=True)

        return {
            "mensagem": "Analise interna da evolucao cognitiva concluida.",
            "nivel": normalized_level,
            "nivel_ptbr": LEVEL_LABELS_PTBR[normalized_level],
            "resumo": self.build_summary(level=normalized_level),
            "regioes_mais_utilizadas": region_metrics[:3],
            "regioes_subutilizadas": list(reversed(region_metrics[-3:])),
            "conexoes_mais_fortes": learning_trails[:4],
            "conexoes_recem_formadas": [
                event
                for event in self.recent_events(level=normalized_level, limit=12)
                if event["quantidade_conexoes_criadas"] > 0
            ][:4],
            "conexoes_reforcadas_recentemente": [
                event
                for event in self.recent_events(level=normalized_level, limit=12)
                if event["quantidade_conexoes_reforcadas"] > 0
            ][:4],
        }

    def build_summary(self, level: str = "historica") -> Dict[str, Any]:
        """Resume o estado atual do historico cognitivo em um payload curto."""

        normalized_level = self._normalize_level(level)
        filtered_events = self._events_for_level(normalized_level)
        created_total = sum(event["quantidade_conexoes_criadas"] for event in filtered_events)
        strengthened_total = sum(event["quantidade_conexoes_reforcadas"] for event in filtered_events)
        impact_total = round(sum(event["impacto_cognitivo_estimado"] for event in filtered_events), 3)
        most_active_region = self._most_active_region(filtered_events)
        return {
            "nivel": normalized_level,
            "nivel_ptbr": LEVEL_LABELS_PTBR[normalized_level],
            "total_eventos": len(filtered_events),
            "conexoes_criadas": created_total,
            "conexoes_reforcadas": strengthened_total,
            "impacto_cognitivo_total": impact_total,
            "regiao_mais_ativa": most_active_region,
            "ultima_atualizacao": self.last_updated_at,
        }

    def _build_snapshot(self) -> Dict[str, Any]:
        """Monta o snapshot serializavel completo do historico evolutivo."""

        return {
            "version": "0.1.0",
            "last_updated_at": self.last_updated_at,
            "event_count": len(self.events),
            "events": [deepcopy(event) for event in self.events],
        }

    def _write_storage(self, snapshot: Optional[Dict[str, Any]] = None) -> None:
        """Persiste o historico cognitivo no arquivo configurado."""

        if self.storage_path is None:
            return
        payload = snapshot or self._build_snapshot()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.storage_path.with_name(f"{self.storage_path.name}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp_path, self.storage_path)

    def _normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza eventos carregados de snapshots antigos ou incompletos."""

        event_type = str(event.get("tipo_evento", "EVENT_NEW_KNOWLEDGE"))
        metadata_template = EVENT_METADATA.get(event_type, EVENT_METADATA["EVENT_NEW_KNOWLEDGE"])
        region = self._normalize_region(str(event.get("regiao_cerebral", "mapa_evolutivo")))
        return {
            "event_id": str(event.get("event_id", f"evolution-{len(self.events) + 1:05d}")),
            "data_evento": str(event.get("data_evento", self._utc_now())),
            "tipo_evento": event_type,
            "tipo_aprendizado": str(event.get("tipo_aprendizado", metadata_template["tipo_aprendizado"])),
            "regiao_cerebral": region["region_id"],
            "regiao_cerebral_ptbr": region["label"],
            "quantidade_conexoes_criadas": max(int(event.get("quantidade_conexoes_criadas", 0)), 0),
            "quantidade_conexoes_reforcadas": max(int(event.get("quantidade_conexoes_reforcadas", 0)), 0),
            "impacto_cognitivo_estimado": round(float(event.get("impacto_cognitivo_estimado", 0.0)), 3),
            "cor_evento": str(event.get("cor_evento", metadata_template["cor"])),
            "descricao_evento": str(event.get("descricao_evento", metadata_template["descricao"])),
            "metadata": deepcopy(event.get("metadata", {})),
        }

    def _normalize_level(self, level: str) -> str:
        """Normaliza a chave de nivel temporal usada nas consultas."""

        normalized = str(level or "historica").strip().lower()
        if normalized not in LEVEL_WINDOWS:
            return "historica"
        return normalized

    def _events_for_level(self, level: str) -> List[Dict[str, Any]]:
        """Filtra os eventos pelo nivel temporal solicitado."""

        normalized_level = self._normalize_level(level)
        window = LEVEL_WINDOWS[normalized_level]
        if window is None:
            return [deepcopy(event) for event in self.events]

        cutoff = datetime.now(timezone.utc) - window
        filtered_events: List[Dict[str, Any]] = []
        for event in self.events:
            event_time = self._parse_timestamp(event["data_evento"])
            if event_time >= cutoff:
                filtered_events.append(deepcopy(event))
        return filtered_events

    def _normalize_region(self, region: str) -> Dict[str, Any]:
        """Resolve um identificador arbitrario para uma das regioes cognitivas conhecidas."""

        normalized = str(region or "mapa_evolutivo").strip().lower()
        for region_definition in REGION_LAYOUT:
            aliases = region_definition.get("aliases", set())
            if normalized == region_definition["region_id"] or normalized in aliases:
                return deepcopy(region_definition)
        return deepcopy(REGION_LAYOUT[-1])

    def _build_region_metrics(self, filtered_events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Agrega score, brilho e volume de neuronios por regiao."""

        region_metrics: Dict[str, Dict[str, Any]] = {}
        for region in REGION_LAYOUT:
            region_metrics[region["region_id"]] = {
                "region_id": region["region_id"],
                "label": region["label"],
                "x": region["x"],
                "y": region["y"],
                "event_count": 0,
                "connections_created": 0,
                "connections_strengthened": 0,
                "cognitive_impact_total": 0.0,
                "growth_score": 0.0,
                "glow_intensity": 0.18,
                "logical_neurons": min(region["base_neurons"], 10000),
                "render_weight": 0.5,
            }

        for event in filtered_events:
            metric = region_metrics[event["regiao_cerebral"]]
            metric["event_count"] += 1
            metric["connections_created"] += event["quantidade_conexoes_criadas"]
            metric["connections_strengthened"] += event["quantidade_conexoes_reforcadas"]
            metric["cognitive_impact_total"] = round(
                metric["cognitive_impact_total"] + event["impacto_cognitivo_estimado"],
                3,
            )

        for region in REGION_LAYOUT:
            metric = region_metrics[region["region_id"]]
            growth_score = (
                metric["connections_created"] * 1.4
                + metric["connections_strengthened"] * 1.8
                + metric["cognitive_impact_total"] * 12
                + metric["event_count"] * 2
            )
            metric["growth_score"] = round(growth_score, 3)
            metric["glow_intensity"] = round(min(1.0, 0.18 + (growth_score / 120 if growth_score else 0.0)), 3)
            metric["logical_neurons"] = min(10000, region["base_neurons"] + int(growth_score * 18))
            metric["render_weight"] = round(min(1.0, 0.2 + metric["glow_intensity"]), 3)
        return region_metrics

    def _build_learning_trails(self, region_metrics: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Monta trilhas de aprendizado entre regioes relacionadas do cerebro cognitivo."""

        trails: List[Dict[str, Any]] = []
        for source_id, target_id in TRAIL_BLUEPRINTS:
            source = region_metrics[source_id]
            target = region_metrics[target_id]
            intensity = round(
                max(source["growth_score"], 0) * 0.35 + max(target["growth_score"], 0) * 0.65,
                3,
            )
            thickness = round(1.0 + min(8.0, intensity / 18 if intensity else 0.0), 3)
            trails.append(
                {
                    "trail_id": f"{source_id}->{target_id}",
                    "source": source_id,
                    "source_label": source["label"],
                    "target": target_id,
                    "target_label": target["label"],
                    "intensidade": intensity,
                    "espessura": thickness,
                    "cor": "#d4af37" if intensity > 0 else "#3e4a61",
                }
            )
        return trails

    def _build_interval_metadata(
        self,
        level: str,
        filtered_events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Resume o intervalo temporal coberto pelo recorte solicitado."""

        if not filtered_events:
            return {
                "inicio": None,
                "fim": None,
                "nivel_ptbr": LEVEL_LABELS_PTBR[self._normalize_level(level)],
            }
        ordered = sorted(filtered_events, key=lambda item: item["data_evento"])
        return {
            "inicio": ordered[0]["data_evento"],
            "fim": ordered[-1]["data_evento"],
            "nivel_ptbr": LEVEL_LABELS_PTBR[self._normalize_level(level)],
        }

    def _most_active_region(self, filtered_events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Retorna a regiao com maior score no recorte informado."""

        if not filtered_events:
            return None
        region_metrics = list(self._build_region_metrics(filtered_events).values())
        region_metrics.sort(key=lambda item: item["growth_score"], reverse=True)
        return region_metrics[0]

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        """Converte timestamps ISO para `datetime` com timezone UTC."""

        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _utc_now() -> str:
        """Retorna o instante atual em UTC, serializado em ISO 8601."""

        return datetime.now(timezone.utc).isoformat()
