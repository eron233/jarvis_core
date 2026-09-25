"""
JARVIS - Módulo 6: Análise, Configuração e Perfil do Dispositivo

Responsável por:
- realizar leitura completa de hardware, componentes e características físicas do dispositivo
- simular internamente em sandbox otimizações antes de qualquer aplicação real
- construir um perfil de uso do usuário (jogos, redes sociais, produtividade, música)
- recomendar otimizações sem causar danos ao equipamento, com decisão final do usuário
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILER_DIR = PROJECT_ROOT / "data" / "device_profile"


class DeviceProfiler:
    """Analisador de hardware, construtor de perfil de utilização e simulador de otimizações."""

    def __init__(self, profiler_dir: Optional[Path] = None) -> None:
        self.profiler_dir = Path(profiler_dir) if profiler_dir else DEFAULT_PROFILER_DIR
        self.profiler_dir.mkdir(parents=True, exist_ok=True)

    def analyze_device_and_profile(
        self,
        installed_apps: Optional[List[str]] = None,
        observed_usages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Coleta dados de hardware, mapeia o perfil de utilização e gera recomendações com simulação prévia.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Leitura de Hardware e Sistema
        hardware_info = {
            "sistema_operacional": platform.system(),
            "versao_so": platform.version(),
            "arquitetura": platform.architecture()[0],
            "processador": platform.processor() or "Desconhecido",
            "cpus_logicos": os.cpu_count() or 1,
        }

        # 2. Perfil de Utilização do Usuário
        apps = installed_apps or ["Steam", "Discord", "Spotify", "Telegram", "VS Code"]
        usages = observed_usages or ["Jogos", "Redes Sociais", "Programacao", "Musica"]

        user_profile = {
            "aplicativos_detectados": apps,
            "foco_uso_principal": usages[0] if usages else "Geral",
            "categorias_frequentes": usages,
        }

        # 3. Recomendações de Otimização (SUGESTÕES, sem simulação ativa de ganhos)
        # Nenhuma medição real de latência/FPS/temperatura é executada aqui.
        # Por isso não se afirma nenhum número de ganho: cada item é uma sugestão
        # textual que depende de aprovação e execução explícita do usuário.
        raw_recommendations = [
            {
                "parametro": "Plano de Energia",
                "sugestao": "Alto Desempenho",
                "justificativa": "Planos de energia de alto desempenho tendem a reduzir limitação de clock em notebooks/desktops.",
                "risco": "baixo",
            },
            {
                "parametro": "Processos em Segundo Plano",
                "sugestao": "Otimizar inicializacao automatica",
                "justificativa": "Menos processos em segundo plano tende a liberar CPU/RAM, mas o efeito varia por máquina.",
                "risco": "baixo",
            },
            {
                "parametro": "Alocacao de Memoria Cache",
                "sugestao": "Ajustar tamanho da pagina de memoria",
                "justificativa": "Ajustes de memória virtual podem ajudar em cenários de RAM limitada, mas dependem do uso real.",
                "risco": "baixo",
            },
        ]

        simulated_optimizations = []
        for rec in raw_recommendations:
            simulated_optimizations.append({
                "parametro": rec["parametro"],
                "sugestao": rec["sugestao"],
                "nivel_risco": rec["risco"],
                "justificativa": rec["justificativa"],
                "impacto_estimado": "não medido - nenhuma simulação ativa foi executada",
                "aprovacao_usuario_requerida": True,
            })

        profile_report = {
            "dispositivo_id": platform.node(),
            "analisado_em": now,
            "hardware": hardware_info,
            "perfil_usuario": user_profile,
            "otimizacoes_simuladas": simulated_optimizations,
            "status_simulacao": "recomendacoes_geradas_sem_simulacao_ativa",
        }

        self._save_profile(profile_report)
        return profile_report

    def _save_profile(self, profile: Dict[str, Any]) -> None:
        """Salva o relatório de perfil em disco."""
        file_path = self.profiler_dir / "current_device_profile.json"
        file_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
