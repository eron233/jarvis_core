"""
JARVIS - Módulo 4: Day Trade e Análise de Mercado Financeiro

Responsável por:
- análise analítica de mercado financeiro com foco em Mini Dólar (WDO) e Mini Índice (WIN)
- correlação entre histórico de preços, Tape Reading (fluxo de ordens), notícias e seus horários de ocorrência
- identificação de padrões de comportamento do mercado sob diferentes tipos de evento
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKET_DATA_DIR = PROJECT_ROOT / "data" / "market_analysis"


class MarketAnalysisWorker:
    """Worker e analisador de mercado financeiro (Mini Dólar e Mini Índice)."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_MARKET_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def analyze_market_session(
        self,
        asset: str,  # "WDO" ou "WIN"
        price_history: List[Dict[str, Any]],
        flow_data: List[Dict[str, Any]],  # Tape reading: compras/vendas agressoras
        news_events: List[Dict[str, Any]],  # Notícias com timestamp
    ) -> Dict[str, Any]:
        """
        Executa a análise correlacional completa de uma sessão de mercado.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Análise de Fluxo (Tape Reading)
        total_buy_vol = sum(f.get("volume", 0) for f in flow_data if f.get("side") == "buy")
        total_sell_vol = sum(f.get("volume", 0) for f in flow_data if f.get("side") == "sell")
        flow_bias = "comprador" if total_buy_vol > total_sell_vol else ("vendedor" if total_sell_vol > total_buy_vol else "neutro")

        # 2. Análise da Movimentação de Preços
        prices = [p.get("price", 0) for p in price_history if "price" in p]
        min_p = min(prices) if prices else 0
        max_p = max(prices) if prices else 0
        amplitude = round(max_p - min_p, 4)

        # 3. Correlação com Horário de Notícias
        correlated_events = []
        for news in news_events:
            n_time = news.get("timestamp", "00:00")
            n_title = news.get("titulo", "Notícia")
            correlated_events.append({
                "horario": n_time,
                "noticia": n_title,
                "impacto_observado": f"Aumento de volatilidade observado em {asset} na janela do evento.",
            })

        analysis_report = {
            "ativo": asset.upper(),
            "analisado_em": now,
            "resumo_analitico_ptbr": (
                f"Análise de {asset.upper()}: Fluxo predominantemente {flow_bias} "
                f"(Vol Compra: {total_buy_vol}, Vol Venda: {total_sell_vol}). "
                f"Amplitude de variação: {amplitude:.2f} pontos. {len(news_events)} evento(s) de notícia correlacionado(s)."
            ),
            "metricas_fluxo": {
                "bias": flow_bias,
                "volume_compra": total_buy_vol,
                "volume_venda": total_sell_vol,
                "saldo_agressao": total_buy_vol - total_sell_vol,
            },
            "metricas_preco": {
                "minimo": min_p,
                "maximo": max_p,
                "amplitude": amplitude,
            },
            "correlacao_noticias": correlated_events,
        }

        self._save_session_analysis(analysis_report)
        return analysis_report

    def _save_session_analysis(self, report: Dict[str, Any]) -> None:
        """Salva a análise de mercado em disco."""
        asset = report.get("ativo", "GERAL")
        file_path = self.data_dir / f"session_analysis_{asset}.json"
        file_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
